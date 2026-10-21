"""Opt-in omni actor/critic and supervised next-tick phase head.

No launcher. The two phase outputs are not motor actions and receive no
exploration noise. The environment's clock, not this head, advances reference.
"""
import math
import types
import torch
from learning.nets import net_builder
from learning.ppo_model import PPOModel
from learning.ppo_agent import PPOAgent


def register_network():
    def build_net(input_dict, activation, widths=(1024, 512, 512)):
        size = sum(math.prod(v.shape) for v in input_dict.values())
        layers = []
        for width in widths:
            layer = torch.nn.Linear(size, width)
            torch.nn.init.zeros_(layer.bias)
            layers.extend((layer, activation()))
            size = width
        return torch.nn.Sequential(*layers), {}
    net_builder.fc_1024_512_512 = types.SimpleNamespace(build_net=build_net)
    net_builder.fc_1024_1024_512 = types.SimpleNamespace(
        build_net=lambda inputs, activation: build_net(inputs, activation, (1024, 1024, 512)))


def circular_phase(phase):
    angle = phase * (2*math.pi)
    return torch.stack((torch.cos(angle), torch.sin(angle)), -1)


def phase_supervision_mse(prediction, batch):
    error = (prediction-batch['next_phase']).square().mean(dim=-1)
    # Keep the original batch denominator: removing autoregressive supervision
    # must not increase the weight of the remaining clock-supervised rows.
    mask = batch.get('phase_supervision')
    return error.mean() if mask is None else (error*mask).mean()


class OmniPPOModel(PPOModel):
    def __init__(self, config, env):
        register_network()
        assert config['actor_net'] == config['critic_net']
        assert config['actor_net'] in ('fc_1024_512_512', 'fc_1024_1024_512')
        super().__init__(config, env)
        self._unit_phase = bool(config.get('auto_phase_unit_output', False))
        self._phase_out = torch.nn.Linear(512, 2)
        torch.nn.init.zeros_(self._phase_out.bias)

    def eval_phase(self, obs):
        value = self._phase_out(self._actor_layers(obs))
        return torch.nn.functional.normalize(value, dim=-1, eps=1e-6) if self._unit_phase else value

    def get_actor_params(self):
        return super().get_actor_params() + list(self._phase_out.parameters())


class OmniPPOAgent(PPOAgent):
    def _load_params(self, config):
        super()._load_params(config)
        # Must be explicit in the prepared config, never an implicit new reward.
        self._phase_weight = float(config['auto_phase_weight'] if 'auto_phase_weight' in config else config['phase_prediction_weight'])
        assert math.isfinite(self._phase_weight) and self._phase_weight > 0
        self._actor_kl_limit = float(config.get('actor_kl_limit', 0.))
        self._actor_kl_probe_size = int(config.get('actor_kl_probe_size', 2048))
        self._actor_min_lr = float(config.get('actor_min_learning_rate', 1e-7))

    def _update_actor(self, batch_size, num_steps):
        if self._actor_kl_limit > 0:
            from kl_guard import guarded_actor_update
            return guarded_actor_update(self, batch_size, num_steps)
        return super()._update_actor(batch_size, num_steps)

    def _build_model(self, config):
        success = getattr(self._env, '_perturb_cfg', {})
        if success.get('getup_success_value', 0.):
            if not math.isclose(float(success['getup_success_discount']), float(config['discount'])):
                raise ValueError('Get-up success accounting must use the PPO discount')
            if self._env.get_reward_succ() != 0:
                raise ValueError('Get-up success bonus requires zero terminal bootstrap')
        self._model = OmniPPOModel(config['model'], self._env)

    def _decide_action(self, obs, info):
        action, action_info = super()._decide_action(obs, info)
        if getattr(self._env, '_recovery_ready', False):
            ids = getattr(self._env, '_phase_feedback_ids', self._env._recovery_ids)
            with torch.no_grad():
                prediction = self._model.eval_phase(self._obs_norm.normalize(obs[ids]))
            self._env.queue_phase_prediction(prediction)
        return action, action_info

    def _compute_action_bound_loss(self, norm_a_dist):
        # A resumed policy retains its original action units and physical noise.
        # The legal normalized interval can therefore be wider than [-1, 1].
        # Use the loaded normalizer, not an assumed scale or a pre-load cache.
        low = self._a_norm.normalize(self._env._action_bound_low)
        high = self._a_norm.normalize(self._env._action_bound_high)
        below = torch.clamp_max(norm_a_dist.mode - low, 0.)
        above = torch.clamp_min(norm_a_dist.mode - high, 0.)
        return (below.square() + above.square()).sum(dim=-1)

    def _record_data_pre_step(self, obs, info, action, action_info):
        super()._record_data_pre_step(obs, info, action, action_info)
        # Record BEFORE stepping/resetting, so terminal labels never use a
        # different episode's phase. Uses this world's own motion duration.
        self._exp_buffer.record('next_phase', self._env.next_phase_target())
        if hasattr(self._env, '_phase_supervision_mask'):
            self._exp_buffer.record('phase_supervision', self._env._phase_supervision_mask)

    def _compute_actor_loss(self, batch):
        # All training actions are stochastic in the current configuration.
        # Share the trunk with auto-phase and avoid CUDA boolean compaction.
        # Retain the reference path for exploration schedules with mixed masks.
        if self._get_exp_prob() == 1.0:
            return shared_actor_loss(self, batch)
        return self._compute_actor_loss_reference(batch)

    def _compute_actor_loss_reference(self, batch):
        info = super()._compute_actor_loss(batch)
        pred = self._model.eval_phase(self._obs_norm.normalize(batch['obs']))
        mse = phase_supervision_mse(pred, batch)
        weighted = self._phase_weight*mse
        info['actor_loss'] = info['actor_loss'] + weighted
        info['phase_prediction_mse'] = mse.detach()
        info['phase_prediction_weighted'] = weighted.detach()
        # Upstream logger accumulates/scales each key in place. Aliasing these
        # with the phase_prediction keys corrupts the reported averages.
        info['auto_phase_mse'] = mse.detach().clone()
        info['auto_phase_weighted'] = weighted.detach().clone()
        return info


def shared_actor_loss(agent, batch):
    obs = agent._obs_norm.normalize(batch['obs'])
    hidden = agent._model._actor_layers(obs)
    dist = agent._model._action_dist(hidden)
    logp = dist.log_prob(agent._a_norm.normalize(batch['action']))
    ratio = torch.exp(logp - batch['a_logp'])
    mask = (batch['rand_action_mask'] == 1.).to(ratio.dtype)
    def mean(value):
        return (value * mask).sum() / mask.sum()
    loss = -mean(torch.minimum(batch['adv'] * ratio,
        batch['adv'] * ratio.clamp(1-agent._ppo_clip_ratio, 1+agent._ppo_clip_ratio)))
    info = dict(actor_loss=loss,
        clip_frac=mean((abs(ratio-1) > agent._ppo_clip_ratio).float()).detach(),
        imp_ratio=mean(ratio).detach())
    if agent._action_bound_weight:
        bound = mean(agent._compute_action_bound_loss(dist))
        info['action_bound_loss'] = bound.detach()
        loss = loss + agent._action_bound_weight * bound
    if agent._action_entropy_weight:
        entropy = mean(dist.entropy())
        info['action_entropy'] = entropy.detach()
        loss = loss - agent._action_entropy_weight * entropy
    if agent._action_reg_weight:
        reg = mean(dist.param_reg())
        info['action_reg_loss'] = reg.detach()
        loss = loss + agent._action_reg_weight * reg
    phase = agent._model._phase_out(hidden)
    if agent._model._unit_phase:
        phase = torch.nn.functional.normalize(phase, dim=-1, eps=1e-6)
    mse = phase_supervision_mse(phase, batch)
    weighted = agent._phase_weight * mse
    info.update(actor_loss=loss+weighted, phase_prediction_mse=mse.detach(),
        phase_prediction_weighted=weighted.detach(), auto_phase_mse=mse.detach().clone(),
        auto_phase_weighted=weighted.detach().clone())
    return info
