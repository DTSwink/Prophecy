"""Isolated smooth-policy screen, preserving a pretrained ReLU policy closely.

Public reproductions use SiLU/ELU. We use beta-SiLU to approach the existing
ReLU checkpoint, rather than silently replacing its learned behavior. This is
an architectural ablation, not an exact reproduction of either implementation.
"""
import argparse
import json
import time
from pathlib import Path

import torch
from torch import nn


class BetaSiLU(nn.Module):
    def __init__(self, beta):
        super().__init__()
        self.beta = float(beta)

    def forward(self, x):
        return x * torch.sigmoid(self.beta * x)


def replace_relu(module, beta):
    """Return exact original activation modules; never replace parameters."""
    replaced = []
    for name, child in list(module.named_children()):
        if isinstance(child, nn.ReLU):
            replaced.append((module, name, child))
            setattr(module, name, BetaSiLU(beta))
        else:
            replaced.extend(replace_relu(child, beta))
    return replaced


def restore_relu(replaced):
    for parent, name, original in replaced:
        setattr(parent, name, original)


@torch.no_grad()
def outputs(model, observations):
    means, phases, stds = [], [], []
    for part in observations.split(1024):
        dist = model.eval_actor(part)
        means.append(dist.mode)
        stds.append(dist.stddev)
        phases.append(model.eval_phase(part))
    return tuple(torch.cat(v) for v in (means, phases, stds))


def differences(original, candidate):
    mean, phase, std = original
    new_mean, new_phase, new_std = candidate
    assert torch.equal(std, new_std), 'Exploration must stay unchanged'
    kl = .5 * ((new_mean - mean) / std).square().sum(-1)
    dp = new_phase - phase
    return dict(mean_action_kl=float(kl.mean()), p99_action_kl=float(kl.quantile(.99)),
                phase_rms=float(dp.square().mean().sqrt()), phase_max_abs=float(dp.abs().max()))


def acceptable(row, factor=1.):
    return (row['mean_action_kl'] <= .001 * factor and row['p99_action_kl'] <= .01 * factor
            and row['phase_rms'] <= .002 * factor and row['phase_max_abs'] <= .02 * factor)


def select_beta(model, training, heldout):
    """Select on training observations; heldout can reject, never select beta."""
    original = outputs(model, training)
    held_original = outputs(model, heldout)
    trials = []
    for beta in [1., 2., 4., 8., 16., 32., 64., 128., 256.]:
        replaced = replace_relu(model._actor_layers, beta)
        assert len(replaced) == 3, len(replaced)
        try:
            metrics = differences(original, outputs(model, training))
            trials.append(dict(beta=beta, **metrics))
            if acceptable(metrics):
                validation = differences(held_original, outputs(model, heldout))
                assert acceptable(validation, 2.), 'Heldout preservation check failed: ' + str(validation)
                return beta, dict(trials=trials, heldout=validation, selection='Training-only output closeness; no reward-based selection')
        finally:
            restore_relu(replaced)
    raise RuntimeError('No smooth activation preserved the checkpoint within the declared bounds')


def input_gradient(model, observations, projection):
    x = observations.detach().clone().requires_grad_(True)
    value = torch.cat((model.eval_actor(x).mode, model.eval_phase(x)), -1)
    return torch.autograd.grad((value * projection).sum(), x)[0].detach()


def prepare(env, agent, mode, evaluation_seeds):
    import supermimic_race as base
    from supermimic_policy_step_audit import calibration_observations
    from supermimic_pilot import rates
    assert mode in ('relu', 'smooth')
    started = time.perf_counter()
    model = agent._model
    state = {k: v.detach().clone() for k, v in model.state_dict().items()}
    original_params = [id(p) for p in model.parameters()]
    observations = calibration_observations(env, agent)
    held = (torch.arange(len(observations), device=observations.device) % 1024) % 10 == 0
    beta, report = select_beta(model, observations[~held], observations[held])
    probe = observations[held][:256]
    generator = torch.Generator(device=probe.device).manual_seed(849109)
    projection = torch.randn((len(probe), 36), device=probe.device, generator=generator)
    old_gradient = input_gradient(model, probe, projection)
    replaced = replace_relu(model._actor_layers, beta)
    try:
        new_gradient = input_gradient(model, probe, projection)
    finally:
        restore_relu(replaced)
    report.update(beta=beta, mode=mode, training_observations=int((~held).sum()),
                  heldout_observations=int(held.sum()),
                  input_gradient_relative_change=float((new_gradient-old_gradient).norm()/old_gradient.norm().clamp_min(1e-12)),
                  input_gradient_cosine=float(torch.nn.functional.cosine_similarity(new_gradient.flatten()[None], old_gradient.flatten()[None])),
                  original_evaluation={})
    for noisy in (False, True):
        label = 'noisy' if noisy else 'deterministic'
        evaluation = dict(rows=base.evaluate(env, agent, evaluation_seeds, max_ticks=120, exploration=noisy))
        report['original_evaluation'][label] = rates(evaluation)
    if mode == 'smooth':
        replace_relu(model._actor_layers, beta)
    assert original_params == [id(p) for p in model.parameters()]
    report['parameter_max_abs_delta'] = max(float((v-state[k]).abs().max()) for k, v in model.state_dict().items())
    assert report['parameter_max_abs_delta'] == 0
    report['seconds'] = time.perf_counter()-started
    print('SMOOTH_ACTOR_PREPARED', json.dumps(report), flush=True)
    return report


def verify_start(report, evaluations):
    """Abort before learning if the small output difference disrupts behavior."""
    from supermimic_pilot import rates
    for mode, evaluation in evaluations.items():
        current = rates(evaluation)
        original = report['original_evaluation'][mode]
        for group in ['normal_loco', 'perturbed_loco']:
            assert current[group] <= original[group] + 1.5, ('Initial failure regression', mode, group, current, original)
            assert current[group+'_return'] >= original[group+'_return'] - 2., ('Initial return regression', mode, group, current, original)
    print('SMOOTH_ACTOR_START_VERIFIED', report['mode'], flush=True)


def run(root, checkpoint, output, method):
    import supermimic_pilot as pilot
    assert method in ('relu', 'smooth')
    pilot.run(root, checkpoint, output, horizon=8, seconds=240, actor_lr=1.125e-6,
              fast=True, warm_model='increments-audited', stochastic_actor=True,
              noisy_eval=True, exact_reward=True, actor_batch=1024, eval_interval=90,
              training_seed=849108, imagined_exact=True, hard_imagined_failure=True,
              increment_model=True, actor_activation=method, evaluation_seeds=[984107, 984108])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ['root', 'checkpoint', 'output', 'method']:
        parser.add_argument('--'+name, required=True)
    run(**vars(parser.parse_args()))
