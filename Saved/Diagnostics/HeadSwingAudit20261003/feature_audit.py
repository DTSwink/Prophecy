import json
from pathlib import Path
import numpy as np
p=Path(__file__).parent;root=p.parents[2]
meta=json.loads((root/'Content/locomotion/NN/prophecy_lower_body_runtime.json').read_text());seed=np.array(meta['seed_root_rotation_rows'])
def matrix(v):
 x=np.array(v[:3]);x/=np.linalg.norm(x);y=np.array(v[3:6]);y-=x*(x@y);y/=np.linalg.norm(y);return np.array([x,y,np.cross(x,y)])
def yaw(v):
 co,si=np.cos(v),np.sin(v);return np.array([[co,0,si],[0,1,0],[-si,0,co]])
def heading(lower,offset):
 return np.r_[np.array(lower[offset:offset+3])@seed,(matrix(lower[offset+3:offset+9])@seed)[:2].ravel()]
allreports={}
for name in ('baseline','no_feedback','later_turn_stop','gaze_zero'):
 trace=[r for r in map(json.loads,(p/(name+'-inputs.jsonl')).read_text().splitlines()) if r['actor']=='BP_ProphecyManualPoseAgent_C_0' and 216<=round(r['time']*60)<=250]
 out=[]
 for r in trace:
  x=np.array(r['upper_input']);lo=r['lower_input'];roots=np.array(r['roots']);delta=(roots[4:7]-roots[:3])@yaw(roots[3]);dy=roots[7]-roots[3]
  def nextheading(offset):
   h=heading(r['published_lower'],offset);return np.r_[(h[:3]-delta)@yaw(dy),(matrix(h[3:])@yaw(dy))[:2].ravel()]
  out.append(dict(tick=round(r['time']*60),previous_pelvis=float(abs(heading(lo[41:],0)-x[180:189]).max()),current_pelvis=float(abs(heading(lo,0)-x[189:198]).max()),next_pelvis=float(abs(nextheading(0)-x[198:207]).max()),current_feet=float(max(abs(heading(lo,9)-x[243:252]).max(),abs(heading(lo,25)-x[252:261]).max())),next_feet=float(max(abs(nextheading(9)-x[261:270]).max(),abs(nextheading(25)-x[270:279]).max())),root_copy=float(abs(np.array(lo[117:152])-x[207:242]).max())))
 allreports[name]=out
 print(name,{k:max(z[k] for z in out) for k in out[0] if k!='tick'})
(p/'feature-audit.json').write_text(json.dumps(allreports,indent=2))
