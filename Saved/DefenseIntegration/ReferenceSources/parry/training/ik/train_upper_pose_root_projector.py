from __future__ import annotations

"""Train and audit the root-transform upper AE1 pose projector.

The locomotion agent remains in its established 90D representation.  This
model's scored space is the actual root-relative transform of every upper
joint, so accumulated chain error is visible to the score.
"""

import argparse
import gc
import hashlib
import json
import math
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import torch
from torch.utils.tensorboard import SummaryWriter

import ik_core as tl
import train_upper_pose_autoencoder as upper_data
from naming import checkpoint_path, ik_run_id
from train_simple_autoencoder import SimpleAEConfig, equal_group_batch_indices, lr_for_step
from training.slashes2.conditional_delta_projector import (
    CalibratedConditionalDeltaProjector,
    ConditionalDeltaProjector,
    GatedCalibratedDeltaProjector,
    ResidualDenoisingDeltaProjector,
)


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
RUNS_ROOT = PROJECT_ROOT / "training" / "runs"
CACHE_ROOT = RUNS_ROOT / "cache" / "upper_pose_root_projector"

POSE_BONES = (
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
    "upperarm_l",
    "hand_l",
    "upperarm_r",
    "hand_r",
)
TRANSFORM_DIM = 9
POSE_DIM = len(POSE_BONES) * TRANSFORM_DIM
DELTA = slice(0, POSE_DIM)
PREVIOUS = slice(POSE_DIM, POSE_DIM * 2)
CURRENT = slice(POSE_DIM * 2, POSE_DIM * 3)
PELVIS_START = POSE_DIM * 3
PELVIS_END = PELVIS_START + upper_data.PELVIS_DIM * 3
ROOT_START = PELVIS_END
ROOT_END = ROOT_START + upper_data.ROOT_DIM
SWORD_START = ROOT_END
SWORD_END = SWORD_START + 1
FEET_START = SWORD_END
FEET_END = FEET_START + upper_data.FOOT_CONDITIONING_DIM
GAZE_START = FEET_END
GAZE_END = GAZE_START + upper_data.GAZE_DIM
FEATURE_DIM = GAZE_END

CACHE_VERSION = "upper_pose_root_projector_rows_v3_no_lowerarms_cycle_unwrapped"
GROUP_NAMES = ("walk_original", "walk_drawn", "run_original", "run_drawn")
GROUP_COUNT = len(GROUP_NAMES)
HORIZON = 32
PROJECTION_ITERATIONS = 16
POSITION_PERTURB_M = 0.05
ROTATION_PERTURB_DEG = 2.0
VARIANTS = ("clean", "normalized05", "physical_full", "physical_curriculum")


def motion_config() -> tl.TrainConfig:
    return upper_data.motion_config()


def clean_pose(values: torch.Tensor) -> torch.Tensor:
    one = values.ndim == 1
    work = values.unsqueeze(0) if one else values
    if work.ndim != 2 or int(work.shape[1]) != POSE_DIM:
        raise ValueError(f"Expected [N,{POSE_DIM}], got {tuple(values.shape)}")
    chunks: list[torch.Tensor] = []
    for index in range(len(POSE_BONES)):
        start = index * TRANSFORM_DIM
        chunks.extend((work[:, start : start + 3], tl.clean_6d(work[:, start + 3 : start + 9])))
    result = torch.cat(chunks, dim=-1)
    return result.squeeze(0) if one else result


def pose_from_globals(
    clip: tl.MotionClip,
    positions: torch.Tensor,
    rotations: torch.Tensor,
    reference_position: torch.Tensor,
    reference_heading: torch.Tensor,
) -> torch.Tensor:
    by_name = {name: index for index, name in enumerate(clip.body_names)}
    parts: list[torch.Tensor] = []
    for name in POSE_BONES:
        joint = by_name[name]
        position = upper_data.root_relative_position(
            positions[:, joint], reference_position, reference_heading
        )
        rotation = tl.rotmat_to_6d(
            upper_data.root_relative_rotation(rotations[:, joint], reference_heading)
        )
        parts.extend((position, rotation))
    return clean_pose(torch.cat(parts, dim=-1))


def posed_state(
    clip: tl.MotionClip,
    frame_indices: torch.Tensor,
    gaze: torch.Tensor,
) -> torch.Tensor:
    positions, rotations = upper_data.gaze_overlay_global_pose(clip, frame_indices, gaze)
    root_position = clip.root_pos.index_select(0, frame_indices)
    root_heading = clip.root_heading_rot.index_select(0, frame_indices)
    return pose_from_globals(clip, positions, rotations, root_position, root_heading)


def held_frame_states(
    clip: tl.MotionClip,
    cfg: tl.TrainConfig,
    previous: torch.Tensor,
    current: torch.Tensor,
    following: torch.Tensor,
    gaze: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    if clip.cyclic_animation:
        period = int(clip.cyclic_period)
        logical_previous = torch.remainder(previous, period)
        logical_current = torch.remainder(current, period)
        logical_following = torch.remainder(following, period)
    else:
        logical_previous = previous
        logical_current = current
        logical_following = following
    indices = torch.cat((logical_previous, logical_current, logical_following), dim=0)
    repeated_gaze = gaze.repeat(3, 1)
    count = int(current.numel())
    own = posed_state(clip, indices, repeated_gaze)
    previous_own = own[:count]
    current_own = own[count : count * 2]
    following_own = own[count * 2 :]
    previous_position, _previous_rotation, _previous_yaw, previous_heading = tl.root_state(
        clip, previous, cfg, torch.device("cpu")
    )
    current_position, _current_rotation, _current_yaw, current_heading = tl.root_state(
        clip, current, cfg, torch.device("cpu")
    )
    following_position, _following_rotation, _following_yaw, following_heading = tl.root_state(
        clip, following, cfg, torch.device("cpu")
    )
    previous_fixed = reframe_pose(
        previous_own,
        previous_position,
        previous_heading,
        current_position,
        current_heading,
    )
    following_fixed = reframe_pose(
        following_own,
        following_position,
        following_heading,
        current_position,
        current_heading,
    )
    return previous_fixed, current_own, following_fixed


def transition_rows(
    clip: tl.MotionClip,
    cfg: tl.TrainConfig,
    current: torch.Tensor,
    gaze: torch.Tensor,
    sword: float,
) -> torch.Tensor:
    if clip.cyclic_animation:
        period = int(clip.cyclic_period)
        previous = current - 1
        following = current + 1
        previous_logical = torch.remainder(previous, period)
        current_logical = torch.remainder(current, period)
        following_logical = torch.remainder(following, period)
    else:
        previous = (current - 1).clamp_min(0)
        following = current + 1
        previous_logical = previous
        current_logical = current
        following_logical = following
    previous_pose, current_pose, following_pose = held_frame_states(
        clip, cfg, previous, current, following, gaze
    )
    delta = following_pose - current_pose
    pelvis = upper_data.pelvis_root_features(clip)
    feet = upper_data.feet_root_features(clip)
    sword_column = torch.full((current.numel(), 1), float(sword), dtype=torch.float32)
    rows = torch.cat(
        (
            delta,
            previous_pose,
            current_pose,
            pelvis.index_select(0, previous_logical),
            pelvis.index_select(0, current_logical),
            pelvis.index_select(0, following_logical),
            upper_data.controller_root_features(clip, cfg, current),
            sword_column,
            feet.index_select(0, current_logical),
            feet.index_select(0, following_logical),
            gaze,
        ),
        dim=-1,
    ).contiguous()
    if rows.shape != (current.numel(), FEATURE_DIM):
        raise RuntimeError(f"root projector row mismatch: {tuple(rows.shape)}")
    if not bool(torch.isfinite(rows).all()):
        raise RuntimeError(f"non-finite root projector rows from {clip.path}")
    return rows


def group_for(relative: str, sword: float) -> int:
    category_offset = 0 if relative.startswith("walk_") else 2
    mode_offset = 0 if sword < 0.0 else 1
    return category_offset + mode_offset


def cache_identity() -> tuple[list[tuple[str, Path, bool]], list[tuple[str, Path, bool]], str]:
    original, drawn, source_fingerprint = upper_data.matched_dataset()
    digest = hashlib.sha256()
    digest.update(CACHE_VERSION.encode("utf-8"))
    digest.update(source_fingerprint.encode("ascii"))
    digest.update("|".join(POSE_BONES).encode("utf-8"))
    return original, drawn, digest.hexdigest()


def prepare_dataset(force_rebuild: bool = False) -> tuple[torch.Tensor, torch.Tensor, dict[str, Any], Path]:
    original, drawn, fingerprint = cache_identity()
    path = CACHE_ROOT / f"{CACHE_VERSION}_{fingerprint[:16]}.pt"
    if path.is_file() and not force_rebuild:
        payload = torch.load(path, map_location="cpu", weights_only=False)
        if payload.get("fingerprint") != fingerprint:
            raise RuntimeError(f"cache fingerprint mismatch: {path}")
        return payload["rows"].float(), payload["groups"].long(), dict(payload["metadata"]), path

    cfg = motion_config()
    chunks: list[torch.Tensor] = []
    group_chunks: list[torch.Tensor] = []
    row_counts = [0] * GROUP_COUNT
    zero_gaze = 0
    for specs, sword in ((original, -1.0), (drawn, 1.0)):
        for relative, source, cyclic in specs:
            clip = tl.MotionClip(source, cfg, cyclic_animation=cyclic)
            if cyclic:
                # Use raw times 1..period inclusive so phase zero is represented
                # at the end of an unwrapped cycle and never needs a negative root.
                current = torch.arange(1, int(clip.cyclic_period) + 1, dtype=torch.long)
            else:
                count = int(clip.T) - int(cfg.future_window)
                current = torch.arange(max(0, count), dtype=torch.long)
            if current.numel() < 2:
                raise RuntimeError(f"clip too short: {source}")
            gaze = upper_data.sampled_window_gaze(relative, int(current.numel()))
            rows = transition_rows(clip, cfg, current, gaze, sword)
            group = group_for(relative, sword)
            chunks.append(rows)
            group_chunks.append(torch.full((rows.shape[0],), group, dtype=torch.long))
            row_counts[group] += int(rows.shape[0])
            zero_gaze += int((gaze == 0.0).all(dim=-1).sum())
            print(
                f"ROOT_AE_CACHE_BUILD group={GROUP_NAMES[group]} clipsource={relative} rows={rows.shape[0]}",
                flush=True,
            )
    rows = torch.cat(chunks, dim=0)
    groups = torch.cat(group_chunks, dim=0)
    metadata = {
        "version": CACHE_VERSION,
        "fingerprint": fingerprint,
        "row_count": int(rows.shape[0]),
        "feature_dim": FEATURE_DIM,
        "pose_dim": POSE_DIM,
        "pose_bones": list(POSE_BONES),
        "group_names": list(GROUP_NAMES),
        "group_row_counts": row_counts,
        "zero_gaze_rows": zero_gaze,
        "zero_gaze_fraction": zero_gaze / float(max(1, rows.shape[0])),
        "original_root": str(upper_data.ORIGINAL_ROOT),
        "drawn_root": str(upper_data.SWORD_ROOT),
    }
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save({"fingerprint": fingerprint, "rows": rows, "groups": groups, "metadata": metadata}, temporary)
    os.replace(temporary, path)
    return rows, groups, metadata, path


def equal_group_normalization(
    rows: torch.Tensor, groups: torch.Tensor, std_floor: float
) -> tuple[torch.Tensor, torch.Tensor]:
    means = []
    second = []
    for group in range(GROUP_COUNT):
        values = rows[groups == group].double()
        means.append(values.mean(dim=0))
        second.append((values * values).mean(dim=0))
    mean64 = torch.stack(means).mean(dim=0)
    second64 = torch.stack(second).mean(dim=0)
    std64 = torch.sqrt((second64 - mean64.square()).clamp_min(0.0)).clamp_min(std_floor)
    return mean64.float(), std64.float()


def random_axis_angle_correction(
    count: int,
    joint_count: int,
    maximum_degrees: torch.Tensor,
    device: torch.device,
) -> torch.Tensor:
    axes = torch.randn((count, joint_count, 3), device=device)
    axes = axes / axes.norm(dim=-1, keepdim=True).clamp_min(1.0e-8)
    angles = (
        (torch.rand((count, joint_count), device=device) * 2.0 - 1.0)
        * maximum_degrees
        * math.pi
        / 180.0
    )
    return tl.axis_angle_to_row_matrix(
        axes.reshape(-1, 3), angles.reshape(-1)
    ).reshape(count, joint_count, 3, 3)


def physical_perturb(
    pose: torch.Tensor,
    position_max_m: torch.Tensor,
    rotation_max_deg: torch.Tensor,
) -> torch.Tensor:
    count = int(pose.shape[0])
    shaped = pose.reshape(count, len(POSE_BONES), TRANSFORM_DIM).clone()
    directions = torch.randn((count, len(POSE_BONES), 3), device=pose.device)
    directions = directions / directions.norm(dim=-1, keepdim=True).clamp_min(1.0e-8)
    radius = torch.rand((count, len(POSE_BONES), 1), device=pose.device) * position_max_m
    shaped[:, :, :3] += directions * radius
    rotations = tl.rotation_6d_to_matrix(shaped[:, :, 3:9].reshape(-1, 6)).reshape(
        count, len(POSE_BONES), 3, 3
    )
    correction = random_axis_angle_correction(
        count, len(POSE_BONES), rotation_max_deg, pose.device
    )
    shaped[:, :, 3:9] = tl.rotmat_to_6d(rotations @ correction)
    return clean_pose(shaped.reshape(count, POSE_DIM))


def corrupt_states(
    normalized: torch.Tensor,
    mean: torch.Tensor,
    std: torch.Tensor,
    variant: str,
) -> tuple[torch.Tensor, torch.Tensor]:
    model_input = normalized.clone()
    clean_delta_raw = normalized[:, DELTA] * std[DELTA] + mean[DELTA]
    clean_previous_raw = normalized[:, PREVIOUS] * std[PREVIOUS] + mean[PREVIOUS]
    clean_current_raw = normalized[:, CURRENT] * std[CURRENT] + mean[CURRENT]
    previous_raw = clean_previous_raw.clone()
    current_raw = clean_current_raw.clone()
    count = int(normalized.shape[0])

    if variant == "normalized05":
        scale = torch.rand((count, 1), device=normalized.device) * 0.05
        previous_raw += torch.randn_like(previous_raw) * scale * std[PREVIOUS]
        current_raw += torch.randn_like(current_raw) * scale * std[CURRENT]
        previous_raw = clean_pose(previous_raw)
        current_raw = clean_pose(current_raw)
    elif variant in ("physical_full", "physical_curriculum"):
        if variant == "physical_full":
            position_max = torch.full((count, 1, 1), POSITION_PERTURB_M, device=normalized.device)
            rotation_max = torch.full((count, 1), ROTATION_PERTURB_DEG, device=normalized.device)
        else:
            tiers = torch.randint(0, 4, (count,), device=normalized.device)
            position_levels = torch.tensor((0.0, 0.01, 0.025, 0.05), device=normalized.device)
            rotation_levels = torch.tensor((0.0, 0.5, 1.0, 2.0), device=normalized.device)
            position_max = position_levels.index_select(0, tiers).reshape(count, 1, 1)
            rotation_max = rotation_levels.index_select(0, tiers).reshape(count, 1)
        previous_raw = physical_perturb(previous_raw, position_max, rotation_max)
        current_raw = physical_perturb(current_raw, position_max, rotation_max)
    elif variant != "clean":
        raise ValueError(variant)

    corrected_delta_raw = clean_delta_raw - (current_raw - clean_current_raw)
    model_input[:, PREVIOUS] = (previous_raw - mean[PREVIOUS]) / std[PREVIOUS]
    model_input[:, CURRENT] = (current_raw - mean[CURRENT]) / std[CURRENT]
    target = (corrected_delta_raw - mean[DELTA]) / std[DELTA]

    # The architecture deliberately cannot copy the proposal.  Populate it
    # with broad candidates so the public AE score is exercised during train.
    modes = torch.randint(0, 5, (count,), device=normalized.device)
    current_delta = (current_raw - previous_raw - mean[DELTA]) / std[DELTA]
    zero = (torch.zeros_like(clean_delta_raw) - mean[DELTA]) / std[DELTA]
    shuffled = target[torch.randperm(count, device=normalized.device)]
    random = torch.randn_like(target)
    noisy = target + 0.10 * torch.randn_like(target)
    candidate = torch.where(
        (modes == 0)[:, None],
        noisy,
        torch.where(
            (modes == 1)[:, None],
            current_delta,
            torch.where(
                (modes == 2)[:, None],
                zero,
                torch.where((modes == 3)[:, None], shuffled, random),
            ),
        ),
    )
    model_input[:, DELTA] = candidate
    return model_input, target


def reframe_pose(
    pose: torch.Tensor,
    source_position: torch.Tensor,
    source_heading: torch.Tensor,
    target_position: torch.Tensor,
    target_heading: torch.Tensor,
) -> torch.Tensor:
    count = int(pose.shape[0])
    shaped = pose.reshape(count, len(POSE_BONES), TRANSFORM_DIM)
    result = shaped.clone()
    world_position = source_position[:, None, :] + torch.matmul(
        shaped[:, :, :3].unsqueeze(-2), source_heading[:, None]
    ).squeeze(-2)
    result[:, :, :3] = torch.matmul(
        (world_position - target_position[:, None, :]).unsqueeze(-2),
        target_heading[:, None].transpose(-1, -2),
    ).squeeze(-2)
    source_rotation = tl.rotation_6d_to_matrix(shaped[:, :, 3:9].reshape(-1, 6)).reshape(
        count, len(POSE_BONES), 3, 3
    )
    world_rotation = source_rotation @ source_heading[:, None]
    target_rotation = world_rotation @ target_heading[:, None].transpose(-1, -2)
    result[:, :, 3:9] = tl.rotmat_to_6d(target_rotation)
    return clean_pose(result.reshape(count, POSE_DIM))


class ForwardWalkAudit:
    def __init__(self, cfg: tl.TrainConfig, device: torch.device) -> None:
        self.cfg = cfg
        self.device = device
        self.cases: list[dict[str, Any]] = []
        relative = "walk_omni/M_Neutral_Walk_Loop_F.npz"
        for mode_name, sword, root in (
            ("original", -1.0, upper_data.ORIGINAL_ROOT),
            ("drawn", 1.0, upper_data.SWORD_ROOT),
        ):
            clip = tl.MotionClip(root / relative, cfg, cyclic_animation=True)
            period = int(clip.cyclic_period)
            starts = torch.arange(1, period + 1, dtype=torch.long)
            logical_starts = torch.remainder(starts, period)
            zero_gaze = torch.zeros((period, 2), dtype=torch.float32)
            poses = posed_state(
                clip,
                torch.arange(period, dtype=torch.long),
                torch.zeros((period, 2), dtype=torch.float32),
            )
            pelvis = upper_data.pelvis_root_features(clip)
            feet = upper_data.feet_root_features(clip)
            root_features = upper_data.controller_root_features(clip, cfg, starts)
            self.cases.append(
                {
                    "mode": mode_name,
                    "sword": sword,
                    "clip": clip,
                    "period": period,
                    "starts": starts,
                    "logical_starts": logical_starts,
                    "gaze": zero_gaze,
                    "poses": poses,
                    "pelvis": pelvis,
                    "feet": feet,
                    "root_features": root_features,
                }
            )

    def conditioning(self, case: dict[str, Any], indices: torch.Tensor) -> torch.Tensor:
        period = int(case["period"])
        current = torch.remainder(indices, period)
        previous = torch.remainder(indices - 1, period)
        following = torch.remainder(indices + 1, period)
        # The feature is cycle invariant.  Index by logical phase while phase
        # zero occupies the final row of the 1..period precomputation.
        root_row = torch.remainder(current - 1, period)
        sword = torch.full((indices.numel(), 1), float(case["sword"]), dtype=torch.float32)
        return torch.cat(
            (
                case["pelvis"].index_select(0, previous),
                case["pelvis"].index_select(0, current),
                case["pelvis"].index_select(0, following),
                case["root_features"].index_select(0, root_row),
                sword,
                case["feet"].index_select(0, current),
                case["feet"].index_select(0, following),
                case["gaze"].index_select(0, current),
            ),
            dim=-1,
        )

    @torch.no_grad()
    def rollout(
        self,
        model: torch.nn.Module,
        mean: torch.Tensor,
        std: torch.Tensor,
        perturbed: bool,
        seed: int = 49381,
    ) -> dict[str, Any]:
        model.eval()
        all_frame_errors: list[torch.Tensor] = []
        per_mode: dict[str, float] = {}
        recovery_k1: dict[str, float] = {}
        for case_index, case in enumerate(self.cases):
            clip: tl.MotionClip = case["clip"]
            period = int(case["period"])
            starts = case["starts"]
            previous_logical = torch.remainder(starts - 1, period)
            current_logical = torch.remainder(starts, period)
            previous = case["poses"].index_select(0, previous_logical).to(self.device)
            current = case["poses"].index_select(0, current_logical).to(self.device)
            if perturbed:
                devices = []
                if self.device.type == "cuda":
                    devices = [self.device.index if self.device.index is not None else torch.cuda.current_device()]
                with torch.random.fork_rng(devices=devices):
                    torch.manual_seed(seed + case_index)
                    if self.device.type == "cuda":
                        torch.cuda.manual_seed_all(seed + case_index)
                    pos = torch.full((period, 1, 1), POSITION_PERTURB_M, device=self.device)
                    rot = torch.full((period, 1), ROTATION_PERTURB_DEG, device=self.device)
                    current = physical_perturb(current, pos, rot)
            mode_errors: list[torch.Tensor] = []
            for step in range(HORIZON):
                indices = starts + step
                next_indices = indices + 1
                next_logical = torch.remainder(next_indices, period)
                source_pos, _source_rot, _source_yaw, source_heading = tl.root_state(
                    clip, indices - 1, self.cfg, self.device
                )
                current_pos, _current_rot, _current_yaw, current_heading = tl.root_state(
                    clip, indices, self.cfg, self.device
                )
                next_pos, _next_rot, _next_yaw, next_heading = tl.root_state(
                    clip, next_indices, self.cfg, self.device
                )
                previous_fixed = reframe_pose(
                    previous, source_pos, source_heading, current_pos, current_heading
                )
                candidate_fixed = clean_pose(current + 2.0 * (current - previous_fixed))
                candidate_delta = candidate_fixed - current
                condition = self.conditioning(case, indices.cpu()).to(self.device)
                row = torch.cat((candidate_delta, previous_fixed, current, condition), dim=-1)
                projected = row
                for _ in range(PROJECTION_ITERATIONS):
                    reconstructed = model((projected - mean) / std) * std + mean
                    projected = projected.clone()
                    projected[:, DELTA] = reconstructed[:, DELTA]
                next_fixed = clean_pose(current + projected[:, DELTA])
                next_pose = reframe_pose(
                    next_fixed, current_pos, current_heading, next_pos, next_heading
                )
                gt = case["poses"].index_select(0, next_logical).to(self.device)
                pred_pos = next_pose.reshape(period, len(POSE_BONES), TRANSFORM_DIM)[:, :, :3]
                gt_pos = gt.reshape(period, len(POSE_BONES), TRANSFORM_DIM)[:, :, :3]
                error = torch.sqrt(torch.mean((pred_pos - gt_pos).square(), dim=(-1, -2))) * 100.0
                mode_errors.append(error.cpu())
                previous, current = current, next_pose
            stacked = torch.stack(mode_errors, dim=1)
            all_frame_errors.append(stacked)
            per_mode[str(case["mode"])] = float(stacked.max().item())
            recovery_k1[str(case["mode"])] = float(stacked[:, 0].max().item())
        combined = torch.cat(all_frame_errors, dim=0)
        by_horizon = {
            str(step + 1): {
                "mean_cm": float(combined[:, step].mean().item()),
                "worst_cm": float(combined[:, step].max().item()),
            }
            for step in range(HORIZON)
        }
        return {
            "perturbed": perturbed,
            "position_perturb_m": POSITION_PERTURB_M if perturbed else 0.0,
            "rotation_perturb_deg": ROTATION_PERTURB_DEG if perturbed else 0.0,
            "all_start_count": int(combined.shape[0]),
            "frames_per_start": HORIZON,
            "mean_upper_joint_position_rmse_cm": float(combined.mean().item()),
            "p95_upper_joint_position_rmse_cm": float(torch.quantile(combined.flatten(), 0.95).item()),
            "strict_worst_frame_upper_joint_position_rmse_cm": float(combined.max().item()),
            "strict_worst_by_mode_cm": per_mode,
            "recovery_k1_worst_by_mode_cm": recovery_k1,
            "by_horizon": by_horizon,
            "strict_below_1cm": bool(float(combined.max().item()) < 1.0),
            "finite": bool(torch.isfinite(combined).all().item()),
        }

    def gradient_audit(
        self,
        model: torch.nn.Module,
        mean: torch.Tensor,
        std: torch.Tensor,
        seed: int = 81277,
    ) -> dict[str, Any]:
        model.eval()
        cosines: list[torch.Tensor] = []
        improvement: list[torch.Tensor] = []
        for case_index, case in enumerate(self.cases):
            clip: tl.MotionClip = case["clip"]
            period = int(case["period"])
            indices = case["starts"]
            previous_logical = torch.remainder(indices - 1, period)
            current_logical = torch.remainder(indices, period)
            next_raw = indices + 1
            next_logical = torch.remainder(next_raw, period)
            previous = case["poses"].index_select(0, previous_logical).to(self.device)
            current_clean = case["poses"].index_select(0, current_logical).to(self.device)
            devices = []
            if self.device.type == "cuda":
                devices = [self.device.index if self.device.index is not None else torch.cuda.current_device()]
            with torch.random.fork_rng(devices=devices):
                torch.manual_seed(seed + case_index)
                if self.device.type == "cuda":
                    torch.cuda.manual_seed_all(seed + case_index)
                current = physical_perturb(
                    current_clean,
                    torch.full((period, 1, 1), POSITION_PERTURB_M, device=self.device),
                    torch.full((period, 1), ROTATION_PERTURB_DEG, device=self.device),
                )
            previous_fixed = reframe_pose(
                previous,
                tl.root_state(clip, indices - 1, self.cfg, self.device)[0],
                tl.root_state(clip, indices - 1, self.cfg, self.device)[3],
                tl.root_state(clip, indices, self.cfg, self.device)[0],
                tl.root_state(clip, indices, self.cfg, self.device)[3],
            )
            candidate_fixed = clean_pose(current + 2.0 * (current - previous_fixed))
            candidate_delta = candidate_fixed - current
            condition = self.conditioning(case, indices.cpu()).to(self.device)
            fixed = torch.cat((previous_fixed, current, condition), dim=-1)
            candidate_normalized = ((candidate_delta - mean[DELTA]) / std[DELTA]).detach().requires_grad_(True)
            normalized_row = torch.cat((candidate_normalized, (fixed - mean[POSE_DIM:]) / std[POSE_DIM:]), dim=-1)
            reconstructed = model(normalized_row)[:, DELTA]
            score = (reconstructed - candidate_normalized).square().mean(dim=-1)
            gradient = torch.autograd.grad(score.sum(), candidate_normalized)[0]
            gt_next = case["poses"].index_select(0, next_logical).to(self.device)
            gt_next_fixed = reframe_pose(
                gt_next,
                tl.root_state(clip, next_raw, self.cfg, self.device)[0],
                tl.root_state(clip, next_raw, self.cfg, self.device)[3],
                tl.root_state(clip, indices, self.cfg, self.device)[0],
                tl.root_state(clip, indices, self.cfg, self.device)[3],
            )
            gt_delta_normalized = ((gt_next_fixed - current - mean[DELTA]) / std[DELTA]).detach()
            desired = gt_delta_normalized - candidate_normalized.detach()
            update = -gradient
            cosine = torch.nn.functional.cosine_similarity(update, desired, dim=-1)
            cosines.append(cosine.detach().cpu())
            before = torch.linalg.vector_norm(desired, dim=-1)
            step_size = torch.sum(desired * update, dim=-1) / torch.sum(update * update, dim=-1).clamp_min(1.0e-12)
            bounded_step = step_size.clamp(0.0, 1.0)
            after_candidate = candidate_normalized.detach() + bounded_step[:, None] * update
            after = torch.linalg.vector_norm(gt_delta_normalized - after_candidate, dim=-1)
            improvement.append((after < before).detach().cpu())
        cosine_all = torch.cat(cosines)
        improvement_all = torch.cat(improvement)
        return {
            "position_perturb_m": POSITION_PERTURB_M,
            "rotation_perturb_deg": ROTATION_PERTURB_DEG,
            "sample_count": int(cosine_all.numel()),
            "mean_cosine_negative_gradient_to_gt": float(cosine_all.mean().item()),
            "minimum_cosine_negative_gradient_to_gt": float(cosine_all.min().item()),
            "positive_cosine_fraction": float((cosine_all > 0.0).float().mean().item()),
            "gradient_step_improves_fraction": float(improvement_all.float().mean().item()),
            "all_gradients_point_toward_gt": bool((cosine_all > 0.0).all().item()),
            "all_gradient_steps_improve": bool(improvement_all.all().item()),
            "finite": bool(torch.isfinite(cosine_all).all().item()),
        }


def checkpoint_payload(
    model: torch.nn.Module,
    optimizer: torch.optim.Optimizer,
    cfg: SimpleAEConfig,
    mean: torch.Tensor,
    std: torch.Tensor,
    metadata: dict[str, Any],
    step: int,
    best: float,
    audit: dict[str, Any],
    *,
    include_optimizer: bool = True,
) -> dict[str, Any]:
    payload = {
        "kind": "upper_pose_root_transform_conditional_projector",
        "model": model.state_dict(),
        "config": asdict(cfg),
        "projector": {
            "architecture": str(metadata["training_contract"]["projector_architecture"]),
            "input_dim": FEATURE_DIM,
            "motion_dim": POSE_DIM,
            "hidden_dim": cfg.hidden_dim,
            "num_hidden_layers": cfg.num_hidden_layers,
        },
        "schema": {
            "total_dim": FEATURE_DIM,
            "scored_delta": [DELTA.start, DELTA.stop],
            "previous_pose": [PREVIOUS.start, PREVIOUS.stop],
            "current_pose": [CURRENT.start, CURRENT.stop],
            "pelvis": [PELVIS_START, PELVIS_END],
            "root_window": [ROOT_START, ROOT_END],
            "sword": [SWORD_START, SWORD_END],
            "feet_current_next": [FEET_START, FEET_END],
            "gaze": [GAZE_START, GAZE_END],
            "pose_bones": list(POSE_BONES),
            "transform_per_bone": "root_relative_position3_rotation6",
        },
        "mean": mean.detach().cpu(),
        "std": std.detach().cpu(),
        "metadata": metadata,
        "step": int(step),
        "best": float(best),
        "audit": audit,
    }
    if include_optimizer:
        payload["optimizer"] = optimizer.state_dict()
    return payload


def atomic_save(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(payload, temporary)
    os.replace(temporary, path)


@torch.no_grad()
def perfect_gt_reconstruction_metrics(
    model: torch.nn.Module,
    normalized: torch.Tensor,
    groups: torch.Tensor,
    chunk_size: int = 2048,
) -> dict[str, Any]:
    group_sums = torch.zeros(GROUP_COUNT, dtype=torch.float64)
    group_counts = torch.zeros(GROUP_COUNT, dtype=torch.long)
    group_maximum = torch.zeros(GROUP_COUNT, dtype=torch.float32)
    for start in range(0, int(normalized.shape[0]), int(chunk_size)):
        values = normalized[start : start + int(chunk_size)]
        selected_groups = groups[start : start + int(chunk_size)]
        reconstruction = model(values)[:, DELTA]
        row_error = (
            reconstruction - values[:, DELTA]
        ).square().mean(dim=-1).detach().cpu()
        selected_groups_cpu = selected_groups.detach().cpu()
        for group in range(GROUP_COUNT):
            selected = row_error[selected_groups_cpu == group]
            if selected.numel() == 0:
                continue
            group_sums[group] += selected.double().sum()
            group_counts[group] += int(selected.numel())
            group_maximum[group] = torch.maximum(
                group_maximum[group], selected.max()
            )
    if bool((group_counts == 0).any()):
        raise RuntimeError(
            f"Perfect-GT audit has empty groups: {group_counts.tolist()}"
        )
    group_mean = group_sums / group_counts.double()
    equal_group_mean = float(group_mean.mean().item())
    return {
        "metric": "normalized scored-delta MSE on an uncorrupted perfect-GT row",
        "group_names": list(GROUP_NAMES),
        "group_mean": [float(value) for value in group_mean.tolist()],
        "equal_group_mean": equal_group_mean,
        "worst_group_mean": float(group_mean.max().item()),
        "group_maximum_row": [float(value) for value in group_maximum.tolist()],
        "finite": bool(
            torch.isfinite(group_mean).all()
            and torch.isfinite(group_maximum).all()
        ),
    }


def train(args: argparse.Namespace) -> Path:
    if args.variant not in VARIANTS:
        raise ValueError(args.variant)
    rows, groups, dataset_metadata, cache = prepare_dataset(args.rebuild_cache)
    mean_cpu, std_cpu = equal_group_normalization(rows, groups, args.std_floor)
    normalized = (rows - mean_cpu) / std_cpu
    del rows
    gc.collect()
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable")
    if device.type == "cuda":
        free, total = torch.cuda.mem_get_info(device)
        print(f"ROOT_AE_GPU free_mib={free/2**20:.0f} total_mib={total/2**20:.0f}", flush=True)
        if free / 2**20 < args.minimum_cuda_free_mib:
            raise RuntimeError(f"Only {free/2**20:.0f} MiB CUDA memory free")
    cfg = SimpleAEConfig(
        latent_dim=POSE_DIM,
        hidden_dim=args.hidden_dim,
        num_hidden_layers=args.hidden_layers,
        batch_size=args.batch_size,
        train_steps=args.train_steps,
        learning_rate=args.learning_rate,
        weight_decay=1.0e-5,
        std_floor=args.std_floor,
        val_fraction=0.0,
        seed=args.seed,
        pose_representation="upper_root_transforms",
        body_mode="upper_body",
        feature="state_conditioned_root_transform_delta",
        ae_feature_mode="pose",
        ae_score_scope="root_transform_delta_only",
        window_frames=2,
        denoise_noise_std=0.05 if args.variant == "normalized05" else 0.0,
    )
    torch.manual_seed(cfg.seed)
    projector_class = {
        "condition_only": ConditionalDeltaProjector,
        "residual_denoising": ResidualDenoisingDeltaProjector,
        "calibrated_condition": CalibratedConditionalDeltaProjector,
        "gated_calibrated": GatedCalibratedDeltaProjector,
    }[args.projector_architecture]
    model = projector_class(
        FEATURE_DIM, POSE_DIM, cfg.hidden_dim, cfg.num_hidden_layers
    ).to(device)
    initialization: dict[str, Any] | None = None
    if args.init_checkpoint is not None:
        init_path = args.init_checkpoint.resolve()
        init_checkpoint = torch.load(
            init_path, map_location="cpu", weights_only=False
        )
        if init_checkpoint.get("kind") != "upper_pose_root_transform_conditional_projector":
            raise RuntimeError(f"Not a root-transform upper AE1: {init_path}")
        projector = dict(init_checkpoint.get("projector", {}))
        expected_projector = {
            "input_dim": FEATURE_DIM,
            "motion_dim": POSE_DIM,
            "hidden_dim": cfg.hidden_dim,
            "num_hidden_layers": cfg.num_hidden_layers,
        }
        for key, expected in expected_projector.items():
            if int(projector.get(key, -1)) != int(expected):
                raise RuntimeError(
                    f"Initialization projector {key}={projector.get(key)!r}, "
                    f"expected {expected}"
                )
        init_architecture = str(
            projector.get("architecture", "condition_only")
        )
        calibrated_from_condition = bool(
            args.projector_architecture
            in ("calibrated_condition", "gated_calibrated")
            and init_architecture == "condition_only"
        )
        if init_architecture != str(args.projector_architecture) and not calibrated_from_condition:
            raise RuntimeError(
                f"Initialization projector architecture={init_architecture!r}, "
                f"expected {args.projector_architecture!r}"
            )
        if not torch.allclose(
            init_checkpoint["mean"].float(), mean_cpu, atol=1.0e-7, rtol=1.0e-6
        ) or not torch.allclose(
            init_checkpoint["std"].float(), std_cpu, atol=1.0e-7, rtol=1.0e-6
        ):
            raise RuntimeError(
                "Initialization AE1 normalization does not match the unchanged dataset"
            )
        if calibrated_from_condition:
            assert isinstance(
                model,
                (CalibratedConditionalDeltaProjector, GatedCalibratedDeltaProjector),
            )
            model.base.load_state_dict(init_checkpoint["model"], strict=True)
            model.freeze_base()
        else:
            model.load_state_dict(init_checkpoint["model"], strict=True)
        initialization = {
            "checkpoint": str(init_path),
            "checkpoint_step": int(init_checkpoint.get("step", -1)),
            "checkpoint_kind": str(init_checkpoint.get("kind")),
        }
    if (
        args.projector_architecture
        in ("calibrated_condition", "gated_calibrated")
        and initialization is None
    ):
        raise RuntimeError(
            "Calibrated projector requires the accepted condition-only AE1 initialization"
        )
    optimizer = torch.optim.AdamW(
        [parameter for parameter in model.parameters() if parameter.requires_grad],
        lr=cfg.learning_rate,
        weight_decay=cfg.weight_decay,
    )
    suffix = (
        f"cleanGTw{args.clean_gt_weight:g}_"
        if float(args.clean_gt_weight) > 0.0
        else ""
    )
    architecture_suffix = (
        "resdenoise_"
        if args.projector_architecture == "residual_denoising"
        else "calibrated_"
        if args.projector_architecture == "calibrated_condition"
        else "gatedcal_"
        if args.projector_architecture == "gated_calibrated"
        else ""
    )
    run_id = ik_run_id(f"upper_root_ae1_{args.variant}_{architecture_suffix}{suffix}h{cfg.hidden_dim}_l{cfg.num_hidden_layers}_{cfg.train_steps}step")
    run_dir = RUNS_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    writer = SummaryWriter(log_dir=str(run_dir / "tb"), flush_secs=1)
    metadata = {
        "variant": args.variant,
        "dataset_cache": str(cache),
        "dataset": dataset_metadata,
        "initialization": initialization,
        "training_contract": {
            "agent_representation_changed": False,
            "projector_architecture": str(args.projector_architecture),
            "residual_projection_correction_limit_normalized": (
                0.25
                if args.projector_architecture == "residual_denoising"
                else None
            ),
            "accepted_condition_projector_frozen": bool(
                args.projector_architecture
                in ("calibrated_condition", "gated_calibrated")
            ),
            "gate_supervision_weight": float(args.gate_loss_weight),
            "clean_context_constant_velocity_hard_negative_weight": float(
                args.hard_negative_weight
            ),
            "scored_pose": "14 actual upper joint transforms relative to root heading; lowerarm_l and lowerarm_r are excluded because the unchanged 90D agent has no lower-arm transform DOF",
            "conditioning": "previous/current pose, pelvis previous/current/next, root window, sword, feet current/next, gaze",
            "candidate_modes": ["noisy_correct", "constant_velocity", "zero", "shuffled", "random"],
            "physical_perturb_position_m": POSITION_PERTURB_M,
            "physical_perturb_rotation_deg": ROTATION_PERTURB_DEG,
            "perfect_gt_loss_weight": float(args.clean_gt_weight),
            "perfect_gt_acceptance_equal_group_mean_normalized_mse": float(
                args.clean_gt_target
            ),
            "checkpoint_optimizer_state_included": not bool(
                args.lightweight_checkpoints
            ),
        },
    }
    (run_dir / "config.json").write_text(
        json.dumps({"config": asdict(cfg), "metadata": metadata}, indent=2), encoding="utf-8"
    )
    normalized = normalized.to(device)
    groups_device = groups.to(device)
    all_indices = torch.arange(normalized.shape[0], device=device)
    group_rows = [all_indices[groups_device == group] for group in range(GROUP_COUNT)]
    mean = mean_cpu.to(device)
    std = std_cpu.to(device)
    audit_runner = ForwardWalkAudit(motion_config(), device)
    best_score = float("inf")
    best_step = 0
    best_path = checkpoint_path(run_dir, run_id, "best")
    last_path = checkpoint_path(run_dir, run_id, "last")
    started = time.perf_counter()
    for step in range(1, cfg.train_steps + 1):
        lr = lr_for_step(step, cfg.train_steps, cfg.learning_rate)
        for group in optimizer.param_groups:
            group["lr"] = lr
        selected = equal_group_batch_indices(group_rows, cfg.batch_size)
        clean = normalized.index_select(0, selected)
        model_input, target = corrupt_states(clean, mean, std, args.variant)
        if args.projector_architecture == "residual_denoising":
            candidate = model_input[:, DELTA]
            limit = float(model.correction_limit)
            target = candidate + limit * torch.tanh(
                (target - candidate) / limit
            )
        reconstructed = model(model_input)[:, DELTA]
        physical_loss = (reconstructed - target).square().mean()
        previous_raw = clean[:, PREVIOUS] * std[PREVIOUS] + mean[PREVIOUS]
        current_raw = clean[:, CURRENT] * std[CURRENT] + mean[CURRENT]
        hard_negative_input = clean.clone()
        hard_negative_input[:, DELTA] = (
            2.0 * (current_raw - previous_raw) - mean[DELTA]
        ) / std[DELTA]
        hard_negative_loss = (
            model(hard_negative_input)[:, DELTA] - clean[:, DELTA]
        ).square().mean()
        perfect_gt_reconstruction = model(clean)[:, DELTA]
        perfect_gt_batch_loss = (
            perfect_gt_reconstruction - clean[:, DELTA]
        ).square().mean()
        gate_loss = physical_loss.new_zeros(())
        if args.projector_architecture == "gated_calibrated":
            assert isinstance(model, GatedCalibratedDeltaProjector)
            gate_loss = (
                torch.nn.functional.binary_cross_entropy(
                    model.gate(clean), torch.ones_like(clean[:, DELTA])
                )
                + torch.nn.functional.binary_cross_entropy(
                    model.gate(model_input),
                    torch.zeros_like(model_input[:, DELTA]),
                )
                + torch.nn.functional.binary_cross_entropy(
                    model.gate(hard_negative_input),
                    torch.zeros_like(hard_negative_input[:, DELTA]),
                )
            )
        loss = (
            physical_loss
            + float(args.hard_negative_weight) * hard_negative_loss
            + float(args.clean_gt_weight) * perfect_gt_batch_loss
            + float(args.gate_loss_weight) * gate_loss
        )
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0)
        optimizer.step()
        if step == 1 or step % args.log_every == 0 or step == cfg.train_steps:
            clean_audit = audit_runner.rollout(model, mean, std, perturbed=False)
            perturb_audit = audit_runner.rollout(model, mean, std, perturbed=True)
            gradient = audit_runner.gradient_audit(model, mean, std)
            perfect_gt = perfect_gt_reconstruction_metrics(
                model, normalized, groups_device
            )
            clean_worst = float(clean_audit["strict_worst_frame_upper_joint_position_rmse_cm"])
            perturb_worst = float(perturb_audit["strict_worst_frame_upper_joint_position_rmse_cm"])
            # Clean K32 dominates selection; perturb recovery breaks ties and
            # prevents selecting a brittle clean-only model.
            legacy_selection_score = clean_worst + perturb_worst
            legacy_constraints_pass = bool(
                clean_audit["strict_below_1cm"]
                and perturb_audit["strict_below_1cm"]
                and gradient["all_gradients_point_toward_gt"]
                and gradient["all_gradient_steps_improve"]
                and perfect_gt["finite"]
            )
            perfect_gt_pass = bool(
                perfect_gt["equal_group_mean"] <= float(args.clean_gt_target)
            )
            selection_score = float(perfect_gt["equal_group_mean"]) + (
                0.0
                if legacy_constraints_pass
                else 1000.0 + legacy_selection_score
            )
            audit = {
                "clean": clean_audit,
                "perturbed": perturb_audit,
                "gradient": gradient,
                "perfect_gt": perfect_gt,
                "acceptance": {
                    "legacy_constraints_pass": legacy_constraints_pass,
                    "perfect_gt_target": float(args.clean_gt_target),
                    "perfect_gt_pass": perfect_gt_pass,
                    "all_passed": bool(legacy_constraints_pass and perfect_gt_pass),
                },
            }
            writer.add_scalar("loss/train_normalized", float(loss.item()), step)
            writer.add_scalar("loss/physical_recovery_normalized", float(physical_loss.item()), step)
            writer.add_scalar("loss/clean_context_constant_velocity_hard_negative", float(hard_negative_loss.item()), step)
            writer.add_scalar("loss/perfect_gt_batch_normalized", float(perfect_gt_batch_loss.item()), step)
            writer.add_scalar("loss/gate_supervision", float(gate_loss.item()), step)
            writer.add_scalar("audit/perfect_gt_equal_group_mean_normalized", float(perfect_gt["equal_group_mean"]), step)
            writer.add_scalar("audit/clean_strict_worst_cm", clean_worst, step)
            writer.add_scalar("audit/perturbed_strict_worst_cm", perturb_worst, step)
            writer.add_scalar("audit/gradient_positive_fraction", float(gradient["positive_cosine_fraction"]), step)
            writer.add_scalar("audit/selection_score", selection_score, step)
            writer.add_scalar("train/gradient_norm", float(grad_norm), step)
            writer.add_scalar("train/learning_rate", lr, step)
            payload = checkpoint_payload(
                model,
                optimizer,
                cfg,
                mean,
                std,
                metadata,
                step,
                best_score,
                audit,
                include_optimizer=not bool(args.lightweight_checkpoints),
            )
            atomic_save(payload, last_path)
            if selection_score < best_score:
                best_score = selection_score
                best_step = step
                payload["best"] = best_score
                payload["metadata"]["selection"] = {
                    "metric": "perfect_GT_normalized_MSE among checkpoints passing the unchanged K32 and 5cm2deg gradient constraints",
                    "score": best_score,
                    "step": best_step,
                }
                atomic_save(payload, best_path)
            print(
                "ROOT_AE_STEP "
                f"variant={args.variant} step={step}/{cfg.train_steps} loss={loss.item():.8f} "
                f"physical={physical_loss.item():.8f} perfect_gt={perfect_gt['equal_group_mean']:.8f} "
                f"clean_worst_cm={clean_worst:.4f} perturb_worst_cm={perturb_worst:.4f} "
                f"grad_positive={gradient['positive_cosine_fraction']:.4f} best={best_score:.4f} "
                f"elapsed_s={time.perf_counter()-started:.1f}",
                flush=True,
            )
    writer.close()
    summary = {
        "run_id": run_id,
        "variant": args.variant,
        "best_step": best_step,
        "best_score": best_score,
        "best_checkpoint": str(best_path),
        "last_checkpoint": str(last_path),
        "elapsed_seconds": time.perf_counter() - started,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    return best_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=VARIANTS, required=True)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--train-steps", type=int, default=12000)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--hidden-dim", type=int, default=1024)
    parser.add_argument("--hidden-layers", type=int, default=3)
    parser.add_argument("--learning-rate", type=float, default=1.0e-3)
    parser.add_argument("--std-floor", type=float, default=1.0e-4)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--log-every", type=int, default=500)
    parser.add_argument("--minimum-cuda-free-mib", type=float, default=1200.0)
    parser.add_argument("--rebuild-cache", action="store_true")
    parser.add_argument("--init-checkpoint", type=Path)
    parser.add_argument("--clean-gt-weight", type=float, default=0.0)
    parser.add_argument("--clean-gt-target", type=float, default=1.0e-4)
    parser.add_argument(
        "--projector-architecture",
        choices=(
            "condition_only",
            "residual_denoising",
            "calibrated_condition",
            "gated_calibrated",
        ),
        default="condition_only",
    )
    parser.add_argument("--gate-loss-weight", type=float, default=0.0)
    parser.add_argument("--hard-negative-weight", type=float, default=0.0)
    parser.add_argument(
        "--lightweight-checkpoints",
        action="store_true",
        help=(
            "Store inference/model checkpoints without AdamW moments. This does not "
            "change training, but those checkpoints cannot resume optimizer state."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    train(parse_args())
