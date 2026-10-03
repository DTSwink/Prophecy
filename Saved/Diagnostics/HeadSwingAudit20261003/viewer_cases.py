import sys,json,hashlib,time
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
import torch
torch.set_num_threads(2)
stepper=Path('C:/Users/singerie/Documents/Cursor/stepper');sys.path.insert(0,str(stepper))
from training.ik import train_upper_pose_controller_pelvis as c
p=Path(__file__).parent;identity=json.loads((p/'checkpoint.json').read_text());cp=Path(identity['path'])
cache=stepper/'training/experimental/upper/upper_lower_cache_runturns_shared_d01d632f.pt'
expected=identity['metadata'].get('lower_cache_sha256','').lower()
actual=hashlib.sha256(cache.read_bytes()).hexdigest()
assert not expected or expected==actual,(expected,actual)
c.resolve_cached_lower_path=lambda metadata:cache
original=c.UpperCachedLowerAgent.forward;inputs=[];outputs=[]
def observed(self,x):
 y=original(self,x);inputs.append(x.detach().cpu().numpy().copy());outputs.append(y.detach().cpu().numpy().copy());return y
c.UpperCachedLowerAgent.forward=observed
report=[]
for side in ('F_R','F_L','B_R','B_L'):
 for drawn in (False,True):
  for gaze in (0.,-1.):
   folder='holding_sword_npz' if drawn else 'authored_pruned_npz'
   source=stepper/f'training/slashes2/walk_run_sword_prep/{folder}/run_transitions/M_Neutral_Run_Reface_Start_{side}_180.npz'
   name=f'viewer_{side}_{"sword" if drawn else "no_sword"}_gaze{gaze:g}'
   inputs.clear();outputs.clear();start=time.monotonic()
   r=c.rollout_upper_cached_lower_checkpoint(cp,source,gaze=(gaze,0.),device='cpu')
   names=list(r.clip.body_names);h=names.index('head');n=names.index('neck_02');pel=names.index('pelvis')
   def metrics(pos,rot):
    # Stepper stores row-vector rotations.
    H=R.from_matrix(rot[:,h].transpose(0,2,1));N=R.from_matrix(rot[:,n].transpose(0,2,1));P=R.from_matrix(rot[:,pel].transpose(0,2,1))
    local=N.inv()*H;rel=P.inv().apply(pos[:,h]-pos[:,pel])*100
    return dict(head_parent_deg_per_policy=np.degrees((local[:-1].inv()*local[1:]).magnitude()).tolist(),
     head_pelvis_displacement_cm_per_policy=np.linalg.norm(np.diff(rel,axis=0),axis=1).tolist())
   m=metrics(r.positions,r.rotations);gt=metrics(r.target_positions,r.target_rotations)
   x=np.concatenate(inputs);y=np.concatenate(outputs)
   np.savez_compressed(p/(name+'.npz'),positions=r.positions,rotations=r.rotations,target_positions=r.target_positions,
    target_rotations=r.target_rotations,inputs=x,deltas=y,roots=r.root_positions,root_rotations=r.root_rotations,names=names)
   entry=dict(name=name,source=str(source),step=r.step,mode=r.mode,gaze=list(r.gaze),frames=len(r.positions),fps=r.fps,
    generated=m,authored=gt,peak_head_deg_per_60hz_tick=max(m['head_parent_deg_per_policy'])/2,
    peak_displacement_cm_per_60hz_tick=max(m['head_pelvis_displacement_cm_per_policy'])/2)
   report.append(entry);(p/'viewer-cases.json').write_text(json.dumps(report,indent=2))
   print(name,'head peak',round(entry['peak_head_deg_per_60hz_tick'],3),'position',round(entry['peak_displacement_cm_per_60hz_tick'],3),'seconds',round(time.monotonic()-start,1),flush=True)
