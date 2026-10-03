import json,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R,Slerp
p=Path(__file__).resolve().parent
def rows(n):return {r['tick']:r for r in json.loads((p/(n+'.json')).read_text())['rows']}
a,b=rows('baseline'),rows('pelvis_off')
tr=min((r for r in (json.loads(l) for l in (p/'baseline-nn.jsonl').read_text().splitlines()) if r['actor'].endswith('_0') and r['frame']==2),key=lambda r:abs(r['time']-a[506]['time']))
axis=R.from_quat(tr['anchor'][3:]).as_matrix()[:,0]
result={'prefix_max_body_difference_cm_through_504':max(float(np.linalg.norm(np.array(a[t]['bones'][n]['body']['p'])-b[t]['bones'][n]['body']['p'])) for t in a if t<=504 for n in a[t]['bones'] if a[t]['bones'][n]['body']),'lateral_head_relative_pelvis':{},'old_NN_midpoint_plus_pelvis_correction_error':{}}
for name,rs in [('baseline',a),('pelvis_off_after_504',b)]:
 result['lateral_head_relative_pelvis'][name]={kind:{t:float(axis@(np.array(rs[t]['bones']['head'][kind]['p'])-rs[t]['bones']['pelvis'][kind]['p'])) for t in range(503,508)} for kind in ('presented','body')}
def midpoint(n):
 before=a[504]['bones'][n]['presented'];future=a[504]['bones'][n]['future']
 return (np.array(before['p'])+future['p'])*.5,Slerp([0,1],R.from_quat([before['q'],future['q']]))(.5)
pos,rot=midpoint('pelvis');actual_pelvis=a[505]['bones']['pelvis']['presented'];correction=R.from_quat(actual_pelvis['q'])*rot.inv()
for n in ('spine_01','spine_05','head'):
 p0,q0=midpoint(n);actual=a[505]['bones'][n]['presented'];expected=np.array(actual_pelvis['p'])+correction.apply(p0-pos)
 result['old_NN_midpoint_plus_pelvis_correction_error'][n]={'cm':float(np.linalg.norm(expected-actual['p'])),'degrees':float(np.degrees(((correction*q0).inv()*R.from_quat(actual['q'])).magnitude()))}
result['without_pelvis_505_matches_unmodified_NN_head_cm']=float(np.linalg.norm(midpoint('head')[0]-b[505]['bones']['head']['presented']['p']))
(p/'analysis.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
assert result['prefix_max_body_difference_cm_through_504']==0
assert result['without_pelvis_505_matches_unmodified_NN_head_cm']<1e-6
