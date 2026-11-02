import unittest
import torch
from torch import nn
from supermimic_planning_student import ResidualStudent,install,preserve_random_state,audit_student_fit
import random
import numpy as np


class Dist:
    def __init__(self,mean,logstd):self.mode=mean;self.logstd=logstd


class Model(nn.Module):
    def __init__(self):
        super().__init__();self.actor=nn.Linear(154,34);self.phase=nn.Linear(154,2)
    def eval_actor(self,x):return Dist(self.actor(x),torch.full((len(x),34),-2.6))
    def eval_phase(self,x):return self.phase(x)


class Checks(unittest.TestCase):
    def test_full_split_audit_distinguishes_fit_from_zero_baseline(self):
        x=torch.arange(21,dtype=torch.float32).reshape(7,3)/10
        class Zero(nn.Module):
            def forward(self,x):return torch.zeros_like(x)
        data={'teacher_valid':(x,x/2),'anchor_valid':(x,torch.zeros_like(x))}
        zero=audit_student_fit(Zero(),data,chunk_size=2)
        self.assertAlmostEqual(zero['teacher_valid']['explained_target_energy'],0)
        self.assertIsNone(zero['anchor_valid']['explained_target_energy'])
        self.assertEqual(zero['anchor_valid']['mse'],0)
        class Exact(nn.Module):
            def forward(self,x):return x/2
        fitted=audit_student_fit(Exact(),data,chunk_size=2)
        self.assertEqual(fitted['teacher_valid']['mse'],0)
        self.assertEqual(fitted['teacher_valid']['explained_target_energy'],1)
        self.assertAlmostEqual(fitted['anchor_valid']['mse'],float((x/2).square().mean()),places=6)
        self.assertEqual(fitted['teacher_valid']['samples'],7)

    def test_evaluation_does_not_change_next_training_draw(self):
        def seed():torch.manual_seed(91);random.seed(92);np.random.seed(93)
        def draw():return (torch.randn(3),random.random(),np.random.rand(3))
        seed();expected=draw();seed()
        with preserve_random_state():
            torch.manual_seed(800);random.seed(801);np.random.seed(802)
            draw();draw()
        actual=draw()
        self.assertTrue(torch.equal(actual[0],expected[0]))
        self.assertEqual(actual[1],expected[1]);np.testing.assert_array_equal(actual[2],expected[2])

    def test_zero_initialization_and_preserved_phase_distribution(self):
        torch.manual_seed(5);m=Model();x=torch.randn(8,154)
        before=m.eval_actor(x);phase=m.eval_phase(x).detach().clone()
        student=ResidualStudent();install(m,student);m._planning_student_enabled=True
        self.assertTrue(torch.equal(before.mode,m.eval_actor(x).mode))
        with torch.no_grad():student.net[-1].bias.fill_(1.)
        self.assertTrue(torch.allclose(m.eval_actor(x).mode-before.mode,student(x)))
        self.assertTrue(torch.equal(before.logstd,m.eval_actor(x).logstd))
        self.assertTrue(torch.equal(phase,m.eval_phase(x)))
        m._planning_student_enabled=False
        self.assertTrue(torch.equal(before.mode,m.eval_actor(x).mode))

    def test_only_residual_learns_and_is_bounded(self):
        torch.manual_seed(6);m=Model()
        for p in m.parameters():p.requires_grad_(False)
        old={k:v.clone() for k,v in m.state_dict().items()}
        s=ResidualStudent();install(m,s);m._planning_student_enabled=True
        opt=torch.optim.Adam(s.parameters(),lr=.01);x=torch.randn(32,154)
        first=s(x).detach().clone();loss=(s(x)-.1).square().mean()
        opt.zero_grad();loss.backward();opt.step()
        self.assertFalse(torch.equal(first,s(x)))
        self.assertTrue(torch.all(s(x).abs()<=.225))
        self.assertTrue(all(torch.equal(v,m.state_dict()[k]) for k,v in old.items()))


if __name__=='__main__':unittest.main()
