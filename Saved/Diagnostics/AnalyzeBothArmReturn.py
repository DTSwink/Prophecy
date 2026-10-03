import json,math
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
p=Path('Saved/Diagnostics/BothArmReturn')
def read(tag):
 a=json.loads((p/(tag+'.json')).read_text());assert a['reason']=='Complete',a['reason']
 return {x['tick']:x for x in a['rows'] if x['possessed']}
def unit(v):return v/np.linalg.norm(v)
def torso(b):
 v=lambda n:np.array(b[n]['p'])
 z=unit(v('neck_01')-v('pelvis'));y=v('upperarm_r')-v('upperarm_l');y=unit(y-z*np.dot(y,z));x=unit(np.cross(y,z))
 return (v('upperarm_r')+v('upperarm_l'))/2,R.from_matrix(np.stack([x,y,z],axis=1))
def swing(a,b):
 c=np.cross(a,b);d=np.dot(a,b)
 if d<-.999999:return R.from_rotvec(np.array([0,1,0])*math.pi)
 return R.from_quat(np.r_[c,1+d])
def angle(a,b):return float(np.degrees((a*b.inv()).magnitude()))
def roll(prev,q):
 axis=q.apply([1,0,0]);car=swing(prev.apply([1,0,0]),axis)*prev
 return float(np.degrees(np.dot((q*car.inv()).as_rotvec(),axis)))
off,on=read('slashru_off'),read('slashru_on')
end=next(t for t in sorted(off) if t>180 and off[t]['attack']=='None')
prefix=0.;firstdiff=None;prefixrot=0.
for t in sorted(off.keys()&on.keys()):
 dist=max(np.linalg.norm(np.array(v['future']['p'])-on[t]['pose'][b]['future']['p']) for b,v in off[t]['pose'].items())
 ang=max(angle(R.from_quat(v['future']['q']),R.from_quat(on[t]['pose'][b]['future']['q'])) for b,v in off[t]['pose'].items())
 if t<end:prefix=max(prefix,float(dist));prefixrot=max(prefixrot,ang)
 if firstdiff is None and (dist>1e-5 or ang>1e-5):firstdiff=t
summary={'attack_end_tick':end,'prefix_max_cm':prefix,'prefix_max_deg':prefixrot,'first_difference':firstdiff,'variants':{}}
for tag,data in [('off',off),('on',on)]:
 rows=[];prev=None
 for t,r in sorted(data.items()):
  b={n:v['future'] for n,v in r['pose'].items()};origin,frame=torso(b)
  h=frame.inv().apply(np.array(b['hand_l']['p'])-origin)
  e=frame.inv().apply(np.array(b['lowerarm_l']['p'])-origin)
  q=frame.inv()*R.from_quat(b['lowerarm_l']['q']);w=frame.inv()*R.from_quat(b['hand_l']['q'])
  row=dict(tick=t,hand=h.tolist(),elbow=e.tolist())
  if prev:row.update(roll=roll(prev[0],q),forearm_step=angle(prev[0],q),hand_step=angle(prev[1],w))
  prev=(q,w);rows.append(row)
 seg=[r for r in rows if end<=r['tick']<=268]
 summary['variants'][tag]=dict(min_hand_forward_cm=min(r['hand'][0] for r in seg),behind_ticks=sum(r['hand'][0]<0 for r in seg),total_abs_forearm_roll_deg=sum(abs(r.get('roll',0)) for r in seg),net_forearm_roll_deg=sum(r.get('roll',0) for r in seg),max_forearm_step_deg=max(r.get('forearm_step',0) for r in seg),max_hand_step_deg=max(r.get('hand_step',0) for r in seg),samples=[r for r in seg if r['tick'] in [end,end+2,210,220,230,240,250,260,268]])
print(json.dumps(summary,indent=2));(p/'summary.json').write_text(json.dumps(summary,indent=2))
