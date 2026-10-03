import json,pathlib,sys,numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path(__file__).parent/'Knee202'
for name in sys.argv[1:]:
 rows=json.loads((p/(name+'.json')).read_text())['rows']; by={r['tick']:r for r in rows}
 print(name)
 for t in [197,365,543]:
  print('exit',t)
  for tick in [t-2,t,t+2,t+6,t+12]:
   v=[]
   for k in [tick-2,tick]:
    d=by[k]['raw'];sp=d['spine_05']['presented'];q=R.from_quat(sp['q']);b=d['hand_l']['presented']
    v.append(q.inv().apply(np.array(b['p'])-sp['p']))
   print(tick,'wrist local speed',np.round((v[1]-v[0])*30,2).tolist())
 r=json.loads((p/(name+'_rotation.json')).read_text())
 for t in [197,365,543]:
  a=[d for d in r if t<=d['tick']<t+12]
  print(t,{k:round(max(abs(d[k]) for d in a),3) for k in ['upperarm_l_twist','lowerarm_l_twist','lowerarm_l_swing','hand_l_step']})
