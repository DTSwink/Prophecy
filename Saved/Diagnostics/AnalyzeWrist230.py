import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
p=Path('Saved/Diagnostics/Knee202')
out={}
for tag in ['wrist230_before','wrist230_after','wrist230_final']:
 f=p/(tag+'.json')
 if not f.exists():continue
 data=json.loads(f.read_text());rows={r['tick']:r for r in data['rows']}
 def pose(t,b,physical=False):
  return rows[t]['meshes']['PhysicalMesh'][b] if physical else rows[t]['raw'][b]['presented']
 def step(t,b,physical=False):
  a,c=pose(t-1,b,physical),pose(t,b,physical)
  return [float(np.linalg.norm(np.array(a['p'])-c['p'])),float(np.degrees((R.from_quat(c['q'])*R.from_quat(a['q']).inv()).magnitude()))]
 result=dict(reason=data['reason'],frames=len(rows),window=[],transitions=[])
 previous=None
 for t,r in rows.items():
  for b,bone in r['raw'].items():
   for slot in ['presented','future']:
    assert np.isfinite(bone[slot]['p']+bone[slot]['q']).all(),(tag,t,b)
  if r['attack']!=previous:
   result['transitions'].append([t,r['attack']]);previous=r['attack']
  if 219<=t<=235 and t-1 in rows:
   result['window'].append(dict(tick=t,nn=step(t,'hand_l'),physical=step(t,'hand_l',True)))
 result['foot_errors']={str(t):{b:float(np.linalg.norm(np.array(pose(t,b)['p'])-pose(t,b,True)['p'])) for b in ['foot_l','foot_r']} for t in [149,151,153,173,175,177,195,197,199,227,229] if t in rows}
 out[tag]=result
 print(tag,'frames',len(rows),'reason',data['reason'])
 for row in result['window']:print(row['tick'],'NN',np.round(row['nn'],3),'physical',np.round(row['physical'],3))
 print('foot errors',result['foot_errors'])
(p/'wrist230_analysis.json').write_text(json.dumps(out,indent=2))
