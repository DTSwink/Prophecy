"""Experimental independently normalized, body-local dynamics increments.

Representation/normalization follow the ideas in zita-ch/supermimic_vibed's
networks.py and train.py. This is an adaptation to our ball-joint character,
COM velocities and first/THIRD-column rotation encoding, not its G1 interface.
Policy normalization, task scoring and real physics remain unchanged.
"""
import torch
from torch import nn
from supermimic_structured import StructuredWorld,matrix_from_six,rotation_increment
from supermimic_equivariant import heading_matrix,rotate_world


def rotation_log(r):
    """Principal rotation vector, finite at identity and stable near pi.

    Choose the quaternion component with largest magnitude to avoid dividing
    by a small component. All unselected branches also stay finite for AD.
    """
    a,b,c=r[...,0,0],r[...,1,1],r[...,2,2]
    squared=torch.stack((1+a+b+c,1+a-b-c,1-a+b-c,1-a-b+c),-1)
    roots=squared.clamp_min(1e-12).sqrt()
    x=r[...,2,1]-r[...,1,2];y=r[...,0,2]-r[...,2,0];z=r[...,1,0]-r[...,0,1]
    xy=r[...,0,1]+r[...,1,0];xz=r[...,0,2]+r[...,2,0];yz=r[...,1,2]+r[...,2,1]
    candidates=torch.stack((torch.stack((squared[...,0],x,y,z),-1),
                            torch.stack((x,squared[...,1],xy,xz),-1),
                            torch.stack((y,xy,squared[...,2],yz),-1),
                            torch.stack((z,xz,yz,squared[...,3]),-1)),-2)/(2*roots[...,None])
    ids=roots.argmax(-1)[...,None,None].expand(*roots.shape[:-1],1,4)
    q=candidates.gather(-2,ids).squeeze(-2)
    q=torch.nn.functional.normalize(q,dim=-1)
    q=torch.where(q[...,:1]<0,-q,q)
    n=q[...,1:].square().sum(-1,keepdim=True).clamp_min(1e-12).sqrt()
    angle=2*torch.atan2(n,q[...,:1])
    scale=torch.where(n>1e-5,angle/n,2/q[...,:1].clamp_min(1e-6))
    return q[...,1:]*scale


def increments(raw,nxt):
    root=matrix_from_six(raw[:,1:7]);rt=root.transpose(-1,-2)
    joints=matrix_from_six(raw[:,13:97].reshape(-1,14,6))
    nj=matrix_from_six(nxt[:,13:97].reshape(-1,14,6))
    return torch.cat((nxt[:,:1]-raw[:,:1],
        rotation_log(rt@matrix_from_six(nxt[:,1:7])),
        (rt@(nxt[:,7:10]-raw[:,7:10])[...,None]).squeeze(-1),
        (rt@(nxt[:,10:13]-raw[:,10:13])[...,None]).squeeze(-1),
        rotation_log(joints.transpose(-1,-2)@nj).flatten(1),
        nxt[:,97:131]-raw[:,97:131]),-1)


def apply_increments(raw,delta):
    root=matrix_from_six(raw[:,1:7]);nr=root@rotation_increment(delta[:,1:4])
    joints=matrix_from_six(raw[:,13:97].reshape(-1,14,6))
    nj=joints@rotation_increment(delta[:,10:52].reshape(-1,14,3))
    v=raw[:,7:10]+(root@delta[:,4:7,None]).squeeze(-1)
    w=raw[:,10:13]+(root@delta[:,7:10,None]).squeeze(-1)
    return torch.cat((raw[:,:1]+delta[:,:1],nr[:,:,0],nr[:,:,2],v,w,
                      torch.cat((nj[:,:,:,0],nj[:,:,:,2]),-1).flatten(1),
                      raw[:,97:131]+delta[:,52:],raw[:,131:]),-1)


class IncrementWorld(StructuredWorld):
    def __init__(self,mean,std,context,kin,keys):
        super().__init__(mean,std,context,kin,keys)
        layers=[];width=180
        for _ in range(3):
            layers.extend((nn.Linear(width,1024),nn.LayerNorm(1024),nn.SiLU()));width=1024
        layers.append(nn.Linear(width,86));self.dynamics=nn.Sequential(*layers)
        nn.init.zeros_(self.dynamics[-1].weight);nn.init.zeros_(self.dynamics[-1].bias)
        self.register_buffer('input_mean',torch.zeros(180));self.register_buffer('input_std',torch.ones(180))
        self.register_buffer('delta_mean',torch.zeros(86));self.register_buffer('delta_std',torch.ones(86))
        self.register_buffer('norm_count',torch.zeros((),dtype=torch.int64))
        floors=[.003]+[.005]*3+[.02]*3+[.05]*3+[.003]*42+[.05]*34
        self.register_buffer('error_floor',torch.tensor(floors))

    def features(self,raw,a):
        canonical=rotate_world(raw,heading_matrix(raw).transpose(-1,-2))
        return torch.cat((canonical,a),-1)

    @torch.no_grad()
    def calibrate(self,buffer):
        """Fixed training-world statistics; held-out worlds never enter them."""
        data=buffer.data;xs=data['x'][:buffer.count].flatten(0,1)
        ys=data['next_x'][:buffer.count].flatten(0,1);actions=data['a'][:buffer.count].flatten(0,1)
        sums=[torch.zeros(d,device=xs.device,dtype=torch.float64) for d in (180,86)]
        squares=[v.clone() for v in sums];count=0
        for start in range(0,len(xs),4096):
            stop=min(start+4096,len(xs))
            keep=(torch.arange(start,stop,device=xs.device)%buffer.n)%10!=0
            x=xs[start:stop][keep]*self.std+self.mean;y=ys[start:stop][keep]*self.std+self.mean
            values=(self.features(x,actions[start:stop][keep]),increments(x,y))
            for i,v in enumerate(values):
                vd=v.double();sums[i]+=vd.sum(0);squares[i]+=vd.square().sum(0)
            count+=len(x)
        assert count>0
        for i,(mean,std,epsilon) in enumerate(((self.input_mean,self.input_std,.01),(self.delta_mean,self.delta_std,.0001))):
            m=sums[i]/count;variance=(squares[i]/count-m.square()).clamp_min(0)
            mean.copy_(m);std.copy_((variance+epsilon**2).sqrt())
        self.norm_count.fill_(count)
        assert all(torch.isfinite(v).all() for v in (self.input_mean,self.input_std,self.delta_mean,self.delta_std))
        return dict(training_transitions=count,heldout_worlds_excluded=True,
                    input_std_min=float(self.input_std.min()),input_std_max=float(self.input_std.max()),
                    output_std_min=float(self.delta_std.min()),output_std_max=float(self.delta_std.max()),
                    output_std=self.delta_std.cpu().tolist(),output_mean=self.delta_mean.cpu().tolist(),
                    policy_normalization_unchanged=True,normalization_frozen_after_calibration=True)

    def step(self,x,a):
        raw=x*self.std+self.mean
        features=(self.features(raw,a)-self.input_mean)/self.input_std
        delta=self.dynamics(features)*self.delta_std+self.delta_mean
        return (self.skeleton(apply_increments(raw,delta))-self.mean)/self.std

    def state_loss(self,predicted,target):
        p=predicted*self.std+self.mean;t=target*self.std+self.mean
        error=increments(t,p)
        return (error/torch.maximum(self.delta_std,self.error_floor)).square().mean(-1)
