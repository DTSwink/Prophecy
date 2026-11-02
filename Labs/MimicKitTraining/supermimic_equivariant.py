"""Heading-equivariant dynamics ablation; policy/scoring stay in world space.

Motivated by the invariant features in the public SuperMimic reproductions.
Keep our model width, initialization, losses and output scales for a controlled
representation test. This does not implement their independent increment norms.
"""
import torch
from supermimic_structured import StructuredWorld,matrix_from_six


def heading_matrix(raw):
    root=matrix_from_six(raw[:,1:7]);x=root[:,0,0];y=root[:,1,0]
    usable=x.square()+y.square()>1e-8
    angle=torch.atan2(torch.where(usable,y,torch.zeros_like(y)),
                      torch.where(usable,x,torch.ones_like(x)))
    c=angle.cos();s=angle.sin();z=torch.zeros_like(c);o=torch.ones_like(c)
    return torch.stack((c,-s,z,s,c,z,z,z,o),-1).reshape(-1,3,3)


def rotate_world(raw,rotation):
    def rotate(v):return (rotation@v[...,None]).squeeze(-1)
    root=rotation@matrix_from_six(raw[:,1:7])
    keys=(rotation[:,None]@raw[:,131:].reshape(-1,5,3,1)).squeeze(-1)
    return torch.cat((raw[:,:1],root[:,:,0],root[:,:,2],rotate(raw[:,7:10]),
                      rotate(raw[:,10:13]),raw[:,13:131],keys.flatten(1)),-1)


class EquivariantWorld(StructuredWorld):
    def step(self,x,a):
        raw=x*self.std+self.mean
        heading=heading_matrix(raw)
        canonical=rotate_world(raw,heading.transpose(-1,-2))
        features=(canonical-self.mean)/self.std
        delta=self.dynamics(torch.cat((features,a),-1))*.1*self.std
        predicted=self.skeleton(canonical+delta)
        return (rotate_world(predicted,heading)-self.mean)/self.std
