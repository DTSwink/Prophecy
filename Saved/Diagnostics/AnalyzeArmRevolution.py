import json,pathlib,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics/Knee202');f=p/'arm_revolution_current.json'
if not f.exists():raise SystemExit('capture pending')
r=json.loads(f.read_text())['rows']
print('rows',len(r),'range',r[0]['tick'],r[-1]['tick'])
last=None
for x in r:
 if x['attack']!=last: print('state',x['tick'],x['attack']);last=x['attack']
for kind in ('future','presented','physical'):
 angles=[]
 for x in r:
  b={k:v[kind] for k,v in x['raw'].items()} if kind!='physical' else x['meshes']['PhysicalMesh']
  inv=R.from_quat(b['spine_05']['q']).inv();v=[inv.apply(np.array(b[n]['p'])-b['upperarm_r']['p']) for n in ('lowerarm_r','hand_r')]
  angles.append([x['tick'],*v[0],*v[1]])
 a=np.array(angles);np.savetxt(p/f'arm_revolution_{kind}.csv',a,delimiter=',',header='tick,elbowX,elbowY,elbowZ,handX,handY,handZ')
 print(kind)
 for x in a:
  if 175<=x[0]<=310 and int(x[0])%10==0:print(np.round(x,1))
