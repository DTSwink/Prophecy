import json,pathlib,sys,collections
import numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path(__file__).parent
mode=sys.argv[1] if len(sys.argv)>1 else 'baseline'
d=json.loads((p/(mode+'.json')).read_text());rows={r['tick']:r for r in d['rows']}
parents={'upperarm_r':'clavicle_r','lowerarm_r':'upperarm_r','hand_r':'lowerarm_r','upperarm_l':'clavicle_r'}
def local(row,b,kind='presented',parent=None):
 bq=row['bones'][b][kind];pq=row['bones'][parent or parents[b]][kind]
 q=R.from_quat(pq['q']);return q.inv().apply(np.array(bq['p'])-pq['p']),q.inv()*R.from_quat(bq['q'])
stats=[]
for t,r in rows.items():
 if t-1 not in rows:continue
 prev=rows[t-1];out={'tick':t}
 for b in parents:
  for k in ('presented','future'):
   _,q=local(r,b,k);_,qp=local(prev,b,k)
   out[b+'_'+k+'_deg']=float(np.rad2deg((qp.inv()*q).magnitude()))
 for k in ('future','presented','target'):
  for parent in ('pelvis','clavicle_r'):
   x,_=local(r,'hand_r',k,parent);xp,_=local(prev,'hand_r',k,parent)
   out['hand_'+k+'_'+parent+'_cm']=float(np.linalg.norm(x-xp))
 out['root_cm']=float(np.linalg.norm(np.array(r['root'])-prev['root']))
 stats.append(out)
(p/(mode+'-speeds.json')).write_text(json.dumps(stats,indent=2))
print('tick  hand/pelvis hand/clav upperLocal foreLocal handLocal root  futureHand')
for r in stats:
 if 124<=r['tick']<=158:
  print(r['tick'],*[round(r[k],3) for k in ('hand_presented_pelvis_cm','hand_presented_clavicle_r_cm','upperarm_r_presented_deg','lowerarm_r_presented_deg','hand_r_presented_deg','root_cm','hand_future_pelvis_cm')])
