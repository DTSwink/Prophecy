import pathlib,json,re,math,sys
import numpy as np
from scipy.spatial.transform import Rotation as R
p=pathlib.Path('Saved/Diagnostics/RunHandThigh');tag=sys.argv[1]
def read(t):
 d=json.loads((p/(t+'.json')).read_text());assert not d['error'],d['error'];return {r['tick']:r for r in d['rows']}
on=read(tag);old=read('wrist_roll205_base');log=(p/(tag+'.log')).read_text();ref=R.from_quat(list(map(float,re.search(r'WristIdleReference q=([\d.,-]+)',log)[1].split(','))));axis=R.from_quat(on[1]['weapon']['grip']['q']).apply([0,0,1]);idle=ref.apply(axis);up=np.array([0.,0.,1.]);face=ref.inv().apply(up-idle*np.dot(up,idle));face/=np.linalg.norm(face)
rows=[];last={}
for t,r in on.items():
 row={'tick':t}
 for key,src in [('new',on),('old',old)]:
  if t not in src:continue
  q=R.from_quat(src[t]['future']['hand_r']['q']);aim=q.apply(axis);actual=q.apply(face);target=up-aim*np.dot(aim,up);target/=np.linalg.norm(target)
  row[key+'_idle_roll_error']=math.degrees(math.atan2(np.dot(aim,np.cross(target,actual)),np.dot(target,actual)))
  if key in last:
   d=(q*last[key].inv()).as_rotvec();row[key+'_rotation_step']=math.degrees(np.linalg.norm(d));row[key+'_axial_step']=math.degrees(np.dot(d,aim))
  last[key]=q
 if t in old:
  row['target_position_difference']=math.dist(r['future']['hand_r']['p'],old[t]['future']['hand_r']['p']);row['presented_position_difference']=math.dist(r['presented']['hand_r']['p'],old[t]['presented']['hand_r']['p'])
  row['pointing_difference']=math.degrees(math.acos(np.clip(np.dot(R.from_quat(r['future']['hand_r']['q']).apply(axis),R.from_quat(old[t]['future']['hand_r']['q']).apply(axis)),-1,1)))
 rows.append(row)
summary={'samples':[r for r in rows if r['tick'] in (185,187,189,193,197,199,201,203,205,207,209,211,215,217,301,303,305,307,309,369,379,381,483,485,487,489,491)],'max_pointing_difference':max(r.get('pointing_difference',0) for r in rows),'max_target_position_difference':max(r.get('target_position_difference',0) for r in rows),'max_presented_position_difference':max(r.get('presented_position_difference',0) for r in rows)}
(p/(tag+'_roll_metrics.json')).write_text(json.dumps({'summary':summary,'rows':rows},indent=2)+'\n');print(json.dumps(summary,indent=2))
