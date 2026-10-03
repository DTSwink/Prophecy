from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import time
from dataclasses import asdict
from pathlib import Path

import torch

try:
    from .bootstrap import PROJECT_ROOT, ensure_paths
    from .naming import checkpoint_path, ik_run_id
    from . import ik_core as tl
    from .train_simple_autoencoder import SimpleAEConfig, SimpleAutoencoder, lr_for_step
except ImportError:
    from bootstrap import PROJECT_ROOT, ensure_paths
    from naming import checkpoint_path, ik_run_id
    import ik_core as tl
    from train_simple_autoencoder import SimpleAEConfig, SimpleAutoencoder, lr_for_step


ensure_paths()

ORIGINAL_ROOT = (
    PROJECT_ROOT
    / "training"
    / "slashes2"
    / "walk_run_sword_prep"
    / "authored_pruned_npz"
)
SWORD_ROOT = (
    PROJECT_ROOT
    / "training"
    / "slashes2"
    / "walk_run_sword_prep"
    / "holding_sword_npz"
)
CACHE_ROOT = PROJECT_ROOT / "training" / "runs" / "cache" / "upper_pose_ae"
RUNS_ROOT = PROJECT_ROOT / "training" / "runs"

CACHE_VERSION = "upper_pose_ae_rows_v2_gaze_feet"
CORE_BONES = (
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
)
ARM_SPECS = (
    ("l", "upperarm_l", "lowerarm_l", "hand_l"),
    ("r", "upperarm_r", "lowerarm_r", "hand_r"),
)

POSE_DIM = 90
PELVIS_DIM = 9
ROOT_DIM = 35
FOOT_TRANSFORM_DIM = 9
FOOT_PAIR_DIM = FOOT_TRANSFORM_DIM * 2
FOOT_CONDITIONING_DIM = FOOT_PAIR_DIM * 2
GAZE_DIM = 2
GAZE_YAW_LIMIT_DEG = 170.0
GAZE_PITCH_LIMIT_DEG = 85.0
GAZE_ZERO_PROBABILITY = 0.05
GAZE_BODY_PITCH_MULTIPLIER = 1.0
GAZE_DATA_SEED = 1234
INPUT_DIM = (
    POSE_DIM * 2
    + PELVIS_DIM * 3
    + ROOT_DIM
    + 1
    + FOOT_CONDITIONING_DIM
    + GAZE_DIM
)
OUTPUT_DIM = POSE_DIM
ROW_DIM = INPUT_DIM + OUTPUT_DIM
WINDOW_FRAMES = 2
WINDOW_DIM = ROW_DIM * WINDOW_FRAMES
CURRENT_FEET_START = POSE_DIM * 2 + PELVIS_DIM * 3 + ROOT_DIM + 1
NEXT_FEET_START = CURRENT_FEET_START + FOOT_PAIR_DIM
GAZE_START = NEXT_FEET_START + FOOT_PAIR_DIM
NEWEST_OUTPUT_START = ROW_DIM + INPUT_DIM
NEWEST_OUTPUT_END = NEWEST_OUTPUT_START + OUTPUT_DIM

GAZE_CHAIN = (
    "spine_01",
    "spine_02",
    "spine_03",
    "spine_04",
    "spine_05",
    "neck_01",
    "neck_02",
    "head",
)


def motion_config() -> tl.TrainConfig:
    cfg = tl.TrainConfig()
    cfg.fps = 30
    cfg.position_unit_scale = 0.01
    cfg.max_speed_scale = 5.0
    cfg.max_turn_rate_per_sec_scale = 4.0 * math.pi
    cfg.future_window_seconds = 0.25
    cfg.pose_representation = tl.IK_POSE_REPRESENTATION
    cfg.body_mode = tl.BODY_MODE_FULL
    cfg.live_viewer = False
    cfg.visual_reporter = False
    cfg.update_comparison_on_exit = False
    cfg.use_torch_compile = False
    cfg.device = "cpu"
    if int(cfg.future_window) != 8:
        raise RuntimeError(f"Expected eight future roots, got {cfg.future_window}")
    return cfg


def dataset_files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path.resolve()
        for path in sorted(root.rglob("*.npz"))
    }


def matched_dataset() -> tuple[list[tuple[str, Path, bool]], list[tuple[str, Path, bool]], str]:
    original = dataset_files(ORIGINAL_ROOT)
    sword = dataset_files(SWORD_ROOT)
    if len(original) != 465 or len(sword) != 465:
        raise RuntimeError(
            f"Expected 465 matched clips per corpus, got original={len(original)} sword={len(sword)}"
        )
    if original.keys() != sword.keys():
        only_original = sorted(original.keys() - sword.keys())
        only_sword = sorted(sword.keys() - original.keys())
        raise RuntimeError(
            "Dataset pairing mismatch: "
            f"only_original={only_original[:3]} only_sword={only_sword[:3]}"
        )

    digest = hashlib.sha256()
    digest.update(CACHE_VERSION.encode("utf-8"))
    original_specs: list[tuple[str, Path, bool]] = []
    sword_specs: list[tuple[str, Path, bool]] = []
    for relative in original:
        cyclic = relative.split("/", 1)[0].endswith("_omni")
        original_path = original[relative]
        sword_path = sword[relative]
        original_stat = original_path.stat()
        sword_stat = sword_path.stat()
        digest.update(relative.encode("utf-8"))
        digest.update(
            f"{original_stat.st_size}:{original_stat.st_mtime_ns}:"
            f"{sword_stat.st_size}:{sword_stat.st_mtime_ns}:{int(cyclic)}".encode("ascii")
        )
        original_specs.append((relative, original_path, cyclic))
        sword_specs.append((relative, sword_path, cyclic))
    return original_specs, sword_specs, digest.hexdigest()


def root_relative_position(
    world: torch.Tensor,
    root_pos: torch.Tensor,
    root_heading: torch.Tensor,
) -> torch.Tensor:
    return torch.matmul(
        (world - root_pos).unsqueeze(1), root_heading.transpose(-1, -2)
    ).squeeze(1)


def root_relative_rotation(world: torch.Tensor, root_heading: torch.Tensor) -> torch.Tensor:
    return world @ root_heading.transpose(-1, -2)


def clean_upper_state(values: torch.Tensor) -> torch.Tensor:
    if values.ndim != 2 or int(values.shape[1]) != POSE_DIM:
        raise ValueError(f"Expected [N,{POSE_DIM}] upper state, got {tuple(values.shape)}")
    count = int(values.shape[0])
    core = tl.clean_6d(values[:, :60].reshape(-1, 6)).reshape(count, 60)
    arms: list[torch.Tensor] = []
    for start in (60, 75):
        arms.append(
            torch.cat(
                (
                    values[:, start : start + 3],
                    tl.clean_6d(values[:, start + 3 : start + 9]),
                    tl.clean_6d(values[:, start + 9 : start + 15]),
                ),
                dim=-1,
            )
        )
    return torch.cat((core, *arms), dim=-1)


def upper_state_from_clip(clip: tl.MotionClip) -> torch.Tensor:
    by_name = {name: index for index, name in enumerate(clip.body_names)}
    heading = clip.root_heading_rot
    core = torch.cat(
        [clip.local_rot6[:, by_name[name]] for name in CORE_BONES], dim=-1
    )
    parts: list[torch.Tensor] = [core]
    for _side, upper_name, _lower_name, hand_name in ARM_SPECS:
        upper = by_name[upper_name]
        hand = by_name[hand_name]
        parts.extend(
            (
                root_relative_position(
                    clip.global_pos[:, hand], clip.root_pos, heading
                ),
                tl.rotmat_to_6d(
                    root_relative_rotation(clip.global_rot[:, hand], heading)
                ),
                tl.rotmat_to_6d(
                    root_relative_rotation(clip.global_rot[:, upper], heading)
                ),
            )
        )
    return clean_upper_state(torch.cat(parts, dim=-1))


def upper_state_from_global_pose_and_heading(
    clip: tl.MotionClip,
    global_pos: torch.Tensor,
    global_rot: torch.Tensor,
    root_pos: torch.Tensor,
    root_heading: torch.Tensor,
) -> torch.Tensor:
    by_name = {name: index for index, name in enumerate(clip.body_names)}
    local_core: list[torch.Tensor] = []
    for name in CORE_BONES:
        joint = by_name[name]
        parent = int(clip.parents_body_list[joint])
        local = (
            global_rot[:, joint]
            if parent < 0
            else global_rot[:, joint] @ global_rot[:, parent].transpose(-1, -2)
        )
        local_core.append(tl.rotmat_to_6d(local))

    parts: list[torch.Tensor] = [torch.cat(local_core, dim=-1)]
    for _side, upper_name, _lower_name, hand_name in ARM_SPECS:
        upper = by_name[upper_name]
        hand = by_name[hand_name]
        parts.extend(
            (
                root_relative_position(global_pos[:, hand], root_pos, root_heading),
                tl.rotmat_to_6d(
                    root_relative_rotation(global_rot[:, hand], root_heading)
                ),
                tl.rotmat_to_6d(
                    root_relative_rotation(global_rot[:, upper], root_heading)
                ),
            )
        )
    return clean_upper_state(torch.cat(parts, dim=-1))


def _rotate_vectors_about_axis(
    vectors: torch.Tensor,
    axis: torch.Tensor,
    angle: torch.Tensor,
) -> torch.Tensor:
    axis = tl.normalize(axis)
    while axis.ndim < vectors.ndim:
        axis = axis.unsqueeze(1)
    while angle.ndim < vectors.ndim - 1:
        angle = angle.unsqueeze(1)
    angle = angle.unsqueeze(-1)
    cosine = torch.cos(angle)
    sine = torch.sin(angle)
    expanded_axis = axis.expand_as(vectors)
    projection = (expanded_axis * vectors).sum(dim=-1, keepdim=True)
    return (
        vectors * cosine
        + torch.cross(expanded_axis, vectors, dim=-1) * sine
        + expanded_axis * projection * (1.0 - cosine)
    )


def _descendants(clip: tl.MotionClip, subtree_root: int) -> list[int]:
    result: list[int] = []
    for joint in range(len(clip.body_names)):
        cursor = joint
        while cursor >= 0:
            if cursor == int(subtree_root):
                result.append(joint)
                break
            cursor = int(clip.parents_body_list[cursor])
    return result


_SUBTREE_INDEX_CACHE: dict[
    tuple[int, int, str], tuple[torch.Tensor, torch.Tensor]
] = {}


def _subtree_index_tensors(
    clip: tl.MotionClip,
    subtree_root: int,
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Cache topology indices before capture; subsequent graph calls reuse them."""

    key = (id(clip), int(subtree_root), str(device))
    cached = _SUBTREE_INDEX_CACHE.get(key)
    if cached is not None:
        return cached
    descendants = _descendants(clip, subtree_root)
    moving = [joint for joint in descendants if joint != int(subtree_root)]
    cached = (
        torch.tensor(moving, dtype=torch.long, device=device),
        torch.tensor(descendants, dtype=torch.long, device=device),
    )
    _SUBTREE_INDEX_CACHE[key] = cached
    return cached


def _rotate_pose_subtree(
    clip: tl.MotionClip,
    positions: torch.Tensor,
    rotations: torch.Tensor,
    subtree_root: int,
    axis: torch.Tensor,
    angle: torch.Tensor,
    pivot_override: torch.Tensor | None = None,
) -> None:
    moving_index, descendant_index = _subtree_index_tensors(
        clip, subtree_root, positions.device
    )
    pivot = positions[:, subtree_root] if pivot_override is None else pivot_override
    if int(moving_index.numel()):
        relative = positions.index_select(1, moving_index) - pivot[:, None, :]
        positions[:, moving_index] = pivot[:, None, :] + _rotate_vectors_about_axis(
            relative, axis, angle
        )
    rotations[:, descendant_index] = _rotate_vectors_about_axis(
        rotations.index_select(1, descendant_index), axis, angle
    )


def _correct_pose_subtree_frame(
    clip: tl.MotionClip,
    positions: torch.Tensor,
    rotations: torch.Tensor,
    subtree_root: int,
    target_axes: torch.Tensor,
) -> None:
    moving_index, descendant_index = _subtree_index_tensors(
        clip, subtree_root, positions.device
    )
    current_axes = rotations[:, subtree_root]
    correction = current_axes.transpose(-1, -2) @ target_axes
    pivot = positions[:, subtree_root]
    if int(moving_index.numel()):
        relative = positions.index_select(1, moving_index) - pivot[:, None, :]
        positions[:, moving_index] = pivot[:, None, :] + torch.matmul(
            relative.unsqueeze(-2), correction[:, None]
        ).squeeze(-2)
    rotations[:, descendant_index] = (
        rotations.index_select(1, descendant_index) @ correction[:, None]
    )


def apply_gaze_overlay_global_pose(
    clip: tl.MotionClip,
    source_positions: torch.Tensor,
    source_rotations: torch.Tensor,
    gaze_normalized: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Apply the accepted gaze overlay to already selected global poses."""

    row_count = int(source_positions.shape[0])
    if source_positions.ndim != 3 or source_positions.shape[-1] != 3:
        raise ValueError(
            f"Expected global positions [N,J,3], got {tuple(source_positions.shape)}"
        )
    if source_rotations.shape != source_positions.shape[:-1] + (3, 3):
        raise ValueError(
            f"Expected global rotations [N,J,3,3], got {tuple(source_rotations.shape)}"
        )
    if gaze_normalized.shape != (row_count, GAZE_DIM):
        raise ValueError(
            f"Expected gaze [{row_count},{GAZE_DIM}], got "
            f"{tuple(gaze_normalized.shape)}"
        )
    positions = source_positions.clone()
    rotations = source_rotations.clone()
    by_name = {name: index for index, name in enumerate(clip.body_names)}
    chain = [by_name[name] for name in GAZE_CHAIN]
    weights = torch.arange(
        1, len(chain) + 1, dtype=positions.dtype, device=positions.device
    )
    # These are topology constants, not tensor data.  Keep them as Python
    # scalars so the dynamic-gaze overlay remains CUDA-Graph capture safe.
    weight_total = float(sum(range(1, len(chain) + 1)))
    yaw = gaze_normalized[:, 0] * math.radians(GAZE_YAW_LIMIT_DEG)
    pitch = gaze_normalized[:, 1] * math.radians(GAZE_PITCH_LIMIT_DEG)
    head = by_name["head"]
    neck2 = by_name["neck_02"]

    for chain_index, joint in enumerate(chain):
        contribution = yaw * float(chain_index + 1) / weight_total
        pivot = positions[:, neck2] if joint == head else None
        _rotate_pose_subtree(
            clip,
            positions,
            rotations,
            joint,
            rotations[:, joint, 0].clone(),
            contribution,
            pivot_override=pivot,
        )

    spine05 = by_name["spine_05"]
    neck_pitch_joints = {by_name["neck_01"], by_name["neck_02"]}
    spine05_yaw_frame = rotations[:, spine05].clone()
    lower_spine_pitch = torch.zeros_like(pitch)
    for chain_index, joint in enumerate(chain[:-1]):
        if joint == spine05 or joint in neck_pitch_joints:
            continue
        contribution = (
            pitch
            * float(chain_index + 1)
            / weight_total
            * float(GAZE_BODY_PITCH_MULTIPLIER)
        )
        lower_spine_pitch += contribution
        _rotate_pose_subtree(
            clip,
            positions,
            rotations,
            joint,
            rotations[:, joint, 2].clone(),
            contribution,
        )
    # Always apply the frame correction.  At zero pitch this is the identity;
    # avoiding a tensor-to-Python branch also keeps the dynamic-gaze overlay
    # valid inside a CUDA Graph capture.
    _correct_pose_subtree_frame(
        clip, positions, rotations, spine05, spine05_yaw_frame
    )

    neck_pitch_target = pitch * 0.60
    neck_weight_total = sum(
        float(index + 1)
        for index, joint in enumerate(chain)
        if joint in neck_pitch_joints
    )
    neck_pitch_applied = torch.zeros_like(pitch)
    for chain_index, joint in enumerate(chain[:-1]):
        if joint not in neck_pitch_joints:
            continue
        contribution = (
            neck_pitch_target * float(chain_index + 1) / neck_weight_total
        )
        neck_pitch_applied += contribution
        _rotate_pose_subtree(
            clip,
            positions,
            rotations,
            joint,
            rotations[:, joint, 2].clone(),
            contribution,
        )
    _rotate_pose_subtree(
        clip,
        positions,
        rotations,
        head,
        rotations[:, head, 2].clone(),
        pitch - neck_pitch_applied,
        pivot_override=positions[:, neck2].clone(),
    )
    return positions, rotations


def gaze_overlay_global_pose(
    clip: tl.MotionClip,
    frame_indices: torch.Tensor,
    gaze_normalized: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Return accepted gaze-overlaid global positions and rotations."""

    return apply_gaze_overlay_global_pose(
        clip,
        clip.global_pos.index_select(0, frame_indices),
        clip.global_rot.index_select(0, frame_indices),
        gaze_normalized,
    )


def gaze_overlay_upper_state(
    clip: tl.MotionClip,
    frame_indices: torch.Tensor,
    gaze_normalized: torch.Tensor,
) -> torch.Tensor:
    """Apply the accepted viewer gaze overlay, with body pitch fixed at 1."""

    positions, rotations = gaze_overlay_global_pose(
        clip, frame_indices, gaze_normalized
    )
    root_pos = clip.root_pos.index_select(0, frame_indices)
    root_heading = clip.root_heading_rot.index_select(0, frame_indices)
    return upper_state_from_global_pose_and_heading(
        clip, positions, rotations, root_pos, root_heading
    )


def rest_offsets_from_pelvis(clip: tl.MotionClip) -> torch.Tensor:
    accumulated: list[torch.Tensor] = []
    zero = torch.zeros(3, dtype=clip.local_offsets.dtype)
    for joint, parent in enumerate(clip.parents_body_list):
        if joint == int(clip.pelvis):
            accumulated.append(zero)
        elif int(parent) < 0:
            accumulated.append(clip.local_offsets[joint])
        else:
            accumulated.append(accumulated[int(parent)] + clip.local_offsets[joint])
    return torch.stack(accumulated)


def fk_base_upper_from_clip(clip: tl.MotionClip) -> torch.Tensor:
    """Exact Slash2 lower-FK upper base: identity upper tree rigid on pelvis."""

    by_name = {name: index for index, name in enumerate(clip.body_names)}
    count = int(clip.T)
    heading = clip.root_heading_rot
    # Recompose the pelvis exactly as the lower-agent FK path does. The visible
    # source globals can differ by tiny FBX decomposition roundoff.
    pelvis_pos = (
        torch.matmul(clip.pelvis_local_pos.unsqueeze(1), clip.root_rot).squeeze(1)
        + clip.root_pos
    )
    pelvis_rot = clip.pelvis_rot_mat @ clip.root_rot
    rest = rest_offsets_from_pelvis(clip)
    identity6 = tl.rotmat_to_6d(torch.eye(3, dtype=pelvis_rot.dtype)).reshape(1, 6)
    parts: list[torch.Tensor] = [identity6.repeat(count, len(CORE_BONES))]
    pelvis_rot_root6 = tl.rotmat_to_6d(root_relative_rotation(pelvis_rot, heading))
    for _side, upper_name, _lower_name, hand_name in ARM_SPECS:
        del upper_name
        hand = by_name[hand_name]
        hand_world = (
            torch.matmul(rest[hand].reshape(1, 1, 3), pelvis_rot).squeeze(1)
            + pelvis_pos
        )
        parts.extend(
            (
                root_relative_position(hand_world, clip.root_pos, heading),
                pelvis_rot_root6,
                pelvis_rot_root6,
            )
        )
    return clean_upper_state(torch.cat(parts, dim=-1))


def pelvis_root_features(clip: tl.MotionClip) -> torch.Tensor:
    heading = clip.root_heading_rot
    pelvis_pos = (
        torch.matmul(clip.pelvis_local_pos.unsqueeze(1), clip.root_rot).squeeze(1)
        + clip.root_pos
    )
    pelvis_rot = clip.pelvis_rot_mat @ clip.root_rot
    return torch.cat(
        (
            root_relative_position(pelvis_pos, clip.root_pos, heading),
            tl.rotmat_to_6d(root_relative_rotation(pelvis_rot, heading)),
        ),
        dim=-1,
    )


def feet_root_features(clip: tl.MotionClip) -> torch.Tensor:
    """Left then right foot, each root-relative position 3 + rotation 6."""

    by_name = {name: index for index, name in enumerate(clip.body_names)}
    heading = clip.root_heading_rot
    parts: list[torch.Tensor] = []
    for name in ("foot_l", "foot_r"):
        joint = by_name[name]
        parts.extend(
            (
                root_relative_position(
                    clip.global_pos[:, joint], clip.root_pos, heading
                ),
                tl.rotmat_to_6d(
                    root_relative_rotation(clip.global_rot[:, joint], heading)
                ),
            )
        )
    result = torch.cat(parts, dim=-1)
    if result.shape != (int(clip.T), FOOT_PAIR_DIM):
        raise RuntimeError(f"Foot feature shape mismatch: {tuple(result.shape)}")
    return result


def controller_root_features(
    clip: tl.MotionClip,
    cfg: tl.TrainConfig,
    current_rows: torch.Tensor,
) -> torch.Tensor:
    future_steps = int(cfg.future_window)
    current_root_idx = current_rows.clone()
    if clip.cyclic_animation:
        current_root_idx = torch.where(
            current_root_idx == 0,
            torch.full_like(current_root_idx, int(clip.cyclic_period)),
            current_root_idx,
        )
        previous_root_idx = current_root_idx - 1
    else:
        previous_root_idx = (current_root_idx - 1).clamp_min(0)

    previous_pos, _previous_rot, previous_yaw, previous_heading = tl.root_state(
        clip, previous_root_idx, cfg, torch.device("cpu")
    )
    current_pos, _current_rot, current_yaw, current_heading = tl.root_state(
        clip, current_root_idx, cfg, torch.device("cpu")
    )
    delta_local = torch.matmul(
        (current_pos - previous_pos).unsqueeze(1), previous_heading
    ).squeeze(1)
    current_feature = torch.stack(
        (
            delta_local[:, 0] / float(cfg.max_speed_scale_final),
            delta_local[:, 2] / float(cfg.max_speed_scale_final),
            tl.wrap_angle(current_yaw - previous_yaw)
            / float(cfg.max_turn_rate_scale_final),
        ),
        dim=-1,
    )

    offsets = torch.arange(1, future_steps + 1, dtype=torch.long)
    flat_idx = (
        current_root_idx.reshape(-1, 1) + offsets.reshape(1, -1)
    ).reshape(-1)
    if not clip.cyclic_animation:
        flat_idx.clamp_(max=int(clip.T) - 1)
    future_pos, _future_rot, future_yaw, _future_heading = tl.root_state(
        clip,
        flat_idx,
        cfg,
        torch.device("cpu"),
    )
    future_pos = future_pos.reshape(current_rows.numel(), future_steps, 3)
    future_yaw = future_yaw.reshape(current_rows.numel(), future_steps)
    future_local = torch.matmul(
        (future_pos - current_pos[:, None, :]).unsqueeze(-2),
        current_heading[:, None],
    ).squeeze(-2)
    scale = (
        offsets.to(dtype=future_local.dtype).reshape(1, future_steps)
        * float(cfg.max_speed_scale_final)
    )
    delta_yaw = tl.wrap_angle(future_yaw - current_yaw[:, None])
    future_feature = torch.stack(
        (
            torch.clamp(future_local[:, :, 0] / scale, -2.0, 2.0),
            torch.clamp(future_local[:, :, 2] / scale, -2.0, 2.0),
            torch.cos(delta_yaw),
            torch.sin(delta_yaw),
        ),
        dim=-1,
    ).reshape(current_rows.numel(), future_steps * 4)
    result = torch.cat((current_feature, future_feature), dim=-1)
    if result.shape != (current_rows.numel(), ROOT_DIM):
        raise RuntimeError(f"Root feature shape mismatch: {tuple(result.shape)}")
    return result


@torch.no_grad()
def sampled_window_gaze(relative_path: str, window_count: int) -> torch.Tensor:
    digest = hashlib.sha256(
        f"{CACHE_VERSION}:{GAZE_DATA_SEED}:{relative_path}".encode("utf-8")
    ).digest()
    seed = int.from_bytes(digest[:8], byteorder="little", signed=False)
    generator = torch.Generator(device="cpu").manual_seed(seed)
    gaze = torch.rand((window_count, GAZE_DIM), generator=generator) * 2.0 - 1.0
    zero_mask = (
        torch.rand((window_count,), generator=generator) < GAZE_ZERO_PROBABILITY
    )
    gaze[zero_mask] = 0.0
    return gaze


@torch.no_grad()
def controller_rows(
    clip: tl.MotionClip,
    cfg: tl.TrainConfig,
    current: torch.Tensor,
    gaze: torch.Tensor,
    has_sword: float,
    base: torch.Tensor,
    pelvis: torch.Tensor,
    feet: torch.Tensor,
) -> torch.Tensor:
    if current.shape[0] != gaze.shape[0]:
        raise ValueError(
            f"Current/gaze row mismatch: {current.shape[0]} versus {gaze.shape[0]}"
        )
    if clip.cyclic_animation:
        previous = torch.remainder(current - 1, int(clip.cyclic_period))
        following = torch.remainder(current + 1, int(clip.cyclic_period))
    else:
        previous = (current - 1).clamp_min(0)
        following = current + 1

    pose_indices = torch.cat((previous, current, following), dim=0)
    repeated_gaze = gaze.repeat(3, 1)
    posed = gaze_overlay_upper_state(clip, pose_indices, repeated_gaze)
    row_count = int(current.numel())
    previous_pose = posed[:row_count]
    current_pose = posed[row_count : row_count * 2]
    following_pose = posed[row_count * 2 :]
    next_pose = clean_upper_state(
        base.index_select(0, following)
        + current_pose
        - base.index_select(0, current)
    )
    target_delta = following_pose - next_pose
    sword_flag = torch.full((row_count, 1), float(has_sword), dtype=torch.float32)
    rows = torch.cat(
        (
            previous_pose,
            next_pose,
            pelvis.index_select(0, previous),
            pelvis.index_select(0, current),
            pelvis.index_select(0, following),
            controller_root_features(clip, cfg, current),
            sword_flag,
            feet.index_select(0, current),
            feet.index_select(0, following),
            gaze,
            target_delta,
        ),
        dim=-1,
    ).contiguous()
    if rows.shape != (row_count, ROW_DIM):
        raise RuntimeError(f"Upper row shape mismatch: {tuple(rows.shape)}")
    return rows


@torch.no_grad()
def clip_windows(
    relative_path: str,
    path: Path,
    cyclic: bool,
    has_sword: float,
    cfg: tl.TrainConfig,
) -> tuple[torch.Tensor, int, int]:
    clip = tl.MotionClip(path, cfg, cyclic_animation=cyclic)
    base = fk_base_upper_from_clip(clip)
    pelvis = pelvis_root_features(clip)
    feet = feet_root_features(clip)

    if cyclic:
        current = torch.arange(int(clip.cyclic_period), dtype=torch.long)
    else:
        row_count = int(clip.T) - int(cfg.future_window)
        current = torch.arange(max(0, row_count), dtype=torch.long)
    if current.numel() < WINDOW_FRAMES:
        raise RuntimeError(f"Clip is too short for upper AE rows: {path}")
    window_count = int(current.numel()) - 1
    gaze = sampled_window_gaze(relative_path, window_count)
    first_rows = controller_rows(
        clip, cfg, current[:-1], gaze, has_sword, base, pelvis, feet
    )
    second_rows = controller_rows(
        clip, cfg, current[1:], gaze, has_sword, base, pelvis, feet
    )
    windows = torch.cat((first_rows, second_rows), dim=-1).contiguous()
    if not bool(torch.isfinite(windows).all()):
        raise RuntimeError(f"Non-finite upper AE windows from {path}")
    if windows.shape != (window_count, WINDOW_DIM):
        raise RuntimeError(f"Upper window shape mismatch for {path}: {tuple(windows.shape)}")
    zero_count = int((gaze == 0.0).all(dim=-1).sum())
    return windows, int(current.numel()), zero_count


def cache_path(fingerprint: str) -> Path:
    return CACHE_ROOT / f"{CACHE_VERSION}_{fingerprint[:16]}.pt"


def prepare_windows(force_rebuild: bool = False) -> tuple[torch.Tensor, dict[str, object], Path]:
    original_specs, sword_specs, fingerprint = matched_dataset()
    path = cache_path(fingerprint)
    if path.is_file() and not force_rebuild:
        payload = torch.load(path, map_location="cpu", weights_only=False)
        if payload.get("fingerprint") != fingerprint or payload.get("version") != CACHE_VERSION:
            raise RuntimeError(f"Upper AE cache contract mismatch: {path}")
        windows = payload["windows"].to(dtype=torch.float32, device="cpu")
        metadata = dict(payload["metadata"])
        print(
            f"UPPER_AE_CACHE status=hit windows={windows.shape[0]} dim={windows.shape[1]} path={path}",
            flush=True,
        )
        return windows, metadata, path

    cfg = motion_config()
    chunks: list[torch.Tensor] = []
    counts = {
        "original_clips": 0,
        "sword_clips": 0,
        "original_rows": 0,
        "sword_rows": 0,
        "original_windows": 0,
        "sword_windows": 0,
        "original_zero_gaze_windows": 0,
        "sword_zero_gaze_windows": 0,
    }
    started = time.perf_counter()
    corpus_specs = (("original", -1.0, original_specs), ("sword", 1.0, sword_specs))
    processed = 0
    for corpus, flag, specs in corpus_specs:
        for relative, motion_path, cyclic in specs:
            windows, row_count, zero_gaze_count = clip_windows(
                relative, motion_path, cyclic, flag, cfg
            )
            chunks.append(windows)
            counts[f"{corpus}_clips"] += 1
            counts[f"{corpus}_rows"] += row_count
            counts[f"{corpus}_windows"] += int(windows.shape[0])
            counts[f"{corpus}_zero_gaze_windows"] += zero_gaze_count
            processed += 1
            if processed == 1 or processed % 25 == 0 or processed == 930:
                print(
                    f"UPPER_AE_BUILD clips={processed}/930 windows={sum(int(x.shape[0]) for x in chunks)} "
                    f"elapsed_s={time.perf_counter() - started:.1f}",
                    flush=True,
                )
    windows = torch.cat(chunks, dim=0).contiguous()
    del chunks
    metadata: dict[str, object] = {
        **counts,
        "original_root": str(ORIGINAL_ROOT),
        "sword_root": str(SWORD_ROOT),
        "fingerprint": fingerprint,
        "future_window": int(cfg.future_window),
        "max_speed_scale_final": float(cfg.max_speed_scale_final),
        "max_turn_rate_scale_final": float(cfg.max_turn_rate_scale_final),
        "window_frames": WINDOW_FRAMES,
        "input_dim": INPUT_DIM,
        "output_dim": OUTPUT_DIM,
        "row_dim": ROW_DIM,
        "window_dim": WINDOW_DIM,
        "foot_conditioning_dim": FOOT_CONDITIONING_DIM,
        "foot_conditioning": "current then next; each left position3 rotation6 then right position3 rotation6 in root heading frame",
        "gaze_dim": GAZE_DIM,
        "gaze_order": ["yaw_normalized", "pitch_normalized"],
        "gaze_yaw_limit_deg": GAZE_YAW_LIMIT_DEG,
        "gaze_pitch_limit_deg": GAZE_PITCH_LIMIT_DEG,
        "gaze_zero_probability": GAZE_ZERO_PROBABILITY,
        "gaze_body_pitch_multiplier": GAZE_BODY_PITCH_MULTIPLIER,
        "gaze_sampling": "one uniform gaze pair per two-row window, shared by both rows; exact 0,0 with configured probability",
    }
    expected_windows = counts["original_windows"] + counts["sword_windows"]
    if windows.shape != (expected_windows, WINDOW_DIM):
        raise RuntimeError(f"Combined upper window shape mismatch: {tuple(windows.shape)}")
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    torch.save(
        {
            "version": CACHE_VERSION,
            "fingerprint": fingerprint,
            "metadata": metadata,
            "windows": windows,
        },
        temporary,
    )
    temporary.replace(path)
    print(
        f"UPPER_AE_CACHE status=built windows={windows.shape[0]} dim={windows.shape[1]} "
        f"elapsed_s={time.perf_counter() - started:.1f} path={path}",
        flush=True,
    )
    return windows, metadata, path


def checkpoint_schema() -> dict[str, object]:
    return {
        "name": "upper_pose_controller_io_two_row",
        "total_dim": WINDOW_DIM,
        "window_frames": WINDOW_FRAMES,
        "base_total_dim": ROW_DIM,
        "input_dim": INPUT_DIM,
        "output_dim": OUTPUT_DIM,
        "newest_output_start": NEWEST_OUTPUT_START,
        "newest_output_end": NEWEST_OUTPUT_END,
        "input_segments": {
            "previous_upper_pose": [0, 90],
            "stiffly_propagated_next_upper_pose": [90, 180],
            "previous_pelvis_in_root": [180, 189],
            "current_pelvis_in_root": [189, 198],
            "next_pelvis_in_root": [198, 207],
            "current_and_future_root_motion": [207, 242],
            "has_sword": [242, 243],
            "current_feet_in_root": [243, 261],
            "next_feet_in_root": [261, 279],
            "gaze_yaw_pitch_normalized": [279, 281],
        },
        "output_segments": {
            "next_upper_pose_delta": [281, 371],
            "core_local_rot6": [281, 341],
            "left_hand_root_and_upperarm_root": [341, 356],
            "right_hand_root_and_upperarm_root": [356, 371],
        },
        "upper_pose_layout": {
            "core_bones": list(CORE_BONES),
            "arm_specs": [list(spec) for spec in ARM_SPECS],
            "per_arm": ["hand_position_root_3", "hand_rotation_root_6", "upperarm_rotation_root_6"],
        },
        "foot_layout": {
            "frames": ["current", "next"],
            "per_frame": [
                "foot_l_position_root_3",
                "foot_l_rotation_root_6",
                "foot_r_position_root_3",
                "foot_r_rotation_root_6",
            ],
            "loss": "conditioning_only_excluded_from_reconstruction_loss",
        },
        "gaze_layout": {
            "yaw": "normalized by 170 degrees",
            "pitch": "normalized by 85 degrees",
            "body_pitch_multiplier": 1.0,
            "sampling": "uniform full range with 5 percent exact zero-zero",
        },
        "loss": "normalized_mse_on_newest_rows_90_value_output_only",
    }


def checkpoint_payload(
    model: SimpleAutoencoder,
    optimizer: torch.optim.Optimizer,
    cfg: SimpleAEConfig,
    mean: torch.Tensor,
    std: torch.Tensor,
    metadata: dict[str, object],
    step: int,
    best: float,
) -> dict[str, object]:
    return {
        "kind": "upper_pose_controller_io_autoencoder",
        "model": model.state_dict(),
        "optimizer": optimizer.state_dict(),
        "config": asdict(cfg),
        "schema": checkpoint_schema(),
        "mean": mean.detach().cpu(),
        "std": std.detach().cpu(),
        "step": int(step),
        "best": float(best),
        "metadata": metadata,
    }


@torch.no_grad()
def evaluate(
    model: SimpleAutoencoder,
    normalized: torch.Tensor,
    device: torch.device,
    std: torch.Tensor,
    batch_size: int = 2048,
) -> dict[str, float]:
    model.eval()
    squared_sum = 0.0
    raw_squared = torch.zeros(OUTPUT_DIM, dtype=torch.float64)
    rows = 0
    target_std = std[NEWEST_OUTPUT_START:NEWEST_OUTPUT_END].to(dtype=torch.float64)
    for start in range(0, int(normalized.shape[0]), int(batch_size)):
        cpu = normalized[start : start + int(batch_size)]
        batch = cpu.to(device=device, non_blocking=False)
        recon = model(batch)
        error = recon[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END] - batch[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END]
        squared_sum += float(error.square().sum().detach().cpu())
        raw_squared += error.detach().cpu().to(dtype=torch.float64).square().sum(dim=0) * target_std.square()
        rows += int(batch.shape[0])
        del batch, recon, error
    normalized_mse = squared_sum / float(max(1, rows * OUTPUT_DIM))
    raw_mse = raw_squared / float(max(1, rows))
    model.train()
    return {
        "normalized_mse": normalized_mse,
        "delta_rmse": float(torch.sqrt(raw_mse.mean())),
        "core_delta_rmse": float(torch.sqrt(raw_mse[:60].mean())),
        "left_arm_delta_rmse": float(torch.sqrt(raw_mse[60:75].mean())),
        "right_arm_delta_rmse": float(torch.sqrt(raw_mse[75:90].mean())),
    }


@torch.no_grad()
def evaluate_gaze_mismatch_curve(
    model: SimpleAutoencoder,
    normalized: torch.Tensor,
    device: torch.device,
    mean: torch.Tensor,
    std: torch.Tensor,
    sample_count: int = 8192,
) -> dict[str, object]:
    """Hold pose fixed and move only gaze inputs progressively farther away."""

    model.eval()
    count = min(int(sample_count), int(normalized.shape[0]))
    generator = torch.Generator(device="cpu").manual_seed(88321)
    indices = torch.randperm(int(normalized.shape[0]), generator=generator)[:count]
    clean = normalized.index_select(0, indices)
    target = clean[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END].to(device)
    distances = (0.0, 0.25, 0.50, 0.75, 1.0)
    modes = {
        "combined": (0, 1),
        "yaw_only": (0,),
        "pitch_only": (1,),
    }
    curves: dict[str, list[dict[str, float]]] = {}
    monotonic_by_mode: dict[str, bool] = {}
    ratios: dict[str, float] = {}
    for mode, axes in modes.items():
        curve: list[dict[str, float]] = []
        for distance in distances:
            candidate = clean.clone()
            for row_offset in (0, ROW_DIM):
                start = row_offset + GAZE_START
                end = start + GAZE_DIM
                raw = candidate[:, start:end] * std[start:end] + mean[start:end]
                wrong = raw.clone()
                for axis_index in axes:
                    direction = torch.where(
                        raw[:, axis_index] <= 0.0, 1.0, -1.0
                    )
                    wrong[:, axis_index] = torch.clamp(
                        raw[:, axis_index] + direction * float(distance), -1.0, 1.0
                    )
                candidate[:, start:end] = (wrong - mean[start:end]) / std[start:end]
            recon = model(candidate.to(device))
            error = (
                recon[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END] - target
            ).square().mean(dim=-1)
            curve.append(
                {
                    "normalized_gaze_distance": float(distance),
                    "normalized_output_mse": float(error.mean().cpu()),
                }
            )
            del candidate, recon, error
        curves[mode] = curve
        scores = [float(row["normalized_output_mse"]) for row in curve]
        monotonic_by_mode[mode] = all(
            scores[index + 1] > scores[index]
            for index in range(len(scores) - 1)
        )
        ratios[mode] = scores[-1] / max(scores[0], 1.0e-12)
    monotonic = all(monotonic_by_mode.values())
    model.train()
    return {
        "sample_count": count,
        "method": "pose held fixed; both AE rows receive the same progressively wrong normalized gaze controls",
        "curves": curves,
        "strictly_monotonic_by_mode": monotonic_by_mode,
        "strictly_monotonic": monotonic,
        "largest_to_correct_ratio_by_mode": ratios,
    }


def train(args: argparse.Namespace) -> None:
    torch.manual_seed(int(args.seed))
    windows, dataset_metadata, dataset_cache = prepare_windows(
        force_rebuild=bool(args.rebuild_cache)
    )
    mean = windows.mean(dim=0)
    std = windows.std(dim=0, unbiased=False).clamp_min(float(args.std_floor))
    windows.sub_(mean).div_(std)
    normalized = windows
    del windows
    gc.collect()

    device = torch.device(args.device)
    if device.type == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA training requested, but CUDA is unavailable")
        cuda_index = (
            int(device.index)
            if device.index is not None
            else int(torch.cuda.current_device())
        )
        torch.cuda.set_device(cuda_index)
        device = torch.device("cuda", cuda_index)
        torch.backends.cuda.matmul.allow_tf32 = True
        free_bytes, total_bytes = torch.cuda.mem_get_info(device)
        free_mib = free_bytes / (1024.0 * 1024.0)
        print(
            f"UPPER_AE_GPU before_model_free_mib={free_mib:.0f} total_mib={total_bytes / (1024.0 * 1024.0):.0f}",
            flush=True,
        )
        if free_mib < float(args.minimum_cuda_free_mib):
            raise RuntimeError(
                f"Only {free_mib:.0f} MiB CUDA memory is free; refusing below "
                f"{args.minimum_cuda_free_mib:.0f} MiB while Unreal is running"
            )

    cfg = SimpleAEConfig(
        latent_dim=128,
        hidden_dim=1024,
        num_hidden_layers=3,
        batch_size=int(args.batch_size),
        train_steps=int(args.train_steps),
        learning_rate=1.0e-3,
        weight_decay=1.0e-5,
        std_floor=float(args.std_floor),
        val_fraction=0.0,
        seed=int(args.seed),
        pose_representation="upper_pose_root_hands",
        body_mode="upper_body",
        feature="upper_pose_controller_input_plus_next_pose_delta",
        ae_feature_mode="pose",
        ae_score_scope="output",
        window_frames=WINDOW_FRAMES,
        denoise_noise_std=0.0,
    )
    model = SimpleAutoencoder(WINDOW_DIM, cfg).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=cfg.learning_rate, weight_decay=cfg.weight_decay
    )
    parameter_count = sum(int(parameter.numel()) for parameter in model.parameters())
    print(
        f"UPPER_AE_READY windows={normalized.shape[0]} dim={WINDOW_DIM} params={parameter_count} "
        f"batch={cfg.batch_size} cache={dataset_cache}",
        flush=True,
    )

    smoke_steps = int(args.smoke_steps)
    train_steps = smoke_steps if smoke_steps > 0 else int(cfg.train_steps)
    generator = torch.Generator(device="cpu").manual_seed(int(cfg.seed))
    run_id = ""
    run_dir: Path | None = None
    best = float("inf")
    best_step = 0
    metrics: list[dict[str, float | int]] = []
    metadata: dict[str, object] = {
        **dataset_metadata,
        "dataset_cache": str(dataset_cache),
        "recipe": {
            "architecture": "symmetric_fc_layernorm_gelu",
            "hidden_dim": 1024,
            "hidden_layers": 3,
            "latent_dim": 128,
            "batch_size": int(cfg.batch_size),
            "optimizer": "AdamW",
            "learning_rate": 1.0e-3,
            "weight_decay": 1.0e-5,
            "train_steps": int(cfg.train_steps),
            "lr_schedule": "1.0_to_70pct__0.3_to_90pct__0.1_final",
            "training_noise": 0.0,
            "val_fraction": 0.0,
            "seed": int(cfg.seed),
            "foot_conditioning": "current_and_next_root_relative_left_then_right_pos3_rot6",
            "foot_reconstruction_loss": "excluded",
            "gaze_conditioning": "normalized_yaw_pitch_uniform_full_range_5pct_zero_zero",
            "gaze_body_pitch_multiplier": 1.0,
        },
    }
    if smoke_steps <= 0:
        run_id = ik_run_id(str(args.run_label))
        run_dir = RUNS_ROOT / run_id
        (run_dir / "checkpoints").mkdir(parents=True, exist_ok=True)
        (run_dir / "config.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "config": asdict(cfg),
                    "schema": checkpoint_schema(),
                    "metadata": metadata,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    started = time.perf_counter()
    last_report_time = started
    for step in range(1, train_steps + 1):
        lr = lr_for_step(step, int(cfg.train_steps), float(cfg.learning_rate))
        for group in optimizer.param_groups:
            group["lr"] = lr
        indices = torch.randint(
            0,
            int(normalized.shape[0]),
            (int(cfg.batch_size),),
            generator=generator,
        )
        batch = normalized.index_select(0, indices).to(device=device, non_blocking=False)
        recon = model(batch)
        loss = (
            recon[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END]
            - batch[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END]
        ).square().mean()
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        del batch, recon

        should_evaluate = (
            smoke_steps > 0
            and (step == 1 or step == train_steps)
            or smoke_steps <= 0
            and (step == 1 or step % int(args.eval_every) == 0 or step == train_steps)
        )
        if should_evaluate:
            report = evaluate(model, normalized, device, std)
            elapsed = time.perf_counter() - started
            row: dict[str, float | int] = {
                "step": int(step),
                "train_batch_loss": float(loss.detach().cpu()),
                "learning_rate": float(lr),
                "elapsed_seconds": float(elapsed),
                **report,
            }
            metrics.append(row)
            improved = float(report["normalized_mse"]) < best
            if improved:
                best = float(report["normalized_mse"])
                best_step = int(step)
                if run_dir is not None:
                    torch.save(
                        checkpoint_payload(
                            model, optimizer, cfg, mean, std, metadata, step, best
                        ),
                        checkpoint_path(run_dir, run_id, "best"),
                    )
            if run_dir is not None:
                (run_dir / "metrics.json").write_text(
                    json.dumps(
                        {
                            "run_id": run_id,
                            "best": best,
                            "best_step": best_step,
                            "history": metrics,
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            gpu_text = ""
            if device.type == "cuda":
                free_bytes, _total_bytes = torch.cuda.mem_get_info(device)
                gpu_text = f" cuda_free_mib={free_bytes / (1024.0 * 1024.0):.0f}"
            print(
                f"UPPER_AE step={step:05d} batch_loss={float(loss.detach().cpu()):.6g} "
                f"eval={report['normalized_mse']:.6g} delta_rmse={report['delta_rmse']:.6g} "
                f"best={best:.6g}@{best_step} lr={lr:.3g} elapsed_s={elapsed:.1f}{gpu_text}",
                flush=True,
            )
            last_report_time = time.perf_counter()
        elif time.perf_counter() - last_report_time >= 45.0:
            print(
                f"UPPER_AE_PROGRESS step={step:05d}/{train_steps} "
                f"batch_loss={float(loss.detach().cpu()):.6g} "
                f"elapsed_s={time.perf_counter() - started:.1f}",
                flush=True,
            )
            last_report_time = time.perf_counter()

    if smoke_steps > 0:
        gaze_audit = evaluate_gaze_mismatch_curve(
            model, normalized, device, mean, std, sample_count=2048
        )
        print(f"UPPER_AE_GAZE_AUDIT {json.dumps(gaze_audit, separators=(',', ':'))}", flush=True)
        print(
            f"UPPER_AE_SMOKE_OK steps={smoke_steps} peak_cuda_mib="
            f"{torch.cuda.max_memory_allocated(device) / (1024.0 * 1024.0) if device.type == 'cuda' else 0.0:.0f}",
            flush=True,
        )
        return

    assert run_dir is not None
    last_path = checkpoint_path(run_dir, run_id, "last")
    torch.save(
        checkpoint_payload(
            model, optimizer, cfg, mean, std, metadata, train_steps, best
        ),
        last_path,
    )
    best_path = checkpoint_path(run_dir, run_id, "best")
    best_payload = torch.load(best_path, map_location=device, weights_only=False)
    model.load_state_dict(best_payload["model"])
    gaze_audit = evaluate_gaze_mismatch_curve(
        model, normalized, device, mean, std
    )
    (run_dir / "gaze_mismatch_audit.json").write_text(
        json.dumps(gaze_audit, indent=2), encoding="utf-8"
    )
    print(f"UPPER_AE_GAZE_AUDIT {json.dumps(gaze_audit, separators=(',', ':'))}", flush=True)
    print(
        f"UPPER_AE_COMPLETE run={run_id} best={best:.6g}@{best_step} last={last_path}",
        flush=True,
    )
    if not bool(gaze_audit["strictly_monotonic"]):
        raise RuntimeError(
            "Gaze mismatch audit is not strictly monotonic; checkpoint is not acceptable as gaze-aware AE1"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train the two-row upper-pose controller I/O autoencoder."
    )
    parser.add_argument("--run-label", default="upper_pose_ae1_h1024_l3_ld128_w2_12k")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--train-steps", type=int, default=12000)
    parser.add_argument("--eval-every", type=int, default=500)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--std-floor", type=float, default=1.0e-4)
    parser.add_argument("--minimum-cuda-free-mib", type=float, default=900.0)
    parser.add_argument("--smoke-steps", type=int, default=0)
    parser.add_argument("--rebuild-cache", action="store_true")
    args = parser.parse_args()
    train(args)


if __name__ == "__main__":
    main()
