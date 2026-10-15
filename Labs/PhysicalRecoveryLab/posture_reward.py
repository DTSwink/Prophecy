"""Standing-posture shaping, independent of physics and policy observations.

The joint-scaled variant adapts mjlab_playground T1's published joint-angle
tolerances to the PHAT's ball joints. Original reward remains reproducible.
"""
import torch


def joint_tolerances(joints):
    std=[];active=[]
    for joint in joints:
        name=joint['body']
        if name.startswith('thigh'):s=(.08,.08,.12)
        elif name.startswith('calf'):s=(.15,.15,.15)
        elif name.startswith('foot'):s=(.2,.2,.2)
        elif name.startswith(('neck','head')):s=(.15,.15,.15)
        elif name.startswith(('spine','clavicle','upperarm','lowerarm','hand')):s=(.5,.5,.5)
        else:raise ValueError(f'Assign a posture tolerance explicitly for new body {name}')
        std.append(list(s));active.append([mode!=2 for mode in joint['modes']])
    return std,active


def relative_rotation_vector(current,reference):
    # Inverse(reference) * current, canonicalized for double-cover invariance.
    aw=reference[...,:1];av=-reference[...,1:]
    bw=current[...,:1];bv=current[...,1:]
    w=aw*bw-(av*bv).sum(-1,keepdim=True)
    xyz=aw*bv+bw*av+torch.cross(av.expand_as(bv),bv,dim=-1)
    xyz=xyz*torch.where(w<0,-1.,1.)
    n=xyz.norm(dim=-1,keepdim=True)
    return xyz*(2*torch.atan2(n,w.abs())/n.clamp_min(1e-9))


class PostureReward:
    def __init__(self,metadata,device,profile='legacy'):
        if profile not in ('legacy','joint_scaled'):raise ValueError('Unknown posture reward profile')
        self.profile=profile
        self.reference=torch.tensor(metadata['reference_qpos'][7:],device=device).reshape(1,-1,4)
        self.contract={'profile':profile,'upright_gravity_error_threshold':.1,'weight':.5}
        if profile=='joint_scaled':
            std,active=joint_tolerances(metadata['joints'])
            self.std=torch.tensor(std,device=device)
            self.active=torch.tensor(active,device=device)
            self.active_count=sum(sum(row) for row in active)
            self.contract.update(joint_std_rad=std,active_axes=active,
                error='Shortest relative-rotation vector in the reference joint frame; average squared normalized error over controllable axes')

    def __call__(self,joints,gravity_error):
        if self.profile=='legacy':
            similarity=(joints*self.reference).sum(-1).square().clamp(0,1)
            value=torch.exp(-4*(1-similarity).mean(-1))
        else:
            error=relative_rotation_vector(joints,self.reference)/self.std
            value=torch.exp(-(error.square()*self.active).sum(dim=(-1,-2))/self.active_count)
        return value*(gravity_error<self.contract['upright_gravity_error_threshold'])
