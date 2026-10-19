"""Correct only intervals that fail dense floor/limit verification."""
from clean_recovery_preview import *
from anim.motion_lib import MotionLib
import yaml
reports=[]
for side in ('front','back'):
 path=OUT/f'getUp_{side}_quick_clean.pkl';data=pickle.loads(path.read_bytes());frames=data['frames'];n=len(frames)
 manifest=OUT/'refine-motion.yaml';manifest.write_text(yaml.safe_dump(dict(motions=[dict(file=str(path),weight=1.)])))
 lib=MotionLib(str(manifest),model,'cpu');times=torch.linspace(0,float(lib.get_motion_length(0)),(n-1)*32+1)
 root,rot,vel,ang,joints,dof=lib.calc_motion_frame(torch.zeros(len(times),dtype=torch.long),times)
 p,q=model.forward_kinematics(root,rot,joints);p=p.numpy();q=q.numpy();low=np.stack([heights(pos,R.from_quat(qt).as_matrix()) for pos,qt in zip(p,q)])
 clearance=np.full((n,len(shapes)),.002);selected=set()
 for i in range(n-1):
  worst=low[i*32:(i+1)*32+1].min(0);needed=worst<0
  if needed.any():
   selected.update((i,i+1));clearance[i:i+2,needed]=np.maximum(clearance[i:i+2,needed],.004-worst[needed])
 dense=np.c_[root.numpy(),R.from_quat(rot.numpy()).as_rotvec(),lib.joint_rot_to_dof(joints).numpy()]
 for e in entries:
  v,_=sampled_coordinates(model,e['j'],dense,1);bad=np.flatnonzero(violation(v,e['j']))
  if len(bad):
   for i in bad//32:selected.update((int(i),min(n-1,int(i)+1)))
   e['scale']*=.98
   a=e['start'];bounds[a,0]+=.005;bounds[a,1]-=.005
 print('Refine',side,'frames',sorted(selected),flush=True)
 fixed,stats=clean(frames,clearance,selected);path.write_bytes(pickle.dumps(dict(data,frames=fixed)))
 reports.append(dict(side=side,selected=sorted(selected),stats=stats))
(OUT/'refinement.json').write_text(json.dumps(reports,indent=2))
# Rebuild visual data without re-running the full optimizer.
sys.argv.append('--reuse');main()
