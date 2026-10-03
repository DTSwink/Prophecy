import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics');a=json.loads((p/'PunchPole-baseline-live.json').read_text())['rows'];b=json.loads((p/'PunchPole-switch-live.json').read_text())['rows']
def measure(r,s):
 d=r['targets'];h,k,f=[np.array(d[n+'_'+s]['p']) for n in ('thigh','calf','foot')];axis=(f-h)/np.linalg.norm(f-h);p=k-h-axis*np.dot(k-h,axis);return R.from_quat(d['foot_'+s]['q']).inv().apply(p/np.linalg.norm(p))
def angle(x,y):return float(np.degrees(np.arccos(np.clip(x@y,-1,1))))
pre=max(np.linalg.norm(np.array(x['targets'][n]['p'])-y['targets'][n]['p']) for x,y in zip(a,b) if x['tick']<=320 for n in x['targets']);print('prefix max cm',pre)
for s in ('l','r'):
 for rows,label in ((a,'old'),(b,'new')):
  print(s,label,[(r['tick'],round(angle(measure(rows[i-1],s),measure(r,s)),3)) for i,r in enumerate(rows) if 319<=r['tick']<=337])
print('firstchanged',next(x['tick'] for x,y in zip(a,b) if any(np.linalg.norm(np.array(x['targets'][n]['p'])-y['targets'][n]['p'])>.0001 for n in x['targets'])))
