import json,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
p=Path(__file__).resolve().parent
def rows(path):return {r['tick']:r for r in json.loads(path.read_text())['rows']}
a=rows(p/'baseline.json');b=rows(p/'fixed.json')
ka=rows(p.parent/'HeadAttackEntry20261003/sync_kinematic.json');kb=rows(p/'sync_kinematic.json')
l=json.loads((p.parents[2]/'Content/locomotion/NN/prophecy_upper_body_runtime.json').read_text())
trace=[json.loads(t) for t in (p/'baseline-nn.jsonl').read_text().splitlines()]
result={}
for entry,end in ((169,176),(504,512)):
    tr=min((r for r in trace if r['actor'].endswith('_0') and r['frame']==2),key=lambda r:abs(r['time']-a[entry+2]['time']))
    axis=R.from_quat(tr['anchor'][3:]).as_matrix()[:,0]
    data={}
    for name,rs in [('before',a),('after',b)]:
        data[name]={}
        for kind in ('body','presented'):
            v={t:float(axis@(np.array(rs[t]['bones']['head'][kind]['p'])-rs[t]['bones']['pelvis'][kind]['p'])) for t in range(entry-2,end+1)}
            data[name][kind]={t:v[t]-v[t-1] for t in range(entry-1,end+1)}
    if entry==169:
        assert abs(data['after']['body'][170])<.25
        assert all(data['after']['presented'][t]<0 for t in range(170,177))
    else:
        assert all(-.6<data['after']['body'][t]<0 for t in range(505,509))
    result[str(entry)]=data
result['prefix_body_position_error_cm']=max(float(np.linalg.norm(np.array(a[t]['bones'][n]['body']['p'])-b[t]['bones'][n]['body']['p'])) for t in a if t<=169 for n in a[t]['bones'] if a[t]['bones'][n]['body'])
assert result['prefix_body_position_error_cm']==0
result['kinematic_position_error_cm']=max(float(np.linalg.norm(np.array(ka[t]['bones'][n]['presented']['p'])-kb[t]['bones'][n]['presented']['p'])) for t in range(165,201) for n in ka[t]['bones'])
result['kinematic_rotation_error_deg']=max(float(np.degrees((R.from_quat(ka[t]['bones'][n]['presented']['q']).inv()*R.from_quat(kb[t]['bones'][n]['presented']['q'])).magnitude())) for t in range(165,201) for n in ka[t]['bones'])
assert result['kinematic_position_error_cm']<1e-6
assert result['kinematic_rotation_error_deg']<1e-6
def offset(t,n):
    parent=l['body_names'][l['parents_body'][l['body_names'].index(n)]]
    x=b[t]['bones'][n]['future'];y=b[t]['bones'][parent]['future']
    return R.from_quat(y['q']).inv().apply(np.array(x['p'])-y['p'])
result['attachment_distance_to_final_NN_cm']={t:max(float(np.linalg.norm(offset(t,n)-offset(198,n))) for n in l['core_bones']) for t in range(176,199,2)}
assert all(result['attachment_distance_to_final_NN_cm'][t+2]<result['attachment_distance_to_final_NN_cm'][t] for t in range(176,192,2))
assert result['attachment_distance_to_final_NN_cm'][192]<.01
assert result['attachment_distance_to_final_NN_cm'][194]<.0001
(p/'final-verification.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
