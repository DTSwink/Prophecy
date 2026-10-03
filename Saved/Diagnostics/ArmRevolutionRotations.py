import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics/Knee202')
for mode in ('current','no_cone','no_inertia'):
 f=p/f'arm_revolution_{mode}.json'
 if not f.exists():continue
 rows=json.loads(f.read_text())['rows'];print(mode)
 for lo,hi in ((165,189),(189,220),(189,310)):
  sel=[r for r in rows if lo<=r['tick']<=hi]
  for bone,parent,tip in [('upperarm_r','clavicle_r','lowerarm_r'),('lowerarm_r','upperarm_r','hand_r'),('hand_r','lowerarm_r','hand_r')]:
   qs=[];axes=[]
   for x in sel:
    d={k:v['future'] for k,v in x['raw'].items()};par=R.from_quat(d[parent]['q']);q=par.inv()*R.from_quat(d[bone]['q']);qs.append(q)
    v=par.inv().apply(np.array(d[tip]['p'])-d[bone if bone!='hand_r' else parent]['p']);axes.append(v/max(np.linalg.norm(v),1e-8))
   delta=[(b*a.inv()).as_rotvec() for a,b in zip(qs,qs[1:])]
   path=np.degrees(sum(np.linalg.norm(v) for v in delta));twist=np.degrees(sum(v@axis for v,axis in zip(delta,axes)))
   print(lo,hi,bone,'local rotation path',round(path,1),'twist',round(twist,1),'maxstep',round(np.degrees(max(np.linalg.norm(v) for v in delta)),1))
