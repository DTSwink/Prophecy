import json,pathlib,numpy as np
p=pathlib.Path(__file__).parent
def load(tag):
 rows=[r for r in map(json.loads,(p/('TimeGait'+tag+'.jsonl')).read_text().splitlines()) if r['actor'].endswith('_C_1')]
 return [r for i,r in enumerate(rows) if i==0 or r['lower_input']!=rows[i-1]['lower_input']]
for tag in ('Double','Normal','AfterFix'):
 if not (p/('TimeGait'+tag+'.jsonl')).exists():continue
 rows=load(tag)
 print(tag,'rows',len(rows),'walk',set(r['walk_policy'] for r in rows),'weights',set(r['walk_weight'] for r in rows))
 for r in rows:
  if 1.4<r['time']<1.65 or (abs(r['time']-round(r['time']))<.002):
   print(round(r['time'],4),'window',np.round(r['lower_input'][120:128],5),'pelvis',np.round(r['lower_input'][:3],5))
if (p/'TimeGaitNormal.jsonl').exists():
 a,b=load('Normal'),load('Double')
 for i,(x,y) in enumerate(zip(a,b)):
  err=max(abs(np.array(x['lower_input'])-y['lower_input']))
  if err>1.e-5:
   d=np.array(y['lower_input'])-x['lower_input'];inds=np.where(abs(d)>1.e-5)[0]
   print('FIRST',i,x['time'],y['time'],'err',err,'indices',inds.tolist());break
