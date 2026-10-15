"""CPU finite-perturbation audit using the real observation/reward/policy code."""
import os, sys, json
from pathlib import Path
from types import SimpleNamespace
ROOT=Path('/workspace/mimickit_trial')
sys.path.insert(0,str(ROOT/'MimicKit/mimickit'))
os.chdir(ROOT/'MimicKit')
import torch, yaml, numpy as np
from gymnasium.spaces import Box
from anim.mjcf_char_model import MJCFCharModel
from envs.char_env import compute_char_obs
from neutral_pose import body_position_mse
from learning.ppo_model import PPOModel
from util import torch_util as u
torch.set_num_threads(1)
source=ROOT/'runs'/json.loads((ROOT/'sweep.json').read_text())['trials'][1]['name']
cfg=yaml.safe_load((source/'env_config.yaml').read_text())
acfg=yaml.safe_load((source/'agent_config.yaml').read_text())
m=MJCFCharModel('cpu');m.load(cfg['char_file'])
neutral=torch.tensor(cfg['neutral_pose'],dtype=torch.float32)[None,:]
j=m.dof_to_rot(neutral[:,6:])
target,_=m.forward_kinematics(neutral[:,:3],u.exp_map_to_quat(neutral[:,3:6]),j)
angles=torch.tensor([89.999,90.001,-89.999,-90.001])
aa=torch.zeros(4,3);aa[:,1]=torch.deg2rad(angles);q=u.exp_map_to_quat(aa)
root=torch.tensor([[0,0,.115]]).expand(4,-1)
pos,_=m.forward_kinematics(root,q,j.expand(4,-1,-1))
key=[m.get_body_names().index(n) for n in cfg['key_bodies']]
obs=compute_char_obs(root,q,torch.zeros(4,3),torch.zeros(4,3),j.expand(4,-1,-1),
    torch.zeros(4,28),pos[:,key],False,True)
obs=torch.cat([obs,torch.ones(4,1)],dim=-1)
state=torch.load(ROOT/'causal_regression/cp150_stock_seed9017/model_0000.pt',map_location='cpu',weights_only=True)
env=SimpleNamespace(get_obs_space=lambda:Box(-np.inf,np.inf,shape=(141,)),
    get_action_space=lambda:Box(-1.,1.,shape=(28,)))
model=PPOModel(acfg['model'],env)
model.load_state_dict({k[len('_model.'):]:v for k,v in state.items() if k.startswith('_model.')})
with torch.no_grad():
    norm=((obs-state['_obs_norm._mean'])/state['_obs_norm._std']).clamp(-10,10)
    means=model.eval_actor(norm).mode
    requested=means*state['_a_norm._std']+state['_a_norm._mean']
    applied=requested.clamp(state['_a_norm._mean']-state['_a_norm._std'],state['_a_norm._mean']+state['_a_norm._std'])
report=dict(pitches=angles.tolist(),heading_degrees=torch.rad2deg(u.calc_heading(q)).tolist(),
    mse=body_position_mse(pos,root,q,target).tolist(),
    body_position_max_delta_m=[float((pos[i]-pos[i+1]).norm(dim=-1).max()) for i in (0,2)],
    observation_max_delta=[float((obs[i]-obs[i+1]).abs().max()) for i in (0,2)],
    applied_motor_target_max_delta_degrees=[float(torch.rad2deg((applied[i]-applied[i+1]).abs()).max()) for i in (0,2)],
    applied_motor_target_rms_delta_degrees=[float(torch.rad2deg((applied[i]-applied[i+1]).square().mean().sqrt())) for i in (0,2)])
(ROOT/'causal_regression/heading_policy_audit.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
