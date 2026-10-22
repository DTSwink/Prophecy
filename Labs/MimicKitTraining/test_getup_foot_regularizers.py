"""Geometry tests independent of training: calf-relative, quaternion sign, units."""
import types
import torch
import numpy as np
from scipy.spatial.transform import Rotation
from getup_foot_regularizers import HELPER

def conj(a):return torch.cat((-a[...,:3],a[...,3:]),-1)
def mul(a,b):
    return torch.cat((a[...,3:]*b[...,:3]+b[...,3:]*a[...,:3]+torch.cross(a[...,:3],b[...,:3],dim=-1),
        a[...,3:]*b[...,3:]-(a[...,:3]*b[...,:3]).sum(-1,keepdim=True)),-1)
scope=dict(torch=torch,q=types.SimpleNamespace(quat_mul=mul,quat_conjugate=conj))
exec(HELPER.replace('@torch.jit.script\n',''),scope)
f=scope['getup_foot_costs']
torch.manual_seed(11)
calf=torch.randn(20,2,4,dtype=torch.float64);calf/=calf.norm(dim=-1,keepdim=True)
idle=torch.randn_like(calf);idle/=idle.norm(dim=-1,keepdim=True)
foot=mul(calf,idle);cmd=torch.zeros(20,6,dtype=torch.float64)
torch.testing.assert_close(f(cmd,foot,calf,idle),torch.zeros(20,2,dtype=torch.float64),atol=1e-25,rtol=1e-7)
turn=torch.tensor([0.,0.,np.sin(np.pi/4),np.cos(np.pi/4)]).expand_as(foot)
rotated=mul(foot,turn);cmd[:,0]=3.
raw=f(cmd,rotated,calf,idle)
torch.testing.assert_close(raw[:,0],torch.full((20,),1.5,dtype=torch.float64))
torch.testing.assert_close(raw[:,1],torch.full((20,),np.pi**2/4,dtype=torch.float64))
torch.testing.assert_close(f(cmd,-rotated,calf,-idle),raw)
global_rot=torch.randn_like(calf);global_rot/=global_rot.norm(dim=-1,keepdim=True)
torch.testing.assert_close(f(cmd,mul(global_rot,rotated),mul(global_rot,calf),idle),raw)
random_foot=torch.randn_like(foot);random_foot/=random_foot.norm(dim=-1,keepdim=True)
expected=(Rotation.from_quat(idle.numpy().reshape(-1,4)).inv()*Rotation.from_quat(calf.numpy().reshape(-1,4)).inv()*Rotation.from_quat(random_foot.numpy().reshape(-1,4))).magnitude().reshape(-1,2)**2
torch.testing.assert_close(f(cmd,random_foot,calf,idle)[:,1],torch.from_numpy(expected.mean(-1)))
print('Foot costs passed: exact zero at idle, 90-degree error, sign and whole-body invariance, physical command units, scipy agreement.')
