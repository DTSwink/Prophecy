"""Bounded disposable checkpoint trace: commands -> physics -> observations."""
import argparse
from collections import deque
import io
import json
import os
from pathlib import Path
import time
import zipfile

import train
import torch
import numpy as np
import yaml
from neutral_pose import NeutralPoseEnv
from learning.ppo_agent import PPOAgent
from resume import restore

p = argparse.ArgumentParser()
p.add_argument('mode', choices=['train', 'frozen', 'weights_only', 'normalization_only'])
p.add_argument('--updates', type=int, default=120)
p.add_argument('--checkpoint', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
a.output.mkdir(exist_ok=False)
torch.set_num_threads(1)
torch.set_num_interop_threads(1)
os.chdir(train.REPO)
with zipfile.ZipFile(a.checkpoint) as z:
    cfg = yaml.safe_load(z.read('env_config.yaml'))
    engine_cfg = yaml.safe_load(z.read('engine_config.yaml'))
    agent_cfg = yaml.safe_load(z.read('agent_config.yaml'))
train.upstream.mp_util.init(0, 1, 'cuda:0', 6742)
train.upstream.set_rand_seed(train.upstream.load_args(['train', '--rand_seed', '20261014']))
env = NeutralPoseEnv(cfg, engine_cfg, 256, 'cuda:0', False)
agent = PPOAgent(agent_cfg, env, 'cuda:0')
restored = restore(agent, a.checkpoint)
offset = restored['iteration_offset']
agent._curr_obs, agent._curr_info = agent._reset_envs()
agent._init_train()
eng = env._engine
char = env._get_char_id()
previous = deque(maxlen=3)
original_step = env.step
iteration_stats = {}
started = time.time()

def emit(name, data):
    (a.output/(name+'.json')).write_text(json.dumps(data, indent=2))
    print(name, json.dumps(data), flush=True)

def state():
    return {key: getattr(eng, 'get_'+key)(char).detach().clone() for key in
            ['body_pos', 'body_rot', 'body_vel', 'body_ang_vel', 'dof_pos', 'dof_vel']}

def finite_max(t):
    return float(torch.nan_to_num(t, nan=0., posinf=0., neginf=0.).abs().max())

def step(action):
    before = state()
    before['action'] = action.detach().clone()
    before['episode_step'] = env._timestep_buf.clone()
    before['applied'] = action.clamp(env._action_bound_low, env._action_bound_high).detach().clone()
    result = original_step(action)
    after = state()
    after['obs'] = result[0].detach().clone()
    after['reward'] = result[1].detach().clone()
    masks = {key: ~torch.isfinite(t).reshape(256, -1).all(-1) for key, t in after.items()}
    bad = torch.stack(list(masks.values())).any(0)
    iteration_stats['requested_abs_max'] = max(iteration_stats.get('requested_abs_max', 0), finite_max(action))
    iteration_stats['body_speed_component_max'] = max(iteration_stats.get('body_speed_component_max', 0), finite_max(after['body_vel']))
    if bool(bad.any()):
        ids = bad.nonzero().flatten()
        arrays = {}
        for label, snapshot in [('before', before), ('after', after)]+[(f'previous{i}', v) for i, v in enumerate(previous)]:
            for key, value in snapshot.items(): arrays[label+'_'+key] = value[ids].cpu().numpy()
        np.savez_compressed(a.output/'first_invalid.npz', worlds=ids.cpu().numpy(), **arrays)
        torch.save(agent.state_dict(), a.output/'policy_at_failure.pt')
        emit('first_invalid', dict(iteration=offset+agent._iter, mode=a.mode, worlds=ids.cpu().tolist(),
             episode_steps=before['episode_step'][ids].cpu().tolist(),
             input_action_finite=bool(torch.isfinite(action).all()),
             applied_action_finite=bool(torch.isfinite(before['applied']).all()),
             requested_abs_max=finite_max(action[ids]), applied_abs_max=finite_max(before['applied'][ids]),
             after={k: dict(finite=bool(torch.isfinite(v[ids]).all()), finite_abs_max=finite_max(v[ids])) for k,v in after.items()},
             first_invalid_indices={k: (~torch.isfinite(v[ids])).nonzero().cpu().tolist()[:12] for k,v in after.items()},
             names=list(eng.get_obj_body_names(char))))
        raise FloatingPointError('Captured first invalid physical/observation state')
    previous.append(before)
    return result

env.step = step
original_actor = agent._update_actor
original_norm = agent._update_normalizers
def actor(*args, **kwargs):
    with torch.no_grad():
        obs = agent._obs_norm.normalize(agent._exp_buffer.get_data_flat('obs')[:512])
        before = agent._model.eval_actor(obs).mean.clone()
    result = original_actor(*args, **kwargs)
    with torch.no_grad():
        after = agent._model.eval_actor(obs).mean
        iteration_stats.update(actor_mean_shift_rms=float((after-before).square().mean().sqrt()),
                               actor_mean_abs_max=finite_max(after), clip_fraction=float(result['clip_frac']))
    return result
def norm():
    with torch.no_grad():
        raw = agent._exp_buffer.get_data_flat('obs')[:512]
        before = agent._model.eval_actor(agent._obs_norm.normalize(raw)).mean.clone()
        original_norm()
        after = agent._model.eval_actor(agent._obs_norm.normalize(raw)).mean
        iteration_stats['normalizer_mean_shift_rms'] = float((after-before).square().mean().sqrt())
agent._update_actor = actor
agent._update_normalizers = norm

def grad_hook(opt, args, kwargs):
    gradients = [p.grad for p in agent._actor_optimizer._param_list if p.grad is not None]
    magnitude = float(sum(g.detach().square().sum() for g in gradients).sqrt())
    iteration_stats['actor_gradient_norm_max'] = max(iteration_stats.get('actor_gradient_norm_max', 0), magnitude)
agent._actor_optimizer._optimizer.register_step_pre_hook(grad_hook)
if a.mode in ('frozen', 'normalization_only'):
    agent._update_model = lambda: {}
if a.mode in ('frozen', 'weights_only'):
    agent._update_normalizers = lambda: None
if a.mode == 'frozen':
    frozen = {k:v.detach().clone() for k,v in agent.state_dict().items()}

try:
    for i in range(a.updates):
        if time.time()-started > 150: break
        iteration_stats = dict(iteration=offset+i)
        result = agent._train_iter()
        iteration_stats['mse'] = -float(result['mean_return'])
        with (a.output/'updates.jsonl').open('a') as f: f.write(json.dumps(iteration_stats)+'\n')
        agent._iter += 1
        if i % 10 == 0: emit('status', dict(**iteration_stats, seconds=time.time()-started))
    if a.mode == 'frozen':
        assert all(torch.equal(v, agent.state_dict()[k]) for k,v in frozen.items())
    emit('complete', dict(updates=agent._iter, seconds=time.time()-started, mode=a.mode, finite=True))
except FloatingPointError as exc:
    emit('stopped', dict(reason=str(exc), completed_updates=agent._iter, seconds=time.time()-started))
