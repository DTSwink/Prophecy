"""Exercise production PPO methods on tensor fixtures without loading a simulator."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
import numpy as np
import torch
torch.set_num_threads(1)

ROOT=Path(__file__).resolve().parents[2]
UPSTREAM=ROOT/'Saved/MimicKit/vendor/MimicKit/mimickit/learning'
if not UPSTREAM.exists(): UPSTREAM=Path('/workspace/mimickit_trial/MimicKit/mimickit/learning')
scope={'torch':torch,'np':np}
exec(compile((UPSTREAM/'distribution_gaussian_diag.py').read_text(),'distribution_gaussian_diag.py','exec'),scope)
exec(compile((UPSTREAM/'experience_buffer.py').read_text(),'experience_buffer.py','exec'),scope)

class FixturePPO(torch.nn.Module):
    def __init__(self,config,env,device):
        super().__init__()
        self._device=device
        self._action_bound_weight=self._action_entropy_weight=self._action_reg_weight=0
        self._ppo_clip_ratio=.2
        self._obs_norm=self._a_norm=SimpleNamespace(normalize=lambda x:x,unnormalize=lambda x:x)
        self.mean=torch.nn.Parameter(torch.zeros(512,28))
        self._model=SimpleNamespace(eval_actor=lambda obs:scope['DistributionGaussianDiag'](
            self.mean[obs[:,0].long()],torch.full((len(obs),28),np.log(.05))))
        self._mode=0
        self._exp_buffer=scope['ExperienceBuffer'](2,512,'cpu')
    def get_num_envs(self): return 512
    def _get_exp_prob(self): return 1.
    def _record_data_pre_step(self,obs,info,action,action_info):
        for name,value in dict(obs=obs,action=action,**{k:action_info[k] for k in ['a_logp','rand_action_mask']}).items():
            self._exp_buffer.record(name,value)

scope.update(PPOAgent=FixturePPO,AgentMode=SimpleNamespace(TRAIN=0))
tree=ast.parse(Path(__file__).with_name('agent_noise.py').read_text())
tree.body=[n for n in tree.body if isinstance(n,ast.ClassDef)]
exec(compile(tree,'agent_noise.py','exec'),scope)
Class=scope['PerAgentNoisePPO']
ppo=ast.parse((UPSTREAM/'ppo_agent.py').read_text())
method=next(n for n in next(n for n in ppo.body if isinstance(n,ast.ClassDef)).body
            if isinstance(n,ast.FunctionDef) and n.name=='_compute_actor_loss')
exec(compile(ast.Module(body=[method],type_ignores=[]),'upstream_actor_loss','exec'),scope)

class Tests(unittest.TestCase):
    def make(self):
        return Class(dict(model=dict(actor_std_type='FIXED',action_std=.05),per_agent_noise_seed=20261014),None,'cpu')
    def test_uniform_persistent_assignment_and_rng(self):
        state=torch.get_rng_state()
        a=self.make()
        # Fixture buffer shuffling itself consumes RNG; compare identical construction.
        torch.set_rng_state(state);b=self.make()
        self.assertTrue(torch.equal(a.agent_action_logstd,b.agent_action_logstd))
        s=a.agent_action_logstd.exp()
        self.assertTrue(bool(((s>0)&(s<.05)).all()))
        self.assertLess(abs(float(s.mean())-.025),.002)
        self.assertEqual(len(s.unique()),512)
        b.agent_action_logstd.zero_();b.load_state_dict(a.state_dict())
        self.assertTrue(torch.equal(a.agent_action_logstd,b.agent_action_logstd))
    def batch(self,a):
        obs=torch.arange(512).float()[:,None]
        for i in range(2):
            action,info=a._decide_action(obs,{})
            a._record_data_pre_step(obs,{},action,info)
            a._exp_buffer.record('adv',torch.linspace(-1,1,512))
            a._exp_buffer.inc()
        return a._exp_buffer.sample(777)
    def test_shuffled_likelihood_matches_sampling_and_reference(self):
        a=self.make();batch=self.batch(a)
        self.assertTrue(torch.equal(batch['action_logstd'],a.agent_action_logstd[batch['obs'][:,0].long()]))
        loss=a._compute_actor_loss(batch)
        self.assertAlmostEqual(float(loss['imp_ratio']),1.,places=6)
        with torch.no_grad():a.mean.add_(1e-5)
        current=a._compute_actor_loss(batch)['actor_loss']
        mean=a.mean[batch['obs'][:,0].long()]
        dist=torch.distributions.Normal(mean,batch['action_logstd'].exp())
        ratio=(dist.log_prob(batch['action']).sum(-1)-batch['a_logp']).exp()
        expected=-torch.minimum(batch['adv']*ratio,batch['adv']*ratio.clamp(.8,1.2)).mean()
        torch.testing.assert_close(current,expected,atol=2e-6,rtol=2e-5)
        current.backward();self.assertTrue(bool(torch.isfinite(a.mean.grad).all()))
    def test_constant_sigma_is_stock_ppo_loss_and_gradient(self):
        a=self.make();a.agent_action_logstd.fill_(np.log(.05));batch=self.batch(a)
        with torch.no_grad():a.mean.add_(.002)
        new=a._compute_actor_loss(batch)['actor_loss'];new.backward();gradient=a.mean.grad.clone();a.mean.grad=None
        old=scope['_compute_actor_loss'](a,batch)['actor_loss'];old.backward()
        torch.testing.assert_close(new,old,atol=1e-6,rtol=1e-5)
        torch.testing.assert_close(gradient,a.mean.grad,atol=1e-6,rtol=2e-5)

if __name__=='__main__':unittest.main()
