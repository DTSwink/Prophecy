"""Isolated FastTD3-style adapter using Holosoma's unmodified C51 critic.

The production actor, motor noise, phase semantics, task and simulator stay
unchanged. This is a checkpoint-compatible adaptation, not a paper reproduction.
"""
import copy
import time
import json
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
import supermimic_race as base
from vendor.holosoma_fast_sac import Critic


def scalar_distribution(value, support):
    """Linear C51 projection, including exact atoms and negative terminal costs."""
    z = value.clamp(float(support[0]), float(support[-1]))
    # Adjacent float32 atoms near -105 suffer cancellation; use the full span.
    b = (z-support[0])/((support[-1]-support[0])/(len(support)-1))
    lo = b.floor().long().clamp(0, len(support)-1)
    hi = (lo+1).clamp_max(len(support)-1)
    mass = b-lo
    p = value.new_zeros(len(value), len(support))
    p.scatter_add_(1, lo[:, None], (1-mass)[:, None])
    p.scatter_add_(1, hi[:, None], mass[:, None])
    return p


def nstep(reward, done, fail, gamma=.99):
    """Stop at the first reset. Timeout bootstraps its PRE-reset next state."""
    total = torch.zeros_like(reward[0])
    active = torch.ones_like(done[0])
    index = torch.zeros_like(done[0], dtype=torch.long)
    bootstrap = torch.ones_like(reward[0])
    discount = torch.ones_like(reward[0])
    for t in range(len(reward)):
        total += active*gamma**t*reward[t]
        index = torch.where(active, t, index)
        bootstrap = torch.where(active, (~fail[t]).float(), bootstrap)
        discount = torch.where(active, gamma**(t+1), discount)
        active = active & ~done[t]
    return total, bootstrap, discount, index


def regularized_actor_objective(q, action, behavior_action, alpha):
    """TD3+BC's published Q normalization and action regression objective."""
    weight = alpha/q.detach().abs().mean().clamp_min(1e-6)
    bc = F.mse_loss(action, behavior_action)
    return -weight*q.mean()+bc, weight, bc


def policy_action(model, obs, pert, fallback, low, high, noise=0.):
    dist = model.eval_actor(obs)
    motor = dist.mode
    if noise:
        motor = motor+(torch.randn_like(motor)*noise).clamp(-3*noise, 3*noise)
    prediction = model.eval_phase(obs)
    length = prediction.norm(dim=-1, keepdim=True)
    phase = torch.where(length > 1e-6, prediction/length.clamp_min(1e-6), fallback)
    return torch.cat((motor.clamp(low, high), phase*pert[:, None]), -1), prediction, dist.mode


def run(ctx, result, out, seconds, setup_started, training_seed=57361,
        actor_lr=3e-5, eval_interval=180, bc_alpha=0.):
    from learning.base_agent import AgentMode
    from envs.base_env import DoneFlags
    import mujoco_warp as mjw
    from supermimic_pilot import rates

    env, agent = ctx.e, ctx.a
    device = ctx.device
    params = list(agent._model.get_actor_params())
    initial_actor = [p.detach().clone() for p in params]
    replay = base.Replay(1024, device, capacity=256)
    started = time.perf_counter()
    result.update(kind='holosoma_c51_td3_adapter', offpolicy_td3=True,
                  warm_model=None, model_pretraining_accounting=None,
                  setup_and_baseline_seconds=started-setup_started,
                  recipe=dict(gamma=.99, nstep=3, batch=2048, critic_width=1024,
                      atoms=201, support=[-105., 105.], critic_lr=3e-4,
                      actor_lr=actor_lr, polyak=.005, actor_delay=2,
                      critic_updates_per_sim_step=2, warmup_ticks=256,
                      warmup_fit_seconds=90, warmup_selection='best_heldout',
                      warmup_min_seconds=30, warmup_patience_seconds=15,
                      mean_q=True, entropy=False,
                      actor_interface_unchanged=True, production_noise=.075,
                      phase_is_deterministic_action=True, bc_alpha=bc_alpha,
                      preserved_initial_data_fraction=.5 if bc_alpha else 0.))
    seed_values = [481031, 481032]
    baseline = rates(result['evaluations'][0])
    noise_baseline = rates(result['noisy_evaluations'][0])
    history = history_xy = None
    transitions = 0

    def reset():
        nonlocal history, history_xy
        agent.set_mode(AgentMode.TRAIN)
        agent.train()
        mjw.reset_data(env._engine._solver.mjw_model, env._engine._solver.mjw_data)
        agent._curr_obs, agent._curr_info = agent._reset_envs()
        history = ctx.physical(agent._curr_obs)[:, None].repeat(1, 3, 1)
        history_xy = env._engine.get_root_pos(env._get_char_id())[:, None, :2].repeat(1, 3, 1)

    def qobs(obs, hist, xy, motion, age, pert, clock):
        # History/age are needed by the existing AE/handoff reward. Absolute XY
        # is irrelevant, but inter-frame displacement is not.
        relxy = (xy[:, :-1]-xy[:, -1:]).flatten(1)
        return torch.cat((obs, hist[:, :-1].flatten(1), relxy,
            F.one_hot(motion, ctx.nmotion).float(), age[:, None]/120.,
            pert[:, None].float(), clock), -1)

    @torch.no_grad()
    def collect(ticks):
        nonlocal history, history_xy, transitions
        for _ in range(ticks):
            obs = agent._curr_obs
            x = ctx.physical(obs)
            normalized = agent._obs_norm.normalize(obs)
            motion = env._motion_ids.clone()
            pert = env._perturbed_rows.clone()
            age = torch.round(env._time_buf*30).clone()
            times = (env._time_buf+env._motion_time_offsets).clone()
            phase = obs[:, -2:].clone()
            clock = ctx.clock_phase(motion, times)
            clock_next = ctx.clock_phase(motion, times+1/30.)
            current_qobs = qobs(normalized, history, history_xy, motion, age, pert, clock)
            action, _ = agent._decide_action(obs, agent._curr_info)
            executed = agent._a_norm.normalize(action.clamp(env._action_bound_low, env._action_bound_high))
            nxt, reward, done, _ = env.step(action)
            nx = ctx.physical(nxt)
            nobs = agent._obs_norm.normalize(nxt)
            xy = env._engine.get_root_pos(env._get_char_id())[:, :2].clone()
            nh = torch.cat((history[:, 1:], nx[:, None]), 1)
            nxy = torch.cat((history_xy[:, 1:], xy[:, None]), 1)
            nqobs = qobs(nobs, nh, nxy, motion, age+1, pert, clock_next)
            # The environment writes the queued prediction into this next input.
            qa = torch.cat((executed, nxt[:, -2:]*pert[:, None]), -1)
            fail = done == DoneFlags.FAIL.value
            ended = done != DoneFlags.NULL.value
            replay.add(obs=normalized, next_obs=nobs, qobs=current_qobs,
                next_qobs=nqobs, action=qa, reward=reward, done=ended, fail=fail,
                pert=pert, phase=phase, next_phase=nxt[:, -2:],
                next_clock=clock_next,
                bootstrap_v=agent._model.eval_critic(nobs).squeeze(-1).clamp(-100, 100))
            history, history_xy = nh, nxy
            agent._curr_obs, agent._curr_info = agent._reset_done_envs(done)
            history[ended] = ctx.physical(agent._curr_obs)[ended, None].repeat(1, 3, 1)
            history_xy[ended] = env._engine.get_root_pos(env._get_char_id())[ended, None, :2].repeat(1, 3, 1)
            transitions += 1024

    base.seed(training_seed)
    reset()
    with torch.no_grad():
        obs = agent._obs_norm.normalize(agent._curr_obs)
        qa, _, mean = policy_action(agent._model, obs, env._perturbed_rows,
                                   agent._curr_obs[:, -2:], ctx.low, ctx.high)
        action, _ = agent._decide_action(agent._curr_obs, agent._curr_info)
        predicted = env._pending_phase.clone()
        phase_error = (qa[env._perturbed_rows, -2:]-predicted[env._perturbed_rows]).abs().max()
        ids = env._phase_feedback_ids
        subset, _, _ = policy_action(agent._model, obs[ids], env._perturbed_rows[ids],
                                    agent._curr_obs[ids, -2:], ctx.low, ctx.high)
        exact_error = (subset[:, -2:]-predicted[ids]).abs().max()
        result['initial_action_max_error'] = float((mean-agent._model.eval_actor(obs).mode).abs().max())
        result['initial_phase_max_error'] = float(phase_error)
        result['initial_phase_same_batch_max_error'] = float(exact_error)
        print('OFFPOLICY_PHASE_PARITY', json.dumps(dict(same_batch=float(exact_error),
            full_batch=float(phase_error), feedback_rows=len(ids),
            recovery_ready=bool(env._recovery_ready))), flush=True)
        assert float(exact_error) < 1e-6, 'Same-batch phase parity failed: '+str(float(exact_error))
        assert float(phase_error) < 2e-4, 'Full-batch phase difference too large: '+str(float(phase_error))
        assert torch.allclose(agent._model.eval_actor(obs).stddev, torch.full_like(mean, .075), atol=1e-6)
    print('OFFPOLICY_START', json.dumps(result['recipe']), flush=True)
    collect(256)
    # Only the initial frozen-actor data use these long real-return targets.
    data = replay.data
    returns = torch.empty_like(data['reward'])
    tail = data['bootstrap_v'][255]
    for t in reversed(range(256)):
        boot = torch.where(data['done'][t], data['bootstrap_v'][t], tail)
        tail = data['reward'][t]+.99*(~data['fail'][t])*boot
        returns[t] = tail
    data['warm_target'] = returns
    d = data['qobs'].shape[-1]
    critic = Critic({'obs': {'start': 0, 'end': d, 'size': d}}, ['obs'],
        n_act=36, num_atoms=201, v_min=-105., v_max=105., hidden_dim=1024,
        use_layer_norm=True, num_q_networks=2, device=device)
    opt_q = torch.optim.AdamW(critic.parameters(), lr=3e-4, betas=(.9, .95), weight_decay=.001)
    opt_actor = torch.optim.Adam(params, lr=actor_lr, betas=(.9, .95))
    target = copy.deepcopy(critic).requires_grad_(False)
    target_actor = copy.deepcopy(agent._model).requires_grad_(False)
    held = {k: v[0] for k, v in replay.sample(4096, 1, holdout=True).items()}
    fit_started = time.perf_counter()
    fits = 0
    warm_checks = []
    best_warm_mse = float('inf')
    best_warm_state = None
    best_warm_optimizer = None
    best_warm_seconds = 0.
    next_warm_check = 5.

    def q_step(obs, actions, target_probs):
        logits = critic(obs, actions)
        loss = -(target_probs*logits.log_softmax(-1)).sum(-1).mean()
        opt_q.zero_grad(set_to_none=True)
        loss.backward()
        norm = nn.utils.clip_grad_norm_(critic.parameters(), 10.)
        if not torch.isfinite(norm):
            raise RuntimeError('Nonfinite off-policy critic gradient')
        opt_q.step()
        return float(loss.detach())

    while time.perf_counter()-fit_started < 90:
        b = {k: v[0] for k, v in replay.sample(2048, 1).items()}
        probs = scalar_distribution(b['warm_target'], critic.q_support)
        q_step(b['qobs'], b['action'], probs[None])
        fits += 1
        # Long Monte Carlo targets are noisy. Retain the best held-out fit
        # instead of using the last of thousands of passes over a fixed buffer.
        fit_elapsed = time.perf_counter()-fit_started
        if fit_elapsed >= next_warm_check:
            with torch.no_grad():
                predicted = critic.get_value(critic(held['qobs'], held['action']).softmax(-1)).mean(0)
                validation_mse = float((predicted-held['warm_target']).square().mean())
            warm_checks.append(dict(seconds=fit_elapsed, fits=fits, mse=validation_mse))
            if validation_mse < best_warm_mse:
                best_warm_mse = validation_mse
                best_warm_state = copy.deepcopy(critic.state_dict())
                best_warm_optimizer = copy.deepcopy(opt_q.state_dict())
                best_warm_seconds = fit_elapsed
            print('Q_WARMUP_VALIDATION', json.dumps(warm_checks[-1]), flush=True)
            next_warm_check += 5.
            if fit_elapsed >= 30 and fit_elapsed-best_warm_seconds >= 15:
                print('Q_WARMUP_EARLY_STOP', fit_elapsed, 'best_at', best_warm_seconds, flush=True)
                break
        if fits % 100 == 0:
            print('Q_WARMUP', fits, 'seconds', time.perf_counter()-fit_started, flush=True)
    assert best_warm_state is not None
    critic.load_state_dict(best_warm_state)
    opt_q.load_state_dict(best_warm_optimizer)
    del best_warm_state, best_warm_optimizer
    result['q_warmup_validation'] = warm_checks
    with torch.no_grad():
        pred = critic.get_value(critic(held['qobs'], held['action']).softmax(-1)).mean(0)
        truth = held['warm_target']
        mse = (pred-truth).square().mean()
        variance = truth.var(unbiased=False)
        correlation = torch.corrcoef(torch.stack((pred, truth)))[0, 1]
        warmup = dict(fits=fits, seconds=time.perf_counter()-started,
            heldout_mse=float(mse), constant_mse=float(variance), correlation=float(correlation),
            support_clip_percent=float((truth.abs()>105).float().mean()*100),
            actor_delta_l2=float(sum((p-q).square().sum() for p, q in zip(params, initial_actor)).sqrt()))
        gate = bool(torch.isfinite(correlation) and mse < .5*variance and correlation > .6)
        warmup['gate'] = gate
        result['q_warmup'] = warmup
        assert warmup['actor_delta_l2'] == 0
        target.load_state_dict(critic.state_dict())
    del data['warm_target']
    offline = copy.deepcopy(replay) if bc_alpha else None
    print('Q_WARMUP_VERIFIED', json.dumps(warmup), flush=True)
    result['stop_reason'] = None if gate else 'Held-out Q warmup gate failed; actor preserved'
    base.write(out/'result.json', result)
    accepted = updates = rejected = 0
    first_actor = None
    evaluation_seconds = 0.
    next_eval = max(eval_interval, time.perf_counter()-started+20)
    next_progress = 0.
    while gate and time.perf_counter()-started < seconds:
        collect(1)
        for _ in range(2):
            if offline is not None:
                recent = replay.sample(1024, 3)
                preserved = offline.sample(1024, 3)
                b = {k: torch.cat((recent[k], preserved[k]), dim=1) for k in recent}
            else:
                b = replay.sample(2048, 3)
            reward, bootstrap, discount, idx = nstep(b['reward'], b['done'], b['fail'])
            worlds = torch.arange(len(idx), device=device)
            final = {k: v[idx, worlds] for k, v in b.items()}
            first = {k: v[0] for k, v in b.items()}
            with torch.no_grad():
                na, _, _ = policy_action(target_actor, final['next_obs'], final['pert'],
                    final['next_phase'], ctx.low, ctx.high, noise=.075)
                distribution = target.projection(final['next_qobs'], na, reward, bootstrap, discount)
                support_clip = ((reward[:, None]+bootstrap[:, None]*discount[:, None]*target.q_support).abs()>105).float().mean()
            loss_q = q_step(first['qobs'], first['action'], distribution)
            updates += 1
            metrics = dict(critic_loss=loss_q, support_clip_fraction=float(support_clip))
            if updates % 2 == 0:
                for p in critic.parameters():
                    p.requires_grad_(False)
                action, phase, mean = policy_action(agent._model, first['obs'], first['pert'],
                    first['phase'], ctx.low, ctx.high)
                old_mean = mean.detach().clone()
                q = critic.get_value(critic(first['qobs'], action).softmax(-1)).mean(0)
                phase_loss = ((phase-first['next_clock']).square().mean(-1)*(~first['pert'])).mean()
                bound = (mean-mean.clamp(ctx.low, ctx.high)).square().sum(-1).mean()
                if bc_alpha:
                    task_loss, q_weight, bc = regularized_actor_objective(q, action, first['action'], bc_alpha)
                    metrics.update(behavior_cloning_loss=float(bc.detach()), q_weight=float(q_weight))
                else:
                    task_loss = -q.mean()
                loss_actor = task_loss+agent._phase_weight*phase_loss+agent._action_bound_weight*bound
                opt_actor.zero_grad(set_to_none=True)
                loss_actor.backward()
                norm = nn.utils.clip_grad_norm_(params, 1.)
                if not torch.isfinite(norm):
                    raise RuntimeError('Nonfinite off-policy actor gradient')
                for p in params:
                    if p.grad is not None:
                        p.grad.clamp_(-.1, .1)
                before = [p.detach().clone() for p in params]
                old_opt = copy.deepcopy(opt_actor.state_dict())
                opt_actor.step()
                with torch.no_grad():
                    new_mean = agent._model.eval_actor(first['obs']).mode
                    kl = .5*((new_mean-old_mean)/.075).square().sum(-1).mean()
                    bad = bool(kl > .18)
                    if bad:
                        for p, old in zip(params, before):
                            p.copy_(old)
                        opt_actor.load_state_dict(old_opt)
                        for group in opt_actor.param_groups:
                            group['lr'] = max(1e-7, group['lr']*.5)
                        rejected += 1
                    else:
                        accepted += 1
                        if first_actor is None:
                            first_actor = time.perf_counter()-started
                    for p, old in zip(params, target_actor.get_actor_params()):
                        old.lerp_(p, .005)
                for p in critic.parameters():
                    p.requires_grad_(True)
                metrics.update(actor_loss=float(loss_actor.detach()), kl=float(kl), rejected=bad,
                    actor_grad_norm=float(norm), actor_lr=opt_actor.param_groups[0]['lr'])
            with torch.no_grad():
                for p, old in zip(critic.parameters(), target.parameters()):
                    old.lerp_(p, .005)
        elapsed = time.perf_counter()-started
        row = dict(update=updates, seconds=elapsed, transitions=transitions,
            accepted_actor_updates=accepted, gate=gate, metrics=metrics)
        if elapsed >= next_progress:
            result['updates'].append(row)
            base.write(out/'result.json', result)
            print('PROGRESS', json.dumps(row), flush=True)
            next_progress = elapsed+15
        if elapsed < seconds and elapsed >= next_eval:
            begin = time.perf_counter()
            replay.data['done'][(replay.ptr-1)%replay.capacity].fill_(True)
            rng = (torch.get_rng_state(), torch.cuda.get_rng_state(), np.random.get_state(), base.random.getstate())
            bad = False
            for noise, key, original, tolerance in [(False, 'evaluations', baseline, 3),
                    (True, 'noisy_evaluations', noise_baseline, 5)]:
                evaluation = dict(training_seconds=elapsed,
                    rows=base.evaluate(env, agent, seed_values, max_ticks=120, exploration=noise))
                result[key].append(evaluation)
                score = rates(evaluation)
                print('EVALUATION_NOISY' if noise else 'EVALUATION', json.dumps(dict(seconds=elapsed, accepted=accepted, **score)), flush=True)
                bad |= score['perturbed_loco'] > original['perturbed_loco']+tolerance or score['normal_loco'] > original['normal_loco']+2
            torch.set_rng_state(rng[0]); torch.cuda.set_rng_state(rng[1])
            np.random.set_state(rng[2]); base.random.setstate(rng[3])
            reset()
            evaluation_seconds += time.perf_counter()-begin
            next_eval += eval_interval
            if bad:
                result['stop_reason'] = 'Real-simulator regression exceeded the short-test threshold'
                break
    result.update(training_seconds=time.perf_counter()-started,
        intermediate_evaluation_seconds=evaluation_seconds,
        accepted_actor_updates=accepted, rejected_actor_updates=rejected,
        first_actor_seconds=first_actor, critic_updates=updates, final_evaluation_ticks=120)
    result['learning_seconds_excluding_checks'] = result['training_seconds']-evaluation_seconds
    final_started = time.perf_counter()
    for noise, key, rate_key in [(False, 'evaluations', 'final_rates'), (True, 'noisy_evaluations', 'final_noisy_rates')]:
        evaluation = dict(training_seconds=result['training_seconds'],
            rows=base.evaluate(env, agent, seed_values, max_ticks=120, exploration=noise))
        result[key].append(evaluation)
        result[rate_key] = rates(evaluation)
    result.update(complete=True, final_evaluation_seconds=time.perf_counter()-final_started,
        total_worker_seconds=time.perf_counter()-setup_started,
        actor_parameter_delta_l2=float(sum((p.detach()-old).square().sum() for p, old in zip(params, initial_actor)).sqrt()))
    torch.save({k: v.detach().cpu() for k, v in agent.state_dict().items()}, out/'policy_final.pt')
    torch.save(critic.state_dict(), out/'offpolicy_critic.pt')
    base.write(out/'result.json', result)
    print('PILOT_COMPLETE', json.dumps({k: v for k, v in result.items() if k not in ['updates', 'evaluations', 'noisy_evaluations', 'restored']}), flush=True)
    return result
