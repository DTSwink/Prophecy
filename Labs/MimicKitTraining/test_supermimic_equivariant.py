import types
import unittest
import torch
from supermimic_equivariant import EquivariantWorld,rotate_world,heading_matrix
from supermimic_structured import StructuredWorld


class EquivarianceTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1);torch.manual_seed(90518)
        kin=types.SimpleNamespace(_parent_indices=[-1]+list(range(14)),
            _local_translation=torch.randn(15,3)*.1,
            _local_rotation=torch.tensor([[0.,0.,0.,1.]]).repeat(15,1),
            get_joint=lambda j:types.SimpleNamespace(get_dof_dim=lambda:3))
        self.w=EquivariantWorld(torch.zeros(146),torch.ones(146),5,kin,[2,5,8,11,14])
        torch.nn.init.normal_(self.w.dynamics[-1].weight,std=.01)
        raw=torch.randn(5,146)*.2
        raw[:,1:7]=torch.tensor([1.,0.,0.,0.,0.,1.])
        raw[:,13:97]=torch.tensor([1.,0.,0.,0.,0.,1.]).repeat(14)
        self.raw=self.w.skeleton(raw)
        angle=torch.tensor([-.3,.9,3.1,-2.3,1.5]);c=angle.cos();s=angle.sin();z=angle*0;o=z+1
        self.rotation=torch.stack((c,-s,z,s,c,z,z,z,o),-1).reshape(5,3,3)

    def test_rotation_roundtrip_preserves_local_joint_pose_and_velocity(self):
        rotated=rotate_world(self.raw,self.rotation)
        torch.testing.assert_close(rotated[:,13:131],self.raw[:,13:131])
        torch.testing.assert_close(rotate_world(rotated,self.rotation.transpose(-1,-2)),self.raw,atol=1e-6,rtol=1e-6)

    def test_nontrivial_learned_dynamics_commute_with_world_yaw(self):
        action=torch.randn(5,34)
        predicted=self.w.step(self.raw,action)
        rotated=self.w.step(rotate_world(self.raw,self.rotation),action)
        torch.testing.assert_close(rotated,rotate_world(predicted,self.rotation),atol=2e-6,rtol=2e-5)
        # A generic world-frame MLP with exactly these weights fails the same test.
        base=StructuredWorld.step
        error=(base(self.w,rotate_world(self.raw,self.rotation),action)-
               rotate_world(base(self.w,self.raw,action),self.rotation)).abs().max()
        self.assertGreater(float(error.detach()),.001)

    def test_action_derivative_matches_finite_difference(self):
        action=torch.randn(5,34,requires_grad=True);direction=torch.randn_like(action)
        value=self.w.step(self.raw,action).square().sum()
        grad=torch.autograd.grad(value,action)[0]
        eps=.002
        plus=self.w.step(self.raw,action.detach()+eps*direction).square().sum()
        minus=self.w.step(self.raw,action.detach()-eps*direction).square().sum()
        self.assertTrue(torch.isfinite(grad).all());self.assertGreater(float(grad.abs().sum()),0.)
        self.assertAlmostEqual(float((grad*direction).sum()),float(((plus-minus)/(2*eps)).detach()),delta=.015)

    def test_vertical_heading_fallback_has_finite_gradient(self):
        raw=self.raw.clone();raw[:,1:7]=torch.tensor([0.,0.,1.,1.,0.,0.]);raw.requires_grad_(True)
        heading_matrix(raw).sum().backward()
        self.assertTrue(torch.isfinite(raw.grad).all())


if __name__=='__main__':unittest.main()
