import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics/Knee202');c=json.loads(pathlib.Path('Content/locomotion/NN/prophecy_upper_body_runtime.json').read_text());names=c['body_names'];axis=np.array(c['local_offsets_m'][names.index('hand_r')])*[1,-1,1];axis/=np.linalg.norm(axis)
for mode in ('current','no_cone','exit_no_inertia'):
 rows=json.loads((p/f'arm_revolution_{mode}.json').read_text())['rows'];print(mode,'axis',axis)
 for x in rows:
  if x['tick']<185 or x['tick']>231 or x['tick']%2==0:continue
  b={k:v['future'] for k,v in x['raw'].items()};hand=R.from_quat(b['hand_r']['q']);fore=R.from_quat(b['lowerarm_r']['q']);v=np.array(b['hand_r']['p'])-b['lowerarm_r']['p'];v/=np.linalg.norm(v);a=hand.apply(axis);angle=np.degrees(np.arccos(np.clip(a@v,-1,1)))
  q=R.align_vectors([v],[a])[0]*hand
  err=np.degrees((q.inv()*fore).magnitude())
  print(x['tick'],round(angle,2),round(err,2))
