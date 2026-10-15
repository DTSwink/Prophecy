"""Fit retained PHAT profiles to accepted omni references plus angular margin.

Read-only: produces a reviewed change plan, never writes assets or motions.
Swing uses the coupled Jolt ellipse, not independent Euler maxima.
"""
import hashlib
import json
import pickle
import sys
from pathlib import Path
import numpy as np
from scipy.optimize import minimize, LinearConstraint, Bounds
from scipy.spatial.transform import Rotation as R, Slerp

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit'))
from anim.mjcf_char_model import MJCFCharModel
from test_model import coords, violation


def sampled_coordinates(model, joint, frames, subdivisions):
    k=model.get_joint(model.get_body_names().index(joint['body']))
    width=3 if joint['kind']=='ball' else 1
    a=frames[:,6+k.dof_idx:6+k.dof_idx+width]
    times=np.arange(len(a))
    query=np.linspace(0,len(a)-1,(len(a)-1)*subdivisions+1)
    if width==3:
        delta=Slerp(times,R.from_rotvec(a))(query)
    else:
        delta=R.from_rotvec(np.column_stack((np.zeros((len(query),2)),np.interp(query,times,a[:,0]))))
    reference=R.from_quat(np.array(joint['reference_wxyz'])[[1,2,3,0]])
    if width==1:
        # Same exact one-axis hinge convention as test_model.test_jolt.
        rv=reference.as_rotvec();assert np.linalg.norm(rv[:2])<1e-5
        reference=R.from_rotvec([0,0,rv[2]])
    q=(reference*delta).as_quat()[:,[3,0,1,2]]
    return coords(q), q


def inflate(v, margin):
    result=v.copy();result[:,0]*=margin
    radius=np.linalg.norm(v[:,1:],axis=1)
    angle=np.arcsin(np.clip(radius,0,1))*margin
    assert np.max(angle)<np.pi/2 and np.max(abs(result[:,0]))<np.pi, 'Motion + margin exceeds 180 degrees'
    result[:,1:]*=np.divide(np.sin(angle),radius,out=np.ones_like(radius),where=radius>1e-12)[:,None]
    return result


def fit(joint, v, margin=1.05):
    wanted=inflate(v,margin)
    modes=np.array(joint['modes']);old=np.array(joint['limits_rad']);new=old.copy()
    # Ignore only the exported fixed-axis rounding residue (under 0.001 deg).
    for axis in range(3):
        if modes[axis]==2 and np.max(abs(v[:,axis]))>1e-5:
            assert joint['kind']=='ball', 'A hinge reference contains unsupported extra articulation'
            modes[axis]=1;new[axis]=0
    if modes[0]==1:new[0]=max(new[0],np.max(abs(wanted[:,0])))
    if modes[1]==modes[2]==1:
        # Minimum-area containing ellipse, bounded below by the old ellipse.
        # Optimize inverse squared axes: linear feasibility, convex objective.
        scale=np.maximum(abs(wanted[:,1:]).max(0),1e-8)
        c=(wanted[:,1:]/scale)**2
        upper=np.minimum(1.,(scale/np.maximum(np.sin(new[1:]/2),1e-8))**2)
        lower=scale**2
        start=upper/max(1.,np.max(c@upper))*0.999999
        result=minimize(lambda x:-np.log(x).sum(),start,jac=lambda x:-1/x,
                        constraints=LinearConstraint(c,-np.inf,1),bounds=Bounds(lower,upper),
                        method='SLSQP',options=dict(ftol=1e-11,maxiter=1000))
        assert result.success and np.max(c@result.x)<=1+1e-7,result.message
        new[1:]=2*np.arcsin(np.clip(scale/np.sqrt(result.x),0,1))
    else:
        for axis in (1,2):
            if modes[axis]==1:new[axis]=max(new[axis],2*np.arcsin(np.max(abs(wanted[:,axis]))))
    degrees=np.rad2deg(new)
    changed=(modes!=np.array(joint['modes'])) | (new>old+1e-8)
    degrees[changed]=np.ceil(degrees[changed]*100)/100
    fitted=dict(joint,modes=modes.tolist(),limits_rad=np.deg2rad(degrees).tolist())
    assert not violation(wanted,fitted).any(), (joint['body'],wanted[violation(wanted,fitted)][:5].tolist(),fitted['modes'],degrees.tolist())
    return dict(source_joint=joint['source_joint'],source_body=joint['source_body'],body=joint['body'],
                old_modes=joint['modes'],new_modes=modes.tolist(),
                old_degrees=np.rad2deg(old).tolist(),new_degrees=degrees.tolist(),
                changed=bool(changed.any()),outside_before=int(violation(v,joint).sum()),
                samples=len(v),outside_after=int(violation(v,fitted).sum()),
                outside_with_margin=int(violation(wanted,fitted).sum()))


def main():
    meta=json.loads((HERE/'limits.json').read_text())
    manifest=json.loads((ROOT/'Saved/MimicKitUEFN/omni/manifest.json').read_text())
    model=MJCFCharModel('cpu');model.load(str(HERE/'humanoid_uefn.xml'))
    clips=[];fingerprints={}
    for item in manifest['motions']:
        path=ROOT/'Saved/MimicKitUEFN/omni'/f"{item['id']}.pkl"
        content=path.read_bytes();clips.append(pickle.loads(content)['frames'])
        fingerprints[path.name]=hashlib.sha256(content).hexdigest()
    assert len(clips)==26
    rows=[]
    for j in meta['joints']:
        v=np.concatenate([sampled_coordinates(model,j,f,16)[0] for f in clips])
        row=fit(j,v);rows.append(row)
        # Independent denser sampling checks the intervals between source frames.
        dense=np.concatenate([sampled_coordinates(model,j,f,128)[0] for f in clips])
        fitted=dict(j,modes=row['new_modes'],limits_rad=np.deg2rad(row['new_degrees']).tolist())
        assert not violation(inflate(dense,1.05),fitted).any(),j['body']
        row['dense_verified_samples']=len(dense)
    report=dict(margin_factor=1.05,clips=len(clips),motion_sha256=fingerprints,
                source_files=meta['source_files'],limits_sha256=hashlib.sha256((HERE/'limits.json').read_bytes()).hexdigest(),
                method='Minimum-area coupled swing ellipse containing 1.05x angular excursions; never shrink existing limits; round outward to 0.01 degree.',joints=rows)
    path=ROOT/'Saved/MimicKitUEFN/omni-limit-plan.json'
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    for row in rows:
        if row['changed']:print(row['body'],row['old_degrees'],'->',row['new_degrees'],row['old_modes'],'->',row['new_modes'])
    print('Verified',len(clips),'clips;',sum(r['dense_verified_samples'] for r in rows),'joint samples')


if __name__=='__main__':main()
