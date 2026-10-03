import json,pathlib,math,numpy as np
from scipy.spatial.transform import Rotation
p=pathlib.Path('Saved/Diagnostics')
d=json.loads((p/'Leg920-capture.json').read_text(encoding='utf-8'))
print('Capture',d['reason'],'rows',len(d['rows']))
rows=d['rows'];out=[]
def angle(a,b):return float(np.degrees(np.arccos(np.clip(np.dot(a,b)/max(np.linalg.norm(a)*np.linalg.norm(b),1e-12),-1,1))))
def unit(v):return v/max(np.linalg.norm(v),1e-10)
def geometry(r,side,kind):
 if kind in ('target','future','previous'):b={k:v[kind] for k,v in r['targets'].items()}
 else:b=r['meshes'][kind]
 h,k,f=[np.array(b[n+'_'+side]['p']) for n in ('thigh','calf','foot')];u=k-h;v=f-k;a=unit(f-h);pole=u-a*np.dot(a,u)
 return dict(bend=angle(u,v),radius=float(np.linalg.norm(pole)),pole=unit(pole),axis=a,knee=k,foot=f,hip=h,lengths=[np.linalg.norm(u),np.linalg.norm(v)],q=b['thigh_'+side]['q'])
for j,r in enumerate(rows):
 for side in ('l','r'):
  for kind in ('target','future','PhysicalMesh'):
   g=geometry(r,side,kind);x=dict(tick=r['clock'],side=side,kind=kind,bend=g['bend'],radius=g['radius'],lengths=[float(v) for v in g['lengths']])
   if j:
    b=geometry(rows[j-1],side,kind)
    # parallel transport preceding pole to current hip-ankle axis before measuring turn
    den=1+np.dot(b['axis'],g['axis']);bp=b['pole']-(b['axis']+g['axis'])*np.dot(b['pole'],g['axis'])/max(den,1e-9)
    x.update(bend_delta=g['bend']-b['bend'],pole_turn=angle(bp,g['pole']),knee_step=float(np.linalg.norm(g['knee']-b['knee'])),foot_step=float(np.linalg.norm(g['foot']-b['foot'])),thigh_turn=float(np.degrees((Rotation.from_quat(g['q'])*Rotation.from_quat(b['q']).inv()).magnitude())))
   out.append(x)
(p/'Leg920-metrics.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
for lo,hi in ((905,940),):
 for r in rows:
  if lo<=r['clock']<=hi:
   print('STATE',r['clock'],r['attack'],r['mode'],r['weights'])
   print(r['pin'])
 for x in out:
  if lo<=x['tick']<=hi and x['kind']=='target':print({k:round(v,3) if isinstance(v,float) else v for k,v in x.items()})
for k in ('pole_turn','bend_delta','thigh_turn'):
 sel=[x for x in out if x['kind']=='target' and k in x]
 print('TOP',k,[(x['tick'],x['side'],round(x[k],3),round(x['radius'],2),round(x['bend'],2)) for x in sorted(sel,key=lambda x:abs(x[k]),reverse=True)[:12]])
