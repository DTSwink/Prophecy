import json,pathlib,re,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics');rows=json.loads((p/'FootHoverCurrent-live.json').read_text())['rows']
pat=re.compile(r'time=([\d.]+) side=(\d) allowance=([\d.-]+) recovery=([\d.-]+) target=\(([^)]+)\) authored=\(([^)]+)\)')
drive={}
for line in (p/'FootHoverCurrent-drive.log').read_text().splitlines():
 m=pat.search(line)
 if m:drive[(round(float(m[1])*60),int(m[2]))]=dict(target=np.array(list(map(float,m[5].split(',')))),authored=np.array(list(map(float,m[6].split(',')))),allowance=float(m[3]),recovery=float(m[4]))
out=[]
for r in rows:
 for i,s in enumerate('lr'):
  name='foot_'+s;target=np.array(r['targets'][name]['p']);mesh=np.array(r['meshes']['PhysicalMesh'][name]['p']);d=drive.get((round(r['t']*60),i))
  if d is None:continue
  a=r['targets'];b=r['meshes']['PhysicalMesh'];length=lambda v:float(np.linalg.norm(np.array(v[name]['p'])-v['calf_'+s]['p']))
  calferror=np.array(b['calf_'+s]['p'])-a['calf_'+s]['p'];err=mesh-target;de=d['target']-d['authored']
  out.append(dict(tick=r['tick'],time=r['t'],side=s,attack=r['attack'],height_error=float(err[2]),error=float(np.linalg.norm(err)),drive_error=float(np.linalg.norm(de)),drive_z=float(de[2]),target_z=float(target[2]),physical_z=float(mesh[2]),target_length=length(a),physical_length=length(b),calf_z_error=float(calferror[2]),rotation_error=float(np.degrees((R.from_quat(b[name]['q'])*R.from_quat(a[name]['q']).inv()).magnitude())),allowance=d['allowance'],recovery=d['recovery']))
(p/'FootHoverCurrent-metrics.json').write_text(json.dumps(out,indent=2))
print('rows',len(rows),'drive samples',len(drive),'matched',len(out),'modes',set(r['mode'] for r in rows))
for s in 'lr':
 vals=[x for x in out if x['side']==s]
 print('SIDE',s,'largest positive height')
 for x in sorted(vals,key=lambda x:x['height_error'],reverse=True)[:6]:print(x)
 for phase in ['attack','loco']:
  v=[x for x in vals if (x['attack']!='None')==(phase=='attack')]
  if v:print(phase,'height error median/max',np.median([x['height_error'] for x in v]),max(x['height_error'] for x in v),'drive max',max(x['drive_error'] for x in v))
print('settings row100',rows[min(99,len(rows)-1)].get('magnetisation'))
