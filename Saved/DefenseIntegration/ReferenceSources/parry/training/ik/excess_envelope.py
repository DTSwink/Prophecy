from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

import torch
import torch.nn.functional as F

try:
    from .bootstrap import PROJECT_ROOT, ensure_paths
    from . import ik_core as tl
    from . import train_simple_ae_controller as ctl
except ImportError:
    from bootstrap import PROJECT_ROOT, ensure_paths
    import ik_core as tl
    import train_simple_ae_controller as ctl

ensure_paths()

try:
    from . import contact_physics as cp
except ImportError:
    import contact_physics as cp


CACHE_VERSION = 23
BOUND_LOOKUP_GLOBAL_P95 = "global_p95_slide_yaw_height_conditioned_and_height_speed_conditioned"
SITUATION_FEATURE_GLOBAL_P95 = (
    "global_yaw_delta/pi,bend_angle/pi,runtime_horizontal_foot_distance_xz_m,"
    "per_foot_height_for_slide_yaw,per_foot_slide_speed_for_height"
)
ENVELOPE_UPPER_PERCENTILE = 0.95
ENVELOPE_LOWER_PERCENTILE = 0.05
MIN_PERCENTILE_KNN = 64
FOOT_HEIGHT_FEATURE_SCALE = 10.0
SOLE_SAMPLE_GRID_VALUES = (
    (-1.0, -1.0),
    (-1.0, 0.0),
    (-1.0, 1.0),
    (0.0, -1.0),
    (0.0, 0.0),
    (0.0, 1.0),
    (1.0, -1.0),
    (1.0, 0.0),
    (1.0, 1.0),
)
_SOLE_SAMPLE_GRID_CACHE: dict[tuple[str, torch.dtype], torch.Tensor] = {}
_LEG_START_INDEX_CACHE: dict[tuple[tuple[int, ...], str], torch.Tensor] = {}
_BOX_DIMS_CACHE: dict[tuple[str, torch.dtype], torch.Tensor] = {}
_ENVELOPE_MEMORY_CACHE: dict[tuple[str, str], dict[str, torch.Tensor | dict[str, float | int | str]]] = {}
_ENVELOPE_FAST_MEMORY_CACHE: dict[tuple, dict[str, torch.Tensor | dict[str, float | int | str]]] = {}
_GROUNDTRUTH_SANITY_CACHE: dict[tuple[str, str], dict[str, float]] = {}


def _groundtruth_sanity_sidecar(cache_path: str, device: torch.device) -> Path | None:
    if not cache_path:
        return None
    safe_device = str(device).replace(":", "_").replace("\\", "_").replace("/", "_")
    return Path(cache_path).with_suffix(Path(cache_path).suffix + f".{safe_device}.sanity.json")


def _load_groundtruth_sanity_sidecar(cache_path: str, device: torch.device) -> dict[str, float] | None:
    sidecar = _groundtruth_sanity_sidecar(cache_path, device)
    if sidecar is None or not sidecar.exists():
        return None
    try:
        envelope_path = Path(cache_path)
        stat = envelope_path.stat()
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        if int(payload.get("envelope_mtime_ns", -1)) != int(stat.st_mtime_ns):
            return None
        if int(payload.get("envelope_size", -1)) != int(stat.st_size):
            return None
        if int(payload.get("cache_version", -1)) != int(CACHE_VERSION):
            return None
        result = payload.get("result")
        if not isinstance(result, dict):
            return None
        return {str(key): float(value) for key, value in result.items()}
    except Exception:
        return None


def _save_groundtruth_sanity_sidecar(cache_path: str, device: torch.device, result: dict[str, float]) -> None:
    sidecar = _groundtruth_sanity_sidecar(cache_path, device)
    if sidecar is None:
        return
    try:
        envelope_path = Path(cache_path)
        stat = envelope_path.stat()
        payload = {
            "cache_version": int(CACHE_VERSION),
            "envelope_mtime_ns": int(stat.st_mtime_ns),
            "envelope_size": int(stat.st_size),
            "device": str(device),
            "result": {str(key): float(value) for key, value in result.items()},
        }
        tmp_path = sidecar.with_suffix(sidecar.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        tmp_path.replace(sidecar)
    except Exception:
        pass


def sole_proxy_toe_offset_m(cfg: cp.ContactGeometryConfig = cp.DEFAULT_GEOMETRY) -> float:
    return float(cfg.toe_height * 0.5 - cfg.sole_vertical_offset)


@dataclass(frozen=True)
class ExcessEnvelopeConfig:
    margin: float = 1.05
    knn: int = MIN_PERCENTILE_KNN
    cache_dir: str = "training/runs/cache/ik_excess_envelopes"
    chunk_size: int = 4096


def signed_horizontal_angle(a: torch.Tensor, b: torch.Tensor, eps: float = 1e-8) -> torch.Tensor:
    a2 = a[..., [0, 2]]
    b2 = b[..., [0, 2]]
    an = torch.linalg.norm(a2, dim=-1)
    bn = torch.linalg.norm(b2, dim=-1)
    dot = (a2 * b2).sum(dim=-1)
    cross = a2[..., 0] * b2[..., 1] - a2[..., 1] * b2[..., 0]
    angle = torch.atan2(cross, dot)
    valid = torch.logical_and(an > eps, bn > eps)
    return torch.where(valid, angle, torch.zeros_like(angle))


@torch.no_grad()
def root_situation_feature(
    clip: tl.MotionClip,
    cur_idx: torch.Tensor,
    cfg: tl.TrainConfig,
    device: torch.device,
) -> torch.Tensor:
    cur_idx = cur_idx.to(device=device, dtype=torch.long)
    prev_idx = cur_idx - 1
    fut_idx = cur_idx + int(cfg.future_window)
    if not clip.cyclic_animation:
        fut_idx = torch.clamp(fut_idx, max=int(clip.T) - 1)
    prev_pos, _prev_rot, prev_yaw, _prev_heading = tl.root_state(clip, prev_idx, cfg, device)
    cur_pos, _cur_rot, _cur_yaw, _cur_heading = tl.root_state(clip, cur_idx, cfg, device)
    fut_pos, _fut_rot, fut_yaw, _fut_heading = tl.root_state(clip, fut_idx, cfg, device)
    yaw_delta = tl.wrap_angle(fut_yaw - prev_yaw) / torch.pi
    bend = signed_horizontal_angle(cur_pos - prev_pos, fut_pos - cur_pos) / torch.pi
    tensors = clip.tensors(device)
    global_pos = tensors["global_pos"].index_select(0, cur_idx)
    left = int(clip.body_names.index("foot_l"))
    right = int(clip.body_names.index("foot_r"))
    foot_distance = torch.linalg.norm(global_pos[:, left, [0, 2]] - global_pos[:, right, [0, 2]], dim=-1)
    return torch.stack((yaw_delta, bend, foot_distance), dim=-1)


def runtime_situation_feature(
    store: ctl.SimpleClipStore,
    cur_pos: torch.Tensor,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
) -> torch.Tensor:
    prev_idx = cur_idx - 1
    fut_idx = cur_idx + int(store.cfg.future_window)
    prev_root_pos, _prev_rot, prev_yaw, _prev_heading = store.root_state(clip_ids, prev_idx)
    cur_root_pos, _cur_rot, _cur_yaw, _cur_heading = store.root_state(clip_ids, cur_idx)
    fut_root_pos, _fut_rot, fut_yaw, _fut_heading = store.root_state(clip_ids, fut_idx)
    yaw_delta = tl.wrap_angle(fut_yaw - prev_yaw) / torch.pi
    bend = signed_horizontal_angle(cur_root_pos - prev_root_pos, fut_root_pos - cur_root_pos) / torch.pi
    left = int(store.prototype.body_names.index("foot_l"))
    right = int(store.prototype.body_names.index("foot_r"))
    foot_distance = torch.linalg.norm(cur_pos[:, left, [0, 2]] - cur_pos[:, right, [0, 2]], dim=-1)
    return torch.stack((yaw_delta, bend, foot_distance), dim=-1)


def runtime_situation_feature_from_feet(
    store: ctl.SimpleClipStore,
    cur_foot_toe_pos: torch.Tensor,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
) -> torch.Tensor:
    prev_idx = cur_idx - 1
    fut_idx = cur_idx + int(store.cfg.future_window)
    prev_root_pos, _prev_rot, prev_yaw, _prev_heading = store.root_state(clip_ids, prev_idx)
    cur_root_pos, _cur_rot, _cur_yaw, _cur_heading = store.root_state(clip_ids, cur_idx)
    fut_root_pos, _fut_rot, fut_yaw, _fut_heading = store.root_state(clip_ids, fut_idx)
    yaw_delta = tl.wrap_angle(fut_yaw - prev_yaw) / torch.pi
    bend = signed_horizontal_angle(cur_root_pos - prev_root_pos, fut_root_pos - cur_root_pos) / torch.pi
    foot_dx = cur_foot_toe_pos[:, 0, 0] - cur_foot_toe_pos[:, 2, 0]
    foot_dz = cur_foot_toe_pos[:, 0, 2] - cur_foot_toe_pos[:, 2, 2]
    foot_distance = torch.sqrt(foot_dx.square() + foot_dz.square() + 1e-12)
    return torch.stack((yaw_delta, bend, foot_distance), dim=-1)


def _leg_base_positions_root(store: ctl.SimpleClipStore, vec: torch.Tensor) -> torch.Tensor:
    clip = store.prototype
    tensors = clip.tensors(store.device)
    b = int(vec.shape[0])
    dtype = vec.dtype
    cursor = 0
    pelvis_pos = vec[:, cursor : cursor + 3]
    cursor += 3
    pelvis_rot = tl.rotation_6d_to_matrix(vec[:, cursor : cursor + 6])
    cursor += 6
    leg_starts = [int(spec["start"]) for spec in clip.ik_limb_specs if str(spec["kind"]) == "leg"]
    if all(int(clip.parents_body_list[start]) == int(clip.pelvis) for start in leg_starts):
        key = (tuple(leg_starts), str(store.device))
        leg_start_tensor = _LEG_START_INDEX_CACHE.get(key)
        if leg_start_tensor is None:
            leg_start_tensor = torch.tensor(leg_starts, dtype=torch.long, device=store.device)
            _LEG_START_INDEX_CACHE[key] = leg_start_tensor
        offsets = tensors["local_offsets"].to(dtype=dtype).index_select(
            0,
            leg_start_tensor,
        )
        return pelvis_pos[:, None, :] + torch.matmul(offsets.reshape(1, len(leg_starts), 3), pelvis_rot)

    core_dim = clip.Jcore * 6
    core_raw = vec[:, cursor : cursor + core_dim].reshape(b, clip.Jcore, 6)
    needed: set[int] = set()
    for start in leg_starts:
        j = int(start)
        while j >= 0:
            needed.add(j)
            j = int(clip.parents_body_list[j])
    local_offsets = tensors["local_offsets"].to(dtype=dtype)
    identity = torch.eye(3, dtype=dtype, device=store.device).expand(b, 3, 3)
    pos_root: dict[int, torch.Tensor] = {}
    rot_root: dict[int, torch.Tensor] = {}
    for j in sorted(needed):
        if j == int(clip.pelvis):
            local_offset = pelvis_pos
            local_rot = pelvis_rot
        else:
            local_offset = local_offsets[j].reshape(1, 3).expand(b, 3)
            if j in clip.core_nonpelvis_map:
                local_rot = tl.rotation_6d_to_matrix(core_raw[:, int(clip.core_nonpelvis_map[j])])
            else:
                local_rot = identity
        parent = int(clip.parents_body_list[j])
        if parent < 0:
            pos_root[j] = local_offset
            rot_root[j] = local_rot
        else:
            parent_pos = pos_root[parent]
            parent_rot = rot_root[parent]
            pos_root[j] = torch.matmul(local_offset.unsqueeze(1), parent_rot).squeeze(1) + parent_pos
            rot_root[j] = local_rot @ parent_rot
    return torch.stack([pos_root[int(start)] for start in leg_starts], dim=1)


def ik_foot_toe_state_from_vec(
    store: ctl.SimpleClipStore,
    root_pos: torch.Tensor,
    root_rot: torch.Tensor,
    vec: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    clip = store.prototype
    tensors = clip.tensors(store.device)
    payload = vec[:, ctl.payload_slice(store)]
    leg_entries = tuple(
        (i, spec) for i, spec in enumerate(store.ik_payload_slices) if str(spec["kind"]).lower().strip() == "leg"
    )
    if len(leg_entries) != 2:
        raise ValueError(f"Expected exactly two active leg IK limbs, got {len(leg_entries)}")
    left_limb_i, left_spec = leg_entries[0]
    right_limb_i, right_spec = leg_entries[1]
    left_pos = left_spec["pos"]
    right_pos = right_spec["pos"]
    left_rot = left_spec["rot6"]
    right_rot = right_spec["rot6"]
    assert isinstance(left_pos, slice) and isinstance(right_pos, slice)
    assert isinstance(left_rot, slice) and isinstance(right_rot, slice)

    b = int(vec.shape[0])
    end_root = torch.stack((payload[:, left_pos], payload[:, right_pos]), dim=1)
    end_rot6 = torch.stack((payload[:, left_rot], payload[:, right_rot]), dim=1).reshape(b * 2, 6)
    end_rot_root = tl.rotation_6d_to_matrix(end_rot6).reshape(b, 2, 3, 3)

    leg_limb_indices = getattr(store, "ik_payload_leg_limb_indices_tensor", None)
    if leg_limb_indices is None or int(leg_limb_indices.numel()) != 2:
        raise ValueError("SimpleClipStore is missing the cached leg IK limb index tensor")
    toe_offset = tensors["ik_toe_offsets"].index_select(0, leg_limb_indices).to(dtype=vec.dtype).reshape(1, 2, 3)
    toe_pos_root = end_root + torch.matmul(toe_offset.unsqueeze(-2), end_rot_root).squeeze(-2)
    foot_pos_world = torch.matmul(end_root, root_rot) + root_pos[:, None, :]
    toe_pos_world = torch.matmul(toe_pos_root, root_rot) + root_pos[:, None, :]
    foot_rot_world = end_rot_root @ root_rot[:, None, :, :]
    positions = torch.stack((foot_pos_world[:, 0], toe_pos_world[:, 0], foot_pos_world[:, 1], toe_pos_world[:, 1]), dim=1)
    rotations = torch.stack((foot_rot_world[:, 0], foot_rot_world[:, 0], foot_rot_world[:, 1], foot_rot_world[:, 1]), dim=1)
    return positions, rotations


def _sole_sample_grid(device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    key = (str(device), dtype)
    cached = _SOLE_SAMPLE_GRID_CACHE.get(key)
    if cached is None:
        cached = torch.tensor(SOLE_SAMPLE_GRID_VALUES, dtype=dtype, device=device)
        _SOLE_SAMPLE_GRID_CACHE[key] = cached
    return cached


def _compact_box_specs(
    positions: torch.Tensor,
    rotations: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    cfg = cp.DEFAULT_GEOMETRY
    foot = torch.stack((positions[:, 0], positions[:, 2]), dim=1)
    toe = torch.stack((positions[:, 1], positions[:, 3]), dim=1)
    toe_vec = toe - foot
    b, sides, _ = toe_vec.shape

    foot_forward, foot_side, foot_up = cp.basis_axes_from_direction(
        torch.stack((rotations[:, 0], rotations[:, 2]), dim=1).reshape(b * sides, 3, 3),
        toe_vec.reshape(b * sides, 3),
        1,
    )
    toe_forward, toe_side, toe_up = cp.basis_axes_from_direction(
        torch.stack((rotations[:, 1], rotations[:, 3]), dim=1).reshape(b * sides, 3, 3),
        toe_vec.reshape(b * sides, 3),
        0,
    )
    foot_forward = foot_forward.reshape(b, sides, 3)
    foot_side = foot_side.reshape(b, sides, 3)
    foot_up = foot_up.reshape(b, sides, 3)
    toe_forward = toe_forward.reshape(b, sides, 3)
    toe_side = toe_side.reshape(b, sides, 3)
    toe_up = toe_up.reshape(b, sides, 3)

    foot_center = toe - foot_forward * (cfg.foot_length * 0.5) + foot_up * cfg.sole_vertical_offset
    toe_center = toe + toe_forward * (cfg.toe_length * 0.5) + toe_up * cfg.sole_vertical_offset
    centers = torch.stack((foot_center, toe_center), dim=2)
    forward = torch.stack((foot_forward, toe_forward), dim=2)
    side = torch.stack((foot_side, toe_side), dim=2)
    up = torch.stack((foot_up, toe_up), dim=2)
    dims = _box_dims(positions.device, positions.dtype)
    return centers, forward, side, up, dims


def _box_dims(device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    key = (str(device), dtype)
    cached = _BOX_DIMS_CACHE.get(key)
    if cached is None:
        cfg = cp.DEFAULT_GEOMETRY
        cached = torch.tensor(
            (
                (cfg.foot_length, cfg.foot_width, cfg.foot_height),
                (cfg.toe_length, cfg.toe_width, cfg.toe_height),
            ),
            dtype=dtype,
            device=device,
        )
        _BOX_DIMS_CACHE[key] = cached
    return cached


def compact_foot_heights(
    positions: torch.Tensor,
    rotations: torch.Tensor,
) -> torch.Tensor:
    """Return signed sole-proxy height for left/right feet.

    `positions` and `rotations` use the compact order:
    foot_l, ball_l, foot_r, ball_r.

    The foot bone is an ankle-style marker and sits higher than the ball/toe
    marker when the foot is flat.  Measure height from two simple sole points:
    one below the foot bone by the local ankle-to-ball vertical gap plus the
    toe sole offset, and one below the ball/toe bone by the toe sole offset.
    """
    cfg = cp.DEFAULT_GEOMETRY
    foot = torch.stack((positions[:, 0], positions[:, 2]), dim=1)
    toe = torch.stack((positions[:, 1], positions[:, 3]), dim=1)
    toe_vec = toe - foot
    b, sides, _ = toe_vec.shape

    _foot_forward, _foot_side, foot_up = cp.basis_axes_from_direction(
        torch.stack((rotations[:, 0], rotations[:, 2]), dim=1).reshape(b * sides, 3, 3),
        toe_vec.reshape(b * sides, 3),
        1,
    )
    _toe_forward, _toe_side, toe_up = cp.basis_axes_from_direction(
        torch.stack((rotations[:, 1], rotations[:, 3]), dim=1).reshape(b * sides, 3, 3),
        toe_vec.reshape(b * sides, 3),
        0,
    )
    foot_up = foot_up.reshape(b, sides, 3)
    toe_up = toe_up.reshape(b, sides, 3)

    toe_sole_offset = sole_proxy_toe_offset_m(cfg)
    ankle_to_ball_vertical = ((foot - toe) * foot_up).sum(dim=-1).clamp_min(0.0)
    foot_sole = foot - foot_up * (ankle_to_ball_vertical + toe_sole_offset).unsqueeze(-1)
    toe_sole = toe - toe_up * toe_sole_offset
    heights = torch.stack((foot_sole[..., 1], toe_sole[..., 1]), dim=-1) - float(cfg.ground_y)
    return heights.amin(dim=-1)


def height_lower_margin(values: torch.Tensor, margin: float) -> torch.Tensor:
    margin = max(1.0, float(margin))
    return torch.where(values >= 0.0, values / margin, values * margin)


def height_upper_margin(values: torch.Tensor, margin: float) -> torch.Tensor:
    margin = max(1.0, float(margin))
    return torch.where(values >= 0.0, values * margin, values / margin)


def compact_foot_slide_speeds(
    cur_pos: torch.Tensor,
    next_pos: torch.Tensor,
    fps: float,
) -> torch.Tensor:
    cur_points = cur_pos.reshape(cur_pos.shape[0], 2, 2, 3)
    next_points = next_pos.reshape(next_pos.shape[0], 2, 2, 3)
    dx = next_points[..., 0] - cur_points[..., 0]
    dz = next_points[..., 2] - cur_points[..., 2]
    return torch.sqrt(dx.square() + dz.square() + 1e-12).amin(dim=-1) * float(fps)


def _fixed_sole_points(
    specs: tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor],
) -> torch.Tensor:
    center, forward, side, up, dims = specs
    grid = _sole_sample_grid(center.device, center.dtype).reshape(1, 1, 1, -1, 2)
    half = dims[:, :2].reshape(1, 1, 2, 1, 2) * 0.5
    offsets = grid * half
    sole_center = center - up * (dims[:, 2].reshape(1, 1, 2, 1) * 0.5)
    return (
        sole_center.unsqueeze(-2)
        + forward.unsqueeze(-2) * offsets[..., 0:1]
        + side.unsqueeze(-2) * offsets[..., 1:2]
    )


def compact_slide_yaw_selected_from_specs(
    cur_pos: torch.Tensor,
    cur_rot: torch.Tensor,
    next_pos: torch.Tensor,
    next_rot: torch.Tensor,
    cur_specs: tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor],
    next_specs: tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor],
    fps: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    cur_points = _fixed_sole_points(cur_specs)
    next_points = _fixed_sole_points(next_specs)
    linear = torch.linalg.norm((next_points - cur_points)[..., [0, 2]], dim=-1).flatten(2).amin(dim=-1) * float(fps)
    planted = cur_points[..., 1].flatten(2).amin(dim=-1).argmin(dim=-1)

    left_delta = cur_rot[:, 0].transpose(-1, -2) @ next_rot[:, 0]
    right_delta = cur_rot[:, 2].transpose(-1, -2) @ next_rot[:, 2]
    left_yaw = torch.atan2(left_delta[:, 0, 2] - left_delta[:, 2, 0], left_delta[:, 0, 0] + left_delta[:, 2, 2]).abs()
    right_yaw = torch.atan2(right_delta[:, 0, 2] - right_delta[:, 2, 0], right_delta[:, 0, 0] + right_delta[:, 2, 2]).abs()
    angular = torch.stack((left_yaw, right_yaw), dim=-1) * float(fps)
    linear_selected = linear.gather(-1, planted.unsqueeze(-1)).squeeze(-1)
    angular_selected = angular.gather(-1, planted.unsqueeze(-1)).squeeze(-1)
    return linear_selected, angular_selected


def compact_slide_yaw_selected(
    cur_pos: torch.Tensor,
    cur_rot: torch.Tensor,
    next_pos: torch.Tensor,
    next_rot: torch.Tensor,
    fps: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    linear, angular, _planted = compact_slide_yaw_selected_with_planted(cur_pos, cur_rot, next_pos, next_rot, fps)
    return linear, angular


def compact_slide_yaw_selected_with_planted(
    cur_pos: torch.Tensor,
    cur_rot: torch.Tensor,
    next_pos: torch.Tensor,
    next_rot: torch.Tensor,
    fps: float,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    cur_points = cur_pos.reshape(cur_pos.shape[0], 2, 2, 3)
    linear = compact_foot_slide_speeds(cur_pos, next_pos, fps)
    planted = cur_points[..., 1].amin(dim=-1).argmin(dim=-1)

    delta = cur_rot.transpose(-1, -2) @ next_rot
    yaw_delta = torch.atan2(delta[:, :, 0, 2] - delta[:, :, 2, 0], delta[:, :, 0, 0] + delta[:, :, 2, 2])
    angular_parts = yaw_delta.abs() * float(fps)
    angular_left = torch.maximum(angular_parts[:, 0], angular_parts[:, 1])
    angular_right = torch.maximum(angular_parts[:, 2], angular_parts[:, 3])
    angular = torch.stack((angular_left, angular_right), dim=-1)
    return (
        linear.gather(-1, planted.unsqueeze(-1)).squeeze(-1),
        angular.gather(-1, planted.unsqueeze(-1)).squeeze(-1),
        planted,
    )


@torch.no_grad()
def clip_reference_values(
    clip: tl.MotionClip,
    cfg: tl.TrainConfig,
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    if clip.cyclic_animation:
        end = int(clip.cyclic_period) - 1
    else:
        end = int(clip.T) - ctl.transition_feature_horizon(cfg) - 1
    if end < 1:
        empty_i = torch.empty((0,), dtype=torch.long, device=device)
        empty_f = torch.empty((0, 3), dtype=torch.float32, device=device)
        empty_v = torch.empty((0,), dtype=torch.float32, device=device)
        empty_h = torch.empty((0, 2), dtype=torch.float32, device=device)
        return empty_i, empty_f, empty_v, empty_v, empty_i, empty_h, empty_h
    idx = torch.arange(1, end + 1, dtype=torch.long, device=device)
    tensors = clip.tensors(device)
    cur_pos = tensors["global_pos"].index_select(0, idx)
    cur_rot = tensors["global_rot"].index_select(0, idx)
    next_pos = tensors["global_pos"].index_select(0, idx + 1)
    next_rot = tensors["global_rot"].index_select(0, idx + 1)
    foot_indices = tuple(int(clip.body_names.index(name)) for name in ("foot_l", "foot_r"))
    toe_indices = tuple(int(clip.body_names.index(name)) for name in ("ball_l", "ball_r"))
    order = (foot_indices[0], toe_indices[0], foot_indices[1], toe_indices[1])
    slide_reference = compact_foot_slide_speeds(cur_pos[:, order], next_pos[:, order], clip.fps)
    yaw_reference = compact_foot_yaw_speeds(cur_rot[:, order], next_rot[:, order], clip.fps)
    planted = compact_planted_side(cur_pos[:, order])
    height_reference = compact_foot_heights(next_pos[:, order], next_rot[:, order])
    height_speed = compact_foot_slide_speeds(cur_pos[:, order], next_pos[:, order], clip.fps)
    features = root_situation_feature(clip, idx, cfg, device)
    return idx, features, slide_reference, yaw_reference, planted, height_reference, height_speed


def _cache_key(
    clips: list[tl.MotionClip],
    cfg: tl.TrainConfig,
    env_cfg: ExcessEnvelopeConfig,
) -> str:
    effective_knn = max(int(env_cfg.knn), MIN_PERCENTILE_KNN)
    payload = {
        "version": CACHE_VERSION,
        "future_window": int(cfg.future_window),
        "position_unit_scale": float(cfg.position_unit_scale),
        "margin": float(env_cfg.margin),
        "knn": int(env_cfg.knn),
        "effective_knn": int(effective_knn),
        "upper_percentile": float(ENVELOPE_UPPER_PERCENTILE),
        "lower_percentile": float(ENVELOPE_LOWER_PERCENTILE),
        "foot_height_feature_scale": float(FOOT_HEIGHT_FEATURE_SCALE),
        "pose_representation": str(cfg.pose_representation),
        "body_mode": tl.normalized_body_mode(getattr(cfg, "body_mode", tl.BODY_MODE_LOWER)),
        "ik_schema_version": int(tl.IK_SCHEMA_VERSION) if tl.uses_ik_markers(cfg.pose_representation) else None,
        "output_reference_root": tl.OUTPUT_REFERENCE_ROOT,
        "output_prediction_mode": tl.normalized_output_prediction_mode(),
        "situation_feature": SITUATION_FEATURE_GLOBAL_P95,
        "bound_lookup": BOUND_LOOKUP_GLOBAL_P95,
        "clips": [
            {
                "path": str(clip.path.resolve()),
                "mtime_ns": int(clip.path.stat().st_mtime_ns),
                "size": int(clip.path.stat().st_size),
                "cyclic": bool(clip.cyclic_animation),
                "period": int(clip.cyclic_period),
            }
            for clip in clips
        ],
    }
    text = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]


def _metadata_effective_knn(metadata: dict[str, float | int | str], n_sources: int) -> int:
    requested = int(metadata.get("effective_knn", metadata.get("knn", MIN_PERCENTILE_KNN)))
    requested = max(1, requested)
    return max(1, min(requested, int(n_sources)))


def _percentile_rank(k: int, percentile: float) -> int:
    return max(1, min(int(k), int(math.ceil(float(percentile) * float(k)))))


def _percentile_from_nearest(values: torch.Tensor, percentile: float) -> torch.Tensor:
    k = int(values.shape[-1])
    rank = _percentile_rank(k, percentile)
    return torch.topk(values, k=rank, largest=False, dim=-1).values[..., -1]


@torch.no_grad()
def _animation_upper_bounds(
    envelope: dict[str, torch.Tensor | dict[str, float | int | str]],
    features: torch.Tensor,
    clip_ids: torch.Tensor,
    side_index: torch.Tensor | None = None,
    heights: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    metadata = envelope["metadata"]  # type: ignore[assignment]
    assert isinstance(metadata, dict)
    if (
        metadata.get("bound_lookup") == BOUND_LOOKUP_GLOBAL_P95
        and heights is not None
        and "source_features" in envelope
        and "source_height_m" in envelope
    ):
        source_features = envelope["source_features"].to(device=features.device, dtype=features.dtype)  # type: ignore[union-attr]
        source_linear = envelope["source_linear_mps"].to(device=features.device, dtype=features.dtype)  # type: ignore[union-attr]
        source_angular = envelope["source_angular_radps"].to(device=features.device, dtype=features.dtype)  # type: ignore[union-attr]
        source_height = envelope["source_height_m"].to(device=features.device, dtype=features.dtype)  # type: ignore[union-attr]
        heights = heights.to(device=features.device, dtype=features.dtype)
        height_scale = float(metadata.get("foot_height_feature_scale", FOOT_HEIGHT_FEATURE_SCALE))
        k = _metadata_effective_knn(metadata, int(source_features.shape[0]))
        linear_parts: list[torch.Tensor] = []
        angular_parts: list[torch.Tensor] = []
        for side in (0, 1):
            query = torch.cat((features, heights[:, side : side + 1] * height_scale), dim=-1)
            source_query = torch.cat((source_features, source_height[:, side : side + 1] * height_scale), dim=-1)
            dist = (source_query.unsqueeze(0) - query[:, None, :]).square().sum(dim=-1)
            nearest = torch.topk(dist, k=k, largest=False, dim=-1).indices
            source_rows = nearest.reshape(-1)
            row_count = int(nearest.shape[0])
            values_shape = (row_count, k)
            linear_values = source_linear[:, side].index_select(0, source_rows).reshape(values_shape)
            angular_values = source_angular[:, side].index_select(0, source_rows).reshape(values_shape)
            linear_parts.append(_percentile_from_nearest(linear_values, ENVELOPE_UPPER_PERCENTILE))
            angular_parts.append(_percentile_from_nearest(angular_values, ENVELOPE_UPPER_PERCENTILE))
        linear_bounds = torch.stack(linear_parts, dim=-1)
        angular_bounds = torch.stack(angular_parts, dim=-1)
        if side_index is not None:
            side_index = side_index.to(device=features.device, dtype=torch.long).clamp(0, int(linear_bounds.shape[-1]) - 1)
            linear_bounds = linear_bounds.gather(-1, side_index.reshape(-1, 1)).squeeze(-1)
            angular_bounds = angular_bounds.gather(-1, side_index.reshape(-1, 1)).squeeze(-1)
        return linear_bounds, angular_bounds

    clip_features = envelope["clip_source_features"].index_select(0, clip_ids)  # type: ignore[union-attr]
    clip_linear = envelope["clip_source_linear_mps"].index_select(0, clip_ids)  # type: ignore[union-attr]
    clip_angular = envelope["clip_source_angular_radps"].index_select(0, clip_ids)  # type: ignore[union-attr]
    clip_counts = envelope["clip_source_counts"].index_select(0, clip_ids)  # type: ignore[union-attr]
    n_sources = int(clip_features.shape[1])
    if "clip_source_row_index" in envelope:
        source_rows = envelope["clip_source_row_index"]  # type: ignore[assignment]
    else:
        source_rows = torch.arange(n_sources, dtype=torch.long, device=features.device).reshape(1, n_sources)
    valid = source_rows < clip_counts.reshape(-1, 1)
    legacy_selected = clip_linear.ndim == 2
    if legacy_selected and side_index is not None and "clip_source_planted_side" in envelope:
        clip_planted = envelope["clip_source_planted_side"].index_select(0, clip_ids)  # type: ignore[union-attr]
        side_valid = valid & (clip_planted == side_index.reshape(-1, 1))
        valid = torch.where(side_valid.any(dim=-1, keepdim=True), side_valid, valid)
    dist = (clip_features - features[:, None, :]).square().sum(dim=-1)
    dist = dist.masked_fill(~valid, torch.inf)
    k = min(int(metadata.get("knn", 32)), n_sources)
    nearest = torch.topk(dist, k=k, largest=False, dim=-1).indices
    if legacy_selected:
        clip_linear = clip_linear.masked_fill(~valid, -torch.inf)
        clip_angular = clip_angular.masked_fill(~valid, -torch.inf)
        return clip_linear.gather(1, nearest).amax(dim=-1), clip_angular.gather(1, nearest).amax(dim=-1)
    linear_valid = clip_linear.masked_fill(~valid.unsqueeze(-1), -torch.inf)
    angular_valid = clip_angular.masked_fill(~valid.unsqueeze(-1), -torch.inf)
    nearest_sides = nearest.unsqueeze(-1).expand(-1, -1, int(clip_linear.shape[-1]))
    linear_bounds = linear_valid.gather(1, nearest_sides).amax(dim=1)
    angular_bounds = angular_valid.gather(1, nearest_sides).amax(dim=1)
    if side_index is not None:
        side_index = side_index.to(device=features.device, dtype=torch.long).clamp(0, int(linear_bounds.shape[-1]) - 1)
        linear_bounds = linear_bounds.gather(-1, side_index.reshape(-1, 1)).squeeze(-1)
        angular_bounds = angular_bounds.gather(-1, side_index.reshape(-1, 1)).squeeze(-1)
    return linear_bounds, angular_bounds


@torch.no_grad()
def _animation_height_bounds(
    envelope: dict[str, torch.Tensor | dict[str, float | int | str]],
    features: torch.Tensor,
    speeds: torch.Tensor,
    clip_ids: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    metadata = envelope["metadata"]  # type: ignore[assignment]
    assert isinstance(metadata, dict)
    if (
        metadata.get("bound_lookup") == BOUND_LOOKUP_GLOBAL_P95
        and "source_features" in envelope
        and "source_height_lower_m" in envelope
        and "source_height_upper_m" in envelope
        and "source_height_speed_mps" in envelope
    ):
        source_features = envelope["source_features"].to(device=features.device, dtype=features.dtype)  # type: ignore[union-attr]
        source_height_lower = envelope["source_height_lower_m"].to(device=features.device, dtype=features.dtype)  # type: ignore[union-attr]
        source_height_upper = envelope["source_height_upper_m"].to(device=features.device, dtype=features.dtype)  # type: ignore[union-attr]
        source_height_speed = envelope["source_height_speed_mps"].to(device=features.device, dtype=features.dtype)  # type: ignore[union-attr]
        speeds = speeds.to(device=features.device, dtype=features.dtype)
        k = _metadata_effective_knn(metadata, int(source_features.shape[0]))
        margin = float(metadata.get("margin", 1.05))
        lower_parts: list[torch.Tensor] = []
        upper_parts: list[torch.Tensor] = []
        for side in (0, 1):
            query = torch.cat((features, speeds[:, side : side + 1]), dim=-1)
            source_query = torch.cat((source_features, source_height_speed[:, side : side + 1]), dim=-1)
            dist = (source_query.unsqueeze(0) - query[:, None, :]).square().sum(dim=-1)
            nearest = torch.topk(dist, k=k, largest=False, dim=-1).indices
            source_rows = nearest.reshape(-1)
            row_count = int(nearest.shape[0])
            values_shape = (row_count, k)
            lower_values = source_height_lower[:, side].index_select(0, source_rows).reshape(values_shape)
            upper_values = source_height_upper[:, side].index_select(0, source_rows).reshape(values_shape)
            raw_lower = _percentile_from_nearest(lower_values, ENVELOPE_LOWER_PERCENTILE)
            raw_upper = _percentile_from_nearest(upper_values, ENVELOPE_UPPER_PERCENTILE)
            lower_parts.append(height_lower_margin(raw_lower, margin))
            upper_parts.append(height_upper_margin(raw_upper, margin))
        return torch.stack(lower_parts, dim=-1), torch.stack(upper_parts, dim=-1)

    clip_features = envelope["clip_source_features"].index_select(0, clip_ids)  # type: ignore[union-attr]
    clip_height_lower = envelope["clip_source_height_lower_m"].index_select(0, clip_ids)  # type: ignore[union-attr]
    clip_height_upper = envelope["clip_source_height_upper_m"].index_select(0, clip_ids)  # type: ignore[union-attr]
    clip_height_speed = envelope["clip_source_height_speed_mps"].index_select(0, clip_ids)  # type: ignore[union-attr]
    clip_counts = envelope["clip_source_counts"].index_select(0, clip_ids)  # type: ignore[union-attr]
    n_sources = int(clip_features.shape[1])
    if "clip_source_row_index" in envelope:
        source_rows = envelope["clip_source_row_index"]  # type: ignore[assignment]
    else:
        source_rows = torch.arange(n_sources, dtype=torch.long, device=features.device).reshape(1, n_sources)
    valid = source_rows < clip_counts.reshape(-1, 1)
    k = min(int(metadata.get("knn", 32)), n_sources)
    margin = float(metadata.get("margin", 1.05))
    lower_parts: list[torch.Tensor] = []
    upper_parts: list[torch.Tensor] = []
    for side in (0, 1):
        side_features = torch.cat((features, speeds[:, side : side + 1]), dim=-1)
        clip_side_features = torch.cat((clip_features, clip_height_speed[:, :, side : side + 1]), dim=-1)
        dist = (clip_side_features - side_features[:, None, :]).square().sum(dim=-1)
        dist = dist.masked_fill(~valid, torch.inf)
        nearest = torch.topk(dist, k=k, largest=False, dim=-1).indices
        lower_values = clip_height_lower[:, :, side].masked_fill(~valid, torch.inf)
        upper_values = clip_height_upper[:, :, side].masked_fill(~valid, -torch.inf)
        raw_lower = lower_values.gather(1, nearest).amin(dim=-1)
        raw_upper = upper_values.gather(1, nearest).amax(dim=-1)
        lower_parts.append(height_lower_margin(raw_lower, margin))
        upper_parts.append(height_upper_margin(raw_upper, margin))
    return torch.stack(lower_parts, dim=-1), torch.stack(upper_parts, dim=-1)


@torch.no_grad()
def _expand_exact_feature_ties(
    features: torch.Tensor,
    values: torch.Tensor,
    planted: torch.Tensor,
    eps: float = 1e-7,
) -> torch.Tensor:
    if int(features.shape[0]) <= 1:
        return values
    out = values.clone()
    if values.ndim > 1:
        same = (features[:, None, :] - features[None, :, :]).abs().amax(dim=-1) <= float(eps)
        tied_max = (
            values.unsqueeze(0)
            .expand(same.shape[0], -1, values.shape[-1])
            .masked_fill(~same.unsqueeze(-1), -torch.inf)
            .amax(dim=1)
        )
        return torch.where(torch.isfinite(tied_max), tied_max, out)
    for side in (0, 1):
        rows = (planted == side).nonzero(as_tuple=False).flatten()
        if rows.numel() <= 1:
            continue
        side_features = features.index_select(0, rows)
        side_values = values.index_select(0, rows)
        same = (side_features[:, None, :] - side_features[None, :, :]).abs().amax(dim=-1) <= float(eps)
        tied_max = side_values.reshape(1, -1).expand_as(same).masked_fill(~same, -torch.inf).amax(dim=-1)
        out[rows] = tied_max
    return out


@torch.no_grad()
def _expand_exact_feature_ties_min(
    features: torch.Tensor,
    values: torch.Tensor,
    eps: float = 1e-7,
) -> torch.Tensor:
    if int(features.shape[0]) <= 1:
        return values
    out = values.clone()
    same = (features[:, None, :] - features[None, :, :]).abs().amax(dim=-1) <= float(eps)
    if values.ndim == 1:
        tied_min = values.reshape(1, -1).expand_as(same).masked_fill(~same, torch.inf).amin(dim=-1)
    else:
        tied_min = values.unsqueeze(0).expand(same.shape[0], -1, values.shape[-1]).masked_fill(~same.unsqueeze(-1), torch.inf).amin(dim=1)
    return torch.where(torch.isfinite(tied_min), tied_min, out)


@torch.no_grad()
def _expand_height_ties(
    features: torch.Tensor,
    speeds: torch.Tensor,
    values: torch.Tensor,
    eps: float = 1e-7,
) -> tuple[torch.Tensor, torch.Tensor]:
    if int(features.shape[0]) <= 1:
        return values, values
    lower = values.clone()
    upper = values.clone()
    for side in (0, 1):
        side_features = torch.cat((features, speeds[:, side : side + 1]), dim=-1)
        same = (side_features[:, None, :] - side_features[None, :, :]).abs().amax(dim=-1) <= float(eps)
        side_values = values[:, side]
        tied_min = side_values.reshape(1, -1).expand_as(same).masked_fill(~same, torch.inf).amin(dim=-1)
        tied_max = side_values.reshape(1, -1).expand_as(same).masked_fill(~same, -torch.inf).amax(dim=-1)
        lower[:, side] = torch.where(torch.isfinite(tied_min), tied_min, lower[:, side])
        upper[:, side] = torch.where(torch.isfinite(tied_max), tied_max, upper[:, side])
    return lower, upper


@torch.no_grad()
def build_excess_envelope(
    store: ctl.SimpleClipStore,
    env_cfg: ExcessEnvelopeConfig | None = None,
) -> dict[str, torch.Tensor | dict[str, float | int | str]]:
    env_cfg = env_cfg or ExcessEnvelopeConfig()
    ctl.ensure_full_store_clips(store)
    frame_count = int(store.lengths.sum().detach().cpu())
    device = store.device
    flat_features = torch.zeros((frame_count, 3), dtype=torch.float32, device=device)
    flat_root_yaw_bend = torch.zeros((frame_count, 2), dtype=torch.float32, device=device)
    flat_linear = torch.zeros((frame_count, 2), dtype=torch.float32, device=device)
    flat_angular = torch.zeros((frame_count, 2), dtype=torch.float32, device=device)
    flat_height = torch.zeros((frame_count, 2), dtype=torch.float32, device=device)
    flat_height_speed = torch.zeros((frame_count, 2), dtype=torch.float32, device=device)
    flat_planted = torch.full((frame_count,), -1, dtype=torch.long, device=device)
    flat_clip_ids = torch.full((frame_count,), -1, dtype=torch.long, device=device)
    valid_mask = torch.zeros((frame_count,), dtype=torch.bool, device=device)
    clip_features: list[torch.Tensor] = []
    clip_linear_values: list[torch.Tensor] = []
    clip_angular_values: list[torch.Tensor] = []
    clip_height_values: list[torch.Tensor] = []
    clip_height_lower_values: list[torch.Tensor] = []
    clip_height_upper_values: list[torch.Tensor] = []
    clip_height_speed_values: list[torch.Tensor] = []
    clip_planted_values: list[torch.Tensor] = []
    clip_frame_values: list[torch.Tensor] = []
    offsets = store.frame_offsets.detach().cpu().tolist()
    for clip_id, clip in enumerate(store.clips):
        if clip.cyclic_animation:
            root_rows = torch.arange(0, int(clip.cyclic_period), dtype=torch.long, device=device)
            root_idx = root_rows.clone()
            if root_idx.numel() > 0:
                root_idx[0] = int(clip.cyclic_period)
        else:
            max_cur = int(clip.T) - ctl.transition_feature_horizon(store.cfg) - 1
            root_rows = torch.arange(1, max(1, max_cur + 1), dtype=torch.long, device=device) if max_cur >= 1 else torch.empty((0,), dtype=torch.long, device=device)
            root_idx = root_rows
        if root_rows.numel() > 0:
            root_features = root_situation_feature(clip, root_idx, store.cfg, device)[:, :2]
            flat_root_yaw_bend.index_copy_(0, root_rows + int(offsets[clip_id]), root_features)

        idx, features, linear, angular, planted, height, height_speed = clip_reference_values(clip, store.cfg, device)
        if idx.numel() == 0:
            clip_features.append(torch.empty((0, 3), dtype=torch.float32, device=device))
            clip_linear_values.append(torch.empty((0, 2), dtype=torch.float32, device=device))
            clip_angular_values.append(torch.empty((0, 2), dtype=torch.float32, device=device))
            clip_height_values.append(torch.empty((0, 2), dtype=torch.float32, device=device))
            clip_height_lower_values.append(torch.empty((0, 2), dtype=torch.float32, device=device))
            clip_height_upper_values.append(torch.empty((0, 2), dtype=torch.float32, device=device))
            clip_height_speed_values.append(torch.empty((0, 2), dtype=torch.float32, device=device))
            clip_planted_values.append(torch.empty((0,), dtype=torch.long, device=device))
            clip_frame_values.append(torch.empty((0,), dtype=torch.long, device=device))
            continue
        flat = idx + int(offsets[clip_id])
        flat_features.index_copy_(0, flat, features)
        linear = _expand_exact_feature_ties(features, linear, planted)
        angular = _expand_exact_feature_ties(features, angular, planted)
        height_lower, height_upper = _expand_height_ties(features, height_speed, height)
        flat_linear.index_copy_(0, flat, linear)
        flat_angular.index_copy_(0, flat, angular)
        flat_height.index_copy_(0, flat, height)
        flat_height_speed.index_copy_(0, flat, height_speed)
        flat_planted.index_copy_(0, flat, planted)
        flat_clip_ids.index_fill_(0, flat, int(clip_id))
        valid_mask.index_fill_(0, flat, True)
        clip_features.append(features)
        clip_linear_values.append(linear)
        clip_angular_values.append(angular)
        clip_height_values.append(height)
        clip_height_lower_values.append(height_lower)
        clip_height_upper_values.append(height_upper)
        clip_height_speed_values.append(height_speed)
        clip_planted_values.append(planted)
        clip_frame_values.append(idx)
    valid_clip_features = [features for features in clip_features if features.numel() > 0]
    if not valid_clip_features:
        raise ValueError("excess envelope could not find any valid clip transitions")

    source_features = torch.cat([features for features in clip_features if features.numel() > 0], dim=0)
    real_linear = torch.cat([linear for linear in clip_linear_values if linear.numel() > 0], dim=0)
    real_angular = torch.cat([angular for angular in clip_angular_values if angular.numel() > 0], dim=0)
    real_height = torch.cat([height for height in clip_height_values if height.numel() > 0], dim=0)
    source_height_lower = torch.cat([height for height in clip_height_lower_values if height.numel() > 0], dim=0)
    source_height_upper = torch.cat([height for height in clip_height_upper_values if height.numel() > 0], dim=0)
    source_height_speed = torch.cat([speed for speed in clip_height_speed_values if speed.numel() > 0], dim=0)
    source_clip_ids = torch.cat(
        [
            torch.full((int(features.shape[0]),), int(clip_id), dtype=torch.long, device=device)
            for clip_id, features in enumerate(clip_features)
            if features.numel() > 0
        ],
        dim=0,
    )
    source_frame_indices = torch.cat([frames for frames in clip_frame_values if frames.numel() > 0], dim=0)
    effective_knn = max(int(env_cfg.knn), MIN_PERCENTILE_KNN)
    source_transition_count = sum(int(features.shape[0]) for features in clip_features)
    max_clip_rows = max(int(features.shape[0]) for features in clip_features)
    clip_count = len(store.clips)
    per_clip_features = torch.zeros((clip_count, max_clip_rows, 3), dtype=torch.float32, device=device)
    per_clip_linear = torch.zeros((clip_count, max_clip_rows, 2), dtype=torch.float32, device=device)
    per_clip_angular = torch.zeros((clip_count, max_clip_rows, 2), dtype=torch.float32, device=device)
    per_clip_height = torch.zeros((clip_count, max_clip_rows, 2), dtype=torch.float32, device=device)
    per_clip_height_lower = torch.zeros((clip_count, max_clip_rows, 2), dtype=torch.float32, device=device)
    per_clip_height_upper = torch.zeros((clip_count, max_clip_rows, 2), dtype=torch.float32, device=device)
    per_clip_height_speed = torch.zeros((clip_count, max_clip_rows, 2), dtype=torch.float32, device=device)
    per_clip_planted = torch.full((clip_count, max_clip_rows), -1, dtype=torch.long, device=device)
    per_clip_counts = torch.zeros((clip_count,), dtype=torch.long, device=device)
    for clip_id, (features, linear, angular, height, height_lower, height_upper, height_speed, planted) in enumerate(
        zip(
            clip_features,
            clip_linear_values,
            clip_angular_values,
            clip_height_values,
            clip_height_lower_values,
            clip_height_upper_values,
            clip_height_speed_values,
            clip_planted_values,
        )
    ):
        count = int(features.shape[0])
        per_clip_counts[clip_id] = count
        if count:
            per_clip_features[clip_id, :count] = features
            per_clip_linear[clip_id, :count] = linear
            per_clip_angular[clip_id, :count] = angular
            per_clip_height[clip_id, :count] = height
            per_clip_height_lower[clip_id, :count] = height_lower
            per_clip_height_upper[clip_id, :count] = height_upper
            per_clip_height_speed[clip_id, :count] = height_speed
            per_clip_planted[clip_id, :count] = planted
    return {
        "groundtruth_linear_mps": flat_linear,
        "groundtruth_angular_radps": flat_angular,
        "groundtruth_height_m": flat_height,
        "groundtruth_height_speed_mps": flat_height_speed,
        "groundtruth_planted_side": flat_planted,
        "features": flat_features,
        "root_yaw_bend": flat_root_yaw_bend,
        "frame_clip_ids": flat_clip_ids,
        "source_features": source_features,
        "source_linear_mps": real_linear,
        "source_angular_radps": real_angular,
        "source_height_m": real_height,
        "source_height_lower_m": source_height_lower,
        "source_height_upper_m": source_height_upper,
        "source_height_speed_mps": source_height_speed,
        "source_clip_ids": source_clip_ids,
        "source_frame_indices": source_frame_indices,
        "clip_source_features": per_clip_features,
        "clip_source_linear_mps": per_clip_linear,
        "clip_source_angular_radps": per_clip_angular,
        "clip_source_height_m": per_clip_height,
        "clip_source_height_lower_m": per_clip_height_lower,
        "clip_source_height_upper_m": per_clip_height_upper,
        "clip_source_height_speed_mps": per_clip_height_speed,
        "clip_source_planted_side": per_clip_planted,
        "clip_source_counts": per_clip_counts,
        "clip_source_row_index": torch.arange(max_clip_rows, dtype=torch.long, device=device).reshape(1, max_clip_rows),
        "valid_mask": valid_mask,
        "metadata": {
            "source_transitions": int(source_transition_count),
            "target_transitions": int(valid_mask.sum().item()),
            "margin": float(env_cfg.margin),
            "knn": int(env_cfg.knn),
            "effective_knn": int(effective_knn),
            "upper_percentile": float(ENVELOPE_UPPER_PERCENTILE),
            "lower_percentile": float(ENVELOPE_LOWER_PERCENTILE),
            "foot_height_feature_scale": float(FOOT_HEIGHT_FEATURE_SCALE),
            "pose_representation": str(store.cfg.pose_representation),
            "body_mode": tl.normalized_body_mode(getattr(store.cfg, "body_mode", tl.BODY_MODE_LOWER)),
            "ik_schema_version": int(tl.IK_SCHEMA_VERSION) if tl.uses_ik_markers(store.cfg.pose_representation) else None,
            "output_reference_root": tl.OUTPUT_REFERENCE_ROOT,
            "output_prediction_mode": tl.normalized_output_prediction_mode(),
            "max_real_linear_mps": float(real_linear.max().detach().cpu()),
            "max_real_angular_radps": float(real_angular.max().detach().cpu()),
            "min_real_height_m": float(real_height.min().detach().cpu()),
            "max_real_height_m": float(real_height.max().detach().cpu()),
            "lookup_scope": "global",
            "situation_feature": SITUATION_FEATURE_GLOBAL_P95,
            "height_definition": "min of foot-bone sole proxy and toe-bone sole proxy; foot proxy subtracts local ankle-to-ball vertical plus toe sole offset",
            "bound_lookup": BOUND_LOOKUP_GLOBAL_P95,
            "cache_version": CACHE_VERSION,
            "max_clip_source_rows": int(max_clip_rows),
            "clip_paths": [str(clip.path.resolve()) for clip in store.clips],
            "body_names": list(store.prototype.body_names),
        },
    }


def load_or_build_excess_envelope(
    store: ctl.SimpleClipStore,
    env_cfg: ExcessEnvelopeConfig | None = None,
) -> dict[str, torch.Tensor | dict[str, float | int | str]]:
    env_cfg = env_cfg or ExcessEnvelopeConfig()
    fast_store_key = getattr(store, "store_cache_key", None)
    fast_memory_key = None
    if fast_store_key is not None:
        fast_memory_key = (
            CACHE_VERSION,
            repr(fast_store_key),
            str(store.device),
            float(env_cfg.margin),
            int(env_cfg.knn),
        )
        cached_fast = _ENVELOPE_FAST_MEMORY_CACHE.get(fast_memory_key)
        if cached_fast is not None:
            return cached_fast
    cache_dir = (PROJECT_ROOT / env_cfg.cache_dir).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = _cache_key(store.clips, store.cfg, env_cfg)
    memory_key = (key, str(store.device))
    cached_memory = _ENVELOPE_MEMORY_CACHE.get(memory_key)
    if cached_memory is not None:
        if fast_memory_key is not None:
            _ENVELOPE_FAST_MEMORY_CACHE[fast_memory_key] = cached_memory
        return cached_memory
    cache_path = cache_dir / f"ik_excess_envelope_{key}.pt"
    if cache_path.exists():
        cached = torch.load(cache_path, map_location=store.device, weights_only=False)
        for name, value in list(cached.items()):
            if isinstance(value, torch.Tensor):
                cached[name] = value.to(store.device)
        cached["metadata"]["cache_path"] = str(cache_path)
        cached["metadata"]["cache_hit"] = 1
        _ENVELOPE_MEMORY_CACHE[memory_key] = cached
        if fast_memory_key is not None:
            _ENVELOPE_FAST_MEMORY_CACHE[fast_memory_key] = cached
        return cached
    built = build_excess_envelope(store, env_cfg)
    torch.save(
        {name: value.detach().cpu() if isinstance(value, torch.Tensor) else value for name, value in built.items()},
        cache_path,
    )
    built["metadata"]["cache_path"] = str(cache_path)
    built["metadata"]["cache_hit"] = 0
    _ENVELOPE_MEMORY_CACHE[memory_key] = built
    if fast_memory_key is not None:
        _ENVELOPE_FAST_MEMORY_CACHE[fast_memory_key] = built
    return built


def envelope_excess_rows(
    store: ctl.SimpleClipStore,
    envelope: dict[str, torch.Tensor | dict[str, float | int | str]],
    cur_pos: torch.Tensor,
    cur_rot: torch.Tensor,
    next_pos: torch.Tensor,
    next_rot: torch.Tensor,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    foot_indices = tuple(int(store.prototype.body_names.index(name)) for name in ("foot_l", "foot_r"))
    toe_indices = tuple(int(store.prototype.body_names.index(name)) for name in ("ball_l", "ball_r"))
    order = (foot_indices[0], toe_indices[0], foot_indices[1], toe_indices[1])
    diag = envelope_diagnostics_ik_state_rows(
        store,
        envelope,
        cur_pos[:, order],
        cur_rot[:, order],
        next_pos[:, order],
        next_rot[:, order],
        clip_ids,
        cur_idx,
        runtime_situation_feature(store, cur_pos, clip_ids, cur_idx).detach(),
    )
    return diag["linear_excess_per_side_mps"].mean(dim=-1), diag["angular_excess_per_side_radps"].mean(dim=-1)


def envelope_excess_ik_state_rows(
    store: ctl.SimpleClipStore,
    envelope: dict[str, torch.Tensor | dict[str, float | int | str]],
    cur_pos: torch.Tensor,
    cur_rot: torch.Tensor,
    next_pos: torch.Tensor,
    next_rot: torch.Tensor,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    diag = envelope_diagnostics_ik_state_rows(
        store, envelope, cur_pos, cur_rot, next_pos, next_rot, clip_ids, cur_idx
    )
    return diag["linear_excess_per_side_mps"].mean(dim=-1), diag["angular_excess_per_side_radps"].mean(dim=-1)


def envelope_feature_ik_state_rows(
    store: ctl.SimpleClipStore,
    envelope: dict[str, torch.Tensor | dict[str, float | int | str]],
    cur_pos: torch.Tensor,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
) -> torch.Tensor:
    if "root_yaw_bend" in envelope:
        frame = store.frame_index(clip_ids, cur_idx)
        root_yaw_bend = envelope["root_yaw_bend"].index_select(0, frame)  # type: ignore[union-attr]
        foot_dx = cur_pos[:, 0, 0] - cur_pos[:, 2, 0]
        foot_dz = cur_pos[:, 0, 2] - cur_pos[:, 2, 2]
        foot_distance = torch.sqrt(foot_dx.square() + foot_dz.square() + 1e-12).unsqueeze(-1)
        return torch.cat((root_yaw_bend, foot_distance), dim=-1).detach()
    return runtime_situation_feature_from_feet(store, cur_pos, clip_ids, cur_idx).detach()


def compact_foot_yaw_speeds(
    cur_rot: torch.Tensor,
    next_rot: torch.Tensor,
    fps: float,
) -> torch.Tensor:
    delta = cur_rot.transpose(-1, -2) @ next_rot
    yaw_delta = torch.atan2(delta[:, :, 0, 2] - delta[:, :, 2, 0], delta[:, :, 0, 0] + delta[:, :, 2, 2]).abs()
    angular_parts = yaw_delta * float(fps)
    return torch.stack(
        (
            torch.maximum(angular_parts[:, 0], angular_parts[:, 1]),
            torch.maximum(angular_parts[:, 2], angular_parts[:, 3]),
        ),
        dim=-1,
    )


def compact_planted_side(cur_pos: torch.Tensor) -> torch.Tensor:
    cur_points = cur_pos.reshape(cur_pos.shape[0], 2, 2, 3)
    return cur_points[..., 1].amin(dim=-1).argmin(dim=-1)


def envelope_diagnostics_ik_state_rows(
    store: ctl.SimpleClipStore,
    envelope: dict[str, torch.Tensor | dict[str, float | int | str]],
    cur_pos: torch.Tensor,
    cur_rot: torch.Tensor | None,
    next_pos: torch.Tensor,
    next_rot: torch.Tensor,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
    features: torch.Tensor | None = None,
) -> dict[str, torch.Tensor]:
    features = features if features is not None else envelope_feature_ik_state_rows(store, envelope, cur_pos, clip_ids, cur_idx)
    features = features.to(device=cur_pos.device, dtype=cur_pos.dtype).detach()
    clip_ids = clip_ids.to(device=cur_pos.device, dtype=torch.long)
    metadata = envelope["metadata"]  # type: ignore[assignment]
    assert isinstance(metadata, dict)
    margin = float(metadata.get("margin", 1.05))
    if cur_rot is None:
        cur_rot = next_rot

    linear_speeds = compact_foot_slide_speeds(cur_pos, next_pos, store.prototype.fps)
    angular_speeds = compact_foot_yaw_speeds(cur_rot, next_rot, store.prototype.fps)
    heights = compact_foot_heights(next_pos, next_rot)
    planted = compact_planted_side(cur_pos)
    linear_selected = linear_speeds.gather(-1, planted.unsqueeze(-1)).squeeze(-1)
    angular_selected = angular_speeds.gather(-1, planted.unsqueeze(-1)).squeeze(-1)
    linear_bound_per_side, angular_bound_per_side = _animation_upper_bounds(
        envelope, features, clip_ids, None, heights.detach()
    )
    if linear_bound_per_side.ndim == 1:
        linear_bound_per_side = linear_bound_per_side.unsqueeze(-1).expand_as(linear_speeds)
        angular_bound_per_side = angular_bound_per_side.unsqueeze(-1).expand_as(angular_speeds)
    linear_bound_per_side = linear_bound_per_side * margin
    angular_bound_per_side = angular_bound_per_side * margin
    linear_bound = linear_bound_per_side.gather(-1, planted.unsqueeze(-1)).squeeze(-1)
    angular_bound = angular_bound_per_side.gather(-1, planted.unsqueeze(-1)).squeeze(-1)

    height_speeds = compact_foot_slide_speeds(cur_pos, next_pos, store.prototype.fps)
    if "clip_source_height_lower_m" in envelope and "clip_source_height_upper_m" in envelope and "clip_source_height_speed_mps" in envelope:
        height_lower_bound, height_upper_bound = _animation_height_bounds(envelope, features, height_speeds.detach(), clip_ids)
    else:
        height_lower_bound = torch.full_like(heights, -torch.inf)
        height_upper_bound = torch.full_like(heights, torch.inf)

    linear_excess_per_side = F.relu(linear_speeds - linear_bound_per_side)
    angular_excess_per_side = F.relu(angular_speeds - angular_bound_per_side)
    height_low_excess = F.relu(height_lower_bound - heights)
    height_high_excess = F.relu(heights - height_upper_bound)
    return {
        "linear_speed_mps": linear_speeds,
        "angular_speed_radps": angular_speeds,
        "planted_side": planted,
        "linear_selected_mps": linear_selected,
        "angular_selected_radps": angular_selected,
        "linear_bound_mps": linear_bound,
        "angular_bound_radps": angular_bound,
        "linear_bound_per_side_mps": linear_bound_per_side,
        "angular_bound_per_side_radps": angular_bound_per_side,
        "linear_selected_excess_mps": F.relu(linear_selected - linear_bound),
        "angular_selected_excess_radps": F.relu(angular_selected - angular_bound),
        "linear_excess_per_side_mps": linear_excess_per_side,
        "angular_excess_per_side_radps": angular_excess_per_side,
        "height_m": heights,
        "height_speed_mps": height_speeds,
        "height_lower_bound_m": height_lower_bound,
        "height_upper_bound_m": height_upper_bound,
        "height_low_excess_m": height_low_excess,
        "height_high_excess_m": height_high_excess,
        "height_excess_m": height_low_excess + height_high_excess,
    }


def envelope_values_ik_state_rows(
    store: ctl.SimpleClipStore,
    envelope: dict[str, torch.Tensor | dict[str, float | int | str]],
    cur_pos: torch.Tensor,
    cur_rot: torch.Tensor,
    next_pos: torch.Tensor,
    next_rot: torch.Tensor,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    diag = envelope_diagnostics_ik_state_rows(
        store, envelope, cur_pos, cur_rot, next_pos, next_rot, clip_ids, cur_idx
    )
    return (
        diag["linear_selected_mps"],
        diag["angular_selected_radps"],
        diag["linear_bound_mps"],
        diag["angular_bound_radps"],
    )


def envelope_height_values_ik_state_rows(
    store: ctl.SimpleClipStore,
    envelope: dict[str, torch.Tensor | dict[str, float | int | str]],
    cur_pos: torch.Tensor,
    next_pos: torch.Tensor,
    next_rot: torch.Tensor,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    diag = envelope_diagnostics_ik_state_rows(store, envelope, cur_pos, None, next_pos, next_rot, clip_ids, cur_idx)
    return diag["height_m"], diag["height_lower_bound_m"], diag["height_upper_bound_m"]


def envelope_height_excess_ik_state_rows(
    store: ctl.SimpleClipStore,
    envelope: dict[str, torch.Tensor | dict[str, float | int | str]],
    cur_pos: torch.Tensor,
    next_pos: torch.Tensor,
    next_rot: torch.Tensor,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
) -> torch.Tensor:
    heights, lower_bound, upper_bound = envelope_height_values_ik_state_rows(
        store, envelope, cur_pos, next_pos, next_rot, clip_ids, cur_idx
    )
    return F.relu(lower_bound - heights) + F.relu(heights - upper_bound)


def envelope_excess_ik_rows(
    store: ctl.SimpleClipStore,
    envelope: dict[str, torch.Tensor | dict[str, float | int | str]],
    cur_root_pos: torch.Tensor,
    cur_root_rot: torch.Tensor,
    cur_vec: torch.Tensor,
    next_root_pos: torch.Tensor,
    next_root_rot: torch.Tensor,
    next_vec: torch.Tensor,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    cur_pos, cur_rot = ik_foot_toe_state_from_vec(store, cur_root_pos, cur_root_rot, cur_vec)
    output_root_pos = cur_root_pos if tl.output_reference_uses_current_root() else next_root_pos
    output_root_rot = cur_root_rot if tl.output_reference_uses_current_root() else next_root_rot
    next_pos, next_rot = ik_foot_toe_state_from_vec(store, output_root_pos, output_root_rot, next_vec)
    return envelope_excess_ik_state_rows(store, envelope, cur_pos, cur_rot, next_pos, next_rot, clip_ids, cur_idx)


@torch.no_grad()
def groundtruth_sanity(
    store: ctl.SimpleClipStore,
    envelope: dict[str, torch.Tensor | dict[str, float | int | str]],
) -> dict[str, float]:
    metadata = envelope["metadata"]  # type: ignore[assignment]
    assert isinstance(metadata, dict)
    cache_path = str(metadata.get("cache_path", ""))
    sanity_key = (cache_path, str(store.device))
    if cache_path:
        cached = _GROUNDTRUTH_SANITY_CACHE.get(sanity_key)
        if cached is not None:
            return dict(cached)
        sidecar_cached = _load_groundtruth_sanity_sidecar(cache_path, store.device)
        if sidecar_cached is not None:
            _GROUNDTRUTH_SANITY_CACHE[sanity_key] = dict(sidecar_cached)
            return dict(sidecar_cached)
    valid = envelope["valid_mask"].bool()  # type: ignore[union-attr]
    linear_gt = envelope["groundtruth_linear_mps"][valid]  # type: ignore[index,union-attr]
    angular_gt = envelope["groundtruth_angular_radps"][valid]  # type: ignore[index,union-attr]
    height_gt = envelope["groundtruth_height_m"][valid]  # type: ignore[index,union-attr]
    height_speed_gt = envelope["groundtruth_height_speed_mps"][valid]  # type: ignore[index,union-attr]
    features = envelope["features"][valid]  # type: ignore[index,union-attr]
    clip_ids = envelope["frame_clip_ids"][valid]  # type: ignore[index,union-attr]
    margin = float(metadata.get("margin", 1.05))
    linear_bound, angular_bound = _animation_upper_bounds(envelope, features, clip_ids, None, height_gt)
    if linear_bound.ndim == 1:
        linear_bound = linear_bound.unsqueeze(-1).expand_as(linear_gt)
        angular_bound = angular_bound.unsqueeze(-1).expand_as(angular_gt)
    linear_bound = linear_bound * margin
    angular_bound = angular_bound * margin
    height_lower_bound, height_upper_bound = _animation_height_bounds(envelope, features, height_speed_gt, clip_ids)
    linear_excess = F.relu(linear_gt - linear_bound)
    angular_excess = F.relu(angular_gt - angular_bound)
    height_low_excess = F.relu(height_lower_bound - height_gt)
    height_high_excess = F.relu(height_gt - height_upper_bound)
    height_excess = height_low_excess + height_high_excess
    result = {
        "gt_linear_excess_mean": float(linear_excess.mean().detach().cpu()),
        "gt_linear_excess_p95": float(torch.quantile(linear_excess, 0.95).detach().cpu()),
        "gt_linear_excess_max": float(linear_excess.max().detach().cpu()),
        "gt_linear_violation_fraction": float((linear_excess > 0.0).float().mean().detach().cpu()),
        "gt_angular_excess_mean": float(angular_excess.mean().detach().cpu()),
        "gt_angular_excess_p95": float(torch.quantile(angular_excess, 0.95).detach().cpu()),
        "gt_angular_excess_max": float(angular_excess.max().detach().cpu()),
        "gt_angular_violation_fraction": float((angular_excess > 0.0).float().mean().detach().cpu()),
        "gt_height_low_excess_mean": float(height_low_excess.mean().detach().cpu()),
        "gt_height_low_excess_p95": float(torch.quantile(height_low_excess.reshape(-1), 0.95).detach().cpu()),
        "gt_height_low_excess_max": float(height_low_excess.max().detach().cpu()),
        "gt_height_low_violation_fraction": float((height_low_excess > 0.0).float().mean().detach().cpu()),
        "gt_height_high_excess_mean": float(height_high_excess.mean().detach().cpu()),
        "gt_height_high_excess_p95": float(torch.quantile(height_high_excess.reshape(-1), 0.95).detach().cpu()),
        "gt_height_high_excess_max": float(height_high_excess.max().detach().cpu()),
        "gt_height_high_violation_fraction": float((height_high_excess > 0.0).float().mean().detach().cpu()),
        "gt_height_excess_mean": float(height_excess.mean().detach().cpu()),
        "gt_height_excess_p95": float(torch.quantile(height_excess.reshape(-1), 0.95).detach().cpu()),
        "gt_height_excess_max": float(height_excess.max().detach().cpu()),
        "gt_height_violation_fraction": float((height_excess > 0.0).float().mean().detach().cpu()),
    }
    if cache_path:
        _GROUNDTRUTH_SANITY_CACHE[sanity_key] = dict(result)
        _save_groundtruth_sanity_sidecar(cache_path, store.device, result)
    return result
