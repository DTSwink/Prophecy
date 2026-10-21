"""Optional, isolated locomotion sweep: expose reward schedule to the critic.

Call install(agent) AFTER checkpoint restore and before the first rollout.
The actor and environment observation remain unchanged. New critic weights start
at zero, so installation preserves every old value prediction and Adam moment.
No production launcher imports this module automatically.
"""
import types

import torch


CONTEXT_FIELDS = ('perturbed', 'elapsed_ticks_div_120', 'tracking_mix')


def context(env):
    """Current state, sampled before resetting any ended episode."""
    return torch.stack((env._perturbed_rows.to(env._time_buf.dtype),
                        env._time_buf * .25, env._tracking_mix), dim=-1)


def critic_value(model, obs, critic_context=None):
    # The original first layer, bias and all subsequent layers stay intact.
    # For ordinary stand-alone value inspection, context defaults to zero.
    value = model._critic_layers[0](obs)
    if critic_context is not None:
        value = value + model._loco_critic_context(critic_context)
    for layer in list(model._critic_layers.children())[1:]:
        value = layer(value)
    return model._critic_out(value)


def build_train_data(agent):
    """Pinned upstream TD-lambda path, with matching current/next context."""
    from envs.base_env import DoneFlags
    from learning import rl_util
    from util import mp_util, torch_util

    agent.eval()
    buffer = agent._exp_buffer
    obs, next_obs, reward, done, random_mask = [buffer.get_data(name) for name in
        ('obs', 'next_obs', 'reward', 'done', 'rand_action_mask')]
    inputs = dict(obs=agent._obs_norm.normalize(next_obs),
                  critic_context=buffer.get_data('next_critic_context'))
    next_values = torch_util.eval_minibatch(agent._model.eval_critic, inputs,
        agent._critic_eval_batch_size).squeeze(-1).detach()
    next_values[done == DoneFlags.SUCC.value] = agent._compute_succ_val()
    next_values[done == DoneFlags.FAIL.value] = agent._compute_fail_val()
    targets = rl_util.compute_td_lambda_return(reward, next_values, done,
        agent._discount, agent._td_lambda)
    inputs = dict(obs=agent._obs_norm.normalize(obs),
                  critic_context=buffer.get_data('critic_context'))
    values = torch_util.eval_minibatch(agent._model.eval_critic, inputs,
        agent._critic_eval_batch_size).squeeze(-1).detach()
    advantage = targets - values
    random_advantage = advantage.flatten()[(random_mask == 1.).flatten()]
    mean, std = mp_util.calc_mean_std(random_advantage)
    normalized = ((advantage - mean) / std.clamp_min(1e-5)).clamp(
        -agent._norm_adv_clip, agent._norm_adv_clip)
    buffer.set_data('tar_val', targets)
    buffer.set_data('adv', normalized)
    return dict(adv_mean=mean, adv_std=std)


def critic_loss(agent, batch):
    value = agent._model.eval_critic(agent._obs_norm.normalize(batch['obs']),
        batch['critic_context']).squeeze(-1)
    return dict(critic_loss=(batch['tar_val'] - value).square().mean())


def install(agent):
    """Augment a restored disposable learner; preserve its 154-input actor."""
    model = agent._model
    if hasattr(model, '_loco_critic_context'):
        raise RuntimeError('Privileged locomotion critic already installed')
    if agent._exp_buffer.get_total_samples() != 0:
        raise RuntimeError('Install before recording the first rollout')
    first = model._critic_layers[0]
    if not isinstance(first, torch.nn.Linear):
        raise TypeError('Expected the pinned feed-forward critic')
    # Do not consume the policy/environment RNG while building this zero layer.
    weight = torch.zeros((first.out_features, len(CONTEXT_FIELDS)),
                         dtype=first.weight.dtype, device=first.weight.device)
    layer = torch.nn.Linear.__new__(torch.nn.Linear)
    torch.nn.Module.__init__(layer)
    layer.in_features, layer.out_features = len(CONTEXT_FIELDS), first.out_features
    layer.weight = torch.nn.Parameter(weight)
    layer.register_parameter('bias', None)
    model.add_module('_loco_critic_context', layer)
    model.eval_critic = types.MethodType(critic_value, model)

    wrapper = agent._critic_optimizer
    optimizer = wrapper._optimizer
    group = {key: value for key, value in optimizer.param_groups[0].items()
             if key != 'params'}
    group['params'] = [layer.weight]
    optimizer.add_param_group(group)
    wrapper._param_list.append(layer.weight)

    original_pre = agent._record_data_pre_step
    original_post = agent._record_data_post_step

    def pre(obs, info, action, action_info):
        original_pre(obs, info, action, action_info)
        agent._exp_buffer.record('critic_context', context(agent._env))

    def post(next_obs, reward, done, next_info):
        original_post(next_obs, reward, done, next_info)
        # BaseAgent records post-step data before calling _reset_done_envs.
        agent._exp_buffer.record('next_critic_context', context(agent._env))

    agent._record_data_pre_step = pre
    agent._record_data_post_step = post
    agent._build_train_data = types.MethodType(build_train_data, agent)
    agent._compute_critic_loss = types.MethodType(critic_loss, agent)
    return dict(fields=list(CONTEXT_FIELDS), actor_unchanged=True,
                existing_value_predictions_preserved=True,
                existing_optimizer_state_preserved=True,
                new_parameters=weight.numel())
