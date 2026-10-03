import json,sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
p=Path(sys.argv[1])
d=json.loads(p.read_text());assert d['error'] is None and d['frames']==360
s=json.loads(Path('Content/locomotion/NN/prophecy_upper_body_runtime.json').read_text())
names=s['body_names'];parents=dict(zip(names,[names[i] if i>=0 else None for i in s['parents_body']]))
previous={};values={};moves={};attacks=0;streak={};handoffs={}
def local(row,name):
    parent_name=parents[name]
    while parent_name not in row['bones']:parent_name=parents[parent_name]
    t=np.array(row['bones'][name][0]);parent=np.array(row['bones'][parent_name][0])
    pr=R.from_quat(parent[3:]);q=pr.inv()*R.from_quat(t[3:])
    return pr.inv().apply(t[:3]-parent[:3]),q
for row in d['rows']:
    agent=row['agent'];old=previous.get(agent);previous[agent]=row
    streak[agent]=streak.get(agent,0)+1 if 'LOCOMOTION' in row['state'] else 0
    attacks+=int('ATTACKING' in row['state'])
    if not old or row['frame']<5 or 'LOCOMOTION' not in row['state'] or 'LOCOMOTION' not in old['state']:continue
    for name in s['core_bones']:
        if name not in row['bones']:continue # PHAT readback omits neck_02; head uses neck_01 ancestor.
        v,q=local(row,name);pv,pq=local(old,name)
        delta=float((pq.inv()*q).magnitude()*180/np.pi)
        posdelta=float(np.linalg.norm(v-pv))
        (values if streak[agent]>4 else handoffs).setdefault(name,[]).append((delta,posdelta))
    q=R.from_quat(row['bones']['pelvis'][0][3:]);pq=R.from_quat(old['bones']['pelvis'][0][3:])
    moves.setdefault(agent,[]).append(float((pq.inv()*q).magnitude()*180/np.pi))
result={'bones':{k:{'samples':len(v),'max_local_rotation_delta_deg':max(x[0] for x in v),'max_local_offset_delta_cm':max(x[1] for x in v)} for k,v in values.items()},'pelvis_max_step_deg':{k:max(v) for k,v in moves.items()},'special_samples':attacks,'handoff_max_local_offset_delta_cm':{k:max(x[1] for x in v) for k,v in handoffs.items()},'note':'PHAT readback has nine core bodies; neck_02 is included in head-to-neck_01 aggregate. First four locomotion game frames include retained attack endpoints and are reported separately.'}
print(json.dumps(result,indent=2));p.with_suffix('.validation.json').write_text(json.dumps(result,indent=2))
assert len(values)==9 and all(len(v)>100 for v in values.values())
if 'CoreBaseline-' not in str(p):
    assert all(max(x[0] for x in v)<.003 for v in values.values()),'Core rotation drift'
assert all(max(x[1] for x in v)<.003 for k,v in values.items()
    if not ('CoreBaseline-' in str(p) and k=='head')),'FK attachment changed'
