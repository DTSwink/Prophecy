"""Optional critic task-clock inputs for isolated imagined-policy experiments.

Reuse the prior PPO sweep's zero-initialized first-layer projection. The policy
and saved checkpoint remain unchanged; this does not expose AE history and is
not a claim that the resulting critic sees a complete Markov state.
"""
import torch
from loco_privileged_critic import CONTEXT_FIELDS, critic_value


def parameters(model):
    params = list(model.get_critic_params())
    if hasattr(model, '_loco_critic_context'):
        params.append(model._loco_critic_context.weight)
    return params


def features(env, age, perturbed):
    mix = (torch.ones_like(age) if env._mse_only else
           ((age - env._perturb_cfg['ae_ticks']) /
            env._perturb_cfg['blend_ticks']).clamp(0, 1))
    mix = torch.where(perturbed, mix, torch.ones_like(mix))
    return torch.stack((perturbed.to(age.dtype), age / 120., mix), -1)


def evaluate(model, obs, context=None):
    if hasattr(model, '_loco_critic_context'):
        if context is None:
            raise RuntimeError('An augmented imagined critic requires explicit matching context')
        return critic_value(model, obs, context)
    return model.eval_critic(obs)


def install(model):
    assert not hasattr(model, '_loco_critic_context')
    first = model._critic_layers[0]
    assert isinstance(first, torch.nn.Linear)
    # Construct without random initialization: paired arms retain the same RNG.
    layer = torch.nn.Linear.__new__(torch.nn.Linear)
    torch.nn.Module.__init__(layer)
    layer.in_features, layer.out_features = len(CONTEXT_FIELDS), first.out_features
    layer.weight = torch.nn.Parameter(first.weight.new_zeros((first.out_features, len(CONTEXT_FIELDS))))
    layer.register_parameter('bias', None)
    probe = torch.linspace(-1, 1, first.in_features, device=first.weight.device,
                           dtype=first.weight.dtype)[None].repeat(3, 1)
    with torch.no_grad():
        original_value = model.eval_critic(probe).clone()
        original_actor = model.eval_actor(probe).mode.clone()
        model.add_module('_loco_critic_context', layer)
        context = probe.new_tensor([[1, 10/120, 0], [1, 45/120, .5], [0, 75/120, 1]])
        error = float((evaluate(model, probe, context) - original_value).abs().max())
        actor_error = float((model.eval_actor(probe).mode - original_actor).abs().max())
    assert error == 0 and actor_error == 0
    return dict(fields=list(CONTEXT_FIELDS), initial_value_max_error=error,
                initial_actor_max_error=actor_error, new_parameters=layer.weight.numel(),
                three_frame_AE_history_included=False)
