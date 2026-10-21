"""Shared training/runtime schema: three poses in the first flat-pelvis frame."""
import torch
from torch import nn

SCHEMA = 'robotic_crawl_ae1_fixed_pelvis_v1'
DIM = 405
HZ = 30


def encode(positions, rotations, ground_height=0.0):
    """(...,3,15,3), (...,3,15,3,3) -> (...,405), metres and world rotations.

    Body 0 is pelvis. Origins remove ONLY initial pelvis XY and ground height.
    Heading uses pelvis local -X, with projected +Y fallback near vertical.
    Rotations are first two matrix columns, column-major (six values per body).
    """
    anchor = rotations[..., 0, 0, :, :]
    forward = -anchor[..., :2, 0]
    side = anchor[..., :2, 1]
    alternate = torch.stack((-side[..., 1], side[..., 0]), -1)
    forward = torch.where((torch.sum(forward**2, -1) < .25**2)[..., None], alternate, forward)
    yaw = torch.atan2(forward[..., 1], forward[..., 0])
    c, s = torch.cos(yaw), torch.sin(yaw)
    zero, one = torch.zeros_like(c), torch.ones_like(c)
    inverse = torch.stack((c,s,zero,-s,c,zero,zero,zero,one), -1).reshape(*yaw.shape,3,3)
    origin = positions[..., 0, 0, :].clone()
    origin[..., 2] = ground_height
    local_p = torch.matmul(inverse[...,None,None,:,:], (positions-origin[...,None,None,:]).unsqueeze(-1)).squeeze(-1)
    local_r = inverse[...,None,None,:,:] @ rotations
    six = local_r[...,:,:2].transpose(-1,-2).flatten(-2)
    return torch.cat((local_p,six),-1).flatten(-3)


class Autoencoder(nn.Module):
    def __init__(self, hidden_dim=512, hidden_layers=2):
        super().__init__()
        layers=[];width=DIM
        for _ in range(hidden_layers):
            layers.extend((nn.Linear(width,hidden_dim),nn.LayerNorm(hidden_dim),nn.GELU()));width=hidden_dim
        layers.extend((nn.Linear(width,128),nn.GELU()));width=128
        for _ in range(hidden_layers):
            layers.extend((nn.Linear(width,hidden_dim),nn.LayerNorm(hidden_dim),nn.GELU()));width=hidden_dim
        layers.append(nn.Linear(width,DIM))
        self.net=nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x)


class Scorer(nn.Module):
    """Frozen AE1-style normalized reconstruction cost; lower is more familiar."""
    def __init__(self, model, mean, std):
        super().__init__();self.model=model
        self.register_buffer('mean',mean);self.register_buffer('std',std)

    def forward(self, features):
        x=(features-self.mean)/self.std
        return ((self.model(x)-x)**2).mean(-1)
