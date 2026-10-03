import json,sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
root=Path('Saved/Diagnostics');out={}
for tag in ['fk_exit626','fk_exit626_after']:
 p=root/'Knee202'/f'{tag}.json'
 if not p.exists():continue
 d=json.loads(p.read_text(encoding='utf8'));rows=d['rows'];events=[]
 for i,x in enumerate(rows):
  if i==0 or x['attack']!='None' or rows[i-1]['attack']=='None':continue
  last=rows[i-1];t=x['targets'];dq={}
  for bone,parent in [('upperarm_r','clavicle_r'),('lowerarm_r','upperarm_r'),('hand_r','lowerarm_r')]:
   q=[R.from_quat(t[parent][k]['q']).inv()*R.from_quat(t[bone][k]['q']) for k in ['previous','future']]
   dq[bone]=float((q[0].inv()*q[1]).magnitude()*180/np.pi)
  z=t['hand_r'];hand_delta=np.array(z['future']['p'])-np.array(z['previous']['p'])
  e=dict(tick=x['tick'],attack=last['attack'],arm_local_degrees=dq,hand_interval_delta_cm=hand_delta.tolist())
  events.append(e)
 out[tag]=dict(reason=d['reason'],rows=len(rows),events=events)
print(json.dumps(out,indent=2));(root/'FKExit626/comparison.json').write_text(json.dumps(out,indent=2),encoding='utf8')
