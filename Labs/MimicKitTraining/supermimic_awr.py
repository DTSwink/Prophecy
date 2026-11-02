"""Isolated native MimicKit AWR objective with the existing omni phase contract.

Use the pinned upstream implementation, rather than another Q/model-gradient
adapter. This first screen retains the production rollout, optimizer and guard;
it does not claim the original paper's long-lived off-policy replay recipe.
"""
import hashlib
import inspect
import math
from collections import deque
import torch


PINNED_SOURCE_SHA256 = '71a7233a87a0df690fbcadafd4781f0de83dd3be07bd1c84913458c4b1f4f3e9'


def merged_rollouts(rollouts, device):
    """Keep time segments in separate columns, never join unrelated episodes."""
    from learning.experience_buffer import ExperienceBuffer
    first=rollouts[0]['obs']
    result=ExperienceBuffer(first.shape[0],sum(r['obs'].shape[1] for r in rollouts),device)
    for key in rollouts[0]:
        result.set_data(key,torch.cat([r[key] for r in rollouts],dim=1))
    result._total_samples=result.get_capacity()
    return result


def install(agent, temperature=1., weight_clip=20., replay_rollouts=1):
    from learning.awr_agent import AWRAgent
    from omni_policy import phase_supervision_mse
    module = inspect.getmodule(AWRAgent)
    loader = module.__loader__
    source = loader.get_data(module.__file__)
    digest = hashlib.sha256(source).hexdigest()
    assert digest == PINNED_SOURCE_SHA256, 'Unexpected upstream AWR source'
    assert temperature > 0 and weight_clip >= 1
    assert replay_rollouts in (1,4)
    agent._awr_temp = temperature
    agent._a_weight_clip = weight_clip
    original_build = agent._build_train_data
    collection_buffer=agent._exp_buffer
    snapshots=deque(maxlen=replay_rollouts)
    training_buffer=None
    agent._awr_audit = {}
    first = True

    def build():
        nonlocal first,training_buffer
        # Verify once on a real rollout: changing the actor objective must not
        # change critic targets, including -100 failures and timeout bootstrap.
        previous_targets = None
        if first:
            original_build()
            previous_targets = agent._exp_buffer.get_data('tar_val').clone()
        if replay_rollouts>1:
            snapshots.append({k:v.detach().clone() for k,v in collection_buffer._buffers.items()
                if k not in ('a_weight','adv','tar_val')})
            training_buffer=merged_rollouts(snapshots,collection_buffer._device)
        else:
            training_buffer=collection_buffer
        agent._exp_buffer=training_buffer
        try:
            info = AWRAgent._build_train_data(agent)
        finally:
            agent._exp_buffer=collection_buffer
        weights = training_buffer.get_data('a_weight')
        assert bool(torch.isfinite(weights).all())
        if first:
            target_error = float((previous_targets-training_buffer.get_data('tar_val')).abs().max())
            assert target_error == 0., 'AWR changed existing critic targets'
            agent._awr_audit['critic_target_max_error'] = target_error
            first = False
        agent._awr_audit.update(weight_mean=float(weights.mean()),
            weight_max=float(weights.max()),
            replay_rollouts=len(snapshots) if replay_rollouts>1 else 1,
            replay_samples=training_buffer.get_sample_count(),
            weight_effective_sample_fraction=float(weights.sum().square() /
                (weights.numel()*weights.square().sum().clamp_min(1e-12))))
        return info

    def update_with_replay():
        # Retain the original number of minibatch updates per NEW rollout.
        # Increasing the data retained must not silently multiply GPU work.
        agent.train()
        n=agent.get_num_envs()
        fresh=collection_buffer.get_sample_count()
        cb=math.ceil(agent._critic_batch_size*n)
        ab=math.ceil(agent._actor_batch_size*n)
        cs=math.ceil(fresh/cb)*agent._critic_epochs
        ac=math.ceil(fresh/ab)*agent._actor_epochs
        assert training_buffer is not None
        agent._exp_buffer=training_buffer
        try:
            critic_info=agent._update_critic(cb,cs)
            # Original AWR implementation recalculates returns/advantages after
            # fitting V, before weighted regression. All labels stay detached.
            refreshed=AWRAgent._build_train_data(agent)
            weights=training_buffer.get_data('a_weight')
            agent._awr_audit.update(weight_mean=float(weights.mean()),
                weight_max=float(weights.max()),
                weight_effective_sample_fraction=float(weights.sum().square()/
                    (weights.numel()*weights.square().sum().clamp_min(1e-12))),
                refreshed_after_critic=1.,actor_steps_requested=ac,critic_steps_requested=cs)
            actor_info=agent._update_actor(ab,ac)
            return {**critic_info,**actor_info,**refreshed}
        finally:
            agent._exp_buffer=collection_buffer

    def loss(batch):
        info = AWRAgent._compute_actor_loss(agent, batch)
        prediction = agent._model.eval_phase(agent._obs_norm.normalize(batch['obs']))
        phase = phase_supervision_mse(prediction, batch)
        weighted = agent._phase_weight*phase
        info['actor_loss'] = info['actor_loss']+weighted
        info['phase_prediction_mse'] = phase.detach()
        info['phase_prediction_weighted'] = weighted.detach()
        return info

    agent._build_train_data = build
    agent._compute_actor_loss = loss
    if replay_rollouts>1:
        agent._update_model=update_with_replay
    return dict(source='MimicKit/mimickit/learning/awr_agent.py', source_sha256=digest,
        temperature=temperature, weight_clip=weight_clip,
        actor_lr=agent._actor_optimizer._optimizer.param_groups[0]['lr'],
        phase_supervision_unchanged=True, exploration_unchanged=True,
        critic_targets_unchanged=True, kl_guard_unchanged=True,
        replay_rollouts=replay_rollouts,refresh_weights_after_critic=replay_rollouts>1,
        replay_scope='current rollout' if replay_rollouts==1 else
            'FIFO last4 independent32tick segments; same update count per new rollout')
