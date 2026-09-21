import pathlib,json,numpy as np,sys
from scipy.spatial.transform import Rotation as R
p=pathlib.Path(__file__).resolve().parent
old=json.loads((p.parents[1]/'Benchmarks/jolt_scope_rig_32channels_20260909_0819.json').read_text())
j=next(x for x in old['passes'][0]['before']['effective_rig']['constraints'] if x['child']=='hand_l')
f0=R.from_quat(j['parent_frame']['quaternion_xyzw']);f1=R.from_quat(j['child_frame']['quaternion_xyzw'])
d=json.loads((p/((sys.argv[1] if len(sys.argv)>1 else 'baseline')+'.json')).read_text())
def decomp(q):
    if q[3]<0:q=-q
    twist=np.array([q[0],0.,0.,q[3]]);twist/=np.linalg.norm(twist)
    swing=(R.from_quat(q)*R.from_quat(twist).inv()).as_quat()
    return np.degrees([2*np.arctan2(twist[0],twist[3]),2*np.arcsin(swing[1]),2*np.arcsin(swing[2])])
for row in d['rows']:
    if row['actor'].endswith('_1') and 8.90<row['t']<9.05:
        bones=row['bones']; qs=[]
        for key in ('q','target'):
            rel=((R.from_quat(bones['lowerarm_l'][key])*f0).inv()*R.from_quat(bones['hand_l'][key])*f1).as_quat()
            qs.append(np.round(decomp(rel),2).tolist())
        print(round(row['t'],4),qs)
