"""Bounded, read-only policy rollout; report physical motion and credit signal."""
import argparse
import io
import json
import os
from pathlib import Path
import zipfile
import train
import torch
import numpy as np
import yaml
from neutral_pose import NeutralPoseEnv
from learning.ppo_agent import PPOAgent
from learning.base_agent import AgentMode
from learning.rl_util import compute_td_lambda_return

p = argparse.ArgumentParser()
p.add_argument('checkpoint', type=Path)
p.add_argument('output', type=Path)
a = p.parse_args()
torch.set_num_threads(1)
torch.set_num_interop_threads(1)
os.chdir(train.REPO)
with zipfile.ZipFile(a.checkpoint) as z:
    cfg = yaml.safe_load(z.read('env_config.yaml'))
    engine = yaml.safe_load(z.read('engine_config.yaml'))
    acfg = yaml.safe_load(z.read('agent_config.yaml'))
    model = torch.load(io.BytesIO(z.read('model.pt')), map_location='cuda:0', weights_only=True)
train.upstream.mp_util.init(0, 1, 'cuda:0', 6742)
torch.manual_seed(461)
torch.cuda.manual_seed_all(461)
env = NeutralPoseEnv(cfg, engine, 128, 'cuda:0', False)
agent = PPOAgent(acfg, env, 'cuda:0')
agent.load_state_dict(model)
agent.eval()
agent.set_mode(AgentMode.TRAIN)
obs, info = env.reset()
data = {k: [] for k in ['reward', 'value', 'next_value', 'done', 'mse', 'clipped', 'mean', 'head', 'pelvis']}
names = env._engine.get_obj_body_names(env._get_char_id())
with torch.no_grad():
    for step in range(45):
        normalized = agent._obs_norm.normalize(obs)
        data['value'].append(agent._model.eval_critic(normalized).flatten())
        data['mean'].append(agent._model.eval_actor(normalized).mean.clone())
        action, _ = agent._decide_action(obs, info)
        data['clipped'].append((action != action.clamp(env._action_bound_low, env._action_bound_high)).float().mean(-1))
        obs, reward, done, info = env.step(action)
        assert torch.isfinite(obs).all() and torch.isfinite(reward).all()
        data['reward'].append(reward.clone())
        data['done'].append(done.clone())
        data['next_value'].append(agent._model.eval_critic(agent._obs_norm.normalize(obs)).flatten())
        data['mse'].append(env._pose_mse().clone())
        pos = env._engine.get_body_pos(env._get_char_id())
        data['head'].append(pos[:,names.index('head'),2].clone())
        data['pelvis'].append(pos[:,names.index('pelvis'),2].clone())
data = {k: torch.stack(v) for k,v in data.items()}
data['next_value'][-1] = 0
target = compute_td_lambda_return(data['reward'], data['next_value'], data['done'], acfg['discount'], acfg['td_lambda'])
adv = target - data['value']
returns = torch.zeros_like(data['reward'])
running = torch.zeros(128, device='cuda:0')
for t in reversed(range(45)):
    running = data['reward'][t] + acfg['discount']*running
    returns[t] = running
def scalar(x): return float(x)
def spread(x):
    # Equal worlds per timestep: total variance = time-mean variance + within-time variance.
    return dict(total_std=scalar(x.std(unbiased=False)),
                time_mean_std=scalar(x.mean(1).std(unbiased=False)),
                within_time_std=scalar((x-x.mean(1,keepdim=True)).square().mean().sqrt()),
                time_mean_variance_fraction=scalar(x.mean(1).var(unbiased=False)/x.var(unbiased=False)))
per = data['mse'].mean(0)
report = dict(checkpoint=str(a.checkpoint), worlds=128, seed=461, sigma=acfg['model']['action_std'],
    scope='Fresh 45-step noisy episodes from copied policy; no optimization, not exact live PPO batch',
    mean_mse=scalar(per.mean()), best_mse=scalar(per.min()), worst_mse=scalar(per.max()),
    episode_mse_std=scalar(per.std()), final_mse=scalar(data['mse'][-1].mean()),
    head_peak_mean=scalar(data['head'].amax(0).mean()),head_peak_max=scalar(data['head'].max()),
    pelvis_peak_mean=scalar(data['pelvis'].amax(0).mean()),pelvis_peak_max=scalar(data['pelvis'].max()),
    clamped_action_fraction=scalar(data['clipped'].mean()),
    advantage=spread(adv), critic_error=spread(data['value']-returns),
    critic_mc_rmse=scalar((data['value']-returns).square().mean().sqrt()),
    critic_explained_variance=scalar(1-(data['value']-returns).var()/returns.var()),
    critic_value_by_frame=data['value'].mean(1)[[0,14,29,44]].cpu().tolist(),
    discounted_actual_return_by_frame=returns.mean(1)[[0,14,29,44]].cpu().tolist(),
    advantage_mean_by_frame=adv.mean(1)[[0,14,29,44]].cpu().tolist())
a.output.write_text(json.dumps(report,indent=2))
print('CONTINUOUS_DIAGNOSIS',json.dumps(report),flush=True)
