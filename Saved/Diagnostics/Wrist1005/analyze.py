import json,pathlib,numpy as np,re
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics/RunHandThigh')
def read(tag):
 d=json.loads((p/(tag+'.json')).read_text());assert not d['error'],d['error'];return {r['tick']:r for r in d['rows']}
old=read('wrist1005_base');new=read('wrist1005_fixed')
axis=R.from_quat(old[1005]['weapon']['grip']['q']).apply([0,0,1])
def yaw(r,kind='future',sword=False):
 pose=r[kind];up=np.array(pose['neck_01']['p'])-pose['pelvis']['p'];up/=np.linalg.norm(up)
 right=np.array(pose['upperarm_r']['p'])-pose['upperarm_l']['p'];right-=up*np.dot(right,up);right/=np.linalg.norm(right)
 forward=np.cross(right,up);aim=R.from_quat(r['weapon']['actual']['q']).apply([0,0,1]) if sword else R.from_quat(pose['hand_r']['q']).apply(axis)
 return float(np.arctan2(np.dot(aim,right),np.dot(aim,forward)))
report={}
for name,rows in [('before',old),('after',new)]:
 ticks=list(range(997,1036,2));y=np.degrees(np.unwrap([yaw(rows[t]) for t in ticks]))
 q=[R.from_quat(rows[t]['future']['hand_r']['q']) for t in ticks]
 turns=[float(np.degrees((b*a.inv()).magnitude())) for a,b in zip(q,q[1:])]
 report[name]=dict(samples=[dict(tick=t,torso_yaw=float(v)) for t,v in zip(ticks,y)],yaw_travel=float(np.abs(np.diff(y)).sum()),max_hand_rotation_step=max(turns))
 physical_ticks=list(range(997,1060,2));physical=np.degrees(np.unwrap([yaw(rows[t],'mesh',True) for t in physical_ticks]))
 report[name]['physical_sword_yaw_travel']=float(np.abs(np.diff(physical)).sum())
 report[name]['physical_sword_samples']=[dict(tick=t,torso_yaw=float(v)) for t,v in zip(physical_ticks,physical)]
report['before_999_hand_target_max_cm']=max(float(np.linalg.norm(np.array(old[t]['future']['hand_r']['p'])-new[t]['future']['hand_r']['p'])) for t in old if t<999)
report['before_999_hand_rotation_max_deg']=max(float(np.degrees((R.from_quat(old[t]['future']['hand_r']['q']).inv()*R.from_quat(new[t]['future']['hand_r']['q'])).magnitude())) for t in old if t<999)
log=(p/'wrist1005_fixed.log').read_text()
report['routes']=re.findall(r'ReturnSwordRoute[^\n]*',log)
report['current_release']=next(line for line in report['routes'] if 'time=16.649999' in line)
assert 'goal=0.000000' in report['current_release'],report['current_release']
assert report['after']['yaw_travel']<90,report['after']
assert report['after']['physical_sword_yaw_travel']<100,report['after']['physical_sword_yaw_travel']
assert all('goal=0.000000' in line for line in report['routes']),report['routes']
assert report['before_999_hand_target_max_cm']<.01,report['before_999_hand_target_max_cm']
assert report['before_999_hand_rotation_max_deg']<.05,report['before_999_hand_rotation_max_deg']
(p/'wrist1005_verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
