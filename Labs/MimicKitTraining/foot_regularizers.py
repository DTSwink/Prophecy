"""Causal device-only foot cadence and world-space reversal costs at 30 Hz."""
import torch


class FootRegularizers:
    buffer_names = ('position', 'rotation', 'previous_velocity', 'history',
                    'ticks', 'air', 'seen_lift', 'lift_age', 'interval', 'raw', 'events')

    def __init__(self, rows, device):
        self.position = torch.zeros((rows, 2, 3), device=device)
        self.rotation = torch.zeros((rows, 2, 4), device=device)
        self.rotation[..., 3] = 1
        self.previous_velocity = torch.zeros((rows, 2, 2, 3), device=device)
        self.history = torch.zeros((rows, 2, 2, 6, 3), device=device)
        self.ticks = torch.zeros(rows, dtype=torch.long, device=device)
        self.air = torch.zeros((rows, 2), dtype=torch.bool, device=device)
        self.seen_lift = torch.zeros_like(self.air)
        self.lift_age = torch.zeros((rows, 2), device=device)
        self.interval = torch.full((rows, 2), 1e6, device=device)
        self.raw = torch.zeros((rows, 3), device=device)
        self.events = torch.zeros((rows, 2), dtype=torch.bool, device=device)
        self.deadzone = torch.tensor([.02, .1], device=device)[None, :, None, None]

    def reset(self, ids, position, rotation, bottoms):
        self.position[ids] = position
        self.rotation[ids] = rotation
        self.previous_velocity[ids] = 0
        self.history[ids] = 0
        self.ticks[ids] = 0
        self.air[ids] = bottoms > .01
        self.seen_lift[ids] = False
        self.lift_age[ids] = 0
        self.interval[ids] = 1e6
        self.raw[ids] = 0
        self.events[ids] = False

    def append(self, position, rotation, bottoms, minimum_period):
        # Finite quaternion increments in WORLD axes (XYZW); sign-invariant.
        a, aw = rotation[..., :3], rotation[..., 3:]
        b, bw = -self.rotation[..., :3], self.rotation[..., 3:]
        xyz = aw*b + bw*a + torch.cross(a, b, dim=-1)
        w = aw*bw - (a*b).sum(-1, keepdim=True)
        xyz = torch.where(w < 0, -xyz, xyz)
        length = xyz.norm(dim=-1, keepdim=True)
        angle = 2*torch.atan2(length, w.abs())
        angular = xyz*(angle/length.clamp_min(1e-8))*30
        velocity = torch.stack(((position-self.position)*30, angular), 1)
        smooth = torch.where((self.ticks > 0)[:, None, None, None],
                             (velocity+self.previous_velocity)*.5, velocity)
        u = smooth*(1-self.deadzone/smooth.norm(dim=-1, keepdim=True).clamp_min(1e-8)).clamp_min(0)
        reversal = (-(self.history*u[..., None, :]).sum(-1)).clamp_min(0).mean((-1, -2))
        reversal = torch.where((self.ticks >= 7)[:, None], reversal, 0)
        new_air = torch.where(self.air, bottoms > .01, bottoms > .025)
        self.events.copy_(new_air & ~self.air)
        age = self.lift_age+1
        self.interval.copy_(torch.where(self.events & self.seen_lift, age, self.interval))
        new_age = torch.where(self.events, 0, age)
        # Dense cost after a too-early repeated lift, decaying as sufficient time passes.
        cadence = (1-(self.interval+new_age)/minimum_period.clamp_min(1)).clamp_min(0).square().mean(-1)
        self.raw.copy_(torch.cat((cadence[:, None], reversal), -1))
        self.seen_lift.logical_or_(self.events)
        self.lift_age.copy_(new_age)
        self.air.copy_(new_air)
        self.history[..., :-1, :].copy_(self.history[..., 1:, :].clone())
        self.history[..., -1, :].copy_(u)
        self.previous_velocity.copy_(velocity)
        self.position.copy_(position)
        self.rotation.copy_(rotation)
        self.ticks.add_(1)
        return self.raw
