"""Head-height torque-limit interpolation shared with exported checkpoints."""
import torch


def strength_fraction(height, vanilla_height, full_height):
    return ((height - vanilla_height) / (full_height - vanilla_height)).clamp(0., 1.)


def torque_multipliers(height, vanilla_height, full_height, maximum_ratio, enabled):
    alpha = strength_fraction(height, vanilla_height, full_height)
    return enabled * (1. + alpha[:, None] * (maximum_ratio[None, :] - 1.))
