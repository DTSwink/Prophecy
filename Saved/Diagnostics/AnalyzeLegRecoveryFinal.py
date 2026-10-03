import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics');data=json.loads((p/'LegRecovery-final-live.json').read_text());r=data['rows'];print(data['reason'],len(r))
def unit(x):return x/max(np.linalg.norm(x),1e-12)
def pole(x,s):
 b=x['targets'];h,k,f=[np.array(b[n+'_'+s]['p']) for n in ('thigh','calf','foot')];a=unit(f-h);return R.from_quat(b['foot_'+s]['q']).inv().apply(unit(k-h-a*np.dot(k-h,a)))
for i,x in enumerate(r):
 if i and x['attack']=='None' and r[i-1]['attack']!='None':
  out=[]
  for s in ('l','r'):
   vals=[np.degrees(np.arccos(np.clip(pole(r[j-1],s)@pole(r[j],s),-1,1))) for j in range(i,min(i+12,len(r)))];out.append(max(vals))
  print('exit',x['tick'],'12tick pole peaks',out)
for i,x in enumerate(r):
 if i and 359<=x['tick']<=375 and x['tick']%2:
  d=np.array(x['targets']['pelvis']['p'])-r[i-1]['targets']['pelvis']['p'];print('pelvis',x['tick'],np.round(d,3),np.linalg.norm(d[:2]))
tr=[json.loads(l) for l in (p/'LegRecovery-final-frozen.jsonl').read_text().splitlines()]
print('smoothing frame spans:');frames=sorted(set(round(x['time']*60) for x in tr));last=None
for f in frames:
 if last is None or f-last>3:print('starts',f)
 if frames[-1]==f or frames[frames.index(f)+1]-f>3:print('ends',f)
 last=f
