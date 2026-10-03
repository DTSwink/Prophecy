import json
from pathlib import Path
r=json.loads(Path('Saved/Benchmarks/jolt_hits_on_A_20260915_v3.json').read_text(encoding='utf-8-sig'))
def walk(x,p=''):
 if isinstance(x,dict):
  if p.endswith('/floor'): print(p,json.dumps(x)[:1800])
  if any(v in ('foot_l','foot_r') for v in x.values() if isinstance(v,str)):
   if '/0/' in p: print(p,json.dumps(x)[:900])
  for k,v in x.items(): walk(v,p+'/'+k)
 elif isinstance(x,list):
  for i,v in enumerate(x[:24] if p.endswith('/bodies') else x[:1]):walk(v,p+'/'+str(i))
walk(r)
