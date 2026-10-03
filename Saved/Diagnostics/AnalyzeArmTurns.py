import json,sys,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
exec(Path('Saved/Diagnostics/AnalyzePikeReturn.py').read_text().split("a,b=load('legacy')")[0])
p=Path('Saved/Diagnostics/ArmReach');tag=sys.argv[1] if len(sys.argv)>1 else 'first_two_turn'
d=json.loads((p/(tag+'.json')).read_text());rows=d['rows'];out={};last=None
for row in rows:
 state=row['attack'].split(',')[0]
 if state!=last:print(row['tick'],state);last=state
def unit(x):return x/max(np.linalg.norm(x),1e-12)
def swing(a,b):
 a=unit(a);b=unit(b);q=np.r_[np.cross(a,b),1+a@b];return R.from_quat(q) if np.linalg.norm(q)>1e-9 else R.identity()
for arm in ['l','r']:
 vals=[];prev=None;total=0.;pole_total=0.
 for row in rows:
  b={n:x['future'] for n,x in row['pose'].items()};origin,tr,w=torso(b)
  s,e,h=[tr.inv().apply(np.array(b[n+'_'+arm]['p'])-origin) for n in ['upperarm','lowerarm','hand']]
  q=tr.inv()*R.from_quat(b['upperarm_'+arm]['q']);upper=unit(e-s);axis=unit(h-s);pole=unit(e-s-axis*((e-s)@axis))
  if prev:
   pq,pu,pa,pp=prev;dq=(q*(swing(pu,upper)*pq).inv()).as_quat();tw=(2*np.arctan2(dq[:3]@upper,dq[3])+np.pi)%(2*np.pi)-np.pi
   pp=swing(pa,axis).apply(pp);pt=np.arctan2(axis@np.cross(pp,pole),np.clip(pp@pole,-1,1))
   total+=np.degrees(tw);pole_total+=np.degrees(pt)
   step=np.degrees((pq.inv()*q).magnitude());vals.append(dict(t=row['tick'],step=float(step),tw=float(np.degrees(tw)),pole=float(np.degrees(pt)),total=float(total),pole_total=float(pole_total)))
  prev=q,upper,axis,pole
 print(arm,'max',sorted(vals,key=lambda v:v['step'],reverse=True)[:6])
 for a,z in [(90,180),(180,270)]:
  v=[x for x in vals if a<=x['t']<z];print(arm,a,z,'signed twist',sum(x['tw'] for x in v),'pole',sum(x['pole'] for x in v),'total rotation',sum(x['step'] for x in v))
 out[arm]=vals
(p/(tag+'_turns.json')).write_text(json.dumps(out))
