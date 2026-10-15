"""Fixed per-world Gaussian exploration, with matching shuffled PPO likelihoods."""
import torch
from learning.ppo_agent import PPOAgent
from learning.base_agent import AgentMode
from learning.distribution_gaussian_diag import DistributionGaussianDiag


class PerAgentNoisePPO(PPOAgent):
    def __init__(self, config, env, device):
        super().__init__(config, env, device)
        assert config['model']['actor_std_type'] == 'FIXED'
        assert self._action_bound_weight == self._action_entropy_weight == self._action_reg_weight == 0
        # Separate generator leaves policy initialization and simulation RNG unchanged.
        generator = torch.Generator().manual_seed(config['per_agent_noise_seed'])
        sigma = torch.rand((self.get_num_envs(), 1), generator=generator)
        # Zero has measure zero in a continuous uniform distribution. Reject only
        # the exact PRNG endpoint; no minimum noise or truncation is introduced.
        while bool((sigma == 0).any()):
            zero = sigma == 0
            sigma[zero] = torch.rand((int(zero.sum()),), generator=generator)
        sigma *= config['model']['action_std']
        self.register_buffer('agent_action_logstd', sigma.log().to(device))

    def _decide_action(self, obs, info):
        if self._mode != AgentMode.TRAIN:
            return super()._decide_action(obs, info)
        original = self._model.eval_actor(self._obs_norm.normalize(obs))
        dist = DistributionGaussianDiag(original.mean, self.agent_action_logstd.expand_as(original.mean))
        random_action = dist.sample()
        mask = torch.bernoulli(torch.full_like(random_action[:, :1], self._get_exp_prob()))
        action = torch.where(mask == 1, random_action, dist.mode)
        return self._a_norm.unnormalize(action.detach()), {
            'a_logp': dist.log_prob(action).detach(), 'rand_action_mask': mask.squeeze(-1),
            'action_logstd': self.agent_action_logstd,
        }

    def _record_data_pre_step(self, obs, info, action, action_info):
        super()._record_data_pre_step(obs, info, action, action_info)
        self._exp_buffer.record('action_logstd', action_info['action_logstd'])

    def _compute_actor_loss(self, batch):
        # Stock PPO clipped objective; only the distribution's std differs.
        mask = batch['rand_action_mask'] == 1
        obs = self._obs_norm.normalize(batch['obs'])[mask]
        action = self._a_norm.normalize(batch['action'])[mask]
        original = self._model.eval_actor(obs)
        dist = DistributionGaussianDiag(original.mean, batch['action_logstd'][mask].expand_as(original.mean))
        ratio = (dist.log_prob(action) - batch['a_logp'][mask]).exp()
        advantage = batch['adv'][mask]
        loss = -torch.minimum(advantage * ratio,
                              advantage * ratio.clamp(1 - self._ppo_clip_ratio, 1 + self._ppo_clip_ratio)).mean()
        return {'actor_loss': loss,
                'clip_frac': ((ratio - 1).abs() > self._ppo_clip_ratio).float().mean().detach(),
                'imp_ratio': ratio.mean().detach()}
