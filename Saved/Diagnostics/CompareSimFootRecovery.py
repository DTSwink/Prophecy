import json,re,numpy as np
from pathlib import Path
p=Path('Saved/Diagnostics')
base=json.loads((p/'SimFootLegacy-capture.json').read_text(encoding='utf-8'))['rows'];test=json.loads((p/'SimFootPaired-capture.json').read_text(encoding='utf-8'))['rows']
B={r['clock']:r for r in base};T={r['clock']:r for r in test}
def v(row,bone,actual):return np.array(row['meshes']['PhysicalMesh'][bone]['p'] if actual else row['targets'][bone]['target']['p'])
def drive(tag):
 out=[]
 for line in (p/(tag+'-drive.log')).read_text(encoding='utf-8').splitlines():
  m=re.search(r'time=([\d.]+) side=(\d).*?target=\(([^)]+)\) authored=\(([^)]+)\)',line)
  if m:out.append((float(m[1]),int(m[2]),np.array([float(x) for x in m[3].split(',')]),np.array([float(x) for x in m[4].split(',')])))
 return out
DB=drive('SimFootLegacy');DT=drive('SimFootPaired')
def nearest(D,row,side):return min((x for x in D if x[1]==side),key=lambda x:abs(x[0]-row['t']))
res=dict(prefix_position_error=max(np.linalg.norm(v(r,n,True)-v(B[r['clock']],n,True)) for r in test if r['clock']<=244 for n in r['meshes']['PhysicalMesh']),frames=[])
for n in range(241,252):
 o=dict(tick=n)
 for tag,rr,dd in [('legacy',B,DB),('fixed',T,DT)]:
  r=rr[n];old=rr[n-1];d=nearest(dd,r,0);prev=nearest(dd,old,0)
  error=v(r,'foot_l',True)-v(r,'foot_l',False);prev_error=v(old,'foot_l',True)-v(old,'foot_l',False)
  o[tag]=dict(error=float(np.linalg.norm(error)),error_step=float(np.linalg.norm(error-prev_error)),physical_step=float(np.linalg.norm(v(r,'foot_l',True)-v(old,'foot_l',True))),authored_step=float(np.linalg.norm(v(r,'foot_l',False)-v(old,'foot_l',False))),drive_step=float(np.linalg.norm(d[2]-prev[2])),drive_to_authored=float(np.linalg.norm(d[2]-d[3])),drive_sample_time_error=abs(d[0]-r['t']))
 res['frames'].append(o)
(p/'SimFootRecovery-comparison.json').write_text(json.dumps(res,indent=2),encoding='utf-8');print(json.dumps(res,indent=2))
