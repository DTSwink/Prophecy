"""Jolt limit axes: independent world-space construction versus GPU local rows."""
import os,json,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['MIMICKIT_TRANSFER_OUT']=str(ROOT/'Saved/MimicKitTransfer/no-armature-3913')
import probe
import numpy as np,warp as wp
from scipy.spatial.transform import Rotation as R
from jolt_limit_directions import directions
from probe_limit_projection import clamp_swing_twist


@wp.kernel(enable_backward=False)
def evaluate(q:wp.array(dtype=wp.quat),limits:wp.array(dtype=wp.vec3),out:wp.array2d(dtype=float)):
    i=wp.tid();tw,sw,tg,sg=directions(q[i],limits[i])
    out[i,0]=float(tw);out[i,1]=float(sw)
    for k in range(3):out[i,2+k]=tg[k];out[i,5+k]=sg[k]


def main():
    folder=ROOT/'Labs/MimicKitUEFN';meta=json.loads((folder/'limits.json').read_text())
    xml={n.attrib['name']:n for n in ET.parse(folder/'humanoid_uefn.xml').iter('body')}
    rng=np.random.default_rng(621);rotations=[];limits=[];expected=[];cross_lengths=[]
    for joint in meta['joints']:
        if joint['kind']!='ball':continue
        parent0=R.from_quat(meta['body_frames'][joint['parent']]['quaternion'])
        frame=parent0.inv()*R.from_quat(joint['source_parent_frame']['quaternion'])
        base=R.from_quat(np.roll(np.fromstring(xml[joint['body']].attrib.get('quat','1 0 0 0'),sep=' '),-1))
        for _ in range(24):
            parent=R.random(random_state=rng);local=R.from_rotvec(rng.normal(0,.55,3))
            child=parent*base*local;parent_frame=parent*frame
            relative=parent_frame.inv()*child
            ref=R.from_quat(np.roll(joint['reference_wxyz'],-1))*local
            assert (relative.inv()*ref).magnitude()<1e-10
            q=relative.as_quat();twist=np.array([q[0],0.,0.,q[3]]);twist/=np.linalg.norm(twist)
            if twist[3]<0:twist=-twist
            swing=relative*R.from_quat(twist).inv();s=swing.as_quat()
            if s[3]<0:s=-s
            a=np.asarray(joint['limits_rad']);tw=abs(twist[0])>np.sin(a[0]/2)
            sw=np.sum((s[1:3]/np.sin(a[1:]/2))**2)>1
            clamped=clamp_swing_twist(q,a)
            current=(parent_frame*swing).apply([1,0,0]);desired=(parent_frame*clamped).apply([1,0,0])
            axis=np.cross(desired,current);length=np.linalg.norm(axis)
            sg=-child.inv().apply(axis/length) if length>0 else np.zeros(3)
            tg=-np.sign(twist[0])*child.inv().apply(current)
            rotations.append(q);limits.append(a);expected.append([float(tw),float(sw),*tg,*sg]);cross_lengths.append(length)
    wp.init();wp.set_device('cuda:0');output=wp.zeros((len(rotations),8),device='cuda:0')
    wp.launch(evaluate,dim=len(rotations),inputs=[wp.array(rotations,dtype=wp.quat,device='cuda:0'),
        wp.array(limits,dtype=wp.vec3,device='cuda:0'),output],device='cuda:0')
    actual=output.numpy();expected=np.asarray(expected)
    np.testing.assert_array_equal(actual[:,:2],expected[:,:2])
    # Inactive axes can have undefined directions due to zero-length cross
    # products; only active unilateral rows are meaningful.
    tw=expected[:,0].astype(bool);sw=expected[:,1].astype(bool)
    np.testing.assert_allclose(actual[tw,2:5],expected[tw,2:5],atol=2e-5,rtol=0)
    # Normalizing a nearly zero cross product amplifies float32 round-off at
    # the cone boundary. Bound the unnormalized error too, rather than treating
    # every angular excursion as equally well-conditioned.
    swing_error=abs(actual[sw,5:]-expected[sw,5:])
    np.testing.assert_allclose(actual[sw,5:],expected[sw,5:],atol=1e-4,rtol=0)
    assert float((swing_error*np.asarray(cross_lengths)[sw,None]).max())<1e-6
    report=dict(cases=len(rotations),active_twist=int(tw.sum()),active_swing=int(sw.sum()),
        max_twist_axis_error=float(abs(actual[tw,2:5]-expected[tw,2:5]).max()),
        max_swing_axis_error=float(swing_error.max()),
        max_unnormalized_swing_error=float((swing_error*np.asarray(cross_lengths)[sw,None]).max()),
        world_frame_construction_verified=True)
    print(json.dumps(report),flush=True)
    (probe.OUT/'causal_transfer/jolt_limit_directions.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':main()
