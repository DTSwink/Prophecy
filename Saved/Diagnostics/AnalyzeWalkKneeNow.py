import json,numpy as np
from pathlib import Path
p=Path('Saved/Diagnostics/WalkKneeNow-capture.json')
if not p.exists():print('Still capturing');raise SystemExit
rows=json.loads(p.read_text(encoding='utf-8'))['rows'];metrics=[]
for r in rows:
 for side in ('l','r'):
  for kind in ('target','future'):
   h,k,f=[np.array(r['targets'][n+'_'+side][kind]['p']) for n in ('thigh','calf','foot')];u=k-h;v=f-k;reach=np.linalg.norm(u)+np.linalg.norm(v)
   metrics.append(dict(tick=r['clock'],side=side,kind=kind,bend=float(np.degrees(np.arccos(np.clip(np.dot(u,v)/np.linalg.norm(u)/np.linalg.norm(v),-1,1)))),slack=float(reach-np.linalg.norm(f-h)),attack=r['attack'],weights=r['weights']))
print('Rows',len(rows),'attacks',set(r['attack'] for r in rows))
for side in ('l','r'):
 print(side,'closest extension', sorted([x for x in metrics if x['kind']=='target' and x['side']==side],key=lambda x:x['slack'])[:3])
Path('Saved/Diagnostics/WalkKneeNow-metrics.json').write_text(json.dumps(metrics),encoding='utf-8')
