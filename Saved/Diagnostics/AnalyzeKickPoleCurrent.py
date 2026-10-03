import json
import numpy as np
from scipy.spatial.transform import Rotation as R
from pathlib import Path
p=Path('Saved/Diagnostics/Knee202');d=json.loads((p/'kick_current_oct2.json').read_text());rows=d['rows']
print(d['reason'],len(rows),rows[0]['mode'],rows[0]['meshes'].keys())
last=None
for r in rows:
    attack=r['attack'].split(',')[0]
    if attack!=last:print('STATE',r['tick'],r['attack']);last=attack
def unit(v):return v/max(1.e-12,np.linalg.norm(v))
def angle(a,b):return np.degrees(np.arccos(np.clip(a@b,-1,1)))
def read(r,stage):
    if stage in ('future','presented'):return {n:v[stage] for n,v in r['raw'].items()}
    if stage=='target':return {n:v['target'] for n,v in r['targets'].items()}
    return r['meshes'].get(stage,{})
def metrics(b,side):
    h,k,f=[np.array(b[n+'_'+side]['p']) for n in ('thigh','calf','foot')]
    axis=unit(f-h);rad=k-h-axis*((k-h)@axis)
    return dict(pole=unit(rad),footpole=R.from_quat(b['foot_'+side]['q']).inv().apply(unit(rad)),
        bodypole=R.from_quat(b['pelvis']['q']).inv().apply(unit(rad)),radius=np.linalg.norm(rad),
        bend=angle(unit(k-h),unit(f-k)),upper=np.linalg.norm(k-h),lower=np.linalg.norm(f-k),knee=k,foot=f,
        thighq=R.from_quat(b['thigh_'+side]['q']),calfq=R.from_quat(b['calf_'+side]['q']))
output={}
for stage in ['future','presented','target','Mesh','PhysicalMesh']:
  output[stage]={}
  for side in ['l','r']:
    out=[]
    for old,r in zip(rows,rows[1:]):
      b,a=read(r,stage),read(old,stage)
      if 'calf_'+side not in b or 'calf_'+side not in a:continue
      x,y=metrics(b,side),metrics(a,side)
      out.append(dict(tick=r['tick'],pole=angle(y['pole'],x['pole']),footpole=angle(y['footpole'],x['footpole']),
        bodypole=angle(y['bodypole'],x['bodypole']),bend=x['bend'],radius=x['radius'],upper=x['upper'],lower=x['lower'],
        knee_step=np.linalg.norm(x['knee']-y['knee']),foot_step=np.linalg.norm(x['foot']-y['foot']),
        thigh_step=np.degrees((y['thighq'].inv()*x['thighq']).magnitude()),calf_step=np.degrees((y['calfq'].inv()*x['calfq']).magnitude())))
    output[stage][side]=out
    peaks=sorted([x for x in out if 150<=x['tick']<=225],key=lambda x:x['bodypole'],reverse=True)[:7]
    print(stage,side,'PEAKS [tick,bodypole,footpole,bend,radius,knee_step,thigh_step]')
    print([[round(x[k],3) for k in ['tick','bodypole','footpole','bend','radius','knee_step','thigh_step']] for x in peaks])
(p/'kick_current_oct2_analysis.json').write_text(json.dumps(output,indent=2))
