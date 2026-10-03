from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.tensorboard import SummaryWriter

try:
    from .bootstrap import PROJECT_ROOT, ensure_paths
    from .naming import checkpoint_path, ik_run_id
    from .dataset_contract import audit_npz_folder
    from . import ik_core as tl
except ImportError:
    from bootstrap import PROJECT_ROOT, ensure_paths
    from naming import checkpoint_path, ik_run_id
    from dataset_contract import audit_npz_folder
    import ik_core as tl

ensure_paths()


DEFAULT_WALK_F = PROJECT_ROOT / "ue5" / "animations_omni_only" / "npz_final" / "M_Neutral_Walk_Loop_F.npz"
RUNS_DIR = PROJECT_ROOT / "training" / "runs"

LATENT_DIM = 32
HIDDEN_DIM = 512
NUM_HIDDEN_LAYERS = 2
BATCH_SIZE = 512
TRAIN_STEPS = 12000
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-5
STD_FLOOR = 1e-4
VAL_FRACTION = 0.0
SEED = 1234
LOG_EVERY = 250
AE_FEATURE_MODE_POSE = "pose"
AE_FEATURE_MODE_VELOCITY = "velocity_current_root"
AE_FEATURE_MODE_VELOCITY_COMMANDED = "velocity_commanded"
AE_FEATURE_MODE_VALUES = (AE_FEATURE_MODE_POSE, AE_FEATURE_MODE_VELOCITY, AE_FEATURE_MODE_VELOCITY_COMMANDED)
AE_SCORE_SCOPE_OUTPUT = "output"
AE_SCORE_SCOPE_FULL_WINDOW = "full_window"
AE_SCORE_SCOPE_VALUES = (AE_SCORE_SCOPE_OUTPUT, AE_SCORE_SCOPE_FULL_WINDOW)


def refresh_tensorboard_async() -> None:
    script = PROJECT_ROOT / "training" / "ik" / "launch_tensorboard_latest.ps1"
    if not script.exists():
        return
    kwargs = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
    }
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        subprocess.Popen(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)],
            cwd=str(PROJECT_ROOT),
            **kwargs,
        )
    except Exception as exc:
        print(f"tensorboard refresh skipped: {exc}", flush=True)


@dataclass
class SimpleAEConfig:
    latent_dim: int = LATENT_DIM
    hidden_dim: int = HIDDEN_DIM
    num_hidden_layers: int = NUM_HIDDEN_LAYERS
    batch_size: int = BATCH_SIZE
    train_steps: int = TRAIN_STEPS
    learning_rate: float = LEARNING_RATE
    weight_decay: float = WEIGHT_DECAY
    std_floor: float = STD_FLOOR
    val_fraction: float = VAL_FRACTION
    seed: int = SEED
    pose_representation: str = tl.IK_POSE_REPRESENTATION
    body_mode: str = tl.BODY_MODE_LOWER
    feature: str = "controller_input_plus_transition_output"
    ae_feature_mode: str = AE_FEATURE_MODE_POSE
    ae_score_scope: str = AE_SCORE_SCOPE_OUTPUT
    window_frames: int = 1
    denoise_noise_std: float = 0.0


class SimpleAutoencoder(nn.Module):
    def __init__(self, dim: int, cfg: SimpleAEConfig):
        super().__init__()
        encoder: list[nn.Module] = []
        in_dim = int(dim)
        for _ in range(int(cfg.num_hidden_layers)):
            encoder.extend((nn.Linear(in_dim, cfg.hidden_dim), nn.LayerNorm(cfg.hidden_dim), nn.GELU()))
            in_dim = int(cfg.hidden_dim)
        encoder.extend((nn.Linear(in_dim, cfg.latent_dim), nn.GELU()))

        decoder: list[nn.Module] = []
        in_dim = int(cfg.latent_dim)
        for _ in range(int(cfg.num_hidden_layers)):
            decoder.extend((nn.Linear(in_dim, cfg.hidden_dim), nn.LayerNorm(cfg.hidden_dim), nn.GELU()))
            in_dim = int(cfg.hidden_dim)
        decoder.append(nn.Linear(in_dim, dim))
        self.net = nn.Sequential(*(encoder + decoder))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


def make_locomotion_cfg(device: torch.device, body_mode: str = tl.BODY_MODE_LOWER) -> tl.TrainConfig:
    cfg = tl.TrainConfig()
    cfg.pose_representation = tl.IK_POSE_REPRESENTATION
    cfg.body_mode = tl.normalized_body_mode(body_mode)
    cfg.cyclic_animation = True
    cfg.predict_residual = tl.output_prediction_uses_residual()
    cfg.zero_init_output = tl.output_prediction_uses_residual()
    cfg.live_viewer = False
    cfg.visual_reporter = False
    cfg.update_comparison_on_exit = False
    cfg.use_torch_compile = False
    cfg.device = str(device)
    return cfg


def resolve_path(path_text: str | Path) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def infer_cyclic_from_path(path: Path) -> bool:
    text = str(path).replace("\\", "/").lower()
    stem = path.stem.lower()
    if "loop" in stem or "animations_omni" in text:
        return True
    if "transition" in text or "turn" in stem or "reface" in stem or "diamond" in stem:
        return False
    return False


def npz_paths_from_text(path_text: str) -> list[Path]:
    paths: list[Path] = []
    for raw_part in str(path_text or "").split(";"):
        part = raw_part.strip()
        if not part:
            continue
        path = resolve_path(part)
        if path.is_dir():
            audit_npz_folder(path)
            found = sorted(path.glob("*.npz"))
            if not found:
                raise FileNotFoundError(f"No .npz files found in {path}")
            paths.extend(found)
        else:
            if not path.exists():
                raise FileNotFoundError(f"NPZ path does not exist: {path}")
            if path.suffix.lower() != ".npz":
                raise ValueError(f"Expected .npz file, got: {path}")
            paths.append(path)
    return paths


def resolve_clip_specs(
    npz_text: str | None,
    periodic_text: str | None,
    nonperiodic_text: str | None,
) -> list[tuple[Path, bool]]:
    specs: list[tuple[Path, bool]] = []
    for path in npz_paths_from_text(periodic_text or ""):
        specs.append((path, True))
    for path in npz_paths_from_text(nonperiodic_text or ""):
        specs.append((path, False))
    if specs:
        return specs
    if npz_text:
        return [(path, infer_cyclic_from_path(path)) for path in npz_paths_from_text(npz_text)]
    if not DEFAULT_WALK_F.exists():
        raise FileNotFoundError(f"Default walk-forward NPZ not found: {DEFAULT_WALK_F}")
    return [(DEFAULT_WALK_F.resolve(), True)]


def load_clips(specs: list[tuple[Path, bool]], cfg: tl.TrainConfig) -> list[tl.MotionClip]:
    clips = [tl.MotionClip(path, cfg, cyclic_animation=cyclic) for path, cyclic in specs]
    first_names = clips[0].body_names
    first_parents = clips[0].parents_body_list
    for clip in clips[1:]:
        if clip.body_names != first_names or clip.parents_body_list != first_parents:
            raise ValueError(f"Skeleton mismatch: {clip.path} vs {clips[0].path}")
    return clips


def valid_current_indices(clip: tl.MotionClip, cfg: tl.TrainConfig, device: torch.device) -> torch.Tensor:
    if clip.cyclic_animation:
        max_cur = int(clip.cyclic_period) - 1
    else:
        max_cur = int(clip.T) - int(cfg.future_window) - 1
    if max_cur < 0:
        return torch.empty((0,), dtype=torch.long, device=device)
    # Include cur_idx=0 so temporal AE windows see the exact same clip-start
    # context rows that rollout/viz scoring builds through initial_ae_context().
    return torch.arange(0, max_cur + 1, dtype=torch.long, device=device)


def feature_schema(clip: tl.MotionClip, cfg: tl.TrainConfig) -> dict[str, object]:
    input_dim, output_dim = tl.make_batch_dims(clip, cfg)
    pose_dim = int(tl.pose_target_output(tl.get_pose_from_clip(clip, torch.tensor([1]), torch.device("cpu"))).shape[-1])
    velocity_dim = input_dim - pose_dim * 2 - 3 - int(cfg.future_window) * 4
    input_root_start = pose_dim * 2 + velocity_dim
    input_root_end = input_dim
    feature_name = (
        "controller_input_plus_current_root_transition_output"
        if tl.output_reference_uses_current_root()
        else "controller_input_plus_future_root_transition_output"
    )
    return {
        "feature": feature_name,
        "output_reference_root": tl.OUTPUT_REFERENCE_ROOT,
        "output_prediction_mode": tl.normalized_output_prediction_mode(),
        "predict_residual": bool(cfg.predict_residual),
        "state_reference_root": tl.STATE_REFERENCE_ROOT,
        "body_mode": tl.normalized_body_mode(getattr(cfg, "body_mode", tl.BODY_MODE_LOWER)),
        "ik_schema_version": tl.IK_SCHEMA_VERSION,
        "ik_pole_reference": tl.IK_POLE_REFERENCE,
        "ik_leg_pole_alpha_deg": math.degrees(tl.IK_LEG_POLE_ALPHA),
        "ik_arm_pole_alpha_deg": math.degrees(tl.IK_ARM_POLE_ALPHA),
        "pose_delta_scale_final": float(cfg.pose_delta_scale_final),
        "total_dim": int(input_dim + output_dim),
        "base_total_dim": int(input_dim + output_dim),
        "window_frames": 1,
        "input_dim": int(input_dim),
        "output_dim": int(output_dim),
        "pose_dim": int(pose_dim),
        "velocity_dim": int(velocity_dim),
        "input_root_start": int(input_root_start),
        "input_root_end": int(input_root_end),
        "target_output_start": int(input_dim),
        "target_output_end": int(input_dim + output_dim),
        "body_names": list(clip.body_names),
        "pose_representation": clip.pose_representation,
        "ik_payload_dim": int(clip.ik_payload_dim),
        "ik_marker_names": list(clip.ik_marker_names),
        "ik_limb_specs": [
            {key: value for key, value in spec.items() if key in {"side", "kind", "start", "mid", "end", "toe"}}
            for spec in clip.ik_limb_specs
        ],
    }


def temporal_feature_schema(base_schema: dict[str, object], frames: int) -> dict[str, object]:
    frames = max(1, int(frames))
    schema = dict(base_schema)
    schema["base_total_dim"] = int(base_schema.get("base_total_dim", base_schema["total_dim"]))
    schema["window_frames"] = frames
    if frames > 1:
        schema["total_dim"] = int(schema["base_total_dim"]) * frames
        schema["feature"] = f"{frames}x_{base_schema.get('feature', 'controller_input_plus_transition_output')}"
    return schema


def temporal_frame_offsets(schema: dict[str, object]) -> list[int]:
    frames = max(1, int(schema.get("window_frames", 1)))
    base_total = int(schema.get("base_total_dim", schema["total_dim"]))
    return [frame * base_total for frame in range(frames)]


def normalized_ae_feature_mode(value: object | None) -> str:
    raw = str(AE_FEATURE_MODE_POSE if value is None else value).strip().lower()
    aliases = {
        "": AE_FEATURE_MODE_POSE,
        "pose": AE_FEATURE_MODE_POSE,
        "positions": AE_FEATURE_MODE_POSE,
        "position": AE_FEATURE_MODE_POSE,
        "velocity": AE_FEATURE_MODE_VELOCITY,
        "vel": AE_FEATURE_MODE_VELOCITY,
        "velocity_current_root": AE_FEATURE_MODE_VELOCITY,
        "current_root_velocity": AE_FEATURE_MODE_VELOCITY,
        "delta": AE_FEATURE_MODE_VELOCITY,
        "deltas": AE_FEATURE_MODE_VELOCITY,
        "velocity_commanded": AE_FEATURE_MODE_VELOCITY_COMMANDED,
        "commanded_velocity": AE_FEATURE_MODE_VELOCITY_COMMANDED,
        "velocity_with_root": AE_FEATURE_MODE_VELOCITY_COMMANDED,
        "velocity_with_command": AE_FEATURE_MODE_VELOCITY_COMMANDED,
    }
    if raw not in aliases:
        raise ValueError(f"Unsupported AE feature mode {value!r}; expected one of {AE_FEATURE_MODE_VALUES!r}")
    return aliases[raw]


def normalized_ae_score_scope(value: object | None) -> str:
    raw = str(AE_SCORE_SCOPE_OUTPUT if value is None else value).strip().lower()
    aliases = {
        "": AE_SCORE_SCOPE_OUTPUT,
        "output": AE_SCORE_SCOPE_OUTPUT,
        "last_output": AE_SCORE_SCOPE_OUTPUT,
        "current_output": AE_SCORE_SCOPE_OUTPUT,
        "output_only": AE_SCORE_SCOPE_OUTPUT,
        "full": AE_SCORE_SCOPE_FULL_WINDOW,
        "full_window": AE_SCORE_SCOPE_FULL_WINDOW,
        "window": AE_SCORE_SCOPE_FULL_WINDOW,
        "all": AE_SCORE_SCOPE_FULL_WINDOW,
        "all_features": AE_SCORE_SCOPE_FULL_WINDOW,
    }
    if raw not in aliases:
        raise ValueError(f"Unsupported AE score scope {value!r}; expected one of {AE_SCORE_SCOPE_VALUES!r}")
    return aliases[raw]


def transform_ae_feature_space(features: torch.Tensor, schema: dict[str, object]) -> torch.Tensor:
    """Map controller IO rows into the AE training/scoring feature space."""
    mode = normalized_ae_feature_mode(schema.get("ae_feature_mode", AE_FEATURE_MODE_POSE))
    if mode == AE_FEATURE_MODE_POSE:
        return features
    if mode not in {AE_FEATURE_MODE_VELOCITY, AE_FEATURE_MODE_VELOCITY_COMMANDED}:
        raise ValueError(f"Unsupported AE feature mode {mode!r}")

    pose_dim = int(schema["pose_dim"])
    output_dim = int(schema["output_dim"])
    input_dim = int(schema["input_dim"])
    input_root_end = int(schema["input_root_end"])
    scale = max(float(schema.get("pose_delta_scale_final", 1.0)), 1e-8)
    y = torch.zeros_like(features)
    for offset in temporal_frame_offsets(schema):
        base = offset
        cur_start = base
        cur_end = cur_start + pose_dim
        prev_start = cur_end
        prev_end = prev_start + pose_dim
        out_start = base + input_dim
        out_end = out_start + output_dim

        cur = features[:, cur_start:cur_end]
        prev = features[:, prev_start:prev_end]
        out = features[:, out_start:out_end]
        comparable = min(pose_dim, output_dim)

        y[:, cur_start:cur_end] = (cur - prev) / scale
        y[:, out_start : out_start + comparable] = (out[:, :comparable] - cur[:, :comparable]) / scale
        if mode == AE_FEATURE_MODE_VELOCITY_COMMANDED:
            # Keep every non-pose conditioning feature: existing pelvis/payload velocities
            # plus current/future root-motion command features.
            y[:, base + prev_end : base + input_root_end] = features[:, base + prev_end : base + input_root_end]
    return y


def build_temporal_features(
    raw: torch.Tensor,
    clip_ids: torch.Tensor,
    cur_indices: torch.Tensor,
    base_schema: dict[str, object],
    frames: int,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, dict[str, object]]:
    frames = max(1, int(frames))
    schema = temporal_feature_schema(base_schema, frames)
    if frames == 1:
        return raw, clip_ids, cur_indices, schema

    chunks: list[torch.Tensor] = []
    clip_chunks: list[torch.Tensor] = []
    idx_chunks: list[torch.Tensor] = []
    for clip_id in clip_ids.unique(sorted=True).tolist():
        rows = (clip_ids == int(clip_id)).nonzero(as_tuple=False).flatten()
        order = torch.argsort(cur_indices.index_select(0, rows))
        rows = rows.index_select(0, order)
        idx = cur_indices.index_select(0, rows)
        if rows.numel() < frames:
            continue
        for end in range(frames - 1, int(rows.numel())):
            idx_window = idx[end - frames + 1 : end + 1]
            if not bool(torch.all(idx_window[1:] - idx_window[:-1] == 1)):
                continue
            row_window = rows[end - frames + 1 : end + 1]
            chunks.append(raw.index_select(0, row_window).reshape(1, -1))
            clip_chunks.append(torch.tensor([int(clip_id)], dtype=torch.long))
            idx_chunks.append(idx[end].reshape(1).to(dtype=torch.long))
    if not chunks:
        raise ValueError(f"No valid {frames}-frame AE windows found.")
    return torch.cat(chunks), torch.cat(clip_chunks), torch.cat(idx_chunks), schema


@torch.no_grad()
def collect_controller_features(
    clips: list[tl.MotionClip],
    locomotion_cfg: tl.TrainConfig,
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, dict[str, object]]:
    chunks: list[torch.Tensor] = []
    clip_chunks: list[torch.Tensor] = []
    idx_chunks: list[torch.Tensor] = []
    schema = feature_schema(clips[0], locomotion_cfg)
    for clip_id, clip in enumerate(clips):
        cur_idx = valid_current_indices(clip, locomotion_cfg, device)
        if cur_idx.numel() == 0:
            continue
        prev_idx = cur_idx - 1 if clip.cyclic_animation else (cur_idx - 1).clamp_min(0)
        target_idx = cur_idx + 1
        prev_pose = tl.get_pose_from_clip(clip, prev_idx, device)
        cur_pose = tl.get_pose_from_clip(clip, cur_idx, device)
        target_pose = tl.get_pose_from_clip(clip, target_idx, device)
        controller_input = tl.build_input(clip, prev_idx, cur_idx, prev_pose, cur_pose, locomotion_cfg, device)
        cur_root_pos, cur_root_rot, _cur_yaw, _cur_heading = tl.root_state(clip, cur_idx, locomotion_cfg, device)
        target_root_pos, target_root_rot, _target_yaw, _target_heading = tl.root_state(
            clip, target_idx, locomotion_cfg, device
        )
        if tl.output_reference_uses_current_root():
            target_pose = tl.rebase_pose_root(
                clip,
                target_pose,
                target_root_pos,
                target_root_rot,
                cur_root_pos,
                cur_root_rot,
            )
        target_output = tl.pose_target_output(target_pose)
        chunks.append(torch.cat((controller_input, target_output), dim=-1).detach().cpu())
        clip_chunks.append(torch.full((cur_idx.numel(),), clip_id, dtype=torch.long))
        idx_chunks.append(cur_idx.detach().cpu())
    if not chunks:
        raise ValueError("No valid AE feature rows found.")
    return torch.cat(chunks), torch.cat(clip_chunks), torch.cat(idx_chunks), schema


def split_rows(row_count: int, val_fraction: float, seed: int, device: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
    generator = torch.Generator(device="cpu").manual_seed(int(seed))
    order = torch.randperm(int(row_count), generator=generator)
    if row_count <= 1 or float(val_fraction) <= 0.0:
        return order.to(device), torch.empty((0,), dtype=torch.long, device=device)
    val_count = max(1, int(round(row_count * float(val_fraction))))
    val_count = min(val_count, int(row_count) - 1)
    val = order[:val_count].to(device)
    train = order[val_count:].to(device)
    if train.numel() == 0:
        train = val
    return train, val


def normalize_features(features: torch.Tensor, std_floor: float) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    mean = features.mean(dim=0)
    std = features.std(dim=0, unbiased=False).clamp_min(float(std_floor))
    return (features - mean) / std, mean, std


def normalize_features_binary_mixture(
    features: torch.Tensor,
    secondary_mask: torch.Tensor,
    secondary_probability: float,
    std_floor: float,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    secondary_probability = float(secondary_probability)
    if not 0.0 < secondary_probability < 1.0:
        raise ValueError("Binary-mixture normalization probability must be strictly between 0 and 1.")
    secondary_mask = secondary_mask.to(device=features.device, dtype=torch.bool)
    # Compute mixture moments in float64. Several root-relative channels have
    # large non-zero means, so E[x^2] - E[x]^2 in float32 measurably understates
    # their variance and breaks the requested 50/50 normalization contract.
    work = features.to(dtype=torch.float64)
    primary = work[~secondary_mask]
    secondary = work[secondary_mask]
    if primary.numel() == 0 or secondary.numel() == 0:
        raise ValueError("Binary-mixture normalization requires non-empty primary and secondary rows.")
    primary_weight = 1.0 - secondary_probability
    mean = primary_weight * primary.mean(dim=0) + secondary_probability * secondary.mean(dim=0)
    variance = (
        primary_weight * (primary - mean).square().mean(dim=0)
        + secondary_probability * (secondary - mean).square().mean(dim=0)
    )
    std = variance.clamp_min(0.0).sqrt().clamp_min(float(std_floor))
    mean = mean.to(dtype=features.dtype)
    std = std.to(dtype=features.dtype)
    return (features - mean) / std, mean, std


def normalize_features_equal_groups(
    features: torch.Tensor,
    group_ids: torch.Tensor,
    group_count: int,
    std_floor: float,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Normalize for an equal mixture of groups, independent of raw row counts."""
    group_count = int(group_count)
    if features.ndim != 2:
        raise ValueError(f"Expected a rank-2 feature matrix, got shape {tuple(features.shape)}.")
    if group_count <= 0:
        raise ValueError("Equal-group normalization requires at least one group.")
    group_ids = group_ids.to(device=features.device, dtype=torch.long)
    if group_ids.numel() != features.shape[0]:
        raise ValueError("Feature rows and equal-group ids must have the same length.")

    # Use centered float64 moments. This avoids cancellation on root-relative
    # channels with large means and gives every group exactly 1 / group_count
    # of the normalization distribution.
    work = features.to(dtype=torch.float64)
    groups: list[torch.Tensor] = []
    for group_index in range(group_count):
        group = work[group_ids == group_index]
        if group.numel() == 0:
            raise ValueError(f"Equal-group normalization group {group_index} has no rows.")
        groups.append(group)
    mean = torch.stack([group.mean(dim=0) for group in groups], dim=0).mean(dim=0)
    variance = torch.stack([(group - mean).square().mean(dim=0) for group in groups], dim=0).mean(dim=0)
    std = variance.clamp_min(0.0).sqrt().clamp_min(float(std_floor))
    mean = mean.to(dtype=features.dtype)
    std = std.to(dtype=features.dtype)
    return (features - mean) / std, mean, std


def batch_indices(rows: torch.Tensor, batch_size: int) -> torch.Tensor:
    if rows.numel() <= int(batch_size):
        return rows.index_select(0, torch.randperm(rows.numel(), device=rows.device))
    choice = torch.randint(0, rows.numel(), (int(batch_size),), device=rows.device)
    return rows.index_select(0, choice)


def binary_mixture_batch_indices(
    primary_rows: torch.Tensor,
    secondary_rows: torch.Tensor,
    batch_size: int,
    secondary_probability: float,
) -> torch.Tensor:
    batch_size = int(batch_size)
    secondary_probability = float(secondary_probability)
    if primary_rows.numel() == 0 or secondary_rows.numel() == 0:
        raise ValueError("Binary-mixture sampling requires non-empty primary and secondary row pools.")
    if not 0.0 <= secondary_probability <= 1.0:
        raise ValueError("Binary-mixture sampling probability must be in [0, 1].")
    secondary_count = int(round(batch_size * secondary_probability))
    primary_count = batch_size - secondary_count

    def sample(pool: torch.Tensor, count: int) -> torch.Tensor:
        if count <= 0:
            return pool.new_empty((0,), dtype=torch.long)
        choices = torch.randint(0, pool.numel(), (count,), device=pool.device)
        return pool.index_select(0, choices)

    rows = torch.cat((sample(primary_rows, primary_count), sample(secondary_rows, secondary_count)))
    return rows.index_select(0, torch.randperm(rows.numel(), device=rows.device))


def equal_group_batch_indices(group_rows: list[torch.Tensor], batch_size: int) -> torch.Tensor:
    """Sample an exactly equal number of rows from every group, with replacement."""
    group_count = len(group_rows)
    batch_size = int(batch_size)
    if group_count <= 0:
        raise ValueError("Equal-group sampling requires at least one group row pool.")
    if batch_size <= 0 or batch_size % group_count != 0:
        raise ValueError(
            f"Equal-group batch size {batch_size} must be positive and divisible by {group_count} groups."
        )
    samples_per_group = batch_size // group_count
    sampled: list[torch.Tensor] = []
    for group_index, pool in enumerate(group_rows):
        if pool.numel() == 0:
            raise ValueError(f"Equal-group sampling group {group_index} has no training rows.")
        choices = torch.randint(0, pool.numel(), (samples_per_group,), device=pool.device)
        sampled.append(pool.index_select(0, choices))
    rows = torch.cat(sampled, dim=0)
    return rows.index_select(0, torch.randperm(rows.numel(), device=rows.device))


def binary_mixture_score(
    values: torch.Tensor,
    secondary_mask: torch.Tensor,
    secondary_probability: float,
) -> tuple[float, float, float]:
    secondary_mask = secondary_mask.to(device=values.device, dtype=torch.bool)
    if values.numel() != secondary_mask.numel():
        raise ValueError("Score values and binary category mask must have the same length.")
    primary = values[~secondary_mask]
    secondary = values[secondary_mask]
    if primary.numel() == 0 or secondary.numel() == 0:
        raise ValueError("Binary-mixture scoring requires non-empty primary and secondary values.")
    primary_mean = float(primary.mean().detach().cpu())
    secondary_mean = float(secondary.mean().detach().cpu())
    mixed = (1.0 - float(secondary_probability)) * primary_mean + float(secondary_probability) * secondary_mean
    return float(mixed), primary_mean, secondary_mean


def equal_group_score(
    values: torch.Tensor,
    group_ids: torch.Tensor,
    group_count: int,
) -> tuple[float, list[float]]:
    """Return the unweighted mean of per-group means and each group mean."""
    group_count = int(group_count)
    group_ids = group_ids.to(device=values.device, dtype=torch.long)
    if values.numel() != group_ids.numel():
        raise ValueError("Score values and equal-group ids must have the same length.")
    group_scores: list[float] = []
    for group_index in range(group_count):
        group_values = values[group_ids == group_index]
        if group_values.numel() == 0:
            raise ValueError(f"Equal-group scoring group {group_index} has no values.")
        group_scores.append(float(group_values.mean().detach().cpu()))
    return float(sum(group_scores) / group_count), group_scores


def attack_clip_mask_from_manifest(
    specs: list[tuple[Path, bool]],
    manifest_path: Path,
) -> torch.Tensor:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = payload.get("files")
    if not isinstance(entries, list):
        raise ValueError(f"Sampling manifest has no files list: {manifest_path}")
    categories: dict[Path, str] = {}
    for entry in entries:
        if not isinstance(entry, dict) or "file" not in entry or "category" not in entry:
            raise ValueError(f"Malformed file entry in sampling manifest: {entry!r}")
        path = resolve_path(str(entry["file"])).resolve()
        if path in categories:
            raise ValueError(f"Duplicate file in sampling manifest: {path}")
        categories[path] = str(entry["category"])
    missing = [path for path, _cyclic in specs if path.resolve() not in categories]
    if missing:
        raise ValueError(f"Sampling manifest is missing {len(missing)} loaded clips; first missing: {missing[0]}")
    mask = torch.tensor(
        [categories[path.resolve()] == "gt_attack" for path, _cyclic in specs],
        dtype=torch.bool,
    )
    if not bool(mask.any()) or bool(mask.all()):
        raise ValueError("Sampling manifest must identify both locomotion and gt_attack clips.")
    return mask


def clip_groups_from_manifest(
    specs: list[tuple[Path, bool]],
    manifest_path: Path,
    group_field: str,
) -> tuple[torch.Tensor, list[str]]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    contract = payload.get("sampling_contract")
    entries = payload.get("files")
    if not isinstance(contract, dict) or not isinstance(contract.get("groups"), list):
        raise ValueError(f"Group sampling manifest has no sampling_contract.groups: {manifest_path}")
    if not isinstance(entries, list):
        raise ValueError(f"Group sampling manifest has no files list: {manifest_path}")
    group_names = [str(name) for name in contract["groups"]]
    if not group_names or len(set(group_names)) != len(group_names):
        raise ValueError(f"Sampling group names must be non-empty and unique: {group_names!r}")
    group_index = {name: index for index, name in enumerate(group_names)}
    groups_by_path: dict[Path, int] = {}
    for entry in entries:
        if not isinstance(entry, dict) or "file" not in entry or group_field not in entry:
            raise ValueError(f"Malformed grouped file entry in {manifest_path}: {entry!r}")
        path = resolve_path(str(entry["file"])).resolve()
        if path in groups_by_path:
            raise ValueError(f"Duplicate file in group sampling manifest: {path}")
        name = str(entry[group_field])
        if name not in group_index:
            raise ValueError(f"Unknown sampling group {name!r} for {path}; expected one of {group_names!r}")
        groups_by_path[path] = group_index[name]
    missing_paths = [path for path, _cyclic in specs if path.resolve() not in groups_by_path]
    if missing_paths:
        raise ValueError(
            f"Group sampling manifest is missing {len(missing_paths)} loaded clips; first missing: {missing_paths[0]}"
        )
    clip_group_ids = torch.tensor([groups_by_path[path.resolve()] for path, _cyclic in specs], dtype=torch.long)
    present = set(int(value) for value in clip_group_ids.tolist())
    missing_groups = [group_names[index] for index in range(len(group_names)) if index not in present]
    if missing_groups:
        raise ValueError(f"No loaded clips belong to sampling groups: {missing_groups!r}")
    return clip_group_ids, group_names


def clip_conditioning_from_manifest(
    specs: list[tuple[Path, bool]],
    manifest_path: Path,
) -> tuple[torch.Tensor, list[str]]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    contract = payload.get("conditioning_contract")
    entries = payload.get("files")
    if not isinstance(contract, dict) or not isinstance(contract.get("feature_names"), list):
        raise ValueError(f"Conditioning manifest has no conditioning_contract.feature_names: {manifest_path}")
    if not isinstance(entries, list):
        raise ValueError(f"Conditioning manifest has no files list: {manifest_path}")
    feature_names = [str(name) for name in contract["feature_names"]]
    if not feature_names or len(set(feature_names)) != len(feature_names):
        raise ValueError(f"Conditioning feature names must be non-empty and unique: {feature_names!r}")
    vectors: dict[Path, list[float]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or "file" not in entry or not isinstance(entry.get("conditioning"), dict):
            raise ValueError(f"Malformed conditioned file entry in {manifest_path}: {entry!r}")
        path = resolve_path(str(entry["file"])).resolve()
        if path in vectors:
            raise ValueError(f"Duplicate file in conditioning manifest: {path}")
        values = entry["conditioning"]
        missing = [name for name in feature_names if name not in values]
        extra = sorted(set(str(name) for name in values) - set(feature_names))
        if missing or extra:
            raise ValueError(f"Conditioning fields mismatch for {path}: missing={missing}, extra={extra}")
        vector = [float(values[name]) for name in feature_names]
        if not all(math.isfinite(value) for value in vector):
            raise ValueError(f"Non-finite conditioning values for {path}: {vector!r}")
        vectors[path] = vector
    missing_paths = [path for path, _cyclic in specs if path.resolve() not in vectors]
    if missing_paths:
        raise ValueError(
            f"Conditioning manifest is missing {len(missing_paths)} loaded clips; first missing: {missing_paths[0]}"
        )
    matrix = torch.tensor([vectors[path.resolve()] for path, _cyclic in specs], dtype=torch.float32)
    return matrix, feature_names


def lr_for_step(step: int, total_steps: int, base_lr: float) -> float:
    progress = float(max(0, step - 1)) / float(max(1, total_steps - 1))
    if progress >= 0.9:
        return float(base_lr) * 0.1
    if progress >= 0.7:
        return float(base_lr) * 0.3
    return float(base_lr)


def set_lr(optimizer: torch.optim.Optimizer, lr: float) -> None:
    for group in optimizer.param_groups:
        group["lr"] = float(lr)


def parse_float_list(text: str) -> list[float]:
    values: list[float] = []
    for raw in str(text or "").replace(";", ",").split(","):
        part = raw.strip()
        if not part:
            continue
        values.append(float(part))
    if not values:
        raise ValueError("Expected at least one float value.")
    return values


def parse_int_list(text: str) -> list[int]:
    values: list[int] = []
    for raw in str(text or "").replace(";", ",").split(","):
        part = raw.strip()
        if not part:
            continue
        values.append(int(part))
    if not values:
        raise ValueError("Expected at least one integer value.")
    return values


def row_mse(model: nn.Module, x: torch.Tensor, batch_size: int = 8192) -> torch.Tensor:
    raise RuntimeError("row_mse requires schema; call masked_output_row_mse instead.")


def score_aligned_output_mask(schema: dict[str, object], device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    total_dim = int(schema["total_dim"])
    scope = normalized_ae_score_scope(schema.get("ae_score_scope", AE_SCORE_SCOPE_OUTPUT))
    if scope == AE_SCORE_SCOPE_FULL_WINDOW:
        return torch.ones((total_dim,), dtype=dtype, device=device)
    input_dim = int(schema["input_dim"])
    output_dim = int(schema["output_dim"])
    base_total = int(schema.get("base_total_dim", total_dim))
    frames = max(1, int(schema.get("window_frames", 1)))
    output_start = (frames - 1) * base_total + input_dim
    output_end = output_start + output_dim
    mask = torch.zeros((total_dim,), dtype=dtype, device=device)
    mask[output_start:output_end] = 1.0
    return mask


def masked_output_row_mse(
    model: nn.Module,
    x: torch.Tensor,
    schema: dict[str, object],
    batch_size: int = 8192,
) -> torch.Tensor:
    return masked_output_row_mse_to_target(model, x, x, schema, batch_size=batch_size)


def masked_output_row_mse_to_target(
    model: nn.Module,
    model_input: torch.Tensor,
    target: torch.Tensor,
    schema: dict[str, object],
    batch_size: int = 8192,
) -> torch.Tensor:
    mask = score_aligned_output_mask(schema, model_input.device, model_input.dtype).reshape(1, -1)
    denom = mask.sum().clamp_min(1.0)
    rows: list[torch.Tensor] = []
    for start in range(0, model_input.shape[0], int(batch_size)):
        part = model_input[start : start + int(batch_size)]
        target_part = target[start : start + int(batch_size)]
        recon = model(part)
        rows.append(((recon - target_part).square() * mask).sum(dim=-1) / denom)
    return torch.cat(rows, dim=0)


def alteration_mask(schema: dict[str, object], device: torch.device) -> torch.Tensor:
    mask = torch.ones((int(schema["total_dim"]),), dtype=torch.float32, device=device)
    for offset in temporal_frame_offsets(schema):
        mask[offset + int(schema["input_root_start"]) : offset + int(schema["input_root_end"])] = 0.0
    return mask


def make_statue_tier(x: torch.Tensor, schema: dict[str, object]) -> torch.Tensor:
    y = x.clone()
    pose_dim = int(schema["pose_dim"])
    output_dim = int(schema["output_dim"])
    output_start = int(schema["target_output_start"])
    for offset in temporal_frame_offsets(schema):
        y[:, offset + output_start : offset + output_start + output_dim] = x[:, offset : offset + pose_dim]
    return y


def make_bad_tiers(x: torch.Tensor, schema: dict[str, object]) -> dict[str, torch.Tensor]:
    mask = alteration_mask(schema, x.device).reshape(1, -1)
    perm = torch.randperm(x.shape[0], device=x.device)
    shuffled = x.clone()
    out_start = int(schema["target_output_start"])
    out_end = int(schema["target_output_end"])
    shuffled_source = x.index_select(0, perm)
    for offset in temporal_frame_offsets(schema):
        shuffled[:, offset + out_start : offset + out_end] = shuffled_source[:, offset + out_start : offset + out_end]
    noise = torch.randn_like(x)
    for offset in temporal_frame_offsets(schema):
        noise[:, offset + int(schema["input_root_start"]) : offset + int(schema["input_root_end"])] = x[
            :, offset + int(schema["input_root_start"]) : offset + int(schema["input_root_end"])
        ]
    return {
        "tier1_clean": x,
        "tier2_slight": x + 0.05 * torch.randn_like(x) * mask,
        "tier3_bad_statue": make_statue_tier(x, schema),
        "tier3_bad_shuffle_output": shuffled,
        "tier4_noise": noise,
    }


def add_denoise_noise(x: torch.Tensor, schema: dict[str, object], noise_std: float) -> torch.Tensor:
    noise_std = float(noise_std)
    if noise_std <= 0.0:
        return x
    mask = alteration_mask(schema, x.device).reshape(1, -1)
    return x + noise_std * torch.randn_like(x) * mask


@torch.no_grad()
def denoise_robust_report(
    model: nn.Module,
    clean_target: torch.Tensor,
    schema: dict[str, object],
    noise_stds: list[float],
    seeds: list[int],
    clean_weight: float,
    slight_weight: float,
    decent_weight: float,
    slight_max_std: float,
    decent_max_std: float,
) -> dict[str, float]:
    model.eval()
    mask = alteration_mask(schema, clean_target.device).reshape(1, -1).to(dtype=clean_target.dtype)
    means_by_std: dict[float, float] = {}
    p95_by_std: dict[float, float] = {}
    max_by_std: dict[float, float] = {}

    for raw_std in noise_stds:
        noise_std = float(raw_std)
        seed_values: list[torch.Tensor] = []
        eval_seeds = [0] if noise_std <= 0.0 else seeds
        for seed in eval_seeds:
            if noise_std <= 0.0:
                noisy_input = clean_target
            else:
                gen = torch.Generator(device=clean_target.device)
                gen.manual_seed(int(seed))
                noise = torch.randn(
                    clean_target.shape,
                    device=clean_target.device,
                    dtype=clean_target.dtype,
                    generator=gen,
                )
                noisy_input = clean_target + noise_std * noise * mask
            seed_values.append(masked_output_row_mse_to_target(model, noisy_input, clean_target, schema))
        values = torch.stack(seed_values, dim=0).mean(dim=0)
        means_by_std[noise_std] = float(values.mean().detach().cpu())
        p95_by_std[noise_std] = float(torch.quantile(values, 0.95).detach().cpu())
        max_by_std[noise_std] = float(values.max().detach().cpu())

    clean_values = [mean for std, mean in means_by_std.items() if std <= 0.0]
    slight_values = [mean for std, mean in means_by_std.items() if 0.0 < std <= float(slight_max_std)]
    decent_values = [mean for std, mean in means_by_std.items() if float(slight_max_std) < std <= float(decent_max_std)]
    clean_mean = sum(clean_values) / max(1, len(clean_values))
    slight_mean = sum(slight_values) / max(1, len(slight_values))
    decent_mean = sum(decent_values) / max(1, len(decent_values))
    robust_score = float(clean_weight) * clean_mean + float(slight_weight) * slight_mean + float(decent_weight) * decent_mean

    report = {
        "robust_clean_mean": float(clean_mean),
        "robust_slight_mean": float(slight_mean),
        "robust_decent_mean": float(decent_mean),
        "robust_score": float(robust_score),
    }
    for std in sorted(means_by_std):
        key = str(std).replace(".", "p")
        report[f"robust_noise_{key}_mean"] = means_by_std[std]
        report[f"robust_noise_{key}_p95"] = p95_by_std[std]
        report[f"robust_noise_{key}_max"] = max_by_std[std]
    model.train()
    return report


@torch.no_grad()
def diagnostic_report(
    model: nn.Module,
    x: torch.Tensor,
    schema: dict[str, object],
) -> dict[str, float]:
    model.eval()
    tiers = make_bad_tiers(x, schema)
    means: dict[str, float] = {}
    for name, tier in tiers.items():
        values = masked_output_row_mse(model, tier, schema)
        means[f"{name}_mean"] = float(values.mean().detach().cpu())
        means[f"{name}_p95"] = float(torch.quantile(values, 0.95).detach().cpu())
    clean = max(means["tier1_clean_mean"], 1e-12)
    for key in list(means):
        if key.endswith("_mean") and key != "tier1_clean_mean":
            means[f"{key[:-5]}_over_clean"] = means[key] / clean
    model.train()
    return means


def save_diagnostic_csv(path: Path, rows: list[dict[str, float | int]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(rows[-1].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def checkpoint_payload(
    model: SimpleAutoencoder,
    optimizer: torch.optim.Optimizer,
    cfg: SimpleAEConfig,
    locomotion_cfg: tl.TrainConfig,
    schema: dict[str, object],
    mean: torch.Tensor,
    std: torch.Tensor,
    step: int,
    best: float,
    metadata: dict[str, object],
) -> dict[str, object]:
    return {
        "kind": "simple_controller_io_autoencoder",
        "model": model.state_dict(),
        "optimizer": optimizer.state_dict(),
        "config": asdict(cfg),
        "locomotion_config": asdict(locomotion_cfg),
        "schema": schema,
        "mean": mean.detach().cpu(),
        "std": std.detach().cpu(),
        "step": int(step),
        "best": float(best),
        "metadata": metadata,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Simple IK controller-input plus output autoencoder.")
    parser.add_argument("--npz", default=None, help="NPZ file/folder or semicolon-separated NPZ list.")
    parser.add_argument("--periodic-folder", default=None, help="Periodic NPZ folder/list.")
    parser.add_argument("--nonperiodic-folder", default=None, help="Nonperiodic NPZ folder/list.")
    parser.add_argument("--body-mode", default=tl.BODY_MODE_LOWER, choices=tl.BODY_MODE_VALUES)
    parser.add_argument("--run-label", default="simple_ae")
    parser.add_argument("--window-frames", type=int, default=1, help="Consecutive transition rows per AE sample.")
    parser.add_argument("--feature-mode", default=AE_FEATURE_MODE_POSE, choices=AE_FEATURE_MODE_VALUES)
    parser.add_argument("--score-scope", default=AE_SCORE_SCOPE_OUTPUT, choices=AE_SCORE_SCOPE_VALUES)
    parser.add_argument("--denoise-noise-std", type=float, default=0.0, help="Normalized non-root input noise for denoising AE training.")
    parser.add_argument(
        "--sampling-manifest",
        default=None,
        help="Dataset manifest whose file categories identify gt_attack versus locomotion clips.",
    )
    parser.add_argument(
        "--conditioning-manifest",
        default=None,
        help="Dataset manifest providing one named conditioning vector per clip, appended once per AE window.",
    )
    parser.add_argument(
        "--balanced-group-manifest",
        default=None,
        help="Dataset manifest providing named groups that receive equal normalization, batch, and score weight.",
    )
    parser.add_argument(
        "--balanced-group-field",
        default="sampling_group",
        help="Per-file manifest field containing the balanced group name.",
    )
    parser.add_argument(
        "--attack-sample-probability",
        type=float,
        default=None,
        help="If set, sample and score gt_attack rows with this probability and locomotion with 1-p.",
    )
    parser.add_argument("--train-steps", type=int, default=TRAIN_STEPS)
    parser.add_argument(
        "--min-train-steps",
        type=int,
        default=None,
        help="Minimum steps before adaptive stopping is allowed. Defaults to --train-steps.",
    )
    parser.add_argument(
        "--lr-schedule-steps",
        type=int,
        default=None,
        help="Step horizon for AE LR decay. Defaults to --train-steps.",
    )
    parser.add_argument(
        "--stop-when-not-best-after-min",
        action="store_true",
        help="After --min-train-steps, stop at the first logged step that is not a new best.",
    )
    parser.add_argument("--latent-dim", type=int, default=LATENT_DIM)
    parser.add_argument("--hidden-dim", type=int, default=HIDDEN_DIM)
    parser.add_argument("--num-hidden-layers", type=int, default=NUM_HIDDEN_LAYERS)
    parser.add_argument("--learning-rate", type=float, default=LEARNING_RATE)
    parser.add_argument(
        "--best-selection",
        default="clean",
        choices=("clean", "robust_denoise"),
        help="Metric used to overwrite best.pt. robust_denoise compares noisy inputs back to clean targets.",
    )
    parser.add_argument("--robust-eval", action="store_true", help="Log robust denoising scores even when best-selection is clean.")
    parser.add_argument("--robust-noise-stds", default="0,0.01,0.025,0.05,0.075,0.1,0.15")
    parser.add_argument("--robust-noise-seeds", default="1234,2345,3456")
    parser.add_argument("--robust-clean-weight", type=float, default=0.20)
    parser.add_argument("--robust-slight-weight", type=float, default=0.50)
    parser.add_argument("--robust-decent-weight", type=float, default=0.30)
    parser.add_argument("--robust-slight-max-std", type=float, default=0.05)
    parser.add_argument("--robust-decent-max-std", type=float, default=0.15)
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        torch.set_float32_matmul_precision("high")
    torch.manual_seed(SEED)

    cfg = SimpleAEConfig()
    cfg.body_mode = tl.normalized_body_mode(args.body_mode)
    cfg.window_frames = max(1, int(args.window_frames))
    cfg.ae_feature_mode = normalized_ae_feature_mode(args.feature_mode)
    cfg.ae_score_scope = normalized_ae_score_scope(args.score_scope)
    cfg.denoise_noise_std = max(0.0, float(args.denoise_noise_std))
    cfg.train_steps = max(1, int(args.train_steps))
    min_train_steps = cfg.train_steps if args.min_train_steps is None else max(1, int(args.min_train_steps))
    min_train_steps = min(min_train_steps, cfg.train_steps)
    lr_schedule_steps = cfg.train_steps if args.lr_schedule_steps is None else max(1, int(args.lr_schedule_steps))
    cfg.latent_dim = max(1, int(args.latent_dim))
    cfg.hidden_dim = max(1, int(args.hidden_dim))
    cfg.num_hidden_layers = max(0, int(args.num_hidden_layers))
    cfg.learning_rate = float(args.learning_rate)
    robust_noise_stds = parse_float_list(args.robust_noise_stds)
    robust_noise_seeds = parse_int_list(args.robust_noise_seeds)
    use_robust_eval = bool(args.robust_eval or args.best_selection == "robust_denoise")
    attack_probability = None if args.attack_sample_probability is None else float(args.attack_sample_probability)
    if attack_probability is not None and not 0.0 < attack_probability < 1.0:
        raise ValueError("--attack-sample-probability must be strictly between 0 and 1.")
    if attack_probability is not None and not args.sampling_manifest:
        raise ValueError("--attack-sample-probability requires --sampling-manifest.")
    if attack_probability is None and args.sampling_manifest:
        raise ValueError("--sampling-manifest requires --attack-sample-probability.")
    if args.balanced_group_manifest and (args.sampling_manifest or attack_probability is not None):
        raise ValueError("Equal-group sampling and binary category sampling are mutually exclusive.")
    if args.balanced_group_manifest and args.best_selection != "clean":
        raise ValueError("Equal-group checkpoint selection currently requires --best-selection clean.")
    locomotion_cfg = make_locomotion_cfg(device, cfg.body_mode)
    specs = resolve_clip_specs(args.npz, args.periodic_folder, args.nonperiodic_folder)
    sampling_manifest = resolve_path(args.sampling_manifest) if args.sampling_manifest else None
    conditioning_manifest = resolve_path(args.conditioning_manifest) if args.conditioning_manifest else None
    group_sampling_manifest = resolve_path(args.balanced_group_manifest) if args.balanced_group_manifest else None
    attack_clip_mask = (
        attack_clip_mask_from_manifest(specs, sampling_manifest)
        if sampling_manifest is not None
        else torch.zeros((len(specs),), dtype=torch.bool)
    )
    clip_conditioning, conditioning_names = (
        clip_conditioning_from_manifest(specs, conditioning_manifest)
        if conditioning_manifest is not None
        else (None, [])
    )
    clip_group_ids, group_names = (
        clip_groups_from_manifest(specs, group_sampling_manifest, str(args.balanced_group_field))
        if group_sampling_manifest is not None
        else (None, [])
    )
    clips = load_clips(specs, locomotion_cfg)
    raw_features, clip_ids, cur_indices, base_schema = collect_controller_features(clips, locomotion_cfg, device)
    raw_row_count = int(raw_features.shape[0])
    raw_features, clip_ids, cur_indices, schema = build_temporal_features(
        raw_features,
        clip_ids,
        cur_indices,
        base_schema,
        cfg.window_frames,
    )
    schema["ae_feature_mode"] = cfg.ae_feature_mode
    schema["ae_score_scope"] = cfg.ae_score_scope
    raw_features = transform_ae_feature_space(raw_features, schema)
    if clip_conditioning is not None:
        conditioning_start = int(raw_features.shape[1])
        row_conditioning = clip_conditioning.index_select(0, clip_ids.to(dtype=torch.long))
        raw_features = torch.cat((raw_features, row_conditioning), dim=-1)
        schema["conditioning_scope"] = "window"
        schema["conditioning_names"] = list(conditioning_names)
        schema["conditioning_dim"] = len(conditioning_names)
        schema["conditioning_start"] = conditioning_start
        schema["conditioning_end"] = int(raw_features.shape[1])
        schema["conditioning_manifest"] = str(conditioning_manifest)
        schema["total_dim"] = int(raw_features.shape[1])
        schema["feature"] = f"{schema['feature']}_plus_window_conditioning"
    row_is_attack_cpu = attack_clip_mask.index_select(0, clip_ids.to(dtype=torch.long))
    row_group_ids_cpu = (
        clip_group_ids.index_select(0, clip_ids.to(dtype=torch.long))
        if clip_group_ids is not None
        else None
    )
    if row_group_ids_cpu is not None:
        x_cpu, mean_cpu, std_cpu = normalize_features_equal_groups(
            raw_features,
            row_group_ids_cpu,
            len(group_names),
            cfg.std_floor,
        )
    elif attack_probability is not None:
        x_cpu, mean_cpu, std_cpu = normalize_features_binary_mixture(
            raw_features,
            row_is_attack_cpu,
            attack_probability,
            cfg.std_floor,
        )
    else:
        x_cpu, mean_cpu, std_cpu = normalize_features(raw_features, cfg.std_floor)
    x = x_cpu.to(device)
    mean = mean_cpu.to(device)
    std = std_cpu.to(device)
    row_is_attack = row_is_attack_cpu.to(device=device)
    row_group_ids = row_group_ids_cpu.to(device=device) if row_group_ids_cpu is not None else None
    train_rows, val_rows = split_rows(x.shape[0], cfg.val_fraction, cfg.seed, device)
    if attack_probability is not None:
        train_is_attack = row_is_attack.index_select(0, train_rows)
        attack_train_rows = train_rows[train_is_attack]
        locomotion_train_rows = train_rows[~train_is_attack]
        if val_rows.numel() > 0:
            val_is_attack = row_is_attack.index_select(0, val_rows)
            attack_val_rows = val_rows[val_is_attack]
            locomotion_val_rows = val_rows[~val_is_attack]
        else:
            attack_val_rows = val_rows
            locomotion_val_rows = val_rows
    else:
        attack_train_rows = train_rows.new_empty((0,), dtype=torch.long)
        locomotion_train_rows = train_rows
        attack_val_rows = val_rows.new_empty((0,), dtype=torch.long)
        locomotion_val_rows = val_rows
    if row_group_ids is not None:
        group_train_rows = [
            train_rows[row_group_ids.index_select(0, train_rows) == group_index]
            for group_index in range(len(group_names))
        ]
        group_val_rows = [
            val_rows[row_group_ids.index_select(0, val_rows) == group_index]
            for group_index in range(len(group_names))
        ]
        empty_train_groups = [group_names[i] for i, rows in enumerate(group_train_rows) if rows.numel() == 0]
        empty_val_groups = (
            [group_names[i] for i, rows in enumerate(group_val_rows) if rows.numel() == 0]
            if val_rows.numel() > 0
            else []
        )
        if empty_train_groups or empty_val_groups:
            raise ValueError(
                f"Every balanced group needs train and validation rows; empty_train={empty_train_groups}, "
                f"empty_val={empty_val_groups}"
            )
        if cfg.batch_size % len(group_names) != 0:
            raise ValueError(
                f"Batch size {cfg.batch_size} must be divisible by {len(group_names)} balanced groups."
            )
    else:
        group_train_rows = []
        group_val_rows = []

    model = SimpleAutoencoder(x.shape[1], cfg).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg.learning_rate, weight_decay=cfg.weight_decay)

    run_id = ik_run_id(args.run_label)
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    writer = SummaryWriter(log_dir=str(run_dir / "tb"), flush_secs=1)
    metadata = {
        "npz_paths": [str(path) for path, _cyclic in specs],
        "npz_folders": [{"path": str(path.parent), "cyclic": bool(cyclic)} for path, cyclic in specs],
        "row_count": int(x.shape[0]),
        "single_frame_row_count": raw_row_count,
        "train_rows": int(train_rows.numel()),
        "val_rows": int(val_rows.numel()),
        "clip_count": int(len(clips)),
        "tensorboard_logdir": str(run_dir / "tb"),
        "body_mode": tl.normalized_body_mode(cfg.body_mode),
        "window_frames": int(cfg.window_frames),
        "ae_feature_mode": cfg.ae_feature_mode,
        "ae_score_scope": cfg.ae_score_scope,
        "denoise_noise_std": float(cfg.denoise_noise_std),
        "category_sampling": {
            "enabled": bool(attack_probability is not None),
            "manifest": str(sampling_manifest) if sampling_manifest is not None else None,
            "locomotion_probability": 1.0 - float(attack_probability) if attack_probability is not None else None,
            "attack_probability": float(attack_probability) if attack_probability is not None else None,
            "locomotion_rows": int((~row_is_attack).sum().item()),
            "attack_rows": int(row_is_attack.sum().item()),
            "locomotion_train_rows": int(locomotion_train_rows.numel()),
            "attack_train_rows": int(attack_train_rows.numel()),
            "normalization": "same binary probability mixture as batch sampling" if attack_probability is not None else "uniform rows",
            "checkpoint_score": "same binary probability mixture" if attack_probability is not None else "uniform rows",
        },
        "group_sampling": {
            "enabled": bool(row_group_ids is not None),
            "manifest": str(group_sampling_manifest) if group_sampling_manifest is not None else None,
            "field": str(args.balanced_group_field) if group_sampling_manifest is not None else None,
            "groups": list(group_names),
            "group_count": len(group_names),
            "probability_per_group": 1.0 / len(group_names) if group_names else None,
            "samples_per_group_per_batch": cfg.batch_size // len(group_names) if group_names else None,
            "clip_counts": {
                name: int((clip_group_ids == index).sum().item())
                for index, name in enumerate(group_names)
            } if clip_group_ids is not None else {},
            "row_counts": {
                name: int((row_group_ids == index).sum().item())
                for index, name in enumerate(group_names)
            } if row_group_ids is not None else {},
            "train_row_counts": {
                name: int(group_train_rows[index].numel())
                for index, name in enumerate(group_names)
            },
            "val_row_counts": {
                name: int(group_val_rows[index].numel())
                for index, name in enumerate(group_names)
            },
            "normalization": "equal mean over group distributions" if group_names else None,
            "checkpoint_score": "equal mean over per-group clean scores" if group_names else None,
        },
        "conditioning": {
            "enabled": bool(clip_conditioning is not None),
            "manifest": str(conditioning_manifest) if conditioning_manifest is not None else None,
            "scope": "one vector per temporal AE window" if clip_conditioning is not None else None,
            "feature_names": list(conditioning_names),
            "dimension": len(conditioning_names),
        },
        "single_frame_schema": base_schema,
        "adaptive_training": {
            "min_train_steps": int(min_train_steps),
            "max_train_steps": int(cfg.train_steps),
            "lr_schedule_steps": int(lr_schedule_steps),
            "stop_when_not_best_after_min": bool(args.stop_when_not_best_after_min),
        },
        "best_selection": str(args.best_selection),
        "robust_denoise_eval": {
            "enabled": bool(use_robust_eval),
            "noise_stds": [float(value) for value in robust_noise_stds],
            "seeds": [int(value) for value in robust_noise_seeds],
            "clean_weight": float(args.robust_clean_weight),
            "slight_weight": float(args.robust_slight_weight),
            "decent_weight": float(args.robust_decent_weight),
            "slight_max_std": float(args.robust_slight_max_std),
            "decent_max_std": float(args.robust_decent_max_std),
        },
    }
    config_payload = {
        "config": asdict(cfg),
        "locomotion_config": asdict(locomotion_cfg),
        "schema": schema,
        "metadata": metadata,
    }
    (run_dir / "config.json").write_text(json.dumps(config_payload, indent=2), encoding="utf-8")
    writer.add_text("config/json", f"```json\n{json.dumps(config_payload, indent=2)}\n```", 0)
    writer.add_scalar("run/started", 1.0, 0)
    writer.flush()
    refresh_tensorboard_async()

    print(
        f"simple_ae run={run_id} rows={x.shape[0]} raw_rows={raw_row_count} window={cfg.window_frames} dim={x.shape[1]} "
        f"train={train_rows.numel()} val={val_rows.numel()} tensorboard_logdir={run_dir / 'tb'}",
        flush=True,
    )
    if attack_probability is not None:
        print(
            f"category_sampling locomotion_rows={locomotion_train_rows.numel()} attack_rows={attack_train_rows.numel()} "
            f"locomotion_probability={1.0 - attack_probability:.3f} attack_probability={attack_probability:.3f} "
            f"batch_locomotion={cfg.batch_size - int(round(cfg.batch_size * attack_probability))} "
            f"batch_attack={int(round(cfg.batch_size * attack_probability))}",
            flush=True,
        )
    if row_group_ids is not None:
        print(
            f"group_sampling groups={len(group_names)} probability_per_group={1.0 / len(group_names):.6f} "
            f"samples_per_group_per_batch={cfg.batch_size // len(group_names)} "
            f"train_rows_min={min(rows.numel() for rows in group_train_rows)} "
            f"train_rows_max={max(rows.numel() for rows in group_train_rows)}",
            flush=True,
        )

    best = float("inf")
    best_step = 0
    clean_best = float("inf")
    clean_best_step = 0
    robust_best = float("inf")
    robust_best_step = 0
    actual_step = 0
    diagnostic_rows: list[dict[str, float | int]] = []
    start_time = time.perf_counter()
    for step in range(1, cfg.train_steps + 1):
        actual_step = int(step)
        lr = lr_for_step(step, lr_schedule_steps, cfg.learning_rate)
        set_lr(optimizer, lr)
        rows = (
            equal_group_batch_indices(group_train_rows, cfg.batch_size)
            if row_group_ids is not None
            else binary_mixture_batch_indices(
                locomotion_train_rows,
                attack_train_rows,
                cfg.batch_size,
                attack_probability,
            )
            if attack_probability is not None
            else batch_indices(train_rows, cfg.batch_size)
        )
        batch = x.index_select(0, rows)
        model_input = add_denoise_noise(batch, schema, cfg.denoise_noise_std)
        recon = model(model_input)
        batch_mask = score_aligned_output_mask(schema, batch.device, batch.dtype).reshape(1, -1)
        batch_denom = batch_mask.sum().clamp_min(1.0)
        loss = ((recon - batch).square() * batch_mask).sum(dim=-1).mean() / batch_denom
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()

        if step == 1 or step % LOG_EVERY == 0 or step == cfg.train_steps:
            with torch.no_grad():
                model.eval()
                train_values = masked_output_row_mse(model, x.index_select(0, train_rows), schema)
                uniform_train_score = float(train_values.mean().detach().cpu())
                if row_group_ids is not None:
                    train_score, group_train_scores = equal_group_score(
                        train_values,
                        row_group_ids.index_select(0, train_rows),
                        len(group_names),
                    )
                    locomotion_train_score = float("nan")
                    attack_train_score = float("nan")
                elif attack_probability is not None:
                    train_score, locomotion_train_score, attack_train_score = binary_mixture_score(
                        train_values,
                        row_is_attack.index_select(0, train_rows),
                        attack_probability,
                    )
                else:
                    train_score = uniform_train_score
                    locomotion_train_score = uniform_train_score
                    attack_train_score = float("nan")
                    group_train_scores = []
                if val_rows.numel() > 0:
                    val_values = masked_output_row_mse(model, x.index_select(0, val_rows), schema)
                    uniform_val_score = float(val_values.mean().detach().cpu())
                    if row_group_ids is not None:
                        val_score, group_val_scores = equal_group_score(
                            val_values,
                            row_group_ids.index_select(0, val_rows),
                            len(group_names),
                        )
                        locomotion_val_score = float("nan")
                        attack_val_score = float("nan")
                    elif attack_probability is not None:
                        val_score, locomotion_val_score, attack_val_score = binary_mixture_score(
                            val_values,
                            row_is_attack.index_select(0, val_rows),
                            attack_probability,
                        )
                    else:
                        val_score = uniform_val_score
                        locomotion_val_score = uniform_val_score
                        attack_val_score = float("nan")
                        group_val_scores = []
                else:
                    val_score = train_score
                    uniform_val_score = uniform_train_score
                    locomotion_val_score = locomotion_train_score
                    attack_val_score = attack_train_score
                    group_val_scores = list(group_train_scores)
                report = diagnostic_report(model, x.index_select(0, val_rows if val_rows.numel() > 0 else train_rows), schema)
                model.train()
            clean_score = val_score if val_rows.numel() > 0 else train_score
            clean_improved = clean_score < clean_best
            if clean_improved:
                clean_best = clean_score
                clean_best_step = int(step)
                if args.best_selection != "clean":
                    path = checkpoint_path(run_dir, run_id, "clean_best")
                    path.parent.mkdir(parents=True, exist_ok=True)
                    clean_metadata = dict(metadata)
                    clean_metadata["checkpoint_selection"] = {
                        "kind": "clean",
                        "score": float(clean_best),
                        "step": int(step),
                    }
                    torch.save(
                        checkpoint_payload(model, optimizer, cfg, locomotion_cfg, schema, mean, std, step, clean_best, clean_metadata),
                        path,
                    )
            robust_report: dict[str, float] = {}
            robust_score = float("nan")
            if use_robust_eval:
                robust_report = denoise_robust_report(
                    model,
                    x.index_select(0, val_rows if val_rows.numel() > 0 else train_rows),
                    schema,
                    robust_noise_stds,
                    robust_noise_seeds,
                    float(args.robust_clean_weight),
                    float(args.robust_slight_weight),
                    float(args.robust_decent_weight),
                    float(args.robust_slight_max_std),
                    float(args.robust_decent_max_std),
                )
                robust_score = float(robust_report["robust_score"])
                if robust_score < robust_best:
                    robust_best = robust_score
                    robust_best_step = int(step)
                    path = checkpoint_path(run_dir, run_id, "robust_best")
                    path.parent.mkdir(parents=True, exist_ok=True)
                    robust_metadata = dict(metadata)
                    robust_metadata["checkpoint_selection"] = {
                        "kind": "robust_denoise",
                        "score": float(robust_best),
                        "step": int(step),
                    }
                    torch.save(
                        checkpoint_payload(model, optimizer, cfg, locomotion_cfg, schema, mean, std, step, robust_best, robust_metadata),
                        path,
                    )
            best_score = robust_score if args.best_selection == "robust_denoise" else clean_score
            improved = best_score < best
            if improved:
                best = best_score
                best_step = int(step)
                path = checkpoint_path(run_dir, run_id, "best")
                path.parent.mkdir(parents=True, exist_ok=True)
                best_metadata = dict(metadata)
                best_metadata["checkpoint_selection"] = {
                    "kind": str(args.best_selection),
                    "score": float(best),
                    "step": int(step),
                    "clean_score": float(clean_score),
                    "locomotion_clean_score": float(locomotion_val_score) if attack_probability is not None else None,
                    "attack_clean_score": float(attack_val_score) if attack_probability is not None else None,
                    "group_clean_scores": {
                        name: float(group_val_scores[index])
                        for index, name in enumerate(group_names)
                    } if group_names else None,
                    "robust_score": float(robust_score) if use_robust_eval else None,
                }
                torch.save(
                    checkpoint_payload(model, optimizer, cfg, locomotion_cfg, schema, mean, std, step, best, best_metadata),
                    path,
                )
            elapsed = time.perf_counter() - start_time
            writer.add_scalar("loss/train_recon", train_score, step)
            writer.add_scalar("loss/val_recon", val_score, step)
            writer.add_scalar("loss/train_recon_uniform_rows", uniform_train_score, step)
            writer.add_scalar("loss/val_recon_uniform_rows", uniform_val_score, step)
            if attack_probability is not None:
                writer.add_scalar("category/locomotion_train_recon", locomotion_train_score, step)
                writer.add_scalar("category/attack_train_recon", attack_train_score, step)
                writer.add_scalar("category/locomotion_val_recon", locomotion_val_score, step)
                writer.add_scalar("category/attack_val_recon", attack_val_score, step)
                writer.add_scalar("category/attack_sample_probability", attack_probability, step)
            if row_group_ids is not None:
                for group_index, group_name in enumerate(group_names):
                    writer.add_scalar(f"group/{group_name}_train_recon", group_train_scores[group_index], step)
                    writer.add_scalar(f"group/{group_name}_val_recon", group_val_scores[group_index], step)
            writer.add_scalar("loss/best", best, step)
            writer.add_scalar("loss/clean_best", clean_best, step)
            if use_robust_eval:
                writer.add_scalar("loss/robust_best", robust_best, step)
            writer.add_scalar("time/elapsed_s", elapsed, step)
            for key, value in report.items():
                writer.add_scalar(f"synthetic/{key}", value, step)
            for key, value in robust_report.items():
                writer.add_scalar(f"robust/{key}", value, step)
            row = {
                "step": step,
                "train_recon": train_score,
                "val_recon": val_score,
                "uniform_train_recon": uniform_train_score,
                "uniform_val_recon": uniform_val_score,
                "locomotion_train_recon": locomotion_train_score,
                "attack_train_recon": attack_train_score,
                "locomotion_val_recon": locomotion_val_score,
                "attack_val_recon": attack_val_score,
                "best": best,
                "best_step": best_step,
                "best_selection": str(args.best_selection),
                "clean_best": clean_best,
                "clean_best_step": clean_best_step,
                "robust_best": robust_best,
                "robust_best_step": robust_best_step,
                **report,
                **robust_report,
            }
            if row_group_ids is not None:
                row.update({f"group_{name}_train_recon": group_train_scores[index] for index, name in enumerate(group_names)})
                row.update({f"group_{name}_val_recon": group_val_scores[index] for index, name in enumerate(group_names)})
            diagnostic_rows.append(row)
            save_diagnostic_csv(run_dir / "synthetic_diagnostics.csv", diagnostic_rows)
            robust_text = (
                f" robust={robust_score:.6g} robust_best={robust_best:.6g} robust_best_step={robust_best_step:05d}"
                if use_robust_eval
                else ""
            )
            category_text = (
                f"groups_min={min(group_val_scores):.6g} groups_max={max(group_val_scores):.6g} "
                if row_group_ids is not None
                else f"locomotion={locomotion_val_score:.6g} attack={attack_val_score:.6g} "
            )
            print(
                f"step={step:05d} train={train_score:.6g} val={val_score:.6g} best={best:.6g} "
                f"best_step={best_step:05d} "
                f"{category_text}"
                f"bad_statue_x={report['tier3_bad_statue_over_clean']:.2f} "
                f"bad_shuffle_x={report['tier3_bad_shuffle_output_over_clean']:.2f} "
                f"noise_x={report['tier4_noise_over_clean']:.2f}{robust_text} lr={lr:.3g} elapsed_s={elapsed:.1f}",
                flush=True,
            )
            if (
                args.stop_when_not_best_after_min
                and step >= min_train_steps
                and not improved
                and step < cfg.train_steps
            ):
                print(
                    f"adaptive_stop step={step:05d} min_train_steps={min_train_steps} "
                    f"best_step={best_step:05d} best={best:.6g}",
                    flush=True,
                )
                break

    last = checkpoint_path(run_dir, run_id, "last")
    last_metadata = dict(metadata)
    last_metadata["checkpoint_selection"] = {
        "kind": "last",
        "selected_best_kind": str(args.best_selection),
        "selected_best": float(best),
        "selected_best_step": int(best_step),
        "clean_best": float(clean_best),
        "clean_best_step": int(clean_best_step),
        "robust_best": float(robust_best),
        "robust_best_step": int(robust_best_step),
    }
    torch.save(checkpoint_payload(model, optimizer, cfg, locomotion_cfg, schema, mean, std, actual_step, best, last_metadata), last)
    writer.close()
    print(f"saved {last}", flush=True)


if __name__ == "__main__":
    main()
