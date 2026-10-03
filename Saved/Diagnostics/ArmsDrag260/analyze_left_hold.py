import json,math,re
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
p=Path(__file__).parent
tags=['left_hold_before','left_hold_no_extra']
datasets=[]
for tag in tags:
 d=json.loads((p/(tag+'.json')).read_text());assert not d['error'],d['error']
 rows={r['tick']:r for r in d['rows'] if r['player']};datasets.append(rows)
 def local(t,bone):
  f=rows[t]['future'];q=R.from_quat(f['spine_05']['q'])
  return q.inv().apply(np.array(f[bone]['p'])-f['spine_05']['p'])
 samples=[]
 for t in (185,187,189,200,210,220,230,240,245,247,250,260):
  f=rows[t]['future'];previous=rows[t-2]['future'];q=R.from_quat(f['spine_05']['q']).inv()*R.from_quat(f['upperarm_l']['q']);qp=R.from_quat(previous['spine_05']['q']).inv()*R.from_quat(previous['upperarm_l']['q'])
  samples.append(dict(tick=t,hand=local(t,'hand_l').tolist(),hand_step2=float(np.linalg.norm(local(t,'hand_l')-local(t-2,'hand_l'))),upper_step2=math.degrees((q*qp.inv()).magnitude())))
 print(tag,json.dumps(samples))
 (p/(tag+'_left_metrics.json')).write_text(json.dumps(samples,indent=2))
a,b=datasets
diff=[]
for t in a:
 f=a[t]['future'];g=b[t]['future'];x=R.from_quat(f['spine_05']['q']);y=R.from_quat(g['spine_05']['q'])
 delta={bone:float(np.linalg.norm(x.inv().apply(np.array(f[bone]['p'])-f['spine_05']['p'])-y.inv().apply(np.array(g[bone]['p'])-g['spine_05']['p']))) for bone in ('hand_l','lowerarm_l','hand_r')}
 diff.append(dict(tick=t,**delta))
print('comparison',json.dumps([r for r in diff if r['tick'] in (151,181,185,187,200,210,220,230,240,247,250,260)]))
print('pre-release max',max(r['hand_l'] for r in diff if r['tick']<=187))
(p/'left_hold_ablation_comparison.json').write_text(json.dumps(diff,indent=2))
