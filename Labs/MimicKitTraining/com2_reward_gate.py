"""Continuous COM2 reward multiplier, independent of termination timing."""
import math
import torch


def com2_reward_gate(velocity, target, basis, leeway, idle, require_both=False):
    # Euclidean distance to the nearest point of the existing directional velocity envelope.
    projected = (basis*(velocity-target)[:, None, :]).sum(-1)
    distance = (projected.abs()-leeway).clamp_min(0.).norm(dim=-1)
    dot = (velocity*target).sum(-1)
    norms = velocity.norm(dim=-1)*target.norm(dim=-1)
    cosine = (dot/norms.clamp_min(1e-12)).clamp(-1., 1.)
    # A stopped non-idle agent has no valid target-directed velocity.
    cosine = torch.where(norms > 1e-12, cosine, -torch.ones_like(cosine))
    angle = torch.acos(cosine)*(180./math.pi)
    angle = torch.where(idle, 0., angle)
    speed_bad = (distance-1.).clamp(0., 1.)
    direction_bad = ((angle-40.)/20.).clamp(0., 1.)
    speed_bad = speed_bad.square()*(3.-2.*speed_bad)
    direction_bad = direction_bad.square()*(3.-2.*direction_bad)
    bad = torch.minimum(speed_bad, direction_bad) if require_both else torch.maximum(speed_bad, direction_bad)
    bad = torch.where(idle, speed_bad, bad)
    return 1.-.999*bad, distance, angle
