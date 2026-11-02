"""Disposable policy dispatch candidates with unchanged math and sampling order."""
from contextlib import contextmanager
import torch
from learning.base_agent import AgentMode

def shared_action(self, obs, info):
    norm_obs = self._obs_norm.normalize(obs)
    hidden = self._model._actor_layers(norm_obs)
    norm_action_dist = self._model._action_dist(hidden)
    if self._mode == AgentMode.TRAIN:
        norm_a_rand = norm_action_dist.sample()
        norm_a_mode = norm_action_dist.mode
        exp_prob = torch.full([norm_a_rand.shape[0], 1], self._get_exp_prob(), device=self._device, dtype=torch.float)
        rand_action_mask = torch.bernoulli(exp_prob)
        norm_a = torch.where(rand_action_mask == 1., norm_a_rand, norm_a_mode)
        rand_action_mask = rand_action_mask.squeeze(-1)
    elif self._mode == AgentMode.TEST:
        norm_a = norm_action_dist.mode
        rand_action_mask = torch.zeros_like(norm_a[..., 0])
    else:
        raise AssertionError('Unsupported agent mode')
    norm_a_logp = norm_action_dist.log_prob(norm_a)
    action = self._a_norm.unnormalize(norm_a.detach())
    action_info = dict(a_logp=norm_a_logp.detach(), rand_action_mask=rand_action_mask)
    if getattr(self._env, '_recovery_ready', False):
        ids = getattr(self._env, '_phase_feedback_ids', self._env._recovery_ids)
        with torch.no_grad():
            prediction = self._model._phase_out(hidden[ids])
            if self._model._unit_phase:
                prediction = torch.nn.functional.normalize(prediction, dim=-1, eps=1e-6)
        self._env.queue_phase_prediction(prediction)
    return action, action_info

class SelectedMinibatches:
    def __init__(self, agent):
        self.a=agent
        self.originals={k:getattr(agent,'_update_'+k) for k in ['actor','critic']}
    @contextmanager
    def select(self, keys):
        b=self.a._exp_buffer
        saved=b._flat_buffers
        b._flat_buffers={k:v for k,v in saved.items() if k in keys}
        try:
            yield
        finally:
            b._flat_buffers=saved
    def actor(self,*args,**kwargs):
        with self.select({'obs','action','a_logp','adv','rand_action_mask','next_phase','phase_supervision'}):
            return self.originals['actor'](*args,**kwargs)
    def critic(self,*args,**kwargs):
        with self.select({'obs','tar_val'}):
            return self.originals['critic'](*args,**kwargs)
    def install(self):
        for k in self.originals: setattr(self.a,'_update_'+k,getattr(self,k))
    def uninstall(self):
        for k,v in self.originals.items(): setattr(self.a,'_update_'+k,v)
