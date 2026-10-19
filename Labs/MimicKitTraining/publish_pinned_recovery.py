"""Publish the baked candidate with an original-motion overlay."""
from pin_recovery_hands import *
from anim.motion_lib import MotionLib
import yaml
preview=json.loads((DEST/'data.json').read_text())
paths=[ROOT/f'Saved/MimicKitEquipment/package/motions/recovery/getUp_{s}_quick_robotic.pkl' for s in ('front','back')]
manifest=DEST/'original-motions.yaml';manifest.write_text(yaml.safe_dump(dict(motions=[dict(file=str(p),weight=1.) for p in paths])))
lib=MotionLib(str(manifest),model,'cpu')
for i,side in enumerate(('front','back')):
 path=DEST/f'getUp_{side}_quick_pinned.pkl';data=pickle.loads(path.read_bytes());frames=data['frames']
 original=pickle.loads(paths[i].read_bytes())['frames']
 n=len(frames);times=torch.linspace(0,float(lib.get_motion_length(i)),n);ids=torch.full((n,),i,dtype=torch.long)
 root,rot,vel,ang,joints,dof=lib.calc_motion_frame(ids,times)
 frames[:,:3]=root.numpy();frames[:,3:6]=R.from_quat(rot.numpy()).as_rotvec()
 frames[::4,:6]=original[:,:6]
 path.write_bytes(pickle.dumps(data))
 p,q=fk(frames);pose=np.concatenate([p,q],-1);pose[:,:,:2]-=p[0,0,:2]
 op,oq=model.forward_kinematics(root,rot,joints);old=np.concatenate([op.numpy(),oq.numpy()],-1);old[:,:,:2]-=old[0,0,:2]
 row=next(c for c in preview['clips'] if side in c['id']);row.update(poses=pose.tolist(),original_poses=old.tolist(),fps=120,frames=n)
(DEST/'data.json').write_text(json.dumps(preview,separators=(',',':')))
