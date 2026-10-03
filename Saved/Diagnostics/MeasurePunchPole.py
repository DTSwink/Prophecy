import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics');rows=json.loads((p/'PunchKneeBaseline-live.json').read_text())['rows']
def u(v):return v/max(np.linalg.norm(v),1e-12)
def m(r,s):
 b=r['targets'];h,k,f=[np.array(b[n+'_'+s]['p']) for n in ('thigh','calf','foot')];a=u(f-h);rad=k-h-a*np.dot(k-h,a);q=R.from_quat(b['foot_'+s]['q']);return u(rad),q.inv().apply(u(rad)),np.linalg.norm(rad)
def angle(a,b):return float(np.rad2deg(np.arccos(np.clip(np.dot(a,b),-1,1))))
for side in ('l','r'):
 print('SIDE',side)
 out=[]
 for i in range(1,len(rows)):
  if rows[i]['attack']!='None':continue
  a=m(rows[i-1],side);b=m(rows[i],side)
  out.append((rows[i]['tick'],angle(a[0],b[0]),angle(a[1],b[1]),b[2]))
 print('largest',sorted(out,key=lambda v:v[2],reverse=True)[:12])
 print('firstexit',[tuple(round(x,3) for x in v) for v in out if 136<=v[0]<=145])
