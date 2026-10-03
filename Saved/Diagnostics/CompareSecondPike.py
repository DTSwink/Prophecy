from pathlib import Path
import sys,json,numpy as np
from scipy.spatial.transform import Rotation as R
exec(Path('Saved/Diagnostics/AnalyzePikeReturn.py').read_text().split("a,b=load('legacy')")[0])
p=Path('Saved/Diagnostics/ArmReach')
tags=sys.argv[1:] or ['second_pike_inward','nn_hinge_latefix']
sets=[{r['tick']:r for r in json.loads((p/(tag+'.json')).read_text())['rows']} for tag in tags]
report={}
for tag,d in zip(tags,sets):
 out={}
 for arm in ['l','r']:
  rot=[];lateral=[];bend=[];positions=[]
  for t in range(207,270):
   b={n:x['future'] for n,x in d[t]['pose'].items()};o,q,w=torso(b)
   e=np.array(b['lowerarm_'+arm]['p']);s=np.array(b['upperarm_'+arm]['p']);h=np.array(b['hand_'+arm]['p']);u=e-s;v=h-e
   lateral.append((t,float(q.inv().apply(u)[1])));positions.append(q.inv().apply(u))
   bend.append((t,float(np.degrees(np.arccos(np.clip(u@v/np.linalg.norm(u)/np.linalg.norm(v),-1,1))))))
   delta=R.from_quat(d[t-1]['pose']['upperarm_'+arm]['future']['q']).inv()*R.from_quat(b['upperarm_'+arm]['q'])
   rot.append((t,float(np.degrees(delta.magnitude()))))
  out[arm]={'max_rot':max(rot,key=lambda x:x[1]),'min_bend':min(bend,key=lambda x:x[1]),'max_inward_cm':max(x[1]*(1 if arm=='l' else -1) for x in lateral),'lateral_samples':[x for x in lateral if (x[0]-207)%6==0],
   'max_elbow_relative_step_cm':float(max(np.linalg.norm(np.diff(positions,axis=0),axis=1))),
   'late_rotation':[x for x in rot if x[0]>=251 and x[0]%2]}
 out['prefix_position_cm']=max(float(np.linalg.norm(np.array(x['future']['p'])-sets[0][t]['pose'][n]['future']['p'])) for t,r in d.items() if t<=206 for n,x in r['pose'].items())
 out['prefix_rotation_deg']=max(float(np.degrees((R.from_quat(x['future']['q']).inv()*R.from_quat(sets[0][t]['pose'][n]['future']['q'])).magnitude())) for t,r in d.items() if t<=206 for n,x in r['pose'].items())
 report[tag]=out
print(json.dumps(report,indent=2));(p/('second_compare_'+tags[-1]+'.json')).write_text(json.dumps(report,indent=2))
