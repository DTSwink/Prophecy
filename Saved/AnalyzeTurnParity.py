import sys,json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
base=Path(__file__).parent/'Diagnostics/TurnParity'
data=json.loads((base/'current.json').read_text())
rows=[r for r in data['rows'] if r['actor']=='BP_ProphecyManualPoseAgent_C_1']
t=np.array([r['t'] for r in rows]); root=R.from_quat([r['root'][3:] for r in rows]); ry=np.unwrap(root.as_euler('ZYX')[:,0])*180/np.pi
mask=(t>=8)&(t<10)
for b in ['pelvis','spine_05','head']:
 q=R.from_quat([r['bones'][b]['target'][3:] for r in rows]); y=np.unwrap((q*q[0].inv()).as_euler('ZYX')[:,0])*180/np.pi
 print(b,'8-10sec yaw',y[mask].min(),y[mask].max(),'peak time',t[mask][np.argmax(y[mask])],'root max',ry[mask].max())
 if b=='head':
  print('t root head pin')
  for i in np.where(mask)[0][::6]: print(round(t[i],3),round(ry[i],2),round(y[i],2),rows[i]['pin'])
if '--viewer' not in sys.argv: sys.exit()
import torch
torch.set_num_threads(1)
stepper=Path('C:/Users/singerie/Documents/Cursor/stepper');sys.path.insert(0,str(stepper))
from training.ik import train_upper_pose_controller_pelvis as ctl
cp=Path(json.loads((Path(__file__).parents[1]/'Content/locomotion/NN/prophecy_upper_body_runtime.json').read_text())['checkpoint_path'])
for mode in ['holding_sword_npz','authored_pruned_npz']:
 clip=stepper/'training/slashes2/walk_run_sword_prep'/mode/'walk_transitions/M_Neutral_Stand_Turn_180_R.npz'
 result=ctl.rollout_upper_cached_lower_checkpoint(cp,clip,gaze=(0,0),device='cpu')
 np.savez(base/f'viewer_{mode}.npz',positions=result.positions,rotations=result.rotations,roots=result.root_positions,root_rotations=result.root_rotations,frames=result.frame_indices,windows=result.ae_windows,bones=result.clip.body_names)
 print('VIEWER SAVED',mode,result.positions.shape,flush=True)
