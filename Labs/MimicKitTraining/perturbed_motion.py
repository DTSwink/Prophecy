"""Tensor helpers for yaw-perturbed motion training; no cloud side effects."""
import importlib.util
import math
from pathlib import Path

import torch

COM2_BODIES = ('pelvis', 'torso', 'head')


def getup_head_height_loss(height, target, elapsed_ticks, perturbed_getup):
    return (target-height).clamp_min(0).square() * (perturbed_getup & (elapsed_ticks > 60))


def getup_head_height_reward(height, target, elapsed_ticks, perturbed_getup):
    return (height/target.clamp_min(1e-6)).clamp(0., 1.) * (perturbed_getup & (elapsed_ticks > 60))


def com2_velocity(body_com_velocity, normalized_masses):
    """Input contains ONLY pelvis, torso and head, in world axes (metres/s)."""
    return (body_com_velocity[..., :2] * normalized_masses[:, None]).sum(-2)


def yaw_matrix(angle):
    c, s = angle.cos(), angle.sin()
    zero, one = torch.zeros_like(c), torch.ones_like(c)
    return torch.stack((c, -s, zero, s, c, zero, zero, zero, one), -1).reshape(-1, 3, 3)


def yaw_velocities_preserving_com2(velocities, angular, rotation, trunk_ids, masses):
    """Rotate articulation velocity, then preserve the original trunk COM XY.

    Adding one uniform translation to every body's COM velocity leaves all
    relative velocities unchanged. Combined with rotated body frames/omega,
    this retains the original local joint velocities. Z is never adjusted.
    """
    before = com2_velocity(velocities[:, trunk_ids], masses)
    turned = (rotation[:, None] @ velocities.unsqueeze(-1)).squeeze(-1)
    after = com2_velocity(turned[:, trunk_ids], masses)
    shift = torch.cat((before-after, torch.zeros_like(before[:, :1])), -1)
    return turned + shift[:, None], (rotation[:, None] @ angular.unsqueeze(-1)).squeeze(-1)


def com2_failure(velocity, target, min_speed_ratio, max_speed_ratio=1.7, angle_degrees=45.):
    """Strict thresholds; a zero actual speed fails the lower speed test.

    Caller enables this only on locomotion and after the eight-frame grace.
    Zero target vectors must be rejected when preparing locomotion targets.
    """
    speed = velocity.norm(dim=-1)
    reference_speed = target.norm(dim=-1)
    dot = (velocity*target).sum(-1)
    wrong_direction = dot < math.cos(math.radians(angle_degrees))*speed*reference_speed
    return wrong_direction | (speed < min_speed_ratio*reference_speed) | (speed > max_speed_ratio*reference_speed)


def tracking_blend(elapsed_ticks, ae_ticks=80, blend_ticks=60):
    """Zero tracking weight through tick 80, one from tick 140 onward."""
    return ((elapsed_ticks-ae_ticks)/blend_ticks).clamp(0., 1.)


class MotionPrior:
    """Frozen three-pose scorer for an RL reward, never a direct PPO gradient.

    All history and scoring stay on the simulator device. Call reset for every
    reset/teleport and append exactly once per 30 Hz policy tick. A reset pose
    counts as the first valid pose; no fabricated/repeated history is scored.
    """
    def __init__(self, folder, rows, device):
        folder = Path(folder)
        spec = importlib.util.spec_from_file_location('motion_prior_features', folder/'motion_features.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.encode = module.encode
        self.scorer = torch.jit.load(str(folder/'motion_scorer.pt'), map_location=device).eval()
        for parameter in self.scorer.parameters():
            parameter.requires_grad_(False)
        self.positions = torch.zeros((rows, 3, 15, 3), device=device)
        self.rotations = torch.zeros((rows, 3, 15, 3, 3), device=device)
        self.valid = torch.zeros(rows, dtype=torch.long, device=device)

    def reset(self, ids, positions, rotations):
        self.positions[ids] = 0.
        self.rotations[ids] = 0.
        self.positions[ids, -1] = positions
        self.rotations[ids, -1] = rotations
        self.valid[ids] = 1

    def append(self, positions, rotations):
        self.positions[:, :-1] = self.positions[:, 1:].clone()
        self.rotations[:, :-1] = self.rotations[:, 1:].clone()
        self.positions[:, -1] = positions
        self.rotations[:, -1] = rotations
        self.valid.add_(1).clamp_(max=3)

    @torch.no_grad()
    def cost(self):
        # MuJoCo transitions are not differentiable here. PPO receives this
        # scalar through rewards, not an input gradient through the simulator.
        cost = self.scorer(self.encode(self.positions, self.rotations, ground_height=0.))
        return torch.where(self.valid == 3, cost, torch.zeros_like(cost))
