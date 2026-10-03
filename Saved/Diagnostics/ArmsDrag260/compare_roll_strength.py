from pathlib import Path
import json,math
import numpy as np
from scipy.spatial.transform import Rotation as R
p=Path(__file__).parent
def rows(tag):
 d=json.loads((p/(tag+'.json')).read_text());assert not d['error'],d['error']
 return {r['tick']:r for r in d['rows'] if r['player']}
old=rows('wrap_roll75_before');new=rows('wrap_roll300_after');raw=rows('wrap_roll75_off_wrist')
axis=R.from_quat(new[1]['weapon']['grip']['q']).apply([0,0,1])
aimmax={'future':0.,'presented':0.};posmax=leftmax=forearmmax=0.;samples=[]
for t,a in new.items():
 b=old[t];c=raw[t]
 for domain in ('future','presented'):
  for bone in ('upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r'):
   posmax=max(posmax,math.dist(a[domain][bone]['p'],b[domain][bone]['p']))
  q=R.from_quat(a[domain]['hand_r']['q']);oldq=R.from_quat(b[domain]['hand_r']['q'])
  aimmax[domain]=max(aimmax[domain],float(np.linalg.norm(q.apply(axis)-oldq.apply(axis))))
  forearmmax=max(forearmmax,(R.from_quat(a[domain]['lowerarm_r']['q'])*R.from_quat(b[domain]['lowerarm_r']['q']).inv()).magnitude())
  leftmax=max(leftmax,(R.from_quat(a[domain]['hand_l']['q'])*R.from_quat(b[domain]['hand_l']['q']).inv()).magnitude())
 if 300<=t<=312:
  q=R.from_quat(a['presented']['hand_r']['q']);free=R.from_quat(c['presented']['hand_r']['q'])
  samples.append(dict(tick=t,correction_degrees=math.degrees((q*free.inv()).magnitude())))
out=dict(max_arm_position_difference_cm=posmax,max_blade_direction_vector_difference=aimmax,max_left_rotation_difference_radians=leftmax,max_forearm_rotation_difference_radians=forearmmax,release=samples)
(p/'roll_strength_comparison.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
