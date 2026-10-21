"""Bounded isolated profiler; never modifies the live trainer or its outputs."""
import sys,json,time,os,types
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial');OUT=ROOT/'perf-batched-20261020';OUT.mkdir(exist_ok=True)
sys.path[:0]=[str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')]
import torch,warp as wp,yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from resume import restore
from omni_policy import OmniPPOAgent
from profile_training import run_profiled_update
torch.set_num_threads(1);torch.set_num_interop_threads(1);wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6796)
cfg,ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
env=PerturbedOmniEnv(cfg,ec,512,'cuda:0',False);agent=OmniPPOAgent(ac,env,'cuda:0')
r=ROOT/'runs/20261020_065209_uefn_replay_getup_selection_linear_512';b=json.loads((r/'backup_status.json').read_text());restore(agent,r/Path(b['key']).name);agent._init_train();agent.set_mode(AgentMode.TRAIN);agent._curr_obs,agent._curr_info=agent._reset_envs()

import importlib.util
spec=importlib.util.spec_from_file_location('batched_joint_conversion','/tmp/batched_joint_conversion.py');batch=importlib.util.module_from_spec(spec);spec.loader.exec_module(batch)
model=env._kin_char_model;old_forward=model.dof_to_rot;old_inverse=model.rot_to_dof
batch.install(model);new_forward=model.dof_to_rot;new_inverse=model.rot_to_dof
errors=[]
for size in [0,1,7,512]:
 dofs=torch.randn(size,model.get_dof_size(),device='cuda')*3
 if size:dofs[0]=0
 expected=old_forward(dofs);actual=new_forward(dofs);torch.testing.assert_close(actual,expected,atol=1e-6,rtol=1e-6)
 a=old_inverse(expected);b=new_inverse(expected);torch.testing.assert_close(a,b,atol=1e-6,rtol=1e-6)
 errors.append(dict(rows=size,forward_max=float((actual-expected).abs().max()) if size else 0,inverse_max=float((a-b).abs().max()) if size else 0))
dofs=env._engine.get_dof_pos(0).clone();rot=old_forward(dofs);bench=[]
for fast in [False,True,True,False]:
 f,g=(new_forward,new_inverse) if fast else (old_forward,old_inverse)
 for _ in range(5):f(dofs);g(rot)
 torch.cuda.synchronize();t=time.perf_counter()
 for _ in range(50):f(dofs);g(rot)
 torch.cuda.synchronize();bench.append(dict(fast=fast,seconds=time.perf_counter()-t,calls_each=50))
# Validate optimized prior against original entire-row rewards at the same state.
model.dof_to_rot=old_forward;model.rot_to_dof=old_inverse
env._update_reward();old_reward=env._reward_buf.clone();old_loss=env.loss_terms.clone()
spec=importlib.util.spec_from_file_location('optimized_perturbed','/tmp/optimized_perturbed_omni.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
keep=~env._perturbed_getup[env._perturbed_ids];env._prior_ids=env._perturbed_ids[keep];env._prior_index.fill_(-1);env._prior_index[env._prior_ids]=torch.arange(len(env._prior_ids),device='cuda')
for name in ['positions','rotations','valid']:setattr(env._prior,name,getattr(env._prior,name)[keep].clone())
env._prior_raw[env._perturbed_getup]=0;env.__class__=mod.PerturbedOmniEnv
# Same pose appended twice for an exactly matched motion window.
for _ in range(3):env._prior.append(env._engine.get_body_pos(0)[env._prior_ids],mod.q.quat_to_matrix(env._engine.get_body_rot(0)[env._prior_ids]))
# Get-up rewards independent of prior history; other-row prior equivalence tested separately.
env._update_reward();torch.testing.assert_close(env._reward_buf[env._perturbed_getup],old_reward[env._perturbed_getup]);torch.testing.assert_close(env.loss_terms[env._perturbed_getup],old_loss[env._perturbed_getup])
agent._curr_obs,agent._curr_info=agent._reset_envs();full=[]
for fast in [False,True,True,False]:
 model.dof_to_rot=new_forward if fast else old_forward;model.rot_to_dof=new_inverse if fast else old_inverse
 agent._train_iter();torch.cuda.synchronize();t=time.perf_counter();agent._train_iter();torch.cuda.synchronize();full.append(dict(fast=fast,seconds=time.perf_counter()-t))
report=dict(conversion_errors=errors,conversion_benchmark=bench,ppo_comparison=full,ae_rows=len(env._prior_ids),getup_reward_equal=True,concurrent_with_live_training=True)
(OUT/'result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
