from __future__ import annotations

"""Differentiable swept blade-box collision against the Slash2 body volumes.

The moving blade is an oriented box attached to ``hand_r``.  Body capsules,
spheres, and boxes follow the same dimensions used by Model Viewer.  A fixed
fractional-frame stencil makes crossings visible even when both integer-frame
poses are disjoint.  Every operation is a regular PyTorch operation, so the
penetration loss is differentiable almost everywhere and CUDA-graph safe.
"""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Collection, Sequence

import torch


SWEEP_SAMPLES = 9
CAPSULE_AXIS_SAMPLES = 9

# These are the explicit training defaults requested for a right-hand-held
# blade.  Callers can pass another set without changing detector math.
DEFAULT_EXCLUDED_COLLIDERS = (
    "right_lowerarm",
    "right_hand",
    "left_calf",
    "right_calf",
    "left_foot",
    "right_foot",
)

CAPSULE_DEFINITIONS = (
    ("upper_neck", "spine_05", "neck_01", 0.042),
    ("neck", "neck_01", "neck_02", 0.020),
    ("left_clavicle", "clavicle_l", "upperarm_l", 0.032),
    ("left_upperarm", "upperarm_l", "lowerarm_l", 0.043),
    ("left_lowerarm", "lowerarm_l", "hand_l", 0.037),
    ("right_clavicle", "clavicle_r", "upperarm_r", 0.032),
    ("right_upperarm", "upperarm_r", "lowerarm_r", 0.043),
    ("right_lowerarm", "lowerarm_r", "hand_r", 0.037),
    ("left_thigh", "thigh_l", "calf_l", 0.064),
    ("left_calf", "calf_l", "foot_l", 0.052),
    ("right_thigh", "thigh_r", "calf_r", 0.064),
    ("right_calf", "calf_r", "foot_r", 0.052),
)

SPHERE_DEFINITIONS = (
    ("left_knee", "calf_l", 0.058),
    ("right_knee", "calf_r", 0.058),
    ("left_wrist", "lowerarm_l", 0.041),
    ("right_wrist", "lowerarm_r", 0.041),
)

BODY_BOX_NAMES = (
    "torso_lower",
    "torso_middle",
    "torso_upper",
    "torso_shoulder_connector",
    "shoulders",
    "left_hand",
)

RIGHT_LOWERARM_SELF_COLLISION_NAMES = (
    "right_lowerarm_vs_torso_lower",
    "right_lowerarm_vs_torso_middle",
    "right_lowerarm_vs_torso_upper",
    "right_lowerarm_vs_head",
)
RIGHT_LOWERARM_RADIUS_M = 0.037


@dataclass(frozen=True)
class BladeBoxDefinition:
    name: str
    attach_joint: str
    center_local_m: tuple[float, float, float]
    axes_local_rows: tuple[tuple[float, float, float], ...]
    half_extents_m: tuple[float, float, float]
    schema_version: int = 1


@dataclass(frozen=True)
class BodyCollisionLayout:
    body_names: tuple[str, ...]
    capsule_names: tuple[str, ...]
    capsule_start: tuple[int, ...]
    capsule_end: tuple[int, ...]
    capsule_radius_m: tuple[float, ...]
    sphere_names: tuple[str, ...]
    sphere_joint: tuple[int, ...]
    sphere_radius_m: tuple[float, ...]
    box_names: tuple[str, ...]
    excluded: tuple[str, ...]


@dataclass
class CollisionResult:
    loss_rows: torch.Tensor
    max_penetration_m: torch.Tensor
    bad_rate: torch.Tensor
    collider_penetration_m: torch.Tensor
    collider_names: tuple[str, ...]


def load_blade_box_definition(path: Path) -> BladeBoxDefinition:
    raw = json.loads(path.read_text(encoding="utf-8"))
    axes = tuple(tuple(float(value) for value in row) for row in raw["axes_local_rows"])
    if len(axes) != 3 or any(len(row) != 3 for row in axes):
        raise ValueError(f"{path}: axes_local_rows must be 3x3")
    center = tuple(float(value) for value in raw["center_local_m"])
    half = tuple(float(value) for value in raw["half_extents_m"])
    if len(center) != 3 or len(half) != 3 or min(half) <= 0.0:
        raise ValueError(f"{path}: invalid center/half extents")
    return BladeBoxDefinition(
        name=str(raw["name"]),
        attach_joint=str(raw["attach_joint"]),
        center_local_m=center,
        axes_local_rows=axes,
        half_extents_m=half,
        schema_version=int(raw.get("schema_version", 1)),
    )


def build_body_collision_layout(
    body_names: Sequence[str],
    excluded: Collection[str] = DEFAULT_EXCLUDED_COLLIDERS,
) -> BodyCollisionLayout:
    names = tuple(str(name) for name in body_names)
    by_name = {name: index for index, name in enumerate(names)}
    excluded_set = {str(name) for name in excluded}
    known = {item[0] for item in CAPSULE_DEFINITIONS} | {item[0] for item in SPHERE_DEFINITIONS} | set(
        BODY_BOX_NAMES
    ) | {"pelvis", "head", "left_foot", "right_foot", "right_hand"}
    unknown = sorted(excluded_set - known)
    if unknown:
        raise ValueError(f"Unknown body collision exclusions: {unknown}")

    capsule = [item for item in CAPSULE_DEFINITIONS if item[0] not in excluded_set]
    missing = sorted({joint for _name, a, b, _radius in capsule for joint in (a, b)} - set(by_name))
    if missing:
        raise ValueError(f"Body skeleton lacks collision capsule joints: {missing}")

    spheres = [item for item in SPHERE_DEFINITIONS if item[0] not in excluded_set]
    # A discarded calf/foot also discards the joint sphere at that boundary.
    spheres = [
        item
        for item in spheres
        if not (
            item[0] == "left_knee" and "left_calf" in excluded_set
            or item[0] == "right_knee" and "right_calf" in excluded_set
            or item[0] == "right_wrist" and "right_lowerarm" in excluded_set
        )
    ]
    missing = sorted({joint for _name, joint, _radius in spheres} - set(by_name))
    if missing:
        raise ValueError(f"Body skeleton lacks collision sphere joints: {missing}")

    box_names = tuple(name for name in BODY_BOX_NAMES if name not in excluded_set)
    if "right_hand" not in excluded_set:
        box_names = (*box_names, "right_hand")
    for required in ("pelvis", "spine_05", "clavicle_l", "clavicle_r", "hand_l", "hand_r"):
        if required not in by_name:
            raise ValueError(f"Body skeleton lacks collision box joint {required!r}")

    return BodyCollisionLayout(
        body_names=names,
        capsule_names=tuple(item[0] for item in capsule),
        capsule_start=tuple(by_name[item[1]] for item in capsule),
        capsule_end=tuple(by_name[item[2]] for item in capsule),
        capsule_radius_m=tuple(float(item[3]) for item in capsule),
        sphere_names=tuple(item[0] for item in spheres),
        sphere_joint=tuple(by_name[item[1]] for item in spheres),
        sphere_radius_m=tuple(float(item[2]) for item in spheres),
        box_names=box_names,
        excluded=tuple(sorted(excluded_set)),
    )


def _normalize(vector: torch.Tensor, eps: float = 1.0e-8) -> torch.Tensor:
    return vector / vector.square().sum(dim=-1, keepdim=True).clamp_min(eps).sqrt()


def _orthonormalize_axes(raw: torch.Tensor) -> torch.Tensor:
    x = _normalize(raw[..., 0, :])
    y_raw = raw[..., 1, :] - (raw[..., 1, :] * x).sum(dim=-1, keepdim=True) * x
    y = _normalize(y_raw)
    z = _normalize(torch.cross(x, y, dim=-1))
    z = torch.where(
        ((z * raw[..., 2, :]).sum(dim=-1, keepdim=True) < 0.0),
        -z,
        z,
    )
    y = _normalize(torch.cross(z, x, dim=-1))
    return torch.stack((x, y, z), dim=-2)


def blade_box_from_pose(
    positions: torch.Tensor,
    rotations: torch.Tensor,
    attach_joint: int,
    definition: BladeBoxDefinition,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    hand_position = positions[:, attach_joint]
    hand_rotation = rotations[:, attach_joint]
    # Build immutable geometry from CUDA-resident scalar expressions. Creating
    # a tensor from Python/CPU data here would make graph capture attempt a
    # forbidden CPU->CUDA copy.
    one = hand_position[:, 0] * 0.0 + 1.0
    center_local = torch.stack(
        tuple(one * float(value) for value in definition.center_local_m), dim=-1
    )
    axes_local = torch.stack(
        tuple(
            torch.stack(tuple(one * float(value) for value in row), dim=-1)
            for row in definition.axes_local_rows
        ),
        dim=-2,
    )
    half = torch.stack(
        tuple(one * float(value) for value in definition.half_extents_m), dim=-1
    )
    center = torch.matmul(center_local.unsqueeze(1), hand_rotation).squeeze(1) + hand_position
    axes = torch.matmul(axes_local, hand_rotation)
    axes = _orthonormalize_axes(axes)
    return center, axes, half


def interpolate_boxes(
    center_a: torch.Tensor,
    axes_a: torch.Tensor,
    half_a: torch.Tensor,
    center_b: torch.Tensor,
    axes_b: torch.Tensor,
    half_b: torch.Tensor,
    samples: int = SWEEP_SAMPLES,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    alpha = torch.linspace(0.0, 1.0, samples, dtype=center_a.dtype, device=center_a.device)
    center = center_a[:, None] + (center_b - center_a)[:, None] * alpha[None, :, None]
    raw_axes = axes_a[:, None] + (axes_b - axes_a)[:, None] * alpha[None, :, None, None]
    axes = _orthonormalize_axes(raw_axes)
    half = half_a[:, None] + (half_b - half_a)[:, None] * alpha[None, :, None]
    return center, axes, half


def point_box_signed_distance(
    points: torch.Tensor,
    box_center: torch.Tensor,
    box_axes: torch.Tensor,
    box_half: torch.Tensor,
) -> torch.Tensor:
    """Signed point/OBB distance; negative values are inside the box."""

    local = torch.einsum("...d,...ad->...a", points - box_center, box_axes)
    q = local.abs() - box_half
    outside_sq = q.clamp_min(0.0).square().sum(dim=-1)
    outside = torch.where(
        outside_sq > 0.0,
        outside_sq.clamp_min(1.0e-16).sqrt(),
        torch.zeros_like(outside_sq),
    )
    inside = q.amax(dim=-1).clamp_max(0.0)
    return outside + inside


def swept_box_capsule_penetration(
    box_center_a: torch.Tensor,
    box_axes_a: torch.Tensor,
    box_half_a: torch.Tensor,
    box_center_b: torch.Tensor,
    box_axes_b: torch.Tensor,
    box_half_b: torch.Tensor,
    capsule_start_a: torch.Tensor,
    capsule_end_a: torch.Tensor,
    capsule_start_b: torch.Tensor,
    capsule_end_b: torch.Tensor,
    capsule_radius: torch.Tensor,
    sweep_samples: int = SWEEP_SAMPLES,
    axis_samples: int = CAPSULE_AXIS_SAMPLES,
) -> torch.Tensor:
    """Return maximum fractional-frame penetration for each body capsule.

    Each temporal sample uses the exact OBB-vs-segment SAT axes, expanded by
    the capsule radius. Degenerate segments (body spheres) use the exact
    point-to-OBB signed distance. ``axis_samples`` remains in the public
    signature for checkpoint-era callers but is intentionally unnecessary.
    """

    del axis_samples

    center, axes, half = interpolate_boxes(
        box_center_a, box_axes_a, box_half_a, box_center_b, box_axes_b, box_half_b, sweep_samples
    )
    alpha = torch.linspace(0.0, 1.0, sweep_samples, dtype=center.dtype, device=center.device)
    start = capsule_start_a[:, :, None] + (
        capsule_start_b - capsule_start_a
    )[:, :, None] * alpha[None, None, :, None]
    end = capsule_end_a[:, :, None] + (
        capsule_end_b - capsule_end_a
    )[:, :, None] * alpha[None, None, :, None]
    segment_center = (start + end) * 0.5
    segment_half = (end - start) * 0.5
    batch, collider_count, _sample_count, _xyz = segment_center.shape
    face_axes = axes[:, None].expand(-1, collider_count, -1, -1, -1)
    cross_axes = torch.cross(segment_half[..., None, :], face_axes, dim=-1)
    cross_sq = cross_axes.square().sum(dim=-1, keepdim=True)
    cross_norm = cross_sq.clamp_min(1.0e-16).sqrt()
    cross_valid = cross_norm.squeeze(-1) > 1.0e-7
    cross_axes = cross_axes / cross_norm.clamp_min(1.0e-8)
    candidates = torch.cat((face_axes, cross_axes), dim=-2)

    delta = segment_center - center[:, None]
    distance = torch.einsum("bcsd,bcskd->bcsk", delta, candidates).abs()
    box_projection = torch.einsum(
        "bcskd,bsad->bcska", candidates, axes
    ).abs()
    box_projection = (
        box_projection * half[:, None, :, None, :]
    ).sum(dim=-1)
    segment_projection = torch.einsum(
        "bcsd,bcskd->bcsk", segment_half, candidates
    ).abs()
    if capsule_radius.ndim == 1:
        radius = capsule_radius[None, :, None]
    elif capsule_radius.ndim == 2:
        radius = capsule_radius[:, :, None]
    else:
        raise ValueError(f"Capsule radii must be [collider] or [batch, collider], got {capsule_radius.shape}")
    gap = distance - box_projection - segment_projection - radius[..., None]
    valid = torch.cat(
        (
            torch.ones_like(gap[..., :3], dtype=torch.bool),
            cross_valid,
        ),
        dim=-1,
    )
    gap = torch.where(valid, gap, torch.full_like(gap, -1.0e6))
    capsule_penetration = (-gap.amax(dim=-1)).clamp_min(0.0)

    sphere_distance = point_box_signed_distance(
        segment_center,
        center[:, None],
        axes[:, None],
        half[:, None],
    )
    sphere_penetration = (radius - sphere_distance).clamp_min(0.0)
    degenerate = segment_half.square().sum(dim=-1) <= 1.0e-12
    penetration = torch.where(degenerate, sphere_penetration, capsule_penetration)
    return penetration.amax(dim=-1)


def _obb_sat_penetration(
    center_a: torch.Tensor,
    axes_a: torch.Tensor,
    half_a: torch.Tensor,
    center_b: torch.Tensor,
    axes_b: torch.Tensor,
    half_b: torch.Tensor,
) -> torch.Tensor:
    center_a, center_b = torch.broadcast_tensors(center_a, center_b)
    axes_a, axes_b = torch.broadcast_tensors(axes_a, axes_b)
    half_a, half_b = torch.broadcast_tensors(half_a, half_b)
    delta = center_b - center_a
    cross = torch.cross(axes_a[..., :, None, :], axes_b[..., None, :, :], dim=-1)
    cross_sq = cross.square().sum(dim=-1, keepdim=True)
    cross_norm = cross_sq.clamp_min(1.0e-16).sqrt()
    cross_axis = cross / cross_norm.clamp_min(1.0e-8)
    axes = torch.cat((axes_a, axes_b, cross_axis.flatten(-3, -2)), dim=-2)
    distance = torch.einsum("...d,...kd->...k", delta, axes).abs()
    radius_a = torch.einsum("...ad,...kd->...ka", axes_a, axes).abs()
    radius_a = (radius_a * half_a[..., None, :]).sum(dim=-1)
    radius_b = torch.einsum("...ad,...kd->...ka", axes_b, axes).abs()
    radius_b = (radius_b * half_b[..., None, :]).sum(dim=-1)
    gap = distance - radius_a - radius_b
    cross_valid = cross_norm.squeeze(-1).flatten(-2, -1) > 1.0e-5
    valid = torch.cat(
        (
            torch.ones_like(gap[..., :6], dtype=torch.bool),
            cross_valid,
        ),
        dim=-1,
    )
    gap = torch.where(valid, gap, torch.full_like(gap, -1.0e6))
    return (-gap.amax(dim=-1)).clamp_min(0.0)


def swept_box_box_penetration(
    box_center_a: torch.Tensor,
    box_axes_a: torch.Tensor,
    box_half_a: torch.Tensor,
    box_center_b: torch.Tensor,
    box_axes_b: torch.Tensor,
    box_half_b: torch.Tensor,
    body_center_a: torch.Tensor,
    body_axes_a: torch.Tensor,
    body_half_a: torch.Tensor,
    body_center_b: torch.Tensor,
    body_axes_b: torch.Tensor,
    body_half_b: torch.Tensor,
    sweep_samples: int = SWEEP_SAMPLES,
) -> torch.Tensor:
    blade_center, blade_axes, blade_half = interpolate_boxes(
        box_center_a, box_axes_a, box_half_a, box_center_b, box_axes_b, box_half_b, sweep_samples
    )
    batch, body_count = body_center_a.shape[:2]
    flat = batch * body_count
    body_center, body_axes, body_half = interpolate_boxes(
        body_center_a.reshape(flat, 3),
        body_axes_a.reshape(flat, 3, 3),
        body_half_a.reshape(flat, 3),
        body_center_b.reshape(flat, 3),
        body_axes_b.reshape(flat, 3, 3),
        body_half_b.reshape(flat, 3),
        sweep_samples,
    )
    body_center = body_center.reshape(batch, body_count, sweep_samples, 3)
    body_axes = body_axes.reshape(batch, body_count, sweep_samples, 3, 3)
    body_half = body_half.reshape(batch, body_count, sweep_samples, 3)
    penetration = _obb_sat_penetration(
        blade_center[:, None],
        blade_axes[:, None],
        blade_half[:, None],
        body_center,
        body_axes,
        body_half,
    )
    return penetration.amax(dim=-1)


def swept_capsule_sphere_penetration(
    capsule_start_a: torch.Tensor,
    capsule_end_a: torch.Tensor,
    capsule_start_b: torch.Tensor,
    capsule_end_b: torch.Tensor,
    capsule_radius: torch.Tensor,
    sphere_center_a: torch.Tensor,
    sphere_center_b: torch.Tensor,
    sphere_radius_a: torch.Tensor,
    sphere_radius_b: torch.Tensor,
    sweep_samples: int = SWEEP_SAMPLES,
) -> torch.Tensor:
    """Maximum swept penetration of moving capsules against moving spheres."""

    alpha = torch.linspace(
        0.0,
        1.0,
        sweep_samples,
        dtype=capsule_start_a.dtype,
        device=capsule_start_a.device,
    )
    start = capsule_start_a[:, :, None] + (
        capsule_start_b - capsule_start_a
    )[:, :, None] * alpha[None, None, :, None]
    end = capsule_end_a[:, :, None] + (
        capsule_end_b - capsule_end_a
    )[:, :, None] * alpha[None, None, :, None]
    center = sphere_center_a[:, :, None] + (
        sphere_center_b - sphere_center_a
    )[:, :, None] * alpha[None, None, :, None]
    segment = end - start
    projection = (
        ((center - start) * segment).sum(dim=-1)
        / segment.square().sum(dim=-1).clamp_min(1.0e-12)
    ).clamp(0.0, 1.0)
    closest = start + segment * projection[..., None]
    distance = (center - closest).square().sum(dim=-1).clamp_min(1.0e-16).sqrt()
    capsule_r = capsule_radius
    if capsule_r.ndim == 1:
        capsule_r = capsule_r[None]
    sphere_r = sphere_radius_a[:, :, None] + (
        sphere_radius_b - sphere_radius_a
    )[:, :, None] * alpha[None, None, :]
    return (capsule_r[:, :, None] + sphere_r - distance).clamp_min(0.0).amax(dim=-1)


def _body_frame(positions: torch.Tensor, by_name: dict[str, int]) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    pelvis = positions[:, by_name["pelvis"]]
    chest = positions[:, by_name["spine_05"]]
    up = _normalize(chest - pelvis)
    side_raw = positions[:, by_name["clavicle_l"]] - positions[:, by_name["clavicle_r"]]
    side = _normalize(side_raw - (side_raw * up).sum(dim=-1, keepdim=True) * up)
    forward = _normalize(torch.cross(side, up, dim=-1))
    side = _normalize(torch.cross(up, forward, dim=-1))
    return side, up, forward


def body_boxes(
    positions: torch.Tensor,
    rotations: torch.Tensor,
    layout: BodyCollisionLayout,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    by_name = {name: index for index, name in enumerate(layout.body_names)}
    side, up, forward = _body_frame(positions, by_name)
    pelvis = positions[:, by_name["pelvis"]]
    chest = positions[:, by_name["spine_05"]]
    hip_distance = (positions[:, by_name["thigh_l"]] - positions[:, by_name["thigh_r"]]).norm(dim=-1)
    base_width = (hip_distance + 0.09).clamp(0.25, 0.32)
    base = pelvis + up * 0.060
    top = chest - up * 0.030
    torso_height = (top - base).norm(dim=-1).clamp(0.30, 0.48)
    box_height = (torso_height / 3.0).clamp_min(0.080)
    widths = torch.stack((base_width * 0.86, base_width * 0.96, base_width * 1.06), dim=-1)
    depths = torch.stack((base_width * 0.54, base_width * 0.57, base_width * 0.55), dim=-1)

    centers = []
    axes = []
    half = []
    frame = torch.stack((side, up, forward), dim=-2)
    for index in range(3):
        centers.append(base + up * (box_height * (0.5 + index))[:, None])
        axes.append(frame)
        half.append(torch.stack((widths[:, index], box_height, depths[:, index]), dim=-1) * 0.5)

    shoulder_center = (positions[:, by_name["clavicle_l"]] + positions[:, by_name["clavicle_r"]]) * 0.5
    shoulder_distance = (
        positions[:, by_name["clavicle_l"]] - positions[:, by_name["clavicle_r"]]
    ).norm(dim=-1)
    shoulder_width = torch.maximum(base_width * 1.16, (shoulder_distance + 0.09).clamp_max(0.46))
    torso_top = base + up * (box_height * 3.0)[:, None]
    connector_top = shoulder_center - up * 0.018
    connector_height = (((connector_top - torso_top) * up).sum(dim=-1) + 0.030).clamp_min(0.052)
    connector_center = torso_top + up * (connector_height * 0.5 - 0.006)[:, None]
    centers.append(connector_center)
    axes.append(frame)
    half.append(
        torch.stack(
            (
                (widths[:, -1] + shoulder_width) * 0.5,
                connector_height,
                base_width * 0.34,
            ),
            dim=-1,
        )
        * 0.5
    )
    centers.append(shoulder_center + up * 0.006)
    axes.append(frame)
    half.append(torch.stack((shoulder_width, torch.full_like(shoulder_width, 0.048), base_width * 0.32), dim=-1) * 0.5)

    for side_name in ("left", "right"):
        collider_name = f"{side_name}_hand"
        if collider_name not in layout.box_names:
            continue
        joint = by_name[f"hand_{'l' if side_name == 'left' else 'r'}"]
        hand_pos = positions[:, joint]
        hand_rot = rotations[:, joint]
        hand_forward = hand_rot[:, 0]
        if side_name == "right":
            hand_forward = -hand_forward
        hand_up = hand_rot[:, 2]
        hand_side = hand_rot[:, 1]
        centers.append(hand_pos + hand_forward * 0.045 - hand_up * 0.0025)
        axes.append(torch.stack((hand_forward, hand_up, hand_side), dim=-2))
        zero = positions[:, 0, 0] * 0.0
        half.append(
            torch.stack((zero + 0.045, zero + 0.034, zero + 0.016), dim=-1)
        )

    all_names = (*BODY_BOX_NAMES[:5], *(name for name in ("left_hand", "right_hand") if name in layout.box_names))
    name_to_slot = {name: index for index, name in enumerate(all_names)}
    slots = [name_to_slot[name] for name in layout.box_names]
    return (
        torch.stack(tuple(centers[index] for index in slots), dim=1),
        _orthonormalize_axes(torch.stack(tuple(axes[index] for index in slots), dim=1)),
        torch.stack(tuple(half[index] for index in slots), dim=1),
    )


def _right_lowerarm_body_penetration(
    previous_positions: torch.Tensor,
    next_positions: torch.Tensor,
    previous_boxes: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    next_boxes: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    layout: BodyCollisionLayout,
    sweep_samples: int,
) -> torch.Tensor:
    """Sweep the standalone-viewer-sized right lower arm against torso/head."""

    by_name = {name: index for index, name in enumerate(layout.body_names)}
    lowerarm_start_a = previous_positions[:, by_name["lowerarm_r"]][:, None]
    lowerarm_end_a = previous_positions[:, by_name["hand_r"]][:, None]
    lowerarm_start_b = next_positions[:, by_name["lowerarm_r"]][:, None]
    lowerarm_end_b = next_positions[:, by_name["hand_r"]][:, None]
    one = previous_positions[:, 0, 0] * 0.0 + 1.0
    lowerarm_radius = (one * RIGHT_LOWERARM_RADIUS_M)[:, None]

    torso_slots = [layout.box_names.index(name) for name in BODY_BOX_NAMES[:3]]
    batch_size = previous_positions.shape[0]
    torso_count = len(torso_slots)
    flat_count = batch_size * torso_count
    # A Python-list advanced index materializes a CUDA index tensor lazily and
    # is therefore illegal when the outer optimizer graph is being captured.
    # Stack the three fixed integer views instead; the values and ordering are
    # identical and every CUDA operation is now warmable/capturable.
    previous_torso_boxes = tuple(
        torch.stack(tuple(box[:, slot] for slot in torso_slots), dim=1)
        for box in previous_boxes
    )
    next_torso_boxes = tuple(
        torch.stack(tuple(box[:, slot] for slot in torso_slots), dim=1)
        for box in next_boxes
    )
    torso_penetration = swept_box_capsule_penetration(
        previous_torso_boxes[0].reshape(flat_count, 3),
        previous_torso_boxes[1].reshape(flat_count, 3, 3),
        previous_torso_boxes[2].reshape(flat_count, 3),
        next_torso_boxes[0].reshape(flat_count, 3),
        next_torso_boxes[1].reshape(flat_count, 3, 3),
        next_torso_boxes[2].reshape(flat_count, 3),
        lowerarm_start_a.expand(-1, torso_count, -1).reshape(flat_count, 1, 3),
        lowerarm_end_a.expand(-1, torso_count, -1).reshape(flat_count, 1, 3),
        lowerarm_start_b.expand(-1, torso_count, -1).reshape(flat_count, 1, 3),
        lowerarm_end_b.expand(-1, torso_count, -1).reshape(flat_count, 1, 3),
        lowerarm_radius.expand(-1, torso_count).reshape(flat_count, 1),
        sweep_samples=sweep_samples,
    ).reshape(batch_size, torso_count)

    head_a = previous_positions[:, by_name["head"]]
    neck_a = previous_positions[:, by_name["neck_02"]]
    head_delta_a = head_a - neck_a
    head_length_a = head_delta_a.norm(dim=-1).clamp_min(1.0e-8)
    head_center_a = neck_a + head_delta_a * 0.62
    head_radius_a = (head_length_a * 0.55).clamp(0.095, 0.125)
    head_b = next_positions[:, by_name["head"]]
    neck_b = next_positions[:, by_name["neck_02"]]
    head_delta_b = head_b - neck_b
    head_length_b = head_delta_b.norm(dim=-1).clamp_min(1.0e-8)
    head_center_b = neck_b + head_delta_b * 0.62
    head_radius_b = (head_length_b * 0.55).clamp(0.095, 0.125)
    head_penetration = swept_capsule_sphere_penetration(
        lowerarm_start_a,
        lowerarm_end_a,
        lowerarm_start_b,
        lowerarm_end_b,
        lowerarm_radius,
        head_center_a[:, None],
        head_center_b[:, None],
        head_radius_a[:, None],
        head_radius_b[:, None],
        sweep_samples=sweep_samples,
    )
    return torch.cat((torso_penetration, head_penetration), dim=-1)


def _body_capsules_and_spheres(
    positions: torch.Tensor,
    layout: BodyCollisionLayout,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, tuple[str, ...]]:
    if layout.capsule_start:
        start = torch.stack(
            tuple(positions[:, index] for index in layout.capsule_start), dim=1
        )
        end = torch.stack(
            tuple(positions[:, index] for index in layout.capsule_end), dim=1
        )
        one = positions[:, 0, 0] * 0.0 + 1.0
        radius = torch.stack(
            tuple(one * float(value) for value in layout.capsule_radius_m), dim=-1
        )
    else:
        start = positions[:, :0]
        end = positions[:, :0]
        radius = positions[:, 0, :0]
    names = list(layout.capsule_names)

    by_name = {name: index for index, name in enumerate(layout.body_names)}
    sphere_centers = []
    sphere_radii = []
    sphere_names = []
    if "pelvis" not in layout.excluded:
        _side, up, _forward = _body_frame(positions, by_name)
        sphere_centers.append(positions[:, by_name["pelvis"]] + up * 0.014)
        sphere_radii.append(0.058)
        sphere_names.append("pelvis")
    for name, joint, sphere_radius in zip(layout.sphere_names, layout.sphere_joint, layout.sphere_radius_m):
        sphere_centers.append(positions[:, joint])
        sphere_radii.append(sphere_radius)
        sphere_names.append(name)
    if "head" not in layout.excluded:
        head = positions[:, by_name["head"]]
        neck = positions[:, by_name["neck_02"]]
        delta = head - neck
        length = delta.norm(dim=-1).clamp_min(1.0e-8)
        sphere_centers.append(neck + delta * 0.62)
        sphere_radii.append((length * 0.55).clamp(0.095, 0.125))
        sphere_names.append("head")

    if sphere_centers:
        sphere_center = torch.stack(sphere_centers, dim=1)
        start = torch.cat((start, sphere_center), dim=1)
        end = torch.cat((end, sphere_center), dim=1)
        radius_parts = [radius]
        one = positions[:, 0, 0] * 0.0 + 1.0
        for value in sphere_radii:
            if torch.is_tensor(value):
                radius_parts.append(value[:, None])
            else:
                radius_parts.append((one * float(value))[:, None])
        radius = torch.cat(radius_parts, dim=1)
    else:
        radius = radius
    return start, end, radius, tuple((*names, *sphere_names))


def swept_blade_body_collision(
    previous_positions: torch.Tensor,
    previous_rotations: torch.Tensor,
    next_positions: torch.Tensor,
    next_rotations: torch.Tensor,
    definition: BladeBoxDefinition,
    layout: BodyCollisionLayout,
    sweep_samples: int = SWEEP_SAMPLES,
) -> CollisionResult:
    by_name = {name: index for index, name in enumerate(layout.body_names)}
    attach = by_name[definition.attach_joint]
    blade_a = blade_box_from_pose(previous_positions, previous_rotations, attach, definition)
    blade_b = blade_box_from_pose(next_positions, next_rotations, attach, definition)

    capsule_a = _body_capsules_and_spheres(previous_positions, layout)
    capsule_b = _body_capsules_and_spheres(next_positions, layout)
    capsule_penetration = swept_box_capsule_penetration(
        *blade_a,
        *blade_b,
        capsule_a[0],
        capsule_a[1],
        capsule_b[0],
        capsule_b[1],
        capsule_a[2],
        sweep_samples=sweep_samples,
    )

    box_a = body_boxes(previous_positions, previous_rotations, layout)
    box_b = body_boxes(next_positions, next_rotations, layout)
    box_penetration = swept_box_box_penetration(
        *blade_a,
        *blade_b,
        *box_a,
        *box_b,
        sweep_samples=sweep_samples,
    )

    # Preserve the legacy blade component exactly. The added arm/body contacts
    # receive the same per-collider squared-penetration scale; they must never
    # enter a wider mean that dilutes the original blade loss.
    blade_penetration = torch.cat((capsule_penetration, box_penetration), dim=-1)
    lowerarm_penetration = _right_lowerarm_body_penetration(
        previous_positions,
        next_positions,
        box_a,
        box_b,
        layout,
        sweep_samples,
    )
    penetration = torch.cat((blade_penetration, lowerarm_penetration), dim=-1)
    names = (
        *capsule_a[3],
        *layout.box_names,
        *RIGHT_LOWERARM_SELF_COLLISION_NAMES,
    )
    legacy_collider_count = blade_penetration.shape[-1]
    loss_rows = blade_penetration.square().mean(dim=-1) + (
        lowerarm_penetration.square().sum(dim=-1) / float(legacy_collider_count)
    )
    return CollisionResult(
        loss_rows=loss_rows,
        max_penetration_m=penetration.amax(dim=-1),
        bad_rate=(penetration > 0.0).to(torch.float32).mean(dim=-1),
        collider_penetration_m=penetration,
        collider_names=names,
    )
