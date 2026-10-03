"""Frozen-locomotion residual defense input/output contract.

The accepted lower and upper locomotion policies act first.  The learned lower
then perturbs the frozen lower transition and the learned upper perturbs the
frozen upper proposal after it has been carried onto the learned pelvis.  All
learned pose outputs remain deltas in the held defender-root frame.
"""
from pathlib import Path
import sys
import torch

SLASHES = Path(__file__).resolve().parent.parent
if str(SLASHES) not in sys.path:
    sys.path.insert(0, str(SLASHES))
from train_slash_controller import DeltaAgent, Recipe

CONDITION_DIM = 81  # Dataset fields: pelvis18 + collider18 + hit1 + root35 + target/type9.
ROOT_SHIFT_INPUT_DIM = 3  # Runtime-only cumulative adaptive-root shift in current-root space.
LOWER_INPUT_DIM = 41 + 41 + CONDITION_DIM + ROOT_SHIFT_INPUT_DIM
UPPER_INPUT_DIM = 90 + 90 + 3*9 + CONDITION_DIM + ROOT_SHIFT_INPUT_DIM
LOWER_OUTPUT_DIM = 43  # Pose delta41; pin commands2, NOT pose deltas.
UPPER_OUTPUT_DIM = 90  # No event output head.


def _join(fields, widths):
    for field, width in zip(fields, widths):
        if field.shape[-1] != width:
            raise ValueError(f'Expected input width {width}, got {field.shape[-1]}')
    return torch.cat(fields, dim=-1)


def build_lower_input(
    current_lower, frozen_next_lower, conditioning, cumulative_root_shift_local
):
    return _join(
        (
            current_lower,
            frozen_next_lower,
            conditioning,
            cumulative_root_shift_local,
        ),
        (41, 41, CONDITION_DIM, ROOT_SHIFT_INPUT_DIM),
    )


def build_upper_input(
    previous_upper,
    next_prior,
    previous_lower,
    current_lower,
    next_lower,
    conditioning,
    cumulative_root_shift_local,
):
    # Like the attack upper policy, observe the newly predicted lower pelvis.
    return _join(
        (
            previous_upper,
            next_prior,
            previous_lower[..., :9],
            current_lower[..., :9],
            next_lower[..., :9],
            conditioning,
            cumulative_root_shift_local,
        ),
        (90, 90, 9, 9, 9, CONDITION_DIM, ROOT_SHIFT_INPUT_DIM),
    )


def create_agents(recipe=None):
    recipe = recipe or Recipe()
    return (DeltaAgent(LOWER_INPUT_DIM, LOWER_OUTPUT_DIM, recipe, gates=False),
            DeltaAgent(UPPER_INPUT_DIM, UPPER_OUTPUT_DIM, recipe, gates=False))


def apply_lower_output(frozen_next_lower, output):
    """Zero pose deltas retain the frozen proposal; pins stay independent."""
    return frozen_next_lower + output[..., :41], output[..., 41:43]


def apply_upper_output(next_prior, output):
    """Delta on the current upper carried by the learned lower's new pelvis."""
    return next_prior + output
