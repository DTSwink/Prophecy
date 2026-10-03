import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R

p=Path('Saved/Diagnostics/HandChain-20260923-122250.json')
d=json.loads(p.read_text())
assert d['error'] is None and d['frames']==360
previous={}; samples={}; moves={}
for row in d['rows']:
    agent=row['agent']; old=previous.get(agent); previous[agent]=row
    if not old or 'LOCOMOTION' not in row['state'] or 'LOCOMOTION' not in old['state']:
        continue
    if row['frame']<5:continue
    b=row['bones']; a=old['bones']
    s=R.from_quat(b['spine_05'][0][3:]); ps=R.from_quat(a['spine_05'][0][3:])
    moves.setdefault(agent,[]).append(float((ps.inv()*s).magnitude()*180/np.pi))
    for side in ('l','r'):
        h=R.from_quat(b['hand_'+side][0][3:]); ph=R.from_quat(a['hand_'+side][0][3:])
        delta=float(((ps.inv()*ph).inv()*(s.inv()*h)).magnitude()*180/np.pi)
        samples.setdefault(agent+'_'+side,[]).append(delta)
result={'samples':{k:{'n':len(v),'max_local_rotation_delta_deg':max(v),'p95':float(np.percentile(v,95))} for k,v in samples.items()},'spine_max_step_deg':{k:max(v) for k,v in moves.items()}}
print(json.dumps(result,indent=2))
p.with_suffix('.spine-validation.json').write_text(json.dumps(result,indent=2))
