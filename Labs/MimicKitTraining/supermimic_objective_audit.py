"""Check model-gradient components against full real episodes; no learning.

The smooth failure derivative is an experimental approximation, not the task's
hard termination. Test its advice rather than assuming a finite gradient is right.
"""
import hashlib
import json
import os
import sys
import threading
import time
import traceback

import torch

import supermimic_race as base
from supermimic_decoupled import anchor
from supermimic_exact_reward import ExactReward


def component_directions(objectives, delta):
    gradients = {
        name: torch.autograd.grad(value.sum(), delta, retain_graph=True)[0].detach()
        for name, value in objectives.items()
    }
    for gradient in gradients.values():
        if not torch.isfinite(gradient).all():
            raise RuntimeError('Nonfinite objective derivative')
    directions = {name: g / g.square().mean(-1, keepdim=True).sqrt().clamp_min(1e-8)
                  for name, g in gradients.items()}
    return gradients, directions


def audit(env, agent, ctx, wm, out, horizon, exploration=False, seconds=480):
    import mujoco_warp as mjw
    from envs.base_env import DoneFlags
    from learning.base_agent import AgentMode

    started = time.perf_counter()
    policy_before = [p.detach().clone() for p in agent.parameters()]
    for model in (agent, wm):
        for p in model.parameters():
            p.requires_grad_(False)
    agent.eval()
    agent.set_mode(AgentMode.TEST)
    exact = ExactReward(ctx)
    n, device = env.get_num_envs(), ctx.device
    result = dict(kind='objective_component_audit', complete=False, exploration=exploration,
                  horizon=horizon, amplitude=.01, seeds=[91871, 92719], probes=[], checks=[])
    state = dict(stage='starting', tick=None, progress=time.monotonic())
    main_thread = threading.get_ident()
    finished = threading.Event()

    def progress(stage, tick=None):
        state.update(stage=stage, tick=tick, progress=time.monotonic())

    def monitor():
        while not finished.wait(20):
            stack = traceback.extract_stack(sys._current_frames()[main_thread])[-8:]
            status = dict(seconds=time.perf_counter()-started, stage=state['stage'], tick=state['tick'],
                          stalled_seconds=time.monotonic()-state['progress'],
                          stack=[dict(file=Path(f.filename).name, line=f.lineno, function=f.name) for f in stack])
            print('OBJECTIVE_AUDIT_LIVE', json.dumps(status), flush=True)
            if status['stalled_seconds'] > 100 or status['seconds'] > seconds + 10:
                base.write(out/'watchdog.json', status)
                print('OBJECTIVE_AUDIT_ERROR no progress within bounded stage timeout', flush=True)
                os._exit(3)

    from pathlib import Path
    threading.Thread(target=monitor, daemon=True).start()
    print('OBJECTIVE_AUDIT_START', json.dumps(dict(exploration=exploration, budget=seconds)), flush=True)

    def check_deadline():
        if time.perf_counter() - started > seconds:
            raise TimeoutError('Objective audit exceeded its bounded budget')

    def real(seed, prefix_ticks, delta=None):
        check_deadline()
        progress('reset')
        with torch.no_grad():
            base.seed(seed)
            mjw.reset_data(env._engine._solver.mjw_model, env._engine._solver.mjw_data)
            obs, info = agent._reset_envs()
            noise = torch.Generator(device=device).manual_seed(seed + 1000000)
            xy = env._engine.get_root_pos(env._get_char_id())[:, :2].clone()
            history = ctx.physical(obs)[:, None].repeat(1, 3, 1)
            xy_history = xy[:, None].repeat(1, 3, 1)
            alive = torch.ones(n, device=device, dtype=torch.bool)
            initial = None
            trajectory = []
            total = torch.zeros(n, device=device)
            short = torch.zeros_like(total)
            discounted = torch.zeros_like(total)
            failed = torch.zeros_like(alive)
            for tick in range(120):
                progress('real rollout', tick)
                if tick == prefix_ticks:
                    initial = dict(obs=obs.clone(), history=history.clone(), xy_history=xy_history.clone(),
                                   valid=alive.clone(), motion=env._motion_ids.clone(), pert=env._perturbed_rows.clone())
                    alive = torch.ones_like(alive)
                action, _ = agent._decide_action(obs, info)
                dist = agent._model.eval_actor(agent._obs_norm.normalize(obs))
                raw = base.sample_normalized_action(dist, noise) if exploration else dist.mode
                if tick == prefix_ticks and delta is not None:
                    raw = raw + delta
                action = agent._a_norm.unnormalize(raw.clamp(ctx.low, ctx.high))
                nxt, reward, done, info = env.step(action)
                xy = env._engine.get_root_pos(env._get_char_id())[:, :2].clone()
                x = ctx.physical(nxt)
                ended, fail = done != DoneFlags.NULL.value, done == DoneFlags.FAIL.value
                if tick >= prefix_ticks:
                    t = tick - prefix_ticks
                    total += alive * reward
                    discounted += .99 ** t * alive * reward
                    if t < horizon:
                        short += .99 ** t * alive * reward
                        trajectory.append(dict(x=x.clone(), xy=xy, phase=nxt[:, -2:].clone(),
                            raw=raw.clone(), mean=dist.mode.clone(), reward=reward.clone(),
                            age=torch.round(env._time_buf * 30).clone(),
                            times=(env._time_buf + env._motion_time_offsets).clone(), done=ended, fail=fail))
                    failed |= alive & fail
                alive &= ~ended
                history = torch.cat((history[:, 1:], x[:, None]), 1)
                xy_history = torch.cat((xy_history[:, 1:], xy[:, None]), 1)
                obs, info = agent._reset_done_envs(done)
                history[ended] = ctx.physical(obs)[ended, None].repeat(1, 3, 1)
                xy_history[ended] = env._engine.get_root_pos(env._get_char_id())[ended, None, :2].repeat(1, 3, 1)
            return dict(initial=initial, trajectory=trajectory, total=total, short=short,
                        discounted=discounted, failed=failed)

    # Prime lazy simulator state before any matched comparisons.
    real(91879, 8)
    for seed in result['seeds']:
        for prefix_ticks in (8, 40):
            control = real(seed, prefix_ticks)
            init = control['initial']
            motion, pert = init['motion'], init['pert']
            penalty = pert * (env._gaits[motion] != -1) * float(env._perturb_cfg['loco_failure_penalty'])
            delta = torch.zeros((n, 34), device=device, requires_grad=True)
            x, phase = ctx.physical(init['obs']), init['obs'][:, -2:]
            h, xh = init['history'], init['xy_history']
            alive = torch.ones(n, device=device)
            dense = torch.zeros_like(alive)
            failure = torch.zeros_like(alive)
            critic = torch.zeros_like(alive)
            reward_error, mean_error, hard_mismatches = [], [], []
            for t, row in enumerate(control['trajectory']):
                progress('differentiable rollout', t)
                raw, _, _ = ctx.policy(x, motion, phase)
                mean_error.append(((raw - row['mean']).abs() * alive[:, None]).amax())
                sample = raw + (row['raw'] - raw.detach())
                action = (sample + (delta if t == 0 else 0)).clamp(ctx.low, ctx.high)
                phase = row['phase'].detach()  # Same phase derivative rule as the actor pilot.
                nx = anchor(wm.step(x, action), row['x'])
                _, _, v, _ = exact.bodies(x, xh[:, -1])
                _, _, nv, _ = exact.bodies(nx, xh[:, -1])
                xy = anchor(xh[:, -1] + (v[:, 0, :2] + nv[:, 0, :2]) / 60, row['xy'])
                h = torch.cat((h[:, 1:], nx[:, None]), 1)
                xh = torch.cat((xh[:, 1:], xy[:, None]), 1)
                reward, _ = exact(h, xh, motion, phase, row['age'], row['times'], pert)
                hard, soft = exact.failure(nx, xy, motion, row['age'], pert)
                reward_error.append(((reward - (row['reward'] + penalty * row['fail'])).abs() * alive).amax())
                scope = pert & (env._gaits[motion] != -1) & (alive > 0)
                hard_mismatches.append(((hard != row['fail']) & scope).sum())
                dense += .99 ** t * alive * reward
                failure -= .99 ** t * alive * penalty * soft
                final = (row['done'] & ~row['fail']) | ((t == horizon - 1) & ~row['done'])
                value = agent._model.eval_critic(ctx.obs(nx, motion, phase)).squeeze(-1)
                critic += .99 ** (t + 1) * alive * final * value
                alive = alive * ~row['done']
                x = nx
            checks = dict(seed=seed, prefix_ticks=prefix_ticks,
                          reward_max_error=float(torch.stack(reward_error).max().detach()),
                          mean_max_error=float(torch.stack(mean_error).max().detach()),
                          hard_failure_mismatches=int(torch.stack(hard_mismatches).sum()))
            if checks['reward_max_error'] > .002 or checks['mean_max_error'] > .002 or checks['hard_failure_mismatches']:
                raise RuntimeError('Objective reconstruction mismatch: ' + str(checks))
            objectives = dict(dense=dense, dense_critic=dense + critic, full=dense + critic + failure)
            progress('three backward passes')
            gradients, directions = component_directions(objectives, delta)
            checks['gradient_norms'] = {k: float(v.norm()) for k, v in gradients.items()}
            checks['gradient_cosine_to_dense'] = {k: float((v * gradients['dense']).sum() /
                (v.norm() * gradients['dense'].norm()).clamp_min(1e-12)) for k, v in gradients.items()}
            result['checks'].append(checks)
            print('OBJECTIVE_AUDIT_CHECK', json.dumps(checks), flush=True)
            candidates = {}
            common = init['valid'] & pert & (env._gaits[motion] != -1)
            for name, direction in directions.items():
                positive = real(seed, prefix_ticks, .01 * direction)
                negative = real(seed, prefix_ticks, -.01 * direction)
                mismatch = torch.stack([(r['initial']['obs'] - init['obs']).abs().amax(-1)
                                        for r in (positive, negative)]).amax(0)
                valid = common & positive['initial']['valid'] & negative['initial']['valid'] & (mismatch < 2e-4)
                candidates[name] = dict(positive=positive, negative=negative, valid=valid)
                common &= valid
            if int(common.sum()) < 32:
                raise RuntimeError('Too few identical surviving starts across objective probes')
            for name, pair in candidates.items():
                p, m = pair['positive'], pair['negative']
                d = p['discounted'] - m['discounted']
                row = dict(seed=seed, prefix_ticks=prefix_ticks, component=name, rows=int(common.sum()),
                           mean_discounted_return_change=float(d[common].mean()),
                           median_discounted_return_change=float(d[common].median()),
                           positive_fraction=float((d[common] > 0).float().mean()),
                           mean_return_change=float((p['total'] - m['total'])[common].mean()),
                           short_return_change=float((p['short'] - m['short'])[common].mean()),
                           positive_failures=int(p['failed'][common].sum()), negative_failures=int(m['failed'][common].sum()),
                           row_valid=common.cpu().tolist(), row_motion=motion.cpu().tolist(),
                           row_return_delta=d.cpu().tolist(), row_failure_delta=(p['failed'].int() - m['failed'].int()).cpu().tolist())
                result['probes'].append(row)
                print('OBJECTIVE_AUDIT_PROBE', json.dumps({k: v for k, v in row.items() if not k.startswith('row_')}), flush=True)
            base.write(out / 'result.json', result)
    change = float(sum((p.detach() - q).square().sum() for p, q in zip(agent.parameters(), policy_before)).sqrt())
    assert change == 0.
    finished.set()
    result.update(complete=True, policy_parameter_delta_l2=change, seconds=time.perf_counter() - started)
    base.write(out / 'result.json', result)
    print('OBJECTIVE_AUDIT_COMPLETE', json.dumps({k: v for k, v in result.items() if k not in ('probes', 'checks')}), flush=True)
    return result
