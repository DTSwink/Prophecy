import json,collections
from pathlib import Path
p=Path('Saved/Diagnostics/ForearmExit/baseline.json');v=json.loads(p.read_text());print(v['reason'],len(v['rows']))
for name,rs in __import__('itertools').groupby(sorted(v['rows'],key=lambda r:r['actor']),key=lambda r:r['actor']):
 rs=list(rs);print(name,len(rs),rs[0]['possessed'],list(rs[0]['meshes']))
 last=None;n=0
 for r in rs:
  state=r['attack'].split(',')[0]
  if state!=last:
   print(r['frame'],r.get('tick'),state);last=state;n+=1
   if n>18:break
