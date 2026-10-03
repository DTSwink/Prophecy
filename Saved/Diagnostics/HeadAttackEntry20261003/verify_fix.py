import json,numpy as np
from scipy.spatial.transform import Rotation as R
from pathlib import Path
p=Path(__file__).resolve().parent
def rows(n):return {r['tick']:r for r in json.loads((p/(n+'.json')).read_text())['rows']}
def traces(n):return {r['frame']:r for r in (json.loads(l) for l in (p/(n+'-nn.jsonl')).read_text().splitlines() if l.strip()) if r['actor'].endswith('_0') and r['frame']<=6}
a,b=rows('baseline'),rows('fixed');na,nb=traces('baseline'),traces('fixed')
rot=R.from_quat(na[2]['anchor'][3:])
result={'prefix_max_body_difference_cm':max(float(np.linalg.norm(np.array(a[t]['bones'][bone]['body']['p'])-b[t]['bones'][bone]['body']['p'])) for t in a if t<=169 for bone in a[t]['bones'] if a[t]['bones'][bone]['body']),
 'first_nn_input_max_difference':max(abs(x-y) for x,y in zip(na[2]['input'],nb[2]['input'])),
 'first_six_nn_input_max_difference':max(abs(x-y) for t in na for x,y in zip(na[t]['input'],nb[t]['input'])),
 'first_six_nn_output_max_difference':max(abs(x-y) for t in na for x,y in zip(na[t]['output'],nb[t]['output'])),
 'pelvis_presented_max_difference_169_174_cm':max(float(np.linalg.norm(np.array(a[t]['bones']['pelvis']['presented']['p'])-b[t]['bones']['pelvis']['presented']['p'])) for t in range(169,175)),
 'lateral_head_relative_pelvis_cm':{}}
for name,rs in [('baseline',a),('fixed',b)]:
 result['lateral_head_relative_pelvis_cm'][name]={}
 for kind in ['presented','body']:
  vals=[]
  for t in (168,169,170,171,172):
   v=rs[t]['bones'];vals.append(float(rot.inv().apply(np.array(v['head'][kind]['p'])-v['pelvis'][kind]['p'])[0]))
  result['lateral_head_relative_pelvis_cm'][name][kind]=vals
print(json.dumps(result,indent=2));(p/'fix-verification.json').write_text(json.dumps(result,indent=2))
assert result['prefix_max_body_difference_cm']<1e-8
assert result['first_nn_input_max_difference']==0
for k in ['presented','body']:
 v=result['lateral_head_relative_pelvis_cm']['fixed'][k]
 assert (v[2]-v[1])*(v[3]-v[2])>=0,'169 > 170 > 171 still reverses'
