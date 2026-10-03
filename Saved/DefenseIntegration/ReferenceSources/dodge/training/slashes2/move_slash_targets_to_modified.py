from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import make_slash_npz_viewer as viewer


ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "slash_attack_config.json"
FOOT_IK_TARGET_FRAME = 0
IDLE_FOOT_REFERENCE_FRAME = 0
PELVIS_OFFSET_SCALE = 1.0


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def free_leg_side_for_clip(clip_name: str) -> str | None:
    name = clip_name.lower()
    if "kickr" in name:
        return "right"
    if "kickl" in name:
        return "left"
    return None


def armed_frame_for_clip(config: dict[str, object], clip_name: str, frame_count: int) -> float | None:
    entry = None
    for key in ("kick_armed_by_clip", "armed_by_clip"):
        entries = config.get(key, {})
        if isinstance(entries, dict) and isinstance(entries.get(clip_name), dict):
            entry = entries[clip_name]
            break
    if not isinstance(entry, dict):
        return None
    value = float(entry.get("frame", 0.0) or 0.0)
    if not np.isfinite(value) or value <= 0.0:
        return None
    return clamp(value, 0.0, float(max(0, frame_count - 1)))


def cleanup_for_clip(config: dict[str, object], clip_name: str) -> dict[str, object]:
    defaults = config.get("defaults", {})
    if not isinstance(defaults, dict):
        defaults = {}
    by_clip = config.get("cleanup_by_clip", {})
    entry = by_clip.get(clip_name, {}) if isinstance(by_clip, dict) else {}
    if not isinstance(entry, dict):
        entry = {}
    offset_scale = float(entry.get("pelvis_offset_scale", defaults.get("pelvis_offset_scale", PELVIS_OFFSET_SCALE)) or 0.0)
    source_blend = float(entry.get("pelvis_source_blend", defaults.get("pelvis_source_blend", 0.0)) or 0.0)
    raw_extra = entry.get("extra_pelvis_offset_m", defaults.get("extra_pelvis_offset_m", [0.0, 0.0, 0.0]))
    try:
        extra = np.asarray(raw_extra, dtype=np.float64)
    except (TypeError, ValueError):
        extra = np.zeros(3, dtype=np.float64)
    if extra.shape != (3,) or not np.isfinite(extra).all():
        extra = np.zeros(3, dtype=np.float64)
    return {
        "pelvis_offset_scale": clamp(offset_scale, 0.0, 1.0),
        "pelvis_source_blend": clamp(source_blend, 0.0, 1.0),
        "extra_pelvis_offset_m": np.clip(extra, -2.0, 2.0),
    }


def normalize(v: np.ndarray, fallback: np.ndarray | None = None) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n > 1e-8:
        return v / n
    if fallback is None:
        fallback = np.asarray([1.0, 0.0, 0.0], dtype=np.float64)
    return fallback.astype(np.float64)


def orthonormal_axes(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
    x = normalize(x)
    y = y - x * float(np.dot(y, x))
    if np.linalg.norm(y) < 1e-6:
        y = normalize(np.cross(z, x))
    else:
        y = normalize(y)
    fixed_z = normalize(np.cross(x, y))
    if float(np.dot(fixed_z, z)) < 0.0:
        fixed_z = -fixed_z
    fixed_y = normalize(np.cross(fixed_z, x))
    return np.stack([x, fixed_y, fixed_z], axis=0)


def quat_normalize(q: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(q))
    if n > 1e-8:
        return q / n
    return np.asarray([1.0, 0.0, 0.0, 0.0], dtype=np.float64)


def quat_from_axes(axes: np.ndarray) -> np.ndarray:
    x, y, z = orthonormal_axes(axes[0], axes[1], axes[2])
    m00, m01, m02 = x[0], y[0], z[0]
    m10, m11, m12 = x[1], y[1], z[1]
    m20, m21, m22 = x[2], y[2], z[2]
    trace = m00 + m11 + m22
    if trace > 0:
        s = np.sqrt(trace + 1.0) * 2.0
        qw = 0.25 * s
        qx = (m21 - m12) / s
        qy = (m02 - m20) / s
        qz = (m10 - m01) / s
    elif m00 > m11 and m00 > m22:
        s = np.sqrt(1.0 + m00 - m11 - m22) * 2.0
        qw = (m21 - m12) / s
        qx = 0.25 * s
        qy = (m01 + m10) / s
        qz = (m02 + m20) / s
    elif m11 > m22:
        s = np.sqrt(1.0 + m11 - m00 - m22) * 2.0
        qw = (m02 - m20) / s
        qx = (m01 + m10) / s
        qy = 0.25 * s
        qz = (m12 + m21) / s
    else:
        s = np.sqrt(1.0 + m22 - m00 - m11) * 2.0
        qw = (m10 - m01) / s
        qx = (m02 + m20) / s
        qy = (m12 + m21) / s
        qz = 0.25 * s
    return quat_normalize(np.asarray([qw, qx, qy, qz], dtype=np.float64))


def axes_from_quat(q: np.ndarray) -> np.ndarray:
    w, x, y, z = quat_normalize(q)
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    return np.asarray(
        [
            [1 - 2 * (yy + zz), 2 * (xy + wz), 2 * (xz - wy)],
            [2 * (xy - wz), 1 - 2 * (xx + zz), 2 * (yz + wx)],
            [2 * (xz + wy), 2 * (yz - wx), 1 - 2 * (xx + yy)],
        ],
        dtype=np.float64,
    )


def quat_slerp(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    a = quat_normalize(a)
    b = quat_normalize(b)
    cos_theta = float(np.dot(a, b))
    if cos_theta < 0.0:
        b = -b
        cos_theta = -cos_theta
    cos_theta = clamp(cos_theta, -1.0, 1.0)
    if cos_theta > 0.9995:
        return quat_normalize(a + (b - a) * t)
    theta = np.arccos(cos_theta)
    sin_theta = np.sin(theta)
    w0 = np.sin((1.0 - t) * theta) / sin_theta
    w1 = np.sin(t * theta) / sin_theta
    return quat_normalize(a * w0 + b * w1)


def quat_slerp_fixed_branch(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray | None:
    a = quat_normalize(a)
    b = quat_normalize(b)
    cos_theta = clamp(float(np.dot(a, b)), -0.999999, 0.999999)
    if cos_theta < -0.9995:
        return None
    if abs(cos_theta) > 0.9995:
        return quat_normalize(a + (b - a) * t)
    theta = np.arccos(cos_theta)
    sin_theta = np.sin(theta)
    w0 = np.sin((1.0 - t) * theta) / sin_theta
    w1 = np.sin(t * theta) / sin_theta
    return quat_normalize(a * w0 + b * w1)


def continuous_blend_quat(
    idle_quat: np.ndarray,
    target_quat: np.ndarray,
    alpha: float,
    previous_quat: np.ndarray | None,
) -> np.ndarray:
    best_q: np.ndarray | None = None
    best_score = -1.0
    for candidate in (target_quat, -target_quat):
        q = quat_slerp_fixed_branch(idle_quat, candidate, alpha)
        if q is None:
            continue
        reference = previous_quat if previous_quat is not None else idle_quat
        score = abs(float(np.dot(q, reference)))
        if score > best_score:
            best_q = q
            best_score = score
    if best_q is None:
        best_q = quat_slerp(idle_quat, target_quat, alpha)
    if previous_quat is not None and float(np.dot(best_q, previous_quat)) < 0.0:
        best_q = -best_q
    return best_q


def sample_info(count: int, frame: float) -> tuple[int, int, float]:
    max_frame = max(0, count - 1)
    x = clamp(float(frame), 0.0, float(max_frame))
    base = int(np.floor(x))
    nxt = min(max_frame, base + 1)
    return base, nxt, x - base


def pos_at(positions: np.ndarray, frame: float, joint: int) -> np.ndarray:
    base, nxt, t = sample_info(int(positions.shape[0]), frame)
    a = positions[base, joint].astype(np.float64)
    if t <= 1e-7 or base == nxt:
        return a
    b = positions[nxt, joint].astype(np.float64)
    return a + (b - a) * t


def raw_basis_axes(basis: np.ndarray, frame: int, joint: int) -> np.ndarray:
    return orthonormal_axes(
        basis[frame, joint, 0].astype(np.float64),
        basis[frame, joint, 1].astype(np.float64),
        basis[frame, joint, 2].astype(np.float64),
    )


def basis_axes_at(basis: np.ndarray, frame: float, joint: int) -> np.ndarray:
    base, nxt, t = sample_info(int(basis.shape[0]), frame)
    a = raw_basis_axes(basis, base, joint)
    if t <= 1e-7 or base == nxt:
        return a
    b = raw_basis_axes(basis, nxt, joint)
    return axes_from_quat(quat_slerp(quat_from_axes(a), quat_from_axes(b), t))


def basis_vector_to_local(v: np.ndarray, basis: np.ndarray, frame: float, joint: int) -> np.ndarray:
    axes = basis_axes_at(basis, frame, joint)
    return np.asarray([np.dot(v, axes[0]), np.dot(v, axes[1]), np.dot(v, axes[2])], dtype=np.float64)


def vector_to_world_from_axes(v: np.ndarray, axes: np.ndarray) -> np.ndarray:
    return axes[0] * v[0] + axes[1] * v[1] + axes[2] * v[2]


def basis_vector_to_world_raw(v: np.ndarray, basis: np.ndarray, frame: float, joint: int) -> np.ndarray:
    return vector_to_world_from_axes(v, basis_axes_at(basis, frame, joint))


def basis_axes_in_local(
    src_basis: np.ndarray,
    src_frame: float,
    src_joint: int,
    target_basis: np.ndarray,
    target_frame: float,
    target_joint: int,
) -> np.ndarray:
    return np.stack(
        [
            basis_vector_to_local(basis_axes_at(target_basis, target_frame, target_joint)[axis], src_basis, src_frame, src_joint)
            for axis in range(3)
        ],
        axis=0,
    )


def carried_basis_axes(src_basis: np.ndarray, src_frame: float, src_joint: int, local_axes: np.ndarray) -> np.ndarray:
    return orthonormal_axes(
        basis_vector_to_world_raw(local_axes[0], src_basis, src_frame, src_joint),
        basis_vector_to_world_raw(local_axes[1], src_basis, src_frame, src_joint),
        basis_vector_to_world_raw(local_axes[2], src_basis, src_frame, src_joint),
    )


def fallback_pole_for(direction: np.ndarray) -> np.ndarray:
    pole = np.cross(direction, np.asarray([0.0, 1.0, 0.0], dtype=np.float64))
    if np.linalg.norm(pole) < 1e-5:
        pole = np.cross(direction, np.asarray([1.0, 0.0, 0.0], dtype=np.float64))
    return normalize(pole)


def leg_pole_from_knee(hip: np.ndarray, knee: np.ndarray, foot: np.ndarray) -> np.ndarray:
    direction = normalize(foot - hip)
    hip_to_knee = knee - hip
    pole = hip_to_knee - direction * float(np.dot(hip_to_knee, direction))
    if np.linalg.norm(pole) > 1e-5:
        return normalize(pole)
    return fallback_pole_for(direction)


def vector_angle_deg(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.degrees(np.arccos(clamp(float(np.dot(normalize(a), normalize(b))), -1.0, 1.0))))


def slerp_unit_vectors(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    a = normalize(a)
    b = normalize(b)
    dot = clamp(float(np.dot(a, b)), -1.0, 1.0)
    if dot > 0.9995:
        return normalize(a + (b - a) * t)
    theta = float(np.arccos(dot))
    sin_theta = float(np.sin(theta))
    if abs(sin_theta) < 1e-7:
        return a
    return normalize((np.sin((1.0 - t) * theta) / sin_theta) * a + (np.sin(t * theta) / sin_theta) * b)


def smoothed_foot_local_poles(
    clip: viewer.Motion,
    spec: dict[str, int | str],
    max_step_deg: float = 30.0,
) -> np.ndarray:
    thigh = int(spec["thigh"])
    calf = int(spec["calf"])
    foot = int(spec["foot"])
    poles: list[np.ndarray] = []
    previous: np.ndarray | None = None
    for f in range(int(clip.positions_m.shape[0])):
        raw_pole = leg_pole_from_knee(
            pos_at(clip.positions_m, f, thigh),
            pos_at(clip.positions_m, f, calf),
            pos_at(clip.positions_m, f, foot),
        )
        local = normalize(basis_vector_to_local(raw_pole, clip.basis, f, foot))
        if previous is not None:
            if float(np.dot(previous, local)) < 0.0:
                local = -local
            angle = vector_angle_deg(previous, local)
            if angle > max_step_deg:
                local = slerp_unit_vectors(previous, local, max_step_deg / angle)
        poles.append(local)
        previous = local
    return np.asarray(poles, dtype=np.float64)


def solve_two_bone_knee_with_pole(
    hip: np.ndarray,
    knee: np.ndarray,
    foot: np.ndarray,
    foot_target: np.ndarray,
    pole_hint: np.ndarray,
    upper_length: float | None = None,
    lower_length: float | None = None,
) -> np.ndarray:
    upper_length = max(1e-5, float(np.linalg.norm(knee - hip) if upper_length is None else upper_length))
    lower_length = max(1e-5, float(np.linalg.norm(foot - knee) if lower_length is None else lower_length))
    to_target = foot_target - hip
    actual_distance = float(np.linalg.norm(to_target))
    if actual_distance < 1e-5:
        return knee
    direction = normalize(to_target)
    pole = pole_hint - direction * float(np.dot(pole_hint, direction))
    pole = normalize(pole) if np.linalg.norm(pole) > 1e-5 else fallback_pole_for(direction)
    min_reach = abs(upper_length - lower_length) + 1e-5
    max_reach = upper_length + lower_length - 1e-5
    solved_distance = clamp(actual_distance, min_reach, max_reach)
    along = (upper_length * upper_length - lower_length * lower_length + solved_distance * solved_distance) / (2.0 * solved_distance)
    height = np.sqrt(max(0.0, upper_length * upper_length - along * along))
    bend_base = hip + direction * along
    return bend_base + pole * height


def descendants_of(parents: np.ndarray, ancestor: int) -> set[int]:
    descendants: set[int] = set()
    for index in range(len(parents)):
        j = index
        while j >= 0:
            if j == ancestor:
                descendants.add(index)
                break
            j = int(parents[j])
    return descendants


def first_frame_foot_deltas(
    clip: viewer.Motion,
    idle: viewer.Motion,
    leg_specs: list[dict[str, int]],
    idx: dict[str, int],
    free_leg_side: str | None = None,
) -> tuple[list[dict[str, object]], dict[str, object] | None, np.ndarray]:
    target_frame = FOOT_IK_TARGET_FRAME
    idle_frame = min(IDLE_FOOT_REFERENCE_FRAME, int(idle.positions_m.shape[0]) - 1)
    root_offset = pos_at(clip.positions_m, target_frame, idx["root"]) - pos_at(idle.positions_m, idle_frame, idx["root"])
    leg_targets: list[dict[str, object]] = []
    free_leg_target: dict[str, object] | None = None
    mean_foot_delta = np.zeros(3, dtype=np.float64)
    mean_foot_count = 0
    for spec in leg_specs:
        foot_target = pos_at(idle.positions_m, idle_frame, spec["foot"]) + root_offset
        foot_delta = foot_target - pos_at(clip.positions_m, target_frame, spec["foot"])
        target = {
            "spec": spec,
            "foot_ik_delta": foot_delta,
            "source_foot_motion_span_m": float(
                np.max(
                    np.linalg.norm(
                        clip.positions_m[:, spec["foot"]].astype(np.float64)
                        - pos_at(clip.positions_m, target_frame, spec["foot"]),
                        axis=1,
                    )
                )
            ),
            "source_pole_local_frames": smoothed_foot_local_poles(clip, spec),
            "foot_local_axes": basis_axes_in_local(
                clip.basis,
                target_frame,
                spec["foot"],
                idle.basis,
                idle_frame,
                spec["foot"],
            ),
            "idle_pole_local": basis_vector_to_local(
                leg_pole_from_knee(
                    pos_at(idle.positions_m, idle_frame, spec["thigh"]),
                    pos_at(idle.positions_m, idle_frame, spec["calf"]),
                    pos_at(idle.positions_m, idle_frame, spec["foot"]),
                ),
                idle.basis,
                idle_frame,
                spec["foot"],
            ),
            "idle_ball_local": basis_vector_to_local(
                pos_at(idle.positions_m, idle_frame, spec["ball"]) - pos_at(idle.positions_m, idle_frame, spec["foot"]),
                idle.basis,
                idle_frame,
                spec["foot"],
            ),
            "idle_ball_local_axes": basis_axes_in_local(
                idle.basis,
                idle_frame,
                spec["foot"],
                idle.basis,
                idle_frame,
                spec["ball"],
            ),
        }
        mean_foot_delta += foot_delta
        mean_foot_count += 1
        if spec.get("side") == free_leg_side:
            free_leg_target = target
            continue
        leg_targets.append(target)
    if mean_foot_count:
        mean_foot_delta /= float(mean_foot_count)
    mean_ground_delta = np.asarray([mean_foot_delta[0], 0.0, mean_foot_delta[2]], dtype=np.float64)
    return leg_targets, free_leg_target, mean_ground_delta


def blend_idle_to_armed(
    clip: viewer.Motion,
    idle: viewer.Motion,
    positions: np.ndarray,
    basis: np.ndarray,
    config: dict[str, object],
    idx: dict[str, int],
) -> None:
    if bool(config.get("skip_idle_to_armed_blend", False)):
        return
    entry = dict(config.get("armed_by_clip", {})).get(clip.path.stem)
    if not isinstance(entry, dict):
        return
    armed_frame = float(entry.get("frame", 0.0))
    if not np.isfinite(armed_frame) or armed_frame <= 0.0:
        return
    armed_frame = min(float(clip.positions_m.shape[0] - 1), max(0.0, armed_frame))
    full_frame = max(0, int(np.floor(armed_frame + 1e-6)))
    if full_frame <= 0:
        return

    idle_frame = min(IDLE_FOOT_REFERENCE_FRAME, int(idle.positions_m.shape[0]) - 1)
    root_offset = pos_at(clip.positions_m, FOOT_IK_TARGET_FRAME, idx["root"]) - pos_at(
        idle.positions_m,
        idle_frame,
        idx["root"],
    )

    # Preserve the already accepted legacy blend for root, pelvis and both
    # legs.  Only the spine_01 subtree needs the hierarchical FK correction:
    # world-space interpolation there shortens articulated links (most visibly
    # the sword arm), while running hierarchical FK over the entire skeleton
    # changes the already-correct leg pose.  The upper body therefore follows
    # interpolated parent-local rotations and fixed target attachment vectors
    # on top of the untouched accepted pelvis/lower-body result.
    target_positions = positions.copy()
    target_basis = basis.copy()
    parents = np.asarray(clip.parents, dtype=np.int32)
    if any(int(parent) >= joint for joint, parent in enumerate(parents) if int(parent) >= 0):
        raise ValueError(f"{clip.path.name}: bones are not in parent-before-child order")

    upper_joints = sorted(descendants_of(parents, idx["spine_01"]))
    upper_set = set(upper_joints)
    preserved_joints = [joint for joint in range(len(clip.names)) if joint not in upper_set]
    idle_global_quats = [quat_from_axes(raw_basis_axes(idle.basis, idle_frame, joint)) for joint in preserved_joints]
    idle_local_axes: list[np.ndarray | None] = []
    for joint, parent_value in enumerate(parents):
        parent = int(parent_value)
        if parent < 0:
            idle_local_axes.append(None)
            continue
        idle_local_axes.append(
            basis_axes_in_local(idle.basis, idle_frame, parent, idle.basis, idle_frame, joint)
        )

    previous_quats: list[np.ndarray | None] = [None for _ in range(len(clip.names))]
    for f in range(min(full_frame, clip.positions_m.shape[0] - 1) + 1):
        alpha = 1.0 if f >= full_frame else clamp(float(f) / armed_frame, 0.0, 1.0)
        if alpha >= 1.0 - 1e-7:
            # Preserve the authored/modified armed pose exactly.
            positions[f, upper_joints] = target_positions[f, upper_joints]
            basis[f, upper_joints] = target_basis[f, upper_joints]
            continue

        for preserved_offset, joint in enumerate(preserved_joints):
            idle_position = pos_at(idle.positions_m, idle_frame, joint) + root_offset
            target_position = target_positions[f, joint].astype(np.float64)
            positions[f, joint] = idle_position + (target_position - idle_position) * alpha

            target_axes = orthonormal_axes(
                target_basis[f, joint, 0],
                target_basis[f, joint, 1],
                target_basis[f, joint, 2],
            )
            q = continuous_blend_quat(
                idle_global_quats[preserved_offset],
                quat_from_axes(target_axes),
                alpha,
                previous_quats[joint],
            )
            previous_quats[joint] = q
            basis[f, joint] = axes_from_quat(q)

        for joint in upper_joints:
            parent_value = parents[joint]
            parent = int(parent_value)
            target_axes = orthonormal_axes(
                target_basis[f, joint, 0],
                target_basis[f, joint, 1],
                target_basis[f, joint, 2],
            )
            target_parent_axes = orthonormal_axes(
                target_basis[f, parent, 0],
                target_basis[f, parent, 1],
                target_basis[f, parent, 2],
            )
            target_local_axes = orthonormal_axes(
                *[
                    np.asarray(
                        [np.dot(target_axes[axis], target_parent_axes[parent_axis]) for parent_axis in range(3)],
                        dtype=np.float64,
                    )
                    for axis in range(3)
                ]
            )
            idle_joint_local_axes = idle_local_axes[joint]
            assert idle_joint_local_axes is not None
            q = continuous_blend_quat(
                quat_from_axes(idle_joint_local_axes),
                quat_from_axes(target_local_axes),
                alpha,
                previous_quats[joint],
            )
            previous_quats[joint] = q
            basis[f, joint] = carried_child_axes_from_parent(basis[f, parent], axes_from_quat(q))

            target_local_position = np.asarray(
                [
                    np.dot(target_positions[f, joint] - target_positions[f, parent], target_parent_axes[axis])
                    for axis in range(3)
                ],
                dtype=np.float64,
            )
            positions[f, joint] = positions[f, parent] + vector_to_world_from_axes(
                target_local_position,
                basis[f, parent],
            )


def slerp_axes(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    if t <= 1e-7:
        return a
    if t >= 1.0 - 1e-7:
        return b
    return axes_from_quat(quat_slerp(quat_from_axes(a), quat_from_axes(b), t))


def carried_child_axes_from_parent(parent_axes: np.ndarray, child_local_axes: np.ndarray) -> np.ndarray:
    return orthonormal_axes(
        vector_to_world_from_axes(child_local_axes[0], parent_axes),
        vector_to_world_from_axes(child_local_axes[1], parent_axes),
        vector_to_world_from_axes(child_local_axes[2], parent_axes),
    )


def foot_frame0_lerp_for_clip(config: dict[str, object], clip_name: str) -> dict[str, float]:
    by_clip = config.get("foot_frame0_lerp_by_clip", {})
    entry = by_clip.get(clip_name, {}) if isinstance(by_clip, dict) else {}
    if not isinstance(entry, dict):
        entry = {}
    return {
        "left": clamp(float(entry.get("left", 0.0) or 0.0), 0.0, 1.0),
        "right": clamp(float(entry.get("right", 0.0) or 0.0), 0.0, 1.0),
    }


def apply_foot_frame0_lerp(
    clip: viewer.Motion,
    positions: np.ndarray,
    basis: np.ndarray,
    config: dict[str, object],
    leg_specs: list[dict[str, int | str]],
) -> None:
    values = foot_frame0_lerp_for_clip(config, clip.path.stem)
    if values["left"] <= 1e-7 and values["right"] <= 1e-7:
        return
    free_leg_side = free_leg_side_for_clip(clip.path.stem)
    for spec in leg_specs:
        side = str(spec["side"])
        if side == free_leg_side:
            continue
        amount = values["left"] if side == "left" else values["right"]
        if amount <= 1e-7:
            continue
        thigh = int(spec["thigh"])
        calf = int(spec["calf"])
        foot = int(spec["foot"])
        ball = int(spec["ball"])

        foot_pos0 = pos_at(positions, 0, foot)
        foot_axes0 = basis_axes_at(basis, 0, foot)
        pole0 = leg_pole_from_knee(pos_at(positions, 0, thigh), pos_at(positions, 0, calf), foot_pos0)
        pole_local0 = normalize(basis_vector_to_local(pole0, basis, 0, foot))

        for f in range(int(clip.positions_m.shape[0])):
            hip = pos_at(positions, f, thigh)
            knee = pos_at(positions, f, calf)
            foot_pos = pos_at(positions, f, foot)
            ball_pos = pos_at(positions, f, ball)
            foot_target = foot_pos + (foot_pos0 - foot_pos) * amount
            foot_target_axes = slerp_axes(basis_axes_at(basis, f, foot), foot_axes0, amount)
            ball_local = basis_vector_to_local(ball_pos - foot_pos, basis, f, foot)
            ball_target = foot_target + vector_to_world_from_axes(ball_local, foot_target_axes)
            ball_local_axes = basis_axes_in_local(basis, f, foot, basis, f, ball)
            ball_target_axes = carried_child_axes_from_parent(foot_target_axes, ball_local_axes)
            raw_pole = leg_pole_from_knee(hip, knee, foot_pos)
            pole_local = normalize(basis_vector_to_local(raw_pole, basis, f, foot))
            target_pole_local = normalize(pole_local + (pole_local0 - pole_local) * amount)
            carried_pole = normalize(vector_to_world_from_axes(target_pole_local, foot_target_axes))
            solved_knee = solve_two_bone_knee_with_pole(hip, knee, foot_pos, foot_target, carried_pole)

            positions[f, calf] = solved_knee
            positions[f, foot] = foot_target
            positions[f, ball] = ball_target
            basis[f, foot] = foot_target_axes
            basis[f, ball] = ball_target_axes


def modified_motion(clip: viewer.Motion, idle: viewer.Motion, config: dict[str, object]) -> tuple[np.ndarray, np.ndarray]:
    idx = viewer.name_index(clip.names)
    required = ["root", "pelvis", "thigh_l", "calf_l", "foot_l", "ball_l", "thigh_r", "calf_r", "foot_r", "ball_r"]
    missing = [name for name in required if name not in idx]
    if missing:
        raise ValueError(f"{clip.path.name} is missing required bones: {missing}")

    leg_specs = [
        {"side": "left", "thigh": idx["thigh_l"], "calf": idx["calf_l"], "foot": idx["foot_l"], "ball": idx["ball_l"]},
        {"side": "right", "thigh": idx["thigh_r"], "calf": idx["calf_r"], "foot": idx["foot_r"], "ball": idx["ball_r"]},
    ]
    positions = clip.positions_m.astype(np.float64).copy()
    basis = clip.basis.astype(np.float64).copy()

    free_leg_side = free_leg_side_for_clip(clip.path.stem)
    root_offset = pos_at(clip.positions_m, FOOT_IK_TARGET_FRAME, idx["root"]) - pos_at(
        idle.positions_m,
        min(IDLE_FOOT_REFERENCE_FRAME, int(idle.positions_m.shape[0]) - 1),
        idx["root"],
    )
    idle_frame = min(IDLE_FOOT_REFERENCE_FRAME, int(idle.positions_m.shape[0]) - 1)
    leg_targets, free_leg_target, mean_ground_delta = first_frame_foot_deltas(clip, idle, leg_specs, idx, free_leg_side)
    armed_frame = armed_frame_for_clip(config, clip.path.stem, int(clip.positions_m.shape[0]))
    is_kick_clip = free_leg_target is not None and armed_frame is not None
    cleanup = cleanup_for_clip(config, clip.path.stem)
    pelvis_source_delta = mean_ground_delta.copy()
    if is_kick_clip and leg_targets:
        support_delta = np.asarray(leg_targets[0]["foot_ik_delta"], dtype=np.float64)
        support_ground_delta = np.asarray([support_delta[0], 0.0, support_delta[2]], dtype=np.float64)
        pelvis_source_delta = mean_ground_delta + (support_ground_delta - mean_ground_delta) * cleanup["pelvis_source_blend"]
    body_delta = pelvis_source_delta * float(cleanup["pelvis_offset_scale"])
    extra_pelvis_offset = np.asarray(cleanup["extra_pelvis_offset_m"], dtype=np.float64)
    excluded: set[int] = set()
    for spec in leg_specs:
        excluded.update([int(spec["calf"]), int(spec["foot"]), int(spec["ball"])])
    pelvis_offset_bones = descendants_of(clip.parents, idx["pelvis"]) - excluded

    for f in range(int(clip.positions_m.shape[0])):
        pose_alpha = 1.0
        if free_leg_target is not None and armed_frame is not None:
            pose_alpha = clamp(float(f) / max(1e-7, armed_frame), 0.0, 1.0)
        pelvis_extra_alpha = 1.0
        if armed_frame is not None:
            pelvis_extra_alpha = 1.0 - clamp(float(f) / max(1e-7, armed_frame), 0.0, 1.0)
        extra_delta = extra_pelvis_offset * pelvis_extra_alpha
        for joint in pelvis_offset_bones:
            target_pos = clip.positions_m[f, joint].astype(np.float64) + body_delta + extra_delta
            target_axes = basis_axes_at(clip.basis, f, joint)
            positions[f, joint] = target_pos
            basis[f, joint] = target_axes
        for target in leg_targets:
            spec = target["spec"]
            assert isinstance(spec, dict)
            support_mode = cleanup["pelvis_source_blend"] if is_kick_clip else 0.0
            raw_hip = clip.positions_m[f, spec["thigh"]].astype(np.float64)
            raw_knee = clip.positions_m[f, spec["calf"]].astype(np.float64)
            raw_foot = clip.positions_m[f, spec["foot"]].astype(np.float64)
            raw_ball = clip.positions_m[f, spec["ball"]].astype(np.float64)
            hip = positions[f, spec["thigh"]].astype(np.float64)
            knee_seed = raw_knee + body_delta
            foot_seed = raw_foot + body_delta
            if is_kick_clip:
                raw_foot0 = clip.positions_m[FOOT_IK_TARGET_FRAME, spec["foot"]].astype(np.float64)
                locked_foot_target = raw_foot0 + target["foot_ik_delta"]
                carried_foot_target = raw_foot + body_delta
                foot_target = locked_foot_target + (carried_foot_target - locked_foot_target) * support_mode
                locked_foot_axes = carried_basis_axes(clip.basis, FOOT_IK_TARGET_FRAME, spec["foot"], target["foot_local_axes"])
                carried_foot_axes = basis_axes_at(clip.basis, f, spec["foot"])
                foot_axes = slerp_axes(locked_foot_axes, carried_foot_axes, support_mode)
            else:
                foot_target = raw_foot + target["foot_ik_delta"]
                foot_axes = carried_basis_axes(clip.basis, f, spec["foot"], target["foot_local_axes"])
            raw_ball_local = basis_vector_to_local(raw_ball - raw_foot, clip.basis, f, spec["foot"])
            ball_local = target["idle_ball_local"] + (raw_ball_local - target["idle_ball_local"]) * support_mode if is_kick_clip else raw_ball_local
            ball_target = foot_target + vector_to_world_from_axes(ball_local, foot_axes)
            raw_ball_local_axes = basis_axes_in_local(clip.basis, f, spec["foot"], clip.basis, f, spec["ball"])
            if is_kick_clip:
                locked_ball_axes = carried_child_axes_from_parent(foot_axes, target["idle_ball_local_axes"])
                carried_ball_axes = carried_child_axes_from_parent(foot_axes, raw_ball_local_axes)
                ball_axes = slerp_axes(locked_ball_axes, carried_ball_axes, support_mode)
            else:
                ball_axes = carried_child_axes_from_parent(foot_axes, raw_ball_local_axes)
            raw_pole = leg_pole_from_knee(raw_hip, raw_knee, raw_foot)
            raw_pole_local = basis_vector_to_local(raw_pole, clip.basis, f, spec["foot"])
            if is_kick_clip:
                pole_local = normalize(target["idle_pole_local"] + (raw_pole_local - target["idle_pole_local"]) * support_mode)
                carried_pole = normalize(vector_to_world_from_axes(pole_local, foot_axes))
            elif float(target["source_foot_motion_span_m"]) <= 0.12:
                source_poles = np.asarray(target["source_pole_local_frames"], dtype=np.float64)
                pole_local = normalize(source_poles[0])
                carried_pole = normalize(vector_to_world_from_axes(pole_local, foot_axes))
            else:
                source_poles = np.asarray(target["source_pole_local_frames"], dtype=np.float64)
                pole_local = normalize(source_poles[f])
                carried_pole = normalize(vector_to_world_from_axes(pole_local, foot_axes))
            upper_length = float(np.linalg.norm(raw_knee - raw_hip))
            lower_length = float(np.linalg.norm(raw_foot - raw_knee))
            solved_knee = solve_two_bone_knee_with_pole(
                hip,
                knee_seed,
                foot_seed,
                foot_target,
                carried_pole,
                upper_length,
                lower_length,
            )
            positions[f, spec["calf"]] = solved_knee
            positions[f, spec["foot"]] = foot_target
            positions[f, spec["ball"]] = ball_target
            basis[f, spec["foot"]] = foot_axes
            basis[f, spec["ball"]] = ball_axes
        if free_leg_target is not None and armed_frame is not None:
            spec = free_leg_target["spec"]
            assert isinstance(spec, dict)
            alpha = pose_alpha
            leg_delta = free_leg_target["foot_ik_delta"] + (body_delta - free_leg_target["foot_ik_delta"]) * alpha
            raw_hip = clip.positions_m[f, spec["thigh"]].astype(np.float64)
            raw_knee = clip.positions_m[f, spec["calf"]].astype(np.float64)
            raw_foot = clip.positions_m[f, spec["foot"]].astype(np.float64)
            raw_ball = clip.positions_m[f, spec["ball"]].astype(np.float64)
            hip = positions[f, spec["thigh"]].astype(np.float64)
            knee_seed = raw_knee + body_delta
            foot_seed = raw_foot + body_delta
            foot_target = raw_foot + leg_delta
            idle_foot_axes = carried_basis_axes(clip.basis, f, spec["foot"], free_leg_target["foot_local_axes"])
            raw_foot_axes = basis_axes_at(clip.basis, f, spec["foot"])
            foot_axes = slerp_axes(idle_foot_axes, raw_foot_axes, alpha)
            raw_ball_local = basis_vector_to_local(raw_ball - raw_foot, clip.basis, f, spec["foot"])
            ball_local = free_leg_target["idle_ball_local"] + (raw_ball_local - free_leg_target["idle_ball_local"]) * alpha
            ball_target = foot_target + vector_to_world_from_axes(ball_local, foot_axes)
            raw_ball_local_axes = basis_axes_in_local(clip.basis, f, spec["foot"], clip.basis, f, spec["ball"])
            idle_ball_axes = carried_child_axes_from_parent(foot_axes, free_leg_target["idle_ball_local_axes"])
            raw_ball_axes = carried_child_axes_from_parent(foot_axes, raw_ball_local_axes)
            ball_axes = slerp_axes(idle_ball_axes, raw_ball_axes, alpha)
            raw_pole = leg_pole_from_knee(raw_hip, raw_knee, raw_foot)
            raw_pole_local = basis_vector_to_local(raw_pole, clip.basis, f, spec["foot"])
            pole_local = normalize(free_leg_target["idle_pole_local"] + (raw_pole_local - free_leg_target["idle_pole_local"]) * alpha)
            carried_pole = normalize(vector_to_world_from_axes(pole_local, foot_axes))
            upper_length = float(np.linalg.norm(raw_knee - raw_hip))
            lower_length = float(np.linalg.norm(raw_foot - raw_knee))
            solved_knee = solve_two_bone_knee_with_pole(
                hip,
                knee_seed,
                foot_seed,
                foot_target,
                carried_pole,
                upper_length,
                lower_length,
            )
            positions[f, spec["calf"]] = solved_knee
            positions[f, spec["foot"]] = foot_target
            positions[f, spec["ball"]] = ball_target
            basis[f, spec["foot"]] = foot_axes
            basis[f, spec["ball"]] = ball_axes

    blend_idle_to_armed(clip, idle, positions, basis, config, idx)
    apply_foot_frame0_lerp(clip, positions, basis, config, leg_specs)
    return positions, basis


def sword_local_to_hand(sword: dict[str, object], v: np.ndarray) -> np.ndarray:
    m = np.asarray(sword["local_to_hand"], dtype=np.float64)
    return np.asarray(
        [
            v[0] * m[0] + v[1] * m[4] + v[2] * m[8] + m[12],
            v[0] * m[1] + v[1] * m[5] + v[2] * m[9] + m[13],
            v[0] * m[2] + v[1] * m[6] + v[2] * m[10] + m[14],
        ],
        dtype=np.float64,
    )


def blade_center_local_at(sword: dict[str, object], t: float, blade_scale: float) -> np.ndarray:
    mn = np.asarray(sword["blade_bounds_min_m"], dtype=np.float64)
    mx = np.asarray(sword["blade_bounds_max_m"], dtype=np.float64)
    v = (mn + mx) * 0.5
    base = float(sword["blade_base_m"])
    tip = base + blade_scale * (float(sword["blade_tip_m"]) - base)
    v[int(sword["blade_axis"])] = base + clamp(t, 0.0, 1.0) * (tip - base)
    return v


def sword_local_point_to_world(sword: dict[str, object], local_point: np.ndarray, hand_pos: np.ndarray, hand_axes: np.ndarray) -> np.ndarray:
    hand_local = sword_local_to_hand(sword, local_point)
    return hand_pos + hand_axes[0] * hand_local[0] + hand_axes[1] * hand_local[1] + hand_axes[2] * hand_local[2]


def hit_world_point(
    sword: dict[str, object],
    positions: np.ndarray,
    basis: np.ndarray,
    frame: float,
    hand_index: int,
    hit_t: float,
    blade_scale: float,
) -> np.ndarray:
    hand_pos = pos_at(positions, frame, hand_index)
    hand_axes = basis_axes_at(basis, frame, hand_index)
    return sword_local_point_to_world(sword, blade_center_local_at(sword, hit_t, blade_scale), hand_pos, hand_axes)


def world_to_pelvis_local(positions: np.ndarray, basis: np.ndarray, frame: float, pelvis_index: int, p: np.ndarray) -> np.ndarray:
    pelvis_pos = pos_at(positions, frame, pelvis_index)
    axes = basis_axes_at(basis, frame, pelvis_index)
    rel = p - pelvis_pos
    return np.asarray([np.dot(rel, axes[0]), np.dot(rel, axes[1]), np.dot(rel, axes[2])], dtype=np.float64)


def round_vec(v: np.ndarray) -> list[float]:
    return [round(float(x), 6) for x in v]


def latest_hit_entry(config: dict[str, object], clip_name: str) -> dict[str, object] | None:
    target = config.get("target", {})
    if not isinstance(target, dict):
        return None
    hits_by_clip = target.get("hits_by_clip", {})
    if not isinstance(hits_by_clip, dict):
        return None
    entries = hits_by_clip.get(clip_name, [])
    if not isinstance(entries, list) or not entries:
        return None
    return entries[-1] if isinstance(entries[-1], dict) else None


def update_config(config_path: Path) -> None:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    idle = viewer.load_motion(viewer.DEFAULT_IDLE_NPZ)
    sword = viewer.load_sword_mesh(viewer.DEFAULT_SWORD_FBX)

    slash_paths = sorted(viewer.DEFAULT_FIXEDROOT_SLASH_DIR.glob("*.npz"))
    if not slash_paths:
        raise FileNotFoundError(f"No slash NPZ files found in {viewer.DEFAULT_FIXEDROOT_SLASH_DIR}")

    report: list[tuple[str, float, float]] = []
    for path in slash_paths:
        clip = viewer.load_motion(path)
        idx = viewer.name_index(clip.names)
        positions, basis = modified_motion(clip, idle, config)
        hand_index = idx["hand_r"]
        pelvis_index = idx["pelvis"]
        clip_name = path.stem

        armed_by_clip = config.setdefault("armed_by_clip", {})
        if not isinstance(armed_by_clip, dict):
            raise ValueError("armed_by_clip must be an object")
        armed = armed_by_clip.get(clip_name)
        if isinstance(armed, dict):
            armed_frame = float(armed.get("frame", 0.0))
            armed_hit_t = float(armed.get("hit_t", config.get("hit", 0.64)))
            armed_blade_scale = float(armed.get("blade_length", config.get("blade_length", 1.0)))
            hit_world = hit_world_point(sword, positions, basis, armed_frame, hand_index, armed_hit_t, armed_blade_scale)
            hand_world = pos_at(positions, armed_frame, hand_index)
            armed["armed_blade_pelvis_m"] = round_vec(world_to_pelvis_local(positions, basis, armed_frame, pelvis_index, hit_world))
            armed["armed_hand_pelvis_m"] = round_vec(world_to_pelvis_local(positions, basis, armed_frame, pelvis_index, hand_world))

        hit = latest_hit_entry(config, clip_name)
        if isinstance(hit, dict):
            hit_frame = float(hit.get("frame", 0.0))
            hit_t = float(hit.get("hit_t", config.get("hit", 0.64)))
            blade_scale = float(hit.get("blade_length", config.get("blade_length", 1.0)))
            old = np.asarray(hit.get("hit_world_m", [np.nan, np.nan, np.nan]), dtype=np.float64)
            new = hit_world_point(sword, positions, basis, hit_frame, hand_index, hit_t, blade_scale)
            hit["hit_world_m"] = round_vec(new)
            if np.isfinite(old).all():
                report.append((clip_name, float(np.linalg.norm(new - old)), hit_frame))

    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"updated {config_path}")
    for clip_name, delta, frame in report:
        print(f"{clip_name:7s} hit frame {frame:7.3f} moved {delta:0.4f} m")


def main() -> None:
    parser = argparse.ArgumentParser(description="Move slash armed/hit targets onto the slashes2 modified pose stream.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    update_config(args.config.resolve())


if __name__ == "__main__":
    main()
