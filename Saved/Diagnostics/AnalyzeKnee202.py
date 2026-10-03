import json,sys,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
p=Path('Saved/Diagnostics/Knee202');tag=sys.argv[1] if len(sys.argv)>1 else 'baseline'
d=json.loads((p/(tag+'.json')).read_text());rows=d['rows'];print(d['reason'],len(rows),rows[0]['mode'])
last=None
for x in rows:
 state=x['attack'].split(',')[0]
 if state!=last:print('state',x['tick'],state);last=state
def unit(v):return v/max(1e-12,np.linalg.norm(v))
def metrics(b):
 h,k,f=[np.array(b[n+'_r']['p']) for n in ('thigh','calf','foot')];axis=unit(f-h);rad=k-h-axis*((k-h)@axis);pole=R.from_quat(b['foot_r']['q']).inv().apply(unit(rad))
 bend=np.degrees(np.arccos(np.clip(unit(k-h)@unit(f-k),-1,1)))
 return bend,pole,np.linalg.norm(f-k),np.linalg.norm(rad)
def read(x,stage):
 if stage in ('future','presented'):return {b:v[stage] for b,v in x['raw'].items()}
 if stage=='target':return {b:v['target'] for b,v in x['targets'].items()}
 return x['meshes'][stage]
result={}
for stage in ['future','presented','target','Mesh','PhysicalMesh']:
 print('STAGE',stage);records=[]
 for i,x in enumerate(rows):
  if not 188<=x['tick']<=218 or i==0:continue
  b=read(x,stage);old=read(rows[i-1],stage)
  if 'calf_r' not in b:continue
  bend,pole,length,radius=metrics(b);ob,op,_,_=metrics(old)
  pole_step=np.degrees(np.arccos(np.clip(pole@op,-1,1)));qstep=np.degrees((R.from_quat(old['thigh_r']['q']).inv()*R.from_quat(b['thigh_r']['q'])).magnitude())
  pos=np.linalg.norm(np.array(b['calf_r']['p'])-old['calf_r']['p']);fstep=np.linalg.norm(np.array(b['foot_r']['p'])-old['foot_r']['p'])
  records.append(dict(t=x['tick'],bend=bend,pole_step=pole_step,length=length,radius=radius,qstep=qstep,knee_step=pos,foot_step=fstep))
  if 195<=x['tick']<=209:print(x['tick'],'bend/pole/qstep/knee/foot/calf',np.round([bend,pole_step,qstep,pos,fstep,length],4).tolist())
 result[stage]=records
for x in rows:
 if 195<=x['tick']<=209:print('pin',x['tick'],x['pin'],'alpha',x.get('alpha'), 'weights',x['weights'])
(p/(tag+'_analysis.json')).write_text(json.dumps(result,indent=2))
