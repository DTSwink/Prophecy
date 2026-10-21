"""Bounded isolated frozen-checkpoint diagnosis. Never writes trainer state."""
import json, sys, time, hashlib
from pathlib import Path
ROOT=Path('/workspace/mimickit_trial')
sys.path[:0]=[str(ROOT/'pipeline'),str(ROOT/'MimicKit/mimickit')]
import torch, numpy as np, warp as wp, yaml
from util import mp_util, torch_util as q
from learning.base_agent import AgentMode
from perturbed_omni import PerturbedOmniEnv
from omni_policy import OmniPPOAgent
from resume import restore

OUT=ROOT/'head-learning-audit';OUT.mkdir(exist_ok=True)
start=time.time()
def save(value):
    (OUT/'result.json').write_text(json.dumps(value,indent=2));print(json.dumps(value),flush=True)
torch.set_num_threads(1);torch.set_num_interop_threads(1)
wp.init();wp.set_device('cuda:0');mp_util.init(0,1,'cuda:0',6797)
cfg,ec,ac=[yaml.safe_load((ROOT/'prepared'/(n+'_config.yaml')).read_text()) for n in ('env','engine','agent')]
env=PerturbedOmniEnv(cfg,ec,128,'cuda:0',False)
agent=OmniPPOAgent(ac,env,'cuda:0')
restored=restore(agent,OUT/'checkpoint.zip');agent._init_train();agent.eval()
result=dict(checkpoint=restored,worlds=128,live_trainer_modified=False,variants=[])
getup=env._perturbed_getup
def stats(x):
    x=x.detach().float().flatten();return dict(mean=float(x.mean()),min=float(x.min()),max=float(x.max())) if x.numel() else {}
def correlation(a,b):
    a=a.float().flatten();b=b.float().flatten();a=a-a.mean();b=b-b.mean()
    return float((a*b).sum()/(a.norm()*b.norm()).clamp_min(1e-12))


agent.set_mode(AgentMode.TRAIN);torch.manual_seed(7411);torch.cuda.manual_seed_all(7411)
agent._curr_obs,agent._curr_info=agent._reset_envs()
def inspect_obs(obs):
    raw=(obs-agent._obs_norm._mean)/agent._obs_norm._std
    clipped=raw.abs()>=agent._obs_norm._clip
    return dict(clip=float(agent._obs_norm._clip),getup_fraction_clipped=float(clipped[getup].float().mean()),
        other_fraction_clipped=float(clipped[~getup].float().mean()),
        getup_max_zscore=float(raw[getup].abs().max()),
        top_getup_channels=torch.topk(clipped[getup].float().mean(0),12).indices.cpu().tolist(),
        getup_command=obs[getup][0,-8:].cpu().tolist())
initial=inspect_obs(agent._curr_obs)
with torch.no_grad():
    for _ in range(3):agent._rollout_train(32)
    late=inspect_obs(agent._curr_obs)
    physical=env._engine.get_body_pos(0).clone()
    original_time=env._time_buf.clone();env._time_buf[getup]=1.
    early_obs=env._compute_obs();early_v=agent._model.eval_critic(agent._obs_norm.normalize(early_obs)).squeeze(-1)
    env._time_buf[getup]=3.
    late_obs=env._compute_obs();late_v=agent._model.eval_critic(agent._obs_norm.normalize(late_obs)).squeeze(-1)
    env._time_buf.copy_(original_time)
    alias=dict(max_raw_observation_difference=float((early_obs[getup]-late_obs[getup]).abs().max()),
        max_critic_difference=float((early_v[getup]-late_v[getup]).abs().max()),
        height_reward_at_tick30=0.,height_reward_at_tick90=stats((physical[getup,env._head_id,2]/env._idle_head_height[env._motion_ids[getup]]).clamp(0,1)))
result=dict(checkpoint=restored,initial=initial,late=late,hidden_clock=alias,seconds=time.time()-start)
(OUT/'observation-audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
