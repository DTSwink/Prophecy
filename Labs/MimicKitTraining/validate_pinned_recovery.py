"""Validate planted hands through the interpolation used by training."""
from pin_recovery_hands import *
from anim.motion_lib import MotionLib
import yaml

def main():
 files=[DEST/f'getUp_{side}_quick_pinned.pkl' for side in ('front','back')]
 manifest=DEST/'motions.yaml'
 manifest.write_text(yaml.safe_dump(dict(motions=[dict(file=str(p),weight=1.) for p in files])))
 lib=MotionLib(str(manifest),model,'cpu');reports=[]
 for i,(side,path) in enumerate(zip(('front','back'),files)):
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
  pin=[]
  anchors=json.loads((DEST/'report.json').read_text())[i]['hands']
  for h in anchors:
   b=names.index(h['side']+'_hand');mask=(times.numpy()>=h['start_frame']/30-1e-7)&(times.numpy()<=h['end_frame']/30+1e-7)
   pos=p[mask,b];r=R.from_quat(q[mask,b]);dr=(r[0].inv()*r).magnitude()
   shape=next(s for s in shapes if s[0]==b)
   pin.append(dict(side=h['side'],max_anchor_error_m=float(np.linalg.norm(pos-np.array(h['anchor_position']),axis=1).max()),
    rotation_excursion_deg=float(np.rad2deg(dr).max()),min_floor_m=float(bottoms[mask][:,gid==b].min())))
  original=pickle.loads((ROOT/f'Saved/MimicKitEquipment/package/motions/recovery/getUp_{side}_quick_robotic.pkl').read_bytes())['frames']
  actual=pickle.loads(path.read_bytes())['frames']
  report=dict(clip=side,samples=count,frequency_hz=960,limit_violations=violations,hands=pin,
   pelvis_exact=bool(np.array_equal(original[:,:6],actual[::round(pickle.loads(path.read_bytes())['fps']/30),:6])),
   minimum_hand_floor_m=float(bottoms[:,np.isin(gid,hands)].min()),
   minimum_per_body_m={name:float(bottoms[:,gid==k].min()) for k,name in enumerate(names)},
   finite_motion_velocities=bool(torch.isfinite(dof).all() and torch.isfinite(vel).all() and torch.isfinite(ang).all()))
  reports.append(report);print(json.dumps(report),flush=True)
 (DEST/'validation.json').write_text(json.dumps(reports,indent=2))
 assert all(not r['limit_violations'] and r['pelvis_exact'] and r['minimum_hand_floor_m']>=0 and r['finite_motion_velocities'] and all(h['max_anchor_error_m']<.00025 and h['rotation_excursion_deg']<1.2 for h in r['hands']) for r in reports),reports
if __name__=='__main__':main()
