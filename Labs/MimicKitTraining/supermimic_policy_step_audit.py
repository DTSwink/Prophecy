"""Probe a complete policy-update direction in real MuJoCo, then restore it.

Earlier fidelity audits perturbed one action, not the shared policy parameters.
This compares positive/negative whole-policy directions at matched action KL.
It is a diagnostic, not a training method or a policy-selection mechanism.
"""
import argparse
import copy
import json
from pathlib import Path
import time

import torch
import supermimic_race as base
import supermimic_pilot as pilot


class AuditComplete(Exception):
    pass


def direction_scale(measure, target=.05, maximum=128.):
    """Bound both signs using actual nonlinear action distributions."""
    lo, hi = 0., 1.
    value = measure(hi)
    while value < target and hi < maximum:
        lo = hi; hi = min(maximum, 2*hi); value = measure(hi)
    if value < target:
        return hi
    for _ in range(14):
        mid = .5*(lo+hi)
        if measure(mid) <= target:lo = mid
        else:hi = mid
    return lo


def assign_direction(parameters, initial, delta, scale):
    with torch.no_grad():
        for p, start, direction in zip(parameters, initial, delta):
            p.copy_(start+float(scale)*direction)


def calibration_observations(env, agent):
    import mujoco_warp as mjw
    from learning.base_agent import AgentMode
    agent.eval(); agent.set_mode(AgentMode.TEST); base.seed(98117)
    mjw.reset_data(env._engine._solver.mjw_model, env._engine._solver.mjw_data)
    obs, info = agent._reset_envs()
    noise = torch.Generator(device=obs.device).manual_seed(1098117)
    states = []
    with torch.no_grad():
        for tick in range(64):
            if tick % 8 == 0:states.append(obs.clone())
            agent._decide_action(obs, info)  # Keep production phase feedback.
            dist = agent._model.eval_actor(agent._obs_norm.normalize(obs))
            action = agent._a_norm.unnormalize(base.sample_normalized_action(dist, noise))
            obs, _, done, info = env.step(action)
            obs, info = agent._reset_done_envs(done)
    return agent._obs_norm.normalize(torch.cat(states))


def audit(agent, env, output, method, before_model, initial_actor, delta, metrics, preparation_seconds, checkpoint_sha):
    started = time.perf_counter(); output = Path(output)
    parameters = list(agent._model.get_actor_params())
    proposal_norm = float(sum(d.square().sum() for d in delta).sqrt())
    assert proposal_norm > 0 and all(torch.isfinite(d).all() for d in delta)
    agent._model.load_state_dict(before_model)
    print('POLICY_AUDIT_CALIBRATING', method, 'proposal_l2', proposal_norm, flush=True)
    calibration = calibration_observations(env, agent)
    with torch.no_grad():
        distribution = agent._model.eval_actor(calibration)
        original_mean = distribution.mode.clone(); std = distribution.stddev.clone()
        original_phase = agent._model.eval_phase(calibration).clone()
    def distribution_metrics(scale):
        assign_direction(parameters, initial_actor, delta, scale)
        with torch.no_grad():
            mean = agent._model.eval_actor(calibration).mode
            phase = agent._model.eval_phase(calibration)
            return dict(kl=float(.5*((mean-original_mean)/std).square().sum(-1).mean()),
                motor_rms=float((mean-original_mean).square().mean().sqrt()),
                phase_rms=float((phase-original_phase).square().mean().sqrt()))
    def measure(scale):
        value = max(distribution_metrics(scale)['kl'], distribution_metrics(-scale)['kl'])
        if not torch.isfinite(torch.tensor(value)):raise ValueError('Nonfinite proposed action KL')
        return value
    original_step = distribution_metrics(1.)
    scale = direction_scale(measure)
    signed = {str(sign):distribution_metrics(sign*scale) for sign in [-1, 1]}
    assert max(v['kl'] for v in signed.values()) <= .050001
    report = dict(kind='whole_policy_direction_audit', complete=False, method=method,
        gpu=torch.cuda.get_device_name(), checkpoint_sha256=checkpoint_sha, original_proposal_l2=proposal_norm,
        original_step=original_step, scale=scale, calibration=signed,
        calibration_seed=98117, evaluation_seeds=[582701,582702], max_ticks=120,
        target_action_kl=.05, proposal_metrics=metrics, preparation_seconds=preparation_seconds,
        probes=[], interpretation='Temporary parameter perturbations; no selected or promoted policy. Normal episodes truncate at120/300ticks.')
    print('POLICY_AUDIT_DIRECTION', json.dumps({k:v for k,v in report.items() if k not in ['probes','proposal_metrics']}), flush=True)
    try:
        # Predeclare all probes; evaluation results never choose the direction/scale.
        probes = [('baseline', 0.), ('raw_positive', 1.), ('raw_negative', -1.),
                  ('scaled_positive', scale), ('scaled_negative', -scale)]
        for label, factor in probes:
            agent._model.load_state_dict(before_model)
            assign_direction(parameters, initial_actor, delta, factor)
            row = dict(label=label, parameter_scale=factor, evaluations={})
            for noisy in [False, True]:
                mode = 'noisy' if noisy else 'deterministic'
                evaluation = dict(rows=base.evaluate(env, agent, report['evaluation_seeds'], max_ticks=120, exploration=noisy))
                row['evaluations'][mode] = evaluation
                print('POLICY_AUDIT_REAL', json.dumps(dict(probe=label, mode=mode, **pilot.rates(evaluation))), flush=True)
            report['probes'].append(row); base.write(output/'result.json', report)
    finally:
        agent._model.load_state_dict(before_model)
    restored = max(float((v-before_model[k]).abs().max()) for k,v in agent._model.state_dict().items())
    assert restored == 0
    report.update(complete=True, final_model_max_abs_delta=restored, audit_seconds=time.perf_counter()-started)
    base.write(output/'result.json', report)
    print('POLICY_AUDIT_COMPLETE', json.dumps(dict(method=method, audit_seconds=report['audit_seconds'], final_model_max_abs_delta=restored)), flush=True)
    raise AuditComplete()


def run(root, checkpoint, output, method):
    started = time.perf_counter()
    checkpoint_sha = base.hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest()
    output = Path(output).resolve(); output.mkdir(exist_ok=True, parents=True)
    if method == 'model':
        import supermimic_imagined_exact
        original = supermimic_imagined_exact.update
        def wrapped(wm, buffer, ctx, actor_opt, critic_opt, scorer, **kwargs):
            before = copy.deepcopy(ctx.a._model.state_dict())
            parameters = list(ctx.a._model.get_actor_params())
            initial = [p.detach().clone() for p in parameters]
            ao, co = copy.deepcopy(actor_opt.state_dict()), copy.deepcopy(critic_opt.state_dict())
            metrics = original(wm, buffer, ctx, actor_opt, critic_opt, scorer, **kwargs)
            assert not metrics['rejected'], 'Cannot audit a rejected initial proposal'
            delta = [p.detach()-q for p,q in zip(parameters,initial)]
            actor_opt.load_state_dict(ao); critic_opt.load_state_dict(co)
            return audit(ctx.a, ctx.e, output, method, before, initial, delta, metrics, time.perf_counter()-started, checkpoint_sha)
        supermimic_imagined_exact.update = wrapped
    elif method == 'ppo':
        import sys
        sys.path[:0] = [str(Path(root).resolve()/'pipeline'), str(Path(root).resolve()/'MimicKit/mimickit')]
        from omni_policy import OmniPPOAgent
        original = OmniPPOAgent._train_iter
        def wrapped(agent):
            before = copy.deepcopy(agent._model.state_dict())
            parameters = list(agent._model.get_actor_params())
            initial = [p.detach().clone() for p in parameters]
            ao = copy.deepcopy(agent._actor_optimizer._optimizer.state_dict())
            co = copy.deepcopy(agent._critic_optimizer._optimizer.state_dict())
            metrics = {k:float(v) for k,v in original(agent).items()}
            delta = [p.detach()-q for p,q in zip(parameters,initial)]
            agent._actor_optimizer._optimizer.load_state_dict(ao)
            agent._critic_optimizer._optimizer.load_state_dict(co)
            return audit(agent, agent._env, output, method, before, initial, delta, metrics, time.perf_counter()-started, checkpoint_sha)
        OmniPPOAgent._train_iter = wrapped
    else:raise ValueError(method)
    try:
        pilot.run(root, checkpoint, str(output), horizon=32, seconds=420, actor_lr=1.125e-6,
            fast=True, native_ppo=method=='ppo', stochastic_actor=method=='model', noisy_eval=True,
            increment_model=method=='model', hard_imagined_failure=method=='model',
            imagined_exact=method=='model', exact_reward=method=='model', actor_batch=1024,
            warm_model='increments-audited' if method=='model' else None,
            eval_interval=90, training_seed=57361)
    except AuditComplete:
        return
    raise RuntimeError('No actor proposal was reached during bounded preparation')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ['root','checkpoint','output','method']:p.add_argument('--'+name, required=True)
    a = p.parse_args(); run(a.root,a.checkpoint,a.output,a.method)
