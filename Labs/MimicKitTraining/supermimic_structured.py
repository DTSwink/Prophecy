"""Constrain imagined observations to the same articulated skeleton as MuJoCo.

This module is used only by isolated experiments. The deployed policy, input
normalization and simulator remain unchanged.
"""
import torch
from torch import nn
from torch.nn import functional as F
from supermimic_race import LearnedWorld


def matrix_from_six(v):
    x=F.normalize(v[..., :3],dim=-1,eps=1e-6)
    z=F.normalize(v[..., 3:]-(v[..., 3:]*x).sum(-1,keepdim=True)*x,dim=-1,eps=1e-6)
    return torch.stack((x,torch.cross(z,x,dim=-1),z),-1)


def matrix_from_quat(q):
    x,y,z,w=q.unbind(-1)
    return torch.stack((1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),
                        2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w),
                        2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)),-1).reshape(*q.shape[:-1],3,3)


class SkeletonProjection(nn.Module):
    def __init__(self,kin,keys):
        super().__init__()
        self.parents=[int(v) for v in kin._parent_indices]
        self.keys=[int(v) for v in keys]
        self.hinges=[]
        for j in range(1,len(self.parents)):
            joint=kin.get_joint(j)
            if joint.get_dof_dim()==1:
                # Exact constants matter: the saved network has large weights
                # on coordinates that are identically zero for these hinges.
                axis=joint.axis.detach().cpu()
                if not torch.allclose(axis.abs(),torch.tensor([0.,0.,1.]),atol=1e-6):
                    raise ValueError('This experiment requires the audited Z-axis hinges')
                self.hinges.append(j-1)
        self.register_buffer('translations',torch.as_tensor(kin._local_translation).clone())
        self.register_buffer('local_matrices',matrix_from_quat(torch.as_tensor(kin._local_rotation)).clone())

    def rotations(self,raw):
        values=raw[:,13:97].reshape(-1,14,6)
        result=[]
        for j in range(14):
            if j in self.hinges:
                xy=F.normalize(values[:,j,:2],dim=-1,eps=1e-6)
                zero=torch.zeros_like(xy[:,:1]);one=torch.ones_like(zero)
                result.append(torch.cat((xy,zero,zero,zero,one),-1))
            else:
                r=matrix_from_six(values[:,j])
                result.append(torch.cat((r[:,:,0],r[:,:,2]),-1))
        return torch.stack(result,1)

    def forward(self,raw):
        root=matrix_from_six(raw[:,1:7]);joints=self.rotations(raw)
        matrices=matrix_from_six(joints)
        positions=[raw.new_zeros((len(raw),3))];rotations=[root]
        for j in range(1,len(self.parents)):
            parent=self.parents[j]
            positions.append(positions[parent]+(rotations[parent]@self.translations[j,:,None]).squeeze(-1))
            rotations.append(rotations[parent]@self.local_matrices[j]@matrices[:,j-1])
        key=torch.stack([positions[j] for j in self.keys],1).flatten(1)
        return torch.cat((raw[:,:1],root[:,:,0],root[:,:,2],raw[:,7:13],
                          joints.flatten(1),raw[:,97:131],key),-1)


class StructuredWorld(LearnedWorld):
    def __init__(self,mean,std,context,kin,keys):
        super().__init__(mean,std,context)
        self.skeleton=SkeletonProjection(kin,keys)

    def step(self,x,a):
        # Residual prediction stays in the original units; FK removes impossible
        # hinge rotations and independent, physically inconsistent key positions.
        raw=(x+self.dynamics(torch.cat((x,a),-1))*.1)*self.std+self.mean
        return (self.skeleton(raw)-self.mean)/self.std


class SimNorm(nn.Module):
    """Grouped softmax from PWM/TD-MPC2, applied to hidden features only."""
    def __init__(self,group=8):
        super().__init__();self.group=group

    def forward(self,x):
        return x.reshape(*x.shape[:-1],-1,self.group).softmax(-1).reshape_as(x)


def regularize_dynamics(dynamics):
    """PWM's contact-example architecture with a physical-state decoder.

    Retain the exact initialized linear layers and residual output. This is a
    regularization ablation, not PWM's full latent-space policy architecture.
    Source: github.com/imgeorgiev/PWM, pedagogical/ball_wall.py and models/mlp.py.
    """
    linears=[m for m in dynamics if isinstance(m,nn.Linear)]
    layers=[]
    for i,linear in enumerate(linears[:-1]):
        layers.extend([linear,nn.LayerNorm(linear.out_features),
                       SimNorm(8) if i==len(linears)-2 else nn.Mish()])
    layers.append(linears[-1])
    return nn.Sequential(*layers)


class RegularizedWorld(StructuredWorld):
    def __init__(self,mean,std,context,kin,keys):
        super().__init__(mean,std,context,kin,keys)
        self.dynamics=regularize_dynamics(self.dynamics)


def rotation_increment(v):
    """SO(3) exponential with finite derivatives at zero angular velocity."""
    x,y,z=v.unbind(-1);zero=torch.zeros_like(x)
    k=torch.stack((zero,-z,y,z,zero,-x,-y,x,zero),-1).reshape(*v.shape[:-1],3,3)
    # torch.sinc implements the removable singularities at zero.
    angle=torch.linalg.vector_norm(v,dim=-1)
    a=torch.sinc(angle/torch.pi)[...,None,None]
    b=(.5*torch.sinc(angle/(2*torch.pi)).square())[...,None,None]
    return torch.eye(3,device=v.device,dtype=v.dtype)+a*k+b*(k@k)


def integrate_observation(raw,delta,velocity_mapping,pelvis_com,dt=1/30.):
    """Velocity integration prior; raw rotations remain six-dimensional.

    Pelvis linear velocity is world COM velocity, angular velocity is world.
    Child DOF velocities map to child-local angular velocities. The residual
    still allows learned position/rotation corrections, including contacts.
    This predicts a control tick; the actual 240 Hz simulator is unchanged.
    """
    velocity=raw[:,7:13]+delta[:,7:13]
    dof=raw[:,97:131]+delta[:,97:131]
    old_root=matrix_from_six(raw[:,1:7])
    root=rotation_increment(velocity[:,3:]*dt)@old_root
    root_six=torch.cat((root[:,:,0],root[:,:,2]),-1)+delta[:,1:7]
    root=matrix_from_six(root_six)
    old_offset=(old_root@pelvis_com[...,None]).squeeze(-1)
    new_offset=(root@pelvis_com[...,None]).squeeze(-1)
    height=raw[:,:1]+velocity[:,2:3]*dt+old_offset[:,2:3]-new_offset[:,2:3]+delta[:,:1]
    local_ang=(dof@velocity_mapping).reshape(-1,14,3)
    joints=matrix_from_six(raw[:,13:97].reshape(-1,14,6))@rotation_increment(local_ang*dt)
    joint_six=torch.cat((joints[:,:,:,0],joints[:,:,:,2]),-1).flatten(1)+delta[:,13:97]
    return torch.cat((height,root_six,velocity,joint_six,dof,raw[:,131:]),-1)


class IntegratedWorld(StructuredWorld):
    """Independent reproduction's integration idea adapted to our ball joints."""
    def __init__(self,mean,std,context,kin,keys,velocity_mapping,pelvis_com):
        super().__init__(mean,std,context,kin,keys)
        self.register_buffer('velocity_mapping',velocity_mapping.detach().clone())
        self.register_buffer('pelvis_com',pelvis_com.detach().clone())

    def step(self,x,a):
        raw=x*self.std+self.mean
        delta=self.dynamics(torch.cat((x,a),-1))*.1*self.std
        integrated=integrate_observation(raw,delta,self.velocity_mapping,self.pelvis_com)
        return (self.skeleton(integrated)-self.mean)/self.std


class GraphModelTrainer:
    """Reuse a fixed eight-step fit graph; keep Adam and checks outside it."""
    def __init__(self,model,optimizer,context):
        self.model=model;self.optimizer=optimizer;self.context=context
        self.graph=None

    def step(self,batch):
        from supermimic_race import model_loss
        if self.graph is None:
            self.static={k:v.clone() for k,v in batch.items()}
            stream=torch.cuda.Stream();stream.wait_stream(torch.cuda.current_stream())
            with torch.cuda.stream(stream):
                for _ in range(3):
                    self.optimizer.zero_grad(set_to_none=True)
                    loss,_=model_loss(self.model,self.static,self.context);loss.backward()
                    nn.utils.clip_grad_norm_(self.model.parameters(),1.)
            torch.cuda.current_stream().wait_stream(stream)
            self.optimizer.zero_grad(set_to_none=True)
            self.graph=torch.cuda.CUDAGraph()
            with torch.cuda.graph(self.graph,stream=stream):
                self.loss,self.metrics=model_loss(self.model,self.static,self.context)
                self.loss.backward()
                self.norm=nn.utils.clip_grad_norm_(self.model.parameters(),1.)
        for k,v in batch.items():self.static[k].copy_(v)
        self.graph.replay()
        if not torch.isfinite(self.norm):raise RuntimeError('Nonfinite graphed model gradient')
        self.optimizer.step()
        return self.loss,self.metrics
