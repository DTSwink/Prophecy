from __future__ import annotations

"""Load the explicit controller-owned pose coordinates from attack NPZs.

The NPZ must already carry the native controller contract.  No joint position
is fitted back into a rotation here: knees/calves and elbows/lower arms are
decoder output, never target inputs.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from target_frame_codec import TARGET_FRAME_SCHEMA, TARGET_FRAME_SCHEMA_VERSION


@dataclass(frozen=True)
class ControllerTargetArrays:
    path: Path
    names: tuple[str, ...]
    parents: np.ndarray
    visible_global_pos_m: np.ndarray
    source_global_rot: np.ndarray
    controller_global_rot: np.ndarray
    controller_local_rot: np.ndarray
    default_local_translation_m: np.ndarray
    root_index: int
    target_origin_world_m: np.ndarray
    target_height_m: float
    pelvis_target_heading: np.ndarray
    lower_hybrid_state: np.ndarray
    upper_hybrid_state: np.ndarray
    armed_event_lower_hybrid: np.ndarray
    armed_event_upper_hybrid: np.ndarray
    armed_event_heading: np.ndarray
    hit_event_lower_hybrid: np.ndarray
    hit_event_upper_hybrid: np.ndarray
    hit_event_heading: np.ndarray
    final_lower_hybrid: np.ndarray
    final_upper_hybrid: np.ndarray
    final_heading: np.ndarray

    @property
    def frame_count(self) -> int:
        return int(self.visible_global_pos_m.shape[0])


def _normalize(values: np.ndarray, *, context: str) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    length = np.linalg.norm(values, axis=-1, keepdims=True)
    if np.any(length < 1.0e-8):
        raise ValueError(f"Degenerate vector while fitting {context}")
    return values / length


def local_rotations_from_global(global_rot: np.ndarray, parents: np.ndarray) -> np.ndarray:
    global_rot = np.asarray(global_rot, dtype=np.float32)
    local = np.empty_like(global_rot)
    for bone, parent in enumerate(np.asarray(parents, dtype=np.int64).tolist()):
        local[:, bone] = (
            global_rot[:, bone]
            if int(parent) < 0
            else global_rot[:, bone] @ np.swapaxes(global_rot[:, int(parent)], -1, -2)
        )
    return local


def load_controller_target_arrays(path: Path) -> ControllerTargetArrays:
    path = path.resolve()
    with np.load(path, allow_pickle=False) as data:
        required = {
            "bone_names",
            "parents",
            "controller_dof_schema_version",
            "controller_ik_payload",
            "controller_render_global_joint_pos_m",
            "controller_render_global_rot",
            "controller_render_local_rot",
            "controller_default_local_translation_m",
            "model_global_joint_pos_m",
            "model_global_matrix",
            "model_ik_payload",
            "slash2_target_frame_schema",
            "slash2_target_frame_schema_version",
            "slash2_target_origin_world_m",
            "slash2_target_height_m",
            "slash2_pelvis_target_heading",
            "slash2_lower_hybrid_state",
            "slash2_upper_hybrid_state",
            "slash2_target_hybrid",
            "slash2_armed_event_lower_hybrid",
            "slash2_armed_event_upper_hybrid",
            "slash2_armed_event_heading",
            "slash2_hit_event_lower_hybrid",
            "slash2_hit_event_upper_hybrid",
            "slash2_hit_event_heading",
            "slash2_final_lower_hybrid",
            "slash2_final_upper_hybrid",
            "slash2_final_heading",
        }
        missing = sorted(required - set(data.files))
        if missing:
            raise ValueError(
                f"{path} is a legacy/non-controller attack NPZ; missing {missing}"
            )
        version = int(np.asarray(data["controller_dof_schema_version"]).reshape(()))
        if version != 3:
            raise ValueError(f"{path} has unsupported controller schema {version}")
        target_schema = str(
            np.asarray(data["slash2_target_frame_schema"]).reshape(())
        )
        if target_schema != TARGET_FRAME_SCHEMA:
            raise ValueError(
                f"{path} has unsupported target-frame schema {target_schema!r}"
            )
        target_schema_version = int(
            np.asarray(data["slash2_target_frame_schema_version"]).reshape(())
        )
        if target_schema_version != TARGET_FRAME_SCHEMA_VERSION:
            raise ValueError(
                f"{path} has unsupported target-frame schema version "
                f"{target_schema_version}"
            )
        names = tuple(str(value) for value in data["bone_names"].tolist())
        parents = np.asarray(data["parents"], dtype=np.int32).copy()
        positions = np.asarray(
            data["controller_render_global_joint_pos_m"],
            dtype=np.float32,
        ).copy()
        controller_rot = np.asarray(
            data["controller_render_global_rot"],
            dtype=np.float32,
        ).copy()
        local = np.asarray(
            data["controller_render_local_rot"],
            dtype=np.float32,
        ).copy()
        offsets = np.asarray(
            data["controller_default_local_translation_m"],
            dtype=np.float32,
        ).copy()
        target_origin = np.asarray(
            data["slash2_target_origin_world_m"], dtype=np.float32
        ).reshape(3).copy()
        target_height = float(
            np.asarray(data["slash2_target_height_m"], dtype=np.float32).reshape(())
        )
        pelvis_target_heading = np.asarray(
            data["slash2_pelvis_target_heading"], dtype=np.float32
        ).copy()
        lower_hybrid = np.asarray(
            data["slash2_lower_hybrid_state"], dtype=np.float32
        ).copy()
        upper_hybrid = np.asarray(
            data["slash2_upper_hybrid_state"], dtype=np.float32
        ).copy()
        armed_event_lower = np.asarray(
            data["slash2_armed_event_lower_hybrid"], dtype=np.float32
        ).reshape(41).copy()
        armed_event_upper = np.asarray(
            data["slash2_armed_event_upper_hybrid"], dtype=np.float32
        ).reshape(90).copy()
        armed_event_heading = np.asarray(
            data["slash2_armed_event_heading"], dtype=np.float32
        ).reshape(3, 3).copy()
        hit_event_lower = np.asarray(
            data["slash2_hit_event_lower_hybrid"], dtype=np.float32
        ).reshape(41).copy()
        hit_event_upper = np.asarray(
            data["slash2_hit_event_upper_hybrid"], dtype=np.float32
        ).reshape(90).copy()
        hit_event_heading = np.asarray(
            data["slash2_hit_event_heading"], dtype=np.float32
        ).reshape(3, 3).copy()
        final_lower = np.asarray(
            data["slash2_final_lower_hybrid"], dtype=np.float32
        ).reshape(41).copy()
        final_upper = np.asarray(
            data["slash2_final_upper_hybrid"], dtype=np.float32
        ).reshape(90).copy()
        final_heading = np.asarray(
            data["slash2_final_heading"], dtype=np.float32
        ).reshape(3, 3).copy()
        target_hybrid = np.asarray(
            data["slash2_target_hybrid"], dtype=np.float32
        )
        model_positions = np.asarray(
            data["model_global_joint_pos_m"],
            dtype=np.float32,
        )
        model_rotations = np.asarray(
            data["model_global_matrix"][..., :3, :3],
            dtype=np.float32,
        )
        if not np.array_equal(
            np.asarray(data["controller_ik_payload"], dtype=np.float32),
            np.asarray(data["model_ik_payload"], dtype=np.float32),
        ):
            raise ValueError(f"{path} controller/model IK payloads differ")
    if not np.array_equal(positions, model_positions):
        raise ValueError(f"{path} model positions are not the controller render cache")
    if not np.array_equal(controller_rot, model_rotations):
        raise ValueError(f"{path} model rotations are not the controller render cache")
    for label, values in (
        ("positions", positions),
        ("controller rotations", controller_rot),
        ("controller local rotations", local),
        ("pelvis target heading", pelvis_target_heading),
        ("lower hybrid state", lower_hybrid),
        ("upper hybrid state", upper_hybrid),
        ("armed event lower", armed_event_lower),
        ("armed event upper", armed_event_upper),
        ("armed event heading", armed_event_heading),
        ("hit event lower", hit_event_lower),
        ("hit event upper", hit_event_upper),
        ("hit event heading", hit_event_heading),
        ("final lower", final_lower),
        ("final upper", final_upper),
        ("final heading", final_heading),
    ):
        if not np.isfinite(values).all():
            raise ValueError(f"{path} contains non-finite {label}")
    frame_count = int(positions.shape[0])
    if pelvis_target_heading.shape != (frame_count, 3, 3):
        raise ValueError(
            f"{path} pelvis-target heading shape {pelvis_target_heading.shape} is invalid"
        )
    if lower_hybrid.shape != (frame_count, 41):
        raise ValueError(f"{path} lower hybrid shape {lower_hybrid.shape} is invalid")
    if upper_hybrid.shape != (frame_count, 90):
        raise ValueError(f"{path} upper hybrid shape {upper_hybrid.shape} is invalid")
    expected_target = np.zeros((frame_count, 3), dtype=np.float32)
    expected_target[:, 1] = np.float32(target_height)
    if target_hybrid.shape != expected_target.shape or not np.allclose(
        target_hybrid, expected_target, atol=1.0e-6, rtol=0.0
    ):
        raise ValueError(f"{path} does not encode target as (0,height,0)")
    return ControllerTargetArrays(
        path=path,
        names=names,
        parents=parents,
        visible_global_pos_m=positions,
        source_global_rot=controller_rot,
        controller_global_rot=controller_rot,
        controller_local_rot=local,
        default_local_translation_m=offsets,
        root_index=names.index("root"),
        target_origin_world_m=target_origin,
        target_height_m=target_height,
        pelvis_target_heading=pelvis_target_heading,
        lower_hybrid_state=lower_hybrid,
        upper_hybrid_state=upper_hybrid,
        armed_event_lower_hybrid=armed_event_lower,
        armed_event_upper_hybrid=armed_event_upper,
        armed_event_heading=armed_event_heading,
        hit_event_lower_hybrid=hit_event_lower,
        hit_event_upper_hybrid=hit_event_upper,
        hit_event_heading=hit_event_heading,
        final_lower_hybrid=final_lower,
        final_upper_hybrid=final_upper,
        final_heading=final_heading,
    )


def direction_angle_deg(
    rotations: np.ndarray,
    local_offset: np.ndarray,
    visible_vector: np.ndarray,
) -> np.ndarray:
    predicted = np.einsum("i,tij->tj", _normalize(local_offset, context="audit offset"), rotations)
    target = _normalize(visible_vector, context="audit visible vector")
    cosine = np.clip(np.sum(predicted * target, axis=-1), -1.0, 1.0)
    return np.rad2deg(np.arccos(cosine)).astype(np.float32)


def rotation_6d(rotation: np.ndarray) -> np.ndarray:
    rotation = np.asarray(rotation, dtype=np.float32)
    return rotation[..., :2, :].reshape(*rotation.shape[:-2], 6)


def _root_relative_position(
    world: np.ndarray,
    root_position: np.ndarray,
    root_rotation: np.ndarray,
) -> np.ndarray:
    return np.einsum(
        "ti,tij->tj",
        np.asarray(world, dtype=np.float32) - np.asarray(root_position, dtype=np.float32),
        np.swapaxes(np.asarray(root_rotation, dtype=np.float32), -1, -2),
    ).astype(np.float32)


def _root_relative_rotation(rotation: np.ndarray, root_rotation: np.ndarray) -> np.ndarray:
    return (
        np.asarray(rotation, dtype=np.float32)
        @ np.swapaxes(np.asarray(root_rotation, dtype=np.float32), -1, -2)
    ).astype(np.float32)


def lower_target_output_from_clip(
    clip: object,
    targets: ControllerTargetArrays | None = None,
) -> torch.Tensor:
    """Build the exact lower IK vector from visible GT and fitted thigh rotations."""

    if targets is None:
        targets = load_controller_target_arrays(Path(getattr(clip, "path")))
    body_names = list(getattr(clip, "body_names"))
    index = {name: i for i, name in enumerate(targets.names)}
    root = targets.root_index
    root_pos = targets.visible_global_pos_m[:, root]
    root_rot = targets.source_global_rot[:, root]
    pelvis_name = body_names[int(getattr(clip, "pelvis"))]
    pelvis = index[pelvis_name]
    pelvis_pos = _root_relative_position(
        targets.visible_global_pos_m[:, pelvis], root_pos, root_rot
    )
    pelvis_rot6 = rotation_6d(
        _root_relative_rotation(targets.controller_global_rot[:, pelvis], root_rot)
    )

    payload = np.asarray(
        getattr(clip, "ik_payload").detach().cpu(), dtype=np.float32
    ).copy()
    for spec in getattr(clip, "ik_payload_slices"):
        if str(spec["kind"]) != "leg":
            continue
        start_name = body_names[int(spec["start"])]
        end_name = body_names[int(spec["end"])]
        start = index[start_name]
        end = index[end_name]
        pos_slice = spec["pos"]
        rot_slice = spec["rot6"]
        start_rot_slice = spec["start_rot6"]
        if not all(isinstance(value, slice) for value in (pos_slice, rot_slice, start_rot_slice)):
            raise TypeError("IK payload position/rotation fields must be slices")
        payload[:, pos_slice] = _root_relative_position(
            targets.visible_global_pos_m[:, end], root_pos, root_rot
        )
        payload[:, rot_slice] = rotation_6d(
            _root_relative_rotation(targets.source_global_rot[:, end], root_rot)
        )
        payload[:, start_rot_slice] = rotation_6d(
            _root_relative_rotation(targets.controller_global_rot[:, start], root_rot)
        )

    output = np.concatenate((pelvis_pos, pelvis_rot6, payload), axis=-1).astype(np.float32)
    expected = 3 + 6 + int(getattr(clip, "ik_payload_dim"))
    if output.shape != (targets.frame_count, expected):
        raise RuntimeError(f"Lower target shape {output.shape} != {(targets.frame_count, expected)}")
    if not np.isfinite(output).all():
        raise ValueError(f"Non-finite lower controller targets from {targets.path}")
    return torch.from_numpy(output)


def install_lower_targets_on_store(store: object) -> list[ControllerTargetArrays]:
    """Replace a store's stale NPZ-matrix targets with the shared visible-GT targets."""

    clips = list(getattr(store, "clips"))
    arrays = [load_controller_target_arrays(Path(clip.path)) for clip in clips]
    outputs = [lower_target_output_from_clip(clip, target) for clip, target in zip(clips, arrays)]
    install_lower_target_output_on_store(store, torch.cat(outputs, dim=0))
    return arrays


def install_lower_target_output_on_store(store: object, output: torch.Tensor) -> None:
    """Install an already-materialized native lower target tensor on one store."""

    clips = list(getattr(store, "clips"))
    expected_rows = sum(int(getattr(clip, "T")) for clip in clips)
    expected_dim = 3 + 6 + int(getattr(clips[0], "ik_payload_dim"))
    if output.shape != (expected_rows, expected_dim):
        raise ValueError(
            f"Native lower target cache shape {tuple(output.shape)} != "
            f"{(expected_rows, expected_dim)}"
        )
    device = getattr(store, "device")
    combined = output.to(device=device, dtype=torch.float32)
    setattr(store, "pelvis_local_pos", combined[:, :3])
    setattr(store, "pelvis_rot6", combined[:, 3:9])
    setattr(store, "ik_payload", combined[:, 9:])
    setattr(store, "target_output", combined)
