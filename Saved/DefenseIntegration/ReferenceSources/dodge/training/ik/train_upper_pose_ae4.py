from __future__ import annotations

"""Condition-only absolute upper-pose predictor for upper locomotion.

AE4 never sees an upper-body pose.  It receives three consecutive complete
lower-body+pelvis poses, the current/future root window, sword mode, and gaze,
then predicts the next absolute upper-body pose in the next actual-root frame.
"""

import argparse
import hashlib
import json
import math
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import torch
from torch.utils.tensorboard import SummaryWriter

try:
    from .bootstrap import PROJECT_ROOT, ensure_paths
    from . import ik_core as tl
    from . import train_upper_pose_autoencoder as upper_data
    from . import train_upper_pose_controller as runtime_data
except ImportError:
    from bootstrap import PROJECT_ROOT, ensure_paths
    import ik_core as tl
    import train_upper_pose_autoencoder as upper_data
    import train_upper_pose_controller as runtime_data


ensure_paths()

RUNS_ROOT = PROJECT_ROOT / "training" / "runs"
CACHE_ROOT = RUNS_ROOT / "cache" / "upper_pose_ae4"
POINTER_PATH = PROJECT_ROOT / "training" / "ik" / "official_upper_pose_ae4.json"
KIND = "upper_pose_condition_absolute_ae4"
CACHE_VERSION = "upper_pose_condition_absolute_ae4_v3_selectable_corpus"
CORPUS_SCOPES = ("omni", "full")

LOWER_CONDITION_BONES = (
    "pelvis",
    "thigh_l",
    "calf_l",
    "foot_l",
    "ball_l",
    "thigh_r",
    "calf_r",
    "foot_r",
    "ball_r",
)
UPPER_TARGET_BONES = (
    "spine_01",
    "spine_02",
    "spine_03",
    "spine_04",
    "spine_05",
    "neck_01",
    "neck_02",
    "head",
    "clavicle_l",
    "upperarm_l",
    "lowerarm_l",
    "hand_l",
    "clavicle_r",
    "upperarm_r",
    "lowerarm_r",
    "hand_r",
)
TRANSFORM_DIM = 9
LOWER_FRAME_DIM = len(LOWER_CONDITION_BONES) * TRANSFORM_DIM
ROOT_DIM = upper_data.ROOT_DIM
MODE_DIM = 1
GAZE_DIM = upper_data.GAZE_DIM
INPUT_DIM = LOWER_FRAME_DIM * 3 + ROOT_DIM + MODE_DIM + GAZE_DIM
OUTPUT_DIM = len(UPPER_TARGET_BONES) * TRANSFORM_DIM
GROUP_NAMES = ("walk_sheathed", "walk_drawn", "run_sheathed", "run_drawn")
GROUP_COUNT = len(GROUP_NAMES)

if INPUT_DIM != 281:
    raise RuntimeError(f"AE4 input contract changed unexpectedly: {INPUT_DIM}")
if OUTPUT_DIM != 144:
    raise RuntimeError(f"AE4 output contract changed unexpectedly: {OUTPUT_DIM}")


@dataclass(frozen=True)
class AE4Config:
    hidden_dim: int = 1024
    hidden_layers: int = 3
    batch_size: int = 512
    learning_rate: float = 1.0e-3
    final_learning_rate: float = 1.0e-4
    weight_decay: float = 1.0e-5
    steps: int = 12000
    gaze_variants: int = 2
    seed: int = 20260812
    corpus_scope: str = "omni"


class UpperPoseAE4(torch.nn.Module):
    def __init__(self, config: AE4Config) -> None:
        super().__init__()
        layers: list[torch.nn.Module] = []
        width = INPUT_DIM
        for _ in range(int(config.hidden_layers)):
            layers.extend(
                (
                    torch.nn.Linear(width, int(config.hidden_dim)),
                    torch.nn.LayerNorm(int(config.hidden_dim)),
                    torch.nn.GELU(),
                )
            )
            width = int(config.hidden_dim)
        layers.append(torch.nn.Linear(width, OUTPUT_DIM))
        self.network = torch.nn.Sequential(*layers)

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        return self.network(values)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def checkpoint_schema() -> dict[str, Any]:
    return {
        "name": "upper_pose_condition_absolute_ae4",
        "mechanism": "condition_only_absolute_pose_predictor",
        "input_dim": INPUT_DIM,
        "output_dim": OUTPUT_DIM,
        "input_segments": {
            "previous_lower_plus_pelvis_transform": [0, LOWER_FRAME_DIM],
            "current_lower_plus_pelvis_transform": [LOWER_FRAME_DIM, LOWER_FRAME_DIM * 2],
            "next_lower_plus_pelvis_transform": [LOWER_FRAME_DIM * 2, LOWER_FRAME_DIM * 3],
            "current_plus_future_root_window": [LOWER_FRAME_DIM * 3, LOWER_FRAME_DIM * 3 + ROOT_DIM],
            "has_sword": [LOWER_FRAME_DIM * 3 + ROOT_DIM, LOWER_FRAME_DIM * 3 + ROOT_DIM + 1],
            "normalized_gaze_yaw_pitch": [INPUT_DIM - GAZE_DIM, INPUT_DIM],
        },
        "lower_condition_bones": list(LOWER_CONDITION_BONES),
        "upper_target_bones": list(UPPER_TARGET_BONES),
        "per_bone": "position3_rotation6",
        "lower_frames": "each transform is expressed in that frame's actual root",
        "target": "next absolute upper pose expressed in the next actual root",
        "upper_body_input": "none",
        "loss": "normalized target MSE",
    }


def _bone_indices(clip: tl.MotionClip, names: Iterable[str]) -> torch.Tensor:
    by_name = {name: index for index, name in enumerate(clip.body_names)}
    missing = [name for name in names if name not in by_name]
    if missing:
        raise RuntimeError(f"Missing AE4 bones in {clip.path}: {missing}")
    return torch.tensor([by_name[name] for name in names], dtype=torch.long)


def root_local_transforms(
    clip: tl.MotionClip,
    positions: torch.Tensor,
    rotations: torch.Tensor,
    root_position: torch.Tensor,
    root_rotation: torch.Tensor,
    bones: Iterable[str],
) -> torch.Tensor:
    indices = _bone_indices(clip, bones).to(positions.device)
    selected_position = positions.index_select(1, indices)
    selected_rotation = rotations.index_select(1, indices)
    inverse = root_rotation.transpose(-1, -2)
    local_position = torch.matmul(
        (selected_position - root_position[:, None]).unsqueeze(-2),
        inverse[:, None],
    ).squeeze(-2)
    local_rotation = selected_rotation @ inverse[:, None]
    result = torch.cat(
        (
            local_position,
            tl.rotmat_to_6d(local_rotation.reshape(-1, 3, 3)).reshape(
                int(positions.shape[0]), int(indices.numel()), 6
            ),
        ),
        dim=-1,
    ).reshape(int(positions.shape[0]), -1)
    return clean_absolute_pose(result, int(indices.numel()))


def clean_absolute_pose(values: torch.Tensor, bone_count: int = len(UPPER_TARGET_BONES)) -> torch.Tensor:
    one = values.ndim == 1
    work = values.unsqueeze(0) if one else values
    expected = int(bone_count) * TRANSFORM_DIM
    if work.ndim != 2 or int(work.shape[-1]) != expected:
        raise ValueError(f"Expected [N,{expected}], got {tuple(values.shape)}")
    shaped = work.reshape(-1, int(bone_count), TRANSFORM_DIM)
    cleaned = torch.cat(
        (
            shaped[..., :3],
            tl.clean_6d(shaped[..., 3:9].reshape(-1, 6)).reshape(
                -1, int(bone_count), 6
            ),
        ),
        dim=-1,
    ).reshape(-1, expected)
    return cleaned.squeeze(0) if one else cleaned


def condition_from_decoded_frames(
    clip: tl.MotionClip,
    previous_pose: tuple[torch.Tensor, torch.Tensor],
    current_pose: tuple[torch.Tensor, torch.Tensor],
    next_pose: tuple[torch.Tensor, torch.Tensor],
    previous_root: tuple[torch.Tensor, torch.Tensor],
    current_root: tuple[torch.Tensor, torch.Tensor],
    next_root: tuple[torch.Tensor, torch.Tensor],
    root_features: torch.Tensor,
    mode: float | torch.Tensor,
    gaze: torch.Tensor,
) -> torch.Tensor:
    batch = int(gaze.shape[0])
    pieces: list[torch.Tensor] = []
    for pose, root in (
        (previous_pose, previous_root),
        (current_pose, current_root),
        (next_pose, next_root),
    ):
        pieces.append(
            root_local_transforms(
                clip,
                pose[0],
                pose[1],
                root[0],
                root[1],
                LOWER_CONDITION_BONES,
            )
        )
    if torch.is_tensor(mode):
        mode_value = mode.to(device=gaze.device, dtype=torch.float32).reshape(batch, 1)
    else:
        mode_value = torch.full(
            (batch, 1), float(mode), dtype=torch.float32, device=gaze.device
        )
    condition = torch.cat((*pieces, root_features, mode_value, gaze), dim=-1)
    if tuple(condition.shape) != (batch, INPUT_DIM):
        raise RuntimeError(f"AE4 condition mismatch: {tuple(condition.shape)}")
    return condition


def absolute_upper_from_decoded(
    clip: tl.MotionClip,
    positions: torch.Tensor,
    rotations: torch.Tensor,
    root_position: torch.Tensor,
    root_rotation: torch.Tensor,
) -> torch.Tensor:
    return root_local_transforms(
        clip,
        positions,
        rotations,
        root_position,
        root_rotation,
        UPPER_TARGET_BONES,
    )


def absolute_upper_to_world(
    clip: tl.MotionClip,
    absolute_pose: torch.Tensor,
    root_position: torch.Tensor,
    root_rotation: torch.Tensor,
    base_positions: torch.Tensor,
    base_rotations: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    pose = clean_absolute_pose(absolute_pose)
    batch = int(pose.shape[0])
    shaped = pose.reshape(batch, len(UPPER_TARGET_BONES), TRANSFORM_DIM)
    world_position = (
        torch.matmul(shaped[..., :3].unsqueeze(-2), root_rotation[:, None]).squeeze(-2)
        + root_position[:, None]
    )
    local_rotation = tl.rotation_6d_to_matrix(
        shaped[..., 3:9].reshape(-1, 6)
    ).reshape(batch, len(UPPER_TARGET_BONES), 3, 3)
    world_rotation = local_rotation @ root_rotation[:, None]
    indices = _bone_indices(clip, UPPER_TARGET_BONES).to(base_positions.device)
    positions = base_positions.clone().index_copy(1, indices, world_position)
    rotations = base_rotations.clone().index_copy(1, indices, world_rotation)
    return positions, rotations


def _sample_gaze(count: int, generator: torch.Generator) -> torch.Tensor:
    gaze = torch.rand((count, GAZE_DIM), generator=generator) * 2.0 - 1.0
    zero = torch.rand((count,), generator=generator) < upper_data.GAZE_ZERO_PROBABILITY
    gaze[zero] = 0.0
    return gaze


def _clip_rows(
    source: Path,
    cyclic: bool,
    sword: float,
    gaze_variants: int,
    generator: torch.Generator,
    *,
    neutral_only: bool = False,
) -> tuple[torch.Tensor, torch.Tensor]:
    cfg = upper_data.motion_config()
    clip = tl.MotionClip(source, cfg, cyclic_animation=cyclic)
    if clip.cyclic_animation:
        current = torch.arange(int(clip.cyclic_period), dtype=torch.long)
        previous = torch.remainder(current - 1, int(clip.cyclic_period))
        following = torch.remainder(current + 1, int(clip.cyclic_period))
    else:
        maximum = int(clip.T) - int(cfg.future_window) - 1
        current = torch.arange(1, max(1, maximum), dtype=torch.long)
        previous = current - 1
        following = current + 1
    count = int(current.numel())
    if count <= 0:
        raise RuntimeError(f"No AE4 rows in {source}")
    roots = []
    lower_frames = []
    for frames in (previous, current, following):
        root = tl.root_state(clip, frames, cfg, torch.device("cpu"))
        roots.append((root[0], root[1]))
        logical = tl.logical_pose_index(clip, frames, torch.device("cpu"))
        lower_frames.append(
            root_local_transforms(
                clip,
                clip.global_pos.index_select(0, logical),
                clip.global_rot.index_select(0, logical),
                root[0],
                root[1],
                LOWER_CONDITION_BONES,
            )
        )
    root_features = upper_data.controller_root_features(clip, cfg, current)
    static = torch.cat(
        (
            *lower_frames,
            root_features,
            torch.full((count, 1), float(sword), dtype=torch.float32),
        ),
        dim=-1,
    )
    variants = max(1, int(gaze_variants))
    repeated_static = static.repeat_interleave(variants, dim=0)
    repeated_following = following.repeat_interleave(variants, dim=0)
    repeated_root_position = roots[2][0].repeat_interleave(variants, dim=0)
    repeated_root_rotation = roots[2][1].repeat_interleave(variants, dim=0)
    gaze = (
        torch.zeros((count * variants, GAZE_DIM), dtype=torch.float32)
        if neutral_only
        else _sample_gaze(count * variants, generator)
    )
    logical_following = tl.logical_pose_index(
        clip, repeated_following, torch.device("cpu")
    )
    target_position, target_rotation = upper_data.gaze_overlay_global_pose(
        clip, logical_following, gaze
    )
    target = absolute_upper_from_decoded(
        clip,
        target_position,
        target_rotation,
        repeated_root_position,
        repeated_root_rotation,
    )
    condition = torch.cat((repeated_static, gaze), dim=-1)
    if tuple(condition.shape) != (count * variants, INPUT_DIM):
        raise RuntimeError(f"AE4 clip input mismatch: {tuple(condition.shape)}")
    if tuple(target.shape) != (count * variants, OUTPUT_DIM):
        raise RuntimeError(f"AE4 clip target mismatch: {tuple(target.shape)}")
    return condition.contiguous(), target.contiguous()


@torch.inference_mode()
def authored_conditions_for_targets(
    source: Path,
    *,
    gaze: tuple[float, float] = (0.0, 0.0),
    has_sword: float = -1.0,
    cyclic_animation: bool = True,
) -> torch.Tensor:
    """Return AE4 conditions aligned by the target frame they predict."""

    generator = torch.Generator(device="cpu").manual_seed(0)
    rows, _targets = _clip_rows(
        Path(source),
        bool(cyclic_animation),
        float(has_sword),
        1,
        generator,
        neutral_only=True,
    )
    gaze_tensor = torch.tensor(gaze, dtype=torch.float32).reshape(1, GAZE_DIM)
    if not bool(torch.isfinite(gaze_tensor).all()) or bool(
        torch.any(gaze_tensor.abs() > 1.0)
    ):
        raise ValueError(f"Normalized gaze must be finite in [-1,1], got {gaze}")
    rows[:, -GAZE_DIM:] = gaze_tensor
    cfg = upper_data.motion_config()
    clip = tl.MotionClip(
        Path(source), cfg, cyclic_animation=bool(cyclic_animation)
    )
    aligned = torch.full((int(clip.T), INPUT_DIM), float("nan"), dtype=torch.float32)
    if clip.cyclic_animation:
        period = int(clip.cyclic_period)
        if int(rows.shape[0]) != period:
            raise RuntimeError(
                f"AE4 cyclic row mismatch: rows={len(rows)} period={period}"
            )
        aligned[1:period] = rows[: period - 1]
        aligned[0] = rows[period - 1]
        aligned[period] = rows[period - 1]
    else:
        target_count = min(int(rows.shape[0]), int(clip.T) - 1)
        aligned[1 : target_count + 1] = rows[:target_count]
    return aligned


def corpus_identity(
    corpus_scope: str = "omni",
) -> tuple[list[tuple[str, Path, bool]], list[tuple[str, Path, bool]], str]:
    corpus_scope = str(corpus_scope).strip().lower()
    if corpus_scope not in CORPUS_SCOPES:
        raise ValueError(
            f"Unknown AE4 corpus scope {corpus_scope!r}; expected one of {CORPUS_SCOPES}"
        )
    original, drawn, matched_hash = upper_data.matched_dataset()
    expected_count = 465
    if corpus_scope == "omni":
        def selected(spec: tuple[str, Path, bool]) -> bool:
            relative = spec[0]
            return (
                relative.startswith("walk_omni/M_Neutral_Walk_Loop_")
                or relative.startswith("run_omni/M_Neutral_Run_Loop_")
            )

        original = [spec for spec in original if selected(spec)]
        drawn = [spec for spec in drawn if selected(spec)]
        expected_count = 30
    if len(original) != expected_count or len(drawn) != expected_count:
        raise RuntimeError(
            f"Expected {expected_count} {corpus_scope} clips per mode, "
            f"got {len(original)} and {len(drawn)}"
        )
    payload = {
        "version": CACHE_VERSION,
        "corpus_scope": corpus_scope,
        "matched": matched_hash,
        "lower_bones": LOWER_CONDITION_BONES,
        "upper_bones": UPPER_TARGET_BONES,
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return original, drawn, fingerprint


def build_corpus(
    gaze_variants: int,
    seed: int,
    *,
    corpus_scope: str = "omni",
    neutral_only: bool = False,
    use_cache: bool = True,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, dict[str, Any]]:
    corpus_scope = str(corpus_scope).strip().lower()
    original, drawn, fingerprint = corpus_identity(corpus_scope)
    cache_path = CACHE_ROOT / (
        f"{fingerprint[:16]}_g{int(gaze_variants)}_s{int(seed)}"
        f"_{'neutral' if neutral_only else 'uniform'}.pt"
    )
    if use_cache and cache_path.is_file():
        payload = torch.load(cache_path, map_location="cpu", weights_only=False)
        return payload["inputs"], payload["targets"], payload["groups"], payload["metadata"]
    generator = torch.Generator(device="cpu").manual_seed(int(seed))
    inputs: list[torch.Tensor] = []
    targets: list[torch.Tensor] = []
    groups: list[torch.Tensor] = []
    group_counts = [0] * GROUP_COUNT
    started = time.perf_counter()
    for specs, sword, group_offset in ((original, -1.0, 0), (drawn, 1.0, 1)):
        for relative, source, cyclic in specs:
            category_offset = 2 if relative.startswith("run_") else 0
            group = group_offset + category_offset
            condition, target = _clip_rows(
                source,
                cyclic,
                sword,
                gaze_variants,
                generator,
                neutral_only=neutral_only,
            )
            inputs.append(condition)
            targets.append(target)
            groups.append(torch.full((len(condition),), group, dtype=torch.long))
            group_counts[group] += int(len(condition))
    all_inputs = torch.cat(inputs, dim=0)
    all_targets = torch.cat(targets, dim=0)
    all_groups = torch.cat(groups, dim=0)
    if not bool(torch.isfinite(all_inputs).all() and torch.isfinite(all_targets).all()):
        raise RuntimeError("AE4 corpus contains non-finite values")
    metadata = {
        "fingerprint": fingerprint,
        "corpus_scope": corpus_scope,
        "clips_per_mode": int(len(original)),
        "gaze_variants": int(gaze_variants),
        "seed": int(seed),
        "neutral_only": bool(neutral_only),
        "rows": int(len(all_inputs)),
        "group_counts": dict(zip(GROUP_NAMES, group_counts)),
        "build_seconds": time.perf_counter() - started,
    }
    if use_cache:
        CACHE_ROOT.mkdir(parents=True, exist_ok=True)
        temporary = cache_path.with_suffix(".tmp")
        torch.save(
            {
                "inputs": all_inputs,
                "targets": all_targets,
                "groups": all_groups,
                "metadata": metadata,
            },
            temporary,
        )
        os.replace(temporary, cache_path)
    return all_inputs, all_targets, all_groups, metadata


def load_checkpoint(
    path: Path, device: torch.device | str = "cpu"
) -> tuple[UpperPoseAE4, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, dict[str, Any]]:
    device = torch.device(device)
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    if checkpoint.get("kind") != KIND:
        raise RuntimeError(f"Not an upper AE4 checkpoint: {path}")
    schema = dict(checkpoint.get("schema", {}))
    if int(schema.get("input_dim", -1)) != INPUT_DIM or int(schema.get("output_dim", -1)) != OUTPUT_DIM:
        raise RuntimeError(f"AE4 schema mismatch in {path}")
    config = AE4Config(**dict(checkpoint["config"]))
    model = UpperPoseAE4(config).to(device)
    model.load_state_dict(checkpoint["model"], strict=True)
    model.eval().requires_grad_(False)
    tensors = [
        checkpoint[key].to(device=device, dtype=torch.float32)
        for key in ("input_mean", "input_std", "target_mean", "target_std")
    ]
    tensors[1] = tensors[1].clamp_min(1.0e-8)
    tensors[3] = tensors[3].clamp_min(1.0e-8)
    return model, tensors[0], tensors[1], tensors[2], tensors[3], checkpoint


def predict_absolute(
    model: UpperPoseAE4,
    condition: torch.Tensor,
    input_mean: torch.Tensor,
    input_std: torch.Tensor,
    target_mean: torch.Tensor,
    target_std: torch.Tensor,
) -> torch.Tensor:
    normalized = model((condition - input_mean) / input_std)
    return clean_absolute_pose(normalized * target_std + target_mean)


def _save_checkpoint(
    path: Path,
    model: UpperPoseAE4,
    optimizer: torch.optim.Optimizer,
    config: AE4Config,
    step: int,
    best: float,
    input_mean: torch.Tensor,
    input_std: torch.Tensor,
    target_mean: torch.Tensor,
    target_std: torch.Tensor,
    metadata: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(
        {
            "kind": KIND,
            "schema": checkpoint_schema(),
            "config": asdict(config),
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "step": int(step),
            "best": float(best),
            "input_mean": input_mean.detach().cpu(),
            "input_std": input_std.detach().cpu(),
            "target_mean": target_mean.detach().cpu(),
            "target_std": target_std.detach().cpu(),
            "metadata": metadata,
        },
        temporary,
    )
    os.replace(temporary, path)


def train(args: argparse.Namespace) -> Path:
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    config = AE4Config(
        hidden_dim=int(args.hidden_dim),
        hidden_layers=int(args.hidden_layers),
        batch_size=int(args.batch_size),
        learning_rate=float(args.learning_rate),
        final_learning_rate=float(args.final_learning_rate),
        weight_decay=float(args.weight_decay),
        steps=int(args.steps),
        gaze_variants=int(args.gaze_variants),
        seed=int(args.seed),
        corpus_scope=str(args.corpus_scope).strip().lower(),
    )
    if config.batch_size % GROUP_COUNT != 0:
        raise ValueError("AE4 batch size must divide exactly across four groups")
    torch.manual_seed(config.seed)
    np.random.seed(config.seed)
    inputs, targets, groups, corpus_metadata = build_corpus(
        config.gaze_variants,
        config.seed,
        corpus_scope=config.corpus_scope,
    )
    input_mean = inputs.mean(dim=0)
    input_std = inputs.std(dim=0).clamp_min(1.0e-5)
    target_mean = targets.mean(dim=0)
    target_std = targets.std(dim=0).clamp_min(1.0e-5)
    model = UpperPoseAE4(config).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay
    )
    resume_checkpoint: dict[str, Any] | None = None
    resume_path = Path(args.resume).resolve() if args.resume else None
    if resume_path is not None:
        resume_checkpoint = torch.load(resume_path, map_location="cpu", weights_only=False)
        if resume_checkpoint.get("kind") != KIND:
            raise RuntimeError(f"Not an upper AE4 checkpoint: {resume_path}")
        previous_config = AE4Config(**dict(resume_checkpoint["config"]))
        if (
            previous_config.hidden_dim != config.hidden_dim
            or previous_config.hidden_layers != config.hidden_layers
        ):
            raise RuntimeError("AE4 resume cannot change the network architecture")
        previous_corpus = dict(resume_checkpoint.get("metadata", {})).get("corpus", {})
        if previous_corpus.get("fingerprint") != corpus_metadata.get("fingerprint"):
            raise RuntimeError("AE4 resume corpus fingerprint mismatch")
        for key, current in (
            ("input_mean", input_mean),
            ("input_std", input_std),
            ("target_mean", target_mean),
            ("target_std", target_std),
        ):
            stored = resume_checkpoint[key].to(dtype=torch.float32)
            if not torch.equal(stored, current):
                raise RuntimeError(f"AE4 resume normalization mismatch: {key}")
        model.load_state_dict(resume_checkpoint["model"], strict=True)
        optimizer.load_state_dict(resume_checkpoint["optimizer"])
        for state in optimizer.state.values():
            for key, value in state.items():
                if torch.is_tensor(value):
                    state[key] = value.to(device)
    run_label = str(args.run_label).strip()
    if not run_label or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for character in run_label):
        raise ValueError(f"Invalid AE4 run label: {run_label!r}")
    run_id = time.strftime("%Y%m%d_%H%M%S") + f"_ik_{run_label}"
    run_dir = RUNS_ROOT / run_id
    checkpoints = run_dir / "checkpoints"
    checkpoints.mkdir(parents=True, exist_ok=True)
    writer = SummaryWriter(log_dir=str(run_dir / "tb"), flush_secs=1)
    metadata = {
        "run_id": run_id,
        "trainer": str(Path(__file__).resolve()),
        "corpus": corpus_metadata,
        "sampling": "exact equal walk/run x sheathed/drawn",
        "upper_body_input": "none",
        "tensorboard_url": "http://127.0.0.1:6006/#timeseries",
        "resume_checkpoint": str(resume_path) if resume_path is not None else None,
        "resume_step": int(resume_checkpoint.get("step", 0)) if resume_checkpoint else 0,
    }
    (run_dir / "config.json").write_text(
        json.dumps({**metadata, "config": asdict(config), "schema": checkpoint_schema()}, indent=2),
        encoding="utf-8",
    )
    init_path = checkpoints / f"{run_id}_init.pt"
    _save_checkpoint(
        init_path,
        model,
        optimizer,
        config,
        int(resume_checkpoint.get("step", 0)) if resume_checkpoint else 0,
        float(resume_checkpoint.get("best", float("inf"))) if resume_checkpoint else float("inf"),
        input_mean,
        input_std,
        target_mean,
        target_std,
        metadata,
    )
    group_indices = [torch.nonzero(groups == group, as_tuple=False).flatten() for group in range(GROUP_COUNT)]
    generator = torch.Generator(device="cpu").manual_seed(config.seed + 1)
    per_group = config.batch_size // GROUP_COUNT
    best = float(resume_checkpoint.get("best", float("inf"))) if resume_checkpoint else float("inf")
    best_path = checkpoints / f"{run_id}_best.pt"
    latest_path = checkpoints / f"{run_id}_latest.pt"
    started = time.perf_counter()
    model.train()
    resume_step = int(resume_checkpoint.get("step", 0)) if resume_checkpoint else 0
    for local_step in range(1, config.steps + 1):
        step = resume_step + local_step
        selected = []
        for indices in group_indices:
            choices = torch.randint(
                0, int(indices.numel()), (per_group,), generator=generator
            )
            selected.append(indices.index_select(0, choices))
        batch_indices = torch.cat(selected, dim=0)
        order = torch.randperm(config.batch_size, generator=generator)
        batch_indices = batch_indices.index_select(0, order)
        x = inputs.index_select(0, batch_indices).to(device)
        y = targets.index_select(0, batch_indices).to(device)
        fraction = float(local_step - 1) / float(max(1, config.steps - 1))
        learning_rate = config.learning_rate * (
            config.final_learning_rate / config.learning_rate
        ) ** fraction
        for group in optimizer.param_groups:
            group["lr"] = learning_rate
        optimizer.zero_grad(set_to_none=True)
        prediction = model((x - input_mean.to(device)) / input_std.to(device))
        normalized_target = (y - target_mean.to(device)) / target_std.to(device)
        loss = (prediction - normalized_target).square().mean()
        loss.backward()
        gradient_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0)
        optimizer.step()
        score = float(loss.detach().cpu())
        if score < best:
            best = score
            _save_checkpoint(
                best_path,
                model,
                optimizer,
                config,
                step,
                best,
                input_mean,
                input_std,
                target_mean,
                target_std,
                metadata,
            )
        if local_step == 1 or local_step % int(args.log_every) == 0 or local_step == config.steps:
            writer.add_scalar("loss/ae4", score, step)
            writer.add_scalar("learning_rate", learning_rate, step)
            writer.add_scalar("gradient_norm", float(gradient_norm), step)
            writer.flush()
            print(
                f"AE4 step={step} loss={score:.8g} best={best:.8g} "
                f"lr={learning_rate:.7g} elapsed_s={time.perf_counter()-started:.1f}",
                flush=True,
            )
        if local_step % int(args.checkpoint_every) == 0 or local_step == config.steps:
            _save_checkpoint(
                latest_path,
                model,
                optimizer,
                config,
                step,
                best,
                input_mean,
                input_std,
                target_mean,
                target_std,
                metadata,
            )
            status = {
                "run_id": run_id,
                "step": step,
                "loss": score,
                "best": best,
                "learning_rate": learning_rate,
                "gradient_norm": float(gradient_norm),
                "finite": all(math.isfinite(value) for value in (score, best, float(gradient_norm))),
                "elapsed_seconds": time.perf_counter() - started,
            }
            temporary = run_dir / "status.json.tmp"
            temporary.write_text(json.dumps(status, indent=2), encoding="utf-8")
            os.replace(temporary, run_dir / "status.json")
    writer.close()
    print(f"AE4_COMPLETE run={run_id} best={best_path}", flush=True)
    return best_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--hidden-dim", type=int, default=1024)
    parser.add_argument("--hidden-layers", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--learning-rate", type=float, default=1.0e-3)
    parser.add_argument("--final-learning-rate", type=float, default=1.0e-4)
    parser.add_argument("--weight-decay", type=float, default=1.0e-5)
    parser.add_argument("--steps", type=int, default=12000)
    parser.add_argument("--gaze-variants", type=int, default=2)
    parser.add_argument("--seed", type=int, default=20260812)
    parser.add_argument("--corpus-scope", choices=CORPUS_SCOPES, default="omni")
    parser.add_argument("--run-label", default="upper_pose_ae4_absolute")
    parser.add_argument("--log-every", type=int, default=25)
    parser.add_argument("--checkpoint-every", type=int, default=250)
    parser.add_argument("--resume")
    train(parser.parse_args())


if __name__ == "__main__":
    main()
