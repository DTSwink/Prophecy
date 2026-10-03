import pathlib,sys,json,numpy as np,torch
stepper=pathlib.Path(r'C:\Users\singerie\Documents\Cursor\stepper');sys.path.insert(0,str(stepper));torch.set_num_threads(1)
from training.ik import train_upper_pose_controller_pelvis as ctl
p=pathlib.Path('Saved/Diagnostics/RunHandThigh');c=json.load(open('Content/locomotion/NN/prophecy_upper_body_runtime.json'))
def selected_cache_only(_):raise FileNotFoundError('Selected clip only')
ctl.resolve_cached_lower_path=selected_cache_only
report={}
cases=[('viewer_unarmed','authored_pruned_npz',-133.3,-119.2),('viewer_sword','holding_sword_npz',-133.3,-119.2),('ue_gaze_sword','holding_sword_npz',-120.4166633,0.)]
for tag,folder,gaze,initial in cases:
 source=stepper/'training/slashes2/walk_run_sword_prep'/folder/'run_omni/M_Neutral_Run_Loop_F.npz'
 print('START',tag,flush=True)
 roll=ctl.rollout_upper_cached_lower_checkpoint(pathlib.Path(c['checkpoint_path']),source,gaze=(gaze/170.,0.),initial_gaze=(initial/170.,0.),device='cpu')
 names=c['body_names'];out={}
 for side in ['l','r']:
  hand=roll.positions[:,names.index('hand_l')];a=roll.positions[:,names.index('thigh_'+side)];b=roll.positions[:,names.index('calf_'+side)];d=b-a
  f=np.clip(np.sum((hand-a)*d,axis=1)/np.sum(d*d,axis=1),0,1);distance=np.linalg.norm(hand-a-f[:,None]*d,axis=1)*100
  i=int(np.argmin(distance));out[side]=dict(min_cm=float(distance[i]),frame=i)
 report[tag]=dict(mode=roll.mode,step=roll.step,frames=len(roll.positions),gaze=gaze,initial_gaze=initial,distances=out)
 np.savez(p/(tag+'.npz'),positions=roll.positions,rotations=roll.rotations,root_positions=roll.root_positions,root_rotations=roll.root_rotations,windows=roll.ae_windows)
 (p/'stepper_gaze_comparison.json').write_text(json.dumps(report,indent=2));print(json.dumps(report[tag]),flush=True)
