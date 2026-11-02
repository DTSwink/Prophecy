import copy,types,unittest
import torch
from supermimic_increments import IncrementWorld,increments,apply_increments,rotation_log
from supermimic_structured import rotation_increment
from supermimic_equivariant import rotate_world


class IncrementTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1);torch.manual_seed(6812)
        kin=types.SimpleNamespace(_parent_indices=[-1]+list(range(14)),
            _local_translation=torch.randn(15,3)*.1,
            _local_rotation=torch.tensor([[0.,0.,0.,1.]]).repeat(15,1),
            get_joint=lambda j:types.SimpleNamespace(get_dof_dim=lambda:3))
        self.w=IncrementWorld(torch.randn(146),torch.rand(146)+.4,5,kin,[2,5,8,11,14])
        raw=torch.randn(20,146)*.2
        root=rotation_increment(torch.randn(20,3))
        raw[:,1:7]=torch.cat((root[:,:,0],root[:,:,2]),-1)
        joints=rotation_increment(torch.randn(20,14,3))
        raw[:,13:97]=torch.cat((joints[:,:,:,0],joints[:,:,:,2]),-1).flatten(1)
        self.raw=self.w.skeleton(raw)

    def test_local_increment_roundtrip_all_physical_components(self):
        delta=torch.randn(20,86)*.12
        nxt=self.w.skeleton(apply_increments(self.raw,delta))
        torch.testing.assert_close(increments(self.raw,nxt),delta,atol=2e-6,rtol=2e-5)
        restored=self.w.skeleton(apply_increments(self.raw,increments(self.raw,nxt)))
        torch.testing.assert_close(restored,nxt,atol=2e-6,rtol=2e-5)

    def test_zero_and_near_pi_rotation_logs_have_finite_gradients(self):
        vectors=torch.tensor([[0.,0.,0.],[1e-7,-2e-7,3e-7],[torch.pi-1e-5,0.,0.],[0.,-torch.pi+1e-5,0.]],dtype=torch.float64,requires_grad=True)
        recovered=rotation_log(rotation_increment(vectors))
        torch.testing.assert_close(recovered,vectors,atol=2e-9,rtol=2e-6)
        recovered.sum().backward();torch.testing.assert_close(vectors.grad,torch.ones_like(vectors),atol=1e-5,rtol=1e-5)

    def test_calibration_excludes_heldout_worlds_and_keeps_policy_scales(self):
        x=(self.raw-self.w.mean)/self.w.std
        y=(self.w.skeleton(apply_increments(self.raw,torch.randn(20,86)*.03))-self.w.mean)/self.w.std
        data=dict(x=x[None].repeat(4,1,1),next_x=y[None].repeat(4,1,1),a=torch.randn(4,20,34))
        buffer=types.SimpleNamespace(data=data,count=4,n=20)
        other=copy.deepcopy(self.w);original=(self.w.mean.clone(),self.w.std.clone())
        stats=self.w.calibrate(buffer);self.assertEqual(stats['training_transitions'],72)
        data['x'][:,::10,:]=1e6;data['next_x'][:,::10,:]=-1e6;data['a'][:,::10,:]=1e6
        other.calibrate(buffer)
        for name in ['input_mean','input_std','delta_mean','delta_std']:
            torch.testing.assert_close(getattr(self.w,name),getattr(other,name),rtol=0,atol=0)
        torch.testing.assert_close(self.w.mean,original[0],rtol=0,atol=0)
        torch.testing.assert_close(self.w.std,original[1],rtol=0,atol=0)

    def test_model_equivariance_and_action_gradient(self):
        torch.nn.init.normal_(self.w.dynamics[-1].weight,std=.002)
        self.w.delta_std.fill_(.03);a=torch.randn(20,34,requires_grad=True)
        yaw=torch.zeros(20,3);yaw[:,2]=torch.linspace(-3,3,20);r=rotation_increment(yaw)
        x=(self.raw-self.w.mean)/self.w.std;rx=(rotate_world(self.raw,r)-self.w.mean)/self.w.std
        pred=self.w.step(x,a)*self.w.std+self.w.mean
        rpred=self.w.step(rx,a)*self.w.std+self.w.mean
        torch.testing.assert_close(rpred,rotate_world(pred,r),atol=2e-6,rtol=2e-5)
        direction=torch.randn_like(a);weight=torch.randn_like(x)
        objective=(self.w.step(x,a)*weight).sum();g=torch.autograd.grad(objective,a)[0]
        eps=.003
        fd=((self.w.step(x,a.detach()+eps*direction)-self.w.step(x,a.detach()-eps*direction))*weight).sum()/(2*eps)
        self.assertGreater(float(g.abs().sum()),.001)
        self.assertAlmostEqual(float((g*direction).sum()),float(fd.detach()),delta=.007)

    def test_exact_target_has_zero_loss_and_finite_gradient(self):
        x=((self.raw-self.w.mean)/self.w.std).detach().requires_grad_(True)
        loss=self.w.state_loss(x,x.detach()).sum()
        self.assertLess(float(loss.detach()),1e-9);loss.backward()
        self.assertTrue(torch.isfinite(x.grad).all())


if __name__=='__main__':unittest.main()
