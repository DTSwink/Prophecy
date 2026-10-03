import json,numpy as np
from pathlib import Path
p=Path('Saved/Diagnostics/Knee202');rows=json.loads((p/'baseline.json').read_text())['rows'];out=[]
def length(b,h,k):return np.linalg.norm(np.array(b[h]['p'])-b[k]['p'])
def bend(h,k,f):
 u=k-h;v=f-k;return float(np.degrees(np.arccos(np.clip(u@v/np.linalg.norm(u)/np.linalg.norm(v),-1,1))))
def solve(h,k,f,upper,lower):
 delta=f-h;dist=np.linalg.norm(delta);axis=delta/dist;pole=k-h-axis*((k-h)@axis);pole/=np.linalg.norm(pole)
 lower=np.clip(lower,abs(dist-upper)+1e-6,dist+upper-1e-6);along=(upper*upper-lower*lower+dist*dist)/(2*dist)
 return h+axis*along+pole*np.sqrt(max(0,upper*upper-along*along))
for r in rows:
 if not 190<=r['tick']<=209:continue
 b={n:v['target'] for n,v in r['targets'].items()};h,k,f=[np.array(b[n+'_r']['p']) for n in ('thigh','calf','foot')]
 prev={n:v['previous'] for n,v in r['targets'].items()};future={n:v['future'] for n,v in r['targets'].items()};alpha=r['alpha']
 upper=(1-alpha)*length(prev,'thigh_r','calf_r')+alpha*length(future,'thigh_r','calf_r')
 lower=(1-alpha)*length(prev,'calf_r','foot_r')+alpha*length(future,'calf_r','foot_r')
 # Change only the presentation upper length before retirement; retain actual
 # published hip/ankle/pole/calf length, with no recurrent state changes.
 fixed=solve(h,k,f,upper,lower) if r['tick']<200 else k
 item=dict(t=r['tick'],before=bend(h,k,f),after=bend(h,fixed,f),before_knee=k.tolist(),after_knee=fixed.tolist(),published_upper=upper,actual_upper=float(np.linalg.norm(k-h)))
 out.append(item)
 if 197<=r['tick']<=203:print(r['tick'],'bend before/consistent-upper',round(item['before'],5),round(item['after'],5),'upper lengths',round(item['actual_upper'],6),round(upper,6))
for i,r in enumerate(out):
 if r['t']==200:
  print('Tick200 knee step cm',np.linalg.norm(np.array(r['before_knee'])-out[i-1]['before_knee']),np.linalg.norm(np.array(r['after_knee'])-out[i-1]['after_knee']))
(p/'length_probe.json').write_text(json.dumps(out,indent=2))
