import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation
p=pathlib.Path(__file__).parent;d=json.loads((p/'capture.json').read_text());by={}
for r in d['rows']:by.setdefault(r['tick'],[]).append(r)
prev={};near=[]
for t,rows in by.items():
 for r in rows:
  phase=(tuple(r['attack'][:4]) if r['attack'] else None,tuple(r.get('sword',{}).get('responses',[])))
  if prev.get(r['actor'])!=phase:print('PHASE',t,r['actor'],phase);prev[r['actor']]=phase
  if not r['player'] or 'sword' not in r:continue
  sw=r['sword'];tf=sw['transform'];rot=Rotation.from_quat(tf['q']);lo,hi=np.array(sw['bounds']);sc=np.array(tf['s'])
  for other in rows:
   if other==r or 'head' not in other['bones']:continue
   h=np.array(other['bones']['head']['transform']['p']);local=rot.inv().apply(h-tf['p'])/sc
   delta=(local-np.clip(local,lo,hi))*sc;dist=float(np.linalg.norm(delta))
   if dist<16:
    near.append(dict(tick=t,other=other['actor'],attack=r['attack'],distance_to_sword_bounds_cm=dist,head_in_sword_local=local.tolist(),responses=sw['responses']))
(p/'near-head.json').write_text(json.dumps(near,indent=2))
for x in near:print('NEAR',x['tick'],x['other'],x['attack'],round(x['distance_to_sword_bounds_cm'],2),x['responses'][1])
print('reason',d['reason'],'rows',len(d['rows']))
