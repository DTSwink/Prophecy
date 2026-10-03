from __future__ import annotations

"""Upper-locomotion pelvis/leg contract.

This module is deliberately isolated from :mod:`ik_core`'s generic decoder.
The upper agent may change the upper pose and pelvis transform, while the
frozen lower agent remains authoritative for both complete foot transforms.
The thigh/calf chains are rebuilt in one direct, differentiable two-bone solve
using the pole direction of the frozen-lower pose.  There is no reach clamp,
iteration, or binary search.
"""

from typing import Iterable

import torch

try:
    from . import ik_core as tl
    from . import train_upper_pose_autoencoder as upper_data
except ImportError:
    import ik_core as tl
    import train_upper_pose_autoencoder as upper_data


UPPER_OUTPUT_DIM = upper_data.OUTPUT_DIM
PELVIS_OUTPUT_DIM = upper_data.PELVIS_DIM
AGENT_OUTPUT_DIM = UPPER_OUTPUT_DIM + PELVIS_OUTPUT_DIM

PHYSICAL_BONES = (
    "pelvis",
    "spine_01",
    "spine_02",
    "spine_03",
    "spine_04",
    "spine_05",
    "neck_01",
    "neck_02",
    "head",
    "clavicle_l",
    "clavicle_r",
    "upperarm_l",
    "hand_l",
    "upperarm_r",
    "hand_r",
    "thigh_l",
    "calf_l",
    "thigh_r",
    "calf_r",
)
TRANSFORM_DIM = 9
PHYSICAL_DIM = len(PHYSICAL_BONES) * TRANSFORM_DIM
POLE_TARGET_DISTANCE_M = 0.65

# The cached-lower controller is allowed to change only the authored upper
# representation.  The accepted AE checkpoint still consumes the historical
# 171D physical vector, but these lower-body channels are conditioning only:
# they are excluded from the controller loss and therefore cannot contribute
# any controller gradient.  Feet were never part of PHYSICAL_BONES.
CACHED_LOWER_PHYSICAL_BONES = (
    "pelvis",
    "thigh_l",
    "calf_l",
    "thigh_r",
    "calf_r",
)
SCORED_UPPER_PHYSICAL_BONES = tuple(
    name for name in PHYSICAL_BONES if name not in CACHED_LOWER_PHYSICAL_BONES
)


def physical_scoring_mask(
    *,
    device: torch.device | str | None = None,
    dtype: torch.dtype = torch.float32,
) -> torch.Tensor:
    """Return the exact upper-only AE output mask used by the controller."""

    mask = torch.zeros(PHYSICAL_DIM, dtype=dtype, device=device)
    for name in SCORED_UPPER_PHYSICAL_BONES:
        bone = PHYSICAL_BONES.index(name)
        start = bone * TRANSFORM_DIM
        mask[start : start + TRANSFORM_DIM] = 1.0
    return mask


def clean_transform(values: torch.Tensor) -> torch.Tensor:
    if values.shape[-1] != TRANSFORM_DIM:
        raise ValueError(f"Expected transform width {TRANSFORM_DIM}, got {values.shape[-1]}")
    return torch.cat((values[..., :3], tl.clean_6d(values[..., 3:9])), dim=-1)


def clean_physical_pose(values: torch.Tensor) -> torch.Tensor:
    one = values.ndim == 1
    work = values.unsqueeze(0) if one else values
    if work.ndim != 2 or int(work.shape[-1]) != PHYSICAL_DIM:
        raise ValueError(f"Expected [N,{PHYSICAL_DIM}], got {tuple(values.shape)}")
    shaped = work.reshape(-1, len(PHYSICAL_BONES), TRANSFORM_DIM)
    cleaned = torch.cat(
        (
            shaped[..., :3],
            tl.clean_6d(shaped[..., 3:9].reshape(-1, 6)).reshape(
                -1, len(PHYSICAL_BONES), 6
            ),
        ),
        dim=-1,
    ).reshape(-1, PHYSICAL_DIM)
    return cleaned.squeeze(0) if one else cleaned


def physical_pose_from_globals(
    clip: tl.MotionClip,
    positions: torch.Tensor,
    rotations: torch.Tensor,
    reference_position: torch.Tensor,
    reference_rotation: torch.Tensor,
) -> torch.Tensor:
    """Encode actual joint transforms relative to one root transform."""

    by_name = {name: index for index, name in enumerate(clip.body_names)}
    parts: list[torch.Tensor] = []
    inverse = reference_rotation.transpose(-1, -2)
    for name in PHYSICAL_BONES:
        joint = by_name[name]
        position = torch.matmul(
            (positions[:, joint] - reference_position).unsqueeze(1), inverse
        ).squeeze(1)
        rotation = rotations[:, joint] @ inverse
        parts.extend((position, tl.rotmat_to_6d(rotation)))
    return clean_physical_pose(torch.cat(parts, dim=-1))


def upper_only_physical_pose(
    clip: tl.MotionClip,
    upper_heading: torch.Tensor,
    root_position: torch.Tensor,
    heading: torch.Tensor,
    cached_lower_positions: torch.Tensor,
    cached_lower_rotations: torch.Tensor,
    reference_position: torch.Tensor,
    reference_rotation: torch.Tensor,
    *,
    local_offsets: torch.Tensor | None = None,
) -> torch.Tensor:
    """Decode only the physical transforms that the upper controller can move.

    ``cached_lower_*`` contains pelvis/thigh/calf transforms in
    :data:`CACHED_LOWER_PHYSICAL_BONES` order.  No leg FK, leg IK, foot-roll
    solve, or frozen lower-network operation occurs here.  The dynamic upper
    chain is reconstructed directly from its 90D representation and the
    cached pelvis transform.
    """

    batch = int(upper_heading.shape[0])
    if tuple(upper_heading.shape) != (batch, UPPER_OUTPUT_DIM):
        raise ValueError(f"Expected upper [{batch},{UPPER_OUTPUT_DIM}], got {tuple(upper_heading.shape)}")
    lower_count = len(CACHED_LOWER_PHYSICAL_BONES)
    if tuple(cached_lower_positions.shape) != (batch, lower_count, 3):
        raise ValueError(
            "Cached lower position shape mismatch: "
            f"{tuple(cached_lower_positions.shape)}"
        )
    if tuple(cached_lower_rotations.shape) != (batch, lower_count, 3, 3):
        raise ValueError(
            "Cached lower rotation shape mismatch: "
            f"{tuple(cached_lower_rotations.shape)}"
        )
    if local_offsets is None:
        local_offsets = clip.local_offsets.to(
            device=upper_heading.device, dtype=upper_heading.dtype
        )
    else:
        local_offsets = local_offsets.to(
            device=upper_heading.device, dtype=upper_heading.dtype
        )
    if local_offsets.ndim == 2:
        local_offsets = local_offsets.unsqueeze(0).expand(batch, -1, -1)
    if int(local_offsets.shape[0]) != batch:
        raise ValueError(
            f"Local-offset batch mismatch: {tuple(local_offsets.shape)} for {batch}"
        )

    by_name = {name: index for index, name in enumerate(clip.body_names)}
    lower_positions = {
        name: cached_lower_positions[:, slot]
        for slot, name in enumerate(CACHED_LOWER_PHYSICAL_BONES)
    }
    lower_rotations = {
        name: cached_lower_rotations[:, slot]
        for slot, name in enumerate(CACHED_LOWER_PHYSICAL_BONES)
    }
    world_positions: dict[str, torch.Tensor] = {"pelvis": lower_positions["pelvis"]}
    world_rotations: dict[str, torch.Tensor] = {"pelvis": lower_rotations["pelvis"]}

    cleaned = upper_data.clean_upper_state(upper_heading)
    local_core = tl.rotation_6d_to_matrix(cleaned[:, :60].reshape(-1, 6)).reshape(
        batch, len(upper_data.CORE_BONES), 3, 3
    )
    for slot, name in enumerate(upper_data.CORE_BONES):
        joint = by_name[name]
        parent_index = int(clip.parents_body_list[joint])
        if parent_index < 0:
            raise RuntimeError(f"Upper bone {name} unexpectedly has no parent")
        parent_name = clip.body_names[parent_index]
        if parent_name not in world_positions:
            raise RuntimeError(
                f"Upper FK order missing parent {parent_name!r} for {name!r}"
            )
        parent_position = world_positions[parent_name]
        parent_rotation = world_rotations[parent_name]
        world_positions[name] = parent_position + torch.matmul(
            local_offsets[:, joint].unsqueeze(1), parent_rotation
        ).squeeze(1)
        world_rotations[name] = local_core[:, slot] @ parent_rotation

    for arm_slot, (_side, upper_name, _lower_name, hand_name) in enumerate(
        upper_data.ARM_SPECS
    ):
        start = 60 + arm_slot * 15
        upper_joint = by_name[upper_name]
        parent_name = clip.body_names[int(clip.parents_body_list[upper_joint])]
        parent_position = world_positions[parent_name]
        parent_rotation = world_rotations[parent_name]
        world_positions[upper_name] = parent_position + torch.matmul(
            local_offsets[:, upper_joint].unsqueeze(1), parent_rotation
        ).squeeze(1)
        upper_heading_rotation = tl.rotation_6d_to_matrix(
            cleaned[:, start + 9 : start + 15]
        )
        world_rotations[upper_name] = upper_heading_rotation @ heading
        world_positions[hand_name] = root_position + torch.matmul(
            cleaned[:, start : start + 3].unsqueeze(1), heading
        ).squeeze(1)
        hand_heading_rotation = tl.rotation_6d_to_matrix(
            cleaned[:, start + 3 : start + 9]
        )
        world_rotations[hand_name] = hand_heading_rotation @ heading

    inverse = reference_rotation.transpose(-1, -2)
    parts: list[torch.Tensor] = []
    for name in PHYSICAL_BONES:
        if name in lower_positions:
            position_world = lower_positions[name]
            rotation_world = lower_rotations[name]
        else:
            position_world = world_positions[name]
            rotation_world = world_rotations[name]
        position = torch.matmul(
            (position_world - reference_position).unsqueeze(1), inverse
        ).squeeze(1)
        rotation = rotation_world @ inverse
        parts.extend((position, tl.rotmat_to_6d(rotation)))
    return clean_physical_pose(torch.cat(parts, dim=-1))


def upper_only_absolute_pose(
    clip: tl.MotionClip,
    upper_heading: torch.Tensor,
    root_position: torch.Tensor,
    root_rotation: torch.Tensor,
    heading: torch.Tensor,
    cached_lower_positions: torch.Tensor,
    cached_lower_rotations: torch.Tensor,
    target_bones: tuple[str, ...],
    *,
    local_offsets: torch.Tensor,
    local_pole_axes: torch.Tensor,
) -> torch.Tensor:
    """Decode the agent-controlled upper chain in the current root frame.

    This is the upper-only counterpart of the full FK/IK decoder.  It keeps the
    cached pelvis authoritative, reconstructs the core with FK, and resolves
    each implicit lower arm exactly as :func:`ik_core.fk_from_pose` does.  No
    leg, foot-roll, or frozen-lower computation is introduced.
    """

    batch = int(upper_heading.shape[0])
    if tuple(upper_heading.shape) != (batch, UPPER_OUTPUT_DIM):
        raise ValueError(
            f"Expected upper [{batch},{UPPER_OUTPUT_DIM}], got {tuple(upper_heading.shape)}"
        )
    lower_count = len(CACHED_LOWER_PHYSICAL_BONES)
    if tuple(cached_lower_positions.shape) != (batch, lower_count, 3):
        raise ValueError(
            "Cached lower position shape mismatch: "
            f"{tuple(cached_lower_positions.shape)}"
        )
    if tuple(cached_lower_rotations.shape) != (batch, lower_count, 3, 3):
        raise ValueError(
            "Cached lower rotation shape mismatch: "
            f"{tuple(cached_lower_rotations.shape)}"
        )
    local_offsets = local_offsets.to(
        device=upper_heading.device, dtype=upper_heading.dtype
    )
    local_pole_axes = local_pole_axes.to(
        device=upper_heading.device, dtype=upper_heading.dtype
    )
    if local_offsets.ndim == 2:
        local_offsets = local_offsets.unsqueeze(0).expand(batch, -1, -1)
    if local_pole_axes.ndim == 3:
        local_pole_axes = local_pole_axes.unsqueeze(0).expand(batch, -1, -1, -1)
    if int(local_offsets.shape[0]) != batch or int(local_pole_axes.shape[0]) != batch:
        raise ValueError(
            "Upper geometry batch mismatch: "
            f"offsets={tuple(local_offsets.shape)} poles={tuple(local_pole_axes.shape)}"
        )

    by_name = {name: index for index, name in enumerate(clip.body_names)}
    lower_positions = {
        name: cached_lower_positions[:, slot]
        for slot, name in enumerate(CACHED_LOWER_PHYSICAL_BONES)
    }
    lower_rotations = {
        name: cached_lower_rotations[:, slot]
        for slot, name in enumerate(CACHED_LOWER_PHYSICAL_BONES)
    }
    world_positions: dict[str, torch.Tensor] = {"pelvis": lower_positions["pelvis"]}
    world_rotations: dict[str, torch.Tensor] = {"pelvis": lower_rotations["pelvis"]}

    cleaned = upper_data.clean_upper_state(upper_heading)
    local_core = tl.rotation_6d_to_matrix(cleaned[:, :60].reshape(-1, 6)).reshape(
        batch, len(upper_data.CORE_BONES), 3, 3
    )
    for slot, name in enumerate(upper_data.CORE_BONES):
        joint = by_name[name]
        parent_name = clip.body_names[int(clip.parents_body_list[joint])]
        parent_position = world_positions[parent_name]
        parent_rotation = world_rotations[parent_name]
        world_positions[name] = parent_position + torch.matmul(
            local_offsets[:, joint].unsqueeze(1), parent_rotation
        ).squeeze(1)
        world_rotations[name] = local_core[:, slot] @ parent_rotation

    arm_limb_rows = [
        (limb, spec)
        for limb, spec in enumerate(clip.ik_limb_specs)
        if str(spec["kind"]) == "arm"
    ]
    if len(arm_limb_rows) != len(upper_data.ARM_SPECS):
        raise ValueError(
            f"Expected {len(upper_data.ARM_SPECS)} arm IK chains, got {len(arm_limb_rows)}"
        )
    for arm_slot, ((limb, spec), (_side, upper_name, lower_name, hand_name)) in enumerate(
        zip(arm_limb_rows, upper_data.ARM_SPECS, strict=True)
    ):
        start = 60 + arm_slot * 15
        upper_joint = by_name[upper_name]
        lower_joint = by_name[lower_name]
        hand_joint = by_name[hand_name]
        parent_name = clip.body_names[int(clip.parents_body_list[upper_joint])]
        parent_position = world_positions[parent_name]
        parent_rotation = world_rotations[parent_name]
        upper_position = parent_position + torch.matmul(
            local_offsets[:, upper_joint].unsqueeze(1), parent_rotation
        ).squeeze(1)
        upper_rotation = tl.rotation_6d_to_matrix(cleaned[:, start + 9 : start + 15]) @ heading
        hand_position = root_position + torch.matmul(
            cleaned[:, start : start + 3].unsqueeze(1), heading
        ).squeeze(1)
        hand_rotation = tl.rotation_6d_to_matrix(cleaned[:, start + 3 : start + 9]) @ heading
        lower_position = upper_position + torch.matmul(
            local_offsets[:, lower_joint].unsqueeze(1), upper_rotation
        ).squeeze(1)
        world_pole = torch.matmul(
            local_pole_axes[:, limb, 0].unsqueeze(1), upper_rotation
        ).squeeze(1)
        lower_axis = hand_position - lower_position
        fallback_axis = torch.matmul(
            local_offsets[:, hand_joint].unsqueeze(1), upper_rotation
        ).squeeze(1)
        lower_axis = torch.where(
            torch.linalg.norm(lower_axis, dim=-1, keepdim=True) > 1.0e-8,
            lower_axis,
            fallback_axis,
        )
        lower_rotation = tl.rotation_from_axis_and_pole(
            local_offsets[:, hand_joint],
            lower_axis,
            local_pole_axes[:, limb, 1],
            world_pole,
        )
        world_positions.update(
            {
                upper_name: upper_position,
                lower_name: lower_position,
                hand_name: hand_position,
            }
        )
        world_rotations.update(
            {
                upper_name: upper_rotation,
                lower_name: lower_rotation,
                hand_name: hand_rotation,
            }
        )

    inverse = root_rotation.transpose(-1, -2)
    parts: list[torch.Tensor] = []
    for name in target_bones:
        if name not in world_positions:
            raise RuntimeError(f"Upper absolute pose has no decoded bone {name!r}")
        position = torch.matmul(
            (world_positions[name] - root_position).unsqueeze(1), inverse
        ).squeeze(1)
        rotation = world_rotations[name] @ inverse
        parts.extend((position, tl.rotmat_to_6d(rotation)))
    return torch.cat(parts, dim=-1)


def upper_only_physical_transition_and_following_pose(
    clip: tl.MotionClip,
    current_upper: torch.Tensor,
    next_upper: torch.Tensor,
    current_root_position: torch.Tensor,
    current_root_rotation: torch.Tensor,
    current_heading: torch.Tensor,
    next_root_position: torch.Tensor,
    next_heading: torch.Tensor,
    current_cached_lower_positions: torch.Tensor,
    current_cached_lower_rotations: torch.Tensor,
    next_cached_lower_positions: torch.Tensor,
    next_cached_lower_rotations: torch.Tensor,
    *,
    local_offsets: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Return the physical delta and following pose from one shared decode."""

    current = upper_only_physical_pose(
        clip,
        current_upper,
        current_root_position,
        current_heading,
        current_cached_lower_positions,
        current_cached_lower_rotations,
        current_root_position,
        current_root_rotation,
        local_offsets=local_offsets,
    )
    following = upper_only_physical_pose(
        clip,
        next_upper,
        next_root_position,
        next_heading,
        next_cached_lower_positions,
        next_cached_lower_rotations,
        current_root_position,
        current_root_rotation,
        local_offsets=local_offsets,
    )
    return following - current, following


def upper_only_physical_transition(
    clip: tl.MotionClip,
    current_upper: torch.Tensor,
    next_upper: torch.Tensor,
    current_root_position: torch.Tensor,
    current_root_rotation: torch.Tensor,
    current_heading: torch.Tensor,
    next_root_position: torch.Tensor,
    next_heading: torch.Tensor,
    current_cached_lower_positions: torch.Tensor,
    current_cached_lower_rotations: torch.Tensor,
    next_cached_lower_positions: torch.Tensor,
    next_cached_lower_rotations: torch.Tensor,
    *,
    local_offsets: torch.Tensor | None = None,
) -> torch.Tensor:
    """Next-minus-current physical transforms without decoding the lower body."""

    transition, _following = upper_only_physical_transition_and_following_pose(
        clip,
        current_upper,
        next_upper,
        current_root_position,
        current_root_rotation,
        current_heading,
        next_root_position,
        next_heading,
        current_cached_lower_positions,
        current_cached_lower_rotations,
        next_cached_lower_positions,
        next_cached_lower_rotations,
        local_offsets=local_offsets,
    )
    return transition


def lowerarm_length_error_rows(
    clip: tl.MotionClip,
    physical_pose: torch.Tensor,
    local_offsets: torch.Tensor,
    limb_lengths: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Symmetric wrist-to-elbow length MSE for both implicit lower arms.

    This is the same geometry used by the final Slash trainer: extension and
    compression are both the squared signed distance from each clip's fixed
    runtime lower-arm length.
    """

    count = int(physical_pose.shape[0])
    if tuple(physical_pose.shape) != (count, PHYSICAL_DIM):
        raise ValueError(
            f"Expected physical pose [{count},{PHYSICAL_DIM}], got "
            f"{tuple(physical_pose.shape)}"
        )
    if local_offsets.ndim == 2:
        local_offsets = local_offsets.unsqueeze(0).expand(count, -1, -1)
    if int(local_offsets.shape[0]) != count:
        raise ValueError(
            f"Local-offset batch mismatch: {tuple(local_offsets.shape)} for {count}"
        )
    arm_rows = [
        (limb, spec)
        for limb, spec in enumerate(clip.ik_limb_specs)
        if str(spec["kind"]) == "arm"
    ]
    if len(arm_rows) != len(upper_data.ARM_SPECS):
        raise ValueError(
            f"Expected {len(upper_data.ARM_SPECS)} arm IK chains, got {len(arm_rows)}"
        )
    shaped = physical_pose.reshape(count, len(PHYSICAL_BONES), TRANSFORM_DIM)
    actual_parts: list[torch.Tensor] = []
    fixed_parts: list[torch.Tensor] = []
    for limb, spec in arm_rows:
        upper_name = clip.body_names[int(spec["start"])]
        lower_joint = int(spec["mid"])
        hand_name = clip.body_names[int(spec["end"])]
        upper_slot = PHYSICAL_BONES.index(upper_name)
        hand_slot = PHYSICAL_BONES.index(hand_name)
        upper_position = shaped[:, upper_slot, :3]
        upper_rotation = tl.rotation_6d_to_matrix(
            shaped[:, upper_slot, 3:9]
        )
        elbow_position = upper_position + torch.matmul(
            local_offsets[:, lower_joint].unsqueeze(1), upper_rotation
        ).squeeze(1)
        hand_position = shaped[:, hand_slot, :3]
        actual_parts.append(
            torch.linalg.vector_norm(hand_position - elbow_position, dim=-1)
        )
        fixed_parts.append(limb_lengths[:, limb, 1])
    actual = torch.stack(actual_parts, dim=-1)
    fixed = torch.stack(fixed_parts, dim=-1).to(
        device=actual.device, dtype=actual.dtype
    )
    error = actual - fixed
    return error.square().mean(dim=-1), error.abs().amax(dim=-1)


def reframe_physical_pose(
    pose: torch.Tensor,
    source_position: torch.Tensor,
    source_rotation: torch.Tensor,
    target_position: torch.Tensor,
    target_rotation: torch.Tensor,
) -> torch.Tensor:
    count = int(pose.shape[0])
    shaped = pose.reshape(count, len(PHYSICAL_BONES), TRANSFORM_DIM)
    source_world_position = source_position[:, None, :] + torch.matmul(
        shaped[..., :3].unsqueeze(-2), source_rotation[:, None]
    ).squeeze(-2)
    target_inverse = target_rotation.transpose(-1, -2)
    target_local_position = torch.matmul(
        (source_world_position - target_position[:, None, :]).unsqueeze(-2),
        target_inverse[:, None],
    ).squeeze(-2)
    source_local_rotation = tl.rotation_6d_to_matrix(
        shaped[..., 3:9].reshape(-1, 6)
    ).reshape(count, len(PHYSICAL_BONES), 3, 3)
    target_local_rotation = (
        source_local_rotation
        @ source_rotation[:, None]
        @ target_inverse[:, None]
    )
    return clean_physical_pose(
        torch.cat(
            (target_local_position, tl.rotmat_to_6d(target_local_rotation)),
            dim=-1,
        ).reshape(count, PHYSICAL_DIM)
    )


def authored_physical_state(
    clip: tl.MotionClip,
    frame_indices: torch.Tensor,
    gaze: torch.Tensor,
) -> torch.Tensor:
    positions, rotations = upper_data.gaze_overlay_global_pose(
        clip, frame_indices, gaze
    )
    return physical_pose_from_globals(
        clip,
        positions,
        rotations,
        clip.root_pos.index_select(0, frame_indices),
        clip.root_rot.index_select(0, frame_indices),
    )


def authored_transition_delta(
    clip: tl.MotionClip,
    cfg: tl.TrainConfig,
    current: torch.Tensor,
    gaze: torch.Tensor,
) -> torch.Tensor:
    """Next-minus-current physical transforms in the current actual-root frame."""

    if clip.cyclic_animation:
        period = int(clip.cyclic_period)
        current_logical = torch.remainder(current, period)
        following = current + 1
        following_logical = torch.remainder(following, period)
    else:
        current_logical = current
        following = current + 1
        following_logical = following

    count = int(current.numel())
    states = authored_physical_state(
        clip,
        torch.cat((current_logical, following_logical), dim=0),
        gaze.repeat(2, 1),
    )
    current_state = states[:count]
    following_state_own = states[count:]
    current_root_position, current_root_rotation, _yaw, _heading = tl.root_state(
        clip, current, cfg, torch.device("cpu")
    )
    following_root_position, following_root_rotation, _yaw, _heading = tl.root_state(
        clip, following, cfg, torch.device("cpu")
    )
    following_state = reframe_physical_pose(
        following_state_own,
        following_root_position,
        following_root_rotation,
        current_root_position,
        current_root_rotation,
    )
    return following_state - current_state


def group_for(relative: str, sword: float) -> int:
    return (0 if relative.startswith("walk_") else 2) + (0 if sword < 0.0 else 1)


def heading_transform_to_root(
    transform: torch.Tensor,
    root_rotation: torch.Tensor,
    heading: torch.Tensor,
) -> torch.Tensor:
    bridge = heading @ root_rotation.transpose(-1, -2)
    position = torch.matmul(transform[:, :3].unsqueeze(1), bridge).squeeze(1)
    rotation = tl.rotation_6d_to_matrix(transform[:, 3:9]) @ bridge
    return torch.cat((position, tl.rotmat_to_6d(rotation)), dim=-1)


def root_transform_to_heading(
    transform: torch.Tensor,
    root_rotation: torch.Tensor,
    heading: torch.Tensor,
) -> torch.Tensor:
    bridge = root_rotation @ heading.transpose(-1, -2)
    position = torch.matmul(transform[:, :3].unsqueeze(1), bridge).squeeze(1)
    rotation = tl.rotation_6d_to_matrix(transform[:, 3:9]) @ bridge
    return torch.cat((position, tl.rotmat_to_6d(rotation)), dim=-1)


def upper_heading_state_to_root(
    upper: torch.Tensor,
    root_rotation: torch.Tensor,
    heading: torch.Tensor,
) -> torch.Tensor:
    bridge = heading @ root_rotation.transpose(-1, -2)
    parts: list[torch.Tensor] = [upper[:, :60]]
    for start in (60, 75):
        position = torch.matmul(upper[:, start : start + 3].unsqueeze(1), bridge).squeeze(1)
        hand_rotation = tl.rotation_6d_to_matrix(upper[:, start + 3 : start + 9]) @ bridge
        upperarm_rotation = tl.rotation_6d_to_matrix(upper[:, start + 9 : start + 15]) @ bridge
        parts.append(
            torch.cat(
                (
                    position,
                    tl.rotmat_to_6d(hand_rotation),
                    tl.rotmat_to_6d(upperarm_rotation),
                ),
                dim=-1,
            )
        )
    return upper_data.clean_upper_state(torch.cat(parts, dim=-1))


def pelvis_proposal(frozen_next: torch.Tensor) -> torch.Tensor:
    """The zero-delta base is exactly the live frozen-lower next proposal."""

    return clean_transform(frozen_next)


def apply_agent_output(
    upper_prior: torch.Tensor,
    pelvis_prior: torch.Tensor,
    raw_output: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    if raw_output.shape[-1] != AGENT_OUTPUT_DIM:
        raise ValueError(
            f"Expected agent output width {AGENT_OUTPUT_DIM}, got {raw_output.shape[-1]}"
        )
    upper = upper_data.clean_upper_state(upper_prior + raw_output[:, :UPPER_OUTPUT_DIM])
    pelvis_delta = raw_output[:, UPPER_OUTPUT_DIM:]
    pelvis = clean_transform(pelvis_prior + pelvis_delta)
    # Preserve the literal delta-zero contract bit-for-bit.  Re-cleaning an
    # already-clean 6D rotation can otherwise introduce roundoff large enough
    # to make feedback take the controlled branch on isolated frames.
    exact_zero = (pelvis_delta == 0.0).all(dim=-1, keepdim=True)
    # Forward value: literal prior at delta zero. Backward value: retain the
    # derivative of the cleaned proposal so the zero-initialized pelvis head
    # can learn on its very first optimizer step.
    zero_exact_with_clean_gradient = pelvis + (pelvis_prior - pelvis).detach()
    pelvis = torch.where(exact_zero, zero_exact_with_clean_gradient, pelvis)
    applied = torch.cat((upper - upper_prior, pelvis - pelvis_prior), dim=-1)
    return upper, pelvis, applied


def _payload_chunk(payload: torch.Tensor, spec: dict[str, object]) -> torch.Tensor:
    start = int(cast_slice(spec["pos"]).start)
    toe = spec.get("toe_float")
    end_slice = cast_slice(toe) if toe is not None else cast_slice(spec["start_rot6"])
    return payload[:, start : int(end_slice.stop)]


def cast_slice(value: object) -> slice:
    if not isinstance(value, slice):
        raise TypeError(f"Expected slice, got {type(value).__name__}")
    return value


def _compose_full_vector(
    full_clip: tl.MotionClip,
    lower_clip: tl.MotionClip,
    lower_vec: torch.Tensor,
    upper_heading: torch.Tensor,
    pelvis_heading: torch.Tensor,
    root_rotation: torch.Tensor,
    heading: torch.Tensor,
) -> torch.Tensor:
    upper = upper_heading_state_to_root(upper_heading, root_rotation, heading)
    pelvis = heading_transform_to_root(pelvis_heading, root_rotation, heading)
    batch = int(lower_vec.shape[0])
    full = lower_vec.new_zeros((batch, 9 + full_clip.Jcore * 6 + full_clip.ik_payload_dim))
    full[:, :9] = pelvis

    core_by_name = {
        name: upper[:, slot * 6 : (slot + 1) * 6]
        for slot, name in enumerate(upper_data.CORE_BONES)
    }
    for slot, body_index in enumerate(full_clip.core_non_pelvis):
        full[:, 9 + slot * 6 : 9 + (slot + 1) * 6] = core_by_name[
            full_clip.body_names[body_index]
        ]

    lower_payload = lower_vec[:, 9:]
    legs = {
        str(spec["side"]): _payload_chunk(lower_payload, spec)
        for spec in lower_clip.ik_payload_slices
        if str(spec.get("kind", "")) == "leg"
    }
    arms = {"l": upper[:, 60:75], "r": upper[:, 75:90]}
    chunks = [
        arms[str(spec["side"])]
        if str(spec["kind"]) == "arm"
        else legs[str(spec["side"])]
        for spec in full_clip.ik_payload_slices
    ]
    full[:, 9 + full_clip.Jcore * 6 :] = torch.cat(chunks, dim=-1)
    return full


def _direct_knee(
    hip: torch.Tensor,
    ankle: torch.Tensor,
    original_hip: torch.Tensor,
    original_knee: torch.Tensor,
    original_ankle: torch.Tensor,
    upper_length: torch.Tensor,
    lower_length: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    original_axis = tl.normalize(original_ankle - original_hip)
    original_pole = tl.project_to_plane(original_knee - original_hip, original_axis)
    pole_target = original_knee + original_pole * float(POLE_TARGET_DISTANCE_M)

    raw = ankle - hip
    raw_distance = torch.linalg.norm(raw, dim=-1, keepdim=True)
    fallback_axis = original_axis
    axis = torch.where(raw_distance > 1.0e-8, tl.normalize(raw), fallback_axis)
    distance = raw_distance.clamp_min(1.0e-8)
    upper = upper_length.unsqueeze(-1)
    lower = lower_length.unsqueeze(-1)
    along = (upper.square() - lower.square() + distance.square()) / (2.0 * distance)
    height_sq = (upper.square() - along.square()).clamp_min(0.0)
    # At a fully extended leg height_sq is exactly zero.  sqrt(0) has an
    # infinite derivative, so an otherwise valid forward IK pose can inject a
    # NaN into an autoregressive controller gradient.  Keep the exact forward
    # value while selecting a zero derivative at that non-differentiable
    # boundary; this does not clamp the controlled pelvis or leg motion.
    height = torch.where(
        height_sq > 0.0,
        torch.sqrt(height_sq.clamp_min(1.0e-12)),
        torch.zeros_like(height_sq),
    )

    pole_raw = pole_target - hip
    pole_raw = pole_raw - axis * (pole_raw * axis).sum(dim=-1, keepdim=True)
    fallback_pole = original_pole - axis * (original_pole * axis).sum(
        dim=-1, keepdim=True
    )
    stable = tl.stable_perpendicular(axis)
    pole = torch.where(
        torch.linalg.norm(pole_raw, dim=-1, keepdim=True) > 1.0e-7,
        tl.normalize(pole_raw),
        torch.where(
            torch.linalg.norm(fallback_pole, dim=-1, keepdim=True) > 1.0e-7,
            tl.normalize(fallback_pole),
            stable,
        ),
    )
    return hip + axis * along + pole * height, pole


def feedback_lower_state(
    lower_clip: tl.MotionClip,
    lower_proposal: torch.Tensor,
    controlled_pelvis_heading: torch.Tensor,
    root_position: torch.Tensor,
    root_rotation: torch.Tensor,
    heading: torch.Tensor,
    geometry_tensors: dict[str, torch.Tensor] | None = None,
    force_solve: torch.Tensor | None = None,
) -> torch.Tensor:
    """Write controlled pelvis and consistent locked-foot leg IK into lower state.

    This returned vector is the state consumed by the frozen lower NN on its
    next autoregressive step.  End-effector position/rotation/toe values are
    copied unchanged from ``lower_proposal``.  If the controlled pelvis equals
    the lower proposal, the original row is returned bit-for-bit so delta zero
    has literal untouched-lower semantics. ``force_solve`` lets a caller that
    already changed an end effector request the same solve even when pelvis is
    unchanged; false rows preserve the literal zero-delta path.
    """

    frozen_pelvis_heading = root_transform_to_heading(
        lower_proposal[:, :9], root_rotation, heading
    )
    controlled_pelvis_heading = clean_transform(controlled_pelvis_heading)
    untouched = (
        (controlled_pelvis_heading - frozen_pelvis_heading)
        .abs()
        .amax(dim=-1)
        <= 1.0e-7
    )
    if force_solve is not None:
        requested = force_solve.to(device=untouched.device, dtype=torch.bool).reshape(-1)
        if tuple(requested.shape) != tuple(untouched.shape):
            raise ValueError(
                f"force_solve shape {tuple(requested.shape)} != batch {tuple(untouched.shape)}"
            )
        untouched = untouched & ~requested

    original_pose, _ = tl.output_to_pose(lower_proposal, lower_clip)
    original_positions, original_rotations, _ = tl.fk_from_pose(
        lower_clip,
        root_position,
        root_rotation,
        original_pose,
        lower_proposal.device,
        geometry_tensors=geometry_tensors,
    )
    result = lower_proposal.clone()
    controlled_pelvis_root = heading_transform_to_root(
        controlled_pelvis_heading, root_rotation, heading
    )
    result[:, :9] = controlled_pelvis_root
    pelvis_world_position = (
        torch.matmul(
            controlled_pelvis_root[:, :3].unsqueeze(1), root_rotation
        ).squeeze(1)
        + root_position
    )
    pelvis_world_rotation = (
        tl.rotation_6d_to_matrix(controlled_pelvis_root[:, 3:9]) @ root_rotation
    )
    tensors = lower_clip.tensors(lower_proposal.device)
    if geometry_tensors is not None:
        tensors = {**tensors, **geometry_tensors}
    offsets = tensors["local_offsets"].to(
        dtype=lower_proposal.dtype, device=lower_proposal.device
    )
    lengths = tensors["ik_limb_lengths"].to(
        dtype=lower_proposal.dtype, device=lower_proposal.device
    )
    local_poles = tensors["ik_local_pole_axis"].to(
        dtype=lower_proposal.dtype, device=lower_proposal.device
    )
    batch = int(lower_proposal.shape[0])
    if offsets.ndim == 2:
        offsets = offsets.unsqueeze(0).expand(batch, -1, -1)
    if lengths.ndim == 2:
        lengths = lengths.unsqueeze(0).expand(batch, -1, -1)
    if local_poles.ndim == 3:
        local_poles = local_poles.unsqueeze(0).expand(batch, -1, -1, -1)
    payload_offset = 9 + lower_clip.Jcore * 6
    for limb_index, (limb, payload_spec) in enumerate(
        zip(lower_clip.ik_limb_specs, lower_clip.ik_payload_slices)
    ):
        if str(limb["kind"]) != "leg":
            continue
        start = int(limb["start"])
        mid = int(limb["mid"])
        end = int(limb["end"])
        hip = (
            torch.matmul(
                offsets[:, start].unsqueeze(1), pelvis_world_rotation
            ).squeeze(1)
            + pelvis_world_position
        )
        knee, pole = _direct_knee(
            hip,
            original_positions[:, end],
            original_positions[:, start],
            original_positions[:, mid],
            original_positions[:, end],
            lengths[:, limb_index, 0],
            lengths[:, limb_index, 1],
        )
        controlled_solved_world_rotation = tl.rotation_from_axis_and_pole(
            offsets[:, mid],
            knee - hip,
            local_poles[:, limb_index, 0],
            pole,
        )
        baseline_knee, baseline_pole = _direct_knee(
            original_positions[:, start],
            original_positions[:, end],
            original_positions[:, start],
            original_positions[:, mid],
            original_positions[:, end],
            lengths[:, limb_index, 0],
            lengths[:, limb_index, 1],
        )
        baseline_solved_world_rotation = tl.rotation_from_axis_and_pole(
            offsets[:, mid],
            baseline_knee - original_positions[:, start],
            local_poles[:, limb_index, 0],
            baseline_pole,
        )
        # The absolute direct solve may use a different but equivalent twist
        # representation from the frozen lower row.  Writing it directly made
        # feedback discontinuous: an arbitrarily small non-zero pelvis delta
        # replaced the authored thigh rotation with that alternate solution.
        # Apply only the controlled-vs-baseline solve delta to the original
        # world rotation so zero is exact and nearby controls remain nearby.
        solve_delta = (
            baseline_solved_world_rotation.transpose(-1, -2)
            @ controlled_solved_world_rotation
        )
        start_world_rotation = original_rotations[:, start] @ solve_delta
        start_root_rotation = (
            start_world_rotation @ root_rotation.transpose(-1, -2)
        )
        start_slice = cast_slice(payload_spec["start_rot6"])
        result[
            :,
            payload_offset + start_slice.start : payload_offset + start_slice.stop,
        ] = tl.rotmat_to_6d(start_root_rotation)

    return torch.where(untouched[:, None], lower_proposal, result)


def decode_full_pose(
    full_clip: tl.MotionClip,
    lower_clip: tl.MotionClip,
    lower_vec: torch.Tensor,
    upper_heading: torch.Tensor,
    pelvis_heading: torch.Tensor,
    root_position: torch.Tensor,
    root_rotation: torch.Tensor,
    heading: torch.Tensor,
    geometry_tensors: dict[str, torch.Tensor] | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Decode upper+pelvis while freezing feet and directly resolving legs."""

    frozen_pelvis = root_transform_to_heading(
        lower_vec[:, :9], root_rotation, heading
    )
    original_full = _compose_full_vector(
        full_clip,
        lower_clip,
        lower_vec,
        upper_heading,
        frozen_pelvis,
        root_rotation,
        heading,
    )
    original_pose, _ = tl.output_to_pose(original_full, full_clip)
    original_positions, _original_rotations, _ = tl.fk_from_pose(
        full_clip,
        root_position,
        root_rotation,
        original_pose,
        lower_vec.device,
        geometry_tensors=geometry_tensors,
    )

    full = _compose_full_vector(
        full_clip,
        lower_clip,
        lower_vec,
        upper_heading,
        pelvis_heading,
        root_rotation,
        heading,
    )
    pelvis_root = heading_transform_to_root(pelvis_heading, root_rotation, heading)
    pelvis_world_position = (
        torch.matmul(pelvis_root[:, :3].unsqueeze(1), root_rotation).squeeze(1)
        + root_position
    )
    pelvis_world_rotation = tl.rotation_6d_to_matrix(pelvis_root[:, 3:9]) @ root_rotation
    tensors = full_clip.tensors(lower_vec.device)
    if geometry_tensors is not None:
        tensors = {**tensors, **geometry_tensors}
    offsets = tensors["local_offsets"].to(dtype=lower_vec.dtype, device=lower_vec.device)
    lengths = tensors["ik_limb_lengths"].to(dtype=lower_vec.dtype, device=lower_vec.device)
    local_poles = tensors["ik_local_pole_axis"].to(
        dtype=lower_vec.dtype, device=lower_vec.device
    )
    batch = int(lower_vec.shape[0])
    if offsets.ndim == 2:
        offsets = offsets.unsqueeze(0).expand(batch, -1, -1)
    if lengths.ndim == 2:
        lengths = lengths.unsqueeze(0).expand(batch, -1, -1)
    if local_poles.ndim == 3:
        local_poles = local_poles.unsqueeze(0).expand(batch, -1, -1, -1)
    payload_offset = 9 + full_clip.Jcore * 6

    for limb_index, (limb, payload_spec) in enumerate(
        zip(full_clip.ik_limb_specs, full_clip.ik_payload_slices)
    ):
        if str(limb["kind"]) != "leg":
            continue
        start = int(limb["start"])
        mid = int(limb["mid"])
        end = int(limb["end"])
        if full_clip.parents_body_list[start] != full_clip.pelvis:
            raise RuntimeError(
                f"Expected {full_clip.body_names[start]} to be parented to pelvis"
            )
        hip = (
            torch.matmul(offsets[:, start].unsqueeze(1), pelvis_world_rotation).squeeze(1)
            + pelvis_world_position
        )
        ankle = original_positions[:, end]
        knee, pole = _direct_knee(
            hip,
            ankle,
            original_positions[:, start],
            original_positions[:, mid],
            original_positions[:, end],
            lengths[:, limb_index, 0],
            lengths[:, limb_index, 1],
        )
        start_world_rotation = tl.rotation_from_axis_and_pole(
            offsets[:, mid],
            knee - hip,
            local_poles[:, limb_index, 0],
            pole,
        )
        start_root_rotation = start_world_rotation @ root_rotation.transpose(-1, -2)
        start_slice = cast_slice(payload_spec["start_rot6"])
        full[:, payload_offset + start_slice.start : payload_offset + start_slice.stop] = (
            tl.rotmat_to_6d(start_root_rotation)
        )

    pose, _ = tl.output_to_pose(full, full_clip)
    positions, rotations, _ = tl.fk_from_pose(
        full_clip,
        root_position,
        root_rotation,
        pose,
        lower_vec.device,
        geometry_tensors=geometry_tensors,
    )
    return positions, rotations


@torch.no_grad()
def authored_decoded_transition_delta(
    full_clip: tl.MotionClip,
    lower_clip: tl.MotionClip,
    cfg: tl.TrainConfig,
    current: torch.Tensor,
    gaze: torch.Tensor,
) -> torch.Tensor:
    """Reachable GT transition produced by the exact upper runtime decoder."""

    following = current + 1
    all_indices = torch.cat((current, following), dim=0)
    logical = tl.logical_pose_index(full_clip, all_indices, torch.device("cpu"))
    repeated_gaze = gaze.repeat(2, 1)
    upper = upper_data.gaze_overlay_upper_state(full_clip, logical, repeated_gaze)
    lower_pose = tl.get_pose_from_clip(lower_clip, all_indices, torch.device("cpu"))
    lower_vector = tl.pose_target_output(lower_pose)
    root_position, root_rotation, _yaw, heading = tl.root_state(
        full_clip, all_indices, cfg, torch.device("cpu")
    )
    pelvis = root_transform_to_heading(
        lower_vector[:, :9], root_rotation, heading
    )
    positions, rotations = decode_full_pose(
        full_clip,
        lower_clip,
        lower_vector,
        upper,
        pelvis,
        root_position,
        root_rotation,
        heading,
    )
    count = int(current.numel())
    current_pose = physical_pose_from_globals(
        full_clip,
        positions[:count],
        rotations[:count],
        root_position[:count],
        root_rotation[:count],
    )
    following_pose = physical_pose_from_globals(
        full_clip,
        positions[count:],
        rotations[count:],
        root_position[:count],
        root_rotation[:count],
    )
    return following_pose - current_pose


@torch.no_grad()
def authored_decoded_physical_states(
    full_clip: tl.MotionClip,
    lower_clip: tl.MotionClip,
    cfg: tl.TrainConfig,
    frames: torch.Tensor,
    gaze: torch.Tensor,
) -> torch.Tensor:
    """Return reachable authored states in each frame's own actual-root frame."""

    logical = tl.logical_pose_index(full_clip, frames, torch.device("cpu"))
    upper = upper_data.gaze_overlay_upper_state(full_clip, logical, gaze)
    lower_pose = tl.get_pose_from_clip(lower_clip, frames, torch.device("cpu"))
    lower_vector = tl.pose_target_output(lower_pose)
    root_position, root_rotation, _yaw, heading = tl.root_state(
        full_clip, frames, cfg, torch.device("cpu")
    )
    pelvis = root_transform_to_heading(lower_vector[:, :9], root_rotation, heading)
    positions, rotations = decode_full_pose(
        full_clip,
        lower_clip,
        lower_vector,
        upper,
        pelvis,
        root_position,
        root_rotation,
        heading,
    )
    return physical_pose_from_globals(
        full_clip,
        positions,
        rotations,
        root_position,
        root_rotation,
    )


@torch.no_grad()
def authored_decoded_two_row_deltas(
    full_clip: tl.MotionClip,
    lower_clip: tl.MotionClip,
    cfg: tl.TrainConfig,
    first_current: torch.Tensor,
    gaze: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Decode t,t+1,t+2 once and return the two consecutive GT deltas."""

    frames = torch.cat(
        (first_current, first_current + 1, first_current + 2), dim=0
    )
    logical = tl.logical_pose_index(full_clip, frames, torch.device("cpu"))
    upper = upper_data.gaze_overlay_upper_state(full_clip, logical, gaze.repeat(3, 1))
    lower_pose = tl.get_pose_from_clip(lower_clip, frames, torch.device("cpu"))
    lower_vector = tl.pose_target_output(lower_pose)
    root_position, root_rotation, _yaw, heading = tl.root_state(
        full_clip, frames, cfg, torch.device("cpu")
    )
    pelvis = root_transform_to_heading(lower_vector[:, :9], root_rotation, heading)
    positions, rotations = decode_full_pose(
        full_clip,
        lower_clip,
        lower_vector,
        upper,
        pelvis,
        root_position,
        root_rotation,
        heading,
    )
    count = int(first_current.numel())
    poses = []
    for slot in range(3):
        selection = slice(slot * count, (slot + 1) * count)
        poses.append(
            physical_pose_from_globals(
                full_clip,
                positions[selection],
                rotations[selection],
                root_position[selection],
                root_rotation[selection],
            )
        )
    second_in_first = reframe_physical_pose(
        poses[1],
        root_position[count : 2 * count],
        root_rotation[count : 2 * count],
        root_position[:count],
        root_rotation[:count],
    )
    third_in_second = reframe_physical_pose(
        poses[2],
        root_position[2 * count :],
        root_rotation[2 * count :],
        root_position[count : 2 * count],
        root_rotation[count : 2 * count],
    )
    return second_in_first - poses[0], third_in_second - poses[1]


def physical_transition_from_decoded(
    clip: tl.MotionClip,
    current_positions: torch.Tensor,
    current_rotations: torch.Tensor,
    next_positions: torch.Tensor,
    next_rotations: torch.Tensor,
    current_root_position: torch.Tensor,
    current_root_rotation: torch.Tensor,
) -> torch.Tensor:
    current = physical_pose_from_globals(
        clip,
        current_positions,
        current_rotations,
        current_root_position,
        current_root_rotation,
    )
    following = physical_pose_from_globals(
        clip,
        next_positions,
        next_rotations,
        current_root_position,
        current_root_rotation,
    )
    return following - current


def foot_indices(clip: tl.MotionClip) -> tuple[int, int]:
    by_name = {name: index for index, name in enumerate(clip.body_names)}
    return by_name["foot_l"], by_name["foot_r"]


def leg_indices(clip: tl.MotionClip) -> tuple[int, ...]:
    by_name = {name: index for index, name in enumerate(clip.body_names)}
    return tuple(by_name[name] for name in ("thigh_l", "calf_l", "thigh_r", "calf_r"))


def physical_indices(clip: tl.MotionClip) -> torch.Tensor:
    by_name = {name: index for index, name in enumerate(clip.body_names)}
    return torch.tensor([by_name[name] for name in PHYSICAL_BONES], dtype=torch.long)


def validate_bones(clips: Iterable[tl.MotionClip]) -> None:
    for clip in clips:
        missing = [name for name in PHYSICAL_BONES if name not in clip.body_names]
        if missing:
            raise RuntimeError(f"Missing physical bones in {clip.path}: {missing}")
