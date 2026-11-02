import unittest
import torch
from torch import nn
from supermimic_transfer_head import constrain_actor,feature_delta


class Actor(nn.Module):
    def __init__(self):
        super().__init__();self._actor_layers=nn.Sequential(nn.Linear(3,5),nn.Tanh());self._action_dist=nn.Linear(5,2);self._phase_out=nn.Linear(5,2)
        self._action_dist.register_parameter('fixed_std',nn.Parameter(torch.ones(2),requires_grad=False))
    def get_actor_params(self):return list(self.parameters())
    def forward(self,x):
        h=self._actor_layers(x);return self._action_dist(h)+self._phase_out(h)


class Checks(unittest.TestCase):
    def test_frozen_features_keep_state_gradients_and_train_both_heads(self):
        torch.manual_seed(31);model=Actor();x=torch.randn(4,3,requires_grad=True)
        output=model(x).clone();before=constrain_actor(model,'heads')
        self.assertTrue(torch.equal(model(x),output))
        opt=torch.optim.Adam(model.get_actor_params(),lr=.01)
        model(x).square().mean().backward();self.assertGreater(float(x.grad.norm()),0)
        self.assertTrue(all(p.grad is None for p in model._actor_layers.parameters()))
        self.assertTrue(all(p.grad is not None for module in [model._action_dist,model._phase_out] for p in module.parameters() if p.requires_grad))
        self.assertFalse(model._action_dist.fixed_std.requires_grad)
        opt.step();self.assertEqual(feature_delta(model,before),0)
        self.assertFalse(torch.equal(model(x),output))

    def test_control_features_really_update(self):
        torch.manual_seed(32);model=Actor();before=constrain_actor(model,'full')
        opt=torch.optim.Adam(model.parameters(),lr=.01);model(torch.randn(4,3)).square().mean().backward();opt.step()
        self.assertGreater(feature_delta(model,before),0)


if __name__=='__main__':unittest.main()
