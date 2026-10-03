import json,re,numpy as np
from scipy.spatial.transform import Rotation as R
from pathlib import Path
header=Path('Source/GameAnimationSample3/Private/ProphecyFKReturnData.h').read_text()
idle={}
for side in ['l','r']:
 line=next(l for l in header.splitlines() if 'TEXT("lowerarm_'+side+'")' in l)
 q=[float(x.rstrip('f')) for x in re.search(r'3, \{([^}]+)',line)[1].split(',')];idle[side]=R.from_quat(q)
gt=json.loads(Path('Content/locomotion/NN/prophecy_slash_half_gt.json').read_text());names=gt['bone_names'];out={}
for family,f in gt['families'].items():
 pose=np.asarray(f['pose_current']);errors={}
 for side in ['l','r']:
  u,e,h=[names.index(b+'_'+side) for b in ['upperarm','lowerarm','hand']]
  ref=R.from_quat(pose[u,3:])*idle[side];axis=np.array([1 if side=='l' else -1,0,0]);a=ref.apply(axis);b=pose[h,:3]-pose[e,:3];b/=np.linalg.norm(b);q=np.r_[np.cross(a,b),1+np.dot(a,b)];q/=np.linalg.norm(q);corrected=R.from_quat(q)*ref
  errors[side]=float(np.degrees((R.from_quat(pose[e,3:]).inv()*corrected).magnitude()))
 out[family]=errors
print(json.dumps(out,indent=2));Path('Saved/Diagnostics/ArmedSpineHitch/forearm-target-mismatch.json').write_text(json.dumps(out,indent=2))
rows=json.loads(Path('Saved/Diagnostics/Knee202/armed_spine_after.json').read_text())['rows'];sumdeg=0
for a,b in zip(rows,rows[1:]):
 if 138<=b['tick']<=152:
  q1=R.from_quat(a['raw']['hand_r']['presented']['q']);q2=R.from_quat(b['raw']['hand_r']['presented']['q']);d=float(np.degrees((q1.inv()*q2).magnitude()));sumdeg+=d;print('hand',b['tick'],round(d,3))
print('hand cumulative',sumdeg)
