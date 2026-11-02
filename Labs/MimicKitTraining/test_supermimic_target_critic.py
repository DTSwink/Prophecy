import unittest
import torch
from torch import nn
from supermimic_target_critic import make_target,advance_target


class Model(nn.Module):
    def __init__(self):
        super().__init__();self.critic=nn.Linear(2,1,bias=False);self.actor=nn.Linear(2,2)
        with torch.no_grad():self.critic.weight.copy_(torch.tensor([[2.,3.]]))
    def get_critic_params(self):return list(self.critic.parameters())
    def eval_critic(self,x):return self.critic(x)


class TargetCriticTests(unittest.TestCase):
    def test_frozen_target_keeps_observation_gradient(self):
        model=Model();target=make_target(model);x=torch.tensor([[4.,5.]],requires_grad=True)
        self.assertTrue(torch.equal(model.eval_critic(x),target.eval_critic(x)))
        with torch.no_grad():model.critic.weight.fill_(9)
        target.eval_critic(x).sum().backward()
        self.assertTrue(torch.equal(x.grad,torch.tensor([[2.,3.]])))
        self.assertTrue(all(p.grad is None and not p.requires_grad for p in target.parameters()))
        self.assertFalse(torch.equal(model.critic.weight,target.critic.weight))

    def test_old_target_retention_and_actor_isolation(self):
        online=Model();target=make_target(online);original_actor=target.actor.weight.clone()
        with torch.no_grad():online.critic.weight.copy_(torch.tensor([[12.,23.]]));online.actor.weight.add_(8)
        advance_target(target,online,.4)
        torch.testing.assert_close(target.critic.weight,torch.tensor([[8.,15.]]))
        self.assertTrue(torch.equal(target.actor.weight,original_actor))
        torch.testing.assert_close(online.critic.weight,torch.tensor([[12.,23.]]))


if __name__=='__main__':unittest.main()
