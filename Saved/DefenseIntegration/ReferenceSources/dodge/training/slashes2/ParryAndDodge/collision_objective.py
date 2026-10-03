from __future__ import annotations

"""Authoritative differentiable OBB geometry for PP/DD training.

The hard event path uses all 15 separating axes and conservative advancement.
The selected event is detached; the loss value evaluated at that event remains
differentiable with respect to the controlled defender transforms.
"""

import json
import math
from dataclasses import dataclass
from pathlib import Path

import torch


HERE = Path(__file__).resolve().parent
COLLIDERS_PATH = HERE.parent / "LimbColliderEditor" / "colliders.json"
# Half the lab leaf width removes the small one-sided conservative-advance
# bias while retaining the lab's 1/4096 authored-contact resolution.
CCD_TIME_TOLERANCE = 1.0 / 8192.0
CCD_GAP_EPSILON_M = 1.0e-7
CCD_MAX_ADVANCES = 96
DD_CONTACT_TEMPERATURE_M = 0.01

_CORNER_SIGNS = (
    (-1.0, -1.0, -1.0),
    (1.0, -1.0, -1.0),
    (1.0, 1.0, -1.0),
    (-1.0, 1.0, -1.0),
    (-1.0, -1.0, 1.0),
    (1.0, -1.0, 1.0),
    (1.0, 1.0, 1.0),
    (-1.0, 1.0, 1.0),
)
_EDGE_INDICES = (
    (0, 1), (1, 2), (2, 3), (3, 0),
    (4, 5), (5, 6), (6, 7), (7, 4),
    (0, 4), (1, 5), (2, 6), (3, 7),
)
_CONSTANT_CACHE: dict[tuple[str, torch.dtype], tuple[torch.Tensor, torch.Tensor]] = {}


def _geometry_constants(reference: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    key = (str(reference.device), reference.dtype)
    cached = _CONSTANT_CACHE.get(key)
    if cached is None:
        cached = (
            torch.tensor(_CORNER_SIGNS, dtype=reference.dtype, device=reference.device),
            torch.tensor(_EDGE_INDICES, dtype=torch.long, device=reference.device),
        )
        _CONSTANT_CACHE[key] = cached
    return cached


def _local_euler_axes(rotation_degrees: list[float]) -> torch.Tensor:
    x, y, z = (math.radians(float(value)) for value in rotation_degrees)
    sx, cx = math.sin(x), math.cos(x)
    sy, cy = math.sin(y), math.cos(y)
    sz, cz = math.sin(z), math.cos(z)
    return torch.tensor(
        (
            (cz * cy, sz * cy, -sy),
            (cz * sy * sx - sz * cx, sz * sy * sx + cz * cx, cy * sx),
            (cz * sy * cx + sz * sx, sz * sy * cx - cz * sx, cy * cx),
        ),
        dtype=torch.float32,
    )


@dataclass(frozen=True)
class ColliderGeometry:
    names: tuple[str, ...]
    bone_indices: torch.Tensor
    offsets_m: torch.Tensor
    local_axes: torch.Tensor
    center_offsets_local: torch.Tensor
    half_sizes_m: torch.Tensor
    radii_m: torch.Tensor
    blocker_blade_index: int
    blocker_melee_index: int

    @property
    def count(self) -> int:
        return len(self.names)

    def to(self, device: torch.device) -> "ColliderGeometry":
        return ColliderGeometry(
            self.names,
            self.bone_indices.to(device=device),
            self.offsets_m.to(device=device),
            self.local_axes.to(device=device),
            self.center_offsets_local.to(device=device),
            self.half_sizes_m.to(device=device),
            self.radii_m.to(device=device),
            self.blocker_blade_index,
            self.blocker_melee_index,
        )


def load_collider_geometry(
    bone_names: list[str], path: Path = COLLIDERS_PATH, *, expected_count: int = 13
) -> ColliderGeometry:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("units") != "centimeters" or payload.get("rotation_units") != "degrees":
        raise RuntimeError(f"Unsupported collider units in {path}")
    by_bone = {name: index for index, name in enumerate(bone_names)}
    names: list[str] = []
    bone_indices: list[int] = []
    offsets: list[torch.Tensor] = []
    axes: list[torch.Tensor] = []
    halves: list[torch.Tensor] = []
    radii: list[torch.Tensor] = []
    for name, raw in dict(payload["limbs"]).items():
        record = dict(raw)
        bone = str(record["bone"])
        if bone not in by_bone:
            raise RuntimeError(f"Collider {name!r} references missing bone {bone!r}")
        size = torch.tensor(record["size"], dtype=torch.float32) / 100.0
        names.append(str(name))
        bone_indices.append(by_bone[bone])
        offsets.append(torch.tensor(record["translation"], dtype=torch.float32) / 100.0)
        axes.append(_local_euler_axes(list(record["rotation"])))
        halves.append(size * 0.5)
        radii.append(torch.linalg.norm(size) * 0.5)
    if len(names) != expected_count:
        raise RuntimeError(f"Authoritative defender collider count changed: {len(names)}")
    return ColliderGeometry(
        tuple(names),
        torch.tensor(bone_indices, dtype=torch.long),
        torch.stack(offsets).contiguous(),
        torch.stack(axes).contiguous(),
        torch.einsum(
            "ci,cji->cj", torch.stack(offsets), torch.stack(axes)
        ).contiguous(),
        torch.stack(halves).contiguous(),
        torch.stack(radii).contiguous(),
        names.index("hand_r"),
        names.index("lowerarm_l"),
    )


def defender_obbs(
    positions: torch.Tensor,
    rotations: torch.Tensor,
    geometry: ColliderGeometry,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Return centres/row-axes as ``[...,13,3]`` / ``[...,13,3,3]``."""

    selected_positions = positions.index_select(-2, geometry.bone_indices)
    selected_rotations = rotations.index_select(-3, geometry.bone_indices)
    centers = selected_positions + torch.einsum(
        "ci,...cij->...cj", geometry.offsets_m, selected_rotations
    )
    axes = torch.einsum(
        "cai,...cij->...caj", geometry.local_axes, selected_rotations
    )
    return centers, axes


def sat_gap(
    center_a: torch.Tensor,
    axes_a: torch.Tensor,
    half_a: torch.Tensor,
    center_b: torch.Tensor,
    axes_b: torch.Tensor,
    half_b: torch.Tensor,
) -> torch.Tensor:
    """Signed 15-axis SAT gap; ``<= 0`` means OBB intersection."""

    delta = center_b - center_a
    dots = torch.einsum("...ik,...jk->...ij", axes_a, axes_b)
    absolute = dots.abs()
    along_a = torch.einsum("...k,...ik->...i", delta, axes_a).abs()
    along_b = torch.einsum("...k,...jk->...j", delta, axes_b).abs()
    gap_a = along_a - half_a - torch.einsum("...j,...ij->...i", half_b, absolute)
    gap_b = along_b - half_b - torch.einsum("...i,...ij->...j", half_a, absolute)

    cross = torch.cross(axes_a.unsqueeze(-2), axes_b.unsqueeze(-3), dim=-1)
    cross_norm = torch.linalg.norm(cross, dim=-1)
    cross_axis = cross / cross_norm.clamp_min(1.0e-12).unsqueeze(-1)
    along_cross = torch.einsum("...k,...ijk->...ij", delta, cross_axis).abs()
    projection_a = torch.einsum("...lk,...ijk->...ijl", axes_a, cross_axis).abs()
    projection_b = torch.einsum("...lk,...ijk->...ijl", axes_b, cross_axis).abs()
    radius_a = (projection_a * half_a.unsqueeze(-2).unsqueeze(-2)).sum(dim=-1)
    radius_b = (projection_b * half_b.unsqueeze(-2).unsqueeze(-2)).sum(dim=-1)
    gap_cross = along_cross - radius_a - radius_b
    gap_cross = torch.where(
        cross_norm > 1.0e-8,
        gap_cross,
        torch.full_like(gap_cross, -torch.inf),
    )
    return torch.maximum(
        torch.maximum(gap_a.amax(dim=-1), gap_b.amax(dim=-1)),
        gap_cross.amax(dim=(-2, -1)),
    )


def _matrix_to_quaternion(row_axes: torch.Tensor) -> torch.Tensor:
    matrix = row_axes.transpose(-1, -2)
    m00, m01, m02 = matrix[..., 0, 0], matrix[..., 0, 1], matrix[..., 0, 2]
    m10, m11, m12 = matrix[..., 1, 0], matrix[..., 1, 1], matrix[..., 1, 2]
    m20, m21, m22 = matrix[..., 2, 0], matrix[..., 2, 1], matrix[..., 2, 2]
    candidates = torch.stack(
        (
            1.0 + m00 + m11 + m22,
            1.0 + m00 - m11 - m22,
            1.0 - m00 + m11 - m22,
            1.0 - m00 - m11 + m22,
        ),
        dim=-1,
    )
    # At least one candidate is >= 1 for a proper rotation. Clamping only the
    # three unselected near-zero candidates prevents sqrt(0) infinite gradients
    # while leaving the selected quaternion algebra exact.
    magnitudes = torch.sqrt(candidates.clamp_min(1.0e-8))
    rows = torch.stack(
        (
            torch.stack((candidates[..., 0], m21 - m12, m02 - m20, m10 - m01), dim=-1),
            torch.stack((m21 - m12, candidates[..., 1], m10 + m01, m02 + m20), dim=-1),
            torch.stack((m02 - m20, m10 + m01, candidates[..., 2], m12 + m21), dim=-1),
            torch.stack((m10 - m01, m20 + m02, m21 + m12, candidates[..., 3]), dim=-1),
        ),
        dim=-2,
    )
    quaternion_candidates = rows / (2.0 * magnitudes.clamp_min(0.1).unsqueeze(-1))
    selected = magnitudes.argmax(dim=-1, keepdim=True)
    gather_index = selected.unsqueeze(-1).expand(*selected.shape[:-1], 1, 4)
    quaternion = quaternion_candidates.gather(-2, gather_index).squeeze(-2)
    return quaternion / torch.linalg.norm(quaternion, dim=-1, keepdim=True).clamp_min(1.0e-12)


def _quaternion_to_matrix(quaternion: torch.Tensor) -> torch.Tensor:
    q = quaternion / torch.linalg.norm(quaternion, dim=-1, keepdim=True).clamp_min(1.0e-12)
    w, x, y, z = q.unbind(dim=-1)
    column_matrix = torch.stack(
        (
            1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w),
            2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w),
            2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y),
        ),
        dim=-1,
    ).reshape(*q.shape[:-1], 3, 3)
    return column_matrix.transpose(-1, -2)


def _slerp_quaternion(
    q0: torch.Tensor, q1: torch.Tensor, fraction: torch.Tensor
) -> torch.Tensor:
    dot = (q0 * q1).sum(dim=-1, keepdim=True)
    q1 = torch.where(dot < 0.0, -q1, q1)
    dot = dot.abs().clamp(max=1.0)
    while fraction.ndim < dot.ndim:
        fraction = fraction.unsqueeze(-1)
    linear_mask = dot > 0.9995
    # The spherical branch is not selected near identity. Evaluate its acos at
    # a finite-gradient boundary anyway, because autograd still builds both
    # torch.where branches and inf*0 from acos(1) would poison the nlerp path.
    safe_dot = torch.where(linear_mask, torch.full_like(dot, 0.9995), dot)
    theta = torch.acos(safe_dot)
    sine = torch.sin(theta)
    linear = q0 + fraction * (q1 - q0)
    spherical = (
        torch.sin((1.0 - fraction) * theta) / sine.clamp_min(1.0e-8) * q0
        + torch.sin(fraction * theta) / sine.clamp_min(1.0e-8) * q1
    )
    return torch.where(linear_mask, linear, spherical)


def slerp_axes(start: torch.Tensor, end: torch.Tensor, fraction: torch.Tensor) -> torch.Tensor:
    q0 = _matrix_to_quaternion(start)
    q1 = _matrix_to_quaternion(end)
    return _quaternion_to_matrix(_slerp_quaternion(q0, q1, fraction))


def interpolate_obb(
    center0: torch.Tensor,
    axes0: torch.Tensor,
    center1: torch.Tensor,
    axes1: torch.Tensor,
    fraction: torch.Tensor,
    center_offset_local: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    expanded = fraction
    while expanded.ndim < center0.ndim:
        expanded = expanded.unsqueeze(-1)
    axes = slerp_axes(axes0, axes1, fraction)
    if center_offset_local is None:
        center = center0 + expanded * (center1 - center0)
    else:
        offset0 = torch.einsum("...i,...ik->...k", center_offset_local, axes0)
        offset1 = torch.einsum("...i,...ik->...k", center_offset_local, axes1)
        anchor0 = center0 - offset0
        anchor1 = center1 - offset1
        anchor = anchor0 + expanded * (anchor1 - anchor0)
        center = anchor + torch.einsum(
            "...i,...ik->...k", center_offset_local, axes
        )
    return center, axes


def refine_contact_time(
    initial_time: torch.Tensor,
    hit: torch.Tensor,
    center_a0: torch.Tensor,
    axes_a0: torch.Tensor,
    center_a1: torch.Tensor,
    axes_a1: torch.Tensor,
    half_a: torch.Tensor,
    center_b0: torch.Tensor,
    axes_b0: torch.Tensor,
    center_b1: torch.Tensor,
    axes_b1: torch.Tensor,
    half_b: torch.Tensor,
    *,
    offset_a: torch.Tensor | None = None,
    offset_b: torch.Tensor | None = None,
    search_span: float = 1.0 / 256.0,
) -> torch.Tensor:
    """Refine a conservative CCD acceptance to the first actual SAT overlap.

    The hard refined time is detached by callers, like the collider ownership
    and original CCD time.  A grazing conservative acceptance that never
    overlaps in the small forward window keeps its original timestamp.
    """

    # The conservative detector accepts at half the lab leaf width. Advancing
    # by one full leaf (two tolerances) lands on the first actual overlap for
    # the normal case without adding an iterative root finder to every graph
    # replay. The wider lab-sized probe is a fixed-cost grazing fallback.
    candidate = (initial_time + 2.0 * CCD_TIME_TOLERANCE).clamp(max=1.0)
    candidate_a, candidate_axes_a = interpolate_obb(
        center_a0, axes_a0, center_a1, axes_a1, candidate, offset_a
    )
    candidate_b, candidate_axes_b = interpolate_obb(
        center_b0, axes_b0, center_b1, axes_b1, candidate, offset_b
    )
    candidate_found = hit & (
        sat_gap(
            candidate_a, candidate_axes_a, half_a,
            candidate_b, candidate_axes_b, half_b,
        )
        <= CCD_GAP_EPSILON_M
    )
    fallback = (initial_time + float(search_span)).clamp(max=1.0)
    fallback_a, fallback_axes_a = interpolate_obb(
        center_a0, axes_a0, center_a1, axes_a1, fallback, offset_a
    )
    fallback_b, fallback_axes_b = interpolate_obb(
        center_b0, axes_b0, center_b1, axes_b1, fallback, offset_b
    )
    fallback_found = hit & (
        sat_gap(
            fallback_a, fallback_axes_a, half_a,
            fallback_b, fallback_axes_b, half_b,
        )
        <= CCD_GAP_EPSILON_M
    )
    return torch.where(
        candidate_found,
        candidate,
        torch.where(fallback_found, fallback, initial_time),
    )


def _interpolate_precomputed(
    center0: torch.Tensor,
    quaternion0: torch.Tensor,
    center1: torch.Tensor,
    quaternion1: torch.Tensor,
    fraction: torch.Tensor,
    center_offset_local: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    expanded = fraction
    while expanded.ndim < center0.ndim:
        expanded = expanded.unsqueeze(-1)
    axes = _quaternion_to_matrix(
        _slerp_quaternion(quaternion0, quaternion1, fraction)
    )
    offset0 = torch.einsum("...i,...ik->...k", center_offset_local, _quaternion_to_matrix(quaternion0))
    offset1 = torch.einsum("...i,...ik->...k", center_offset_local, _quaternion_to_matrix(quaternion1))
    anchor0 = center0 - offset0
    anchor1 = center1 - offset1
    center = anchor0 + expanded * (anchor1 - anchor0)
    center = center + torch.einsum("...i,...ik->...k", center_offset_local, axes)
    return center, axes


def rotation_angle(start: torch.Tensor, end: torch.Tensor) -> torch.Tensor:
    relative = torch.einsum("...ij,...kj->...ik", start, end)
    cosine = ((relative.diagonal(dim1=-2, dim2=-1).sum(dim=-1) - 1.0) * 0.5).clamp(-1.0, 1.0)
    return torch.acos(cosine)


@dataclass(frozen=True)
class FirstContact:
    hit: torch.Tensor
    time: torch.Tensor
    collider_index: torch.Tensor
    gap: torch.Tensor
    iterations: torch.Tensor


def conservative_first_contact(
    defender_center0: torch.Tensor,
    defender_axes0: torch.Tensor,
    defender_center1: torch.Tensor,
    defender_axes1: torch.Tensor,
    defender_half: torch.Tensor,
    defender_radius: torch.Tensor,
    attacker_center0: torch.Tensor,
    attacker_axes0: torch.Tensor,
    attacker_center1: torch.Tensor,
    attacker_axes1: torch.Tensor,
    attacker_half: torch.Tensor,
    attacker_radius: torch.Tensor,
    *,
    defender_center_offset_local: torch.Tensor | None = None,
    attacker_center_offset_local: torch.Tensor | None = None,
    tolerance: float = CCD_TIME_TOLERANCE,
    maximum_advances: int = CCD_MAX_ADVANCES,
) -> FirstContact:
    """Find the first collider reached in one normalized frame interval.

    SAT separation is a lower bound on Euclidean separation. Dividing it by a
    conservative translation+angular point-speed bound cannot step across a
    contact. A separation smaller than one tolerance step is the same
    conservative leaf acceptance used by Collision Lab at depth 12.
    """

    batch, collider_count = defender_center0.shape[:2]
    if defender_center_offset_local is None:
        defender_center_offset_local = torch.zeros_like(defender_center0)
    if attacker_center_offset_local is None:
        attacker_center_offset_local = torch.zeros_like(attacker_center0)
    if defender_center0.is_cuda:
        from triton_ccd import first_contact_pairs

        pair_hit, pair_time, pair_gap, pair_iterations = first_contact_pairs(
            defender_center0.contiguous(), defender_axes0.contiguous(),
            defender_center1.contiguous(), defender_axes1.contiguous(),
            defender_half.contiguous(), defender_radius.contiguous(),
            defender_center_offset_local.contiguous(),
            attacker_center0.contiguous(), attacker_axes0.contiguous(),
            attacker_center1.contiguous(), attacker_axes1.contiguous(),
            attacker_half.contiguous(), attacker_radius.contiguous(),
            attacker_center_offset_local.contiguous(),
            tolerance=float(tolerance), gap_epsilon=CCD_GAP_EPSILON_M,
            max_iterations=4096,
        )
        candidate_time = torch.where(
            pair_hit, pair_time, torch.full_like(pair_time, torch.inf)
        )
        earliest_time, earliest_index = candidate_time.min(dim=-1)
        any_hit = torch.isfinite(earliest_time)
        selected_gap = pair_gap.gather(1, earliest_index[:, None]).squeeze(1)
        selected_iterations = pair_iterations.gather(
            1, earliest_index[:, None]
        ).squeeze(1)
        return FirstContact(
            any_hit, earliest_time, earliest_index, selected_gap, selected_iterations
        )
    attack_center0 = attacker_center0[:, None, :].expand(-1, collider_count, -1)
    attack_center1 = attacker_center1[:, None, :].expand(-1, collider_count, -1)
    attack_axes0 = attacker_axes0[:, None, :, :].expand(-1, collider_count, -1, -1)
    attack_axes1 = attacker_axes1[:, None, :, :].expand(-1, collider_count, -1, -1)
    attack_half = attacker_half[:, None, :].expand(-1, collider_count, -1)
    attacker_center_offset_local = attacker_center_offset_local[:, None, :].expand(
        -1, collider_count, -1
    )
    defender_offset0 = torch.einsum(
        "...i,...ik->...k", defender_center_offset_local, defender_axes0
    )
    defender_offset1 = torch.einsum(
        "...i,...ik->...k", defender_center_offset_local, defender_axes1
    )
    attacker_offset0 = torch.einsum(
        "...i,...ik->...k", attacker_center_offset_local, attack_axes0
    )
    attacker_offset1 = torch.einsum(
        "...i,...ik->...k", attacker_center_offset_local, attack_axes1
    )
    defender_anchor0, defender_anchor1 = (
        defender_center0 - defender_offset0,
        defender_center1 - defender_offset1,
    )
    attacker_anchor0, attacker_anchor1 = (
        attack_center0 - attacker_offset0,
        attack_center1 - attacker_offset1,
    )
    defender_speed = torch.linalg.norm(defender_anchor1 - defender_anchor0, dim=-1)
    defender_sweep_radius = defender_radius + torch.linalg.norm(
        defender_center_offset_local, dim=-1
    )
    defender_speed = defender_speed + defender_sweep_radius * rotation_angle(defender_axes0, defender_axes1)
    attacker_speed = torch.linalg.norm(attacker_anchor1 - attacker_anchor0, dim=-1)
    attacker_sweep_radius = attacker_radius[:, None] + torch.linalg.norm(
        attacker_center_offset_local, dim=-1
    )
    attacker_speed = attacker_speed + attacker_sweep_radius * rotation_angle(attack_axes0, attack_axes1)
    speed_bound = defender_speed + attacker_speed
    defender_quaternion0 = _matrix_to_quaternion(defender_axes0)
    defender_quaternion1 = _matrix_to_quaternion(defender_axes1)
    attacker_quaternion0 = _matrix_to_quaternion(attack_axes0)
    attacker_quaternion1 = _matrix_to_quaternion(attack_axes1)

    current_time = defender_center0.new_zeros((batch, collider_count))
    hit = torch.zeros((batch, collider_count), dtype=torch.bool, device=defender_center0.device)
    finished = torch.zeros_like(hit)
    iterations = torch.zeros(
        (batch, collider_count), dtype=torch.int64, device=defender_center0.device
    )
    event_gap = defender_center0.new_full((batch, collider_count), torch.inf)
    for _ in range(int(maximum_advances)):
        def_center, def_axes = _interpolate_precomputed(
            defender_center0, defender_quaternion0,
            defender_center1, defender_quaternion1, current_time,
            defender_center_offset_local,
        )
        atk_center, atk_axes = _interpolate_precomputed(
            attack_center0, attacker_quaternion0,
            attack_center1, attacker_quaternion1, current_time,
            attacker_center_offset_local,
        )
        gap = sat_gap(def_center, def_axes, defender_half, atk_center, atk_axes, attack_half)
        active = ~finished
        iterations = iterations + active.to(iterations.dtype)
        reached = active & (
            (gap <= CCD_GAP_EPSILON_M)
            | (gap <= speed_bound * float(tolerance) + CCD_GAP_EPSILON_M)
        )
        hit = hit | reached
        event_gap = torch.where(reached, gap, event_gap)
        finished = finished | reached
        safe_step = gap.clamp_min(0.0) / speed_bound.clamp_min(1.0e-12)
        next_time = current_time + safe_step
        escaped = active & ~reached & ((speed_bound <= 1.0e-12) | (next_time >= 1.0))
        finished = finished | escaped
        current_time = torch.where(active & ~reached, next_time.clamp(max=1.0), current_time)
    # An unresolved row is conservatively accepted. This is never a silent miss;
    # the diagnostic is visible as a candidate at its last proven-safe time.
    unresolved = ~finished
    hit = hit | unresolved
    event_gap = torch.where(unresolved, torch.zeros_like(event_gap), event_gap)
    candidate_time = torch.where(hit, current_time, torch.full_like(current_time, torch.inf))
    earliest_time, earliest_index = candidate_time.min(dim=-1)
    any_hit = torch.isfinite(earliest_time)
    selected_gap = event_gap.gather(1, earliest_index[:, None]).squeeze(1)
    selected_iterations = iterations.gather(1, earliest_index[:, None]).squeeze(1)
    return FirstContact(
        any_hit, earliest_time, earliest_index, selected_gap, selected_iterations
    )


def point_to_obb_distance(
    points: torch.Tensor,
    center: torch.Tensor,
    axes: torch.Tensor,
    half: torch.Tensor,
) -> torch.Tensor:
    delta = points - center.unsqueeze(-2)
    local = torch.einsum("...pk,...ik->...pi", delta, axes)
    outside = (local.abs() - half.unsqueeze(-2)).clamp_min(0.0)
    return torch.linalg.norm(outside, dim=-1)


def obb_corners(center: torch.Tensor, axes: torch.Tensor, half: torch.Tensor) -> torch.Tensor:
    signs, _edges = _geometry_constants(center)
    local = signs * half.unsqueeze(-2)
    return center.unsqueeze(-2) + torch.einsum("...pi,...ik->...pk", local, axes)


def _closest_point_on_obb(
    point: torch.Tensor,
    center: torch.Tensor,
    axes: torch.Tensor,
    half: torch.Tensor,
) -> torch.Tensor:
    local = torch.einsum("...k,...ik->...i", point - center, axes).clamp(-half, half)
    return center + torch.einsum("...i,...ik->...k", local, axes)


def _segment_obb_contacts(
    corners: torch.Tensor,
    center: torch.Tensor,
    axes: torch.Tensor,
    half: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Return both clipped endpoints for all 12 box edges and valid masks."""

    _signs, edges = _geometry_constants(corners)
    start = corners.index_select(-2, edges[:, 0])
    end = corners.index_select(-2, edges[:, 1])
    delta = end - start
    local_start = torch.einsum("...ek,...ik->...ei", start - center.unsqueeze(-2), axes)
    local_direction = torch.einsum("...ek,...ik->...ei", delta, axes)
    parallel = local_direction.abs() < 1.0e-10
    parallel_inside = (~parallel) | (
        local_start.abs() <= half.unsqueeze(-2) + 1.0e-7
    )
    safe_direction = torch.where(
        parallel, torch.ones_like(local_direction), local_direction
    )
    first = (-half.unsqueeze(-2) - local_start) / safe_direction
    second = (half.unsqueeze(-2) - local_start) / safe_direction
    enter = torch.minimum(first, second)
    leave = torch.maximum(first, second)
    enter = torch.where(parallel, torch.full_like(enter, -torch.inf), enter)
    leave = torch.where(parallel, torch.full_like(leave, torch.inf), leave)
    lo = torch.maximum(enter.amax(dim=-1), torch.zeros_like(enter[..., 0]))
    hi = torch.minimum(leave.amin(dim=-1), torch.ones_like(leave[..., 0]))
    valid = parallel_inside.all(dim=-1) & (lo <= hi + 1.0e-7)
    fractions = torch.stack((lo.clamp(0.0, 1.0), hi.clamp(0.0, 1.0)), dim=-1)
    points = start.unsqueeze(-2) + fractions.unsqueeze(-1) * delta.unsqueeze(-2)
    return points.flatten(-3, -2), valid.unsqueeze(-1).expand(*valid.shape, 2).flatten(-2)


def _minimum_overlap_axis(
    center_a: torch.Tensor,
    axes_a: torch.Tensor,
    half_a: torch.Tensor,
    center_b: torch.Tensor,
    axes_b: torch.Tensor,
    half_b: torch.Tensor,
) -> torch.Tensor:
    cross = torch.cross(axes_a.unsqueeze(-2), axes_b.unsqueeze(-3), dim=-1)
    cross_norm = torch.linalg.vector_norm(cross, dim=-1)
    cross_axes = cross / cross_norm.clamp_min(1.0e-12).unsqueeze(-1)
    candidates = torch.cat((axes_a, axes_b, cross_axes.flatten(-3, -2)), dim=-2)
    valid = torch.cat(
        (
            torch.ones_like(half_a, dtype=torch.bool),
            torch.ones_like(half_b, dtype=torch.bool),
            (cross_norm > 1.0e-8).flatten(-2),
        ),
        dim=-1,
    )
    delta = center_b - center_a
    separation = torch.einsum("...k,...ak->...a", delta, candidates)
    radius_a = (
        torch.einsum("...ik,...ak->...ai", axes_a, candidates).abs()
        * half_a.unsqueeze(-2)
    ).sum(dim=-1)
    radius_b = (
        torch.einsum("...ik,...ak->...ai", axes_b, candidates).abs()
        * half_b.unsqueeze(-2)
    ).sum(dim=-1)
    overlap = radius_a + radius_b - separation.abs()
    overlap = torch.where(valid, overlap, torch.full_like(overlap, torch.inf))
    selected = overlap.argmin(dim=-1, keepdim=True)
    gather = selected.unsqueeze(-1).expand(*selected.shape, 3)
    normal = candidates.gather(-2, gather).squeeze(-2)
    direction = separation.gather(-1, selected).squeeze(-1)
    return torch.where(direction.unsqueeze(-1) < 0.0, -normal, normal)


def _line_obb_interval(
    point: torch.Tensor,
    direction: torch.Tensor,
    center: torch.Tensor,
    axes: torch.Tensor,
    half: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    origin = torch.einsum("...k,...ik->...i", point - center, axes)
    local_direction = torch.einsum("...k,...ik->...i", direction, axes)
    parallel = local_direction.abs() < 1.0e-10
    valid_parallel = (~parallel) | (origin.abs() <= half + 1.0e-6)
    safe_direction = torch.where(
        parallel, torch.ones_like(local_direction), local_direction
    )
    first = (-half - origin) / safe_direction
    second = (half - origin) / safe_direction
    enter = torch.minimum(first, second)
    leave = torch.maximum(first, second)
    enter = torch.where(parallel, torch.full_like(enter, -torch.inf), enter)
    leave = torch.where(parallel, torch.full_like(leave, torch.inf), leave)
    lo = enter.amax(dim=-1)
    hi = leave.amin(dim=-1)
    return lo, hi, valid_parallel.all(dim=-1) & (lo <= hi)


def obb_contact_witness(
    center_a: torch.Tensor,
    axes_a: torch.Tensor,
    half_a: torch.Tensor,
    center_b: torch.Tensor,
    axes_b: torch.Tensor,
    half_b: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Collision-Lab-equivalent surface witnesses for two OBBs.

    The discrete manifold and minimum-axis selections are intentionally hard;
    gradients flow through the selected witness exactly as they do through the
    CCD-selected time/collider.  For a conservative near-contact event with no
    overlap manifold, the lab's closest-point midpoint fallback is used.
    """

    corners_a = obb_corners(center_a, axes_a, half_a)
    corners_b = obb_corners(center_b, axes_b, half_b)
    local_a_in_b = torch.einsum(
        "...pk,...ik->...pi", corners_a - center_b.unsqueeze(-2), axes_b
    )
    local_b_in_a = torch.einsum(
        "...pk,...ik->...pi", corners_b - center_a.unsqueeze(-2), axes_a
    )
    inside_a = (local_a_in_b.abs() <= half_b.unsqueeze(-2) + 1.0e-6).all(dim=-1)
    inside_b = (local_b_in_a.abs() <= half_a.unsqueeze(-2) + 1.0e-6).all(dim=-1)
    edge_a, edge_a_valid = _segment_obb_contacts(
        corners_a, center_b, axes_b, half_b
    )
    edge_b, edge_b_valid = _segment_obb_contacts(
        corners_b, center_a, axes_a, half_a
    )
    points = torch.cat((corners_a, corners_b, edge_a, edge_b), dim=-2)
    valid = torch.cat((inside_a, inside_b, edge_a_valid, edge_b_valid), dim=-1)
    count = valid.sum(dim=-1)
    manifold_center = (
        points * valid.unsqueeze(-1).to(points.dtype)
    ).sum(dim=-2) / count.clamp_min(1).unsqueeze(-1)
    on_a = _closest_point_on_obb(center_b, center_a, axes_a, half_a)
    on_b = _closest_point_on_obb(on_a, center_b, axes_b, half_b)
    fallback_center = 0.5 * (on_a + on_b)
    contact_center = torch.where(
        (count > 0).unsqueeze(-1), manifold_center, fallback_center
    )

    normal = _minimum_overlap_axis(
        center_a, axes_a, half_a, center_b, axes_b, half_b
    )
    lo_a, hi_a, valid_a = _line_obb_interval(
        contact_center, normal, center_a, axes_a, half_a
    )
    lo_b, _hi_b, valid_b = _line_obb_interval(
        contact_center, normal, center_b, axes_b, half_b
    )
    point_a = contact_center + normal * hi_a.unsqueeze(-1)
    point_b = contact_center + normal * lo_b.unsqueeze(-1)
    point_a = torch.where(
        valid_a.unsqueeze(-1), point_a,
        _closest_point_on_obb(center_b, center_a, axes_a, half_a),
    )
    point_b = torch.where(
        valid_b.unsqueeze(-1), point_b,
        _closest_point_on_obb(center_a, center_b, axes_b, half_b),
    )
    return point_a, point_b


def _edge_edge_distances(corners_a: torch.Tensor, corners_b: torch.Tensor) -> torch.Tensor:
    _signs, edges = _geometry_constants(corners_a)
    p1 = corners_a.index_select(-2, edges[:, 0]).unsqueeze(-2)
    q1 = corners_a.index_select(-2, edges[:, 1]).unsqueeze(-2)
    p2 = corners_b.index_select(-2, edges[:, 0]).unsqueeze(-3)
    q2 = corners_b.index_select(-2, edges[:, 1]).unsqueeze(-3)
    d1 = q1 - p1
    d2 = q2 - p2
    relative = p1 - p2
    a = (d1 * d1).sum(dim=-1)
    e = (d2 * d2).sum(dim=-1)
    b = (d1 * d2).sum(dim=-1)
    c = (d1 * relative).sum(dim=-1)
    f = (d2 * relative).sum(dim=-1)
    denominator = a * e - b * b
    s = ((b * f - c * e) / denominator.clamp_min(1.0e-12)).clamp(0.0, 1.0)
    parallel_s = (-c / a.clamp_min(1.0e-12)).clamp(0.0, 1.0)
    s = torch.where(denominator > 1.0e-12, s, parallel_s)
    t = (b * s + f) / e.clamp_min(1.0e-12)
    below = t < 0.0
    above = t > 1.0
    s_below = (-c / a.clamp_min(1.0e-12)).clamp(0.0, 1.0)
    s_above = ((b - c) / a.clamp_min(1.0e-12)).clamp(0.0, 1.0)
    s = torch.where(below, s_below, torch.where(above, s_above, s))
    t = t.clamp(0.0, 1.0)
    closest_a = p1 + s.unsqueeze(-1) * d1
    closest_b = p2 + t.unsqueeze(-1) * d2
    return torch.linalg.norm(closest_a - closest_b, dim=-1)


def obb_feature_distance(
    center_a: torch.Tensor,
    axes_a: torch.Tensor,
    half_a: torch.Tensor,
    center_b: torch.Tensor,
    axes_b: torch.Tensor,
    half_b: torch.Tensor,
) -> torch.Tensor:
    """Exact continuous closest-feature distance for two OBBs.

    Convex-box closest features are vertex/face or edge/edge. Both symmetric
    vertex-to-box sets and all 12x12 edge pairs are evaluated. SAT forces the
    result to literal zero for intersecting/touching boxes.
    """

    gap = sat_gap(center_a, axes_a, half_a, center_b, axes_b, half_b)
    corners_a = obb_corners(center_a, axes_a, half_a)
    corners_b = obb_corners(center_b, axes_b, half_b)
    vertex_distance = torch.minimum(
        point_to_obb_distance(corners_a, center_b, axes_b, half_b).amin(dim=-1),
        point_to_obb_distance(corners_b, center_a, axes_a, half_a).amin(dim=-1),
    )
    edge_distance = _edge_edge_distances(corners_a, corners_b).amin(dim=(-2, -1))
    separated = torch.minimum(vertex_distance, edge_distance)
    return torch.where(gap <= CCD_GAP_EPSILON_M, torch.zeros_like(separated), separated)


def dodge_contact_surrogate(first: FirstContact) -> torch.Tensor:
    """Positive continuous local penalty, gated only by hard CCD ownership."""

    temperature = DD_CONTACT_TEMPERATURE_M
    smooth = torch.nn.functional.softplus(-first.gap / temperature) * temperature
    return torch.where(first.hit.detach(), smooth, torch.zeros_like(smooth))
