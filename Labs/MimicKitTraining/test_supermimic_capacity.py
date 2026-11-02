import copy
import unittest
import torch
from torch import nn
from supermimic_capacity import widen_dynamics


class CapacityTest(unittest.TestCase):
    def test_predictions_input_gradients_and_trainable_replicas(self):
        torch.manual_seed(81);layers=[];width=11
        for _ in range(3):
            layers.extend([nn.Linear(width,17),nn.LayerNorm(17),nn.SiLU()]);width=17
        layers.append(nn.Linear(width,5));original=nn.Sequential(*layers).double()
        before=copy.deepcopy(original.state_dict())
        expanded=widen_dynamics(original)
        x=torch.randn(32,11,dtype=torch.float64,requires_grad=True)
        a,b=original(x),expanded(x)
        torch.testing.assert_close(a,b,rtol=1e-12,atol=1e-12)
        ga=torch.autograd.grad(a.square().sum(),x)[0]
        gb=torch.autograd.grad(b.square().sum(),x)[0]
        torch.testing.assert_close(ga,gb,rtol=1e-11,atol=1e-11)
        for key,value in original.state_dict().items():
            torch.testing.assert_close(value,before[key],rtol=0,atol=0)
        # Same initial function must not trap the added units in exact symmetry.
        target=torch.randn(32,5,dtype=torch.float64)
        opt=torch.optim.Adam(expanded.parameters(),lr=.0002)
        loss=(expanded(x.detach())-target).square().mean()
        opt.zero_grad();loss.backward()
        self.assertGreater(float((expanded[0].weight.grad[:17]-expanded[0].weight.grad[17:]).abs().max()),1e-8)
        opt.step()
        self.assertGreater(float((expanded[0].weight[:17]-expanded[0].weight[17:]).detach().abs().max()),1e-8)
        self.assertTrue(all(torch.isfinite(p).all() for p in expanded.parameters()))


if __name__=='__main__':unittest.main()
