import json, math, sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
p=Path(__file__).parent
tag=sys.argv[1]
d=json.loads((p/(tag+'.json')).read_text())
out=[]
for row in d['rows']:
 if not row['player']: continue
 w=row['weapon']; lo=np.array(w['lo']); hi=np.array(w['hi']); axis=np.argmax(hi-lo)
 a=(lo+hi)/2; b=a.copy(); a[axis]=lo[axis]; b[axis]=hi[axis]
 grip=R.from_quat(w['grip']['q']); a=grip.apply(a*w['scale'])+w['grip']['p']; b=grip.apply(b*w['scale'])+w['grip']['p']
 if np.linalg.norm(a)>np.linalg.norm(b): a,b=b,a
 pose=row['future']; h=pose['hand_r']; q=R.from_quat(h['q']); a=q.apply(a)+h['p']; b=q.apply(b)+h['p']; blade=(b-a)/np.linalg.norm(b-a)
 torso=(np.array(pose['upperarm_l']['p'])+pose['upperarm_r']['p'])/2
 inward=torso-h['p']; bearing=math.degrees(math.atan2(inward[1],inward[0])); yaw=math.degrees(math.atan2(blade[1],blade[0])); relative=(yaw-bearing+180)%360-180
 pelvis=np.array(pose['pelvis']['p']); spine=np.array(pose['neck_01']['p']); pts=pelvis[None,:]+np.linspace(0,1,501)[:,None]*(spine-pelvis)
 v=pts-a; along=np.clip(v@blade,0,np.linalg.norm(b-a)); distances=np.linalg.norm(v-along[:,None]*blade,axis=1)
 out.append(dict(tick=row['tick'],time=row['time'],yaw=yaw,inward=bearing,relative=relative,clearance=float(min(distances)),hand=(np.array(h['p'])-torso).tolist(),elevation=math.degrees(math.asin(blade[2]))))
print(json.dumps([r for r in out if r['tick'] in (185,187,191,195,200,205,210,215,220,230,240,250,260,280,300)],indent=2))
print('minimum',min((r['clearance'],r['tick']) for r in out if 187<=r['tick']<=306))
(p/(tag+'_route.json')).write_text(json.dumps(out,indent=2))
