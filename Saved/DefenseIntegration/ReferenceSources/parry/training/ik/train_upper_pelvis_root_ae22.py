from __future__ import annotations

"""Train the slash-AE22 mechanism in the current 19-bone root-relative space.

The public row starts with a proposed physical transition, but the network is
condition-only and never sees that proposal.  It predicts the correct next
transition from previous/current physical poses and locomotion controls.  This
is the important AE22 property: the public MSE score pulls any proposal toward
the teacher prediction instead of letting an autoencoder copy its candidate.
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

try:
    from .bootstrap import PROJECT_ROOT, ensure_paths
    from .naming import checkpoint_path, ik_run_id
    from .train_simple_autoencoder import SimpleAEConfig, equal_group_batch_indices, lr_for_step
    from . import ik_core as tl
    from . import train_upper_pose_root_simple_ae1 as source
    from . import upper_pose_pelvis_contract as physical
except ImportError:
    from bootstrap import PROJECT_ROOT, ensure_paths
    from naming import checkpoint_path, ik_run_id
    from train_simple_autoencoder import SimpleAEConfig, equal_group_batch_indices, lr_for_step
    import ik_core as tl
    import train_upper_pose_root_simple_ae1 as source
    import upper_pose_pelvis_contract as physical

from training.slashes2.conditional_delta_projector import ConditionalDeltaProjector


ensure_paths()
RUNS_ROOT = PROJECT_ROOT / "training" / "runs"
MOTION_DIM = physical.PHYSICAL_DIM
CONTROL_SOURCE_START = source.upper_data.POSE_DIM * 2
CONTROL_DIM = source.INPUT_DIM - CONTROL_SOURCE_START
DELTA = slice(0, MOTION_DIM)
PREVIOUS = slice(MOTION_DIM, MOTION_DIM * 2)
CURRENT = slice(MOTION_DIM * 2, MOTION_DIM * 3)
CONTROLS = slice(MOTION_DIM * 3, MOTION_DIM * 3 + CONTROL_DIM)
FEATURE_DIM = CONTROLS.stop
GROUP_COUNT = source.GROUP_COUNT
GROUP_NAMES = source.GROUP_NAMES
POSITION_PERTURB_M = 0.05
ROTATION_PERTURB_DEG = 2.0
STATE_NOISE_MAX = 0.05


def equal_group_normalization(
    values: torch.Tensor, groups: torch.Tensor, std_floor: float
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


@torch.no_grad()
def build_rows(
    raw_windows: torch.Tensor,
    support: dict[str, torch.Tensor],
    selected: torch.Tensor,
    prototype: tl.MotionClip,
    lower_prototype: tl.MotionClip,
    gaze: torch.Tensor,
) -> torch.Tensor:
    """Build AE22 rows at t+1, expressing t/t+1/t+2 in the t+1 root."""

    count = int(selected.numel())
    if tuple(gaze.shape) != (count, 2):
        raise ValueError(f"Expected gaze [{count},2], got {tuple(gaze.shape)}")

    upper_positions = support["upper_positions"].index_select(0, selected)
    upper_rotations = support["upper_rotations"].index_select(0, selected)
    repeated_gaze = gaze[:, None, :].expand(count, 4, 2).reshape(count * 4, 2)
    overlaid_positions, overlaid_rotations = source.upper_data.apply_gaze_overlay_global_pose(
        prototype,
        upper_positions.reshape(count * 4, prototype.J, 3),
        upper_rotations.reshape(count * 4, prototype.J, 3, 3),
        repeated_gaze,
    )
    upper_states = source.upper_data.upper_state_from_global_pose_and_heading(
        prototype,
        overlaid_positions,
        overlaid_rotations,
        support["upper_root_positions"].index_select(0, selected).reshape(count * 4, 3),
        support["upper_root_headings"].index_select(0, selected).reshape(count * 4, 3, 3),
    ).reshape(count, 4, source.upper_data.POSE_DIM)

    lower_vectors = support["lower_vectors"].index_select(0, selected).reshape(count * 3, -1)
    pelvis_heading = support["pelvis_heading"].index_select(0, selected).reshape(
        count * 3, source.upper_data.PELVIS_DIM
    )
    root_positions = support["physical_root_positions"].index_select(0, selected)
    root_rotations = support["physical_root_rotations"].index_select(0, selected)
    root_headings = support["physical_root_headings"].index_select(0, selected)
    positions, rotations = physical.decode_full_pose(
        prototype,
        lower_prototype,
        lower_vectors,
        upper_states[:, 1:4].reshape(count * 3, source.upper_data.POSE_DIM),
        pelvis_heading,
        root_positions.reshape(count * 3, 3),
        root_rotations.reshape(count * 3, 3, 3),
        root_headings.reshape(count * 3, 3, 3),
    )
    positions = positions.reshape(count, 3, prototype.J, 3)
    rotations = rotations.reshape(count, 3, prototype.J, 3, 3)

    own: list[torch.Tensor] = []
    for slot in range(3):
        own.append(
            physical.physical_pose_from_globals(
                prototype,
                positions[:, slot],
                rotations[:, slot],
                root_positions[:, slot],
                root_rotations[:, slot],
            )
        )
    previous = physical.reframe_physical_pose(
        own[0],
        root_positions[:, 0],
        root_rotations[:, 0],
        root_positions[:, 1],
        root_rotations[:, 1],
    )
    current = own[1]
    following = physical.reframe_physical_pose(
        own[2],
        root_positions[:, 2],
        root_rotations[:, 2],
        root_positions[:, 1],
        root_rotations[:, 1],
    )

    base = raw_windows.index_select(0, selected)
    control_start = source.ROW_DIM + CONTROL_SOURCE_START
    controls = base[:, control_start : control_start + CONTROL_DIM].clone()
    controls[:, -source.upper_data.GAZE_DIM :] = gaze
    rows = torch.cat((following - current, previous, current, controls), dim=-1)
    if tuple(rows.shape) != (count, FEATURE_DIM):
        raise RuntimeError(f"AE22 row mismatch: {tuple(rows.shape)}")
    if not bool(torch.isfinite(rows).all()):
        raise RuntimeError("Non-finite AE22 rows")
    return rows.contiguous()


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
    joint_count = len(physical.PHYSICAL_BONES)
    shaped = pose.reshape(count, joint_count, physical.TRANSFORM_DIM).clone()
    directions = torch.randn((count, joint_count, 3), device=pose.device)
    directions = directions / directions.norm(dim=-1, keepdim=True).clamp_min(1.0e-8)
    radius = torch.rand((count, joint_count, 1), device=pose.device) * position_max_m
    shaped[..., :3] += directions * radius
    rotations = tl.rotation_6d_to_matrix(shaped[..., 3:9].reshape(-1, 6)).reshape(
        count, joint_count, 3, 3
    )
    correction = random_axis_angle_correction(
        count, joint_count, rotation_max_deg, pose.device
    )
    shaped[..., 3:9] = tl.rotmat_to_6d(rotations @ correction)
    return physical.clean_physical_pose(shaped.reshape(count, MOTION_DIM))


def corrupt_states(
    normalized: torch.Tensor,
    mean: torch.Tensor,
    std: torch.Tensor,
    full_perturbation: bool = False,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Use the original slash-AE22 normalized state-corruption recipe."""

    model_input = normalized.clone()
    clean_delta = normalized[:, DELTA] * std[DELTA] + mean[DELTA]
    count = int(normalized.shape[0])
    state_scale = (
        torch.full((count, 1), STATE_NOISE_MAX, device=normalized.device)
        if full_perturbation
        else torch.rand((count, 1), device=normalized.device) * STATE_NOISE_MAX
    )
    previous_noise = torch.randn_like(normalized[:, PREVIOUS]) * state_scale
    current_noise = torch.randn_like(normalized[:, CURRENT]) * state_scale
    model_input[:, PREVIOUS] += previous_noise
    model_input[:, CURRENT] += current_noise
    current_perturb_raw = current_noise * std[CURRENT]
    corrected_delta = clean_delta - current_perturb_raw
    target = (corrected_delta - mean[DELTA]) / std[DELTA]

    previous = model_input[:, PREVIOUS] * std[PREVIOUS] + mean[PREVIOUS]
    current = model_input[:, CURRENT] * std[CURRENT] + mean[CURRENT]
    modes = torch.randint(0, 5, (count,), device=normalized.device)
    constant_velocity = (current - previous - mean[DELTA]) / std[DELTA]
    zero = (torch.zeros_like(clean_delta) - mean[DELTA]) / std[DELTA]
    shuffled = normalized[
        torch.randperm(count, device=normalized.device), DELTA
    ]
    candidates = torch.where(
        (modes == 0)[:, None],
        target + 0.10 * torch.randn_like(target),
        torch.where(
            (modes == 1)[:, None],
            constant_velocity,
            torch.where(
                (modes == 2)[:, None],
                zero,
                torch.where((modes == 3)[:, None], shuffled, torch.randn_like(target)),
            ),
        ),
    )
    model_input[:, DELTA] = candidates
    return model_input, target, current


def corrupt_states_physical(
    normalized: torch.Tensor,
    mean: torch.Tensor,
    std: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Build the separate 5 cm/2 degree physical recovery audit case."""

    model_input = normalized.clone()
    clean_delta = normalized[:, DELTA] * std[DELTA] + mean[DELTA]
    previous = normalized[:, PREVIOUS] * std[PREVIOUS] + mean[PREVIOUS]
    clean_current = normalized[:, CURRENT] * std[CURRENT] + mean[CURRENT]
    count = int(normalized.shape[0])
    position_max = torch.full(
        (count, 1, 1), POSITION_PERTURB_M, device=normalized.device
    )
    rotation_max = torch.full(
        (count, 1), ROTATION_PERTURB_DEG, device=normalized.device
    )
    previous = physical_perturb(previous, position_max, rotation_max)
    current = physical_perturb(clean_current, position_max, rotation_max)
    corrected_delta = clean_delta - (current - clean_current)
    model_input[:, PREVIOUS] = (previous - mean[PREVIOUS]) / std[PREVIOUS]
    model_input[:, CURRENT] = (current - mean[CURRENT]) / std[CURRENT]
    target = (corrected_delta - mean[DELTA]) / std[DELTA]
    return model_input, target, current


def physical_error_summary(
    predicted_next: torch.Tensor, target_next: torch.Tensor
) -> dict[str, Any]:
    predicted_next = physical.clean_physical_pose(predicted_next)
    target_next = physical.clean_physical_pose(target_next)
    joint_count = len(physical.PHYSICAL_BONES)
    predicted = predicted_next.reshape(-1, joint_count, physical.TRANSFORM_DIM)
    target = target_next.reshape_as(predicted)
    position_cm = torch.linalg.vector_norm(predicted[..., :3] - target[..., :3], dim=-1) * 100.0
    predicted_rotation = tl.rotation_6d_to_matrix(predicted[..., 3:9].reshape(-1, 6))
    target_rotation = tl.rotation_6d_to_matrix(target[..., 3:9].reshape(-1, 6))
    relative = predicted_rotation @ target_rotation.transpose(-1, -2)
    cosine = ((torch.diagonal(relative, dim1=-2, dim2=-1).sum(dim=-1) - 1.0) * 0.5).clamp(-1.0, 1.0)
    rotation_deg = torch.rad2deg(torch.acos(cosine)).reshape_as(position_cm)
    position_flat = position_cm.reshape(-1)
    rotation_flat = rotation_deg.reshape(-1)
    position_index = int(position_flat.argmax())
    rotation_index = int(rotation_flat.argmax())
    return {
        "mean_joint_position_error_cm": float(position_cm.mean()),
        "strict_max_joint_position_error_cm": float(position_flat[position_index]),
        "worst_position_bone": physical.PHYSICAL_BONES[position_index % joint_count],
        "mean_joint_rotation_error_deg": float(rotation_deg.mean()),
        "strict_max_joint_rotation_error_deg": float(rotation_flat[rotation_index]),
        "worst_rotation_bone": physical.PHYSICAL_BONES[rotation_index % joint_count],
        "all_joints_below_1cm": bool(float(position_flat[position_index]) < 1.0),
    }


@torch.no_grad()
def evaluate_case(
    model: torch.nn.Module,
    model_input: torch.Tensor,
    target: torch.Tensor,
    current_raw: torch.Tensor,
    groups: torch.Tensor,
    mean: torch.Tensor,
    std: torch.Tensor,
    batch_size: int = 2048,
) -> dict[str, Any]:
    model.eval()
    predictions: list[torch.Tensor] = []
    for start in range(0, int(model_input.shape[0]), int(batch_size)):
        predictions.append(model(model_input[start : start + batch_size])[:, DELTA])
    prediction = torch.cat(predictions)
    row_mse = (prediction - target).square().mean(dim=-1)
    group_mse: dict[str, float] = {}
    for group, name in enumerate(GROUP_NAMES):
        mask = groups == group
        group_mse[name] = float(row_mse[mask].mean())
    prediction_raw = prediction * std[DELTA] + mean[DELTA]
    target_raw = target * std[DELTA] + mean[DELTA]
    result = physical_error_summary(current_raw + prediction_raw, current_raw + target_raw)
    result.update(
        {
            "equal_group_normalized_mse": sum(group_mse.values()) / GROUP_COUNT,
            "group_normalized_mse": group_mse,
            "raw_transition_mse": float((prediction_raw - target_raw).square().mean()),
            "finite": bool(torch.isfinite(prediction).all()),
        }
    )
    return result


@torch.no_grad()
def evaluate(
    model: torch.nn.Module,
    clean_normalized: torch.Tensor,
    perturbed_input: torch.Tensor,
    perturbed_target: torch.Tensor,
    perturbed_current: torch.Tensor,
    groups: torch.Tensor,
    mean: torch.Tensor,
    std: torch.Tensor,
) -> dict[str, Any]:
    clean_target = clean_normalized[:, DELTA]
    clean_current = clean_normalized[:, CURRENT] * std[CURRENT] + mean[CURRENT]
    clean = evaluate_case(
        model, clean_normalized, clean_target, clean_current, groups, mean, std
    )
    perturbed = evaluate_case(
        model, perturbed_input, perturbed_target, perturbed_current, groups, mean, std
    )

    # The negative candidate-gradient of the public AE22 score points from the
    # candidate to the teacher.  Compare that direction to candidate -> exact GT.
    teacher = model(perturbed_input)[:, DELTA]
    candidate = perturbed_input[:, DELTA]
    teacher_direction = teacher - candidate
    gt_direction = perturbed_target - candidate
    cosine = torch.nn.functional.cosine_similarity(teacher_direction, gt_direction, dim=-1)
    audit = {
        "clean": clean,
        "perturbed_5cm_2deg": perturbed,
        "gradient_to_gt_cosine_mean": float(cosine.mean()),
        "gradient_to_gt_cosine_min": float(cosine.min()),
        "gradient_to_gt_positive_fraction": float((cosine > 0.0).float().mean()),
        "finite": bool(clean["finite"] and perturbed["finite"] and torch.isfinite(cosine).all()),
    }
    audit["accepted"] = bool(
        audit["finite"]
        and clean["all_joints_below_1cm"]
        and perturbed["all_joints_below_1cm"]
        and audit["gradient_to_gt_positive_fraction"] == 1.0
    )
    model.train()
    return audit


def checkpoint_schema() -> dict[str, Any]:
    return {
        "name": "upper_pelvis_root_ae22_condition_only_v1",
        "total_dim": FEATURE_DIM,
        "candidate_physical_transition": [DELTA.start, DELTA.stop],
        "previous_physical_pose": [PREVIOUS.start, PREVIOUS.stop],
        "current_physical_pose": [CURRENT.start, CURRENT.stop],
        "controls": [CONTROLS.start, CONTROLS.stop],
        "controls_source": "current controller input excluding both 90D upper-pose blocks",
        "pose_bones": list(physical.PHYSICAL_BONES),
        "per_bone": "position3_rotation6_relative_to_current_actual_root",
        "candidate_visible_to_network": False,
        "controller_agent_representation_changed": False,
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
    rng_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "kind": "upper_pelvis_root_ae22_condition_only",
        "model": model.state_dict(),
        "optimizer": optimizer.state_dict(),
        "config": asdict(cfg),
        "projector": {
            "architecture": "condition_only",
            "input_dim": FEATURE_DIM,
            "motion_dim": MOTION_DIM,
            "hidden_dim": cfg.hidden_dim,
            "num_hidden_layers": cfg.num_hidden_layers,
        },
        "schema": checkpoint_schema(),
        "mean": mean.detach().cpu(),
        "std": std.detach().cpu(),
        "metadata": metadata,
        "step": int(step),
        "best": float(best),
        "audit": audit,
    }
    if rng_state is not None:
        payload["rng_state"] = rng_state
    return payload


def capture_rng_state(generator: torch.Generator, device: torch.device) -> dict[str, Any]:
    state: dict[str, Any] = {
        "torch_cpu": torch.get_rng_state().cpu(),
        "gaze_generator": generator.get_state().cpu(),
    }
    if device.type == "cuda":
        state["torch_cuda"] = torch.cuda.get_rng_state(device).cpu()
    return state


def restore_rng_state(
    state: dict[str, Any], generator: torch.Generator, device: torch.device
) -> None:
    torch.set_rng_state(state["torch_cpu"].cpu())
    generator.set_state(state["gaze_generator"].cpu())
    if device.type == "cuda":
        torch.cuda.set_rng_state(state["torch_cuda"].cpu(), device)


@torch.no_grad()
def reconstruct_legacy_rng_position(
    completed_steps: int,
    generator: torch.Generator,
    group_rows: list[torch.Tensor],
    clean_normalized: torch.Tensor,
    mean: torch.Tensor,
    std: torch.Tensor,
    batch_size: int,
) -> None:
    """Reproduce the pre-RNG-checkpoint draw sequence without any model update."""

    for _ in range(int(completed_steps)):
        selected = equal_group_batch_indices(group_rows, int(batch_size))
        source.sample_rollout_gaze(int(selected.numel()), generator)
        dummy = clean_normalized.index_select(0, selected)
        corrupt_states(dummy, mean, std)


def atomic_save(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(payload, temporary)
    os.replace(temporary, path)


def initialize_fresh_run_checkpoint(
    path: Path,
    model: torch.nn.Module,
    optimizer: torch.optim.Optimizer,
    cfg: SimpleAEConfig,
    mean: torch.Tensor,
    std: torch.Tensor,
    metadata: dict[str, Any],
    audit: dict[str, Any],
) -> None:
    """Mandatory step-zero snapshot; training may not begin without it."""

    if path.exists():
        raise FileExistsError(f"Fresh-run init checkpoint already exists: {path}")
    atomic_save(
        checkpoint_payload(
            model,
            optimizer,
            cfg,
            mean,
            std,
            metadata,
            0,
            math.inf,
            audit,
        ),
        path,
    )
    if not path.is_file() or path.stat().st_size <= 0:
        raise RuntimeError(f"Mandatory init checkpoint was not written: {path}")
    verification = torch.load(path, map_location="cpu", weights_only=False)
    if (
        verification.get("kind") != "upper_pelvis_root_ae22_condition_only"
        or int(verification.get("step", -1)) != 0
        or "model" not in verification
        or "optimizer" not in verification
    ):
        raise RuntimeError(f"Mandatory init checkpoint failed verification: {path}")


@torch.no_grad()
def build_full_corpus(
    windows: torch.Tensor,
    support: dict[str, torch.Tensor],
    prototype: tl.MotionClip,
    lower_prototype: tl.MotionClip,
    device: torch.device,
    seed: int,
) -> torch.Tensor:
    generator = torch.Generator(device="cpu").manual_seed(int(seed))
    chunks: list[torch.Tensor] = []
    for start in range(0, int(windows.shape[0]), 512):
        selected = torch.arange(start, min(start + 512, int(windows.shape[0])), device=device)
        gaze = source.sample_rollout_gaze(int(selected.numel()), generator).to(device)
        chunks.append(build_rows(windows, support, selected, prototype, lower_prototype, gaze))
    return torch.cat(chunks)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def train(args: argparse.Namespace) -> Path:
    torch.manual_seed(int(args.seed))
    windows, groups, dataset_metadata, dataset_cache = source.prepare_windows(False)
    support, support_cache, prototype_source = source.prepare_dynamic_support(False)
    cfg_motion = source.upper_data.motion_config()
    prototype = source.tl.MotionClip(prototype_source, cfg_motion, cyclic_animation=True)
    lower_cfg = source.upper_data.motion_config()
    lower_cfg.body_mode = source.tl.BODY_MODE_LOWER
    lower_prototype = source.tl.MotionClip(prototype_source, lower_cfg, cyclic_animation=True)

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable")
    if device.type == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        torch.set_float32_matmul_precision("high")
    windows = windows.to(device)
    support = {key: value.to(device) for key, value in support.items()}
    groups_device = groups.to(device)
    group_rows = [torch.where(groups_device == group)[0] for group in range(GROUP_COUNT)]

    full_corpus = build_full_corpus(
        windows, support, prototype, lower_prototype, device, int(args.seed) + 99173
    )
    mean_cpu, std_cpu = equal_group_normalization(full_corpus.cpu(), groups, float(args.std_floor))
    mean = mean_cpu.to(device)
    std = std_cpu.to(device)
    clean_normalized = (full_corpus - mean) / std

    cfg = SimpleAEConfig(
        latent_dim=MOTION_DIM,
        hidden_dim=int(args.hidden_dim),
        num_hidden_layers=3,
        batch_size=int(args.batch_size),
        train_steps=int(args.train_steps),
        learning_rate=float(args.learning_rate),
        weight_decay=1.0e-5,
        std_floor=float(args.std_floor),
        val_fraction=0.0,
        seed=int(args.seed),
        pose_representation="nineteen_physical_transforms_in_current_actual_root",
        body_mode="upper_plus_pelvis_and_leg_ik",
        feature="AE22_condition_only_physical_transition",
        ae_feature_mode="state_conditioned_delta",
        ae_score_scope="physical_transition_only",
        window_frames=1,
        denoise_noise_std=0.0,
    )
    model = ConditionalDeltaProjector(
        FEATURE_DIM, MOTION_DIM, cfg.hidden_dim, cfg.num_hidden_layers
    ).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=cfg.learning_rate, weight_decay=cfg.weight_decay
    )

    torch.manual_seed(int(args.seed) + 771)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(int(args.seed) + 771)
    perturbed_input, perturbed_target, perturbed_current = corrupt_states_physical(
        clean_normalized, mean, std
    )
    torch.manual_seed(int(args.seed) + 17)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(int(args.seed) + 17)

    resume_checkpoint: dict[str, Any] | None = None
    if args.resume_checkpoint:
        resume_path = Path(args.resume_checkpoint).resolve()
        resume_checkpoint = torch.load(resume_path, map_location="cpu", weights_only=False)
        if resume_checkpoint.get("kind") != "upper_pelvis_root_ae22_condition_only":
            raise RuntimeError(f"Not a resumable AE22 checkpoint: {resume_path}")
        run_dir = Path(args.resume_run_dir).resolve()
        if run_dir.parent != RUNS_ROOT.resolve():
            raise ValueError(f"Resume run must be directly under {RUNS_ROOT}: {run_dir}")
        run_id = run_dir.name
        if not run_dir.is_dir() or resume_path.parent != run_dir / "checkpoints":
            raise ValueError("Resume checkpoint must belong to the requested original run")
        if not torch.allclose(resume_checkpoint["mean"].float(), mean_cpu, atol=1e-7, rtol=1e-6):
            raise RuntimeError("Resume mean does not match unchanged AE22 data")
        if not torch.allclose(resume_checkpoint["std"].float(), std_cpu, atol=1e-7, rtol=1e-6):
            raise RuntimeError("Resume std does not match unchanged AE22 data")
        model.load_state_dict(resume_checkpoint["model"], strict=True)
        optimizer.load_state_dict(resume_checkpoint["optimizer"])
    else:
        run_id = ik_run_id(
            f"ae22_rootphysical_conditiononly_h{cfg.hidden_dim}_l3_bs{cfg.batch_size}_{cfg.train_steps}step"
        )
        run_dir = RUNS_ROOT / run_id
        (run_dir / "checkpoints").mkdir(parents=True, exist_ok=False)
    writer = SummaryWriter(log_dir=str(run_dir / "tb"), flush_secs=1)
    metadata = {
        "dataset": dataset_metadata,
        "dataset_cache": str(dataset_cache),
        "dynamic_gaze_support_cache": str(support_cache),
        "training_contract": {
            "mechanism": "slash_AE22_condition_only_teacher",
            "candidate_visible_to_network": False,
            "groups": list(GROUP_NAMES),
            "batch_sampling": "exact_equal_four_groups",
            "state_condition": "previous/current 19-bone physical poses in current root",
            "controls": "pelvis previous/current/next, future root window, sword, feet current/next, gaze",
            "target": "next physical pose minus current physical pose in current root",
            "state_perturbation": "original AE22 normalized Gaussian state noise up to 0.05",
            "physical_recovery_audit": "separate exact 5cm and 2deg case; not the training distribution",
            "proposal_modes_equal_probability": [
                "noisy_correct",
                "constant_velocity",
                "zero",
                "shuffled",
                "random",
            ],
            "gaze_sampling": "fresh uniform per row with 5 percent exact zero-zero",
            "agent_representation_changed": False,
        },
    }
    if resume_checkpoint is None:
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

    generator = torch.Generator(device="cpu").manual_seed(cfg.seed)
    best = math.inf
    best_step = 0
    init_path = checkpoint_path(run_dir, run_id, "init")
    best_path = checkpoint_path(run_dir, run_id, "best")
    last_path = checkpoint_path(run_dir, run_id, "last")
    if resume_checkpoint is None:
        initial_audit = evaluate(
            model,
            clean_normalized,
            perturbed_input,
            perturbed_target,
            perturbed_current,
            groups_device,
            mean,
            std,
        )
        initialize_fresh_run_checkpoint(
            init_path,
            model,
            optimizer,
            cfg,
            mean,
            std,
            metadata,
            initial_audit,
        )
        print(f"AE22_INIT checkpoint={init_path}", flush=True)
        start_step = 0
    else:
        start_step = int(resume_checkpoint.get("step", -1))
        if start_step < 0 or start_step >= cfg.train_steps:
            raise ValueError(f"Invalid resume step {start_step}")
        best_file = torch.load(best_path, map_location="cpu", weights_only=False)
        best = float(best_file.get("best", math.inf))
        best_step = int(dict(best_file.get("metadata", {})).get("selection", {}).get("step", start_step))
        saved_rng = resume_checkpoint.get("rng_state")
        if saved_rng is not None:
            restore_rng_state(dict(saved_rng), generator, device)
            rng_source = "checkpoint"
        else:
            reconstruct_legacy_rng_position(
                start_step,
                generator,
                group_rows,
                clean_normalized,
                mean,
                std,
                cfg.batch_size,
            )
            rng_source = "deterministic_reconstruction"
        print(
            f"AE22_RESUME run={run_id} step={start_step} best={best:.7g}@{best_step} "
            f"optimizer=restored rng={rng_source}",
            flush=True,
        )
    started = time.perf_counter()
    for step in range(start_step + 1, cfg.train_steps + 1):
        lr = lr_for_step(step, cfg.train_steps, cfg.learning_rate)
        for group in optimizer.param_groups:
            group["lr"] = lr
        selected = equal_group_batch_indices(group_rows, cfg.batch_size)
        gaze = source.sample_rollout_gaze(int(selected.numel()), generator).to(device)
        raw = build_rows(windows, support, selected, prototype, lower_prototype, gaze)
        normalized = (raw - mean) / std
        model_input, target, _current = corrupt_states(normalized, mean, std)
        prediction = model(model_input)[:, DELTA]
        loss = (prediction - target).square().mean()
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        # Original slash AE22 does not clip; use this only to measure the norm.
        grad = torch.nn.utils.clip_grad_norm_(model.parameters(), float("inf"))
        optimizer.step()

        if step == 1 or step % int(args.log_every) == 0 or step == cfg.train_steps:
            audit = evaluate(
                model,
                clean_normalized,
                perturbed_input,
                perturbed_target,
                perturbed_current,
                groups_device,
                mean,
                std,
            )
            # Preserve original AE22 checkpoint selection. Physical recovery is
            # a separate acceptance audit, not a replacement training metric.
            selection = float(audit["clean"]["equal_group_normalized_mse"])
            writer.add_scalar("loss/ae22", float(loss.detach()), step)
            writer.add_scalar("metric/clean_normalized_mse", float(audit["clean"]["equal_group_normalized_mse"]), step)
            writer.add_scalar("metric/perturbed_normalized_mse", float(audit["perturbed_5cm_2deg"]["equal_group_normalized_mse"]), step)
            writer.add_scalar("metric/clean_max_joint_cm", float(audit["clean"]["strict_max_joint_position_error_cm"]), step)
            writer.add_scalar("metric/perturbed_max_joint_cm", float(audit["perturbed_5cm_2deg"]["strict_max_joint_position_error_cm"]), step)
            writer.add_scalar("metric/gradient_to_gt_cosine", float(audit["gradient_to_gt_cosine_mean"]), step)
            writer.add_scalar("train/gradient_norm", float(grad), step)
            writer.add_scalar("train/learning_rate", lr, step)
            writer.flush()
            payload = checkpoint_payload(
                model,
                optimizer,
                cfg,
                mean,
                std,
                metadata,
                step,
                best,
                audit,
                capture_rng_state(generator, device),
            )
            atomic_save(payload, last_path)
            if selection < best:
                best = selection
                best_step = step
                payload["best"] = best
                payload["metadata"]["selection"] = {"score": best, "step": best_step}
                atomic_save(payload, best_path)
            print(
                f"AE22 step={step}/{cfg.train_steps} train={float(loss.detach()):.7g} "
                f"clean={audit['clean']['equal_group_normalized_mse']:.7g} "
                f"pert={audit['perturbed_5cm_2deg']['equal_group_normalized_mse']:.7g} "
                f"clean_max_cm={audit['clean']['strict_max_joint_position_error_cm']:.4f} "
                f"pert_max_cm={audit['perturbed_5cm_2deg']['strict_max_joint_position_error_cm']:.4f} "
                f"grad_cos={audit['gradient_to_gt_cosine_mean']:.5f} "
                f"grad={float(grad):.5g} best={best:.7g}@{best_step} "
                f"elapsed_s={time.perf_counter()-started:.1f}",
                flush=True,
            )
    writer.close()
    summary = {
        "run_id": run_id,
        "init_checkpoint": str(init_path) if init_path.is_file() else None,
        "init_sha256": sha256_file(init_path) if init_path.is_file() else None,
        "best_checkpoint": str(best_path),
        "best_sha256": sha256_file(best_path),
        "last_checkpoint": str(last_path),
        "last_sha256": sha256_file(last_path),
        "best_step": best_step,
        "best_score": best,
        "best_audit": torch.load(best_path, map_location="cpu", weights_only=False)["audit"],
        "last_audit": torch.load(last_path, map_location="cpu", weights_only=False)["audit"],
        "elapsed_seconds": time.perf_counter() - started,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    return best_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--train-steps", type=int, default=12000)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--hidden-dim", type=int, default=1024)
    parser.add_argument("--learning-rate", type=float, default=1.0e-3)
    parser.add_argument("--std-floor", type=float, default=1.0e-4)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--log-every", type=int, default=250)
    parser.add_argument("--gaze-cache-draws", type=int, default=4)
    parser.add_argument("--resume-checkpoint")
    parser.add_argument("--resume-run-dir")
    parsed = parser.parse_args()
    if bool(parsed.resume_checkpoint) != bool(parsed.resume_run_dir):
        parser.error("--resume-checkpoint and --resume-run-dir must be supplied together")
    train(parsed)


if __name__ == "__main__":
    main()
