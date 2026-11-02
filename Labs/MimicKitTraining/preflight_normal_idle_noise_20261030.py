"""Disposable full-size rollout and PPO update; never touches production trainer."""
import sys,os,json,time
from pathlib import Path
root=Path('/workspace/mimickit_trial/normal-idle-preflight')
sys.path[:0]=[str(root/'pipeline'),str(root/'MimicKit/mimickit')];os.chdir(root)
import torch,warp as wp,yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from omni_policy import OmniPPOAgent
from cohort_noise import normal_idle_mask,apply_noise_offset
from resume import restore

torch.set_num_threads(1);torch.set_num_interop_threads(1)
wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6998)
cfg,ec,ac=[yaml.safe_load((root/'prepared'/(n+'_config.yaml')).read_text()) for n in ['env','engine','agent']]
e=PerturbedOmniEnv(cfg,ec,2048,'cuda:0',False);a=OmniPPOAgent(ac,e,'cuda:0')
restore(a,Path('/workspace/mimickit_trial/upperbody-paired-20261030/after.zip'))
a._init_train();a._sample_count=13000000000;a.eval();a.set_mode(AgentMode.TRAIN)
a._curr_obs,a._curr_info=a._reset_envs();mask=normal_idle_mask(e)
assert int(mask.sum())==41 and int(e._final.minus.sum())==62
idle=e._gaits[e._fixed_motion_ids]==-1
assert int((idle&~mask&~e._final.minus).sum())==100
assert int((~idle).sum())==1845
with torch.no_grad():
    a._init_iter();a._rollout_train(a._steps_per_iter)
a._build_train_data();batch=a._exp_buffer.sample(4096)
assert int((batch['action_logstd_offset']<0).sum())>0
shared=a._compute_actor_loss(batch);reference=a._compute_actor_loss_reference(batch)
for name in ['actor_loss','imp_ratio','clip_frac']:
    torch.testing.assert_close(shared[name],reference[name],atol=2e-5,rtol=1e-5)
assert abs(float(shared['imp_ratio'])-1)<1e-5
with torch.no_grad():
    dist=apply_noise_offset(a._model.eval_actor(a._obs_norm.normalize(batch['obs'])),batch['action_logstd_offset'])
    error=(dist.log_prob(a._a_norm.normalize(batch['action']))-batch['a_logp']).abs().max()
    assert float(error)<1e-3
    norm=a._obs_norm.normalize(a._curr_obs)
    base=a._model.eval_actor(norm)
    d=apply_noise_offset(base,a._action_noise_offset)
    torch.testing.assert_close(d.stddev[mask],torch.full_like(d.stddev[mask],.025))
    torch.testing.assert_close(d.stddev[~mask],torch.full_like(d.stddev[~mask],.075))
    a.set_mode(AgentMode.TEST);act,_=a._decide_action(a._curr_obs,a._curr_info)
    torch.testing.assert_close(act,a._a_norm.unnormalize(base.mode),rtol=0,atol=0)
    a.set_mode(AgentMode.TRAIN)
result=a._update_actor(4096,1)
assert all(torch.isfinite(v).all() for v in result.values() if torch.is_tensor(v))
assert int(result['actor_steps_accepted'])==1
report=dict(passed=True,normal_idle=41,pushed_idle=62,other_idle=100,locomotion=1845,
    rollout_likelihood_max_error=float(error),reference_shared_parity=True,
    isolated_actor_steps=int(result['actor_steps_accepted']),policy_kl=float(result['policy_kl']),
    normal_idle_std=.025,other_std=.075,deterministic_actions_unchanged=True)
(root/'preflight.json').write_text(json.dumps(report,indent=2));print('PREFLIGHT',json.dumps(report),flush=True)
