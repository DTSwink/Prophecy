"""Detached auxiliary inputs preserve head training and remove only dynamics feedback."""
import copy
from types import SimpleNamespace
import unittest
import torch
from torch import nn
from supermimic_race import model_loss


class AuxiliaryFitTest(unittest.TestCase):
    def test_forward_equal_and_dynamics_gradient_is_state_only(self):
        class Model(nn.Module):
            def __init__(self):
                super().__init__();self.dynamics=nn.Linear(1,1,bias=False)
                self.reward=nn.Linear(3,1);self.terminal=nn.Linear(3,1)
            def step(self,x,a):return self.dynamics(x)+a
            def heads(self,h,c):return self.reward(h.flatten(1)).sigmoid().flatten(),self.terminal(h.flatten(1)).flatten()
        torch.manual_seed(347);a=Model();b=copy.deepcopy(a);b.detach_auxiliary_inputs=True
        batch=dict(x=torch.ones(3,2,1),next_x=torch.ones(3,2,1)*.2,a=torch.ones(3,2,1)*.1,
            history=torch.ones(3,2,3,1),motion=torch.zeros(3,2,dtype=torch.long),next_phase=torch.zeros(3,2,2),
            age=torch.zeros(3,2),pert=torch.ones(3,2,dtype=torch.bool),base_reward=torch.zeros(3,2),
            fail=torch.zeros(3,2,dtype=torch.bool),done=torch.zeros(3,2,dtype=torch.bool))
        ctx=SimpleNamespace(head_context=lambda *args:None)
        loss_a,metrics_a=model_loss(a,batch,ctx);loss_b,metrics_b=model_loss(b,batch,ctx)
        self.assertEqual(float(loss_a.detach()),float(loss_b.detach()))
        expected=torch.autograd.grad(metrics_b['state_nse'],b.dynamics.weight,retain_graph=True)[0]
        loss_a.backward();loss_b.backward()
        torch.testing.assert_close(b.dynamics.weight.grad,expected)
        self.assertGreater(float((a.dynamics.weight.grad-b.dynamics.weight.grad).abs().max()),1e-5)
        for left,right in [(a.reward,b.reward),(a.terminal,b.terminal)]:
            self.assertGreater(float(right.weight.grad.norm()),0)
            torch.testing.assert_close(left.weight.grad,right.weight.grad)


if __name__=='__main__':unittest.main()
