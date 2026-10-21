"""Optional sweep diagnostics; observe PPO advantages without changing them.

Reuse the current-state critic predictions already computed by _build_train_data.
No extra model forward, RNG use, optimizer step, or per-minibatch host sync.
Install after any privileged-critic helper, before the first training update.
"""
import math

import torch


def statistics(normalized, random_action_mask, perturbed_rows):
    """Return device scalars; threshold comparisons describe pre-clamp values."""
    eligible = (random_action_mask == 1.).to(normalized.dtype)
    absolute = normalized.abs()
    total = eligible.sum().clamp_min(1.)
    absolute_total = (absolute * eligible).sum().clamp_min(1e-12)
    cohorts = dict(normal=~perturbed_rows, perturbed=perturbed_rows)
    result = {'adv_unclipped_abs_max': (absolute * eligible).amax()}
    for limit in (4, 10):
        exceeded = (absolute > limit).to(normalized.dtype)
        result[f'adv_clip_fraction_at{limit}'] = (exceeded * eligible).sum() / total
        result[f'adv_removed_l1_fraction_at{limit}'] = (
            (absolute - limit).clamp_min(0.) * eligible).sum() / absolute_total
        for name, mask in cohorts.items():
            weight = eligible * mask.to(normalized.dtype)
            result[f'adv_clip_fraction_at{limit}_{name}'] = (
                exceeded * weight).sum() / weight.sum().clamp_min(1.)
    return result


def install(agent):
    """Wrap the pinned PPO/privileged-critic return builder, diagnostics only."""
    if getattr(agent, '_loco_advantage_diagnostics', False):
        raise RuntimeError('Advantage diagnostics already installed')
    original = agent._build_train_data

    def build():
        predictions = []
        model = agent._model
        original_evaluate = model.eval_critic

        def evaluate(*args, **kwargs):
            value = original_evaluate(*args, **kwargs)
            predictions.append(value.detach())
            return value

        model.eval_critic = evaluate
        try:
            info = original()
        finally:
            model.eval_critic = original_evaluate

        buffer = agent._exp_buffer
        targets = buffer.get_data('tar_val')
        size = agent._critic_eval_batch_size
        chunks = math.ceil(targets.shape[0] / size) if size > 0 else 1
        # Pinned builders evaluate next states first, then current states.
        # A future builder with a different order needs an explicit adaptation.
        if len(predictions) != 2 * chunks:
            raise RuntimeError('Unexpected critic-call layout in sweep diagnostics')
        current = predictions[chunks:]
        values = (current[0] if len(current) == 1 else torch.cat(current, dim=0)).squeeze(-1)
        with torch.no_grad():
            normalized = ((targets - values) - info['adv_mean']) / info['adv_std'].clamp_min(1e-5)
            diagnostic = statistics(normalized, buffer.get_data('rand_action_mask'),
                                    agent._env._perturbed_rows)
        # Do not alter the stored advantages or targets, even for unselected rows.
        return {**info, **diagnostic}

    agent._build_train_data = build
    agent._loco_advantage_diagnostics = True
    return dict(thresholds=[4, 10], pre_clipping=True,
                extra_critic_forwards=0, modifies_training_data=False)
