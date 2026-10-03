import json,math
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
p=Path('Saved/Diagnostics');d=json.loads((p/'Calf1495-capture.json').read_text());rows=d['rows']
def metric(b,side,old=None):
 c,f=b['calf_'+side],b['foot_'+side]
 off=np.array([-42.561031,.107739,.42919] if side=='l' else [42.561165,-.107729,-.429205])
 tip=np.array(c['p'])+R.from_quat(c['q']).apply(off*np.array(c['s']))
 out=dict(length=float(np.linalg.norm(np.array(c['p'])-f['p'])),tip_gap=float(np.linalg.norm(tip-f['p'])),scale=c['s'])
 if old:
  out.update(calf_move=float(np.linalg.norm(np.array(c['p'])-old['calf_'+side]['p'])),foot_move=float(np.linalg.norm(np.array(f['p'])-old['foot_'+side]['p'])),calf_turn=float((R.from_quat(c['q'])*R.from_quat(old['calf_'+side]['q']).inv()).magnitude()*180/math.pi),foot_turn=float((R.from_quat(f['q'])*R.from_quat(old['foot_'+side]['q']).inv()).magnitude()*180/math.pi))
 return out
actors={};report=[]
for row in rows:actors.setdefault(row['actor'],[]).append(row)
print('REASON',d['reason'],'rows',len(rows))
for name,rr in actors.items():
 print('\nACTOR',name,'possessed',rr[0]['possessed'],'mode',rr[0]['mode'],'ticks',rr[0]['tick'],rr[-1]['tick'])
 for i,r in enumerate(rr):
  if not 1488<=r['clock']<=1502:continue
  old=rr[i-1] if i else None
  item=dict(actor=name,tick=r['tick'],time=r['t'],attack=r['attack'],alpha=r.get('alpha'),layers={})
  for kind in ('PhysicalMesh','Mesh','target','future','previous'):
   def layer(row):return row['meshes'].get(kind,{}) if kind in ('PhysicalMesh','Mesh') else {b:v[kind] for b,v in row['targets'].items()}
   b=layer(r);prev=layer(old) if old else None
   if 'calf_l' not in b:continue
   item['layers'][kind]={side:metric(b,side,prev) for side in ('l','r')}
  report.append(item)
  m=item['layers'].get('PhysicalMesh',{})
  print(r['clock'],r['attack'],'alpha',round(r.get('alpha',-1),3),{s:{k:round(v,3) if isinstance(v,float) else v for k,v in x.items() if k!='scale'} for s,x in m.items()})
 print('LARGEST CALF ROTATION STEPS IN CAPTURE')
 ranks=[]
 for i in range(1,len(rr)):
  a,b=rr[i-1],rr[i]
  if 'PhysicalMesh' not in b['meshes']:continue
  for side in ('l','r'):
   m=metric(b['meshes']['PhysicalMesh'],side,a['meshes']['PhysicalMesh']);ranks.append((m['calf_turn'],b['clock'],side,m['calf_move'],m['foot_move']))
 print(sorted(ranks,reverse=True)[:8])
(p/'Calf1495-analysis.json').write_text(json.dumps(report,indent=2))
