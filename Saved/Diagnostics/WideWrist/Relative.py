import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path(__file__).resolve().parent
audit=json.loads((p.parents[1]/'Benchmarks/jolt_scope_rig_32channels_20260909_0819.json').read_text())
j=next(j for j in audit['passes'][0]['before']['effective_rig']['constraints'] if j['child']=='hand_r')
f=R.from_quat(j['parent_frame']['quaternion_xyzw']);g=R.from_quat(j['child_frame']['quaternion_xyzw'])
for mode in ('current','free','twist_only','swing_only'):
    rows=[x for x in json.loads((p/(mode+'.json')).read_text())['rows'] if x['actor'].endswith('_1')]
    q=R.from_quat([x['bones']['hand_r']['q'] for x in rows]);par=R.from_quat([x['bones']['lowerarm_r']['q'] for x in rows])
    rel=((par*f).inv()*q*g).as_quat()
    principal=np.degrees(2*np.arctan2(rel[:,0],rel[:,3])); principal=(principal+180)%360-180
    amplitude=np.sqrt(rel[:,0]**2+rel[:,3]**2)
    swing=np.degrees(2*np.arccos(np.clip(amplitude,0,1)))
    winding=np.degrees(np.unwrap(np.radians(principal)))
    err=np.degrees((R.from_quat([x['bones']['lowerarm_r']['q'] for x in rows]).inv()*R.from_quat([x['bones']['lowerarm_r']['target'] for x in rows])).magnitude())
    print(mode,'wrist twist max',round(abs(principal).max(),2),'swing max',round(swing.max(),2),'unwrapped span',round(np.ptp(winding),2),'minimum twist decomposition norm',round(amplitude.min(),3))
    for index in np.where(err>20)[0][:4]:
        print('  first error',round(rows[index]['t'],3),'forearm_error',round(err[index],2),'twist',round(principal[index],2),'previous_twist',round(principal[index-1],2))
