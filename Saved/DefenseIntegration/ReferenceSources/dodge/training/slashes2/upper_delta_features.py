from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from native_controller_targets import load_controller_target_arrays


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
ROOT_CONDITION_NAMES: tuple[str, ...] = ()
TARGET_NAMES = ("target_height_m",)
ATTACK_LABEL_NAMES = ("attack_angle", "is_pike", "is_melee", "is_kick", "is_headbutt")

CORE_DELTA_DIM = len(CORE_BONES) * 6
ARM_DELTA_DIM = len(ARM_SPECS) * (3 + 6 + 6)
MOTION_DELTA_DIM = CORE_DELTA_DIM + ARM_DELTA_DIM
UPPER_STATE_DIM = MOTION_DELTA_DIM
AE2_DIM = MOTION_DELTA_DIM
AE22_DIM = AE2_DIM + len(TARGET_NAMES) + len(ATTACK_LABEL_NAMES)
STATE_CONDITIONED_AE2_DIM = (
    MOTION_DELTA_DIM
    + UPPER_STATE_DIM * 2
)
STATE_CONDITIONED_AE_DIM = (
    MOTION_DELTA_DIM
    + UPPER_STATE_DIM * 2
    + len(TARGET_NAMES)
    + len(ATTACK_LABEL_NAMES)
)


@dataclass(frozen=True)
class MotionArrays:
    path: Path
    names: tuple[str, ...]
    parents: np.ndarray
    global_pos_m: np.ndarray
    global_rot: np.ndarray
    local_rot: np.ndarray
    root_index: int

    @property
    def frame_count(self) -> int:
        return int(self.global_pos_m.shape[0])


def rotation_6d(rotation: np.ndarray) -> np.ndarray:
    return np.asarray(rotation[..., :2, :], dtype=np.float32).reshape(*rotation.shape[:-2], 6)


def canonicalize_positions(values: np.ndarray, up_axis: int) -> np.ndarray:
    values = np.asarray(values, dtype=np.float32)
    if int(up_axis) == 2:
        return values
    if int(up_axis) != 3:
        raise ValueError(f"Unsupported axis_up_axis={up_axis}; expected 2 (Y-up) or 3 (Z-up).")
    return np.stack((values[..., 0], values[..., 2], -values[..., 1]), axis=-1).astype(np.float32)


def canonicalize_rotations(values: np.ndarray, up_axis: int) -> np.ndarray:
    values = np.asarray(values, dtype=np.float32)
    if int(up_axis) == 2:
        return values
    if int(up_axis) != 3:
        raise ValueError(f"Unsupported axis_up_axis={up_axis}; expected 2 (Y-up) or 3 (Z-up).")
    basis = np.asarray(((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0)), dtype=np.float32)
    return (basis.T @ values @ basis).astype(np.float32)


def local_rotations_from_global(global_rot: np.ndarray, parents: np.ndarray) -> np.ndarray:
    local = np.empty_like(global_rot, dtype=np.float32)
    for bone, parent in enumerate(np.asarray(parents, dtype=np.int32).tolist()):
        if int(parent) < 0:
            local[:, bone] = global_rot[:, bone]
        else:
            local[:, bone] = global_rot[:, bone] @ np.swapaxes(global_rot[:, int(parent)], -1, -2)
    return local


def load_motion_arrays(path: Path) -> MotionArrays:
    path = path.resolve()
    with np.load(path, allow_pickle=False) as data:
        names = tuple(str(value) for value in data["bone_names"].tolist())
        parents = np.asarray(data["parents"], dtype=np.int32).copy()
        if "model_global_joint_pos_m" in data.files and "model_global_matrix" in data.files:
            # One shared extraction contract for AE datasets, the Slash2
            # trainer, evaluators, and viewers.  Visible joint positions define
            # controller-owned parent rotations; the NPZ itself is untouched.
            controller = load_controller_target_arrays(path)
            global_pos_m = controller.visible_global_pos_m
            global_rot = controller.controller_global_rot
            local_rot = controller.controller_local_rot
        else:
            up_axis = int(np.asarray(data["axis_up_axis"]).item())
            global_pos_m = canonicalize_positions(
                np.asarray(data["global_joint_pos"], dtype=np.float32) * np.float32(0.01), up_axis
            )
            global_rot = canonicalize_rotations(
                np.asarray(data["global_matrix"][..., :3, :3], dtype=np.float32), up_axis
            )
            local_rot = canonicalize_rotations(
                np.asarray(data["local_matrix"][..., :3, :3], dtype=np.float32), up_axis
            )
    required = {"root", *CORE_BONES}
    for _side, upper, lower, hand in ARM_SPECS:
        required.update((upper, lower, hand))
    missing = sorted(required - set(names))
    if missing:
        raise ValueError(f"{path} is missing AE2 bones: {missing}")
    expected_frames = global_pos_m.shape[0]
    if global_rot.shape != (expected_frames, len(names), 3, 3):
        raise ValueError(f"Unexpected global rotation shape in {path}: {global_rot.shape}")
    if local_rot.shape != global_rot.shape:
        raise ValueError(f"Unexpected local rotation shape in {path}: {local_rot.shape}")
    if not np.isfinite(global_pos_m).all() or not np.isfinite(global_rot).all() or not np.isfinite(local_rot).all():
        raise ValueError(f"Non-finite motion arrays in {path}")
    return MotionArrays(path, names, parents, global_pos_m, global_rot, local_rot, names.index("root"))


def heading_yaw(root_rot: np.ndarray) -> np.ndarray:
    forward = -np.asarray(root_rot[..., 1, :], dtype=np.float64)
    return np.arctan2(forward[..., 0], forward[..., 2])


def wrap_angle(value: np.ndarray) -> np.ndarray:
    return np.arctan2(np.sin(value), np.cos(value))


def yaw_rotation(yaw: np.ndarray) -> np.ndarray:
    yaw = np.asarray(yaw, dtype=np.float64)
    cosine = np.cos(yaw)
    sine = np.sin(yaw)
    zeros = np.zeros_like(cosine)
    ones = np.ones_like(cosine)
    row0 = np.stack((cosine, zeros, sine), axis=-1)
    row1 = np.stack((zeros, ones, zeros), axis=-1)
    row2 = np.stack((-sine, zeros, cosine), axis=-1)
    return np.stack((row0, row1, row2), axis=-2)


def root_relative_position(position: np.ndarray, root_position: np.ndarray, root_rotation: np.ndarray) -> np.ndarray:
    return np.einsum("...i,...ij->...j", position - root_position, np.swapaxes(root_rotation, -1, -2))


def root_relative_rotation(rotation: np.ndarray, root_rotation: np.ndarray) -> np.ndarray:
    return rotation @ np.swapaxes(root_rotation, -1, -2)


def upper_transition_features(
    motion: MotionArrays,
    current_indices: np.ndarray,
    next_indices: np.ndarray,
) -> np.ndarray:
    current_indices = np.asarray(current_indices, dtype=np.int64)
    next_indices = np.asarray(next_indices, dtype=np.int64)
    if current_indices.shape != next_indices.shape or current_indices.ndim != 1:
        raise ValueError("Current and next transition indices must be equally sized vectors.")
    if current_indices.size == 0:
        return np.empty((0, AE2_DIM), dtype=np.float32)

    index_by_name = {name: index for index, name in enumerate(motion.names)}
    root = motion.root_index
    current_root_rot = motion.global_rot[current_indices, root]
    fixed_heading = yaw_rotation(heading_yaw(current_root_rot))

    core_indices = [index_by_name[name] for name in CORE_BONES]
    current_core = rotation_6d(motion.local_rot[current_indices][:, core_indices])
    next_core = rotation_6d(motion.local_rot[next_indices][:, core_indices])
    parts = [(next_core - current_core).reshape(current_indices.size, -1)]

    for _side, upper_name, _lower_name, hand_name in ARM_SPECS:
        upper = index_by_name[upper_name]
        hand = index_by_name[hand_name]
        current_hand_pos = np.einsum(
            "...i,...ij->...j",
            motion.global_pos_m[current_indices, hand],
            np.swapaxes(fixed_heading, -1, -2),
        )
        next_hand_pos = np.einsum(
            "...i,...ij->...j",
            motion.global_pos_m[next_indices, hand],
            np.swapaxes(fixed_heading, -1, -2),
        )
        current_hand_rot6 = rotation_6d(
            root_relative_rotation(motion.global_rot[current_indices, hand], fixed_heading)
        )
        next_hand_rot6 = rotation_6d(
            root_relative_rotation(motion.global_rot[next_indices, hand], fixed_heading)
        )
        current_upper_rot6 = rotation_6d(
            root_relative_rotation(motion.global_rot[current_indices, upper], fixed_heading)
        )
        next_upper_rot6 = rotation_6d(
            root_relative_rotation(motion.global_rot[next_indices, upper], fixed_heading)
        )
        parts.extend(
            (
                next_hand_pos - current_hand_pos,
                next_hand_rot6 - current_hand_rot6,
                next_upper_rot6 - current_upper_rot6,
            )
        )

    features = np.concatenate(parts, axis=-1).astype(np.float32)
    if features.shape != (current_indices.size, AE2_DIM):
        raise RuntimeError(f"AE2 feature shape {features.shape} does not match {(current_indices.size, AE2_DIM)}")
    if not np.isfinite(features).all():
        raise ValueError(f"Non-finite AE2 features from {motion.path}")
    return features


def upper_state_features(motion: MotionArrays, indices: np.ndarray) -> np.ndarray:
    """Return the exact 90-value following-root upper state used by Slash2."""

    indices = np.asarray(indices, dtype=np.int64)
    if indices.ndim != 1:
        raise ValueError("Upper-state indices must be a rank-1 vector.")
    if indices.size == 0:
        return np.empty((0, UPPER_STATE_DIM), dtype=np.float32)

    index_by_name = {name: index for index, name in enumerate(motion.names)}
    root = motion.root_index
    root_pos = motion.global_pos_m[indices, root]
    root_rot = motion.global_rot[indices, root]
    core_indices = [index_by_name[name] for name in CORE_BONES]
    parts: list[np.ndarray] = [
        rotation_6d(motion.local_rot[indices][:, core_indices]).reshape(indices.size, -1)
    ]
    for _side, upper_name, _lower_name, hand_name in ARM_SPECS:
        upper = index_by_name[upper_name]
        hand = index_by_name[hand_name]
        parts.extend(
            (
                root_relative_position(motion.global_pos_m[indices, hand], root_pos, root_rot),
                rotation_6d(
                    root_relative_rotation(motion.global_rot[indices, hand], root_rot)
                ),
                rotation_6d(
                    root_relative_rotation(motion.global_rot[indices, upper], root_rot)
                ),
            )
        )
    features = np.concatenate(parts, axis=-1).astype(np.float32)
    if features.shape != (indices.size, UPPER_STATE_DIM):
        raise RuntimeError(
            f"Upper-state shape {features.shape} does not match "
            f"{(indices.size, UPPER_STATE_DIM)}"
        )
    if not np.isfinite(features).all():
        raise ValueError(f"Non-finite upper-state features from {motion.path}")
    return features


def state_conditioned_feature_schema() -> dict[str, object]:
    cursor = 0
    schema: dict[str, object] = {
        "kind": "slash2_upper_state_conditioned_transition_projector",
        "motion_delta": {
            "start": cursor,
            "end": cursor + MOTION_DELTA_DIM,
            "description": "held target-frame proposed next state minus current state",
            "scored": True,
        },
    }
    cursor += MOTION_DELTA_DIM
    schema["previous_upper_state"] = {
        "start": cursor,
        "end": cursor + UPPER_STATE_DIM,
        "reference": "previous upper state in one held target frame",
    }
    cursor += UPPER_STATE_DIM
    schema["current_upper_state"] = {
        "start": cursor,
        "end": cursor + UPPER_STATE_DIM,
        "reference": "current upper state in one held target frame",
    }
    cursor += UPPER_STATE_DIM
    schema["target_condition"] = {
        "start": cursor,
        "end": cursor + len(TARGET_NAMES),
        "names": list(TARGET_NAMES),
        "reference": "target world Y above the zero-height root/floor plane",
    }
    cursor += len(TARGET_NAMES)
    schema["attack_labels"] = {
        "start": cursor,
        "end": cursor + len(ATTACK_LABEL_NAMES),
        "names": list(ATTACK_LABEL_NAMES),
        "scope": "once per transition sample",
    }
    cursor += len(ATTACK_LABEL_NAMES)
    schema.update(
        {
            "score_start": 0,
            "score_end": MOTION_DELTA_DIM,
            "motion_delta_dim": MOTION_DELTA_DIM,
            "upper_state_dim": UPPER_STATE_DIM,
            "phase_or_frame_input": False,
            "total_dim": cursor,
        }
    )
    if cursor != STATE_CONDITIONED_AE_DIM:
        raise RuntimeError(
            f"State-conditioned schema dimension {cursor} != {STATE_CONDITIONED_AE_DIM}"
        )
    return schema


def state_conditioned_ae2_feature_schema() -> dict[str, object]:
    cursor = 0
    schema: dict[str, object] = {
        "kind": "slash2_upper_state_conditioned_transition_projector",
        "prior": "ae2",
        "label_agnostic": True,
        "target_agnostic": True,
        "motion_delta": {
            "start": cursor,
            "end": cursor + MOTION_DELTA_DIM,
            "description": "held target-frame proposed next state minus current state",
            "scored": True,
        },
    }
    cursor += MOTION_DELTA_DIM
    schema["previous_upper_state"] = {
        "start": cursor,
        "end": cursor + UPPER_STATE_DIM,
        "reference": "previous upper state in one held target frame",
    }
    cursor += UPPER_STATE_DIM
    schema["current_upper_state"] = {
        "start": cursor,
        "end": cursor + UPPER_STATE_DIM,
        "reference": "current upper state in one held target frame",
    }
    cursor += UPPER_STATE_DIM
    schema.update(
        {
            "score_start": 0,
            "score_end": MOTION_DELTA_DIM,
            "motion_delta_dim": MOTION_DELTA_DIM,
            "upper_state_dim": UPPER_STATE_DIM,
            "phase_or_frame_input": False,
            "total_dim": cursor,
        }
    )
    if cursor != STATE_CONDITIONED_AE2_DIM:
        raise RuntimeError(
            f"State-conditioned AE2 schema dimension {cursor} != {STATE_CONDITIONED_AE2_DIM}"
        )
    return schema


def target_height_condition(
    motion: MotionArrays,
    next_indices: np.ndarray,
    target_world_m: np.ndarray,
) -> np.ndarray:
    next_indices = np.asarray(next_indices, dtype=np.int64)
    target = np.asarray(target_world_m, dtype=np.float32)
    if target.shape != (3,):
        raise ValueError(f"Expected one world-space target vec3, got {target.shape}")
    return np.full((next_indices.size, 1), target[1], dtype=np.float32)


def root_flatness_metrics(motion: MotionArrays) -> dict[str, float]:
    root_rot = np.asarray(motion.global_rot[:, motion.root_index], dtype=np.float64)
    root_pos = np.asarray(motion.global_pos_m[:, motion.root_index], dtype=np.float64)
    forward = -root_rot[:, 1, :]
    up = root_rot[:, 2, :]
    return {
        "max_abs_forward_vertical": float(np.max(np.abs(forward[:, 1]))),
        "max_up_horizontal": float(np.max(np.linalg.norm(up[:, (0, 2)], axis=-1))),
        "root_height_range_m": float(np.max(root_pos[:, 1]) - np.min(root_pos[:, 1])),
    }


def feature_schema(include_target_and_labels: bool) -> dict[str, object]:
    schema: dict[str, object] = {
        "kind": "slash2_upper_following_root_transition_delta",
        "delta_parameterization": "next following-root values minus current following-root values",
        "motion_delta_dim": MOTION_DELTA_DIM,
        "score_start": 0,
        "score_end": MOTION_DELTA_DIM,
        "core": {
            "start": 0,
            "end": CORE_DELTA_DIM,
            "bones": list(CORE_BONES),
            "channels_per_bone": ["rotation_6d_delta"],
        },
        "arms": {
            "start": CORE_DELTA_DIM,
            "end": MOTION_DELTA_DIM,
            "order": [spec[0] for spec in ARM_SPECS],
            "channels_per_arm": ["hand_position_delta_m", "hand_rotation_6d_delta", "upperarm_rotation_6d_delta"],
            "lowerarm_contract": "implicit two-bone IK middle joint, matching the run/walk thigh-calf-end encoding",
        },
        "root_condition": {
            "start": MOTION_DELTA_DIM,
            "end": AE2_DIM,
            "names": list(ROOT_CONDITION_NAMES),
            "reference": "current root",
        },
        "target_agnostic": not include_target_and_labels,
        "label_agnostic": not include_target_and_labels,
    }
    cursor = AE2_DIM
    if include_target_and_labels:
        schema["target_condition"] = {
            "start": cursor,
            "end": cursor + len(TARGET_NAMES),
            "names": list(TARGET_NAMES),
            "reference": "next root",
        }
        cursor += len(TARGET_NAMES)
        schema["attack_labels"] = {
            "start": cursor,
            "end": cursor + len(ATTACK_LABEL_NAMES),
            "names": list(ATTACK_LABEL_NAMES),
            "scope": "once per transition sample",
        }
        cursor += len(ATTACK_LABEL_NAMES)
    schema["total_dim"] = cursor
    return schema
