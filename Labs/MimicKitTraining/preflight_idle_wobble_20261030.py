"""Disposable actual environment rollout, graph state and reward reconstruction."""
import sys,os,json,math,time
from pathlib import Path
root=Path('/workspace/mimickit_trial/idle-wobble-preflight')
sys.path[:0]=[str(root/'pipeline'),str(root/'MimicKit/mimickit')];os.chdir(root)
import torch,numpy as np,warp as wp,yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from omni_policy import OmniPPOAgent
from resume import restore
from lossless_runtime import install
torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.backends.cuda.matmul.allow_tf32=False
torch.set_float32_matmul_precision('highest');wp.init();mp_util.init(0,1,'cuda:0',6999)
cfg,ec,ac=[yaml.safe_load((root/'prepared'/(n+'_config.yaml')).read_text()) for n in ['env','engine','agent']]
cfg['idle_row_fraction']=.5
e=PerturbedOmniEnv(cfg,ec,128,'cuda:0',False);a=OmniPPOAgent(ac,e,'cuda:0')
restore(a,Path('/workspace/mimickit_trial/resume.zip'));a._init_train();a._sample_count=14000000000;a.eval();a.set_mode(AgentMode.TRAIN)
install(a,e);obs,info=a._reset_envs()
idx=e.loss_term_names.index('idle_wobble')
normal=(e._gaits[e._fixed_motion_ids]==-1)&~e._perturbed_rows&~e._final.minus
active=(e._gaits[e._fixed_motion_ids]==-1)&(e._perturbed_rows|e._final.minus)
errors=[];costs=[];reset_checks=0
with torch.no_grad():
 for t in range(150):
  action,_=a._decide_action(obs,info);obs,reward,done,info=e.step(action)
  total=e.loss_terms.sum(-1)
  shaped=e._com2_reward_values[:,0]/(1+total)
  valid=done==0
  errors.append(float((reward[valid]-shaped[valid]).abs().max()))
  assert (e.loss_terms[~active,idx]==0).all()
  assert torch.isfinite(e.loss_terms).all()
  costs.append(e.loss_terms[:,idx].clone())
  obs,info=a._reset_done_envs(done)
  ids=torch.where(done!=0)[0]
  if len(ids):
   assert (e._idle_wobble.mass[ids]==0).all();reset_checks+=len(ids)
assert max(errors)<2e-6
assert float(torch.stack(costs)[:,active].max())>0
# Compare a captured reward tick with eager from identical complete reward state.
from lossless_runtime import REWARD_BUFFERS
buffers=[getattr(e,n) for n in REWARD_BUFFERS]
buffers.extend(getattr(e._prior,n) for n in ['positions','rotations','valid'])
for obj in [e._head_reversal,e._foot_regularizers,e._leg_reversal,e._idle_wobble]:
 buffers.extend(getattr(obj,n) for n in obj.buffer_names)
saved=[v.clone() for v in buffers]
e._update_reward();actual=e.loss_terms.clone()
for v,s in zip(buffers,saved):v.copy_(s)
e._update_reward.original();torch.testing.assert_close(actual,e.loss_terms,atol=1e-5,rtol=1e-5)
ids=torch.tensor([0,1],device='cuda:0');untouched=e._idle_wobble.vector[2:].clone()
e.reset(ids)
assert (e._idle_wobble.mass[ids]==0).all() and (e._idle_wobble.raw[ids]==0).all()
torch.testing.assert_close(untouched,e._idle_wobble.vector[2:],rtol=0,atol=0)
report=dict(passed=True,frames=150,worlds=128,reward_error=max(errors),graph_eager_parity=True,
 inactive_rows_zero=True,explicit_reset_isolation=True,episode_reset_rows=reset_checks,active_rows=int(active.sum()),normal_idle_rows=int(normal.sum()),
 mean_added_cost=float(torch.stack(costs)[:,active].mean()))
(root/'preflight.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
