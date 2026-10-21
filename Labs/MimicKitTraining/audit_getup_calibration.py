"""Bounded disposable learner: current rewards/advantages and matched actor-LR probes.

Uses deployed modules and a verified saved checkpoint. Never writes live state.
"""
import sys,json,time,copy,hashlib
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial')
sys.path[:0]=[str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')]
import torch,numpy as np,warp as wp,yaml
from util import mp_util
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from omni_policy import OmniPPOAgent
from resume import restore
from kl_guard import Snapshot

started=time.time();run=ROOT/'runs'/sys.argv[1]
out=ROOT/'getup-calibration-audit';out.mkdir(exist_ok=True)
torch.set_num_threads(1);torch.set_num_interop_threads(1)
wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6794)
cfg,ec,ac=[yaml.safe_load((run/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
backup=json.loads((run/'backup_status.json').read_text())
checkpoint=run/Path(backup['key']).name
digest=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
if backup.get('sha256') and digest!=backup['sha256']:raise ValueError('Checkpoint hash mismatch')
env=PerturbedOmniEnv(cfg,ec,512,'cuda:0',False)
agent=OmniPPOAgent(ac,env,'cuda:0');restored=restore(agent,checkpoint)
agent._init_train();agent.set_mode(AgentMode.TRAIN)
torch.manual_seed(20261020);torch.cuda.manual_seed_all(20261020)
agent._curr_obs,agent._curr_info=agent._reset_envs()
getup=env._perturbed_getup
loco=env._perturbed_rows & (env._gaits[env._motion_ids]!=-1)
masks={'getup':getup,'perturbed_loco':loco,'other':~(getup|loco)}
result=dict(checkpoint=checkpoint.name,sha256=digest,worlds=512,
            live_trainer_modified=False,cohort_rows={k:int(v.sum()) for k,v in masks.items()},
            buffers=[],lr_trials=[])
def save():
    result['elapsed_seconds']=time.time()-started
    (out/'result.json').write_text(json.dumps(result,indent=2))
def stats(x):
    x=x.detach().float().flatten()
    return dict(n=x.numel(),mean=float(x.mean()),std=float(x.std()),min=float(x.min()),max=float(x.max())) if x.numel() else {}
records=[];orig=agent._step_env
def step(action):
    alpha=env._pose_blend.clone();side=env._recovery_motion.clone()
    value=orig(action)
    records.append(torch.stack((alpha,side.float(),env._reset_reason.float().clone(),
        env._time_buf.clone()*30,
        env._engine.get_body_pos(0)[:,env._head_id,2]/env._idle_head_height[env._motion_ids]),-1).detach())
    return value
agent._step_env=step
for index in range(6):
    with torch.no_grad():agent._rollout_train(32)
    info=agent._build_train_data();buf=agent._exp_buffer
    obs=buf.get_data('obs');reward=buf.get_data('reward');done=buf.get_data('done')
    with torch.no_grad():value=agent._model.eval_critic(agent._obs_norm.normalize(obs)).squeeze(-1)
    target=buf.get_data('tar_val');adv=buf.get_data('adv')
    entry=dict(index=index,normalization={k:float(v) for k,v in info.items()},cohorts={})
    for name,mask in masks.items():
        entry['cohorts'][name]=dict(reward=stats(reward[:,mask]),value=stats(value[:,mask]),
            target=stats(target[:,mask]),raw_adv=stats((target-value)[:,mask]),
            normalized_adv=stats(adv[:,mask]),critic_mse=float((target-value)[:,mask].square().mean()),
            clipped_fraction=float((adv[:,mask].abs()>=3.999).float().mean()))
    # Same states and critic: quantify cross-cohort normalization from loco costs.
    original_reward=reward.clone();original_adv=adv.clone();original_target=target.clone()
    reward.add_(((done==1)&loco[None]).float()*cfg['perturbed_motion']['loco_failure_penalty'])
    without=agent._build_train_data()
    entry['without_loco_penalty_same_states']={k:float(v) for k,v in without.items()}
    reward.copy_(original_reward);adv.copy_(original_adv);target.copy_(original_target)
    result['buffers'].append(entry);save()
data=torch.stack(records)[:,getup].cpu()
result['episode_difficulty']=[]
for side in [0,1]:
    for low,high in [(0,.25),(.25,.5),(.5,.75),(.75,1.00001)]:
        sel=(data[:,:,1]==side)&(data[:,:,0]>=low)&(data[:,:,0]<high)&(data[:,:,2]>0)
        ends=data[sel];reasons=ends[:,2]
        result['episode_difficulty'].append(dict(side=side,alpha=[low,high],ends=len(ends),
            failures=int((reasons==1).sum()),success=int((reasons==2).sum()),timeouts=int((reasons==3).sum()),
            fail_head_ratio=stats(ends[reasons==1,4]),success_ticks=stats(ends[reasons==2,3])))
# Identical checkpoint, batch, moments, minibatch order and RNG for each LR trial.
buf=agent._exp_buffer;initial=Snapshot(agent._actor_optimizer)
old_lr=agent._actor_optimizer._optimizer.param_groups[0]['lr']
sample_order=buf._sample_buf.clone();sample_head=buf._sample_buf_head
cuda_rng=torch.cuda.get_rng_state();cpu_rng=torch.get_rng_state()
flat={k:v for k,v in buf._flat_buffers.items()}
def surrogate():
    with torch.no_grad():
        dist=agent._model.eval_actor(agent._obs_norm.normalize(flat['obs']))
        ratio=(dist.log_prob(agent._a_norm.normalize(flat['action']))-flat['a_logp']).exp()
        objective=torch.minimum(flat['adv']*ratio,flat['adv']*ratio.clamp(.8,1.2))
        return {k:float(objective[m.expand(32,-1).flatten()].mean()) for k,m in masks.items()}
result['surrogate_before']=surrogate()
for multiplier in [1,2,4,8]:
    initial.restore();buf._sample_buf.copy_(sample_order);buf._sample_buf_head=sample_head
    torch.cuda.set_rng_state(cuda_rng);torch.set_rng_state(cpu_rng)
    for group in agent._actor_optimizer._optimizer.param_groups:group['lr']=old_lr*multiplier
    agent.train()
    info=agent._update_actor(2048,40)
    result['lr_trials'].append(dict(multiplier=multiplier,requested_lr=old_lr*multiplier,
        metrics={k:float(v) for k,v in info.items()},surrogate_after=surrogate()))
    save()
initial.restore();result['complete']=True;save()
print('CALIBRATION_AUDIT_COMPLETE',flush=True)
