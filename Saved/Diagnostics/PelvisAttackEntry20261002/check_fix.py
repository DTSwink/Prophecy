import json,numpy as np
from pathlib import Path
p=Path(__file__).resolve().parent
def rows(name):return {r['tick']:r for r in json.loads((p/(name+'.json')).read_text(encoding='utf8'))['rows']}
def nn(name):return {r['frame']:r for r in (json.loads(l) for l in (p/(name+'-nn.jsonl')).read_text(encoding='utf8').splitlines() if l.strip()) if r['actor'].endswith('_0') and r['frame']<=7}
a,b=rows('baseline'),rows('fixed');na,nb=nn('baseline'),nn('fixed')
def pos(r,bone='pelvis',kind='presented'):return np.array(r['bones'][bone][kind]['p'])
result=dict(first_interval_backward_xy_cm=float(np.linalg.norm((pos(b[172])-pos(b[170]))[:2])),
    entry_jump_cm=float(np.linalg.norm(pos(b[170])-pos(b[169]))),
    pre_entry_max_body_difference_cm=max(float(np.linalg.norm(pos(a[t],kind='body')-pos(b[t],kind='body'))) for t in a if t<=169),
    full_attack_max_nn_input_difference=max(max(abs(x-y) for x,y in zip(na[f]['input'],nb[f]['input'])) for f in na),
    full_attack_max_nn_output_difference=max(max(abs(x-y) for x,y in zip(na[f]['output'],nb[f]['output'])) for f in na),
    root_difference_169_177_cm=max(float(np.linalg.norm(np.array(a[t]['root'])-b[t]['root'])) for t in range(169,178)),
    max_entry_foot_step_cm={name:{bone:max(float(np.linalg.norm(pos(rows[t],bone)-pos(rows[t-1],bone))) for t in range(169,175)) for bone in ('foot_l','foot_r')} for name,rows in [('baseline',a),('fixed',b)]})
assert result['entry_jump_cm']<1e-6
assert result['first_interval_backward_xy_cm']<1
assert result['pre_entry_max_body_difference_cm']==0
assert result['full_attack_max_nn_input_difference']==0 and result['full_attack_max_nn_output_difference']==0
assert result['root_difference_169_177_cm']==0
(p/'fix-verification.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result,indent=2))
