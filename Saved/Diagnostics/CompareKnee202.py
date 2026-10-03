import json
from pathlib import Path
import numpy as np
p=Path('Saved/Diagnostics/Knee202')
data=json.loads((p/'paired.json').read_text());rows=data['rows']
assert data['reason']=='Complete'
def old(x):return {b:v['target'] for b,v in x['targets'].items()}
def point(b,n):return np.array(b[n]['p'])
def bend(b):
 a=point(b,'calf_r')-point(b,'thigh_r');c=point(b,'foot_r')-point(b,'calf_r')
 return float(np.degrees(np.arccos(np.clip(a@c/np.linalg.norm(a)/np.linalg.norm(c),-1,1))))
result=[];max_endpoint=0.
for i,x in enumerate(rows):
 if 'consistent_upper' not in x:continue
 a=old(x);b=x['consistent_upper']
 for n in ('pelvis','thigh_l','thigh_r','foot_l','foot_r','ball_l','ball_r'):
  max_endpoint=max(max_endpoint,float(np.linalg.norm(point(a,n)-point(b,n))))
 for n in ('pelvis','foot_l','foot_r','ball_l','ball_r'):
  assert np.allclose(a[n]['q'],b[n]['q'],rtol=0,atol=1e-12),(x['tick'],n)
 if 'consistent_upper' not in rows[i-1]:continue
 prev=rows[i-1];oa=old(prev);ob=prev['consistent_upper']
 r=dict(tick=x['tick'],old_step=float(np.linalg.norm(point(a,'calf_r')-point(oa,'calf_r'))),new_step=float(np.linalg.norm(point(b,'calf_r')-point(ob,'calf_r'))),old_bend=bend(a),new_bend=bend(b),old_upper=float(np.linalg.norm(point(a,'calf_r')-point(a,'thigh_r'))),new_upper=float(np.linalg.norm(point(b,'calf_r')-point(b,'thigh_r'))))
 result.append(r)
 if 195<=x['tick']<=204:print(r)
baseline={r['tick']:r for r in json.loads((p/'baseline.json').read_text())['rows']}
prefix=max(float(np.linalg.norm(point(old(x),'calf_r')-point(old(baseline[x['tick']]),'calf_r'))) for x in rows if x['tick'] in baseline and 120<=x['tick']<=215)
summary=dict(max_endpoint_difference_cm=max_endpoint,legacy_replay_max_right_knee_difference_cm=prefix,frames=result)
print('SUMMARY',max_endpoint,prefix)
(p/'paired_analysis.json').write_text(json.dumps(summary,indent=2))
