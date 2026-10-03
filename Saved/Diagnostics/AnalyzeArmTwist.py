import json,sys,pathlib
import numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path(__file__).parent/'Knee202'
name=sys.argv[1] if len(sys.argv)>1 else 'arm_twist_before'
rows=json.loads((p/(name+'.json')).read_text())['rows']
def unit(v):return v/max(np.linalg.norm(v),1e-12)
def get(row,b):return row['raw'][b]['presented']
data=[]
for a,b in zip(rows,rows[1:]):
 if not a.get('raw') or not b.get('raw'):continue
 try:
  qa=R.from_quat(get(a,'spine_05')['q']);qb=R.from_quat(get(b,'spine_05')['q'])
  d={'tick':b['tick'],'attack':b['attack']}
  for side in ['l','r']:
   for bone,end in [('upperarm','lowerarm'),('lowerarm','hand'),('hand',None)]:
    key=bone+'_'+side
    ra=qa.inv()*R.from_quat(get(a,key)['q']);rb=qb.inv()*R.from_quat(get(b,key)['q'])
    v=(rb*ra.inv()).as_rotvec()*180/np.pi
    d[key+'_step']=float(np.linalg.norm(v))
    if end:
     axis=qb.inv().apply(unit(np.array(get(b,end+'_'+side)['p'])-get(b,key)['p']))
     d[key+'_twist']=float(np.dot(v,axis));d[key+'_swing']=float(np.linalg.norm(v-axis*np.dot(v,axis)))
  data.append(d)
 except KeyError:pass
for lo,hi in [(190,240),(360,410),(538,590)]:
 vals=[d for d in data if lo<=d['tick']<=hi]
 print('WINDOW',lo,hi)
 for k in ['hand_l_step','lowerarm_l_step','lowerarm_l_twist','lowerarm_l_swing','upperarm_l_step','hand_r_step']:
  top=sorted(vals,key=lambda x:abs(x[k]),reverse=True)[:4]
  print(k,[(d['tick'],round(d[k],3)) for d in top])
 print('early', [{k:round(v,3) if isinstance(v,float) else v for k,v in d.items() if k in ['tick','hand_l_step','lowerarm_l_twist','lowerarm_l_swing']} for d in vals[:14]])
(p/(name+'_rotation.json')).write_text(json.dumps(data))
