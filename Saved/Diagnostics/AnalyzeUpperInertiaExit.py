import json,numpy as np
from pathlib import Path
from scipy.spatial.transform import Rotation as R
p=Path('Saved/Diagnostics/Knee202')
for tag in ['upper_inertia_current','upper_inertia_isolated']:
 f=p/(tag+'.json')
 if not f.exists():continue
 rows=json.loads(f.read_text())['rows'];rr={r['tick']:r for r in rows}
 print(tag)
 def xyz(t,b,slot='future'):return np.array(rr[t]['raw'][b][slot]['p'])
 def local(t):
  s=rr[t]['raw']['spine_05']['future'];return R.from_quat(s['q']).inv().apply(xyz(t,'hand_r')-s['p'])
 for t in range(186,205,2):
  v=(xyz(t,'hand_r')-xyz(t-2,'hand_r'))*30
  pv=(np.array(rr[t]['meshes']['PhysicalMesh']['hand_r']['p'])-rr[t-2]['meshes']['PhysicalMesh']['hand_r']['p'])*30
  lv=(local(t)-local(t-2))*30
  print(t,'hand world cm/s',np.round(v,2),'torso-local',np.round(lv,2),'physical',np.round(pv,2),'state',rr[t]['attack'])
 for end in [190,192,194]:
  start=end-2
  def relative(t):
   c=rr[t]['raw']['clavicle_r']['future'];q=R.from_quat(c['q']);return np.array(c['p']),q,q.inv().apply(xyz(t,'hand_r')-c['p'])
  pa,qa,la=relative(start);pb,qb,lb=relative(end)
  print('DECOMPOSE',end,'clavicle translation',np.round((pb-pa)*30,2),'clavicle rotation',np.round((qb.apply(la)-qa.apply(la))*30,2),'arm relative motion',np.round(qb.apply(lb-la)*30,2))
 for b in ['spine_05','clavicle_r','upperarm_r','hand_r']:
  velocities=[]
  for t in [190,192,194]:
   qa=R.from_quat(rr[t-2]['raw'][b]['future']['q']);qb=R.from_quat(rr[t]['raw'][b]['future']['q'])
   velocities.append(np.round((qb*qa.inv()).as_rotvec()*30*180/np.pi,2).tolist())
  print('ANGULAR world deg/s',b,velocities)
