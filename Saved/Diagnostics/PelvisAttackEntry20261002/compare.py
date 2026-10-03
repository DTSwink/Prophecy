import json,numpy as np
from pathlib import Path
p=Path(__file__).resolve().parent
def load(n):return {r['tick']:r for r in json.loads((p/(n+'.json')).read_text(encoding='utf8'))['rows']}
a,b=load('baseline'),load('no_physical_seed')
def pos(r,kind):return np.array(r['bones']['pelvis'][kind]['p'])
result={'prefix_max_pelvis_body_difference_cm':max(float(np.linalg.norm(pos(a[t],'body')-pos(b[t],'body'))) for t in a if t<=169),
 'root_difference_169_177_cm':max(float(np.linalg.norm(np.array(a[t]['root'])-b[t]['root'])) for t in range(169,178))}
for name,rows in [('baseline',a),('no_physical_seed',b)]:
 delta=pos(rows[172],'presented')-pos(rows[170],'presented')
 result[name]={'first_presented_reversal_xy_cm':float(np.linalg.norm(delta[:2])), 'first_presented_delta_cm':delta.tolist(),
  'max_physical_target_xy_error_170_174_cm':max(float(np.linalg.norm((pos(rows[t],'body')-pos(rows[t],'target'))[:2])) for t in range(170,175))}
(p/'comparison.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result,indent=2))
