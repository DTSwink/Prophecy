"""Verify actual MotionLib interpolation, joint constraints and collider floor clearance."""
from clean_recovery_preview import *
from anim.motion_lib import MotionLib
import yaml
files=[OUT/f'getUp_{side}_quick_clean.pkl' for side in ('front','back')]
manifest=OUT/'motions.yaml';manifest.write_text(yaml.safe_dump(dict(motions=[dict(file=str(p),weight=1.) for p in files])))
lib=MotionLib(str(manifest),model,'cpu');reports=[]
for i,path in enumerate(files):
 duration=float(lib.get_motion_length(i));count=round(duration*960)+1
 times=torch.linspace(0,duration,count);ids=torch.full((count,),i,dtype=torch.long)
 root,rot,vel,ang,joints,dof=lib.calc_motion_frame(ids,times)
 p,q=model.forward_kinematics(root,rot,joints);p=p.numpy();q=q.numpy()
 bottoms=np.stack([heights(pos,R.from_quat(qt).as_matrix()) for pos,qt in zip(p,q)])
 frames=np.c_[root.numpy(),R.from_quat(rot.numpy()).as_rotvec(),lib.joint_rot_to_dof(joints).numpy()]
 violations=[]
 for j in meta['joints']:
  v,_=sampled_coordinates(model,j,frames,1);bad=violation(v,j)
  if bad.any():violations.append(dict(body=j['body'],count=int(bad.sum()),first_time=float(times[np.flatnonzero(bad)[0]])))
 report=dict(clip=path.name,samples=count,frequency_hz=960,limit_violations=violations,
  minimum_clearance_m=float(bottoms.min()),minimum_per_body_m={name:float(bottoms[:,gid==k].min()) for k,name in enumerate(names)},
  finite_motion_velocities=bool(torch.isfinite(dof).all() and torch.isfinite(vel).all() and torch.isfinite(ang).all()))
 reports.append(report);print(json.dumps(report),flush=True)
(OUT/'validation.json').write_text(json.dumps(reports,indent=2))
assert all(not r['limit_violations'] and r['minimum_clearance_m']>=-2e-5 and r['finite_motion_velocities'] for r in reports),reports
