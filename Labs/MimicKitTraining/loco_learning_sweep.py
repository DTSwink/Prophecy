"""Disposable, paired locomotion PPO experiments; never touches live run state.

Run in the pinned GPU runtime:
    venv/bin/python pipeline/loco_learning_sweep.py SWEEP_DIRECTORY VARIANT

SWEEP_DIRECTORY contains checkpoint.zip, base_config/*_config.yaml and plan.json.
The parent controller owns GPU allocation, timeout, transfer and cleanup. Each
variant is a fresh process, with a complete checkpoint restore. Evaluation runs
only AFTER all learning, using CPU policy snapshots and identical held-out starts.
No replay arrays, TensorBoard writer or production checkpoint pointer is written.
"""
import argparse
import copy
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys
import time
import traceback
import zipfile


REFERENCE_WORLDS = 512
REFERENCE_TICKS = 32
REFERENCE_TRANSITIONS = REFERENCE_WORLDS * REFERENCE_TICKS


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, separators=(',', ':'), allow_nan=False))
    temporary.replace(path)


def clean(value):
    """Keep scalar diagnostics valid JSON even when a failed run has NaNs."""
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def world_counts(spec, plan):
    training = int(spec.get('training_worlds', plan.get('training_worlds', plan.get('worlds', 512))))
    evaluation = int(plan.get('evaluation_worlds', 512))
    if training not in (512, 1024) or evaluation != 512:
        raise ValueError('Supported training worlds are512/1024; paired evaluation remains512')
    return training, evaluation


def experiment_schedule(spec, plan):
    worlds, _ = world_counts(spec, plan)
    ticks = int(spec.get('steps_per_iter', 32))
    equivalent = int(spec.get('equivalent_updates', plan.get('equivalent_updates', 256)))
    evaluations = sorted(set(int(v) for v in spec.get('evaluate_at_updates',
        plan.get('evaluate_at_updates', [equivalent]))))
    if equivalent not in evaluations:
        evaluations.append(equivalent)
    if ticks not in (32, 64) or equivalent < 0:
        raise ValueError('Supported rollout lengths are 32/64; update budget must be nonnegative')
    transitions_per_update = worlds * ticks
    if (any(v < 0 or v > equivalent or v * REFERENCE_TRANSITIONS % transitions_per_update for v in evaluations)
            or equivalent * REFERENCE_TRANSITIONS % transitions_per_update):
        raise ValueError('Evaluation checkpoints must land on whole PPO updates within the budget')
    return ticks, equivalent, {v * REFERENCE_TRANSITIONS // transitions_per_update: v for v in evaluations}


def evaluation_pair(training_env, training_agent, training_worlds, evaluation_worlds,
                    env_factory, agent_factory, privileged_installer=None):
    """Recreate only when world counts differ; snapshots are loaded by caller."""
    if training_worlds == evaluation_worlds:
        return training_env, training_agent, False
    env = env_factory(evaluation_worlds)
    agent = agent_factory(env)
    if privileged_installer is not None:
        privileged_installer(agent)
    return env, agent, True


def adaptive_lr(previous, actual_kl, target, minimum, maximum, rejected=False, factor=1.1):
    """Slow between-update adjustment; the production transactional guard stays on."""
    if not math.isfinite(actual_kl) or rejected or actual_kl > target * 1.5:
        return max(minimum, previous / factor)
    if actual_kl < target * .5:
        return min(maximum, previous * factor)
    return previous


def configure_matmul_precision(torch_module, spec):
    """Optional TF32-style experiment; never enable autocast or change dtypes."""
    previous = torch_module.get_float32_matmul_precision()
    requested = spec.get('matmul_precision')
    if 'matmul_precision' in spec:
        if requested != 'high':
            raise ValueError("The isolated matmul experiment supports only matmul_precision='high'")
        torch_module.set_float32_matmul_precision('high')
    return dict(requested=requested, previous=previous,
        actual=torch_module.get_float32_matmul_precision(),
        allow_tf32=bool(torch_module.backends.cuda.matmul.allow_tf32),
        autocast_changed=False, parameter_dtype_changed=False)


@contextmanager
def canonical_initialization_precision(torch_module, spec):
    """Match starts; candidate precision resumes before any policy/physics tick."""
    if 'matmul_precision' not in spec:
        yield
        return
    previous = torch_module.get_float32_matmul_precision()
    torch_module.set_float32_matmul_precision('highest')
    try:
        yield
    finally:
        torch_module.set_float32_matmul_precision(previous)


def run(directory, name):
    root = Path(os.environ.get('MIMICKIT_SWEEP_RUNTIME', '/workspace/mimickit_trial'))
    sys.path[:0] = [str(root / 'pipeline'), str(root / 'MimicKit/mimickit')]
    os.environ.setdefault('PYGLET_HEADLESS', 'true')
    os.environ.setdefault('OMP_NUM_THREADS', '1')
    import numpy as np
    import torch
    import warp as wp
    import mujoco_warp as mjw
    import yaml
    from util import mp_util
    from learning.base_agent import AgentMode
    from envs.base_env import DoneFlags
    from perturbed_omni import PerturbedOmniEnv
    from omni_policy import OmniPPOAgent
    from resume import restore, override_actor_learning_rate, override_fixed_action_noise

    directory = Path(directory).resolve()
    plan = json.loads((directory / 'plan.json').read_text())
    spec = plan['variants'][name]
    ticks, equivalent, evaluate_after = experiment_schedule(spec, plan)
    worlds, evaluation_worlds = world_counts(spec, plan)
    seeds = plan.get('evaluation_seeds', list(range(83191, 83199)))
    if len(seeds) < 8 or len(set(seeds)) != len(seeds):
        raise ValueError('Use at least eight distinct paired held-out evaluation seeds')
    normal_seed_count = int(plan.get('normal_evaluation_seed_count', len(seeds)))
    if not 1 <= normal_seed_count <= len(seeds):
        raise ValueError('Full normal evaluation seed count must be between one and all seeds')
    if not name or Path(name).name != name or name in ('.', '..'):
        raise ValueError('Variant name must be a simple directory name')
    output = directory / name
    output.mkdir(exist_ok=True)
    result_file = directory / ('result_' + name + '.json')
    if result_file.exists() and json.loads(result_file.read_text()).get('complete'):
        raise RuntimeError('Completed variant already exists; use a new variant name')
    started = time.perf_counter()
    result = dict(variant=name, settings=spec, complete=False, failed=False,
        checkpoint_sha256=None, updates=[], evaluations=[], phase='initializing',
        worlds=worlds, training_worlds=worlds, evaluation_worlds=evaluation_worlds,
        reference_worlds=REFERENCE_WORLDS, reference_steps_per_update=REFERENCE_TICKS,
        reference_transitions_per_update=REFERENCE_TRANSITIONS, steps_per_iter=ticks,
        equivalent_update_budget=equivalent, evaluation_seeds=seeds,
        normal_evaluation_seed_count=normal_seed_count,
        production_state_modified=False, evaluation_after_training=True)

    def save():
        result['elapsed_seconds'] = time.perf_counter() - started
        atomic_json(result_file, clean(result))

    def digest(tensor):
        return hashlib.sha256(tensor.detach().cpu().contiguous().numpy().tobytes()).hexdigest()

    def seed_all(seed):
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)

    def cpu_tree(value):
        if torch.is_tensor(value):
            return value.detach().cpu().clone()
        if isinstance(value, dict):
            return {k: cpu_tree(v) for k, v in value.items()}
        if isinstance(value, list):
            return [cpu_tree(v) for v in value]
        if isinstance(value, tuple):
            return tuple(cpu_tree(v) for v in value)
        return copy.deepcopy(value)

    def normalizer_aux(agent):
        return {n: {k: cpu_tree(getattr(m, k)) for k in
            ('_mean_sq', '_new_count', '_new_sum', '_new_sum_sq')}
            for n, m in agent.named_modules() if hasattr(m, '_new_sum_sq')}

    def policy_snapshot(agent):
        return dict(model=cpu_tree(agent.state_dict()), normalizer_aux=normalizer_aux(agent))

    def load_policy(agent, snapshot):
        agent.load_state_dict(snapshot['model'])
        modules = dict(agent.named_modules())
        for n, values in snapshot['normalizer_aux'].items():
            for k, value in values.items():
                setattr(modules[n], k, value.to(agent._device) if torch.is_tensor(value) else value)

    def set_lr(agent, part, value):
        value = float(value)
        if not math.isfinite(value) or value <= 0:
            raise ValueError(part + ' learning rate must be positive and finite')
        optimizer = getattr(agent, '_' + part + '_optimizer')._optimizer
        previous = [float(g['lr']) for g in optimizer.param_groups]
        for group in optimizer.param_groups:
            group['lr'] = value
        return dict(previous=previous, requested=value, optimizer_state_preserved=True)

    try:
        save()
        checkpoint = directory / 'checkpoint.zip'
        sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        expected = plan.get('sha256', plan.get('checkpoint_sha256'))
        if not expected or sha != expected:
            raise RuntimeError('Experiment checkpoint checksum does not match the isolated plan')
        result['checkpoint_sha256'] = sha
        base = directory / 'base_config'
        configs = {kind: yaml.safe_load((base / (kind + '_config.yaml')).read_text())
                   for kind in ('env', 'engine', 'agent')}
        with zipfile.ZipFile(checkpoint) as bundle:
            originals = {kind: yaml.safe_load(bundle.read(kind + '_config.yaml'))
                         for kind in ('env', 'engine', 'agent')}
        # Prevent accidental use of stale prepared YAML. The parent extracts
        # these from the actual latest checkpoint, with no objective edits.
        if configs != originals:
            raise ValueError('base_config must match configs embedded in checkpoint.zip exactly')
        cfg, ec, ac = (copy.deepcopy(configs[k]) for k in ('env', 'engine', 'agent'))
        ac['steps_per_iter'] = ticks
        for knob in ('actor_epochs', 'critic_epochs', 'actor_batch_size', 'critic_batch_size',
                     'td_lambda', 'actor_kl_limit', 'discount', 'norm_adv_clip'):
            if knob in spec:
                ac[knob] = spec[knob]
        if spec.get('adaptive_actor_kl_target') and float(ac.get('actor_kl_limit', 0)) <= 0:
            raise ValueError('Adaptive actor LR requires the existing analytic KL guard')
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        result['matmul_precision'] = configure_matmul_precision(torch, spec)
        result['initialization_precision_protocol'] = dict(
            environment_and_model_construction='highest' if 'matmul_precision' in spec else 'unchanged',
            explicit_initial_training_and_heldout_resets='highest' if 'matmul_precision' in spec else 'unchanged',
            automatic_episode_resets='candidate_precision',
            rollout_and_optimizer='candidate_precision', exact_initial_hash_validation=True)
        wp.init()
        wp.set_device('cuda:0')
        mp_util.init(0, 1, 'cuda:0', int(plan.get('master_port', 6793)))
        os.chdir(root / 'MimicKit')
        training_seed = int(spec.get('seed', plan.get('training_seed', 13579)))
        seed_all(training_seed)
        with canonical_initialization_precision(torch, spec):
            env = PerturbedOmniEnv(cfg, ec, worlds, 'cuda:0', False)
            agent = OmniPPOAgent(ac, env, 'cuda:0')
        restored = restore(agent, checkpoint)
        agent._init_train()
        if not restored['optimizer_restored']:
            raise RuntimeError('Sweep requires both saved optimizer states to restore without migration')
        if bool(env._recovery_rows.any()):
            raise ValueError('This runner is for the zero-get-up locomotion branch only')
        overrides = {}
        if spec.get('privileged_critic', False):
            from loco_privileged_critic import install
            overrides['privileged_critic'] = install(agent)
        if spec.get('advantage_diagnostics', False):
            from loco_advantage_diagnostics import install
            overrides['advantage_diagnostics'] = install(agent)
        for part in ('actor', 'critic'):
            if part + '_lr' in spec:
                overrides[part + '_lr'] = set_lr(agent, part, spec[part + '_lr'])
        if 'noise' in spec:
            overrides['noise'] = override_fixed_action_noise(agent, spec['noise'])
        result.update(restored=restored, overrides=overrides, training_seed=training_seed,
            effective_agent_config=ac, environment_config_sha256=hashlib.sha256(
                json.dumps(cfg, sort_keys=True).encode()).hexdigest(),
            actual_actor_lr=[float(g['lr']) for g in agent._actor_optimizer._optimizer.param_groups],
            actual_critic_lr=[float(g['lr']) for g in agent._critic_optimizer._optimizer.param_groups],
            actual_noise=agent._model._action_dist._logstd_net.exp().detach().cpu().tolist(),
            normalizer_frozen=not agent._need_normalizer_update(),
            gpu=torch.cuda.get_device_name(0), loss_term_names=env.loss_term_names)
        actor_batch = int(math.ceil(ac['actor_batch_size'] * worlds))
        critic_batch = int(math.ceil(ac['critic_batch_size'] * worlds))
        result['training_batches'] = dict(rollout_samples=worlds * ticks,
            actor_minibatch_samples=actor_batch, critic_minibatch_samples=critic_batch,
            requested_actor_steps_per_update=math.ceil(worlds * ticks / actor_batch) * ac['actor_epochs'],
            requested_critic_steps_per_update=math.ceil(worlds * ticks / critic_batch) * ac['critic_epochs'],
            actor_batch_factor=ac['actor_batch_size'], critic_batch_factor=ac['critic_batch_size'])

        def reset(seed, mode):
            with canonical_initialization_precision(torch, spec):
                seed_all(int(seed))
                agent.eval()
                agent.set_mode(mode)
                solver = env._engine._solver
                # Clearing only articulated positions leaves warm-start accelerations
                # and contacts from the previous evaluation; clear MJWarp first.
                mjw.reset_data(solver.mjw_model, solver.mjw_data)
                obs, info = agent._reset_envs()
            # Env reset clears AE history, pending/feedback phase, time, reward
            # and done per row through the pinned production reset methods.
            return obs, info

        stage_events = {}
        for method_name in ('_rollout_train', '_build_train_data', '_update_critic', '_update_actor'):
            original = getattr(agent, method_name)
            def timed(*args, _original=original, _name=method_name, **kwargs):
                begin, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
                begin.record()
                value = _original(*args, **kwargs)
                end.record()
                stage_events[_name] = (begin, end)
                return value
            setattr(agent, method_name, timed)

        agent._curr_obs, agent._curr_info = reset(training_seed, AgentMode.TRAIN)
        result['training_initial_hashes'] = dict(observation=digest(agent._curr_obs),
            position=digest(env._engine.get_body_pos(0)), velocity=digest(env._engine.get_body_vel(0)),
            target=digest(env.reward_target_pos), motion=digest(env._motion_ids), yaw=digest(env._yaw_degrees))
        result['training_initial_hashes_worlds'] = worlds
        result['initialization_seconds'] = time.perf_counter() - started
        result['phase'] = 'training'
        snapshots = {}
        if 0 in evaluate_after:
            snapshots[0] = policy_snapshot(agent)
        num_updates = equivalent * REFERENCE_TRANSITIONS // (worlds * ticks)
        result['actual_training_updates'] = num_updates
        training_start = time.perf_counter()
        for index in range(num_updates):
            agent._iter = index
            begin = time.perf_counter()
            info = agent._train_iter()
            torch.cuda.synchronize()
            elapsed = time.perf_counter() - begin
            agent._sample_count = agent._update_sample_count()
            metrics = {k: float(v) for k, v in info.items()}
            with torch.no_grad():
                observations = agent._exp_buffer.get_data_flat('obs')
                targets = agent._exp_buffer.get_data_flat('tar_val')
                if spec.get('privileged_critic', False):
                    context = agent._exp_buffer.get_data_flat('critic_context')
                    pred = agent._model.eval_critic(agent._obs_norm.normalize(observations), context).squeeze(-1)
                else:
                    pred = agent._model.eval_critic(agent._obs_norm.normalize(observations)).squeeze(-1)
                residual = targets - pred
                variance = targets.var(unbiased=False)
                metrics['critic_target_variance'] = float(variance)
                metrics['critic_mse_after_update'] = float(residual.square().mean())
                metrics['critic_explained_variance'] = float(1 - residual.var(unbiased=False) / variance.clamp_min(1e-12))
                metrics['critic_target_mean'] = float(targets.mean())
                metrics['critic_prediction_mean'] = float(pred.mean())
            adjustment = None
            target = spec.get('adaptive_actor_kl_target')
            if target is not None:
                current = float(agent._actor_optimizer._optimizer.param_groups[0]['lr'])
                new = adaptive_lr(current, metrics['policy_kl'], float(target),
                    float(spec.get('adaptive_actor_min_lr', 1.125e-6)),
                    float(spec.get('adaptive_actor_max_lr', 9e-6)),
                    rejected=bool(metrics.get('actor_full_rollback', 0)
                                  or metrics.get('actor_steps_rejected', 0)))
                adjustment = set_lr(agent, 'actor', new)
            row = dict(update=index + 1,
                equivalent_updates=(index + 1) * worlds * ticks / REFERENCE_TRANSITIONS,
                transitions=(index + 1) * worlds * ticks, seconds=elapsed,
                stage_gpu_seconds={k: a.elapsed_time(b) / 1000 for k, (a, b) in stage_events.items()},
                metrics=metrics, outcomes=env.take_training_outcomes(), adaptive_lr=adjustment)
            result['updates'].append(row)
            if index + 1 in evaluate_after:
                snap = policy_snapshot(agent)
                snapshots[evaluate_after[index + 1]] = snap
                torch.save(snap, output / ('policy_' + str(evaluate_after[index + 1]) + '.pt'))
            save()
            if (index + 1) % 32 == 0:
                print('SWEEP_TRAIN', name, index + 1, '/', num_updates,
                      'KL', metrics.get('policy_kl'), 'EV', metrics['critic_explained_variance'], flush=True)
            if not all(math.isfinite(metrics[k]) for k in ('critic_loss', 'actor_loss')):
                raise RuntimeError('Nonfinite PPO loss; isolated experiment stopped')
        result['training_wall_seconds'] = time.perf_counter() - training_start
        result['training_seconds'] = sum(r['seconds'] for r in result['updates'])
        result['training_transitions'] = num_updates * ticks * worlds
        # This full continuation save precedes evaluation, so no evaluation RNG,
        # normalizer or phase state can leak into it. Physical episodes restart.
        final_state = dict(model=cpu_tree(agent.state_dict()), normalizer_aux=normalizer_aux(agent),
            actor_optimizer=cpu_tree(agent._actor_optimizer._optimizer.state_dict()),
            critic_optimizer=cpu_tree(agent._critic_optimizer._optimizer.state_dict()),
            actor_steps=agent._actor_optimizer._steps, critic_steps=agent._critic_optimizer._steps,
            samples=agent._sample_count, completed_iteration=restored['iteration_offset'] + num_updates - 1,
            torch_rng=torch.get_rng_state(), cuda_rng=torch.cuda.get_rng_state_all(),
            numpy_rng=np.random.get_state(), python_rng=random.getstate(),
            env_config=cfg, engine_config=ec, agent_config=ac,
            experiment_settings=spec, matmul_precision=result['matmul_precision'],
            initialization_precision_protocol=result['initialization_precision_protocol'],
            training_worlds=worlds, evaluation_worlds=evaluation_worlds,
            reference_transitions_per_update=REFERENCE_TRANSITIONS,
            physics_episode_state_saved=False, isolated_sweep=True)
        torch.save(final_state, output / 'training_final_state.pt')
        del final_state
        result['phase'] = 'evaluating'
        result['evaluation_matmul_precision'] = dict(
            actual=torch.get_float32_matmul_precision(),
            allow_tf32=bool(torch.backends.cuda.matmul.allow_tf32))
        save()
        evaluation_start = time.perf_counter()
        # Retain the training CUDA graphs/buffers until the process exits. The
        # second simulator fits comfortably on the sweep GPU and avoids unsafe
        # teardown assumptions. Default512-world runs construct nothing extra.
        training_environment_and_agent = (env, agent)
        privileged_installer = None
        if spec.get('privileged_critic', False):
            from loco_privileged_critic import install as privileged_installer
        with canonical_initialization_precision(torch, spec):
            env, agent, recreated = evaluation_pair(env, agent, worlds, evaluation_worlds,
                lambda count: PerturbedOmniEnv(copy.deepcopy(cfg), copy.deepcopy(ec), count, 'cuda:0', False),
                lambda evaluation_env: OmniPPOAgent(copy.deepcopy(ac), evaluation_env, 'cuda:0'),
                privileged_installer)
        result['evaluation_environment_recreated'] = recreated
        result['evaluation_setup_seconds'] = time.perf_counter() - evaluation_start
        save()
        first_seed_hashes = {}
        motion_names = [Path(env._motion_lib.get_motion_file(i)).stem
                        for i in range(env._motion_lib.get_num_motions())]
        result['motion_names'] = motion_names
        for equivalent_step in sorted(snapshots):
            load_policy(agent, snapshots[equivalent_step])
            for seed_index, seed in enumerate(seeds):
                obs, info = reset(seed, AgentMode.TEST)
                ids = torch.arange(evaluation_worlds, device='cuda:0')
                motion = env._motion_ids.clone()
                perturbed = env._perturbed_rows.clone()
                gait = env._gaits[motion].clone()
                group = torch.where(gait == -1, torch.where(perturbed, 3, 2), perturbed.long())
                hashes = dict(observation=digest(obs), position=digest(env._engine.get_body_pos(0)),
                    velocity=digest(env._engine.get_body_vel(0)), target=digest(env.reward_target_pos),
                    motion=digest(motion), yaw=digest(env._yaw_degrees))
                if seed not in first_seed_hashes:
                    first_seed_hashes[seed] = hashes
                elif first_seed_hashes[seed] != hashes:
                    raise RuntimeError('Held-out initial state changed between policy snapshots')
                initial_yaw = env._yaw_degrees.clone()
                active = torch.ones(evaluation_worlds, device='cuda:0', dtype=torch.bool)
                done_end = torch.zeros(evaluation_worlds, device='cuda:0', dtype=torch.long)
                reason_end = torch.zeros_like(done_end)
                end_ticks = torch.zeros_like(done_end)
                sums = torch.zeros((evaluation_worlds, len(env.loss_term_names)), device='cuda:0')
                final_terms = torch.zeros_like(sums)
                returns = torch.zeros(evaluation_worlds, device='cuda:0')
                position_cost = torch.zeros_like(returns)
                final_position_cost = torch.zeros_like(returns)
                normal_horizon = int(round(float(cfg['episode_length']) * 30))
                perturbed_horizon = int(cfg['perturbed_motion'].get('episode_ticks', 120))
                full_normal_horizon = seed_index < normal_seed_count
                max_ticks = max(normal_horizon, perturbed_horizon) if full_normal_horizon else perturbed_horizon
                # Later screening seeds retain all perturbed episodes but stop
                # after their horizon. Exclude ALL normal rows from those seeds,
                # including early failures, to avoid censoring/survivorship bias.
                eligible = torch.ones_like(active) if full_normal_horizon else perturbed
                with torch.no_grad():
                    for tick in range(max_ticks):
                        action, _ = agent._decide_action(obs, info)
                        obs, reward, done, info = env.step(action)
                        raw_pos_cost = (env._engine.get_body_pos(0) - env.reward_target_pos).square().mean((1, 2))
                        sums += torch.where(active[:, None], env.loss_terms, 0)
                        returns += torch.where(active, reward, 0)
                        position_cost += torch.where(active, raw_pos_cost, 0)
                        finishing = active & (done != DoneFlags.NULL.value)
                        end_ticks[finishing] = tick + 1
                        done_end[finishing] = done[finishing].long()
                        reason_end[finishing] = env._reset_reason[finishing]
                        final_terms[finishing] = env.loss_terms[finishing]
                        final_position_cost[finishing] = raw_pos_cost[finishing]
                        active &= ~finishing
                        if not bool(active.any()):
                            break
                        obs, info = agent._reset_done_envs(done)
                end_ticks[active] = max_ticks
                final_terms[active] = env.loss_terms[active]
                final_position_cost[active] = raw_pos_cost[active]
                means = sums / end_ticks.clamp_min(1)[:, None]
                entry = dict(evaluation_update=equivalent_step, seed=seed, rows=evaluation_worlds,
                    initial_hashes=hashes, unfinished=int(active.sum()),
                    unfinished_eligible=int((active & eligible).sum()),
                    full_normal_horizon=full_normal_horizon,
                    normal_horizon_ticks=normal_horizon, max_evaluation_ticks=max_ticks,
                    evaluation_eligible=eligible.cpu().tolist(),
                    censored=(active & ~eligible).cpu().tolist(),
                    group_labels={'0': 'normal_loco', '1': 'perturbed_loco',
                                  '2': 'normal_idle', '3': 'perturbed_idle'},
                    group=group.cpu().tolist(), row_ids=ids.cpu().tolist(),
                    motion_id=motion.cpu().tolist(), gait=gait.cpu().tolist(),
                    equipment=env._equipment[motion].cpu().tolist(),
                    initial_yaw_degrees=initial_yaw.cpu().tolist(),
                    final_done=done_end.cpu().tolist(), reasons=reason_end.cpu().tolist(),
                    end_ticks=end_ticks.cpu().tolist(), episode_return=returns.cpu().tolist(),
                    mean_loss_terms=means.cpu().tolist(), end_loss_terms=final_terms.cpu().tolist(),
                    mean_body_tracking_cost=means[:, :4].sum(-1).cpu().tolist(),
                    mean_body_position_distance_m2=(position_cost / end_ticks.clamp_min(1)).cpu().tolist(),
                    end_body_position_distance_m2=final_position_cost.cpu().tolist())
                summaries = {}
                for key, label in entry['group_labels'].items():
                    selected = (group == int(key)) & eligible
                    count = int(selected.sum())
                    if count:
                        summaries[label] = dict(rows=count,
                            failures=int((selected & (done_end == DoneFlags.FAIL.value)).sum()),
                            timeouts=int((selected & (done_end == DoneFlags.TIME.value)).sum()),
                            unfinished=int((selected & active).sum()),
                            mean_end_tick=float(end_ticks[selected].float().mean()),
                            mean_body_tracking_cost=float(means[selected, :4].sum(-1).mean()))
                entry['summary'] = summaries
                result['evaluations'].append(entry)
                save()
                print('SWEEP_EVAL', name, equivalent_step, seed, json.dumps(summaries), flush=True)
        result.update(phase='complete', complete=True,
            evaluation_seconds=time.perf_counter() - evaluation_start)
        save()
        print('LOCOMOTION_SWEEP_COMPLETE', name, flush=True)
    except BaseException as error:
        result.update(failed=True, phase='failed', error=type(error).__name__ + ': ' + str(error),
                      traceback=traceback.format_exc())
        save()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory')
    parser.add_argument('variant')
    args = parser.parse_args()
    run(args.directory, args.variant)


if __name__ == '__main__':
    main()
