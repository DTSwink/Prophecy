import pathlib,sys,json,numpy as np,torch
stepper=pathlib.Path(r'C:\Users\singerie\Documents\Cursor\stepper');sys.path.insert(0,str(stepper));torch.set_num_threads(1)
from training.ik import train_upper_pose_controller_pelvis as ctl
p=pathlib.Path('Saved/Diagnostics/RunHandThigh');c=json.load(open('Content/locomotion/NN/prophecy_upper_body_runtime.json'))
def selected_cache_only(_):raise FileNotFoundError('Use viewer fallback for selected clip only')
ctl.resolve_cached_lower_path=selected_cache_only
report={}
for folder,suffix in [('authored_pruned_npz','B'),('authored_pruned_npz','F'),('holding_sword_npz','F')]:
 source=stepper/'training/slashes2/walk_run_sword_prep'/folder/'run_omni'/f'M_Neutral_Run_Loop_{suffix}.npz'
 tag=folder+'_'+suffix
 print('START',tag,flush=True)
 roll=ctl.rollout_upper_cached_lower_checkpoint(pathlib.Path(c['checkpoint_path']),source,gaze=(0.,0.),device='cpu')
 names=list(roll.body_names) if hasattr(roll,'body_names') else c['body_names']
 out={}
 for side in ['l','r']:
  hand=roll.positions[:,names.index('hand_l')];a=roll.positions[:,names.index('thigh_'+side)];b=roll.positions[:,names.index('calf_'+side)];d=b-a
  t=np.clip(np.sum((hand-a)*d,axis=1)/np.sum(d*d,axis=1),0,1);distance=np.linalg.norm(hand-a-t[:,None]*d,axis=1)*100
  i=int(np.argmin(distance));out[side]=dict(min_cm=float(distance[i]),frame=i)
 report[tag]=dict(mode=roll.mode,step=roll.step,frames=len(roll.positions),distances=out,source=str(source),root_start=roll.root_positions[0].tolist(),root_end=roll.root_positions[-1].tolist())
 np.savez(p/(tag+'.npz'),positions=roll.positions,rotations=roll.rotations,root_positions=roll.root_positions,root_rotations=roll.root_rotations,windows=roll.ae_windows if hasattr(roll,'ae_windows') else np.array([]))
 (p/'stepper_comparison.json').write_text(json.dumps(report,indent=2));print(json.dumps(report[tag]),flush=True)
