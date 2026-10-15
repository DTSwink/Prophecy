"""Read-only first-divergence audit of saved matched-state native/MJ trials."""
from pathlib import Path
import json,sys,xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial.transform import Rotation as R

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'Saved/MimicKitTransfer/no-armature-3913'
OUT=BASE/'causal_transfer'
asset=BASE/'source/assets/uefn'
nodes=list(ET.parse(asset/'humanoid_uefn.xml').getroot().find('worldbody').iter('body'))
names=[n.attrib['name'] for n in nodes]
meta=json.loads((asset/'limits.json').read_text())


def limit_envelope(state):
    result=[]
    for i,j in enumerate(meta['joints'],1):
        parent=names.index(j['parent']);local=R.from_quat(np.roll(np.fromstring(nodes[i].attrib.get('quat','1 0 0 0'),sep=' '),-1))
        ref=R.from_quat(np.array(j['reference_wxyz'])[[1,2,3,0]])
        delta=local.inv()*R.from_quat(state[parent,3:7]).inv()*R.from_quat(state[i,3:7])
        x,y,z,w=(ref*delta).as_quat();n=max(np.hypot(w,x),1e-12)
        twist=(2*np.arctan2(x,w)+np.pi)%(2*np.pi)-np.pi
        sy=(w*y-x*z)/n;sz=(x*y+w*z)/n
        limit=j['limits_rad'];modes=j['modes']
        swing=np.sqrt((sy/np.sin(limit[1]/2))**2+(sz/np.sin(limit[2]/2))**2) if modes[1]==modes[2]==1 else 0.
        result.append(dict(body=j['body'],twist_excess_deg=float(np.degrees(max(0,abs(twist)-limit[0]))) if modes[0]==1 else 0.,
                           swing_envelope_ratio=float(swing)))
    return sorted(result,key=lambda r:max(r['twist_excess_deg']/10,r['swing_envelope_ratio']-1),reverse=True)


def main(world=9,tag='point'):
    with np.load(OUT/'body_velocity_engine_cuda_0_worlds16.npz') as z:m={k:z[k] for k in z.files}
    path=OUT/('body_velocity_engine_cuda_0_worlds16_self0_native_v40p8'+('_'+tag if tag else '')+'.npz')
    with np.load(path) as z:n=z['world'+str(world)];a=z['actions'+str(world)]
    records=[]
    for tick,state in enumerate(n):
        ref=m['states'][tick,world].copy();ref[:,:2]+=state[0,:2]-ref[0,:2]
        pe=np.linalg.norm(state[:,:3]-ref[:,:3],axis=1)
        re=np.degrees((R.from_quat(state[:,3:7]).inv()*R.from_quat(ref[:,3:7])).magnitude())
        ve=np.linalg.norm(state[:,10:13]-ref[:,10:13],axis=1)
        row=dict(tick=tick,max_position_m=float(max(pe)),max_rotation_deg=float(max(re)),
            worst_angular_velocity=[dict(body=names[i],error_rad_s=float(ve[i]),position_m=float(pe[i]),rotation_deg=float(re[i])) for i in np.argsort(ve)[-3:][::-1]],
            native_limits=limit_envelope(state)[:2],mj_limits=limit_envelope(ref)[:2])
        if tick:row['action_max_difference']=float(abs(a[tick-1]-m['actions'][tick,world]).max())
        records.append(row)
    result=dict(world=world,phase=world/16,profile=tag,records=records)
    (OUT/f'divergence_world{world}_{tag or "manifold"}.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__':main(int(sys.argv[1]) if len(sys.argv)>1 else 9,sys.argv[2] if len(sys.argv)>2 else 'point')
