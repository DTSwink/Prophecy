"""Idle path inefficiency: detect reversals and looping motion, not straight recovery."""
import math
import torch


class IdleWobble:
    # All state is device-resident and included in CUDA warmup/reset snapshots.
    buffer_names = ('vector', 'speed', 'mass', 'last_kick', 'raw')

    def __init__(self, rows, bodies, device):
        self.vector = torch.zeros(rows, 2, 2, bodies, 3, device=device)
        self.speed = torch.zeros(rows, 2, 2, bodies, device=device)
        self.mass = torch.zeros(rows, 2, device=device)
        self.last_kick = torch.full((rows,), -1, dtype=torch.long, device=device)
        self.raw = torch.zeros(rows, device=device)
        self.decay = torch.tensor([math.exp(-1/(30*.2)), math.exp(-1/(30*.7))], device=device)
        self.deadzone = torch.tensor([.02, .1], device=device)[None, :, None, None]
        self.metric = torch.tensor([1., .3**2], device=device)[None, None, :, None]

    def reset(self, ids):
        self.vector[ids] = 0
        self.speed[ids] = 0
        self.mass[ids] = 0
        self.last_kick[ids] = -1
        self.raw[ids] = 0

    def append(self, velocity, angular, kick, active):
        changed = kick != self.last_kick
        self.vector.mul_((~changed)[:, None, None, None, None])
        self.speed.mul_((~changed)[:, None, None, None])
        self.mass.mul_((~changed)[:, None])
        x = torch.stack((velocity, angular), 1)
        x = x*(1-self.deadzone/x.norm(dim=-1, keepdim=True).clamp_min(1e-8)).clamp_min(0)
        speed = x.norm(dim=-1)
        d = self.decay[None]
        self.vector.mul_(d[..., None, None, None]).add_((1-d[..., None, None, None])*x[:, None])
        self.speed.mul_(d[..., None, None]).add_((1-d[..., None, None])*speed[:, None])
        self.mass.mul_(d).add_(1-d)
        vector = self.vector/self.mass[..., None, None, None].clamp_min(1e-8)
        mean_speed = self.speed/self.mass[..., None, None].clamp_min(1e-8)
        # Triangle inequality gap: zero for any speed profile in one direction.
        gap = (mean_speed-vector.norm(dim=-1)).clamp_min(0)
        # Current speed makes the cost vanish as soon as the body actually stops.
        cost = (gap*speed[:, None]*self.metric).mean((1, 3)).sum(-1)
        self.raw.copy_(torch.where(active & ~changed, cost, 0.))
        self.last_kick.copy_(kick)
        return self.raw
