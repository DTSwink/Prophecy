import sys,json
from pathlib import Path
import numpy as np
import torch
torch.set_num_threads(1)
sys.path.insert(0,'C:/Users/singerie/Documents/Cursor/stepper')
from training.ik import train_upper_pose_controller_pelvis as ctl
from training.ik import train_upper_pose_autoencoder as ud
from training.ik import ik_core as tl
base=Path(__file__).parent/'Diagnostics/TurnParity'
contract=json.loads((Path(__file__).parents[1]/'Content/locomotion/NN/prophecy_upper_body_runtime.json').read_text())
model=ctl.UpperCachedLowerAgent();model.load_state_dict(torch.load(contract['checkpoint_path'],map_location='cpu',weights_only=False)['model']);model.eval()
ue=[json.loads(l) for l in (base/'current_inputs.jsonl').read_text().splitlines()];ue=[r for r in ue if r['actor']=='BP_ProphecyManualPoseAgent_C_1']
x=torch.tensor([r['upper_input'] for r in ue]);delta=torch.tensor([r['upper_delta'] for r in ue])
with torch.inference_mode():
 d=model(x);print('UE vs PyTorch delta max',float((delta-d).abs().max()),'mean',float((delta-d).abs().mean()))
 pred=ud.clean_upper_state(x[:,90:180]+d)
 # Rebuild base independently using the same reference skeleton / training implementation.
 cp=tl.MotionClip(Path(contract['reference_clip_path']),ud.motion_config(),cyclic_animation=True)
 rest=ud.rest_offsets_from_pelvis(cp)
 def base_from_pelvis(pel):
  rot=tl.rotation_6d_to_matrix(pel[:,3:9]);parts=[torch.tensor([1,0,0,0,1,0]).repeat(len(pel),10)]
  for name in ['hand_l','hand_r']:
   hp=(rest[cp.body_names.index(name)][None,None,:]@rot).squeeze(1)+pel[:,:3]
   parts.extend([hp,pel[:,3:9],pel[:,3:9]])
  return ud.clean_upper_state(torch.cat(parts,-1))
 # Pure training recurrence using recorded lower conditioning and root inputs.
 replay=[]; prev=x[:1,:90].clone();cur=torch.tensor([ue[0]['previous_upper']]);basecur=base_from_pelvis(x[:1,189:198])
 for i in range(len(x)):
  nextbase=base_from_pelvis(x[i:i+1,198:207]);prior=ud.clean_upper_state(nextbase+cur-basecur)
  v=torch.cat([prev,prior,x[i:i+1,180:]],-1)
  following=ud.clean_upper_state(prior+model(v));replay.append(following[0]);prev,cur=cur,following;basecur=nextbase
 replay=torch.stack(replay)
 print('Training recurrence vs UE clean output max',float((pred-replay).abs().max()),'mean',float((pred-replay).abs().mean()))
 np.savez(base/'ue_upper_replay.npz',pred=pred.numpy(),replay=replay.numpy(),inputs=x.numpy(),times=np.array([r['time'] for r in ue]))
for path in base.glob('viewer_*.npz'):
 v=np.load(path);print(path.name)
 for bone in ['root','pelvis','spine_05','head']:
  q=v['root_rotations'] if bone=='root' else v['rotations'][:,list(v['bones']).index(bone)]
  rel=q[0].T@q;y=np.unwrap(np.arctan2(rel[:,2,0],rel[:,2,2]))*180/np.pi
  print(bone,'yaw range',np.round([y.min(),y.max(),y[-1]],2),'rate',np.max(np.abs(np.diff(y)))*30,'by5',np.round(y[::5],1))
