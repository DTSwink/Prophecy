import json,math,sys
import numpy as np
from scipy.spatial.transform import Rotation as R
from pathlib import Path
p=Path('Saved/Diagnostics/ForearmExit');tag=sys.argv[1] if len(sys.argv)>1 else 'baseline';a=[x for x in json.loads((p/(tag+'.json')).read_text())['rows'] if x['possessed']]
def unit(x):return x/np.linalg.norm(x)
def swing(a,b):
 c=np.cross(a,b);dot=np.dot(a,b)
 if dot<-.999999:return R.from_rotvec(np.array([0,1,0])*math.pi)
 return R.from_quat(np.r_[c,1+dot])
def roll(q0,q1):
 axis=q1.apply([1,0,0]);car=swing(q0.apply([1,0,0]),axis)*q0
 return np.degrees(np.dot((q1*car.inv()).as_rotvec(),axis))
def angle(a,b):return np.degrees((a*b.inv()).magnitude())
rows=[]
for i,r in enumerate(a):
 b={k:v['future'] for k,v in r['pose'].items()};f=R.from_quat(b['lowerarm_l']['q']);h=R.from_quat(b['hand_l']['q']);d=unit(np.array(b['hand_l']['p'])-b['lowerarm_l']['p']);expect=swing(h.apply([1,0,0]),d)*h
 bend=np.degrees(np.arccos(np.clip(np.dot(h.apply([1,0,0]),d),-1,1)))
 row=dict(tick=r['tick'],attack=r['attack']!='None',bend=bend,roll_error=angle(f,expect))
 if i:
  prev=a[i-1]['pose'];pf=R.from_quat(prev['lowerarm_l']['future']['q']);ph=R.from_quat(prev['hand_l']['future']['q'])
  row.update(froll=roll(pf,f),hroll=roll(ph,h),fstep=angle(f,pf),hstep=angle(h,ph))
 rows.append(row)
for start,end in [(110,155),(200,245),(290,335),]:
 seg=[r for r in rows if start<=r['tick']<=end]
 print('WINDOW',start,end,'sum_roll',round(sum(r.get('froll',0) for r in seg),2),'hand',round(sum(r.get('hroll',0) for r in seg),2),'maxerr',round(max(r['roll_error'] for r in seg),2),'maxbend',round(max(r['bend'] for r in seg),2))
for r in sorted(rows[1:],key=lambda r:r['fstep'],reverse=True)[:15]:print({k:round(v,2) if isinstance(v,float) else v for k,v in r.items()})
(p/(tag+'-angles.json')).write_text(json.dumps(rows))
