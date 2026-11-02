"""Frozen-policy audit: first episodes versus repeated training-style resets."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import torch
import supermimic_race as base

GROUPS = ['normal_loco', 'normal_idle', 'perturbed_loco', 'perturbed_idle']


def continuous(env, agent, seed, exploration, ticks=480):
    from learning.base_agent import AgentMode
    from envs.base_env import DoneFlags
    import mujoco_warp as mjw
    agent.eval(); agent.set_mode(AgentMode.TEST)
    base.seed(seed)
    mjw.reset_data(env._engine._solver.mjw_model, env._engine._solver.mjw_data)
    obs, info = agent._reset_envs()
    noise = torch.Generator(device=obs.device).manual_seed(seed + 1000000)
    n = len(obs)
    sums = torch.zeros((2, 4, 4), device=obs.device)
    episode_return = torch.zeros(n, device=obs.device)
    episode_ticks = torch.zeros_like(episode_return)
    initial_yaw = env._yaw_degrees.detach().clone()
    first = torch.ones(n, device=obs.device, dtype=torch.bool)
    first_fail = torch.zeros_like(first)
    first_group = env._perturbed_rows.long()*2 + (env._gaits[env._motion_ids] == -1).long()
    with torch.no_grad():
        for tick in range(ticks):
            group = env._perturbed_rows.long()*2 + (env._gaits[env._motion_ids] == -1).long()
            action, _ = agent._decide_action(obs, info)
            if exploration:
                dist = agent._model.eval_actor(agent._obs_norm.normalize(obs))
                action = agent._a_norm.unnormalize(base.sample_normalized_action(dist, noise))
            obs, reward, done, info = env.step(action)
            end = done != DoneFlags.NULL.value
            fail = done == DoneFlags.FAIL.value
            first_fail |= first & fail
            first &= ~end
            episode_return += reward
            episode_ticks += 1
            # Report all completed episodes and the later, warmed stream separately.
            for window in range(2):
                if window == 1 and tick < 120:
                    continue
                for g in range(4):
                    mask = (group == g) & end
                    sums[window, g, 0] += mask.sum()
                    sums[window, g, 1] += (mask & fail).sum()
                    sums[window, g, 2] += episode_return[mask].sum()
                    sums[window, g, 3] += episode_ticks[mask].sum()
            episode_return.masked_fill_(end, 0)
            episode_ticks.masked_fill_(end, 0)
            obs, info = agent._reset_done_envs(done)
            if (tick+1) % 120 == 0:
                print('AUDIT_PROGRESS', json.dumps(dict(tick=tick+1, exploration=exploration,
                    completed=int(sums[0,:,0].sum()), failures=int(sums[0,:,1].sum()))), flush=True)
    result = dict(seed=seed, exploration=exploration, ticks=ticks, groups={}, first_cohort={},
        initial_perturbed_yaw_min=float(initial_yaw[env._perturbed_rows].min()),
        initial_perturbed_yaw_max=float(initial_yaw[env._perturbed_rows].max()))
    values = sums.cpu().tolist()
    for w, label in enumerate(['all_completed', 'completed_after_tick120']):
        result['groups'][label] = {}
        for g, name in enumerate(GROUPS):
            count, failures, reward, length = values[w][g]
            result['groups'][label][name] = dict(episodes=int(count), failures=int(failures),
                failure_percent=100*failures/count if count else None,
                mean_return=reward/count if count else None, mean_ticks=length/count if count else None)
    for g, name in enumerate(GROUPS):
        mask = first_group == g
        result['first_cohort'][name] = dict(rows=int(mask.sum()), failures=int(first_fail[mask].sum()),
            failure_percent=100*float(first_fail[mask].float().mean()), unfinished=int(first[mask].sum()))
    return result


def run(root, checkpoint, output):
    started = time.perf_counter()
    root = Path(root).resolve(); checkpoint = Path(checkpoint).resolve()
    output = Path(output).resolve(); output.mkdir(exist_ok=True, parents=True)
    os.environ['PYGLET_HEADLESS'] = 'true'
    sys.path[:0] = [str(root/'pipeline'), str(root/'MimicKit/mimickit')]
    os.chdir(root/'MimicKit'); torch.set_num_threads(2)
    import yaml
    import warp as wp
    from util import mp_util
    from perturbed_omni import PerturbedOmniEnv
    from omni_policy import OmniPPOAgent
    from resume import restore, migrate_physical_observation_scales
    wp.init(); wp.set_device('cuda:0'); mp_util.init(0, 1, 'cuda:0', 6899)
    cfg, ec, ac = [yaml.safe_load((root/'prepared'/(n+'_config.yaml')).read_text()) for n in ['env','engine','agent']]
    env = PerturbedOmniEnv(cfg, ec, 1024, 'cuda:0', False)
    agent = OmniPPOAgent(ac, env, 'cuda:0')
    restored = restore(agent, checkpoint)
    if cfg['perturbed_motion'].get('observation_normalization') == 'physical_scales_v1':
        migrate_physical_observation_scales(agent)
    agent._init_train()
    initial = {k:v.detach().clone() for k,v in agent._model.state_dict().items()}
    report = dict(kind='frozen_headroom_audit', complete=False, restored=restored,
        checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        gpu=torch.cuda.get_device_name(), accepted_actor_updates=0,
        first_episodes={}, continuous={}, setup_seconds=time.perf_counter()-started)
    print('AUDIT_RESTORED', json.dumps({k:v for k,v in report.items() if k not in ['first_episodes','continuous']}), flush=True)
    for noisy in [False, True]:
        label = 'noisy' if noisy else 'deterministic'
        report['first_episodes'][label] = base.evaluate(env, agent, [481031,481032], max_ticks=120, exploration=noisy)
        print('AUDIT_FIRST_EPISODES', json.dumps(dict(mode=label,
            groups=[r['groups'] for r in report['first_episodes'][label]])), flush=True)
        report['continuous'][label] = continuous(env, agent, 481031, noisy)
        base.write(output/'result.json', report)
    delta = max(float((v-initial[k]).abs().max()) for k,v in agent._model.state_dict().items())
    assert delta == 0, 'Frozen audit unexpectedly changed model parameters'
    report.update(complete=True, model_max_abs_delta=delta, total_seconds=time.perf_counter()-started)
    base.write(output/'result.json', report)
    print('AUDIT_COMPLETE', json.dumps(dict(total_seconds=report['total_seconds'], model_max_abs_delta=delta)), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', required=True); p.add_argument('--checkpoint', required=True); p.add_argument('--output', required=True)
    a = p.parse_args(); run(a.root, a.checkpoint, a.output)
