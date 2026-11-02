"""World-space thigh/shin translation and angular reversals, matching foot timing."""
import torch


class LegReversal:
    buffer_names = ('position', 'rotation', 'previous_velocity', 'history', 'ticks', 'raw')

    def __init__(self, rows, device):
        self.position = torch.zeros(rows, 4, 3, device=device)
        self.rotation = torch.zeros(rows, 4, 4, device=device)
        self.rotation[..., 3] = 1
        self.previous_velocity = torch.zeros(rows, 2, 4, 3, device=device)
        self.history = torch.zeros(rows, 2, 4, 6, 3, device=device)
        self.ticks = torch.zeros(rows, dtype=torch.long, device=device)
        self.raw = torch.zeros(rows, 2, device=device)
        self.deadzone = torch.tensor([.02, .1], device=device)[None, :, None, None]

    def reset(self, ids, position, rotation):
        self.position[ids] = position
        self.rotation[ids] = rotation
        self.previous_velocity[ids] = 0
        self.history[ids] = 0
        self.ticks[ids] = 0
        self.raw[ids] = 0

    def append(self, position, rotation):
        a, aw = rotation[..., :3], rotation[..., 3:]
        b, bw = -self.rotation[..., :3], self.rotation[..., 3:]
        xyz = aw*b + bw*a + torch.cross(a, b, dim=-1)
        w = aw*bw - (a*b).sum(-1, keepdim=True)
        xyz = torch.where(w < 0, -xyz, xyz)
        length = xyz.norm(dim=-1, keepdim=True)
        angular = xyz*(2*torch.atan2(length, w.abs())/length.clamp_min(1e-8))*30
        velocity = torch.stack(((position-self.position)*30, angular), 1)
        smooth = torch.where((self.ticks > 0)[:, None, None, None],
                             (velocity+self.previous_velocity)*.5, velocity)
        u = smooth*(1-self.deadzone/smooth.norm(dim=-1, keepdim=True).clamp_min(1e-8)).clamp_min(0)
        reversal = (-(self.history*u[..., None, :]).sum(-1)).clamp_min(0).mean((-1, -2))
        self.raw.copy_(torch.where((self.ticks >= 7)[:, None], reversal, 0))
        self.history[..., :-1, :].copy_(self.history[..., 1:, :].clone())
        self.history[..., -1, :].copy_(u)
        self.previous_velocity.copy_(velocity)
        self.position.copy_(position)
        self.rotation.copy_(rotation)
        self.ticks.add_(1)
        return self.raw
