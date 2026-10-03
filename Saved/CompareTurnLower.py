import sys,json
from pathlib import Path
import numpy as np
import torch
torch.set_num_threads(1)
stepper=Path('C:/Users/singerie/Documents/Cursor/stepper');sys.path.insert(0,str(stepper))
from training.ik import train_upper_pose_controller_pelvis as ctl
from training.ik import train_upper_pose_controller as rt
from training.ik import train_upper_pose_autoencoder as ud
from training.ik import train_simple_ae_controller as lc
from training.ik import ik_core as tl,visualize
base=Path(__file__).parent/'Diagnostics/TurnParity'
c=json.loads((Path(__file__).parents[1]/'Content/locomotion/NN/prophecy_upper_body_runtime.json').read_text())
uppercp=torch.load(c['checkpoint_path'],map_location='cpu',weights_only=False)
lowerpath=Path(uppercp['metadata']['lower_selection']['walk']['checkpoint']); lowerpath=lowerpath if lowerpath.is_absolute() else stepper/lowerpath
checkpoint=torch.load(lowerpath,map_location='cpu',weights_only=False);device=torch.device('cpu');cfg=rt.apply_checkpoint_config(checkpoint,device)
relative='walk_transitions/M_Neutral_Stand_Turn_180_R.npz'
clip=tl.MotionClip(ud.ORIGINAL_ROOT/relative,cfg,cyclic_animation=False)
model=visualize.load_model(checkpoint,clip,cfg,device);model.eval()
runtime=rt.build_category_runtime('walk',[relative],checkpoint,cfg,model,device);runtime.install_policy()
rows=[json.loads(l) for l in (base/'current_inputs.jsonl').read_text().splitlines()];rows=[r for r in rows if r['actor']=='BP_ProphecyManualPoseAgent_C_1']
x=torch.tensor([r['lower_input'] for r in rows]);actual=torch.tensor([r['published_lower'] for r in rows]);u=np.load(base/'ue_upper_replay.npz')
with torch.inference_mode():
 raw=lc.model_raw_output(model,x,x[:,:41],runtime.store)
 expected,unp,pins=lc.clean_output_vector_pair_with_pin_prob(raw,runtime.store,x[:,:41],x[:,41:82])
 e=(expected-actual).abs();print('lower transition max/mean',float(e.max()),float(e.mean()),'worst col',torch.argmax(e).item()%41)
 print('per block',[(a,b,float(e[:,a:b].max())) for a,b in [(0,9),(9,12),(12,25),(25,28),(28,41)]])
 print('pin mode',lc.FOOT_ROLL_PIN_MODE,'cfg clamps',[(k,v) for k,v in vars(cfg).items() if 'clamp' in k or 'roll' in k or 'fake' in k])
 # Decode the exact recorded upper result, with the next pelvis/frame used by training.
 pelvis=torch.tensor(u['inputs'][:,198:207]);upper=torch.tensor(u['pred']);n=len(x)
 seed=torch.tensor([[1.,0,0],[0,0,-1],[0,1,0]])
 rootinfo=torch.tensor([r['roots'] for r in rows]);yaw=rootinfo[:,7]
 heading=torch.eye(3).repeat(n,1,1);heading[:,0,0]=yaw.cos();heading[:,0,2]=-yaw.sin();heading[:,2,0]=yaw.sin();heading[:,2,2]=yaw.cos()
 rootrot=seed@heading;rootpos=rootinfo[:,4:7]
 # lower vector exact next state reconstructed from captured next-pelvis and feet heading.
 lower=actual.clone()
 for p,r,f in [(0,3,198),(9,12,261),(25,28,270)]:
  feat=torch.tensor(u['inputs'][:,f:f+9]);lower[:,p:p+3]=feat[:,:3]@seed.T;lower[:,r:r+6]=tl.rotmat_to_6d(tl.rotation_6d_to_matrix(feat[:,3:])@seed.T)
 # Thigh rotations are rebased from output carrier to next carrier.
 delta_yaw=rootinfo[:,7]-rootinfo[:,11];bridge=torch.eye(3).repeat(n,1,1);bridge[:,0,0]=delta_yaw.cos();bridge[:,0,2]=delta_yaw.sin();bridge[:,2,0]=-delta_yaw.sin();bridge[:,2,2]=delta_yaw.cos()
 for r in [18,34]: lower[:,r:r+6]=tl.rotmat_to_6d(tl.rotation_6d_to_matrix(actual[:,r:r+6])@seed@bridge@seed.T)
 p,q=ctl.decode_rows(runtime,1.,lower,upper,pelvis,rootpos,rootrot,heading,torch.zeros(n,dtype=torch.long))
 np.savez(base/'ue_training_decoded.npz',positions=p.numpy(),rotations=q.numpy(),times=np.array([r['time'] for r in rows]),bones=runtime.full_by_mode[1.].body_names,lower_error=e.numpy(),pins=pins.numpy(),raw=raw.numpy())
