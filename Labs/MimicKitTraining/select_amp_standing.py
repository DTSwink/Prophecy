"""Compare candidate standing poses under the unchanged position controller."""
import os,sys,json,pickle
from pathlib import Path
os.environ['PYGLET_HEADLESS']='true'
root=Path('/workspace/mimickit_trial');sys.path.insert(0,str(root/'MimicKit/mimickit'))
import torch,yaml,numpy as np
from amp_standing import StandingAMPEnv
from util import torch_util
os.chdir(root/'MimicKit');torch.set_num_threads(1)
cfg=yaml.safe_load(Path('data/envs/amp_humanoid_env.yaml').read_text())
neutral=cfg['init_pose'].copy()
target=json.loads((root/'pipeline/amp_standing_target.json').read_text())
cfg.update(episode_length=2.,num_disc_obs_steps=3,init_pose=target['pose'],
    motion_file=str(root/'pipeline/amp_standing_target.pkl'),reset_seed=20261014,
    reset_joint_noise_degrees=5.,reset_floor_clearance_m=.002)
engine=yaml.safe_load(Path('data/engines/newton_engine.yaml').read_text())
e=StandingAMPEnv(cfg,engine,512,'cuda:0',False);e.reset();c=e._get_char_id()
candidates=[];names=[]
for name in ('humanoid_getup_facedown','humanoid_getup_faceup'):
    source=pickle.loads((root/(name+'.pkl')).read_bytes())['frames']
    for i in range(max(0,len(source)-60),len(source)):
        if source[i][2]>.80:candidates.append(source[i]);names.append(f'{name}:{i}')
# Also evaluate the same recorded upper body on the original planted lower body.
# This is a reference-pose choice only; no controller or physical body changes.
upper=pickle.loads((root/'humanoid_getup_facedown.pkl').read_bytes())['frames'][-1]
combined=neutral.copy();combined[6:20]=upper[6:20]
candidates.extend((combined,neutral));names.extend(('recorded_upper_body_with_planted_neutral_legs','neutral_baseline_only'))
count=len(candidates);assert count<=512
poses=torch.tensor(candidates,device='cuda:0',dtype=torch.float32)
poses=poses[torch.arange(512,device='cuda:0')%count].clone();poses[:,:2]=0
q=torch_util.exp_map_to_quat(poses[:,3:6]);heading=torch_util.calc_heading_quat_inv(q);q=torch_util.quat_mul(heading,q)
p,r=e._kin_char_model.forward_kinematics(poses[:,:3],q,e._kin_char_model.dof_to_rot(poses[:,6:]))
poses[:,2]+=.002-e._lowest_geometry(p,r)
ids=torch.arange(512,device='cuda:0')
e._engine.set_root_pos(ids,c,poses[:,:3]);e._engine.set_root_rot(ids,c,q);e._engine.set_dof_pos(ids,c,poses[:,6:]);e._reset_char_rigid_body_state(ids)
heights=[];hits=torch.zeros(512,device='cuda:0')
for i in range(60):
    obs,reward,done,_=e.step(poses[:,6:]);assert torch.isfinite(obs).all()
    heights.append(e._engine.get_body_pos(c)[:,2,2].clone())
    forces=e._engine.get_ground_contact_forces(c).clone();forces[:,e._contact_body_ids]=0
    hits+=(forces.abs().amax(dim=(1,2))>.1)
height=torch.stack(heights)
reports=[dict(name=name,head_end_m=float(height[-1,i]),head_min_m=float(height[:,i].min()),nonfoot_contact_ticks=int(hits[i])) for i,name in enumerate(names)]
valid=[i for i in range(count-1) if reports[i]['head_min_m']>1.1 and reports[i]['nonfoot_contact_ticks']==0]
print('CANDIDATES',json.dumps(sorted(reports,key=lambda x:-x['head_min_m'])[:8]),flush=True)
(root/'standing-candidates.json').write_text(json.dumps(reports,indent=2))
assert valid,'No naturally standing candidate remains standing for two seconds'
best=max(valid,key=lambda i:reports[i]['head_min_m'])
pose=poses[best].cpu().numpy();pose[3:6]=torch_util.quat_to_exp_map(q[best]).cpu().numpy()
report=dict(source=names[best],pose=pose.tolist(),selection_test=reports[best],reference_frames=61,fps=30,
    changes='Root XY/heading normalized, floor clearance 2mm; source naming identifies any combined upper/lower pose')
(root/'pipeline/amp_standing_target.json').write_text(json.dumps(report,indent=2))
(root/'pipeline/amp_standing_target.pkl').write_bytes(pickle.dumps(dict(loop_mode=1,fps=30,frames=np.tile(pose,(61,1)).tolist())))
print('SELECTED',json.dumps(report),flush=True)
