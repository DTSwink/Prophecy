"""Causal six-tick head reversal cost, matching the user-vetted replay preview."""
import torch


class HeadReversal:
    """Device-resident history; feed body origins once per 30Hz reward tick."""
    buffer_names = ('relative', 'previous_velocity', 'history', 'ticks', 'raw')

    def __init__(self, rows, device):
        self.relative = torch.zeros((rows, 3), device=device)
        self.previous_velocity = torch.zeros_like(self.relative)
        self.history = torch.zeros((rows, 6, 3), device=device)
        self.ticks = torch.zeros(rows, dtype=torch.long, device=device)
        self.raw = torch.zeros(rows, device=device)

    def reset(self, ids, relative_position):
        self.relative[ids] = relative_position
        self.previous_velocity[ids] = 0.
        self.history[ids] = 0.
        self.ticks[ids] = 0
        self.raw[ids] = 0.

    def append(self, relative_position):
        velocity = (relative_position-self.relative)*30.
        smooth = torch.where((self.ticks > 0)[:, None],
                             (velocity+self.previous_velocity)*.5, velocity)
        speed = smooth.norm(dim=-1, keepdim=True)
        u = smooth*(1.-.02/speed.clamp_min(1e-12)).clamp_min(0.)
        cost = (-(self.history*u[:, None]).sum(-1)).clamp_min(0.).mean(-1)
        self.raw.copy_(torch.where(self.ticks >= 7, cost, 0.))
        self.history[:, :-1].copy_(self.history[:, 1:].clone())
        self.history[:, -1].copy_(u)
        self.relative.copy_(relative_position)
        self.previous_velocity.copy_(velocity)
        self.ticks.add_(1)
        return self.raw
