from __future__ import annotations

"""Train upper AE1 with the exact accepted running AE1 recipe.

This deliberately reuses the running AE1 mechanism:

* two consecutive ``controller_input + transition_output`` rows;
* the unchanged :class:`SimpleAutoencoder` bottleneck implementation;
* hidden width 1024, three layers, latent width 128;
* no denoising and no auxiliary losses;
* reconstruction MSE only on the newest transition output.

The upper-specific output is the 171D delta of nineteen actual transforms in
the current root frame: pelvis, upper chain, both hands, and the thighs/calves
resolved by the approved locked-foot IK.  Feet remain input-only because the
frozen lower agent owns them.  The controller is 281 -> 99 (upper 90 + pelvis
9), but AE1 judges the resulting physical 171D transition.
"""

import argparse
import gc
import hashlib
import json
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import torch
from torch.utils.tensorboard import SummaryWriter

try:
    from .bootstrap import PROJECT_ROOT, ensure_paths
    from .naming import checkpoint_path, ik_run_id
    from .train_simple_autoencoder import (
        SimpleAEConfig,
        SimpleAutoencoder,
        equal_group_batch_indices,
        lr_for_step,
    )
    from . import train_upper_pose_autoencoder as upper_data
    from . import upper_pose_pelvis_contract as physical_data
    from . import ik_core as tl
except ImportError:
    from bootstrap import PROJECT_ROOT, ensure_paths
    from naming import checkpoint_path, ik_run_id
    from train_simple_autoencoder import (
        SimpleAEConfig,
        SimpleAutoencoder,
        equal_group_batch_indices,
        lr_for_step,
    )
    import train_upper_pose_autoencoder as upper_data
    import upper_pose_pelvis_contract as physical_data
    import ik_core as tl


ensure_paths()

RUNS_ROOT = PROJECT_ROOT / "training" / "runs"
CACHE_ROOT = RUNS_ROOT / "cache" / "upper_pose_root_simple_ae1"
OMNI_CACHE_VERSION = "upper_pose_pelvis_simple_ae1_rows_v3_omni_reachable_runtime"
FULL_CACHE_VERSION = "upper_pose_pelvis_simple_ae1_rows_v4_full_corpus_runtime"
OMNI_DYNAMIC_SUPPORT_VERSION = "upper_pose_pelvis_gaze_resample_support_v1"
FULL_DYNAMIC_SUPPORT_VERSION = "upper_pose_pelvis_gaze_resample_support_v2_full_corpus"

# These are configured once from CLI before any cache/schema/model work.  The
# defaults preserve every existing accepted checkpoint and caller.
_FULL_CORPUS = False
_STATUE_NEGATIVES = False
_INBETWEEN_NEGATIVES = False
_HAND_LOSS_WEIGHT = 1.0

INPUT_DIM = upper_data.INPUT_DIM
OUTPUT_DIM = physical_data.PHYSICAL_DIM
ROW_DIM = INPUT_DIM + OUTPUT_DIM
WINDOW_FRAMES = 2
WINDOW_DIM = ROW_DIM * WINDOW_FRAMES
NEWEST_OUTPUT_START = ROW_DIM + INPUT_DIM
NEWEST_OUTPUT_END = NEWEST_OUTPUT_START + OUTPUT_DIM
GROUP_NAMES = ("walk_sheathed", "walk_drawn", "run_sheathed", "run_drawn")
GROUP_COUNT = len(GROUP_NAMES)


def cache_version() -> str:
    return FULL_CACHE_VERSION if _FULL_CORPUS else OMNI_CACHE_VERSION


def dynamic_support_version() -> str:
    return (
        FULL_DYNAMIC_SUPPORT_VERSION
        if _FULL_CORPUS
        else OMNI_DYNAMIC_SUPPORT_VERSION
    )


def physical_output_weights(
    device: torch.device | None = None,
    dtype: torch.dtype = torch.float32,
) -> torch.Tensor:
    """Return the checkpoint/runtime-identical relative physical loss weights."""

    result = torch.ones(OUTPUT_DIM, dtype=dtype, device=device)
    for hand in ("hand_l", "hand_r"):
        bone = physical_data.PHYSICAL_BONES.index(hand)
        start = bone * physical_data.TRANSFORM_DIM
        result[start : start + physical_data.TRANSFORM_DIM] = float(
            _HAND_LOSS_WEIGHT
        )
    return result


def weighted_output_mse(
    error: torch.Tensor,
    weights: torch.Tensor,
) -> torch.Tensor:
    """Per-row MSE with declared relative weights and a stable overall scale."""

    return (error.square() * weights).sum(dim=-1) / weights.sum()


def checkpoint_schema() -> dict[str, Any]:
    return {
        "name": "upper_pelvis_physical_controller_io_two_row",
        "mechanism": "running_AE1_simple_autoencoder",
        "total_dim": WINDOW_DIM,
        "window_frames": WINDOW_FRAMES,
        "base_total_dim": ROW_DIM,
        "input_dim": INPUT_DIM,
        "output_dim": OUTPUT_DIM,
        "newest_output_start": NEWEST_OUTPUT_START,
        "newest_output_end": NEWEST_OUTPUT_END,
        "input_segments": upper_data.checkpoint_schema()["input_segments"],
        "output_segments": {
            "physical_transform_delta": [INPUT_DIM, ROW_DIM],
            "pose_bones": list(physical_data.PHYSICAL_BONES),
            "per_bone": "position3_rotation6_in_current_actual_root_frame",
        },
        "loss": (
            f"normalized_weighted_mse_on_newest_{OUTPUT_DIM}_value_output_only"
            + ("_plus_equal_statue_to_clean_correction" if _STATUE_NEGATIVES else "")
        ),
        "scoring_weights": {
            "normalization": "sum_weighted_squared_error_divided_by_sum_weights",
            "default_transform_weight": 1.0,
            "hand_l_transform_weight": float(_HAND_LOSS_WEIGHT),
            "hand_r_transform_weight": float(_HAND_LOSS_WEIGHT),
        },
        "negative_training": (
            "equal clean reconstruction and zero-physical-transition statue-to-clean correction"
            if _STATUE_NEGATIVES
            else "none"
        ),
        "controller_agent_representation": "281_to_99_upper90_plus_pelvis9",
        "feet": "current_and_next_input_only_frozen_by_lower_agent",
        "leg_resolution": "single_direct_unclamped_two_bone_IK_preserving_sampled_pole",
    }


def cache_identity() -> tuple[list[tuple[str, Path, bool]], list[tuple[str, Path, bool]], str]:
    original, drawn, source_fingerprint = upper_data.matched_dataset()
    if not _FULL_CORPUS:
        def selected(spec: tuple[str, Path, bool]) -> bool:
            relative = spec[0]
            return (
                relative.startswith("walk_omni/M_Neutral_Walk_Loop_")
                or relative.startswith("run_omni/M_Neutral_Run_Loop_")
            )
        original = [spec for spec in original if selected(spec)]
        drawn = [spec for spec in drawn if selected(spec)]
        if len(original) != 30 or len(drawn) != 30:
            raise RuntimeError(
                f"Expected 30 walk/run omni clips per mode, got {len(original)} and {len(drawn)}"
            )
    elif len(original) != 465 or len(drawn) != 465:
        raise RuntimeError(
            f"Expected complete matched corpus 465+465, got {len(original)}+{len(drawn)}"
        )
    digest = hashlib.sha256()
    digest.update(cache_version().encode("utf-8"))
    digest.update(source_fingerprint.encode("ascii"))
    digest.update("|".join(physical_data.PHYSICAL_BONES).encode("utf-8"))
    return original, drawn, digest.hexdigest()


@torch.no_grad()
def clip_windows(
    relative: str,
    source: Path,
    cyclic: bool,
    sword: float,
    cfg: tl.TrainConfig,
) -> tuple[torch.Tensor, int]:
    clip = tl.MotionClip(source, cfg, cyclic_animation=cyclic)
    lower_cfg = upper_data.motion_config()
    lower_cfg.body_mode = tl.BODY_MODE_LOWER
    lower_clip = tl.MotionClip(source, lower_cfg, cyclic_animation=cyclic)
    base = upper_data.fk_base_upper_from_clip(clip)
    pelvis = upper_data.pelvis_root_features(clip)
    feet = upper_data.feet_root_features(clip)

    if cyclic:
        current = torch.arange(1, int(clip.cyclic_period) + 1, dtype=torch.long)
    else:
        count = int(clip.T) - int(cfg.future_window)
        current = torch.arange(max(0, count), dtype=torch.long)
    if int(current.numel()) < WINDOW_FRAMES:
        raise RuntimeError(f"clip too short for two-row AE1 window: {source}")

    window_count = int(current.numel()) - 1
    gaze = upper_data.sampled_window_gaze(relative, window_count)
    physical_deltas = physical_data.authored_decoded_two_row_deltas(
        clip, lower_clip, cfg, current[:-1], gaze
    )
    rows: list[torch.Tensor] = []
    for frame_current, physical in zip(
        (current[:-1], current[1:]), physical_deltas
    ):
        controller = upper_data.controller_rows(
            clip,
            cfg,
            frame_current,
            gaze,
            sword,
            base,
            pelvis,
            feet,
        )
        row = torch.cat(
            (
                controller[:, :INPUT_DIM],
                physical,
            ),
            dim=-1,
        )
        if tuple(row.shape) != (window_count, ROW_DIM):
            raise RuntimeError(f"upper root AE1 row mismatch: {tuple(row.shape)}")
        rows.append(row)
    windows = torch.cat(rows, dim=-1).contiguous()
    if tuple(windows.shape) != (window_count, WINDOW_DIM):
        raise RuntimeError(f"upper root AE1 window mismatch: {tuple(windows.shape)}")
    if not bool(torch.isfinite(windows).all()):
        raise RuntimeError(f"non-finite upper root AE1 window from {source}")
    return windows, int((gaze == 0.0).all(dim=-1).sum())


def prepare_windows(
    force_rebuild: bool = False,
) -> tuple[torch.Tensor, torch.Tensor, dict[str, Any], Path]:
    original, drawn, fingerprint = cache_identity()
    version = cache_version()
    path = CACHE_ROOT / f"{version}_{fingerprint[:16]}.pt"
    if path.is_file() and not force_rebuild:
        payload = torch.load(path, map_location="cpu", weights_only=False)
        if payload.get("fingerprint") != fingerprint:
            raise RuntimeError(f"cache fingerprint mismatch: {path}")
        return (
            payload["windows"].float(),
            payload["groups"].long(),
            dict(payload["metadata"]),
            path,
        )

    cfg = upper_data.motion_config()
    chunks: list[torch.Tensor] = []
    group_chunks: list[torch.Tensor] = []
    row_counts = [0] * GROUP_COUNT
    zero_gaze = 0
    started = time.perf_counter()
    processed = 0
    total_clips = len(original) + len(drawn)
    for specs, sword in ((original, -1.0), (drawn, 1.0)):
        for relative, source, cyclic in specs:
            windows, zero_count = clip_windows(
                relative, source, cyclic, sword, cfg
            )
            group = physical_data.group_for(relative, sword)
            chunks.append(windows)
            group_chunks.append(
                torch.full((windows.shape[0],), group, dtype=torch.long)
            )
            row_counts[group] += int(windows.shape[0])
            zero_gaze += zero_count
            processed += 1
            if processed == 1 or processed % 25 == 0 or processed == total_clips:
                print(
                    f"UPPER_ROOT_SIMPLE_AE_BUILD clips={processed}/{total_clips} "
                    f"windows={sum(int(chunk.shape[0]) for chunk in chunks)} "
                    f"elapsed_s={time.perf_counter() - started:.1f}",
                    flush=True,
                )
    windows = torch.cat(chunks, dim=0)
    groups = torch.cat(group_chunks, dim=0)
    metadata: dict[str, Any] = {
        "version": version,
        "fingerprint": fingerprint,
        "window_count": int(windows.shape[0]),
        "window_dim": WINDOW_DIM,
        "group_names": list(GROUP_NAMES),
        "group_window_counts": row_counts,
        "zero_gaze_windows": zero_gaze,
        "zero_gaze_fraction": zero_gaze / float(max(1, windows.shape[0])),
        "original_root": str(upper_data.ORIGINAL_ROOT),
        "drawn_root": str(upper_data.SWORD_ROOT),
    }
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(
        {
            "fingerprint": fingerprint,
            "windows": windows,
            "groups": groups,
            "metadata": metadata,
        },
        temporary,
    )
    os.replace(temporary, path)
    print(
        f"UPPER_ROOT_SIMPLE_AE_CACHE windows={windows.shape[0]} dim={windows.shape[1]} "
        f"groups={row_counts} elapsed_s={time.perf_counter() - started:.1f} path={path}",
        flush=True,
    )
    return windows, groups, metadata, path


@torch.no_grad()
def clip_dynamic_support(
    source: Path,
    cyclic: bool,
    cfg: tl.TrainConfig,
) -> dict[str, torch.Tensor]:
    """Cache only gaze-independent tensors for exact per-draw gaze resampling."""

    full = tl.MotionClip(source, cfg, cyclic_animation=cyclic)
    lower_cfg = upper_data.motion_config()
    lower_cfg.body_mode = tl.BODY_MODE_LOWER
    lower = tl.MotionClip(source, lower_cfg, cyclic_animation=cyclic)
    if cyclic:
        current = torch.arange(1, int(full.cyclic_period) + 1, dtype=torch.long)
        previous = torch.remainder(current[:-1] - 1, int(full.cyclic_period))
    else:
        count = int(full.T) - int(cfg.future_window)
        current = torch.arange(max(0, count), dtype=torch.long)
        previous = (current[:-1] - 1).clamp_min(0)
    first = current[:-1]
    rows = int(first.numel())
    if rows < 1:
        raise RuntimeError(f"clip too short for dynamic gaze support: {source}")

    upper_frames = torch.stack(
        (previous, first, first + 1, first + 2), dim=1
    )
    upper_logical = tl.logical_pose_index(
        full, upper_frames.reshape(-1), torch.device("cpu")
    )
    upper_positions = full.global_pos.index_select(0, upper_logical).reshape(
        rows, 4, full.J, 3
    )
    upper_rotations = full.global_rot.index_select(0, upper_logical).reshape(
        rows, 4, full.J, 3, 3
    )
    upper_root_positions = full.root_pos.index_select(0, upper_logical).reshape(
        rows, 4, 3
    )
    upper_root_headings = full.root_heading_rot.index_select(0, upper_logical).reshape(
        rows, 4, 3, 3
    )

    physical_frames = torch.stack((first, first + 1, first + 2), dim=1)
    physical_flat = physical_frames.reshape(-1)
    physical_logical = tl.logical_pose_index(
        full, physical_flat, torch.device("cpu")
    )
    lower_pose = tl.get_pose_from_clip(lower, physical_flat, torch.device("cpu"))
    lower_vector = tl.pose_target_output(lower_pose)
    root_position, root_rotation, _yaw, heading = tl.root_state(
        full, physical_flat, cfg, torch.device("cpu")
    )
    pelvis = physical_data.root_transform_to_heading(
        lower_vector[:, :9], root_rotation, heading
    )
    base = upper_data.fk_base_upper_from_clip(full).index_select(
        0, physical_logical
    )
    return {
        "upper_positions": upper_positions.contiguous(),
        "upper_rotations": upper_rotations.contiguous(),
        "upper_root_positions": upper_root_positions.contiguous(),
        "upper_root_headings": upper_root_headings.contiguous(),
        "lower_vectors": lower_vector.reshape(rows, 3, -1).contiguous(),
        "pelvis_heading": pelvis.reshape(rows, 3, upper_data.PELVIS_DIM).contiguous(),
        "physical_root_positions": root_position.reshape(rows, 3, 3).contiguous(),
        "physical_root_rotations": root_rotation.reshape(rows, 3, 3, 3).contiguous(),
        "physical_root_headings": heading.reshape(rows, 3, 3, 3).contiguous(),
        "base_upper": base.reshape(rows, 3, upper_data.POSE_DIM).contiguous(),
    }


@torch.no_grad()
def prepare_dynamic_support(
    force_rebuild: bool = False,
) -> tuple[dict[str, torch.Tensor], Path, Path]:
    original, drawn, fingerprint = cache_identity()
    version = dynamic_support_version()
    path = CACHE_ROOT / f"{version}_{fingerprint[:16]}.pt"
    if path.is_file() and not force_rebuild:
        payload = torch.load(path, map_location="cpu", weights_only=False)
        if payload.get("fingerprint") != fingerprint:
            raise RuntimeError(f"dynamic support fingerprint mismatch: {path}")
        return dict(payload["support"]), path, Path(payload["prototype_source"])

    cfg = upper_data.motion_config()
    chunks: dict[str, list[torch.Tensor]] = {}
    prototype_source: Path | None = None
    prototype_names: list[str] | None = None
    started = time.perf_counter()
    processed = 0
    total_clips = len(original) + len(drawn)
    for specs in (original, drawn):
        for _relative, source, cyclic in specs:
            clip = tl.MotionClip(source, cfg, cyclic_animation=cyclic)
            names = list(clip.body_names)
            if prototype_names is None:
                prototype_names = names
                prototype_source = source
            elif names != prototype_names:
                raise RuntimeError(f"dynamic gaze support skeleton mismatch: {source}")
            support = clip_dynamic_support(source, cyclic, cfg)
            for key, value in support.items():
                chunks.setdefault(key, []).append(value)
            processed += 1
            if processed == 1 or processed % 25 == 0 or processed == total_clips:
                print(
                    f"UPPER_ROOT_DYNAMIC_SUPPORT_BUILD clips={processed}/{total_clips} "
                    f"rows={sum(int(value.shape[0]) for value in chunks['upper_positions'])} "
                    f"elapsed_s={time.perf_counter() - started:.1f}",
                    flush=True,
                )
    assert prototype_source is not None
    combined = {key: torch.cat(values, dim=0) for key, values in chunks.items()}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(
        {
            "version": version,
            "fingerprint": fingerprint,
            "prototype_source": str(prototype_source),
            "support": combined,
        },
        temporary,
    )
    os.replace(temporary, path)
    print(
        f"UPPER_ROOT_DYNAMIC_GAZE_SUPPORT rows={next(iter(combined.values())).shape[0]} "
        f"elapsed_s={time.perf_counter() - started:.1f} path={path}",
        flush=True,
    )
    return combined, path, prototype_source


@torch.no_grad()
def sample_rollout_gaze(
    count: int, generator: torch.Generator
) -> torch.Tensor:
    gaze = torch.rand((int(count), 2), generator=generator) * 2.0 - 1.0
    zero = torch.rand((int(count),), generator=generator) < upper_data.GAZE_ZERO_PROBABILITY
    gaze[zero] = 0.0
    return gaze


@torch.no_grad()
def resampled_gaze_upper_states(
    support: dict[str, torch.Tensor],
    selected: torch.Tensor,
    prototype: tl.MotionClip,
    gaze: torch.Tensor,
) -> torch.Tensor:
    """Return the four authored upper poses for one freshly sampled gaze."""

    count = int(selected.numel())
    if tuple(gaze.shape) != (count, 2):
        raise ValueError(f"Expected sampled gaze [{count},2], got {tuple(gaze.shape)}")
    upper_positions = support["upper_positions"].index_select(0, selected)
    upper_rotations = support["upper_rotations"].index_select(0, selected)
    repeated_gaze4 = gaze[:, None, :].expand(count, 4, 2).reshape(count * 4, 2)
    overlaid_positions, overlaid_rotations = upper_data.apply_gaze_overlay_global_pose(
        prototype,
        upper_positions.reshape(count * 4, prototype.J, 3),
        upper_rotations.reshape(count * 4, prototype.J, 3, 3),
        repeated_gaze4,
    )
    upper_states = upper_data.upper_state_from_global_pose_and_heading(
        prototype,
        overlaid_positions,
        overlaid_rotations,
        support["upper_root_positions"].index_select(0, selected).reshape(count * 4, 3),
        support["upper_root_headings"].index_select(0, selected).reshape(count * 4, 3, 3),
    ).reshape(count, 4, upper_data.POSE_DIM)
    return upper_states


@torch.no_grad()
def resample_gaze_windows(
    raw_windows: torch.Tensor,
    support: dict[str, torch.Tensor],
    selected: torch.Tensor,
    prototype: tl.MotionClip,
    lower_prototype: tl.MotionClip,
    gaze: torch.Tensor,
    *,
    upper_states: torch.Tensor | None = None,
) -> torch.Tensor:
    """Rebuild gaze-dependent inputs and targets for one sampled rollout reset."""

    count = int(selected.numel())
    if tuple(gaze.shape) != (count, 2):
        raise ValueError(f"Expected sampled gaze [{count},2], got {tuple(gaze.shape)}")
    batch = raw_windows.index_select(0, selected).clone()
    if upper_states is None:
        upper_states = resampled_gaze_upper_states(
            support, selected, prototype, gaze
        )
    if tuple(upper_states.shape) != (count, 4, upper_data.POSE_DIM):
        raise ValueError(
            f"Expected gaze upper states [{count},4,{upper_data.POSE_DIM}], "
            f"got {tuple(upper_states.shape)}"
        )
    base = support["base_upper"].index_select(0, selected)
    priors = (
        upper_data.clean_upper_state(base[:, 1] + upper_states[:, 1] - base[:, 0]),
        upper_data.clean_upper_state(base[:, 2] + upper_states[:, 2] - base[:, 1]),
    )
    for row_index, (previous_slot, prior) in enumerate(((0, priors[0]), (1, priors[1]))):
        offset = row_index * ROW_DIM
        batch[:, offset : offset + upper_data.POSE_DIM] = upper_states[:, previous_slot]
        batch[
            :,
            offset + upper_data.POSE_DIM : offset + upper_data.POSE_DIM * 2,
        ] = prior
        gaze_start = offset + upper_data.GAZE_START
        batch[:, gaze_start : gaze_start + 2] = gaze

    physical_upper = upper_states[:, 1:4].reshape(count * 3, upper_data.POSE_DIM)
    lower_vectors = support["lower_vectors"].index_select(0, selected).reshape(count * 3, -1)
    pelvis_heading = support["pelvis_heading"].index_select(0, selected).reshape(
        count * 3, upper_data.PELVIS_DIM
    )
    physical_root_positions = support["physical_root_positions"].index_select(
        0, selected
    )
    physical_root_rotations = support["physical_root_rotations"].index_select(
        0, selected
    )
    physical_root_headings = support["physical_root_headings"].index_select(
        0, selected
    )
    physical_positions, physical_rotations = physical_data.decode_full_pose(
        prototype,
        lower_prototype,
        lower_vectors,
        physical_upper,
        pelvis_heading,
        physical_root_positions.reshape(count * 3, 3),
        physical_root_rotations.reshape(count * 3, 3, 3),
        physical_root_headings.reshape(count * 3, 3, 3),
    )
    physical_positions = physical_positions.reshape(count, 3, prototype.J, 3)
    physical_rotations = physical_rotations.reshape(count, 3, prototype.J, 3, 3)
    root_positions = physical_root_positions
    root_rotations = physical_root_rotations
    for row_index in range(2):
        delta = physical_data.physical_transition_from_decoded(
            prototype,
            physical_positions[:, row_index],
            physical_rotations[:, row_index],
            physical_positions[:, row_index + 1],
            physical_rotations[:, row_index + 1],
            root_positions[:, row_index],
            root_rotations[:, row_index],
        )
        output_start = row_index * ROW_DIM + INPUT_DIM
        batch[:, output_start : output_start + OUTPUT_DIM] = delta
    return batch


@torch.no_grad()
def coherent_timid_window(
    clean_raw: torch.Tensor,
    clean_upper_states: torch.Tensor,
    support: dict[str, torch.Tensor],
    selected: torch.Tensor,
    prototype: tl.MotionClip,
    lower_prototype: tl.MotionClip,
    fraction: torch.Tensor,
) -> torch.Tensor:
    """Build a self-consistent authored upper trajectory with reduced motion.

    The same per-window fraction scales each of the three consecutive authored
    upper-pose increments.  Both controller pose-history fields and both
    physical transitions are then rebuilt from that one timid trajectory.
    Lower body, pelvis, roots, feet, sword mode and gaze remain untouched.
    """

    count = int(clean_raw.shape[0])
    if tuple(clean_raw.shape) != (count, WINDOW_DIM):
        raise ValueError(f"Expected clean windows [N,{WINDOW_DIM}], got {tuple(clean_raw.shape)}")
    if tuple(clean_upper_states.shape) != (count, 4, upper_data.POSE_DIM):
        raise ValueError(
            f"Expected clean upper states [N,4,{upper_data.POSE_DIM}], "
            f"got {tuple(clean_upper_states.shape)}"
        )
    if fraction.ndim == 1:
        fraction = fraction.unsqueeze(-1)
    if tuple(fraction.shape) != (count, 1):
        raise ValueError(
            f"Expected one coherent timid fraction per window, got {tuple(fraction.shape)}"
        )
    if not bool(((fraction >= 0.0) & (fraction <= 1.0)).all()):
        raise ValueError("Coherent timid fractions must stay in [0,1]")

    timid_states = torch.empty_like(clean_upper_states)
    timid_states[:, 0] = clean_upper_states[:, 0]
    alpha = fraction
    for frame in range(1, 4):
        authored_increment = (
            clean_upper_states[:, frame] - clean_upper_states[:, frame - 1]
        )
        timid_states[:, frame] = upper_data.clean_upper_state(
            timid_states[:, frame - 1] + alpha * authored_increment
        )

    result = clean_raw.clone()
    base = support["base_upper"].index_select(0, selected)
    priors = (
        upper_data.clean_upper_state(base[:, 1] + timid_states[:, 1] - base[:, 0]),
        upper_data.clean_upper_state(base[:, 2] + timid_states[:, 2] - base[:, 1]),
    )
    for row_index, (previous_slot, prior) in enumerate(((0, priors[0]), (1, priors[1]))):
        offset = row_index * ROW_DIM
        result[:, offset : offset + upper_data.POSE_DIM] = timid_states[:, previous_slot]
        result[
            :,
            offset + upper_data.POSE_DIM : offset + upper_data.POSE_DIM * 2,
        ] = prior

    physical_upper = timid_states[:, 1:4].reshape(count * 3, upper_data.POSE_DIM)
    lower_vectors = support["lower_vectors"].index_select(0, selected).reshape(count * 3, -1)
    pelvis_heading = support["pelvis_heading"].index_select(0, selected).reshape(
        count * 3, upper_data.PELVIS_DIM
    )
    root_positions = support["physical_root_positions"].index_select(0, selected)
    root_rotations = support["physical_root_rotations"].index_select(0, selected)
    root_headings = support["physical_root_headings"].index_select(0, selected)
    physical_positions, physical_rotations = physical_data.decode_full_pose(
        prototype,
        lower_prototype,
        lower_vectors,
        physical_upper,
        pelvis_heading,
        root_positions.reshape(count * 3, 3),
        root_rotations.reshape(count * 3, 3, 3),
        root_headings.reshape(count * 3, 3, 3),
    )
    physical_positions = physical_positions.reshape(count, 3, prototype.J, 3)
    physical_rotations = physical_rotations.reshape(count, 3, prototype.J, 3, 3)
    for row_index in range(2):
        delta = physical_data.physical_transition_from_decoded(
            prototype,
            physical_positions[:, row_index],
            physical_rotations[:, row_index],
            physical_positions[:, row_index + 1],
            physical_rotations[:, row_index + 1],
            root_positions[:, row_index],
            root_rotations[:, row_index],
        )
        output_start = row_index * ROW_DIM + INPUT_DIM
        result[:, output_start : output_start + OUTPUT_DIM] = delta
    if not bool(torch.isfinite(result).all()):
        raise RuntimeError("Coherent timid window construction produced non-finite values")
    return result


def equal_group_normalization(
    values: torch.Tensor,
    groups: torch.Tensor,
    std_floor: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    means: list[torch.Tensor] = []
    seconds: list[torch.Tensor] = []
    for group in range(GROUP_COUNT):
        selected = values[groups == group].double()
        means.append(selected.mean(dim=0))
        seconds.append((selected * selected).mean(dim=0))
    mean64 = torch.stack(means).mean(dim=0)
    second64 = torch.stack(seconds).mean(dim=0)
    std64 = torch.sqrt((second64 - mean64.square()).clamp_min(0.0))
    return mean64.float(), std64.clamp_min(float(std_floor)).float()


def statue_window(
    normalized: torch.Tensor,
    mean: torch.Tensor,
    std: torch.Tensor,
) -> torch.Tensor:
    """Replace both candidate physical transitions by an exact zero-motion statue."""

    result = normalized.clone()
    normalized_zero = -mean / std
    for row_offset in (0, ROW_DIM):
        start = row_offset + INPUT_DIM
        result[:, start : start + OUTPUT_DIM] = normalized_zero[
            start : start + OUTPUT_DIM
        ]
    return result


@torch.no_grad()
def evaluate(
    model: SimpleAutoencoder,
    normalized: torch.Tensor,
    groups: torch.Tensor,
    mean: torch.Tensor,
    std: torch.Tensor,
    weights: torch.Tensor,
    device: torch.device,
    batch_size: int = 2048,
    normalized_inbetween: torch.Tensor | None = None,
) -> dict[str, Any]:
    model.eval()
    clean_group_sum = torch.zeros(GROUP_COUNT, dtype=torch.float64)
    statue_group_sum = torch.zeros(GROUP_COUNT, dtype=torch.float64)
    correction_group_sum = torch.zeros(GROUP_COUNT, dtype=torch.float64)
    inbetween_score_group_sum = torch.zeros(GROUP_COUNT, dtype=torch.float64)
    inbetween_correction_group_sum = torch.zeros(GROUP_COUNT, dtype=torch.float64)
    group_count = torch.zeros(GROUP_COUNT, dtype=torch.long)
    clean_maximum = 0.0
    statue_minimum = float("inf")
    for start in range(0, int(normalized.shape[0]), int(batch_size)):
        end = min(int(normalized.shape[0]), start + int(batch_size))
        batch = normalized[start:end].to(device)
        reconstruction = model(batch)
        clean_row = weighted_output_mse(
            reconstruction[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END]
            - batch[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END],
            weights,
        )
        statue = statue_window(batch, mean, std)
        statue_reconstruction = model(statue)
        statue_row = weighted_output_mse(
            statue_reconstruction[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END]
            - statue[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END],
            weights,
        )
        correction_row = weighted_output_mse(
            statue_reconstruction[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END]
            - batch[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END],
            weights,
        )
        if normalized_inbetween is not None:
            inbetween = normalized_inbetween[start:end]
            inbetween_reconstruction = model(inbetween)
            inbetween_score_row = weighted_output_mse(
                inbetween_reconstruction[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END]
                - inbetween[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END],
                weights,
            )
            inbetween_correction_row = weighted_output_mse(
                inbetween_reconstruction[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END]
                - batch[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END],
                weights,
            )
        else:
            inbetween_score_row = clean_row.new_zeros(clean_row.shape)
            inbetween_correction_row = clean_row.new_zeros(clean_row.shape)
        clean_cpu = clean_row.detach().double().cpu()
        statue_cpu = statue_row.detach().double().cpu()
        correction_cpu = correction_row.detach().double().cpu()
        inbetween_score_cpu = inbetween_score_row.detach().double().cpu()
        inbetween_correction_cpu = inbetween_correction_row.detach().double().cpu()
        group_cpu = groups[start:end]
        for group in range(GROUP_COUNT):
            selection = group_cpu == group
            clean_selected = clean_cpu[selection]
            statue_selected = statue_cpu[selection]
            correction_selected = correction_cpu[selection]
            inbetween_score_selected = inbetween_score_cpu[selection]
            inbetween_correction_selected = inbetween_correction_cpu[selection]
            clean_group_sum[group] += clean_selected.sum()
            statue_group_sum[group] += statue_selected.sum()
            correction_group_sum[group] += correction_selected.sum()
            inbetween_score_group_sum[group] += inbetween_score_selected.sum()
            inbetween_correction_group_sum[group] += inbetween_correction_selected.sum()
            group_count[group] += int(clean_selected.numel())
        clean_maximum = max(clean_maximum, float(clean_cpu.max()))
        statue_minimum = min(statue_minimum, float(statue_cpu.min()))
    denominator = group_count.clamp_min(1)
    clean_group_mean = clean_group_sum / denominator
    statue_group_mean = statue_group_sum / denominator
    correction_group_mean = correction_group_sum / denominator
    inbetween_score_group_mean = inbetween_score_group_sum / denominator
    inbetween_correction_group_mean = inbetween_correction_group_sum / denominator
    clean_mean = clean_group_mean.mean()
    statue_mean = statue_group_mean.mean()
    correction_mean = correction_group_mean.mean()
    inbetween_score_mean = inbetween_score_group_mean.mean()
    inbetween_correction_mean = inbetween_correction_group_mean.mean()
    model.train()
    return {
        "equal_group_mean": float(clean_mean),
        "selection_objective": float(
            clean_mean + correction_mean + inbetween_correction_mean
        ),
        "group_mean": [float(value) for value in clean_group_mean],
        "clean_group_mean": [float(value) for value in clean_group_mean],
        "statue_group_mean": [float(value) for value in statue_group_mean],
        "statue_correction_group_mean": [
            float(value) for value in correction_group_mean
        ],
        "statue_score": float(statue_mean),
        "statue_correction_mse": float(correction_mean),
        "inbetween_score": float(inbetween_score_mean),
        "inbetween_correction_mse": float(inbetween_correction_mean),
        "inbetween_score_group_mean": [
            float(value) for value in inbetween_score_group_mean
        ],
        "inbetween_correction_group_mean": [
            float(value) for value in inbetween_correction_group_mean
        ],
        "statue_over_clean": float(statue_mean / clean_mean.clamp_min(1.0e-12)),
        "clean_maximum_row": clean_maximum,
        "statue_minimum_row": statue_minimum,
        "finite": bool(
            torch.isfinite(clean_group_mean).all()
            and torch.isfinite(statue_group_mean).all()
            and torch.isfinite(correction_group_mean).all()
            and torch.isfinite(inbetween_score_group_mean).all()
            and torch.isfinite(inbetween_correction_group_mean).all()
        ),
    }


def checkpoint_payload(
    model: SimpleAutoencoder,
    optimizer: torch.optim.Optimizer,
    cfg: SimpleAEConfig,
    mean: torch.Tensor,
    std: torch.Tensor,
    metadata: dict[str, Any],
    step: int,
    best: float,
    sampling_generator: torch.Generator | None = None,
) -> dict[str, Any]:
    payload = {
        "kind": "upper_pose_pelvis_physical_simple_autoencoder",
        "model": model.state_dict(),
        "optimizer": optimizer.state_dict(),
        "config": asdict(cfg),
        "schema": checkpoint_schema(),
        "mean": mean.cpu(),
        "std": std.cpu(),
        "step": int(step),
        "best": float(best),
        "metadata": metadata,
    }
    if sampling_generator is not None:
        payload["rng_state"] = {
            "torch_cpu": torch.get_rng_state().cpu(),
            "sampling_generator": sampling_generator.get_state().cpu(),
            "torch_cuda_all": (
                [state.cpu() for state in torch.cuda.get_rng_state_all()]
                if torch.cuda.is_available()
                else []
            ),
        }
    return payload


def train(args: argparse.Namespace) -> None:
    global _FULL_CORPUS, _STATUE_NEGATIVES, _INBETWEEN_NEGATIVES, _HAND_LOSS_WEIGHT
    _FULL_CORPUS = bool(args.full_corpus)
    _STATUE_NEGATIVES = bool(args.statue_negatives)
    _INBETWEEN_NEGATIVES = bool(args.inbetween_negatives)
    _HAND_LOSS_WEIGHT = float(args.hand_loss_weight)
    if _HAND_LOSS_WEIGHT < 1.0 or not torch.isfinite(
        torch.tensor(_HAND_LOSS_WEIGHT)
    ):
        raise ValueError("--hand-loss-weight must be finite and at least 1")
    torch.manual_seed(int(args.seed))
    if args.cache_only == "windows":
        windows, _groups, _metadata, path = prepare_windows(
            bool(args.rebuild_cache)
        )
        print(
            f"UPPER_ROOT_SIMPLE_AE_WINDOWS_CACHE_OK rows={windows.shape[0]} path={path}",
            flush=True,
        )
        return
    if args.cache_only == "support":
        support, path, _prototype = prepare_dynamic_support(
            bool(args.rebuild_cache)
        )
        print(
            "UPPER_ROOT_SIMPLE_AE_SUPPORT_CACHE_OK "
            f"rows={next(iter(support.values())).shape[0]} path={path}",
            flush=True,
        )
        return
    windows, groups, dataset_metadata, dataset_cache = prepare_windows(
        bool(args.rebuild_cache)
    )
    mean, std = equal_group_normalization(windows, groups, float(args.std_floor))
    resume_checkpoint = (
        Path(args.resume_checkpoint).resolve()
        if args.resume_checkpoint is not None
        else None
    )
    parent: dict[str, Any] | None = None
    parent_sha256 = ""
    start_step = 0
    if resume_checkpoint is not None:
        if not resume_checkpoint.is_file():
            raise FileNotFoundError(resume_checkpoint)
        parent = torch.load(resume_checkpoint, map_location="cpu", weights_only=False)
        if parent.get("kind") != "upper_pose_pelvis_physical_simple_autoencoder":
            raise RuntimeError(f"Unsupported resume checkpoint kind: {parent.get('kind')!r}")
        if parent.get("schema") != checkpoint_schema():
            raise RuntimeError("Resume checkpoint schema does not match the current AE contract")
        if not torch.equal(parent["mean"].cpu(), mean.cpu()):
            raise RuntimeError("Resume checkpoint mean does not exactly match this dataset")
        if not torch.equal(parent["std"].cpu(), std.cpu()):
            raise RuntimeError("Resume checkpoint std does not exactly match this dataset")
        start_step = int(parent["step"])
        if int(args.additional_steps) <= 0:
            raise RuntimeError("--additional-steps must be positive when resuming")
        parent_sha256 = hashlib.sha256(resume_checkpoint.read_bytes()).hexdigest()
    support, support_cache, prototype_source = prepare_dynamic_support(
        bool(args.rebuild_cache)
    )
    if any(int(value.shape[0]) != int(windows.shape[0]) for value in support.values()):
        raise RuntimeError(
            f"Dynamic gaze support rows do not match windows: "
            f"windows={windows.shape[0]} support="
            f"{sorted({int(value.shape[0]) for value in support.values()})}"
        )
    prototype = tl.MotionClip(
        prototype_source,
        upper_data.motion_config(),
        cyclic_animation=True,
    )
    lower_prototype_cfg = upper_data.motion_config()
    lower_prototype_cfg.body_mode = tl.BODY_MODE_LOWER
    lower_prototype = tl.MotionClip(
        prototype_source,
        lower_prototype_cfg,
        cyclic_animation=True,
    )
    raw_windows = windows
    gc.collect()

    device = torch.device(args.device)
    if device.type == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but unavailable")
        cuda_index = (
            int(device.index)
            if device.index is not None
            else int(torch.cuda.current_device())
        )
        torch.cuda.set_device(cuda_index)
        device = torch.device("cuda", cuda_index)
        torch.backends.cuda.matmul.allow_tf32 = True
    raw_windows = raw_windows.to(device=device, non_blocking=False)
    support = {
        key: value.to(device=device, non_blocking=False)
        for key, value in support.items()
    }
    mean = mean.to(device=device)
    std = std.to(device=device)
    output_weights = physical_output_weights(device=device)

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
        pose_representation="actual_pelvis_upper_leg_transforms_in_current_root",
        body_mode="upper_plus_pelvis_and_leg_ik",
        feature="two_rows_of_upper_controller_input_plus_physical_transform_delta",
        ae_feature_mode="pose",
        ae_score_scope="output",
        window_frames=2,
        denoise_noise_std=0.0,
    )
    if parent is not None:
        parent_config = dict(parent["config"])
        current_config = asdict(cfg)
        ignored = {"train_steps"}
        mismatches = {
            key: (parent_config.get(key), current_config.get(key))
            for key in current_config
            if key not in ignored and parent_config.get(key) != current_config.get(key)
        }
        if mismatches:
            raise RuntimeError(f"Resume checkpoint recipe mismatch: {mismatches}")
        cfg.train_steps = start_step + int(args.additional_steps)
    model = SimpleAutoencoder(WINDOW_DIM, cfg).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=cfg.learning_rate, weight_decay=cfg.weight_decay
    )
    if parent is not None:
        model.load_state_dict(parent["model"], strict=True)
        optimizer.load_state_dict(parent["optimizer"])
        for state in optimizer.state.values():
            for key, value in state.items():
                if torch.is_tensor(value):
                    state[key] = value.to(device=device)
        mean = parent["mean"].to(device=device)
        std = parent["std"].to(device=device)
    group_rows = [torch.where(groups == group)[0] for group in range(GROUP_COUNT)]
    evaluation_generator = torch.Generator(device="cpu").manual_seed(int(cfg.seed) + 99173)
    evaluation_chunks: list[torch.Tensor] = []
    evaluation_inbetween_chunks: list[torch.Tensor] = []
    for start in range(0, int(raw_windows.shape[0]), 512):
        end = min(int(raw_windows.shape[0]), start + 512)
        selected = torch.arange(start, end, dtype=torch.long, device=device)
        gaze = sample_rollout_gaze(
            int(selected.numel()), evaluation_generator
        ).to(device=device)
        upper_states = resampled_gaze_upper_states(
            support, selected, prototype, gaze
        )
        raw = resample_gaze_windows(
            raw_windows,
            support,
            selected,
            prototype,
            lower_prototype,
            gaze,
            upper_states=upper_states,
        )
        evaluation_chunks.append((raw - mean) / std)
        if _INBETWEEN_NEGATIVES:
            levels = torch.tensor(
                (0.25, 0.5, 0.75), device=device, dtype=raw.dtype
            )
            fraction = levels[
                torch.arange(start, end, device=device) % int(levels.numel())
            ].unsqueeze(-1)
            timid_raw = coherent_timid_window(
                raw,
                upper_states,
                support,
                selected,
                prototype,
                lower_prototype,
                fraction,
            )
            evaluation_inbetween_chunks.append((timid_raw - mean) / std)
    normalized_evaluation = torch.cat(evaluation_chunks, dim=0)
    del evaluation_chunks
    normalized_inbetween_evaluation = (
        torch.cat(evaluation_inbetween_chunks, dim=0)
        if _INBETWEEN_NEGATIVES
        else None
    )
    del evaluation_inbetween_chunks

    continuation_baseline_report: dict[str, Any] | None = None
    if parent is not None and _INBETWEEN_NEGATIVES:
        continuation_baseline_report = evaluate(
            model,
            normalized_evaluation,
            groups,
            mean,
            std,
            output_weights,
            device,
            normalized_inbetween=normalized_inbetween_evaluation,
        )

    metadata: dict[str, Any] = {
        "dataset": dataset_metadata,
        "dataset_cache": str(dataset_cache),
        "dynamic_gaze_support_cache": str(support_cache),
        "recipe": {
            "source": "accepted running AE1",
            "model_class": "train_simple_autoencoder.SimpleAutoencoder",
            "architecture": "symmetric_fc_layernorm_gelu",
            "hidden_dim": 1024,
            "hidden_layers": 3,
            "latent_dim": 128,
            "window_frames": 2,
            "optimizer": "AdamW",
            "learning_rate": 1.0e-3,
            "weight_decay": 1.0e-5,
            "lr_schedule": "1.0_to_70pct__0.3_to_90pct__0.1_final",
            "training_noise": 0.0,
            "loss": "newest_output_reconstruction_mse_only",
            "statue_negatives": bool(_STATUE_NEGATIVES),
            "statue_construction": (
                "both physical-transition rows set to exact raw zero; controller conditioning unchanged"
                if _STATUE_NEGATIVES
                else "disabled"
            ),
            "statue_target": (
                "clean newest physical transition"
                if _STATUE_NEGATIVES
                else "n/a"
            ),
            "inbetween_negatives": bool(_INBETWEEN_NEGATIVES),
            "inbetween_construction": (
                "one authored-only uniform fraction in [0,1) scales all three consecutive upper-pose increments; both controller pose-history fields and both physical transitions are rebuilt coherently from that timid trajectory; lower/pelvis/root/feet/sword/gaze unchanged; no rollout data"
                if _INBETWEEN_NEGATIVES
                else "disabled"
            ),
            "inbetween_target": (
                "clean newest authored physical transition"
                if _INBETWEEN_NEGATIVES
                else "n/a"
            ),
            "hand_transform_loss_weight": float(_HAND_LOSS_WEIGHT),
            "dataset_scope": "all_465_matched_clips_per_mode" if _FULL_CORPUS else "30_omni_loops_per_mode",
            "transition_boundary": "stop_at_last_usable_frame_without_wrap_or_padding",
            "batch_sampling": "exact_equal_four_groups",
            "gaze_sampling": (
                "one fresh uniform gaze per sampled two-row rollout reset; "
                "held constant across both rows; 5 percent exact zero-zero"
            ),
            "evaluation_gaze": "fixed independent uniform held-out draw per window",
            "seed": int(args.seed),
        },
    }
    if parent is not None:
        metadata["continuation"] = {
            "parent_checkpoint": str(resume_checkpoint),
            "parent_sha256": parent_sha256,
            "parent_step": start_step,
            "additional_steps": int(args.additional_steps),
            "learning_rate": float(optimizer.param_groups[0]["lr"]),
            "schedule": "preserve_parent_final_learning_rate",
            "recipe_changes": (
                "add authored-only coherent upper-trajectory timid-to-clean correction"
                if _INBETWEEN_NEGATIVES
                else "none"
            ),
        }
        if continuation_baseline_report is not None:
            metadata["continuation"]["baseline"] = continuation_baseline_report

    smoke_steps = int(args.smoke_steps)
    train_steps = (
        start_step + smoke_steps
        if smoke_steps > 0 and parent is not None
        else smoke_steps
        if smoke_steps > 0
        else int(cfg.train_steps)
    )
    run_id = ""
    run_dir: Path | None = None
    writer: SummaryWriter | None = None
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
        writer = SummaryWriter(log_dir=str(run_dir / "tb"))

    best = (
        float(continuation_baseline_report["selection_objective"])
        if continuation_baseline_report is not None
        else float(parent["best"])
        if parent is not None
        else float("inf")
    )
    best_step = start_step if parent is not None else 0
    generator = torch.Generator(device="cpu")
    if parent is not None and "rng_state" in parent:
        rng_state = parent["rng_state"]
        torch.set_rng_state(rng_state["torch_cpu"].cpu())
        generator.set_state(rng_state["sampling_generator"].cpu())
        if device.type == "cuda" and rng_state.get("torch_cuda_all"):
            torch.cuda.set_rng_state_all(
                [state.cpu() for state in rng_state["torch_cuda_all"]]
            )
        metadata["continuation"]["rng"] = "restored_exactly_from_parent"
    else:
        continuation_seed = int(cfg.seed) + int(start_step)
        torch.manual_seed(continuation_seed)
        generator.manual_seed(continuation_seed)
        metadata.setdefault("continuation", {})["rng"] = (
            "parent_predates_rng_capture; deterministic reseed at seed_plus_parent_step"
        )
    if run_dir is not None:
        initial_payload = checkpoint_payload(
            model, optimizer, cfg, mean, std, metadata, start_step, best, generator
        )
        torch.save(initial_payload, checkpoint_path(run_dir, run_id, "init"))
        if parent is not None:
            torch.save(initial_payload, checkpoint_path(run_dir, run_id, "best"))
    history: list[dict[str, Any]] = []
    started = time.perf_counter()
    first_step = start_step + 1 if parent is not None else 1
    for step in range(first_step, train_steps + 1):
        lr = (
            float(optimizer.param_groups[0]["lr"])
            if parent is not None
            else lr_for_step(step, int(cfg.train_steps), float(cfg.learning_rate))
        )
        for parameter_group in optimizer.param_groups:
            parameter_group["lr"] = lr
        selected = equal_group_batch_indices(group_rows, int(cfg.batch_size))
        selected = selected.to(device=device)
        gaze = sample_rollout_gaze(int(selected.numel()), generator).to(device=device)
        batch_raw = resample_gaze_windows(
            raw_windows,
            support,
            selected,
            prototype,
            lower_prototype,
            gaze,
            upper_states=(
                upper_states := resampled_gaze_upper_states(
                    support, selected, prototype, gaze
                )
            ),
        )
        batch = ((batch_raw - mean) / std).to(device)
        variants = [batch]
        statue = None
        inbetween = None
        if _STATUE_NEGATIVES:
            statue = statue_window(batch, mean, std)
            variants.append(statue)
        if _INBETWEEN_NEGATIVES:
            fraction = torch.rand(
                (int(batch.shape[0]), 1), device=device, dtype=batch.dtype
            )
            inbetween_raw = coherent_timid_window(
                batch_raw,
                upper_states,
                support,
                selected,
                prototype,
                lower_prototype,
                fraction,
            )
            inbetween = (inbetween_raw - mean) / std
            variants.append(inbetween)
        reconstruction_variants = model(torch.cat(variants, dim=0)).split(
            int(batch.shape[0]), dim=0
        )
        reconstruction = reconstruction_variants[0]
        clean_loss = weighted_output_mse(
            reconstruction[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END]
            - batch[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END],
            output_weights,
        ).mean()
        statue_loss = clean_loss.new_zeros(())
        variant_index = 1
        if _STATUE_NEGATIVES:
            assert statue is not None
            statue_reconstruction = reconstruction_variants[variant_index]
            variant_index += 1
            statue_loss = weighted_output_mse(
                statue_reconstruction[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END]
                - batch[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END],
                output_weights,
            ).mean()
        inbetween_loss = clean_loss.new_zeros(())
        if _INBETWEEN_NEGATIVES:
            assert inbetween is not None
            inbetween_reconstruction = reconstruction_variants[variant_index]
            inbetween_loss = weighted_output_mse(
                inbetween_reconstruction[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END]
                - batch[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END],
                output_weights,
            ).mean()
        loss = clean_loss + statue_loss + inbetween_loss
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()

        evaluate_now = (
            step == 1
            or step == train_steps
            or step % int(args.eval_every) == 0
        )
        if not evaluate_now:
            continue
        report = evaluate(
            model,
            normalized_evaluation,
            groups,
            mean,
            std,
            output_weights,
            device,
            normalized_inbetween=normalized_inbetween_evaluation,
        )
        score = float(report["selection_objective"])
        row = {
            "step": int(step),
            "train_batch_loss": float(loss.detach().cpu()),
            "train_clean_loss": float(clean_loss.detach().cpu()),
            "train_statue_correction_loss": float(statue_loss.detach().cpu()),
            "train_inbetween_correction_loss": float(inbetween_loss.detach().cpu()),
            "learning_rate": float(lr),
            "elapsed_seconds": time.perf_counter() - started,
            **report,
        }
        legacy_objective = float(report["equal_group_mean"]) + float(
            report["statue_correction_mse"]
        )
        baseline_legacy_objective = (
            float(continuation_baseline_report["equal_group_mean"])
            + float(continuation_baseline_report["statue_correction_mse"])
            if continuation_baseline_report is not None
            else float("inf")
        )
        legacy_nonregression = bool(
            continuation_baseline_report is None
            or legacy_objective <= baseline_legacy_objective
        )
        row["legacy_selection_objective"] = legacy_objective
        row["baseline_legacy_selection_objective"] = baseline_legacy_objective
        row["legacy_nonregression"] = legacy_nonregression
        history.append(row)
        improved = score < best and legacy_nonregression
        if improved:
            best = score
            best_step = int(step)
            if run_dir is not None:
                torch.save(
                    checkpoint_payload(
                        model, optimizer, cfg, mean, std, metadata, step, best, generator
                    ),
                    checkpoint_path(run_dir, run_id, "best"),
                )
        if run_dir is not None:
            torch.save(
                checkpoint_payload(
                    model, optimizer, cfg, mean, std, metadata, step, best, generator
                ),
                checkpoint_path(run_dir, run_id, "latest"),
            )
            (run_dir / "metrics.json").write_text(
                json.dumps(
                    {
                        "run_id": run_id,
                        "best": best,
                        "best_step": best_step,
                        "latest": row,
                        "history": history,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            if writer is not None:
                writer.add_scalar("loss/ae1", float(report["equal_group_mean"]), step)
                writer.add_scalar("loss/statue_correction", float(report["statue_correction_mse"]), step)
                if _INBETWEEN_NEGATIVES:
                    writer.add_scalar("loss/inbetween_correction", float(report["inbetween_correction_mse"]), step)
                    writer.add_scalar("metric/inbetween_score", float(report["inbetween_score"]), step)
                writer.add_scalar("metric/statue_score", float(report["statue_score"]), step)
                writer.add_scalar("metric/statue_over_clean", float(report["statue_over_clean"]), step)
                writer.add_scalar("loss/train_batch", float(loss.detach().cpu()), step)
                writer.add_scalar("learning_rate", lr, step)
                writer.flush()
        print(
            f"UPPER_ROOT_SIMPLE_AE1 step={step} objective={score:.8g} "
            f"clean={float(report['equal_group_mean']):.8g} "
            f"statue={float(report['statue_score']):.8g} "
            f"statue_x={float(report['statue_over_clean']):.3f} "
            f"between={float(report['inbetween_correction_mse']):.8g} "
            f"batch={float(loss.detach().cpu()):.8g} best={best:.8g}@{best_step} "
            f"lr={lr:.3g} elapsed_s={time.perf_counter() - started:.1f}",
            flush=True,
        )

    if smoke_steps > 0:
        print("UPPER_ROOT_SIMPLE_AE1_SMOKE_OK", flush=True)
        return

    assert run_dir is not None
    torch.save(
        checkpoint_payload(
            model, optimizer, cfg, mean, std, metadata, train_steps, best, generator
        ),
        checkpoint_path(run_dir, run_id, "last"),
    )
    if writer is not None:
        writer.close()
    print(
        f"UPPER_ROOT_SIMPLE_AE1_COMPLETE run={run_id} best={best:.8g}@{best_step}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train the faithful running-style upper root-transform AE1."
    )
    parser.add_argument(
        "--run-label",
        default="ae1_upper_pelvis_physical_h1024_l3_ld128_w2_12k",
    )
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--train-steps", type=int, default=12000)
    parser.add_argument("--resume-checkpoint", type=Path)
    parser.add_argument("--additional-steps", type=int, default=0)
    parser.add_argument("--eval-every", type=int, default=500)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--std-floor", type=float, default=1.0e-4)
    parser.add_argument("--smoke-steps", type=int, default=0)
    parser.add_argument("--rebuild-cache", action="store_true")
    parser.add_argument(
        "--full-corpus",
        action="store_true",
        help="Use all 465 matched walk/run omni+transition clips per sword mode.",
    )
    parser.add_argument(
        "--statue-negatives",
        action="store_true",
        help="Train an equal statue-to-clean correction batch beside every clean batch.",
    )
    parser.add_argument(
        "--inbetween-negatives",
        action="store_true",
        help="Add authored-only coherent upper-trajectory timid-to-clean correction beside clean and exact-statue losses.",
    )
    parser.add_argument(
        "--hand-loss-weight",
        type=float,
        default=1.0,
        help="Relative weight for every value of both hand transforms.",
    )
    parser.add_argument(
        "--cache-only",
        choices=("windows", "support"),
        help="Build exactly one full-corpus cache and exit before allocating the other.",
    )
    train(parser.parse_args())


if __name__ == "__main__":
    main()
