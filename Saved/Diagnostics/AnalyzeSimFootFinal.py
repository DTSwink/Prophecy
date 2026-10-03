import json, math
from pathlib import Path
import numpy as np
p=Path('Saved/Diagnostics')
def analyze(tag):
 d=json.loads((p/(tag+'-capture.json')).read_text(encoding='utf-8'));rows=d['rows']
 out=dict(reason=d['reason'],rows=len(rows),modes=sorted(set(r['mode'] for r in rows)),exits=[],finite=True)
 for r in rows:
  for group in r['meshes'].values():
   for tr in group.values():
    out['finite'] &= all(math.isfinite(x) for v in tr.values() for x in v)
 for old,r in zip(rows,rows[1:]):
  if old['attack']=='None' or r['attack']!='None':continue
  item=dict(tick=r['clock'],attack=old['attack'])
  for s in ('l','r'):
   b='foot_'+s
   a=np.array(r['targets'][b]['target']['p']);a0=np.array(old['targets'][b]['target']['p'])
   v=np.array(r['meshes']['PhysicalMesh'][b]['p']);v0=np.array(old['meshes']['PhysicalMesh'][b]['p'])
   item[s]=dict(error_step=float(np.linalg.norm((v-a)-(v0-a0))),error=float(np.linalg.norm(v-a)),authored_step=float(np.linalg.norm(a-a0)))
  out['exits'].append(item)
 return out
out={tag:analyze(tag) for tag in ('SimFootExit','SimFootFinal')}
(p/'SimFootFinal-summary.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
