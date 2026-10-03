import json,numpy as np
from pathlib import Path
p=Path('Saved/Diagnostics/Knee202')
out={}
for tag in ['upper_inertia_current','upper_inertia_isolated','upper_inertia_fixed']:
 f=p/(tag+'.json')
 if not f.exists():continue
 d=json.loads(f.read_text());rr={r['tick']:r for r in d['rows']}
 def pos(t,b='hand_r',physical=False):
  return np.array(rr[t]['meshes']['PhysicalMesh'][b]['p'] if physical else rr[t]['raw'][b]['future']['p'])
 rows=[]
 for t in [188,190,192,194,196,198,200,250,278,280,282,284,300,328]:
  if t not in rr:continue
  rows.append(dict(tick=t,velocity_cm_s=((pos(t)-pos(t-2))*30).tolist(),physical_velocity_cm_s=((pos(t,physical=True)-pos(t-2,physical=True))*30).tolist(),
   forearm_length_cm=float(np.linalg.norm(pos(t)-pos(t,'lowerarm_r'))),upper_length_cm=float(np.linalg.norm(pos(t,'lowerarm_r')-pos(t,'upperarm_r')))))
 out[tag]=dict(reason=d['reason'],samples=rows)
 print(tag,d['reason'])
 for r in rows:print(r['tick'],'target',np.round(r['velocity_cm_s'],2),'physical',np.round(r['physical_velocity_cm_s'],2),'lengths',round(r['upper_length_cm'],3),round(r['forearm_length_cm'],3))
 if tag=='upper_inertia_isolated':
  prediction=pos(190)*2-pos(188)
  print('Expected first inertial hand',prediction,'reach',np.linalg.norm(prediction-pos(192,'upperarm_r')),'available',np.linalg.norm(pos(190)-pos(190,'lowerarm_r'))+np.linalg.norm(pos(190,'lowerarm_r')-pos(190,'upperarm_r')))
(p/'upper_inertia_fixed_analysis.json').write_text(json.dumps(out,indent=2))
