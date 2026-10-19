"""Horizontal, mass-weighted COM speed bands; fixed world axes, SI units."""
import torch

CORE_BODIES = ('pelvis', 'torso', 'head', 'right_thigh', 'right_shin',
               'right_foot', 'left_thigh', 'left_shin', 'left_foot')


@torch.jit.script
def flat_com_velocity(body_com_velocity: torch.Tensor, mass_weights: torch.Tensor):
    return (body_com_velocity[..., :2] * mass_weights[:, None]).sum(-2)


@torch.jit.script
def expanded_band(reference_velocity: torch.Tensor, leeway: float):
    low = reference_velocity.amin(0)
    high = reference_velocity.amax(0)
    padding = (high-low)*leeway
    return torch.stack((low-padding, high+padding))


@torch.jit.script
def band_loss(velocity: torch.Tensor, bounds: torch.Tensor):
    excess = torch.relu(bounds[..., 0, :]-velocity) + torch.relu(velocity-bounds[..., 1, :])
    return excess.square().mean(-1)
