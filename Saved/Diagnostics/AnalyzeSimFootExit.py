import json,numpy as np
from scipy.spatial.transform import Rotation as R
from pathlib import Path
p=Path('Saved/Diagnostics');f=p/'SimFootExit-capture.json'
if not f.exists():print('Still capturing');raise SystemExit
rows=json.loads(f.read_text(encoding='utf-8'))['rows'];out=[]
for i,r in enumerate(rows):
 if not i:continue
 old=rows[i-1]
 for side in ('l','r'):
  foot='foot_'+side;calf='calf_'+side
  a=np.array(r['targets'][foot]['target']['p']);b=np.array(r['meshes']['PhysicalMesh'][foot]['p'])
  a0=np.array(old['targets'][foot]['target']['p']);b0=np.array(old['meshes']['PhysicalMesh'][foot]['p'])
  off=np.array([-42.561031,.107739,.42919] if side=='l' else [42.561165,-.107729,-.429205]);c=r['targets'][calf]['target'];end=np.array(c['p'])+R.from_quat(c['q']).apply(off*np.array(c['s']))
  c0=old['targets'][calf]['target'];end0=np.array(c0['p'])+R.from_quat(c0['q']).apply(off*np.array(c0['s']))
  drive=a if r['attack']!='None' else end;drive0=a0 if old['attack']!='None' else end0
  x=dict(tick=r['clock'],side=side,mode=r['mode'],attack=r['attack'],prior=old['attack'],error=float(np.linalg.norm(b-a)),errorstep=float(np.linalg.norm((b-a)-(b0-a0))),meshstep=float(np.linalg.norm(b-b0)),targetstep=float(np.linalg.norm(a-a0)),tipgap=float(np.linalg.norm(end-a)),estdrivestep=float(np.linalg.norm(drive-drive0)),exiting=old['attack']!='None' and r['attack']=='None');out.append(x)
print('Rows',len(rows),'modes',set(r['mode'] for r in rows))
print('EXITS')
for x in out:
 if x['exiting']:print(x)
print('TOP LEFT ERROR STEP')
for x in sorted([x for x in out if x['side']=='l'],key=lambda x:x['errorstep'],reverse=True)[:12]:print(x)
(p/'SimFootExit-metrics.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
