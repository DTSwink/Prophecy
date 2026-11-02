import unittest
import numpy as np
import torch
from scipy.spatial.transform import Rotation
from foot_regularizers import FootRegularizers


class FootTests(unittest.TestCase):
    def measure(self,p,q,h=None,period=20):
        p=torch.tensor(p,dtype=torch.float32);q=torch.tensor(q,dtype=torch.float32)
        h=torch.zeros(len(p),2) if h is None else torch.tensor(h,dtype=torch.float32)
        f=FootRegularizers(1,'cpu');f.reset(torch.tensor([0]),p[:1],q[:1],h[:1]);out=[np.zeros(3)]
        for k in range(1,len(p)):
            out.append(f.append(p[k:k+1],q[k:k+1],h[k:k+1],torch.full((1,2),period))[0].numpy().copy())
        return np.asarray(out),f

    def test_aligned_motion_and_quaternion_sign(self):
        t=np.arange(80)/30;p=np.zeros((80,2,3));p[:,:,0]=t[:,None]
        q=np.repeat(Rotation.from_rotvec(np.c_[0*t,0*t,.7*t]).as_quat()[:,None],2,axis=1)
        out,_=self.measure(p,q);self.assertLess(out.max(),1e-6)
        q[::2]*=-1
        out,_=self.measure(p,q);self.assertLess(out.max(),1e-6)

    def test_back_and_forth_and_rotation_covariance(self):
        t=np.arange(80)/30;p=np.zeros((80,2,3));p[:,:,0]=(.03*np.sin(2*np.pi*5*t))[:,None]
        q=np.repeat(Rotation.from_rotvec(np.c_[0*t,.1*np.sin(2*np.pi*5*t),0*t]).as_quat()[:,None],2,axis=1)
        out,_=self.measure(p,q);self.assertGreater(out[:,1].max(),.01);self.assertGreater(out[:,2].max(),.1)
        rot=Rotation.from_euler('xyz',[.5,-.3,1.]);newp=rot.apply(p.reshape(-1,3)).reshape(p.shape)
        newq=(rot*Rotation.from_quat(q.reshape(-1,4))).as_quat().reshape(q.shape)
        transformed,_=self.measure(newp,newq)
        np.testing.assert_allclose(out,transformed,atol=1e-5,rtol=2e-4)

    def test_cadence_and_no_airborne_reset_event(self):
        p=np.zeros((80,2,3));q=np.zeros((80,2,4));q[:,:,3]=1
        for period in [20,8]:
            h=np.repeat(np.where(np.arange(80)%period<4,.04,0)[:,None],2,axis=1)
            out,_=self.measure(p,q,h)
            if period==20:self.assertEqual(out[:,0].max(),0)
            else:self.assertGreater(out[:,0].max(),.2)
        out,_=self.measure(p,q,np.ones((80,2))*.1);self.assertEqual(out[:,0].max(),0)

    def test_partial_reset(self):
        f=FootRegularizers(2,'cpu');p=torch.zeros(2,2,3);q=torch.zeros(2,2,4);q[:,:,3]=1
        f.reset(torch.arange(2),p,q,torch.zeros(2,2))
        for k in range(20):f.append(p+k%2,q,torch.zeros(2,2),torch.ones(2,2)*20)
        second=[getattr(f,n)[1].clone() for n in f.buffer_names]
        f.reset(torch.tensor([0]),p[:1],q[:1],torch.zeros(1,2))
        for n,v in zip(f.buffer_names,second):torch.testing.assert_close(getattr(f,n)[1],v)
        self.assertEqual(f.ticks[0],0);self.assertEqual(f.raw[0].count_nonzero(),0)


if __name__=='__main__':unittest.main()
