"""Numerical invariants for the isolated privileged imagined critic."""
import types
import unittest
import torch
from supermimic_value_context import install, features, evaluate, parameters


class Model(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self._critic_layers = torch.nn.Sequential(torch.nn.Linear(4, 16), torch.nn.Tanh())
        self._critic_out = torch.nn.Linear(16, 1)
        self.actor = torch.nn.Linear(4, 2)

    def eval_actor(self, obs):
        return types.SimpleNamespace(mode=self.actor(obs))

    def eval_critic(self, obs):
        return self._critic_out(self._critic_layers(obs))

    def get_critic_params(self):
        return list(self._critic_layers.parameters()) + list(self._critic_out.parameters())


class ContextTests(unittest.TestCase):
    def test_install_preserves_values_actor_and_rng(self):
        model=Model();obs=torch.randn(8,4)
        before=model.eval_critic(obs).detach().clone();actor=model.eval_actor(obs).mode.detach().clone()
        rng=torch.random.get_rng_state().clone();meta=install(model)
        torch.testing.assert_close(rng,torch.random.get_rng_state(),rtol=0,atol=0)
        context=torch.randn(8,3)
        torch.testing.assert_close(evaluate(model,obs,context),before,rtol=0,atol=0)
        torch.testing.assert_close(model.eval_actor(obs).mode,actor,rtol=0,atol=0)
        self.assertEqual(meta['initial_value_max_error'],0.)
        self.assertIs(parameters(model)[-1],model._loco_critic_context.weight)
        with self.assertRaises(RuntimeError):evaluate(model,obs)

    def test_context_matches_reward_schedule_and_keeps_next_age(self):
        env=types.SimpleNamespace(_mse_only=False,_perturb_cfg=dict(ae_ticks=30,blend_ticks=30))
        age=torch.tensor([[29.,59.,119.],[30.,60.,120.],[31.,61.,121.]])
        pert=torch.tensor([[True,True,False]]).expand(3,-1)
        c=features(env,age,pert)
        torch.testing.assert_close(c[...,1],age/120.)
        torch.testing.assert_close(c[...,2],torch.tensor([[0.,29/30,1.],[0.,1.,1.],[1/30,1.,1.]]))

    def test_same_observation_distinct_context_can_fit_distinct_values(self):
        torch.manual_seed(41);model=Model();install(model)
        obs=torch.zeros(32,4);context=torch.zeros(32,3);context[16:,1:]=1
        target=evaluate(model,obs,context).detach().clone();target[16:]+=.5
        # Fit only the new projection: verify context can carry the distinction,
        # while both the actor and every pre-existing critic parameter are fixed.
        old=[p.detach().clone() for p in model.get_critic_params()]
        opt=torch.optim.Adam([model._loco_critic_context.weight],lr=.04)
        for _ in range(150):
            loss=(evaluate(model,obs,context)-target).square().mean()
            opt.zero_grad();loss.backward();opt.step()
        self.assertGreater(float((evaluate(model,obs,context)[16:].mean()-evaluate(model,obs,context)[:16].mean()).detach()),.45)
        self.assertLess(float(loss.detach()),.005)
        for p,q in zip(model.get_critic_params(),old):torch.testing.assert_close(p,q,rtol=0,atol=0)
        self.assertGreater(float(model._loco_critic_context.weight.detach().norm()),0)


if __name__=='__main__':unittest.main()
