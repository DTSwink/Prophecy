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
    def build_net(input_dict, activation):
        size = sum(math.prod(v.shape) for v in input_dict.values())
        layers = []
        for width in (1024, 512, 512):
            layer = torch.nn.Linear(size, width)
            torch.nn.init.zeros_(layer.bias)
            layers.extend((layer, activation()))
            size = width
        return torch.nn.Sequential(*layers), {}
    net_builder.fc_1024_512_512 = types.SimpleNamespace(build_net=build_net)


def circular_phase(phase):
    angle = phase * (2*math.pi)
    return torch.stack((torch.cos(angle), torch.sin(angle)), -1)


class OmniPPOModel(PPOModel):
    def __init__(self, config, env):
        register_network()
        assert config['actor_net'] == config['critic_net'] == 'fc_1024_512_512'
        super().__init__(config, env)
        self._phase_out = torch.nn.Linear(512, 2)
        torch.nn.init.zeros_(self._phase_out.bias)

    def eval_phase(self, obs):
        return self._phase_out(self._actor_layers(obs))

    def get_actor_params(self):
        return super().get_actor_params() + list(self._phase_out.parameters())


class OmniPPOAgent(PPOAgent):
    def _load_params(self, config):
        super()._load_params(config)
        # Must be explicit in the prepared config, never an implicit new reward.
        self._phase_weight = float(config['phase_prediction_weight'])
        assert math.isfinite(self._phase_weight) and self._phase_weight > 0

    def _build_model(self, config):
        self._model = OmniPPOModel(config['model'], self._env)

    def _record_data_pre_step(self, obs, info, action, action_info):
        super()._record_data_pre_step(obs, info, action, action_info)
        # Record BEFORE stepping/resetting, so terminal labels never use a
        # different episode's phase. Uses this world's own motion duration.
        self._exp_buffer.record('next_phase', self._env.next_phase_target())

    def _compute_actor_loss(self, batch):
        info = super()._compute_actor_loss(batch)
        pred = self._model.eval_phase(self._obs_norm.normalize(batch['obs']))
        mse = (pred-batch['next_phase']).square().mean()
        weighted = self._phase_weight*mse
        info['actor_loss'] = info['actor_loss'] + weighted
        info['phase_prediction_mse'] = mse.detach()
        info['phase_prediction_weighted'] = weighted.detach()
        return info
