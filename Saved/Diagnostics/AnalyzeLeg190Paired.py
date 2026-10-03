import pathlib,json,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics');data=json.loads((p/'Leg190-paired.json').read_text())['rows']
def bend(b,s):
 h,k,f=[np.array(b[n+'_'+s]['p']) for n in ('thigh','calf','foot')];u=k-h;v=f-k
 return float(np.degrees(np.arccos(np.clip(u@v/(np.linalg.norm(u)*np.linalg.norm(v)),-1,1))))
for x in data:
 if not 187<=x['tick']<=203 or 'fixed' not in x:continue
 print(x['tick'],*[round(bend(x[n],'r'),3) for n in ('targets','fixed')])
for side in ('l','r'):
 for n in ('targets','fixed'):
  rr=[x for x in data if 189<=x['tick']<=201 and 'fixed' in x]
  values=np.array([bend(x[n],side) for x in rr]);d=np.diff(values)
  print(side,n,'bend variation',sum(abs(d)),'second difference',max(abs(np.diff(d))))
same={}
for name in ('pelvis','foot_l','foot_r'):
 rr=[x for x in data if 'fixed' in x];same[name]=dict(position=max(np.linalg.norm(np.array(x['targets'][name]['p'])-x['fixed'][name]['p']) for x in rr),rotation=max(float((R.from_quat(x['targets'][name]['q']).inv()*R.from_quat(x['fixed'][name]['q'])).magnitude()) for x in rr))
print('Same-frame invariants',same)
(p/'Leg190-paired-summary.json').write_text(json.dumps(same,indent=2))
