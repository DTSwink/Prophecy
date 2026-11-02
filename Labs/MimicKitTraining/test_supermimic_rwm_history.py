"""Boundary and released recurrent-component checks without a GPU."""
from pathlib import Path
import unittest
import torch
from torch import nn
from supermimic_rwm_history import prefix_indices,RecurrentCorrection,com2_error,gradient_coefficient,failure_windows,Windows

SOURCE=Path(__file__).resolve().parents[2]/'Saved/MimicKitSuperMimic/research/rsl-rl-rwm/rsl_rl/modules/architectures'


class Warm(nn.Module):
    def __init__(self):
        super().__init__();self.register_buffer('mean',torch.zeros(146));self.register_buffer('std',torch.ones(146))
        self.register_buffer('input_mean',torch.zeros(180));self.register_buffer('input_std',torch.ones(180))
        self.register_buffer('delta_mean',torch.zeros(86));self.register_buffer('delta_std',torch.ones(86))
        self.dynamics=nn.Linear(180,86);nn.init.zeros_(self.dynamics.weight);nn.init.zeros_(self.dynamics.bias)
        self.skeleton=nn.Identity()
    def features(self,x,a):return torch.cat((x,a),-1)


def state(n):
    x=torch.zeros(n,146);x[:,0]=1;x[:,1]=1;x[:,6]=1
    for i in range(14):x[:,13+i*6]=1;x[:,18+i*6]=1
    return x


class Boundaries(unittest.TestCase):
    def setUp(self):torch.set_num_threads(1);torch.manual_seed(7)

    def test_auxiliary_weight_is_invariant_to_loss_units(self):
        main=torch.tensor([3.,4.]);aux=torch.tensor([20.,0.])
        weight=gradient_coefficient(main,aux,.5)
        self.assertAlmostEqual(float((weight*aux).norm()/main.norm()),.5)
        rescaled=gradient_coefficient(main,aux*100,.5)
        self.assertTrue(torch.allclose(weight*aux,rescaled*aux*100))

    def test_failure_pool_excludes_timeout_reset_and_holdout_leakage(self):
        done=torch.zeros(14,20,dtype=torch.bool);failed=done.clone()
        done[2,1]=True  # timeout preceding the failure
        done[7,1]=True;failed[7,1]=True
        done[6,10]=True;failed[6,10]=True  # validation world
        pool=failure_windows(done,failed)
        self.assertEqual(pool.tolist(),[[start,1] for start in range(3,7)])
        x=state(280).reshape(14,20,146)
        data=dict(x=x,a=torch.zeros(14,20,34),done=done,boundary_failure=failed,
                  world=torch.arange(20).expand(14,20),tick=torch.arange(14)[:,None].expand(14,20))
        windows=Windows(data,Warm());b=windows.sample(40,8,priority_fraction=.5)
        self.assertEqual(windows.priority_samples,20)
        self.assertTrue((b['world'][:, :20]==1).all())
        self.assertTrue((b['tick'][0,:20]>=3).all())
        alive=torch.ones(20,dtype=torch.bool);covered=torch.zeros_like(alive)
        for i in range(8):
            covered|=alive&b['boundary_failure'][i,:20];alive&=~b['done'][i,:20]
        self.assertTrue(covered.all())
        with self.assertRaises(AssertionError):windows.sample(40,8,holdout=True,priority_fraction=.5)

    def test_task_auxiliary_scope_and_gradient_direction(self):
        predicted=torch.tensor([[2.,1.],[100.,100.]],requires_grad=True)
        target=torch.tensor([[1.,0.],[0.,0.]])
        value=com2_error(predicted,target,torch.tensor([2.,0.]),torch.tensor([True,False]))
        self.assertEqual(value.tolist(),[.5,0.])
        value.sum().backward();self.assertTrue(torch.equal(predicted.grad[1],torch.zeros(2)))
        improved=predicted.detach()-.1*predicted.grad
        self.assertLess(float(com2_error(improved,target,torch.tensor([2.,0.]),torch.tensor([True,False])).sum()),float(value.sum().detach()))

    def test_reset_history_and_current_action_alignment(self):
        done=torch.zeros(8,2,dtype=torch.bool);done[2,0]=True;done[4,1]=True
        ids,keep=prefix_indices(done,torch.tensor([5,5]),torch.arange(2),4)
        self.assertEqual(ids[:,0].tolist(),[1,2,3,4])
        self.assertEqual(keep[:,0].tolist(),[False,False,True,True])
        self.assertEqual(keep[:,1].tolist(),[False]*4)
        ids,keep=prefix_indices(done,torch.tensor([0,1]),torch.arange(2),4)
        self.assertFalse(keep[:,0].any());self.assertEqual(int(keep[:,1].sum()),1)
        self.assertEqual(int(ids[-1,1]),0)

    def test_official_recurrence_reset_and_member_isolation(self):
        model=RecurrentCorrection(Warm(),SOURCE)
        for h in model.heads:nn.init.normal_(h.state_mean_layers[-1].weight,std=.002)
        prefix=torch.randn(10,31,180);x=state(10);a=torch.randn(10,34)*.1
        members=torch.arange(10)//2
        model.begin(prefix,members);first=model.step(x,a)
        model.step(first,a)
        model.begin(prefix,members);again=model.step(x,a)
        self.assertTrue(torch.equal(first,again))
        for i in range(10):
            model.begin(prefix[i:i+1],members[i:i+1]);single=model.step(x[i:i+1],a[i:i+1])
            self.assertTrue(torch.allclose(single,first[i:i+1],atol=2e-6))

    def test_actual_gradients_change_predictions_preserve_frozen_base(self):
        warm=Warm();model=RecurrentCorrection(warm,SOURCE);before={k:v.clone() for k,v in warm.state_dict().items()}
        prefix=torch.randn(10,31,180);x=state(10);a=torch.randn(10,34)*.1
        model.begin(prefix);initial=model.step(x,a);self.assertTrue(torch.equal(initial,x))
        opt=torch.optim.Adam([p for p in model.parameters() if p.requires_grad],lr=1e-3)
        target=x.clone();target[:,97:131]=.5
        for _ in range(2):
            model.begin(prefix,torch.arange(10)//2);pred=model.step(x,a)
            loss=(pred-target).square().mean();opt.zero_grad();loss.backward();opt.step()
        model.begin(prefix);after=model.step(x,a)
        self.assertGreater(float((after-initial).abs().max()),0)
        for k,v in warm.state_dict().items():self.assertTrue(torch.equal(v,before[k]))


if __name__=='__main__':unittest.main()
