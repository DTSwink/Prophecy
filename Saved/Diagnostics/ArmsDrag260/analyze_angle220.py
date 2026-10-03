from pathlib import Path
import json,re,math
import numpy as np
from scipy.spatial.transform import Rotation as R
p=Path(__file__).parent
m=re.search(r'WristIdleReference q=([\d.,-]+) axis=([\d.,-]+)',(p/'wrap_angle220_before.log').read_text(encoding='utf-8'))
idle_q=R.from_quat([float(x) for x in m[1].split(',')]);up=np.array([float(x) for x in m[2].split(',')]);up/=np.linalg.norm(up)
report={}
for tag in ('wrap_angle220_before','wrap_angle220_off_wrist','wrap_angle220_recoil60'):
 d=json.loads((p/(tag+'.json')).read_text(encoding='utf-8'));assert not d['error'],d['error']
 rr=[r for r in d['rows'] if r['player']];assert len(rr)==400
 axis=R.from_quat(rr[0]['weapon']['grip']['q']).apply([0,0,1]);idle=idle_q.apply(axis);forward=idle-up*np.dot(idle,up);forward/=np.linalg.norm(forward)
 out=[]
 for row in rr:
  f=row['presented'];sp=R.from_quat(f['spine_05']['q']);q=sp.inv()*R.from_quat(f['hand_r']['q']);world=R.from_quat(row['weapon']['actual']['q']).apply([0,0,1]);aim=sp.inv().apply(world)
  yaw=math.degrees(math.atan2(np.dot(up,np.cross(forward,aim)),np.dot(forward,aim)))
  el=math.degrees(math.asin(np.clip(np.dot(aim,up),-1,1)));error=math.degrees(math.acos(np.clip(np.dot(idle,aim),-1,1)))
  out.append(dict(tick=row['tick'],yaw=yaw,spine_elevation=el,idle_error=error,world_elevation=math.degrees(math.asin(np.clip(world[2],-1,1))),idle_world_elevation=math.degrees(math.asin(np.clip(sp.apply(idle)[2],-1,1))),quaternion=q.as_quat().tolist(),position=f['hand_r']['p']))
 report[tag]=dict(samples=[r for r in out if r['tick'] in (191,210,220,227,230,240,250,260,270,280,281,290,300,310,311,312)],first_inside5=next((r['tick'] for r in out if r['tick']>=191 and r['idle_error']<=5),None),min_error_hold=min(r['idle_error'] for r in out if 191<=r['tick']<=281),rows=out)
 print(tag,json.dumps({k:v for k,v in report[tag].items() if k!='rows'}))
baseline=report['wrap_angle220_before']['rows'];raw=report['wrap_angle220_off_wrist']['rows'];boost=report['wrap_angle220_recoil60']['rows']
report['position_difference_cm']=dict(off=max(math.dist(x['position'],y['position']) for x,y in zip(baseline,raw)),boost=max(math.dist(x['position'],y['position']) for x,y in zip(baseline,boost)))
print('positions',report['position_difference_cm'])
(p/'angle220_diagnosis.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
