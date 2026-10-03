from __future__ import annotations

"""Train the non-attack upper-body locomotion controller.

The semantic recipe in this file is intentionally narrow:

* the accepted walk and run controllers are frozen locomotion proposals;
* training samples only the matched walk_omni and run_omni corpora;
* every physical batch is exactly balanced over walk/run x sheathed/drawn;
* gaze is conditioning only and follows the upper AE1 sampling law;
* the sole optimized objective matches the accepted root-transform upper
  AE1's frozen condition-only prediction; the calibrated identity gate is
  deliberately excluded because it can copy an incorrect candidate;
* maximum rollout K follows real wall time: 2, 4, 8, 16, then 32,
  3 minutes each; every batch mixes geometric effective K values through K1.

There are no attack inputs, labels, targets, gates, or losses here.
"""

import argparse
import copy
import hashlib
import json
import math
import os
import random
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.tensorboard import SummaryWriter

try:
    from .bootstrap import PROJECT_ROOT, ensure_paths
    from . import ik_core as tl
    from . import train_simple_ae_controller as lower_ctl
    from . import train_upper_pose_autoencoder as upper_ae_data
    from . import visualize
except ImportError:
    from bootstrap import PROJECT_ROOT, ensure_paths
    import ik_core as tl
    import train_simple_ae_controller as lower_ctl
    import train_upper_pose_autoencoder as upper_ae_data
    import visualize


ensure_paths()

import train_upper_pose_root_projector as root_ae_data
from training.slashes2.conditional_delta_projector import (
    CalibratedConditionalDeltaProjector,
    ConditionalDeltaProjector,
    GatedCalibratedDeltaProjector,
    ResidualDenoisingDeltaProjector,
)

HERE = PROJECT_ROOT / "training" / "ik"
RUNS_ROOT = PROJECT_ROOT / "training" / "runs"
ORIGINAL_ROOT = upper_ae_data.ORIGINAL_ROOT
DRAWN_ROOT = upper_ae_data.SWORD_ROOT

WALK_POINTER = HERE / "official_walk_omni_baseline.json"
RUN_POINTER = HERE / "official_run_omni_baseline.json"
UPPER_AE_POINTER = HERE / "official_upper_pose_root_ae1.json"

EXPECTED_WALK_SHA256 = "860934962AD94894E5AF1262DD403D85DA46733E02A6BE4AFC09CF5E1197F64E"
EXPECTED_RUN_SHA256 = "CCC03FEE15E825EBCBCD24F9E71934D515B5133E760114ABE664445042D379C1"
EXPECTED_AE_SHA256 = "14FCA93B08F0AB823F249624429A6BF2FB1982BBFD9E0F26A0587B14FC5FFF6B"

MODE_SHEATHED = -1.0
MODE_DRAWN = 1.0
CATEGORY_WALK = "walk"
CATEGORY_RUN = "run"
CATEGORY_ORDER = (CATEGORY_WALK, CATEGORY_RUN)
MODE_ORDER = (MODE_SHEATHED, MODE_DRAWN)

ROLLOUT_SCHEDULE = (2, 4, 8, 16, 32)
ROLLOUT_STAGE_SECONDS = 3.0 * 60.0
ROLLOUT_ARCHIVE_INTERVAL_SECONDS = 7.0 * 60.0
GAZE_ZERO_PROBABILITY = 0.05
LEGACY_UPPER_CONTROLLER_KIND = "upper_pose_ae1_only_controller"
UPPER_CONTROLLER_KIND = "upper_pose_root_ae1_only_controller"
SUPPORTED_UPPER_CONTROLLER_KINDS = (
    LEGACY_UPPER_CONTROLLER_KIND,
    UPPER_CONTROLLER_KIND,
)

INPUT_DIM = upper_ae_data.INPUT_DIM
OUTPUT_DIM = upper_ae_data.OUTPUT_DIM
ROW_DIM = upper_ae_data.ROW_DIM
WINDOW_DIM = upper_ae_data.WINDOW_DIM
NEWEST_OUTPUT_START = upper_ae_data.NEWEST_OUTPUT_START
NEWEST_OUTPUT_END = upper_ae_data.NEWEST_OUTPUT_END


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def atomic_compact_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, separators=(",", ":")), encoding="utf-8")
    os.replace(temporary, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(8 * 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest().upper()


def resolve_pointer(path: Path, expected_sha256: str) -> tuple[Path, dict[str, Any]]:
    pointer = json.loads(path.read_text(encoding="utf-8"))
    checkpoint = Path(str(pointer["checkpoint"]))
    if not checkpoint.is_absolute():
        checkpoint = (PROJECT_ROOT / checkpoint).resolve()
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    actual = sha256_file(checkpoint)
    pointer_hash = str(pointer.get("checkpoint_sha256", "")).upper()
    if actual != expected_sha256 or (pointer_hash and pointer_hash != actual):
        raise RuntimeError(
            f"Checkpoint hash mismatch for {path}: expected={expected_sha256} "
            f"pointer={pointer_hash} actual={actual}"
        )
    return checkpoint, pointer


def apply_checkpoint_config(checkpoint: dict[str, Any], device: torch.device) -> tl.TrainConfig:
    cfg = tl.TrainConfig()
    visualize.apply_config_dict(cfg, dict(checkpoint.get("config", {})))
    cfg.device = str(device)
    cfg.use_torch_compile = False
    cfg.live_viewer = False
    cfg.visual_reporter = False
    cfg.update_comparison_on_exit = False
    if tl.normalized_body_mode(cfg.body_mode) != tl.BODY_MODE_LOWER:
        raise RuntimeError(f"Frozen checkpoint is not lower-body: {cfg.body_mode}")
    if int(cfg.future_window) != 8:
        raise RuntimeError(f"Frozen checkpoint future window is {cfg.future_window}, expected 8")
    return cfg


def full_motion_config(device: torch.device) -> tl.TrainConfig:
    cfg = upper_ae_data.motion_config()
    cfg.body_mode = tl.BODY_MODE_FULL
    cfg.device = "cpu"
    cfg.use_torch_compile = False
    return cfg


class UpperDeltaAgent(torch.nn.Module):
    """The established Slash2 delta-agent trunk without attack gates."""

    def __init__(self) -> None:
        super().__init__()
        layers: list[torch.nn.Module] = []
        width = INPUT_DIM
        for _ in range(2):
            layers.extend(
                (
                    torch.nn.Linear(width, 512),
                    torch.nn.LayerNorm(512),
                    torch.nn.GELU(),
                )
            )
            width = 512
        self.trunk = torch.nn.Sequential(*layers)
        self.delta_head = torch.nn.Linear(width, OUTPUT_DIM)
        torch.nn.init.zeros_(self.delta_head.weight)
        torch.nn.init.zeros_(self.delta_head.bias)

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        return self.delta_head(self.trunk(values))


def load_upper_ae(
    path: Path,
    device: torch.device,
) -> tuple[torch.nn.Module, torch.Tensor, torch.Tensor, dict[str, Any]]:
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    if checkpoint.get("kind") != "upper_pose_root_transform_conditional_projector":
        raise RuntimeError(f"Not the accepted root-transform upper AE1: {path}")
    schema = dict(checkpoint.get("schema", {}))
    expected = {
        "total_dim": root_ae_data.FEATURE_DIM,
        "scored_delta": [root_ae_data.DELTA.start, root_ae_data.DELTA.stop],
        "previous_pose": [root_ae_data.PREVIOUS.start, root_ae_data.PREVIOUS.stop],
        "current_pose": [root_ae_data.CURRENT.start, root_ae_data.CURRENT.stop],
    }
    for key, value in expected.items():
        if schema.get(key) != value:
            raise RuntimeError(f"Upper AE1 schema {key}={schema.get(key)!r}, expected {value}")
    cfg = dict(checkpoint["config"])
    projector = dict(checkpoint.get("projector", {}))
    projector_class = {
        "condition_only": ConditionalDeltaProjector,
        "residual_denoising": ResidualDenoisingDeltaProjector,
        "calibrated_condition": CalibratedConditionalDeltaProjector,
        "gated_calibrated": GatedCalibratedDeltaProjector,
    }[str(projector.get("architecture", "condition_only"))]
    model = projector_class(
        root_ae_data.FEATURE_DIM,
        root_ae_data.POSE_DIM,
        hidden_dim=int(cfg["hidden_dim"]),
        num_hidden_layers=int(cfg["num_hidden_layers"]),
    ).to(device)
    model.load_state_dict(checkpoint["model"], strict=True)
    model.eval().requires_grad_(False)
    mean = checkpoint["mean"].to(device=device, dtype=torch.float32)
    std = checkpoint["std"].to(device=device, dtype=torch.float32).clamp_min(1.0e-8)
    if tuple(mean.shape) != (root_ae_data.FEATURE_DIM,) or tuple(std.shape) != (
        root_ae_data.FEATURE_DIM,
    ):
        raise RuntimeError(
            f"Root-transform upper AE1 normalization mismatch: mean={tuple(mean.shape)} "
            f"std={tuple(std.shape)}"
        )
    return model, mean, std, checkpoint


def ae1_base_delta_target(
    model: torch.nn.Module,
    normalized_features: torch.Tensor,
) -> torch.Tensor:
    """Return AE1's frozen condition-only delta answer.

    The accepted checkpoint is a gated calibrated projector.  Its public
    reconstruction blends the candidate back into the condition-only answer;
    a gate near one therefore makes arbitrary candidates look reconstructed.
    Agent training must instead match the unchanged condition-only ``base``
    prediction.  Detaching the target prevents the agent from changing its
    history merely to move the teacher during the same loss evaluation.
    """

    if isinstance(model, GatedCalibratedDeltaProjector):
        with torch.no_grad():
            target = model.base(normalized_features.detach())[:, root_ae_data.DELTA]
    elif isinstance(model, ConditionalDeltaProjector):
        with torch.no_grad():
            target = model(normalized_features.detach())[:, root_ae_data.DELTA]
    else:
        raise RuntimeError(
            "Upper-agent training requires a condition-only AE1 projector or "
            "the accepted gated AE1 checkpoint with its frozen condition-only base"
        )
    if tuple(target.shape) != (
        int(normalized_features.shape[0]),
        root_ae_data.POSE_DIM,
    ):
        raise RuntimeError(f"AE1 base target shape mismatch: {tuple(target.shape)}")
    if not bool(torch.isfinite(target).all()):
        raise RuntimeError("AE1 base target is non-finite")
    return target


def relative_datasets() -> dict[str, list[str]]:
    original = upper_ae_data.dataset_files(ORIGINAL_ROOT)
    drawn = upper_ae_data.dataset_files(DRAWN_ROOT)
    if original.keys() != drawn.keys() or len(original) != 465:
        raise RuntimeError(
            f"Matched corpus contract failed: original={len(original)} drawn={len(drawn)}"
        )
    result = {
        CATEGORY_WALK: [
            key
            for key in original
            if key.startswith("walk_omni/M_Neutral_Walk_Loop_")
        ],
        CATEGORY_RUN: [
            key
            for key in original
            if key.startswith("run_omni/M_Neutral_Run_Loop_")
        ],
    }
    if len(result[CATEGORY_WALK]) != 14 or len(result[CATEGORY_RUN]) != 16:
        raise RuntimeError(
            "Walk/run animation filter contract failed: "
            f"walk={len(result[CATEGORY_WALK])} run={len(result[CATEGORY_RUN])}"
        )
    return result


def full_relative_datasets() -> dict[str, list[str]]:
    """Return the complete matched authored locomotion corpus by lower policy.

    Unlike :func:`relative_datasets`, this includes idle and every authored
    non-periodic transition.  The directory prefix is the authoritative lower
    policy assignment used by the accepted AE1 corpus.
    """

    original = upper_ae_data.dataset_files(ORIGINAL_ROOT)
    drawn = upper_ae_data.dataset_files(DRAWN_ROOT)
    if original.keys() != drawn.keys() or len(original) != 465:
        raise RuntimeError(
            f"Matched full corpus contract failed: original={len(original)} "
            f"drawn={len(drawn)}"
        )
    result = {
        CATEGORY_WALK: [key for key in original if key.startswith("walk_")],
        CATEGORY_RUN: [key for key in original if key.startswith("run_")],
    }
    if len(result[CATEGORY_WALK]) != 229 or len(result[CATEGORY_RUN]) != 236:
        raise RuntimeError(
            "Full walk/run corpus split changed: "
            f"walk={len(result[CATEGORY_WALK])} run={len(result[CATEGORY_RUN])}"
        )
    return result


def is_cyclic(relative: str) -> bool:
    return relative.split("/", 1)[0].endswith("_omni")


def rest_offsets_from_pelvis(clip: tl.MotionClip, device: torch.device) -> torch.Tensor:
    values = upper_ae_data.rest_offsets_from_pelvis(clip)
    return values.to(device=device, dtype=torch.float32)


def root_frame_transform(
    position: torch.Tensor,
    rotation6: torch.Tensor,
    root_rotation: torch.Tensor,
    heading: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Re-express an actual-root-local transform in the flat heading frame."""

    bridge = root_rotation @ heading.transpose(-1, -2)
    position_heading = torch.matmul(position.unsqueeze(1), bridge).squeeze(1)
    rotation = tl.rotation_6d_to_matrix(rotation6)
    rotation_heading = rotation @ bridge
    return position_heading, tl.rotmat_to_6d(rotation_heading)


def pelvis_heading_features(
    lower_vec: torch.Tensor,
    root_rotation: torch.Tensor,
    heading: torch.Tensor,
) -> torch.Tensor:
    position, rotation6 = root_frame_transform(
        lower_vec[:, :3], lower_vec[:, 3:9], root_rotation, heading
    )
    return torch.cat((position, rotation6), dim=-1)


def foot_heading_features(
    store: lower_ctl.SimpleClipStore,
    lower_vec: torch.Tensor,
    root_rotation: torch.Tensor,
    heading: torch.Tensor,
) -> torch.Tensor:
    payload = lower_vec[:, lower_ctl.payload_slice(store)]
    by_side: dict[str, tuple[torch.Tensor, torch.Tensor]] = {}
    for spec in store.ik_payload_slices:
        if str(spec.get("kind", "")) != "leg":
            continue
        position_slice = spec["pos"]
        rotation_slice = spec["rot6"]
        assert isinstance(position_slice, slice) and isinstance(rotation_slice, slice)
        by_side[str(spec["side"])] = root_frame_transform(
            payload[:, position_slice],
            payload[:, rotation_slice],
            root_rotation,
            heading,
        )
    parts: list[torch.Tensor] = []
    for side in ("l", "r"):
        if side not in by_side:
            raise RuntimeError(f"Frozen lower payload has no {side!r} leg")
        parts.extend(by_side[side])
    result = torch.cat(parts, dim=-1)
    if tuple(result.shape) != (int(lower_vec.shape[0]), upper_ae_data.FOOT_PAIR_DIM):
        raise RuntimeError(f"Foot feature shape mismatch: {tuple(result.shape)}")
    return result


def base_upper_from_lower(
    lower_vec: torch.Tensor,
    root_position: torch.Tensor,
    root_rotation: torch.Tensor,
    heading: torch.Tensor,
    full_clip: tl.MotionClip,
    rest_offsets: torch.Tensor,
) -> torch.Tensor:
    batch = int(lower_vec.shape[0])
    pelvis_position_world = (
        torch.matmul(lower_vec[:, :3].unsqueeze(1), root_rotation).squeeze(1)
        + root_position
    )
    pelvis_rotation_world = tl.rotation_6d_to_matrix(lower_vec[:, 3:9]) @ root_rotation
    pelvis_rotation_heading6 = tl.rotmat_to_6d(
        pelvis_rotation_world @ heading.transpose(-1, -2)
    )
    identity6 = tl.rotmat_to_6d(
        torch.eye(3, dtype=lower_vec.dtype, device=lower_vec.device)
    ).reshape(1, 6)
    parts: list[torch.Tensor] = [identity6.repeat(batch, len(upper_ae_data.CORE_BONES))]
    by_name = {name: index for index, name in enumerate(full_clip.body_names)}
    for _side, _upper, _lower, hand_name in upper_ae_data.ARM_SPECS:
        hand = by_name[hand_name]
        if rest_offsets.ndim == 2:
            hand_rest = rest_offsets[hand].reshape(1, 1, 3)
        elif rest_offsets.ndim == 3 and int(rest_offsets.shape[0]) == batch:
            hand_rest = rest_offsets[:, hand, :].unsqueeze(1)
        else:
            raise RuntimeError(
                f"Rest-offset batch mismatch: {tuple(rest_offsets.shape)} for {batch} rows"
            )
        hand_world = (
            torch.matmul(hand_rest, pelvis_rotation_world).squeeze(1)
            + pelvis_position_world
        )
        hand_heading = torch.matmul(
            (hand_world - root_position).unsqueeze(1), heading.transpose(-1, -2)
        ).squeeze(1)
        parts.extend((hand_heading, pelvis_rotation_heading6, pelvis_rotation_heading6))
    return upper_ae_data.clean_upper_state(torch.cat(parts, dim=-1))


def sample_gaze(count: int, generator: torch.Generator, device: torch.device) -> torch.Tensor:
    gaze = torch.rand((count, 2), generator=generator, device="cpu") * 2.0 - 1.0
    zero = torch.rand((count,), generator=generator, device="cpu") < GAZE_ZERO_PROBABILITY
    gaze[zero] = 0.0
    return gaze.to(device=device, dtype=torch.float32)


def valid_start_max(clip: tl.MotionClip, rollout_k: int, future_window: int) -> int:
    end = int(clip.cyclic_period) if clip.cyclic_animation else int(clip.T)
    # Need start-2, every transition through start+K, and eight future roots.
    return end - int(rollout_k) - int(future_window) - 1


def sample_starts(
    clip: tl.MotionClip,
    count: int,
    rollout_k: int,
    future_window: int,
    generator: torch.Generator,
    device: torch.device,
) -> torch.Tensor:
    maximum = valid_start_max(clip, rollout_k, future_window)
    if maximum < 2:
        raise RuntimeError(
            f"Clip too short for K={rollout_k} and W={future_window}: {clip.path}"
        )
    return torch.randint(2, maximum + 1, (count,), generator=generator, device="cpu").to(device)


def sample_runtime_rows(
    runtime: "CategoryRuntime",
    count: int,
    rollout_k: int,
    generator: torch.Generator,
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Independently sample one animation and one valid start for every row."""

    clip_ids_cpu = torch.randint(
        0,
        len(runtime.lower_clips),
        (count,),
        generator=generator,
        device="cpu",
    )
    starts_cpu = torch.empty((count,), dtype=torch.long, device="cpu")
    for row, clip_id in enumerate(clip_ids_cpu.tolist()):
        clip = runtime.lower_clips[int(clip_id)]
        maximum = valid_start_max(
            clip, rollout_k, int(runtime.cfg.future_window)
        )
        if maximum < 2:
            raise RuntimeError(
                f"Clip too short for K={rollout_k}: {clip.path}"
            )
        starts_cpu[row] = torch.randint(
            2,
            maximum + 1,
            (1,),
            generator=generator,
            device="cpu",
        )[0]
    return clip_ids_cpu.to(device=device), starts_cpu.to(device=device)


def upper_overlay_rows(
    clip: tl.MotionClip,
    indices: torch.Tensor,
    gaze: torch.Tensor,
    device: torch.device,
) -> torch.Tensor:
    cpu_indices = indices.detach().cpu().long()
    cpu_gaze = gaze.detach().cpu().to(dtype=torch.float32)
    values = upper_ae_data.gaze_overlay_upper_state(clip, cpu_indices, cpu_gaze)
    return values.to(device=device, dtype=torch.float32)


def upper_overlay_runtime_rows(
    runtime: "CategoryRuntime",
    mode: float,
    clip_ids: torch.Tensor,
    indices: torch.Tensor,
    gaze: torch.Tensor,
    device: torch.device,
) -> torch.Tensor:
    """Gather authored upper poses for heterogeneous per-row animation clips."""

    cpu_clip_ids = clip_ids.detach().cpu().long()
    cpu_indices = indices.detach().cpu().long()
    cpu_gaze = gaze.detach().cpu().to(dtype=torch.float32)
    result = torch.empty(
        (int(indices.shape[0]), OUTPUT_DIM),
        dtype=torch.float32,
        device="cpu",
    )
    for clip_id in torch.unique(cpu_clip_ids, sorted=True).tolist():
        selection = torch.nonzero(cpu_clip_ids == int(clip_id), as_tuple=False).flatten()
        values = upper_ae_data.gaze_overlay_upper_state(
            runtime.full_clips_by_mode[mode][int(clip_id)],
            cpu_indices.index_select(0, selection),
            cpu_gaze.index_select(0, selection),
        )
        result.index_copy_(0, selection, values.to(dtype=torch.float32))
    return result.to(device=device, dtype=torch.float32)


class CategoryRuntime:
    def __init__(
        self,
        name: str,
        checkpoint: dict[str, Any],
        cfg: tl.TrainConfig,
        model: torch.nn.Module,
        relative: str | list[str],
        device: torch.device,
        *,
        lower_source_paths: list[Path] | None = None,
        full_source_paths_by_mode: dict[float, list[Path]] | None = None,
        cyclic_flags: list[bool] | None = None,
    ) -> None:
        self.name = name
        self.checkpoint = checkpoint
        self.cfg = cfg
        self.model = model
        self.relatives = [relative] if isinstance(relative, str) else list(relative)
        if not self.relatives:
            raise RuntimeError(f"Category {name!r} has no animation clips")
        self.relative = self.relatives[0]
        if lower_source_paths is None:
            lower_source_paths = [ORIGINAL_ROOT / value for value in self.relatives]
        else:
            lower_source_paths = [Path(value).resolve() for value in lower_source_paths]
        if len(lower_source_paths) != len(self.relatives):
            raise RuntimeError(
                f"Category {name!r} lower-source count changed: "
                f"{len(lower_source_paths)} != {len(self.relatives)}"
            )
        if cyclic_flags is None:
            cyclic_flags = [is_cyclic(value) for value in self.relatives]
        if len(cyclic_flags) != len(self.relatives):
            raise RuntimeError(
                f"Category {name!r} cyclic-flag count changed: "
                f"{len(cyclic_flags)} != {len(self.relatives)}"
            )
        self.lower_clips = [
            tl.MotionClip(
                source_path,
                cfg,
                cyclic_animation=bool(cyclic),
            )
            for source_path, cyclic in zip(lower_source_paths, cyclic_flags)
        ]
        self.lower_clip = self.lower_clips[0]
        self.store = lower_ctl.SimpleClipStore(self.lower_clips, cfg, device)
        full_cfg = full_motion_config(device)
        if full_source_paths_by_mode is None:
            full_source_paths_by_mode = {
                mode: [
                    (DRAWN_ROOT if mode == MODE_DRAWN else ORIGINAL_ROOT) / value
                    for value in self.relatives
                ]
                for mode in MODE_ORDER
            }
        for mode in MODE_ORDER:
            paths = full_source_paths_by_mode.get(mode)
            if paths is None or len(paths) != len(self.relatives):
                raise RuntimeError(
                    f"Category {name!r} full-source count changed for mode {mode}: "
                    f"{0 if paths is None else len(paths)} != {len(self.relatives)}"
                )
        self.full_clips_by_mode = {
            mode: [
                tl.MotionClip(
                    Path(source_path).resolve(),
                    full_cfg,
                    cyclic_animation=bool(cyclic),
                )
                for source_path, cyclic in zip(
                    full_source_paths_by_mode[mode], cyclic_flags
                )
            ]
            for mode in MODE_ORDER
        }
        self.full_by_mode = {
            mode: clips[0] for mode, clips in self.full_clips_by_mode.items()
        }
        self.rest_by_mode = {
            mode: rest_offsets_from_pelvis(clip, device)
            for mode, clip in self.full_by_mode.items()
        }
        self.rest_offsets_by_mode = {
            mode: torch.stack(
                [rest_offsets_from_pelvis(clip, device) for clip in clips], dim=0
            )
            for mode, clips in self.full_clips_by_mode.items()
        }
        lower_tensors = [clip.tensors(device) for clip in self.lower_clips]
        self.lower_geometry = {
            name: torch.stack([values[name] for values in lower_tensors], dim=0)
            for name in (
                "local_offsets",
                "ik_limb_lengths",
                "ik_local_pole_axis",
                "ik_toe_offsets",
                "ik_toe_axis",
            )
        }
        self.full_geometry_by_mode = {
            mode: {
                name: torch.stack(
                    [
                        getattr(clip, name).to(
                            device=device, dtype=torch.float32
                        )
                        for clip in clips
                    ],
                    dim=0,
                )
                for name in (
                    "local_offsets",
                    "ik_limb_lengths",
                    "ik_local_pole_axis",
                    "ik_toe_offsets",
                    "ik_toe_axis",
                )
            }
            for mode, clips in self.full_clips_by_mode.items()
        }

    def install_policy(self) -> None:
        root, prediction = visualize.checkpoint_output_contract(self.checkpoint)
        tl.OUTPUT_REFERENCE_ROOT = root
        tl.OUTPUT_PREDICTION_MODE = prediction
        visualize.apply_simple_controller_policy(self.checkpoint)


@dataclass(frozen=True)
class UpperPoseRollout:
    """One checkpoint-driven upper locomotion rollout for visualization."""

    checkpoint_path: Path
    checkpoint_kind: str
    source_path: Path
    category: str
    mode: float
    gaze: tuple[float, float]
    step: int
    fps: float
    positions: np.ndarray
    rotations: np.ndarray
    target_positions: np.ndarray
    target_rotations: np.ndarray
    frame_indices: np.ndarray
    root_positions: np.ndarray
    root_rotations: np.ndarray
    cfg: tl.TrainConfig
    clip: tl.MotionClip
    ae_windows: np.ndarray | None = None
    ae4_conditions: np.ndarray | None = None
    episode_start_noise: dict[str, Any] | None = None
    # Optional because older rollout producers use one gaze for both seeding and
    # conditioning.  Cached-lower viewer rollouts can now expose the distinct
    # gaze used to author the three controller-context poses.
    initial_gaze: tuple[float, float] | None = None


def is_upper_controller_checkpoint_data(checkpoint: object) -> bool:
    if (
        not isinstance(checkpoint, dict)
        or checkpoint.get("kind") not in SUPPORTED_UPPER_CONTROLLER_KINDS
    ):
        return False
    schema = checkpoint.get("schema", {})
    if not isinstance(schema, dict):
        return False
    return (
        int(schema.get("input_dim", -1)) == INPUT_DIM
        and int(schema.get("output_dim", -1)) == OUTPUT_DIM
        and isinstance(checkpoint.get("model"), dict)
    )


def require_upper_controller_checkpoint(checkpoint: object, path: Path) -> dict[str, Any]:
    if not is_upper_controller_checkpoint_data(checkpoint):
        kind = checkpoint.get("kind") if isinstance(checkpoint, dict) else type(checkpoint).__name__
        raise ValueError(
            f"Not a current {INPUT_DIM}->{OUTPUT_DIM} upper locomotion checkpoint: "
            f"{path} (kind={kind!r})"
        )
    assert isinstance(checkpoint, dict)
    return checkpoint


def _path_relative_to(path: Path, root: Path) -> str | None:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def upper_rollout_source(
    checkpoint: dict[str, Any],
    source_path: Path | None = None,
    *,
    prefer_drawn: bool = True,
) -> tuple[Path, str, float]:
    """Resolve a source only from the checkpoint's immutable matched corpus."""

    metadata = dict(checkpoint.get("metadata", {}))
    original_root = Path(str(metadata.get("original_dataset", ORIGINAL_ROOT))).resolve()
    drawn_root = Path(str(metadata.get("drawn_dataset", DRAWN_ROOT))).resolve()
    if not original_root.is_dir() or not drawn_root.is_dir():
        raise FileNotFoundError(
            f"Upper matched corpus is unavailable: original={original_root} drawn={drawn_root}"
        )

    if source_path is not None:
        resolved = Path(source_path).resolve()
        relative = _path_relative_to(resolved, drawn_root)
        mode = MODE_DRAWN
        if relative is None:
            relative = _path_relative_to(resolved, original_root)
            mode = MODE_SHEATHED
        if relative is None:
            raise ValueError(
                "Upper locomotion source must belong to the checkpoint's original or "
                f"holding-sword corpus: {resolved}"
            )
        counterpart = (drawn_root if mode == MODE_DRAWN else original_root) / relative
        if not counterpart.is_file():
            raise FileNotFoundError(counterpart)
        source = counterpart
    else:
        preferred_root = drawn_root if prefer_drawn else original_root
        preferred_relative = Path("walk_omni") / "M_Neutral_Walk_Loop_F.npz"
        source = preferred_root / preferred_relative
        if source.is_file():
            relative = preferred_relative.as_posix()
        else:
            candidates = sorted(preferred_root.rglob("*.npz"))
            candidates = [path for path in candidates if path.relative_to(preferred_root).as_posix().startswith("walk_")] or candidates
            if not candidates:
                raise FileNotFoundError(f"No upper locomotion NPZs under {preferred_root}")
            source = candidates[0]
            relative = source.relative_to(preferred_root).as_posix()
        mode = MODE_DRAWN if prefer_drawn else MODE_SHEATHED

    category = CATEGORY_WALK if relative.startswith("walk_") else CATEGORY_RUN if relative.startswith("run_") else ""
    if not category:
        raise ValueError(f"Upper source is neither walk nor run: {relative}")
    paired_original = original_root / relative
    paired_drawn = drawn_root / relative
    if not paired_original.is_file() or not paired_drawn.is_file():
        raise FileNotFoundError(
            f"Upper source is not a complete matched pair: {paired_original} / {paired_drawn}"
        )
    return source, category, mode


def _upper_heading_state_to_root(
    upper: torch.Tensor,
    root_rotation: torch.Tensor,
    heading: torch.Tensor,
) -> torch.Tensor:
    """Convert only the root-referenced arm fields from flat heading to actual root."""

    bridge = heading @ root_rotation.transpose(-1, -2)
    parts: list[torch.Tensor] = [upper[:, :60]]
    for start in (60, 75):
        position = torch.matmul(upper[:, start : start + 3].unsqueeze(1), bridge).squeeze(1)
        hand_rotation = tl.rotation_6d_to_matrix(upper[:, start + 3 : start + 9]) @ bridge
        upperarm_rotation = tl.rotation_6d_to_matrix(upper[:, start + 9 : start + 15]) @ bridge
        parts.append(
            torch.cat(
                (
                    position,
                    tl.rotmat_to_6d(hand_rotation),
                    tl.rotmat_to_6d(upperarm_rotation),
                ),
                dim=-1,
            )
        )
    return upper_ae_data.clean_upper_state(torch.cat(parts, dim=-1))


def full_pose_globals(
    runtime: CategoryRuntime,
    lower_vec: torch.Tensor,
    upper_heading: torch.Tensor,
    root_position: torch.Tensor,
    root_rotation: torch.Tensor,
    heading: torch.Tensor,
    mode: float,
    clip_ids: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Decode the frozen lower state plus learned upper state through full IK FK."""

    if clip_ids is None:
        clip_ids = torch.zeros(
            (int(lower_vec.shape[0]),), dtype=torch.long, device=lower_vec.device
        )
    if tuple(clip_ids.shape) != (int(lower_vec.shape[0]),):
        raise RuntimeError(
            f"Full-pose clip-id shape mismatch: {tuple(clip_ids.shape)}"
        )
    if bool(torch.any(clip_ids != clip_ids[0])):
        positions = None
        rotations = None
        for clip_id in torch.unique(clip_ids, sorted=True).tolist():
            selection = torch.nonzero(
                clip_ids == int(clip_id), as_tuple=False
            ).flatten()
            selected_positions, selected_rotations = full_pose_globals(
                runtime,
                lower_vec.index_select(0, selection),
                upper_heading.index_select(0, selection),
                root_position.index_select(0, selection),
                root_rotation.index_select(0, selection),
                heading.index_select(0, selection),
                mode,
                torch.full_like(selection, int(clip_id)),
            )
            if positions is None:
                positions = selected_positions.new_zeros(
                    (int(lower_vec.shape[0]),) + tuple(selected_positions.shape[1:])
                )
                rotations = selected_rotations.new_zeros(
                    (int(lower_vec.shape[0]),) + tuple(selected_rotations.shape[1:])
                )
            positions = positions.index_copy(0, selection, selected_positions)
            rotations = rotations.index_copy(0, selection, selected_rotations)
        assert positions is not None and rotations is not None
        return positions, rotations

    full_clip = runtime.full_clips_by_mode[mode][int(clip_ids[0].detach().cpu())]
    upper = _upper_heading_state_to_root(upper_heading, root_rotation, heading)
    batch = int(lower_vec.shape[0])
    full = lower_vec.new_zeros(
        (batch, 9 + full_clip.Jcore * 6 + full_clip.ik_payload_dim)
    )
    full[:, :9] = lower_vec[:, :9]
    core_by_name = {
        name: upper[:, slot * 6 : (slot + 1) * 6]
        for slot, name in enumerate(upper_ae_data.CORE_BONES)
    }
    for slot, body_index in enumerate(full_clip.core_non_pelvis):
        name = full_clip.body_names[body_index]
        full[:, 9 + slot * 6 : 9 + (slot + 1) * 6] = core_by_name[name]

    lower_payload = lower_vec[:, 9:]
    legs: dict[str, torch.Tensor] = {}
    for spec in runtime.lower_clip.ik_payload_slices:
        start = int(spec["pos"].start)
        stop_slice = spec["toe_float"] if spec["toe_float"] is not None else spec["start_rot6"]
        legs[str(spec["side"])] = lower_payload[:, start : int(stop_slice.stop)]
    arms = {"l": upper[:, 60:75], "r": upper[:, 75:90]}
    payload = [
        arms[str(spec["side"])] if str(spec["kind"]) == "arm" else legs[str(spec["side"])]
        for spec in full_clip.ik_payload_slices
    ]
    full[:, 9 + full_clip.Jcore * 6 :] = torch.cat(payload, dim=-1)
    pose, _raw = tl.output_to_pose(full, full_clip)
    positions, rotations, _canonical = tl.fk_from_pose(
        full_clip, root_position, root_rotation, pose, lower_vec.device
    )
    return positions, rotations


def rotation_error_degrees(
    predicted: torch.Tensor,
    target: torch.Tensor,
) -> torch.Tensor:
    """Geodesic rotation error for matching row-matrix transforms."""

    relative = predicted @ target.transpose(-1, -2)
    cosine = (
        relative.diagonal(dim1=-2, dim2=-1).sum(dim=-1) - 1.0
    ) * 0.5
    return torch.rad2deg(torch.acos(cosine.clamp(-1.0, 1.0)))


def root_ae_transition_features(
    runtime: CategoryRuntime,
    mode: float,
    lower_states: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    upper_states: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    root_states: tuple[
        tuple[torch.Tensor, torch.Tensor, torch.Tensor],
        tuple[torch.Tensor, torch.Tensor, torch.Tensor],
        tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    ],
    conditioning: torch.Tensor,
    clip_ids: torch.Tensor | None = None,
    capture_globals: list[tuple[torch.Tensor, torch.Tensor]] | None = None,
) -> torch.Tensor:
    """Build the accepted 479D scorer row through differentiable full-pose FK.

    Previous, current, and next upper transforms are all expressed in the
    current frame's root referential. The final 101 values are the unchanged
    pelvis/root/sword/feet/gaze portion of the 281D controller input.
    """

    batch = int(conditioning.shape[0])
    if tuple(conditioning.shape) != (batch, root_ae_data.FEATURE_DIM - 3 * root_ae_data.POSE_DIM):
        raise RuntimeError(
            f"Root AE conditioning shape mismatch: {tuple(conditioning.shape)}"
        )
    if clip_ids is None:
        clip_ids = torch.zeros((batch,), dtype=torch.long, device=conditioning.device)
    positions, rotations = full_pose_globals(
        runtime,
        torch.cat(lower_states, dim=0),
        torch.cat(upper_states, dim=0),
        torch.cat(tuple(state[0] for state in root_states), dim=0),
        torch.cat(tuple(state[1] for state in root_states), dim=0),
        torch.cat(tuple(state[2] for state in root_states), dim=0),
        mode,
        clip_ids.repeat(3),
    )
    if capture_globals is not None:
        capture_globals.append((positions.detach(), rotations.detach()))
    current_root_position = root_states[1][0]
    current_root_heading = root_states[1][2]
    pose = root_ae_data.pose_from_globals(
        runtime.full_by_mode[mode],
        positions,
        rotations,
        torch.cat((current_root_position,) * 3, dim=0),
        torch.cat((current_root_heading,) * 3, dim=0),
    )
    previous_pose = pose[:batch]
    current_pose = pose[batch : batch * 2]
    next_pose = pose[batch * 2 :]
    feature = torch.cat(
        (
            next_pose - current_pose,
            previous_pose,
            current_pose,
            conditioning,
        ),
        dim=-1,
    )
    if tuple(feature.shape) != (batch, root_ae_data.FEATURE_DIM):
        raise RuntimeError(f"Root AE feature shape mismatch: {tuple(feature.shape)}")
    return feature


@torch.inference_mode()
def rollout_upper_pose_checkpoint(
    checkpoint_path: Path,
    source_path: Path | None = None,
    *,
    gaze: tuple[float, float] = (0.0, 0.0),
    device: torch.device | str = "cpu",
    max_frames: int | None = None,
    start_frame: int = 2,
) -> UpperPoseRollout:
    """Run the frozen lower proposal and upper controller in training pass order."""

    device = torch.device(device)
    checkpoint_path = Path(checkpoint_path).resolve()
    checkpoint = require_upper_controller_checkpoint(
        torch.load(checkpoint_path, map_location="cpu", weights_only=False),
        checkpoint_path,
    )
    source, category, mode = upper_rollout_source(checkpoint, source_path)
    relative_root = DRAWN_ROOT if mode == MODE_DRAWN else ORIGINAL_ROOT
    relative = source.resolve().relative_to(relative_root.resolve()).as_posix()

    gaze_values = (float(gaze[0]), float(gaze[1]))
    if any(not math.isfinite(value) or abs(value) > 1.0 for value in gaze_values):
        raise ValueError(f"Normalized gaze must be finite in [-1,1], got {gaze_values}")

    lower_path, _pointer = resolve_pointer(
        WALK_POINTER if category == CATEGORY_WALK else RUN_POINTER,
        EXPECTED_WALK_SHA256 if category == CATEGORY_WALK else EXPECTED_RUN_SHA256,
    )
    lower_checkpoint = torch.load(lower_path, map_location="cpu", weights_only=False)
    cfg = apply_checkpoint_config(lower_checkpoint, device)
    probe = tl.MotionClip(
        ORIGINAL_ROOT / relative, cfg, cyclic_animation=is_cyclic(relative)
    )
    lower_model = visualize.load_model(lower_checkpoint, probe, cfg, device)
    lower_model.eval().requires_grad_(False)
    runtime = build_category_runtime(
        category, relative, lower_checkpoint, cfg, lower_model, device
    )

    upper_model = UpperDeltaAgent().to(device)
    upper_model.load_state_dict(checkpoint["model"], strict=True)
    upper_model.eval().requires_grad_(False)

    start_frame = int(start_frame)
    if start_frame < 2:
        raise ValueError(f"Upper rollout start frame must be at least 2, got {start_frame}")
    starts = torch.tensor([start_frame], dtype=torch.long, device=device)
    state = lower_initial_state(runtime, starts)
    gaze_tensor = torch.tensor([gaze_values], dtype=torch.float32, device=device)
    context_row, previous_upper, current_upper, current_base = make_context_row(
        runtime, state, mode, gaze_tensor, 0, 1
    )

    full_clip = runtime.full_by_mode[mode]
    seed_indices = torch.tensor(
        [start_frame - 2, start_frame - 1, start_frame],
        dtype=torch.long,
        device=device,
    )
    seed_upper = upper_overlay_rows(
        full_clip,
        seed_indices,
        gaze_tensor.repeat(3, 1),
        device,
    )
    seed_lower = (state["older"], state["prev"], state["cur"])
    positions_rows: list[torch.Tensor] = []
    rotations_rows: list[torch.Tensor] = []
    target_positions_rows: list[torch.Tensor] = []
    target_rotations_rows: list[torch.Tensor] = []
    frame_indices: list[int] = []
    root_positions: list[torch.Tensor] = []
    root_rotations: list[torch.Tensor] = []

    def append_pose(frame_index: int, lower: torch.Tensor, upper: torch.Tensor) -> None:
        index = torch.tensor([frame_index], dtype=torch.long, device=device)
        root_position, root_rotation, heading = root_state(runtime, index)
        position, rotation = full_pose_globals(
            runtime,
            lower,
            upper,
            root_position,
            root_rotation,
            heading,
            mode,
        )
        positions_rows.append(position[0].detach().cpu())
        rotations_rows.append(rotation[0].detach().cpu())
        authored_upper = upper_overlay_rows(
            full_clip,
            index,
            gaze_tensor,
            device,
        )
        target_position, target_rotation = full_pose_globals(
            runtime,
            lower,
            authored_upper,
            root_position,
            root_rotation,
            heading,
            mode,
        )
        target_positions_rows.append(target_position[0].detach().cpu())
        target_rotations_rows.append(target_rotation[0].detach().cpu())
        frame_indices.append(int(frame_index))
        root_positions.append(root_position[0].detach().cpu())
        root_rotations.append(root_rotation[0].detach().cpu())

    for frame_index, lower, upper in zip((0, 1, 2), seed_lower, seed_upper):
        append_pose(frame_index, lower, upper.unsqueeze(0))

    if runtime.lower_clip.cyclic_animation:
        final_index = min(int(runtime.lower_clip.T) - 1, int(runtime.lower_clip.cyclic_period) - 1)
    else:
        final_index = int(runtime.lower_clip.T) - int(runtime.cfg.future_window) - 1
    if max_frames is not None:
        final_index = min(final_index, max(0, int(max_frames) - 1))

    while int(state["cur_idx"].item()) < final_index:
        next_lower = lower_next(runtime, state)
        next_index = state["cur_idx"] + 1
        previous_root_pos, previous_root_rot, previous_heading = root_state(
            runtime, state["cur_idx"] - 1
        )
        current_root_pos, current_root_rot, current_heading = root_state(
            runtime, state["cur_idx"]
        )
        next_root_pos, next_root_rot, next_heading = root_state(runtime, next_index)
        pelvis_previous = pelvis_heading_features(
            state["prev"], previous_root_rot, previous_heading
        )
        pelvis_current = pelvis_heading_features(
            state["cur"], current_root_rot, current_heading
        )
        pelvis_next = pelvis_heading_features(next_lower, next_root_rot, next_heading)
        feet_current = foot_heading_features(
            runtime.store, state["cur"], current_root_rot, current_heading
        )
        feet_next = foot_heading_features(
            runtime.store, next_lower, next_root_rot, next_heading
        )
        roots = runtime.store.get_input_root_features(
            state["clip_ids"], state["cur_idx"]
        )
        next_base = base_upper_from_lower(
            next_lower,
            next_root_pos,
            next_root_rot,
            next_heading,
            full_clip,
            runtime.rest_by_mode[mode],
        )
        prior = upper_ae_data.clean_upper_state(
            next_base + (current_upper - current_base)
        )
        controller_input = torch.cat(
            (
                previous_upper,
                prior,
                pelvis_previous,
                pelvis_current,
                pelvis_next,
                roots,
                torch.full((1, 1), float(mode), dtype=torch.float32, device=device),
                feet_current,
                feet_next,
                gaze_tensor,
            ),
            dim=-1,
        )
        if int(controller_input.shape[-1]) != INPUT_DIM:
            raise RuntimeError(
                f"Upper rollout input is {controller_input.shape[-1]}, expected {INPUT_DIM}"
            )
        raw_delta = upper_model(controller_input)
        next_upper = upper_ae_data.clean_upper_state(prior + raw_delta)
        applied_delta = next_upper - prior
        append_pose(int(next_index.item()), next_lower, next_upper)

        context_row = torch.cat((controller_input, applied_delta), dim=-1)
        del context_row
        previous_upper = current_upper
        current_upper = next_upper
        current_base = next_base
        state["prev"] = state["cur"]
        state["cur"] = next_lower
        state["prev_pelvis"] = state["prev"][:, :3]
        state["cur_pelvis"] = state["cur"][:, :3]
        payload_slice = lower_ctl.payload_slice(runtime.store)
        state["prev_payload"] = state["prev"][:, payload_slice]
        state["cur_payload"] = state["cur"][:, payload_slice]
        state["cur_idx"] = next_index

    positions = torch.stack(positions_rows).numpy().astype(np.float32, copy=False)
    rotations = torch.stack(rotations_rows).numpy().astype(np.float32, copy=False)
    target_positions = (
        torch.stack(target_positions_rows).numpy().astype(np.float32, copy=False)
    )
    target_rotations = (
        torch.stack(target_rotations_rows).numpy().astype(np.float32, copy=False)
    )
    if not (
        np.isfinite(positions).all()
        and np.isfinite(rotations).all()
        and np.isfinite(target_positions).all()
        and np.isfinite(target_rotations).all()
    ):
        raise RuntimeError("Upper checkpoint rollout produced non-finite transforms")
    return UpperPoseRollout(
        checkpoint_path=checkpoint_path,
        checkpoint_kind=str(checkpoint["kind"]),
        source_path=source,
        category=category,
        mode=mode,
        gaze=gaze_values,
        step=int(checkpoint.get("step", -1)),
        fps=float(full_clip.fps),
        positions=positions,
        rotations=rotations,
        target_positions=target_positions,
        target_rotations=target_rotations,
        frame_indices=np.asarray(frame_indices, dtype=np.int32),
        root_positions=torch.stack(root_positions).numpy().astype(np.float32, copy=False),
        root_rotations=torch.stack(root_rotations).numpy().astype(np.float32, copy=False),
        cfg=runtime.cfg,
        clip=full_clip,
    )


def upper_rollout_debug_payload(rollout: UpperPoseRollout) -> dict[str, Any]:
    bones = [
        [int(parent), int(joint)]
        for joint, parent in enumerate(rollout.clip.parents_body_list)
        if int(parent) >= 0
    ]
    has_sword = bool(rollout.mode == MODE_DRAWN)
    frame_count = int(rollout.positions.shape[0])
    return {
        "schema_version": 2,
        "computed_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "run_id": rollout.checkpoint_path.parent.parent.name,
        "step": int(rollout.step),
        "fps": float(rollout.fps),
        "joint_names": list(rollout.clip.body_names),
        "bones": bones,
        "rows": [
            {
                "row": 0,
                "clip_id": 0,
                "clip_name": rollout.source_path.stem,
                "clip_path": str(rollout.source_path),
                "start": int(rollout.frame_indices[0]),
                "effective_k": frame_count - 1,
                "virtual": False,
                "noisy": False,
                "noisy_seed_source": "checkpoint",
                "has_sword": has_sword,
                "locomotion_category": rollout.category,
                "gaze_normalized": list(rollout.gaze),
            }
        ],
        "positions": [rollout.positions.tolist()],
        "basis": [rollout.rotations.tolist()],
        "controller_root_pos": [rollout.root_positions.tolist()],
        "controller_root_rot": [rollout.root_rotations.tolist()],
        "frozen_root_pos": [rollout.root_positions.tolist()],
        "frozen_root_rot": [rollout.root_rotations.tolist()],
        "source_frame": [rollout.frame_indices.tolist()],
        "source_clip_name": [[rollout.source_path.stem] * frame_count],
        "metadata": {
            "body_mode": "full",
            "checkpoint_kind": rollout.checkpoint_kind,
            "checkpoint": str(rollout.checkpoint_path),
            "source": str(rollout.source_path),
            "mode": "drawn" if has_sword else "sheathed",
            "has_sword": has_sword,
            "gaze_normalized": list(rollout.gaze),
            "capture_source": "checkpoint_replay",
        },
        "message": "Loaded upper locomotion checkpoint replay.",
    }


def expected_training_groups(rows_per_mode: int) -> dict[str, int]:
    return {
        f"{category}_{'drawn' if mode == MODE_DRAWN else 'sheathed'}": rows_per_mode
        for category in CATEGORY_ORDER
        for mode in MODE_ORDER
    }


def exact_training_rollout_debug_payload(
    run_id: str,
    step: int,
    runtime: "CategoryRuntime",
    rows: list[dict[str, Any]],
    positions: torch.Tensor,
    basis: torch.Tensor,
    root_positions: torch.Tensor,
    root_rotations: torch.Tensor,
    source_frames: torch.Tensor,
    request: dict[str, Any] | None,
) -> dict[str, Any]:
    """Serialize the exact last physical microbatch; never rerun or replace rows."""

    row_count = len(rows)
    frame_count = int(positions.shape[1])
    expected_groups = expected_training_groups(
        row_count // max(1, len(CATEGORY_ORDER) * len(MODE_ORDER))
    )
    expected_rows = sum(expected_groups.values())
    if row_count != expected_rows or int(positions.shape[0]) != row_count:
        raise RuntimeError(
            f"Faithful upper rollout must contain the physical {expected_rows} rows, "
            f"got {row_count}"
        )
    if tuple(basis.shape[:2]) != (row_count, frame_count):
        raise RuntimeError("Faithful upper rollout basis shape does not match positions")
    if tuple(root_positions.shape[:2]) != (row_count, frame_count):
        raise RuntimeError("Faithful upper rollout root positions do not match positions")
    if tuple(root_rotations.shape[:2]) != (row_count, frame_count):
        raise RuntimeError("Faithful upper rollout root rotations do not match positions")
    if tuple(source_frames.shape) != (row_count, frame_count):
        raise RuntimeError("Faithful upper rollout source frames do not match positions")
    if not all(
        bool(torch.isfinite(value).all())
        for value in (positions, basis, root_positions, root_rotations)
    ):
        raise RuntimeError("Faithful upper rollout contains a non-finite transform")

    group_counts: dict[str, int] = {}
    for row in rows:
        group = (
            f"{row['locomotion_category']}_"
            f"{'drawn' if bool(row['has_sword']) else 'sheathed'}"
        )
        group_counts[group] = group_counts.get(group, 0) + 1
    if group_counts != expected_groups:
        raise RuntimeError(
            f"Faithful upper rollout group split changed: {group_counts}"
        )

    prototype = runtime.full_by_mode[MODE_SHEATHED]
    clip_names = [str(row["clip_name"]) for row in rows]
    return {
        "schema_version": 2,
        "computed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "run_id": run_id,
        "step": int(step),
        "fps": float(prototype.fps),
        "joint_names": list(prototype.body_names),
        "bones": [
            [int(parent), int(joint)]
            for joint, parent in enumerate(prototype.parents_body_list)
            if int(parent) >= 0
        ],
        "rows": rows,
        "positions": positions.tolist(),
        "basis": basis.tolist(),
        "controller_root_pos": root_positions.tolist(),
        "controller_root_rot": root_rotations.tolist(),
        "frozen_root_pos": root_positions.tolist(),
        "frozen_root_rot": root_rotations.tolist(),
        "source_frame": source_frames.tolist(),
        "source_clip_name": [
            [clip_name] * frame_count for clip_name in clip_names
        ],
        "metadata": {
            "body_mode": "full",
            "capture_source": "exact_training_microbatch",
            "source_contract": (
                f"exact {row_count}-row physical microbatch copied from the real training pass; "
                "no checkpoint rerun, row substitution, phase duplication, or animation replacement"
            ),
            "group_counts": group_counts,
            "row_count": row_count,
            "frame_count": frame_count,
        },
        "request": request,
        "message": "Loaded the exact latest 32-row training rollout.",
    }


def build_category_runtime(
    category: str,
    relative: str | list[str],
    checkpoint: dict[str, Any],
    cfg: tl.TrainConfig,
    model: torch.nn.Module,
    device: torch.device,
) -> CategoryRuntime:
    runtime = CategoryRuntime(category, checkpoint, cfg, model, relative, device)
    if category == CATEGORY_WALK:
        runtime.install_policy()
        if lower_ctl.FOOT_ROLL_PIN_MODE != lower_ctl.FOOT_ROLL_PIN_MODE_LEGACY_LOGIT_SELECTED:
            raise RuntimeError(f"Walk pin mode restored as {lower_ctl.FOOT_ROLL_PIN_MODE}")
    else:
        runtime.install_policy()
        if lower_ctl.FOOT_ROLL_PIN_MODE != lower_ctl.FOOT_ROLL_PIN_MODE_CONTINUOUS_SIGMOID:
            raise RuntimeError(f"Run pin mode restored as {lower_ctl.FOOT_ROLL_PIN_MODE}")
    return runtime


def build_external_viewer_category_runtime(
    category: str,
    source_path: Path,
    checkpoint: dict[str, Any],
    cfg: tl.TrainConfig,
    model: torch.nn.Module,
    device: torch.device,
) -> CategoryRuntime:
    """Build a one-clip runtime for a standalone-viewer motion outside the corpus."""

    source = Path(source_path).resolve()
    runtime = CategoryRuntime(
        category,
        checkpoint,
        cfg,
        model,
        source.name,
        device,
        lower_source_paths=[source],
        full_source_paths_by_mode={
            MODE_SHEATHED: [source],
            MODE_DRAWN: [source],
        },
        cyclic_flags=[False],
    )
    runtime.install_policy()
    if category == CATEGORY_WALK:
        if lower_ctl.FOOT_ROLL_PIN_MODE != lower_ctl.FOOT_ROLL_PIN_MODE_LEGACY_LOGIT_SELECTED:
            raise RuntimeError(f"Walk pin mode restored as {lower_ctl.FOOT_ROLL_PIN_MODE}")
    elif lower_ctl.FOOT_ROLL_PIN_MODE != lower_ctl.FOOT_ROLL_PIN_MODE_CONTINUOUS_SIGMOID:
        raise RuntimeError(f"Run pin mode restored as {lower_ctl.FOOT_ROLL_PIN_MODE}")
    return runtime


def model_tensor_digest(model: torch.nn.Module) -> str:
    digest = hashlib.sha256()
    for name, tensor in model.state_dict().items():
        digest.update(name.encode("utf-8"))
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest().upper()


def lower_initial_state(
    runtime: CategoryRuntime,
    starts: torch.Tensor,
    clip_ids: torch.Tensor | None = None,
) -> dict[str, torch.Tensor]:
    runtime.install_policy()
    if clip_ids is None:
        clip_ids = torch.zeros_like(starts)
    if tuple(clip_ids.shape) != tuple(starts.shape):
        raise RuntimeError(
            f"Clip/start row mismatch: clips={tuple(clip_ids.shape)} starts={tuple(starts.shape)}"
        )
    older, _older_pelvis, _older_payload = lower_ctl.target_state(
        runtime.store, clip_ids, starts - 2
    )
    previous, previous_pelvis, previous_payload = lower_ctl.target_state(
        runtime.store, clip_ids, starts - 1
    )
    current, current_pelvis, current_payload = lower_ctl.target_state(
        runtime.store, clip_ids, starts
    )
    return {
        "clip_ids": clip_ids,
        "cur_idx": starts,
        "older": older,
        "prev": previous,
        "cur": current,
        "prev_pelvis": previous_pelvis,
        "cur_pelvis": current_pelvis,
        "prev_payload": previous_payload,
        "cur_payload": current_payload,
    }


@torch.no_grad()
def lower_next(runtime: CategoryRuntime, state: dict[str, torch.Tensor]) -> torch.Tensor:
    runtime.install_policy()
    values = lower_ctl.build_controller_input(
        runtime.store,
        state["clip_ids"],
        state["cur_idx"],
        state["prev"],
        state["cur"],
        state["prev_pelvis"],
        state["cur_pelvis"],
        state["prev_payload"],
        state["cur_payload"],
    )
    raw = lower_ctl.model_raw_output(
        runtime.model, values, state["cur"], runtime.store
    )
    transition = lower_ctl.clean_output_vector(
        raw, runtime.store, state["cur"], state["prev"]
    )
    next_vec, _next_pelvis, _next_payload = lower_ctl.advance_transition_state(
        runtime.store,
        state["clip_ids"],
        state["cur_idx"],
        transition,
    )
    return next_vec.detach()


def root_state(
    runtime: CategoryRuntime,
    indices: torch.Tensor,
    clip_ids: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    if clip_ids is None:
        clip_ids = torch.zeros_like(indices)
    pos, rot, _yaw, heading = runtime.store.root_state(
        clip_ids, indices
    )
    return pos, rot, heading


def make_context_row(
    runtime: CategoryRuntime,
    state: dict[str, torch.Tensor],
    mode: float,
    gaze: torch.Tensor,
    mode_offset: int,
    rows_per_mode: int,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    selection = slice(mode_offset, mode_offset + rows_per_mode)
    starts = state["cur_idx"][selection]
    clip_ids = state["clip_ids"][selection]
    older = state["older"][selection]
    previous = state["prev"][selection]
    current = state["cur"][selection]
    selected_gaze = gaze[selection]
    full = runtime.full_by_mode[mode]
    rest = runtime.rest_offsets_by_mode[mode].index_select(0, clip_ids)

    upper_indices = torch.cat((starts - 2, starts - 1, starts), dim=0)
    upper_clip_ids = clip_ids.repeat(3)
    repeated_gaze = selected_gaze.repeat(3, 1)
    posed = upper_overlay_runtime_rows(
        runtime,
        mode,
        upper_clip_ids,
        upper_indices,
        repeated_gaze,
        starts.device,
    )
    count = rows_per_mode
    older_upper = posed[:count]
    previous_upper = posed[count : 2 * count]
    current_upper = posed[2 * count :]

    old_root_pos, old_root_rot, old_heading = root_state(
        runtime, starts - 2, clip_ids
    )
    prev_root_pos, prev_root_rot, prev_heading = root_state(
        runtime, starts - 1, clip_ids
    )
    cur_root_pos, cur_root_rot, cur_heading = root_state(
        runtime, starts, clip_ids
    )
    old_base = base_upper_from_lower(
        older, old_root_pos, old_root_rot, old_heading, full, rest
    )
    previous_base = base_upper_from_lower(
        previous, prev_root_pos, prev_root_rot, prev_heading, full, rest
    )
    current_base = base_upper_from_lower(
        current, cur_root_pos, cur_root_rot, cur_heading, full, rest
    )
    del old_base
    prior = upper_ae_data.clean_upper_state(
        current_base + (previous_upper - previous_base)
    )
    applied_delta = current_upper - prior

    pelvis_old = pelvis_heading_features(older, old_root_rot, old_heading)
    pelvis_previous = pelvis_heading_features(previous, prev_root_rot, prev_heading)
    pelvis_current = pelvis_heading_features(current, cur_root_rot, cur_heading)
    feet_previous = foot_heading_features(
        runtime.store, previous, prev_root_rot, prev_heading
    )
    feet_current = foot_heading_features(
        runtime.store, current, cur_root_rot, cur_heading
    )
    root_features = runtime.store.get_input_root_features(
        clip_ids, starts - 1
    )
    sword = torch.full((count, 1), float(mode), device=starts.device)
    controller_input = torch.cat(
        (
            older_upper,
            prior,
            pelvis_old,
            pelvis_previous,
            pelvis_current,
            root_features,
            sword,
            feet_previous,
            feet_current,
            selected_gaze,
        ),
        dim=-1,
    )
    row = torch.cat((controller_input, applied_delta), dim=-1)
    if tuple(row.shape) != (count, ROW_DIM):
        raise RuntimeError(f"Context row shape mismatch: {tuple(row.shape)}")
    return row, previous_upper, current_upper, current_base


def rollout_stage(elapsed_seconds: float) -> tuple[int, int]:
    stage = min(
        len(ROLLOUT_SCHEDULE) - 1,
        max(0, int(float(elapsed_seconds) // ROLLOUT_STAGE_SECONDS)),
    )
    return stage, int(ROLLOUT_SCHEDULE[stage])


def sample_effective_rollout_k(
    batch_size: int,
    maximum_k: int,
    device: torch.device,
) -> torch.Tensor:
    """Use the accepted lower-agent geometric mixed-K batch recipe."""

    batch_size = max(1, int(batch_size))
    values = lower_ctl.rollout_values_for(maximum_k)
    remaining = batch_size
    chunks: list[torch.Tensor] = []
    for value in values[:-1]:
        count = remaining // 2
        if count:
            chunks.append(
                torch.full((count,), int(value), dtype=torch.long, device=device)
            )
        remaining -= count
    chunks.append(
        torch.full((remaining,), int(values[-1]), dtype=torch.long, device=device)
    )
    effective_k = torch.cat(chunks, dim=0)
    return effective_k.index_select(0, torch.randperm(batch_size, device=device))


def effective_rollout_k_counts(batch_size: int, maximum_k: int) -> dict[str, int]:
    values = lower_ctl.rollout_values_for(maximum_k)
    remaining = max(1, int(batch_size))
    result: dict[str, int] = {}
    for value in values[:-1]:
        count = remaining // 2
        result[str(int(value))] = int(count)
        remaining -= count
    result[str(int(values[-1]))] = int(remaining)
    return result


def save_checkpoint(
    path: Path,
    model: UpperDeltaAgent,
    optimizer: torch.optim.Optimizer,
    step: int,
    best: float,
    elapsed_seconds: float,
    rollout_k: int,
    metadata: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    payload = {
        "kind": UPPER_CONTROLLER_KIND,
        "model": model.state_dict(),
        "optimizer": optimizer.state_dict(),
        "step": int(step),
        "best": float(best),
        "elapsed_seconds": float(elapsed_seconds),
        "rollout_k": int(rollout_k),
        "schema": upper_ae_data.checkpoint_schema(),
        "recipe": {
            "architecture": "DeltaAgent Linear-LayerNorm-GELU 512x2, zero output head",
            "microbatch_size": int(metadata["microbatch_size"]),
            "gradient_accumulation_steps": int(metadata["gradient_accumulation_steps"]),
            "effective_batch_size": int(metadata["effective_batch_size"]),
            "optimizer": "AdamW",
            "learning_rate": float(metadata["learning_rate"]),
            "weight_decay": 0.0,
            "gradient_clip_norm": 50.0,
            "gradient_clip_timing": "once after averaging every accumulation microbatch",
            "loss": "accepted frozen root-transform upper AE1 condition-only base-target normalized delta MSE only",
            "checkpoint_selection": "lowest logged AE1 base-target delta MSE",
            "rollout_schedule": list(metadata["rollout_schedule"]["values"]),
            "rollout_stage_wall_minutes": metadata["rollout_schedule"][
                "wall_minutes_per_stage"
            ],
            "rollout_mode": str(metadata["rollout_schedule"]["mode"]),
            "rollout_row_weight": "1/effective_k/effective_batch_size",
        },
        "metadata": metadata,
        "rng": {
            "torch": torch.get_rng_state(),
            "cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],
            "python": random.getstate(),
        },
    }
    torch.save(payload, temporary)
    os.replace(temporary, path)


def contract_audit(
    runtimes: dict[str, CategoryRuntime],
    rows_per_mode: int,
    generator: torch.Generator,
    device: torch.device,
    ae: ConditionalDeltaProjector,
    mean: torch.Tensor,
    std: torch.Tensor,
    upper: UpperDeltaAgent,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "batch_groups": expected_training_groups(rows_per_mode),
        "checks": {},
    }
    maximum_base = 0.0
    maximum_pelvis = 0.0
    maximum_feet = 0.0
    root_feature_rows = 0
    root_agent_gradient_norm: float | None = None
    for category, runtime in runtimes.items():
        clip_ids, starts = sample_runtime_rows(
            runtime,
            rows_per_mode * 2,
            2,
            generator,
            device,
        )
        state = lower_initial_state(runtime, starts, clip_ids)
        gaze = torch.zeros((rows_per_mode * 2, 2), device=device)
        next_lower = lower_next(runtime, state)
        previous_root = root_state(
            runtime, state["cur_idx"] - 1, state["clip_ids"]
        )
        current_root = root_state(
            runtime, state["cur_idx"], state["clip_ids"]
        )
        next_root = root_state(
            runtime, state["cur_idx"] + 1, state["clip_ids"]
        )
        pelvis_previous_all = pelvis_heading_features(
            state["prev"], previous_root[1], previous_root[2]
        )
        pelvis_current_all = pelvis_heading_features(
            state["cur"], current_root[1], current_root[2]
        )
        pelvis_next_all = pelvis_heading_features(
            next_lower, next_root[1], next_root[2]
        )
        feet_current_all = foot_heading_features(
            runtime.store, state["cur"], current_root[1], current_root[2]
        )
        feet_next_all = foot_heading_features(
            runtime.store, next_lower, next_root[1], next_root[2]
        )
        roots_all = runtime.store.get_input_root_features(
            state["clip_ids"], state["cur_idx"]
        )
        for mode_index, mode in enumerate(MODE_ORDER):
            offset = mode_index * rows_per_mode
            selection = slice(offset, offset + rows_per_mode)
            full = runtime.full_by_mode[mode]
            selected_starts = starts[selection]
            selected_clip_ids = state["clip_ids"][selection]
            rest = runtime.rest_offsets_by_mode[mode].index_select(
                0, selected_clip_ids
            )
            current = state["cur"][selection]
            root_pos, root_rot, heading = root_state(
                runtime, selected_starts, selected_clip_ids
            )
            base = base_upper_from_lower(
                current, root_pos, root_rot, heading, full, rest
            )
            selected_pairs = list(
                zip(
                    selected_clip_ids.detach().cpu().tolist(),
                    selected_starts.detach().cpu().tolist(),
                )
            )
            authored_base = torch.stack(
                [
                    upper_ae_data.fk_base_upper_from_clip(
                        runtime.full_clips_by_mode[mode][int(clip_id)]
                    )[int(frame)]
                    for clip_id, frame in selected_pairs
                ]
            ).to(device)
            maximum_base = max(
                maximum_base, float((base - authored_base).abs().max().detach().cpu())
            )
            pelvis = pelvis_heading_features(current, root_rot, heading)
            authored_pelvis = torch.stack(
                [
                    upper_ae_data.pelvis_root_features(
                        runtime.full_clips_by_mode[mode][int(clip_id)]
                    )[int(frame)]
                    for clip_id, frame in selected_pairs
                ]
            ).to(device)
            maximum_pelvis = max(
                maximum_pelvis,
                float((pelvis - authored_pelvis).abs().max().detach().cpu()),
            )
            feet = foot_heading_features(runtime.store, current, root_rot, heading)
            authored_feet = torch.stack(
                [
                    upper_ae_data.feet_root_features(
                        runtime.full_clips_by_mode[mode][int(clip_id)]
                    )[int(frame)]
                    for clip_id, frame in selected_pairs
                ]
            ).to(device)
            maximum_feet = max(
                maximum_feet,
                float((feet - authored_feet).abs().max().detach().cpu()),
            )
            row, previous_upper, current_upper, current_base = make_context_row(
                runtime, state, mode, gaze, offset, rows_per_mode
            )
            if not bool(torch.isfinite(row).all()):
                raise RuntimeError(f"Non-finite context row in {category}/{mode}")
            next_base = base_upper_from_lower(
                next_lower[selection],
                next_root[0][selection],
                next_root[1][selection],
                next_root[2][selection],
                full,
                rest,
            )
            pose = upper_ae_data.clean_upper_state(
                next_base + (current_upper - current_base)
            )
            controller_input = torch.cat(
                (
                    previous_upper,
                    pose,
                    pelvis_previous_all[selection],
                    pelvis_current_all[selection],
                    pelvis_next_all[selection],
                    roots_all[selection],
                    torch.full(
                        (rows_per_mode, 1),
                        float(mode),
                        dtype=torch.float32,
                        device=device,
                    ),
                    feet_current_all[selection],
                    feet_next_all[selection],
                    gaze[selection],
                ),
                dim=-1,
            )
            if tuple(controller_input.shape) != (rows_per_mode, INPUT_DIM):
                raise RuntimeError(
                    f"Controller preflight input mismatch: {tuple(controller_input.shape)}"
                )
            proposed_upper = upper_ae_data.clean_upper_state(
                pose + upper(controller_input)
            )
            features = root_ae_transition_features(
                runtime,
                mode,
                (
                    state["prev"][selection],
                    state["cur"][selection],
                    next_lower[selection],
                ),
                (previous_upper, current_upper, proposed_upper),
                (
                    tuple(value[selection] for value in previous_root),
                    tuple(value[selection] for value in current_root),
                    tuple(value[selection] for value in next_root),
                ),
                controller_input[:, OUTPUT_DIM * 2 :],
                selected_clip_ids,
            )
            if not bool(torch.isfinite(features).all()):
                raise RuntimeError(f"Non-finite root AE feature in {category}/{mode}")
            root_feature_rows += int(features.shape[0])
            normalized = (features - mean) / std
            target = ae1_base_delta_target(ae, normalized)
            score = (
                normalized[:, root_ae_data.DELTA] - target
            ).square().mean()
            if not bool(torch.isfinite(score)):
                raise RuntimeError(f"Non-finite root AE score in {category}/{mode}")
            if root_agent_gradient_norm is None:
                gradients = torch.autograd.grad(
                    score,
                    tuple(upper.parameters()),
                    allow_unused=True,
                )
                finite_gradients = [
                    value for value in gradients if value is not None
                ]
                if not finite_gradients or any(
                    not bool(torch.isfinite(value).all()) for value in finite_gradients
                ):
                    raise RuntimeError("Root AE to upper-agent gradient is missing or non-finite")
                root_agent_gradient_norm = float(
                    torch.stack(
                        [value.detach().square().sum() for value in finite_gradients]
                    ).sum().sqrt().cpu()
                )
                if not math.isfinite(root_agent_gradient_norm) or root_agent_gradient_norm <= 0.0:
                    raise RuntimeError(
                        f"Root AE to upper-agent gradient is invalid: {root_agent_gradient_norm}"
                    )
    result["checks"] = {
        "lower_to_upper_base_max_abs": maximum_base,
        "lower_to_pelvis_feature_max_abs": maximum_pelvis,
        "lower_to_feet_feature_max_abs": maximum_feet,
        "walk_pin_mode": lower_ctl.FOOT_ROLL_PIN_MODE_LEGACY_LOGIT_SELECTED,
        "run_pin_mode": (
            lower_ctl.FOOT_ROLL_PIN_MODE_CONTINUOUS_SIGMOID
            if CATEGORY_RUN in CATEGORY_ORDER
            else None
        ),
        "gaze_input_only": True,
        "loss_terms": ["upper_root_transform_ae1_base_target"],
        "root_ae_feature_dim": root_ae_data.FEATURE_DIM,
        "root_ae_scored_delta_dim": root_ae_data.POSE_DIM,
        "root_ae_feature_rows_checked": root_feature_rows,
        "root_ae_to_agent_gradient_norm": root_agent_gradient_norm,
        "agent_io_unchanged": {"input": INPUT_DIM, "output": OUTPUT_DIM},
    }
    # Matched-mode lower values are allowed only extraction roundoff.
    if maximum_base > 2.0e-5 or maximum_pelvis > 2.0e-5 or maximum_feet > 2.0e-5:
        raise RuntimeError(f"Lower/full feature contract mismatch: {result['checks']}")
    return result


def train(args: argparse.Namespace) -> None:
    global CATEGORY_ORDER
    if str(args.motion_scope) == "walk_forward":
        CATEGORY_ORDER = (CATEGORY_WALK,)
        required_batch_size = 4
    else:
        CATEGORY_ORDER = (CATEGORY_WALK, CATEGORY_RUN)
        required_batch_size = 32
    if int(args.batch_size) != required_batch_size:
        raise ValueError(
            f"Motion scope {args.motion_scope!r} requires physical batch "
            f"{required_batch_size}, got {args.batch_size}"
        )
    group_count = len(CATEGORY_ORDER) * len(MODE_ORDER)
    if int(args.batch_size) % group_count != 0:
        raise ValueError(
            f"Batch must divide exactly into {group_count} category/mode groups"
        )
    rows_per_mode = int(args.batch_size) // group_count
    device = torch.device(args.device)
    if device.type == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable")
        cuda_index = (
            int(device.index)
            if device.index is not None
            else int(torch.cuda.current_device())
        )
        torch.cuda.set_device(cuda_index)
        device = torch.device("cuda", cuda_index)
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True

    torch.manual_seed(int(args.seed))
    random.seed(int(args.seed))
    generator = torch.Generator(device="cpu").manual_seed(int(args.seed))

    walk_path, walk_pointer = resolve_pointer(WALK_POINTER, EXPECTED_WALK_SHA256)
    if args.ae_checkpoint is None:
        ae_path, ae_pointer = resolve_pointer(UPPER_AE_POINTER, EXPECTED_AE_SHA256)
        ae_sha256 = EXPECTED_AE_SHA256
        ae_source = "official_pointer"
    else:
        ae_path = Path(args.ae_checkpoint).resolve()
        if not ae_path.is_file():
            raise FileNotFoundError(ae_path)
        ae_sha256 = sha256_file(ae_path)
        ae_pointer = {
            "selection": {
                "mode": "explicit_cli_checkpoint_override",
                "checkpoint_sha256": ae_sha256,
            }
        }
        ae_source = "explicit_cli_checkpoint_override"
    checkpoints = {
        CATEGORY_WALK: torch.load(walk_path, map_location="cpu", weights_only=False),
    }
    run_path: Path | None = None
    run_pointer: dict[str, Any] = {}
    if CATEGORY_RUN in CATEGORY_ORDER:
        run_path, run_pointer = resolve_pointer(RUN_POINTER, EXPECTED_RUN_SHA256)
        checkpoints[CATEGORY_RUN] = torch.load(
            run_path, map_location="cpu", weights_only=False
        )
    configs = {
        category: apply_checkpoint_config(checkpoint, device)
        for category, checkpoint in checkpoints.items()
    }
    if (
        CATEGORY_RUN in checkpoints
        and visualize.checkpoint_output_contract(checkpoints[CATEGORY_WALK])
        != visualize.checkpoint_output_contract(checkpoints[CATEGORY_RUN])
    ):
        raise RuntimeError("Walk and run output-reference contracts differ")

    relative_by_category = relative_datasets()
    if str(args.motion_scope) == "walk_forward":
        walk_forward = "walk_omni/M_Neutral_Walk_Loop_F.npz"
        if walk_forward not in relative_by_category[CATEGORY_WALK]:
            raise RuntimeError(f"Walk-forward source is missing: {walk_forward}")
        relative_by_category = {CATEGORY_WALK: [walk_forward]}
    first_relative = relative_by_category[CATEGORY_WALK][0]
    probe_clip = tl.MotionClip(
        ORIGINAL_ROOT / first_relative,
        configs[CATEGORY_WALK],
        cyclic_animation=is_cyclic(first_relative),
    )
    frozen_models: dict[str, torch.nn.Module] = {}
    for category in CATEGORY_ORDER:
        model = visualize.load_model(
            checkpoints[category], probe_clip, configs[category], device
        )
        model.eval().requires_grad_(False)
        frozen_models[category] = model
    del probe_clip
    frozen_digests = {
        category: model_tensor_digest(model)
        for category, model in frozen_models.items()
    }

    ae, mean, std, ae_checkpoint = load_upper_ae(ae_path, device)
    upper = UpperDeltaAgent().to(device)
    optimizer = torch.optim.AdamW(
        upper.parameters(), lr=float(args.learning_rate), weight_decay=0.0
    )
    initialization: dict[str, Any] | None = None
    initial_step = 0
    initial_best = float("inf")
    initial_elapsed_seconds = 0.0
    if args.init_checkpoint is not None:
        init_path = Path(args.init_checkpoint).resolve()
        init_checkpoint = require_upper_controller_checkpoint(
            torch.load(init_path, map_location="cpu", weights_only=False),
            init_path,
        )
        upper.load_state_dict(init_checkpoint["model"], strict=True)
        if bool(args.load_optimizer):
            if not isinstance(init_checkpoint.get("optimizer"), dict):
                raise RuntimeError(f"Resume checkpoint has no optimizer state: {init_path}")
            optimizer.load_state_dict(init_checkpoint["optimizer"])
        initial_step = int(init_checkpoint.get("step", 0))
        source_best = float(init_checkpoint.get("best", float("inf")))
        source_recipe = init_checkpoint.get("recipe", {})
        source_selection = (
            str(source_recipe.get("checkpoint_selection", ""))
            if isinstance(source_recipe, dict)
            else ""
        )
        initial_best = (
            source_best
            if source_selection == "lowest logged training AE1"
            else float("inf")
        )
        initial_elapsed_seconds = max(
            0.0, float(init_checkpoint.get("elapsed_seconds", 0.0))
        )
        initialization = {
            "checkpoint": str(init_path),
            "checkpoint_sha256": sha256_file(init_path),
            "checkpoint_kind": str(init_checkpoint["kind"]),
            "source_step": initial_step,
            "source_best": source_best,
            "source_checkpoint_selection": source_selection,
            "training_ae1_best_carried_forward": math.isfinite(initial_best),
            "source_elapsed_seconds": initial_elapsed_seconds,
            "optimizer_loaded": bool(args.load_optimizer),
            "curriculum_wall_clock_preserved": True,
        }

    fixed_k = int(args.fixed_k) if args.fixed_k is not None else None
    schedule_label = f"k{fixed_k}fixed" if fixed_k is not None else "k2to32"
    run_suffix = (
        f"_ik_ae1_walkf_modes_{schedule_label}"
        if str(args.motion_scope) == "walk_forward"
        else f"_ik_ae1_walk_run_omni_modes_{schedule_label}"
    )
    run_id = time.strftime("%Y%m%d_%H%M%S") + run_suffix
    if bool(args.smoke):
        run_id += "_smoke"
    run_dir = RUNS_ROOT / run_id
    checkpoint_dir = run_dir / "checkpoints"
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "metrics.jsonl"
    status_path = run_dir / "status.json"
    active_marker_path = run_dir / "debug" / "training.active.json"
    tensorboard_dir = run_dir / "tb"
    writer = SummaryWriter(log_dir=str(tensorboard_dir), flush_secs=1)
    atomic_json(
        active_marker_path,
        {
            "pid": os.getpid(),
            "run_id": run_id,
            "trainer": str(Path(__file__).resolve()),
            "started_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        },
    )

    metadata: dict[str, Any] = {
        "run_id": run_id,
        "walk_checkpoint": str(walk_path),
        "walk_checkpoint_sha256": EXPECTED_WALK_SHA256,
        "walk_selection": walk_pointer.get("selection", {}),
        "walk_foot_roll_pin_mode": "legacy_logit_selected",
        "run_checkpoint": str(run_path) if run_path is not None else None,
        "run_checkpoint_sha256": (
            EXPECTED_RUN_SHA256 if run_path is not None else None
        ),
        "run_selection": run_pointer.get("selection", {}) if run_path is not None else None,
        "run_foot_roll_pin_mode": (
            "continuous_sigmoid" if run_path is not None else None
        ),
        "upper_ae1": str(ae_path),
        "upper_ae1_sha256": ae_sha256,
        "upper_ae1_source": ae_source,
        "upper_ae1_selection": ae_pointer.get("selection", {}),
        "upper_ae1_contract": {
            "feature_dim": root_ae_data.FEATURE_DIM,
            "scored_delta_dim": root_ae_data.POSE_DIM,
            "pose_bones": list(root_ae_data.POSE_BONES),
            "pose_representation": "current-root-relative position3 rotation6",
            "excluded_uncontrolled_bones": ["lowerarm_l", "lowerarm_r"],
            "agent_input_dim": INPUT_DIM,
            "agent_output_dim": OUTPUT_DIM,
            "agent_representation_changed": False,
        },
        "original_dataset": str(ORIGINAL_ROOT),
        "drawn_dataset": str(DRAWN_ROOT),
        "motion_scope": str(args.motion_scope),
        "walk_relative_clips": len(relative_by_category[CATEGORY_WALK]),
        "run_relative_clips": len(relative_by_category.get(CATEGORY_RUN, [])),
        "dataset_subset": (
            {
                "walk": "only walk_omni/M_Neutral_Walk_Loop_F.npz",
                "run": "disabled",
            }
            if str(args.motion_scope) == "walk_forward"
            else {
                "walk": "14 M_Neutral_Walk_Loop_* files from walk_omni; idle excluded",
                "run": "16 M_Neutral_Run_Loop_* files from run_omni; copied walk/idle files excluded",
            }
        ),
        "sampling": (
            "every physical batch is exactly two walk-forward sheathed rows and two walk-forward drawn rows"
            if str(args.motion_scope) == "walk_forward"
            else "every microbatch is exactly 25% walk-sheathed, walk-drawn, run-sheathed, run-drawn"
        ),
        "clip_sampling": (
            "one fixed authored walk-forward animation; only frame starts, gaze, mode, and effective K vary"
            if str(args.motion_scope) == "walk_forward"
            else "every physical row independently samples one genuine category animation uniformly with replacement"
        ),
        "clip_residency": (
            "the one matched walk-forward original/drawn pair stays resident"
            if str(args.motion_scope) == "walk_forward"
            else "the filtered 14-walk and 16-run omni pools stay resident; no per-batch animation substitution"
        ),
        "rollout_debug": {
            "latest": "debug/last_batch_rollout.json",
            "chronological_pattern": "debug/rollout_step_XXXXXXXX.json",
            "archive_interval_minutes": 7.0,
            "capture_source": "exact_training_microbatch",
        },
        "mode_signal": {"sheathed": -1, "drawn": 1},
        "gaze": "normalized yaw/170,pitch/85; uniform [-1,1]^2 with 5% exact 0,0; constant per rollout",
        "gaze_loss": False,
        "loss": "root-transform upper AE1 frozen condition-only base target only",
        "lower_agents_frozen": True,
        "lower_model_loaded_sha256": frozen_digests,
        "rollout_schedule": {
            "values": [fixed_k] if fixed_k is not None else list(ROLLOUT_SCHEDULE),
            "wall_minutes_per_stage": None if fixed_k is not None else 3,
            "terminal": fixed_k if fixed_k is not None else 32,
            "mode": "mixed_geometric_at_max",
            "promotion": "manual user confirmation" if fixed_k is not None else "wall clock",
            "effective_k_values_at_terminal": list(
                lower_ctl.rollout_values_for(fixed_k if fixed_k is not None else 32)
            ),
            "effective_k_counts_at_terminal_batch": effective_rollout_k_counts(
                int(args.batch_size), fixed_k if fixed_k is not None else 32
            ),
            "row_weight": "1/effective_k/effective_batch_size after gradient averaging",
        },
        "pid": os.getpid(),
        "device": str(device),
        "learning_rate": float(args.learning_rate),
        "microbatch_size": int(args.batch_size),
        "gradient_accumulation_steps": int(args.gradient_accumulation_steps),
        "effective_batch_size": int(args.batch_size) * int(args.gradient_accumulation_steps),
        "initialization": initialization,
        "upper_parameter_count": sum(int(p.numel()) for p in upper.parameters()),
        "ae_parameter_count": sum(int(p.numel()) for p in ae.parameters()),
        "ae_checkpoint_step": int(ae_checkpoint.get("step", -1)),
        "tensorboard_logdir": str(tensorboard_dir),
        "tensorboard_local_url": "http://127.0.0.1:6006/",
    }
    initial_checkpoint_path = checkpoint_dir / f"{run_id}_init.pt"
    metadata["initial_checkpoint"] = (
        None if bool(args.audit_only) else str(initial_checkpoint_path)
    )

    runtimes = {
        category: build_category_runtime(
            category,
            relative_by_category[category],
            checkpoints[category],
            configs[category],
            frozen_models[category],
            device,
        )
        for category in CATEGORY_ORDER
    }
    audit = contract_audit(
        runtimes,
        rows_per_mode,
        generator,
        device,
        ae,
        mean,
        std,
        upper,
    )
    metadata["startup_contract_audit"] = audit

    atomic_json(run_dir / "contract.json", metadata)
    def configured_rollout_stage(elapsed_seconds: float) -> tuple[int, int]:
        if fixed_k is not None:
            return ROLLOUT_SCHEDULE.index(fixed_k), fixed_k
        return rollout_stage(elapsed_seconds)

    _initial_stage, initial_rollout_k = configured_rollout_stage(
        initial_elapsed_seconds
    )
    writer.add_scalar("run/started", 1.0, initial_step)
    writer.add_scalar("curriculum/rollout_k", int(initial_rollout_k), initial_step)
    writer.add_scalar("curriculum/effective_rollout_k_max", int(initial_rollout_k), initial_step)
    writer.add_scalar("integrity/lower_models_unchanged", 1.0, initial_step)
    writer.add_scalar("integrity/finite", 1.0, initial_step)
    writer.flush()
    lower_ctl.refresh_tensorboard_async()

    if device.type == "cuda":
        free, total = torch.cuda.mem_get_info(device)
        print(
            f"UPPER_CONTROLLER_GPU free_mib={free / 1048576:.0f} total_mib={total / 1048576:.0f}",
            flush=True,
        )
    print(
        f"UPPER_CONTROLLER_READY run={run_id} batch={args.batch_size} "
        f"groups={expected_training_groups(rows_per_mode)} "
        f"loss=root_AE1_base_target_only K={initial_rollout_k} device={device}",
        flush=True,
    )
    print(f"UPPER_CONTROLLER_CONTRACT {json.dumps(audit, separators=(',', ':'))}", flush=True)

    if bool(args.audit_only):
        atomic_json(status_path, {"state": "audit_passed", **metadata})
        writer.add_scalar("run/audit_passed", 1.0, 0)
        writer.close()
        active_marker_path.unlink(missing_ok=True)
        return

    save_checkpoint(
        initial_checkpoint_path,
        upper,
        optimizer,
        initial_step,
        initial_best,
        initial_elapsed_seconds,
        initial_rollout_k,
        metadata,
    )
    metadata["initial_checkpoint_sha256"] = sha256_file(initial_checkpoint_path)
    atomic_json(run_dir / "contract.json", metadata)
    print(
        f"UPPER_CONTROLLER_INIT step={initial_step} K={initial_rollout_k} "
        f"checkpoint={initial_checkpoint_path}",
        flush=True,
    )

    started = time.monotonic() - initial_elapsed_seconds
    last_log = started
    last_save = started
    last_rollout_archive = started - ROLLOUT_ARCHIVE_INTERVAL_SECONDS
    step = initial_step
    session_steps = 0
    best = initial_best
    recent_loss: list[float] = []
    total_rows = {f"{category}_{'sheathed' if mode < 0 else 'drawn'}": 0 for category in CATEGORY_ORDER for mode in MODE_ORDER}
    gaze_rows = 0
    gaze_zero_rows = 0
    current_stage = -1
    accumulation_steps = max(1, int(args.gradient_accumulation_steps))
    accumulation_index = 0
    accumulated_loss_value = 0.0
    accumulated_category_loss_value = {
        category: 0.0 for category in CATEGORY_ORDER
    }
    accumulated_applied_delta_rms: list[torch.Tensor] = []
    accumulated_upper_residual_rms: list[torch.Tensor] = []
    accumulated_clip_pairs: list[dict[str, list[str]]] = []

    while True:
        now = time.monotonic()
        elapsed = now - started
        scheduled_stage, scheduled_rollout_k = configured_rollout_stage(elapsed)
        if accumulation_index == 0:
            stage, rollout_k = scheduled_stage, scheduled_rollout_k
        else:
            stage = current_stage
            rollout_k = int(ROLLOUT_SCHEDULE[current_stage])
        if stage != current_stage and accumulation_index == 0:
            current_stage = stage
            print(
                f"UPPER_CONTROLLER_STAGE elapsed_min={elapsed / 60.0:.3f} "
                f"stage={stage} K={rollout_k}",
                flush=True,
            )
            if step > 0:
                save_checkpoint(
                    checkpoint_dir / f"{run_id}_stage{stage}_k{rollout_k}.pt",
                    upper,
                    optimizer,
                    step,
                    best,
                    elapsed,
                    rollout_k,
                    metadata,
                )

        if bool(args.smoke) and session_steps >= int(args.smoke_steps) and accumulation_index == 0:
            break
        if (
            float(args.max_hours) > 0.0
            and elapsed >= float(args.max_hours) * 3600.0
            and accumulation_index == 0
        ):
            break
        effective_k = sample_effective_rollout_k(
            int(args.batch_size), rollout_k, device
        )
        effective_k_float = effective_k.to(dtype=torch.float32)
        rollout_row_weight = (
            1.0 / effective_k_float.clamp_min(1.0)
        ) / float(args.batch_size)
        capture_training_rollout = accumulation_index == accumulation_steps - 1
        debug_rows: list[dict[str, Any]] = []
        debug_positions_frames: list[torch.Tensor] = []
        debug_basis_frames: list[torch.Tensor] = []
        debug_root_position_frames: list[torch.Tensor] = []
        debug_root_rotation_frames: list[torch.Tensor] = []
        debug_source_frames: list[torch.Tensor] = []
        capture_position_errors: list[torch.Tensor] = []
        capture_rotation_errors: list[torch.Tensor] = []
        capture_head_errors: list[torch.Tensor] = []
        capture_hand_l_errors: list[torch.Tensor] = []
        capture_hand_r_errors: list[torch.Tensor] = []
        capture_end_position_errors: list[torch.Tensor] = []

        upper.train()
        if accumulation_index == 0:
            optimizer.zero_grad(set_to_none=True)
        gaze_by_category: dict[str, torch.Tensor] = {}
        state_by_category: dict[str, dict[str, torch.Tensor]] = {}
        upper_state: dict[tuple[str, float], dict[str, torch.Tensor]] = {}

        for category in CATEGORY_ORDER:
            runtime = runtimes[category]
            clip_ids, starts = sample_runtime_rows(
                runtime,
                rows_per_mode * 2,
                rollout_k,
                generator,
                device,
            )
            gaze = sample_gaze(rows_per_mode * 2, generator, device)
            gaze_by_category[category] = gaze
            state = lower_initial_state(runtime, starts, clip_ids)
            state_by_category[category] = state
            gaze_rows += int(gaze.shape[0])
            gaze_zero_rows += int((gaze == 0.0).all(dim=-1).sum().item())
            for mode_index, mode in enumerate(MODE_ORDER):
                offset = mode_index * rows_per_mode
                _row, previous_upper, current_upper, current_base = make_context_row(
                    runtime,
                    state,
                    mode,
                    gaze,
                    offset,
                    rows_per_mode,
                )
                key = (category, mode)
                upper_state[key] = {
                    "previous": previous_upper,
                    "current": current_upper,
                    "current_base": current_base,
                }
                total_rows[f"{category}_{'sheathed' if mode < 0 else 'drawn'}"] += rows_per_mode

        sampled_relatives_by_category = {
            category: [
                runtimes[category].relatives[int(clip_id)]
                for clip_id in state_by_category[category]["clip_ids"].detach().cpu().tolist()
            ]
            for category in CATEGORY_ORDER
        }
        accumulated_clip_pairs.append(sampled_relatives_by_category)

        if capture_training_rollout:
            row_cursor = 0
            for category in CATEGORY_ORDER:
                runtime = runtimes[category]
                state = state_by_category[category]
                gaze = gaze_by_category[category]
                for mode_index, mode in enumerate(MODE_ORDER):
                    offset = mode_index * rows_per_mode
                    dataset_root = DRAWN_ROOT if mode == MODE_DRAWN else ORIGINAL_ROOT
                    for local_row in range(rows_per_mode):
                        source_row = offset + local_row
                        clip_id = int(
                            state["clip_ids"][source_row].detach().cpu()
                        )
                        clip_path = dataset_root / runtime.relatives[clip_id]
                        debug_rows.append(
                            {
                                "row": row_cursor,
                                "clip_id": clip_id,
                                "clip_name": clip_path.stem,
                                "clip_path": str(clip_path),
                                "start": int(state["cur_idx"][source_row].detach().cpu()),
                                "effective_k": int(effective_k[row_cursor].detach().cpu()),
                                "virtual": False,
                                "noisy": False,
                                "noisy_seed_source": "exact_training_row",
                                "has_sword": bool(mode == MODE_DRAWN),
                                "locomotion_category": category,
                                "gaze_normalized": [
                                    float(value)
                                    for value in gaze[source_row].detach().cpu().tolist()
                                ],
                            }
                        )
                        row_cursor += 1
            if row_cursor != int(args.batch_size):
                raise RuntimeError(
                    f"Faithful capture row assembly produced {row_cursor} rows"
                )

        step_losses: list[torch.Tensor] = []
        step_category_losses: dict[str, list[torch.Tensor]] = {
            category: [] for category in CATEGORY_ORDER
        }
        applied_delta_rms: list[torch.Tensor] = []
        upper_residual_rms: list[torch.Tensor] = []
        for rollout_step in range(rollout_k):
            next_lower_by_category = {
                category: lower_next(runtimes[category], state_by_category[category])
                for category in CATEGORY_ORDER
            }
            controller_inputs: list[torch.Tensor] = []
            priors: list[torch.Tensor] = []
            next_bases: list[torch.Tensor] = []
            keys: list[tuple[str, float]] = []
            scoring_context: dict[tuple[str, float], dict[str, Any]] = {}

            for category in CATEGORY_ORDER:
                runtime = runtimes[category]
                state = state_by_category[category]
                next_lower = next_lower_by_category[category]
                next_indices = state["cur_idx"] + 1
                prev_root_pos, prev_root_rot, prev_heading = root_state(
                    runtime, state["cur_idx"] - 1, state["clip_ids"]
                )
                cur_root_pos, cur_root_rot, cur_heading = root_state(
                    runtime, state["cur_idx"], state["clip_ids"]
                )
                next_root_pos, next_root_rot, next_heading = root_state(
                    runtime, next_indices, state["clip_ids"]
                )
                pelvis_previous = pelvis_heading_features(
                    state["prev"], prev_root_rot, prev_heading
                )
                pelvis_current = pelvis_heading_features(
                    state["cur"], cur_root_rot, cur_heading
                )
                pelvis_next = pelvis_heading_features(
                    next_lower, next_root_rot, next_heading
                )
                feet_current = foot_heading_features(
                    runtime.store, state["cur"], cur_root_rot, cur_heading
                )
                feet_next = foot_heading_features(
                    runtime.store, next_lower, next_root_rot, next_heading
                )
                roots = runtime.store.get_input_root_features(
                    state["clip_ids"], state["cur_idx"]
                )
                gaze = gaze_by_category[category]

                for mode_index, mode in enumerate(MODE_ORDER):
                    offset = mode_index * rows_per_mode
                    selection = slice(offset, offset + rows_per_mode)
                    key = (category, mode)
                    full = runtime.full_by_mode[mode]
                    selected_clip_ids = state["clip_ids"][selection]
                    rest = runtime.rest_offsets_by_mode[mode].index_select(
                        0, selected_clip_ids
                    )
                    next_base = base_upper_from_lower(
                        next_lower[selection],
                        next_root_pos[selection],
                        next_root_rot[selection],
                        next_heading[selection],
                        full,
                        rest,
                    )
                    current = upper_state[key]
                    prior = upper_ae_data.clean_upper_state(
                        next_base + (current["current"] - current["current_base"])
                    )
                    sword = torch.full(
                        (rows_per_mode, 1), float(mode), device=device
                    )
                    controller_input = torch.cat(
                        (
                            current["previous"],
                            prior,
                            pelvis_previous[selection],
                            pelvis_current[selection],
                            pelvis_next[selection],
                            roots[selection],
                            sword,
                            feet_current[selection],
                            feet_next[selection],
                            gaze[selection],
                        ),
                        dim=-1,
                    )
                    if int(controller_input.shape[-1]) != INPUT_DIM:
                        raise RuntimeError(
                            f"Controller input is {controller_input.shape[-1]}, expected {INPUT_DIM}"
                        )
                    controller_inputs.append(controller_input)
                    priors.append(prior)
                    next_bases.append(next_base)
                    keys.append(key)
                    scoring_context[key] = {
                        "lower_states": (
                            state["prev"][selection],
                            state["cur"][selection],
                            next_lower[selection],
                        ),
                        "root_states": (
                            (
                                prev_root_pos[selection],
                                prev_root_rot[selection],
                                prev_heading[selection],
                            ),
                            (
                                cur_root_pos[selection],
                                cur_root_rot[selection],
                                cur_heading[selection],
                            ),
                            (
                                next_root_pos[selection],
                                next_root_rot[selection],
                                next_heading[selection],
                            ),
                        ),
                        "frame_indices": (
                            state["cur_idx"][selection],
                            next_indices[selection],
                        ),
                        "conditioning": controller_input[:, OUTPUT_DIM * 2 :],
                        "clip_ids": selected_clip_ids,
                        "gaze": gaze[selection],
                    }

            batched_input = torch.cat(controller_inputs, dim=0)
            batched_prior = torch.cat(priors, dim=0)
            raw_delta = upper(batched_input)
            next_upper = upper_ae_data.clean_upper_state(batched_prior + raw_delta)
            applied_delta = next_upper - batched_prior
            feature_rows: list[torch.Tensor] = []
            captured_feature_globals: list[
                tuple[torch.Tensor, torch.Tensor]
            ] | None = [] if capture_training_rollout else None
            cursor = 0
            for key in keys:
                next_values = next_upper[cursor : cursor + rows_per_mode]
                context = scoring_context[key]
                feature_rows.append(
                    root_ae_transition_features(
                        runtimes[key[0]],
                        key[1],
                        context["lower_states"],
                        (
                            upper_state[key]["previous"],
                            upper_state[key]["current"],
                            next_values,
                        ),
                        context["root_states"],
                        context["conditioning"],
                        context["clip_ids"],
                        captured_feature_globals,
                    )
                )
                if capture_training_rollout:
                    assert captured_feature_globals is not None
                    predicted_positions = captured_feature_globals[-1][0][
                        rows_per_mode * 2 :
                    ]
                    predicted_rotations = captured_feature_globals[-1][1][
                        rows_per_mode * 2 :
                    ]
                    runtime = runtimes[key[0]]
                    authored_next = upper_overlay_runtime_rows(
                        runtime,
                        key[1],
                        context["clip_ids"],
                        context["frame_indices"][1],
                        context["gaze"],
                        device,
                    )
                    target_positions, target_rotations = full_pose_globals(
                        runtime,
                        context["lower_states"][2],
                        authored_next,
                        context["root_states"][2][0],
                        context["root_states"][2][1],
                        context["root_states"][2][2],
                        key[1],
                        context["clip_ids"],
                    )
                    full_clip = runtime.full_by_mode[key[1]]
                    body_by_name = {
                        name: index for index, name in enumerate(full_clip.body_names)
                    }
                    pose_indices = torch.tensor(
                        [body_by_name[name] for name in root_ae_data.POSE_BONES],
                        dtype=torch.long,
                        device=device,
                    )
                    position_error = torch.linalg.vector_norm(
                        predicted_positions.index_select(1, pose_indices)
                        - target_positions.index_select(1, pose_indices),
                        dim=-1,
                    ) * 100.0
                    rotation_error = rotation_error_degrees(
                        predicted_rotations.index_select(1, pose_indices),
                        target_rotations.index_select(1, pose_indices),
                    )
                    group_active = effective_k[
                        cursor : cursor + rows_per_mode
                    ] > int(rollout_step)
                    if bool(group_active.any()):
                        selected_position = position_error[group_active]
                        selected_rotation = rotation_error[group_active]
                        capture_position_errors.append(
                            selected_position.flatten().detach().cpu()
                        )
                        capture_rotation_errors.append(
                            selected_rotation.flatten().detach().cpu()
                        )
                        capture_head_errors.append(
                            selected_position[
                                :, root_ae_data.POSE_BONES.index("head")
                            ].detach().cpu()
                        )
                        capture_hand_l_errors.append(
                            selected_position[
                                :, root_ae_data.POSE_BONES.index("hand_l")
                            ].detach().cpu()
                        )
                        capture_hand_r_errors.append(
                            selected_position[
                                :, root_ae_data.POSE_BONES.index("hand_r")
                            ].detach().cpu()
                        )
                        if int(rollout_step) == int(rollout_k) - 1:
                            capture_end_position_errors.append(
                                selected_position.flatten().detach().cpu()
                            )
                cursor += rows_per_mode
            if capture_training_rollout:
                assert captured_feature_globals is not None
                if len(captured_feature_globals) != len(keys):
                    raise RuntimeError(
                        "Faithful capture did not receive one transform block per training group"
                    )
                if rollout_step == 0:
                    debug_positions_frames.append(
                        torch.cat(
                            [
                                values[0][rows_per_mode : rows_per_mode * 2]
                                for values in captured_feature_globals
                            ],
                            dim=0,
                        ).cpu()
                    )
                    debug_basis_frames.append(
                        torch.cat(
                            [
                                values[1][rows_per_mode : rows_per_mode * 2]
                                for values in captured_feature_globals
                            ],
                            dim=0,
                        ).cpu()
                    )
                    debug_root_position_frames.append(
                        torch.cat(
                            [scoring_context[key]["root_states"][1][0] for key in keys],
                            dim=0,
                        ).detach().cpu()
                    )
                    debug_root_rotation_frames.append(
                        torch.cat(
                            [scoring_context[key]["root_states"][1][1] for key in keys],
                            dim=0,
                        ).detach().cpu()
                    )
                    debug_source_frames.append(
                        torch.cat(
                            [scoring_context[key]["frame_indices"][0] for key in keys],
                            dim=0,
                        ).detach().cpu()
                    )
                debug_positions_frames.append(
                    torch.cat(
                        [
                            values[0][rows_per_mode * 2 :]
                            for values in captured_feature_globals
                        ],
                        dim=0,
                    ).cpu()
                )
                debug_basis_frames.append(
                    torch.cat(
                        [
                            values[1][rows_per_mode * 2 :]
                            for values in captured_feature_globals
                        ],
                        dim=0,
                    ).cpu()
                )
                debug_root_position_frames.append(
                    torch.cat(
                        [scoring_context[key]["root_states"][2][0] for key in keys],
                        dim=0,
                    ).detach().cpu()
                )
                debug_root_rotation_frames.append(
                    torch.cat(
                        [scoring_context[key]["root_states"][2][1] for key in keys],
                        dim=0,
                    ).detach().cpu()
                )
                debug_source_frames.append(
                    torch.cat(
                        [scoring_context[key]["frame_indices"][1] for key in keys],
                        dim=0,
                    ).detach().cpu()
                )
            features = torch.cat(feature_rows, dim=0)
            normalized = (features - mean) / std
            target = ae1_base_delta_target(ae, normalized)
            error = normalized[:, root_ae_data.DELTA] - target
            active = (effective_k > int(rollout_step)).to(dtype=error.dtype)
            row_ae1 = error.square().mean(dim=-1)
            ae1_loss = (row_ae1 * active * rollout_row_weight).sum()
            step_losses.append(ae1_loss)
            category_row_count = rows_per_mode * len(MODE_ORDER)
            for category_index, category in enumerate(CATEGORY_ORDER):
                category_slice = slice(
                    category_index * category_row_count,
                    (category_index + 1) * category_row_count,
                )
                # The full loss averages walk and run equally. Rescale each
                # half so ae1_walk and ae1_run are category means.
                step_category_losses[category].append(
                    (
                        row_ae1[category_slice]
                        * active[category_slice]
                        * rollout_row_weight[category_slice]
                    ).sum()
                    * float(len(CATEGORY_ORDER))
                )
            applied_delta_rms.append(applied_delta.square().mean().sqrt().detach())

            cursor = 0
            for key_index, key in enumerate(keys):
                next_values = next_upper[cursor : cursor + rows_per_mode]
                upper_state[key] = {
                    "previous": upper_state[key]["current"],
                    "current": next_values,
                    "current_base": next_bases[key_index],
                }
                upper_residual_rms.append(
                    (
                        upper_state[key]["current"]
                        - upper_state[key]["current_base"]
                    ).square().mean().sqrt().detach()
                )
                cursor += rows_per_mode

            for category in CATEGORY_ORDER:
                state = state_by_category[category]
                next_lower = next_lower_by_category[category]
                state["prev"] = state["cur"]
                state["cur"] = next_lower
                state["prev_pelvis"] = state["prev"][:, :3]
                state["cur_pelvis"] = state["cur"][:, :3]
                payload = lower_ctl.payload_slice(runtimes[category].store)
                state["prev_payload"] = state["prev"][:, payload]
                state["cur_payload"] = state["cur"][:, payload]
                state["cur_idx"] = state["cur_idx"] + 1

        capture_motion: dict[str, float] | None = None
        if capture_training_rollout:
            if not (
                capture_position_errors
                and capture_rotation_errors
                and capture_head_errors
                and capture_hand_l_errors
                and capture_hand_r_errors
                and capture_end_position_errors
            ):
                raise RuntimeError("Faithful rollout did not produce motion-quality metrics")
            all_position = torch.cat(capture_position_errors)
            all_rotation = torch.cat(capture_rotation_errors)
            all_head = torch.cat(capture_head_errors)
            all_hand_l = torch.cat(capture_hand_l_errors)
            all_hand_r = torch.cat(capture_hand_r_errors)
            end_position = torch.cat(capture_end_position_errors)
            capture_motion = {
                "pose_mean_cm": float(all_position.mean()),
                "pose_worst_cm": float(all_position.max()),
                "rotation_mean_deg": float(all_rotation.mean()),
                "rotation_worst_deg": float(all_rotation.max()),
                "head_mean_cm": float(all_head.mean()),
                "head_worst_cm": float(all_head.max()),
                "hand_l_mean_cm": float(all_hand_l.mean()),
                "hand_l_worst_cm": float(all_hand_l.max()),
                "hand_r_mean_cm": float(all_hand_r.mean()),
                "hand_r_worst_cm": float(all_hand_r.max()),
                "end_pose_mean_cm": float(end_position.mean()),
                "end_pose_worst_cm": float(end_position.max()),
            }

        loss = torch.stack(step_losses).sum()
        category_losses = {
            category: torch.stack(values).sum()
            for category, values in step_category_losses.items()
        }
        if not bool(torch.isfinite(loss)):
            raise RuntimeError(f"Non-finite AE1 loss at step {step}: {float(loss.detach().cpu())}")
        (loss / float(accumulation_steps)).backward()
        accumulated_loss_value += float(loss.detach().cpu()) / float(accumulation_steps)
        for category in CATEGORY_ORDER:
            accumulated_category_loss_value[category] += (
                float(category_losses[category].detach().cpu())
                / float(accumulation_steps)
            )
        accumulated_applied_delta_rms.extend(applied_delta_rms)
        accumulated_upper_residual_rms.extend(upper_residual_rms)
        accumulation_index += 1
        if accumulation_index < accumulation_steps:
            continue
        gradient_norm = torch.nn.utils.clip_grad_norm_(upper.parameters(), 50.0)
        if not bool(torch.isfinite(gradient_norm)):
            raise RuntimeError(f"Non-finite upper gradient at step {step}")
        optimizer.step()
        accumulation_index = 0
        step += 1
        session_steps += 1
        loss_value = accumulated_loss_value
        category_loss_values = dict(accumulated_category_loss_value)
        optimizer_applied_delta_rms = list(accumulated_applied_delta_rms)
        optimizer_upper_residual_rms = list(accumulated_upper_residual_rms)
        optimizer_clip_pairs = list(accumulated_clip_pairs)
        if capture_motion is None:
            raise RuntimeError("Optimizer step is missing faithful motion-quality metrics")
        optimizer_motion = dict(capture_motion)
        accumulated_loss_value = 0.0
        for category in CATEGORY_ORDER:
            accumulated_category_loss_value[category] = 0.0
        accumulated_applied_delta_rms.clear()
        accumulated_upper_residual_rms.clear()
        accumulated_clip_pairs.clear()
        if capture_training_rollout:
            expected_frames = int(rollout_k) + 1
            if not (
                len(debug_positions_frames)
                == len(debug_basis_frames)
                == len(debug_root_position_frames)
                == len(debug_root_rotation_frames)
                == len(debug_source_frames)
                == expected_frames
            ):
                raise RuntimeError(
                    "Faithful rollout frame capture mismatch: "
                    f"expected={expected_frames} positions={len(debug_positions_frames)} "
                    f"basis={len(debug_basis_frames)} roots={len(debug_root_position_frames)}"
                )
            request_path = run_dir / "debug" / "export_last_rollout.request.json"
            request_text: str | None = None
            request_payload: dict[str, Any] | None = None
            if request_path.is_file():
                try:
                    request_text = request_path.read_text(encoding="utf-8")
                    decoded_request = json.loads(request_text)
                    request_payload = (
                        decoded_request if isinstance(decoded_request, dict) else None
                    )
                except (OSError, json.JSONDecodeError):
                    request_payload = None
            debug_payload = exact_training_rollout_debug_payload(
                run_id,
                step,
                runtimes[CATEGORY_WALK],
                debug_rows,
                torch.stack(debug_positions_frames, dim=1),
                torch.stack(debug_basis_frames, dim=1),
                torch.stack(debug_root_position_frames, dim=1),
                torch.stack(debug_root_rotation_frames, dim=1),
                torch.stack(debug_source_frames, dim=1),
                request_payload,
            )
            debug_artifact = run_dir / "debug" / "last_batch_rollout.json"
            atomic_compact_json(debug_artifact, debug_payload)
            archive_now = time.monotonic()
            if (
                archive_now - last_rollout_archive
                >= ROLLOUT_ARCHIVE_INTERVAL_SECONDS
            ):
                archive_artifact = (
                    run_dir / "debug" / f"rollout_step_{step:08d}.json"
                )
                atomic_compact_json(archive_artifact, debug_payload)
                last_rollout_archive = archive_now
                print(
                    f"UPPER_CHRONOLOGICAL_ROLLOUT step={step} "
                    f"artifact={archive_artifact}",
                    flush=True,
                )
            if (
                request_text is not None
                and request_path.is_file()
                and request_path.read_text(encoding="utf-8") == request_text
            ):
                request_path.unlink()
            print(
                f"UPPER_EXACT_TRAINING_ROLLOUT step={step} rows={len(debug_rows)} "
                f"frames={expected_frames} artifact={debug_artifact}",
                flush=True,
            )
        recent_loss.append(loss_value)
        if len(recent_loss) > 100:
            recent_loss.pop(0)
        recent_mean = sum(recent_loss) / len(recent_loss)

        now = time.monotonic()
        elapsed = now - started
        should_log = step == 1 or now - last_log >= float(args.log_seconds)
        if should_log:
            last_log = now
            frozen_now = {
                category: model_tensor_digest(model)
                for category, model in frozen_models.items()
            }
            if frozen_now != frozen_digests:
                raise RuntimeError("A frozen lower model tensor changed")
            metric = {
                "step": step,
                "elapsed_minutes": elapsed / 60.0,
                "rollout_k": rollout_k,
                "rollout_mode": "mixed_geometric_at_max",
                "effective_k_mean": float(effective_k_float.mean().detach().cpu()),
                "effective_k_max": int(effective_k.max().detach().cpu()),
                "effective_k_counts": effective_rollout_k_counts(
                    int(args.batch_size), rollout_k
                ),
                "ae1_loss": loss_value,
                "ae1_recent_mean": recent_mean,
                "gradient_norm": float(gradient_norm.detach().cpu()),
                "applied_delta_rms": float(torch.stack(optimizer_applied_delta_rms).mean().cpu()),
                "upper_residual_rms": float(torch.stack(optimizer_upper_residual_rms).mean().cpu()),
                "gradient_accumulation_steps": accumulation_steps,
                "effective_batch_size": int(args.batch_size) * accumulation_steps,
                "active_clip_pairs": optimizer_clip_pairs,
                "gaze_zero_fraction": gaze_zero_rows / max(1, gaze_rows),
                "sampled_rows": dict(total_rows),
                "active_clips": sampled_relatives_by_category,
                "motion": optimizer_motion,
                "lower_models_unchanged": True,
                "finite": True,
            }
            for category in CATEGORY_ORDER:
                metric[f"ae1_{category}"] = category_loss_values[category]
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(metric, separators=(",", ":")) + "\n")
            tensorboard_values = {
                "ae1": metric["ae1_loss"],
                "optim/gradient_norm": metric["gradient_norm"],
                "motion/applied_delta_rms": metric["applied_delta_rms"],
                "motion/upper_residual_rms": metric["upper_residual_rms"],
                "motion/pose_mean_cm": metric["motion"]["pose_mean_cm"],
                "motion/pose_worst_cm": metric["motion"]["pose_worst_cm"],
                "motion/rotation_mean_deg": metric["motion"]["rotation_mean_deg"],
                "motion/rotation_worst_deg": metric["motion"]["rotation_worst_deg"],
                "motion/head_mean_cm": metric["motion"]["head_mean_cm"],
                "motion/head_worst_cm": metric["motion"]["head_worst_cm"],
                "motion/hand_l_mean_cm": metric["motion"]["hand_l_mean_cm"],
                "motion/hand_l_worst_cm": metric["motion"]["hand_l_worst_cm"],
                "motion/hand_r_mean_cm": metric["motion"]["hand_r_mean_cm"],
                "motion/hand_r_worst_cm": metric["motion"]["hand_r_worst_cm"],
                "motion/end_pose_mean_cm": metric["motion"]["end_pose_mean_cm"],
                "motion/end_pose_worst_cm": metric["motion"]["end_pose_worst_cm"],
                "curriculum/rollout_k": metric["rollout_k"],
                "curriculum/effective_rollout_k_mean": metric["effective_k_mean"],
                "curriculum/effective_rollout_k_max": metric["effective_k_max"],
                "timing/elapsed_minutes": metric["elapsed_minutes"],
                "integrity/lower_models_unchanged": 1.0,
                "integrity/finite": 1.0,
            }
            for category in CATEGORY_ORDER:
                tensorboard_values[f"ae1_{category}"] = metric[f"ae1_{category}"]
            for sample_name, sample_count in metric["sampled_rows"].items():
                tensorboard_values[f"sampling/rows_{sample_name}"] = sample_count
            for effective_value, effective_count in metric["effective_k_counts"].items():
                tensorboard_values[f"sampling/effective_k_{effective_value}_rows"] = effective_count
            for scalar_name, scalar_value in tensorboard_values.items():
                writer.add_scalar(scalar_name, float(scalar_value), step)
            writer.flush()
            atomic_json(
                status_path,
                {
                    "state": "training",
                    "pid": os.getpid(),
                    "run_dir": str(run_dir),
                    "latest": metric,
                    "immutable_contract": metadata,
                },
            )
            print(
                "UPPER_CONTROLLER_STEP "
                + " ".join(
                    [
                        f"step={step}",
                        f"elapsed_min={elapsed / 60.0:.2f}",
                        f"K={rollout_k}",
                        f"effK_mean={metric['effective_k_mean']:.3f}",
                        f"ae1={loss_value:.8f}",
                    ]
                    + [
                        f"ae1_{category}={metric[f'ae1_{category}']:.8f}"
                        for category in CATEGORY_ORDER
                    ]
                    + [
                        f"mean100={recent_mean:.8f}",
                        f"grad={float(gradient_norm.detach().cpu()):.5f}",
                        f"delta_rms={metric['applied_delta_rms']:.6f}",
                        f"residual_rms={metric['upper_residual_rms']:.6f}",
                        f"pose_cm={metric['motion']['pose_mean_cm']:.3f}/"
                        f"{metric['motion']['pose_worst_cm']:.3f}",
                        f"end_cm={metric['motion']['end_pose_mean_cm']:.3f}/"
                        f"{metric['motion']['end_pose_worst_cm']:.3f}",
                        f"gaze_zero={metric['gaze_zero_fraction']:.4f}",
                    ]
                ),
                flush=True,
            )

            if loss_value < best:
                best = loss_value
                save_checkpoint(
                    checkpoint_dir / f"{run_id}_best.pt",
                    upper,
                    optimizer,
                    step,
                    best,
                    elapsed,
                    rollout_k,
                    metadata,
                )

        if now - last_save >= float(args.save_minutes) * 60.0:
            last_save = now
            save_checkpoint(
                checkpoint_dir / f"{run_id}_latest.pt",
                upper,
                optimizer,
                step,
                best,
                elapsed,
                rollout_k,
                metadata,
            )

    elapsed = time.monotonic() - started
    _stage, rollout_k = configured_rollout_stage(elapsed)
    final_path = checkpoint_dir / f"{run_id}_latest.pt"
    save_checkpoint(
        final_path,
        upper,
        optimizer,
        step,
        best,
        elapsed,
        rollout_k,
        metadata,
    )
    atomic_json(
        status_path,
        {
            "state": "smoke_complete" if bool(args.smoke) else "complete",
            "pid": os.getpid(),
            "run_dir": str(run_dir),
            "checkpoint": str(final_path),
            "step": step,
            "elapsed_minutes": elapsed / 60.0,
            "rollout_k": rollout_k,
            "best": best,
            "sampled_rows": total_rows,
            "gaze_zero_fraction": gaze_zero_rows / max(1, gaze_rows),
            "immutable_contract": metadata,
        },
    )
    print(
        f"UPPER_CONTROLLER_DONE step={step} elapsed_min={elapsed / 60.0:.2f} "
        f"K={rollout_k} checkpoint={final_path}",
        flush=True,
    )
    writer.add_scalar("run/completed", 1.0, int(step))
    writer.close()
    active_marker_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train the AE1-only walk/run upper-body locomotion controller."
    )
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument(
        "--motion-scope",
        choices=("omni", "walk_forward"),
        default="omni",
    )
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--learning-rate", type=float, default=5.0e-6)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=4)
    parser.add_argument(
        "--fixed-k",
        type=int,
        choices=ROLLOUT_SCHEDULE,
        help="Hold maximum rollout K indefinitely; promotion requires a new launch.",
    )
    parser.add_argument("--init-checkpoint", type=Path)
    parser.add_argument(
        "--ae-checkpoint",
        type=Path,
        help=(
            "Use an explicit upper AE1 checkpoint for an isolated diagnostic or "
            "training run; the official pointer remains unchanged."
        ),
    )
    parser.add_argument("--load-optimizer", action="store_true")
    parser.add_argument("--log-seconds", type=float, default=30.0)
    parser.add_argument("--save-minutes", type=float, default=5.0)
    parser.add_argument("--max-hours", type=float, default=0.0)
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--smoke-steps", type=int, default=3)
    train(parser.parse_args())


if __name__ == "__main__":
    main()
