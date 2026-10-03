from __future__ import annotations

"""Shared Slash2 v3 target-origin/current-pelvis-facing coordinate codec.

The learned agents use a frame whose origin is the target projected onto the
zero-height floor and whose horizontal forward direction points from the
current pelvis to the target.  A prediction step constructs this basis from the
current pose once and holds it for the complete lower/upper prediction.  The
frozen locomotion policy, when enabled, keeps its historical root-relative
contract; this module is the only adapter between the two representations.
"""

from dataclasses import dataclass
from pathlib import Path
import sys

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
IK_DIR = PROJECT_ROOT / "training" / "ik"
if str(IK_DIR) not in sys.path:
    sys.path.insert(0, str(IK_DIR))

import ik_core as tl
import train_simple_ae_controller as ik_ctl


TARGET_FRAME_SCHEMA = "slash2_target_xz_current_pelvis_facing_v3"
TARGET_FRAME_SCHEMA_VERSION = 3
LOWER_STATE_DIM = 41
UPPER_STATE_DIM = 90
LOWER_OUTPUT_DIM = 43
UPPER_INPUT_DIM = 217
UPPER_OUTPUT_DIM = 92
AE11_INPUT_DIM = 129
AE22_INPUT_DIM = 276
AE33_INPUT_DIM = 276

# One registry owns the lower input contract.  The frozen proposal is omitted
# entirely in the disabled graph instead of being replaced by zeros or a copy.
LOWER_INPUT_FIELDS = (
    ("current_lower", LOWER_STATE_DIM),
    ("frozen_next", LOWER_STATE_DIM),
    ("attack_labels", 5),
    ("current_to_next_dyaw", 1),
    ("next_to_future_dyaw", 1),
    ("target_height", 1),
    ("reserved", 2),
)


def lower_input_dim(*, frozen_agent_enabled: bool) -> int:
    return sum(
        width
        for name, width in LOWER_INPUT_FIELDS
        if frozen_agent_enabled or name != "frozen_next"
    )


LOWER_INPUT_DIM_FROZEN_ENABLED = lower_input_dim(frozen_agent_enabled=True)
LOWER_INPUT_DIM_FROZEN_DISABLED = lower_input_dim(frozen_agent_enabled=False)


@dataclass(frozen=True)
class RootContractTolerance:
    root_height_m: float = 1.0e-6
    root_non_yaw_axis: float = 1.0e-5
    root_orthogonality: float = 1.0e-5


def target_origin(target_world: torch.Tensor) -> torch.Tensor:
    """Return `(target_x, 0, target_z)` without changing dtype or device."""

    if target_world.shape[-1] != 3:
        raise ValueError(f"Expected target [...,3], got {tuple(target_world.shape)}")
    origin = target_world.clone()
    origin[..., 1] = 0.0
    return origin


def target_height(target_world: torch.Tensor) -> torch.Tensor:
    """Return target world height as an explicit one-value condition."""

    if target_world.shape[-1] != 3:
        raise ValueError(f"Expected target [...,3], got {tuple(target_world.shape)}")
    return target_world[..., 1:2]


def target_facing_heading(
    pelvis_world: torch.Tensor,
    target_world: torch.Tensor,
) -> torch.Tensor:
    """Return the horizontal row-vector basis facing pelvis -> target.

    The caller owns the held-step lifetime of the returned basis.  No fallback
    direction is invented: a forbidden coincident pelvis/target XZ pair yields
    non-finite values and is rejected by corpus/runtime finite checks.
    """

    if pelvis_world.shape[-1] != 3 or target_world.shape[-1] != 3:
        raise ValueError(
            "pelvis_world and target_world must both end in three coordinates"
        )
    flat = target_world - pelvis_world
    flat = torch.stack((flat[..., 0], torch.zeros_like(flat[..., 0]), flat[..., 2]), dim=-1)
    inv_length = torch.rsqrt((flat * flat).sum(dim=-1))
    forward = flat * inv_length[..., None]
    yaw = torch.atan2(forward[..., 0], forward[..., 2])
    return tl.yaw_to_row_matrix(-yaw)


def target_facing_heading_numpy(
    pelvis_world: np.ndarray,
    target_world: np.ndarray,
) -> np.ndarray:
    """NumPy equivalent of :func:`target_facing_heading` for corpus builds."""

    pelvis = np.asarray(pelvis_world, dtype=np.float32)
    target = np.asarray(target_world, dtype=np.float32)
    if pelvis.shape[-1] != 3 or target.shape[-1] != 3:
        raise ValueError(
            "pelvis_world and target_world must both end in three coordinates"
        )
    flat = target - pelvis
    flat = flat.copy()
    flat[..., 1] = 0.0
    length = np.linalg.norm(flat, axis=-1)
    if not np.all(np.isfinite(length)) or np.any(length <= np.float32(0.0)):
        raise ValueError("Pelvis-to-target horizontal direction must be finite and nonzero")
    forward = flat / length[..., None]
    yaw = np.arctan2(forward[..., 0], forward[..., 2])
    c = np.cos(-yaw)
    s = np.sin(-yaw)
    z = np.zeros_like(c)
    o = np.ones_like(c)
    return np.stack(
        (
            np.stack((c, z, s), axis=-1),
            np.stack((z, o, z), axis=-1),
            np.stack((-s, z, c), axis=-1),
        ),
        axis=-2,
    ).astype(np.float32)


def assert_root_contract(
    root_position: torch.Tensor,
    root_rotation: torch.Tensor,
    *,
    tolerance: RootContractTolerance = RootContractTolerance(),
) -> None:
    """Reject roots that violate the zero-height, yaw-only Slash2 contract."""

    if root_position.shape[-1] != 3:
        raise ValueError(
            f"Expected root position [...,3], got {tuple(root_position.shape)}"
        )
    max_height = float(root_position[..., 1].abs().max().detach().cpu())
    expected_up = torch.zeros_like(root_rotation[..., 2, :])
    expected_up[..., 1] = 1.0
    max_non_yaw = float(
        (root_rotation[..., 2, :] - expected_up).abs().max().detach().cpu()
    )
    identity = torch.eye(
        3, dtype=root_rotation.dtype, device=root_rotation.device
    ).expand_as(root_rotation)
    max_orthogonality = float(
        (root_rotation @ root_rotation.transpose(-1, -2) - identity)
        .abs()
        .max()
        .detach()
        .cpu()
    )
    if max_height > float(tolerance.root_height_m):
        raise ValueError(
            f"Slash2 root height must be zero; maximum |y|={max_height:.9g} m"
        )
    if max_non_yaw > float(tolerance.root_non_yaw_axis):
        raise ValueError(
            "Slash2 root rotation must be yaw-only; "
            f"maximum vertical-axis residual={max_non_yaw:.9g}"
        )
    if max_orthogonality > float(tolerance.root_orthogonality):
        raise ValueError(
            "Slash2 root rotation must be orthonormal; "
            f"maximum residual={max_orthogonality:.9g}"
        )


def _rebase_position(
    position: torch.Tensor,
    from_origin: torch.Tensor,
    from_heading: torch.Tensor,
    to_origin: torch.Tensor,
    to_heading: torch.Tensor,
) -> torch.Tensor:
    world = torch.matmul(position.unsqueeze(-2), from_heading).squeeze(-2) + from_origin
    return torch.matmul(
        (world - to_origin).unsqueeze(-2), to_heading.transpose(-1, -2)
    ).squeeze(-2)


def _rebase_rot6(
    rotation: torch.Tensor,
    from_heading: torch.Tensor,
    to_heading: torch.Tensor,
) -> torch.Tensor:
    local = tl.rotation_6d_to_matrix(rotation)
    world = local @ from_heading
    return tl.rotmat_to_6d(world @ to_heading.transpose(-1, -2))


def rebase_lower_state(
    store: ik_ctl.SimpleClipStore,
    state: torch.Tensor,
    from_origin: torch.Tensor,
    from_heading: torch.Tensor,
    to_origin: torch.Tensor,
    to_heading: torch.Tensor,
) -> torch.Tensor:
    """Re-express all lower controller DOFs under another rigid frame."""

    if state.shape[-1] != LOWER_STATE_DIM:
        raise ValueError(
            f"Expected {LOWER_STATE_DIM} lower values, got {state.shape[-1]}"
        )
    return ik_ctl.fast_rebase_output_vector_root(
        store,
        state,
        from_origin,
        from_heading,
        to_origin,
        to_heading,
    )


def lower_root_to_target_frame(
    store: ik_ctl.SimpleClipStore,
    state: torch.Tensor,
    root_position: torch.Tensor,
    root_rotation: torch.Tensor,
    target_world: torch.Tensor,
    held_heading: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Encode a root-relative lower state and return its held v3 basis."""

    pelvis_world = (
        torch.matmul(state[..., :3].unsqueeze(-2), root_rotation).squeeze(-2)
        + root_position
    )
    heading = (
        target_facing_heading(pelvis_world, target_world)
        if held_heading is None
        else held_heading
    )
    encoded = rebase_lower_state(
        store,
        state,
        root_position,
        root_rotation,
        target_origin(target_world),
        heading,
    )
    return encoded, heading


def lower_target_frame_to_root(
    store: ik_ctl.SimpleClipStore,
    state: torch.Tensor,
    root_position: torch.Tensor,
    root_rotation: torch.Tensor,
    target_world: torch.Tensor,
    held_heading: torch.Tensor,
) -> torch.Tensor:
    return rebase_lower_state(
        store,
        state,
        target_origin(target_world),
        held_heading,
        root_position,
        root_rotation,
    )


def rebase_upper_state(
    state: torch.Tensor,
    from_origin: torch.Tensor,
    from_heading: torch.Tensor,
    to_origin: torch.Tensor,
    to_heading: torch.Tensor,
) -> torch.Tensor:
    """Rebase hand/upper-arm fields while preserving parent-local core fields."""

    if state.shape[-1] != UPPER_STATE_DIM:
        raise ValueError(
            f"Expected {UPPER_STATE_DIM} upper values, got {state.shape[-1]}"
        )
    core = tl.clean_6d(state[..., :60].reshape(-1, 6)).reshape(
        *state.shape[:-1], 60
    )
    arms: list[torch.Tensor] = []
    for start in (60, 75):
        arms.append(
            torch.cat(
                (
                    _rebase_position(
                        state[..., start : start + 3],
                        from_origin,
                        from_heading,
                        to_origin,
                        to_heading,
                    ),
                    _rebase_rot6(
                        state[..., start + 3 : start + 9],
                        from_heading,
                        to_heading,
                    ),
                    _rebase_rot6(
                        state[..., start + 9 : start + 15],
                        from_heading,
                        to_heading,
                    ),
                ),
                dim=-1,
            )
        )
    return torch.cat((core, *arms), dim=-1)


def upper_root_to_target_frame(
    state: torch.Tensor,
    root_position: torch.Tensor,
    root_rotation: torch.Tensor,
    target_world: torch.Tensor,
    held_heading: torch.Tensor,
) -> torch.Tensor:
    return rebase_upper_state(
        state,
        root_position,
        root_rotation,
        target_origin(target_world),
        held_heading,
    )


def upper_target_frame_to_root(
    state: torch.Tensor,
    root_position: torch.Tensor,
    root_rotation: torch.Tensor,
    target_world: torch.Tensor,
    held_heading: torch.Tensor,
) -> torch.Tensor:
    return rebase_upper_state(
        state,
        target_origin(target_world),
        held_heading,
        root_position,
        root_rotation,
    )


def lower_to_held_heading(
    store: ik_ctl.SimpleClipStore,
    state: torch.Tensor,
    target_world: torch.Tensor,
    state_heading: torch.Tensor,
    held_heading: torch.Tensor,
) -> torch.Tensor:
    """Express a v3 lower state in another held step basis."""

    origin = target_origin(target_world)
    return rebase_lower_state(
        store,
        state,
        origin,
        state_heading,
        origin,
        held_heading,
    )


def upper_to_held_heading(
    state: torch.Tensor,
    target_world: torch.Tensor,
    state_heading: torch.Tensor,
    held_heading: torch.Tensor,
) -> torch.Tensor:
    """Express a v3 upper state in another held step basis."""

    origin = target_origin(target_world)
    return rebase_upper_state(
        state,
        origin,
        state_heading,
        origin,
        held_heading,
    )


def held_heading_to_lower(
    store: ik_ctl.SimpleClipStore,
    state: torch.Tensor,
    target_world: torch.Tensor,
    held_heading: torch.Tensor,
    state_heading: torch.Tensor,
) -> torch.Tensor:
    origin = target_origin(target_world)
    return rebase_lower_state(
        store,
        state,
        origin,
        held_heading,
        origin,
        state_heading,
    )


def held_heading_to_upper(
    state: torch.Tensor,
    target_world: torch.Tensor,
    held_heading: torch.Tensor,
    state_heading: torch.Tensor,
) -> torch.Tensor:
    origin = target_origin(target_world)
    return rebase_upper_state(
        state,
        origin,
        held_heading,
        origin,
        state_heading,
    )


def _numpy_matrix_from_rot6(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float32)
    a1 = values[..., :3]
    a2 = values[..., 3:6]
    b1 = a1 / np.maximum(np.linalg.norm(a1, axis=-1, keepdims=True), 1.0e-8)
    projected = a2 - np.sum(b1 * a2, axis=-1, keepdims=True) * b1
    b2 = projected / np.maximum(
        np.linalg.norm(projected, axis=-1, keepdims=True), 1.0e-8
    )
    b3 = np.cross(b1, b2)
    return np.stack((b1, b2, b3), axis=-2).astype(np.float32)


def numpy_matrix_from_rot6(values: np.ndarray) -> np.ndarray:
    """Public offline rot6 decoder shared by corpus builders and validators."""

    return _numpy_matrix_from_rot6(values)


def _numpy_rebase_rot6(
    values: np.ndarray,
    from_heading: np.ndarray,
    to_heading: np.ndarray,
) -> np.ndarray:
    rotation = _numpy_matrix_from_rot6(values)
    rebased = (
        rotation
        @ np.asarray(from_heading, dtype=np.float32)
        @ np.swapaxes(np.asarray(to_heading, dtype=np.float32), -1, -2)
    )
    return rebased[..., :2, :].reshape(values.shape).astype(np.float32)


def _numpy_rebase_position(
    values: np.ndarray,
    from_heading: np.ndarray,
    to_heading: np.ndarray,
) -> np.ndarray:
    world = np.einsum(
        "...i,...ij->...j",
        np.asarray(values, dtype=np.float32),
        np.asarray(from_heading, dtype=np.float32),
    )
    return np.einsum(
        "...i,...ij->...j",
        world,
        np.swapaxes(np.asarray(to_heading, dtype=np.float32), -1, -2),
    ).astype(np.float32)


def rebase_lower_same_origin_numpy(
    state: np.ndarray,
    from_heading: np.ndarray,
    to_heading: np.ndarray,
) -> np.ndarray:
    """Offline equivalent of lower target-frame rebasing at one target origin."""

    state = np.asarray(state, dtype=np.float32)
    if state.shape[-1] != LOWER_STATE_DIM:
        raise ValueError(f"Expected lower width {LOWER_STATE_DIM}, got {state.shape}")
    result = state.copy()
    for start in (0, 9, 25):
        result[..., start : start + 3] = _numpy_rebase_position(
            state[..., start : start + 3], from_heading, to_heading
        )
    for start in (3, 12, 18, 28, 34):
        result[..., start : start + 6] = _numpy_rebase_rot6(
            state[..., start : start + 6], from_heading, to_heading
        )
    return result


def rebase_upper_same_origin_numpy(
    state: np.ndarray,
    from_heading: np.ndarray,
    to_heading: np.ndarray,
) -> np.ndarray:
    """Offline equivalent of upper target-frame rebasing at one target origin."""

    state = np.asarray(state, dtype=np.float32)
    if state.shape[-1] != UPPER_STATE_DIM:
        raise ValueError(f"Expected upper width {UPPER_STATE_DIM}, got {state.shape}")
    result = state.copy()
    for start in (60, 75):
        result[..., start : start + 3] = _numpy_rebase_position(
            state[..., start : start + 3], from_heading, to_heading
        )
        for rotation_start in (start + 3, start + 9):
            result[..., rotation_start : rotation_start + 6] = (
                _numpy_rebase_rot6(
                    state[..., rotation_start : rotation_start + 6],
                    from_heading,
                    to_heading,
                )
            )
    return result
