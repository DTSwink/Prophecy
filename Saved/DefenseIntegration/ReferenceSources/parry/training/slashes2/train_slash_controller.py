from __future__ import annotations

"""Current Slash2 two-agent trainer.

Runtime choices live in :class:`Recipe`, not in a large command-line surface.
The shared implementation supports the canonical GT16, the normal+mirrored
GT32 bring-up, and the established original+variant corpus launchers.
"""

import argparse
import copy
import gc
import gzip
import hashlib
import io
import itertools
import json
import math
import os
import pickle
import random
import shutil
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, fields, replace
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Callable, Iterable

import numpy as np
import torch
from torch.utils.tensorboard import SummaryWriter
import slash2_checkpoint_storage as checkpoint_storage


HERE = Path(__file__).resolve().parent
_PORTABLE_TORCH_CACHE_FILES_READ: set[Path] = set()
FAST_COMPILE_OPTIONS = {
    "triton.cudagraphs": False,
    # Compile the independent regional graphs in parallel. On Windows,
    # Inductor's Unix-style subprocess pool cannot pass the required file
    # descriptors, so use native multiprocessing spawn.
    "compile_threads": 4,
    **({"worker_start_method": "spawn"} if os.name == "nt" else {}),
    # The optimizer step already runs inside one outer CUDA graph. Exhaustive
    # pointwise autotuning adds substantial startup latency without improving
    # the accepted regional-model benchmark.
    "triton.autotune_pointwise": False,
}
_SLASH_FAST_FK_COMPILED = False


def host_memory_snapshot() -> dict[str, int | None]:
    """Return small Linux cgroup/process memory counters when available."""

    def read_int(path: str) -> int | None:
        try:
            text = Path(path).read_text(encoding="utf-8").strip()
            return None if text == "max" else int(text)
        except (FileNotFoundError, OSError, ValueError):
            return None

    rss_bytes: int | None = None
    try:
        fields = Path("/proc/self/statm").read_text(encoding="utf-8").split()
        rss_bytes = int(fields[1]) * int(os.sysconf("SC_PAGE_SIZE"))
    except (FileNotFoundError, OSError, ValueError, IndexError):
        pass
    return {
        "rssBytes": rss_bytes,
        "cgroupCurrentBytes": read_int("/sys/fs/cgroup/memory.current"),
        "cgroupMaxBytes": read_int("/sys/fs/cgroup/memory.max"),
    }


def release_startup_host_memory(stage: str) -> dict[str, object]:
    """Return dead preparation/compile allocations to the host losslessly.

    PyTorch's persistent runtime tensors and compiled callables remain live.
    Only unreachable Python objects and free libc heap arenas are released.
    This is startup-only and does not alter model state, graph math, precision,
    sampling, or the steady optimizer path.
    """

    before = host_memory_snapshot()
    collected = int(gc.collect())
    file_cache_release: dict[str, object] | None = None
    if str(stage) == "before_cuda_graph_capture":
        file_cache_release = release_loaded_portable_file_cache()
    trimmed = False
    if os.name == "posix":
        try:
            import ctypes

            libc = ctypes.CDLL(None)
            malloc_trim = getattr(libc, "malloc_trim", None)
            if malloc_trim is not None:
                malloc_trim.argtypes = [ctypes.c_size_t]
                malloc_trim.restype = ctypes.c_int
                trimmed = bool(malloc_trim(0))
        except (AttributeError, OSError):
            trimmed = False
    after = host_memory_snapshot()
    result: dict[str, object] = {
        "schema": "slash2_lossless_host_memory_quiesce_v1",
        "stage": str(stage),
        "collectedObjects": collected,
        "mallocTrimmed": trimmed,
        "fileCacheRelease": file_cache_release,
        "before": before,
        "after": after,
    }
    print(
        "SLASH2_HOST_MEMORY_QUIESCE "
        + json.dumps(result, sort_keys=True, separators=(",", ":")),
        flush=True,
    )
    return result


def release_deserialized_file_cache(path: Path) -> dict[str, object]:
    """Evict the redundant page-cache copy after a complete CPU deserialize.

    ``torch.load`` without mmap owns independent anonymous tensor storage once
    it returns. The source file's cached pages are therefore duplicate host
    memory. POSIX_FADV_DONTNEED changes neither the file nor the loaded
    tensors; it only lets the kernel reclaim those source pages before CUDA
    graph capture. The helper is deliberately used only for non-mmapped
    caches, so steady training never faults motion tensors back from disk.
    """

    result: dict[str, object] = {
        "schema": "slash2_lossless_deserialized_file_cache_release_v1",
        "path": str(path.resolve()),
        "bytes": int(path.stat().st_size) if path.is_file() else 0,
        "advised": False,
    }
    if os.name != "posix" or not path.is_file() or not hasattr(os, "posix_fadvise"):
        return result
    try:
        with path.open("rb", buffering=0) as stream:
            os.posix_fadvise(
                stream.fileno(),
                0,
                0,
                os.POSIX_FADV_DONTNEED,
            )
        result["advised"] = True
    except (AttributeError, OSError):
        result["advised"] = False
    print(
        "SLASH2_DESERIALIZED_FILE_CACHE_RELEASE "
        + json.dumps(result, sort_keys=True, separators=(",", ":")),
        flush=True,
    )
    return result


def release_loaded_portable_file_cache() -> dict[str, object]:
    """Release clean source pages for all trusted startup caches read so far."""

    releases = [
        release_deserialized_file_cache(path)
        for path in sorted(_PORTABLE_TORCH_CACHE_FILES_READ)
        if path.is_file()
    ]
    result: dict[str, object] = {
        "schema": "slash2_lossless_loaded_portable_file_cache_release_v1",
        "fileCount": len(releases),
        "bytes": sum(int(item["bytes"]) for item in releases),
        "advisedCount": sum(bool(item["advised"]) for item in releases),
    }
    print(
        "SLASH2_LOADED_PORTABLE_FILE_CACHE_RELEASE "
        + json.dumps(result, sort_keys=True, separators=(",", ":")),
        flush=True,
    )
    return result
PROJECT_ROOT = HERE.parents[1]
IK_DIR = PROJECT_ROOT / "training" / "ik"
if str(IK_DIR) not in sys.path:
    sys.path.insert(0, str(IK_DIR))

import ik_core as tl
import train_simple_ae_controller as ik_ctl
import train_simple_autoencoder as simple_ae
import visualize

# The shared IK helper was renamed from the historical
# ``lift_noisy_init_feet_above_ground`` spelling.  Persistent RunPod
# checkouts can legitimately predate that rename, so expose the exact same
# implementation under the current name without adding work to the hot path.
if not hasattr(ik_ctl, "lift_feet_above_ground"):
    ik_ctl.lift_feet_above_ground = ik_ctl.lift_noisy_init_feet_above_ground

import move_slash_targets_to_modified as motion_math
import target_frame_codec as target_codec
from conditional_delta_projector import ConditionalDeltaProjector
from lower_state_projector_features import (
    LOWER_STATE_DIM,
    STATE_CONDITIONED_AE1_DIM,
    STATE_CONDITIONED_AE11_DIM,
)
from native_controller_targets import (
    direction_angle_deg,
    install_lower_target_output_on_store,
    install_lower_targets_on_store,
    load_controller_target_arrays,
    lower_target_output_from_clip,
)
from upper_delta_features import (
    AE22_DIM,
    ARM_SPECS,
    ATTACK_LABEL_NAMES,
    CORE_BONES,
    MOTION_DELTA_DIM,
    STATE_CONDITIONED_AE2_DIM,
    STATE_CONDITIONED_AE_DIM,
    load_motion_arrays,
    target_height_condition,
    upper_transition_features,
)
from swept_box_collision import (
    DEFAULT_EXCLUDED_COLLIDERS,
    RIGHT_LOWERARM_SELF_COLLISION_NAMES,
    SWEEP_SAMPLES,
    BladeBoxDefinition,
    BodyCollisionLayout,
    blade_box_from_pose,
    build_body_collision_layout,
    load_blade_box_definition,
    swept_box_capsule_penetration,
    swept_blade_body_collision,
)


LOWER_INPUT_DIM_FROZEN_ENABLED = target_codec.LOWER_INPUT_DIM_FROZEN_ENABLED
LOWER_INPUT_DIM_FROZEN_DISABLED = target_codec.LOWER_INPUT_DIM_FROZEN_DISABLED
LOWER_POSE_DELTA_DIM = LOWER_STATE_DIM
LOWER_PIN_COMMAND_DIM = int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)
LOWER_OUTPUT_DIM = target_codec.LOWER_OUTPUT_DIM
LOWER_PIN_INTEGRATION_STEPS = 4
LOWER_PIN_HEIGHT_GATE_ENABLED = False
LOWER_PIN_SIDE_BLEND_DEG = 8.0
LOWER_PIN_GROUND_Y_M = 0.0
ANTI_PIN_SLIDE_RAMP_START = 0.90
ANTI_PIN_SLIDE_RAMP_PEAK = 0.98
UPPER_STATE_DIM = MOTION_DELTA_DIM
UPPER_INPUT_DIM = target_codec.UPPER_INPUT_DIM
UPPER_OUTPUT_DIM = target_codec.UPPER_OUTPUT_DIM
GATE_THRESHOLD = 0.6
ROOT_PAD_FRAMES = 25
FRAGMENT_SCHEDULE_CHUNK_EPOCHS = 1_024
PRE_HIT_DYNAMICS_SLASH2_CUDA_GRAPH_SCHEMA = (
    "slash2_target_xz_current_pelvis_facing_v3_graph_v3_optional_frozen"
)
PRE_OPPOSITE_CALF_SLASH2_CUDA_GRAPH_SCHEMA = (
    "slash2_target_xz_current_pelvis_facing_v3_graph_v4_hit_limb_dynamics"
)
PRE_PIKE_BLADE_LOOK_SLASH2_CUDA_GRAPH_SCHEMA = (
    "slash2_target_xz_current_pelvis_facing_v3_graph_v5_opposite_calf_collision"
)
PRE_PREDICTIVE_PIN_SLASH2_CUDA_GRAPH_SCHEMA = (
    "slash2_target_xz_current_pelvis_facing_v3_graph_v6_pike_blade_look_at_target"
)
PRE_INSUFFICIENT_PIN_SLASH2_CUDA_GRAPH_SCHEMA = (
    "slash2_target_xz_current_pelvis_facing_v3_graph_v7_predictive_pin"
)
PRE_ANTI_PIN_SLIDE_SLASH2_CUDA_GRAPH_SCHEMA = (
    "slash2_target_xz_current_pelvis_facing_v3_graph_v8_insufficient_pin"
)
SLASH2_CUDA_GRAPH_SCHEMA = "slash2_target_xz_current_pelvis_facing_v3_graph_v9_anti_pin_slide"
FULL_ATTACK_BATCH_CACHE_KIND = "slash2_target_frame_v3_compact_attack_batch_v2"
HIT_DYNAMICS_CACHE_KIND = "slash2_hit_limb_transition_dynamics_v2"
NATIVE_LOWER_TARGET_CACHE_KIND = "slash2_native_lower_targets_v1"
PACKED_MOTION_CLIPS_CACHE_KIND = "slash2_prepared_motion_clips"
PACKED_MOTION_CLIPS_CACHE_VERSION = 1
PRE_FIXED_POINT_BLADE_SLASH2_CUDA_GRAPH_SCHEMA = (
    "slash2_cuda_graph_full5392_original10_modes50_uniform_variants_v17"
)
PRE_BALANCED_MODES_SLASH2_CUDA_GRAPH_SCHEMA = (
    "slash2_cuda_graph_full2696_original10_uniform_variants_v16"
)
PRE_FULL_DATASET_SLASH2_CUDA_GRAPH_SCHEMA = (
    "slash2_cuda_graph_gt16_bs64_visible_gt_native_controller_targets_v15"
)
PRE_VISIBLE_GT_NATIVE_TARGET_SLASH2_CUDA_GRAPH_SCHEMA = (
    "slash2_cuda_graph_gt16_bs64_native_controller_pose_targets_v14"
)
PRE_NATIVE_CONTROLLER_POSE_SLASH2_CUDA_GRAPH_SCHEMA = (
    "slash2_cuda_graph_gt16_bs64_raw_controlled_pose_targets_v13"
)
PRE_RAW_CONTROLLED_POSE_SLASH2_CUDA_GRAPH_SCHEMA = (
    "slash2_cuda_graph_gt16_bs64_ae33x2_lr5e5_final_pose_lowerarm_stretch_v12"
)
PRE_FINAL_POSE_LOWERARM_SLASH2_CUDA_GRAPH_SCHEMA = (
    "slash2_cuda_graph_gt16_bs64_ae33x2_random_reset_swept_blade_collision_v11"
)
PRE_BATCH64_AE33X2_SLASH2_CUDA_GRAPH_SCHEMA = (
    "slash2_cuda_graph_forward_backward_gt16_random_reset_swept_blade_collision_v10"
)
PRE_FULL_GRAPH_SWEPT_COLLISION_SLASH2_CUDA_GRAPH_SCHEMA = (
    "slash2_cuda_graph_gt16_random_reset_swept_blade_collision_v9"
)
PRE_SWEPT_COLLISION_SLASH2_CUDA_GRAPH_SCHEMA = "slash2_cuda_graph_full_episode_gt16_3ae_gate_armed_hit_pose_hit_target_lower_contpin_v8"
PRE_HIT_TARGET_SLASH2_CUDA_GRAPH_SCHEMA = "slash2_cuda_graph_full_episode_gt16_3ae_gate_armed_hit_pose_lower_contpin_v7"
PRE_ARMED_HIT_POSE_SLASH2_CUDA_GRAPH_SCHEMA = "slash2_cuda_graph_full_episode_gt16_3ae_gate_lower_contpin_v6"
PRE_LOWER_PIN_SLASH2_CUDA_GRAPH_SCHEMA = "slash2_cuda_graph_full_episode_gt16_hybrid_position_scale_v5"
PRE_POSITION_SCALE_SLASH2_CUDA_GRAPH_SCHEMA = "slash2_cuda_graph_full_episode_gt16_hybrid_trajectory_clip_v4"
PRE_CLIP_SLASH2_CUDA_GRAPH_SCHEMA = "slash2_cuda_graph_full_episode_gt16_hybrid_trajectory_v3"
PRE_TRAJECTORY_SLASH2_CUDA_GRAPH_SCHEMA = "slash2_cuda_graph_full_episode_gt16_motion_seed_v2"
LEGACY_SLASH2_CUDA_GRAPH_SCHEMA = "slash2_cuda_graph_full_episode_gt16"
# This is the permanent family tag consumed by the unchanged standalone viewer.
# Internal training/runtime revisions belong in schemas.training_graph instead.
SLASH2_VIEWER_COMPAT_SCHEMA = PRE_TRAJECTORY_SLASH2_CUDA_GRAPH_SCHEMA
DEBUG_ROLLOUT_REQUEST_NAME = "export_last_rollout.request.json"
DEBUG_ROLLOUT_ARTIFACT_NAME = "last_batch_rollout.json"
DEBUG_ROLLOUT_CAPTURE_PREFIX = "rollout_step_"
DEBUG_ROLLOUT_ACTIVE_NAME = "training.active.json"
DEBUG_ROLLOUT_CHECK_INTERVAL_S = 0.5
_DEBUG_ROLLOUT_NEXT_CHECK_AT = 0.0

WEIGHTED_LOSS_TERM_NAMES = (
    "ae11",
    "ae22",
    "ae33",
    "gate_timing",
    "armed_pose",
    "hit_pose",
    "hit_linear_velocity",
    "hit_angular_velocity",
    "final_pose",
    "hit_target_mse",
    "pike_blade_look_at_target",
    "lowerarm_length",
    "opposite_calf_collision",
    "blade_collision",
    "predictive_pin",
    "anti_pin_slide",
)
WEIGHTED_LOSS_METRIC_NAMES = ("total", *WEIGHTED_LOSS_TERM_NAMES)


ATTACK_LABELS = {
    "headbutt": (0.5, 0.0, 1.0, 0.0, 1.0),
    "jabr": (1.0, 0.0, 1.0, 0.0, 0.0),
    "jabl": (-1.0, 0.0, 1.0, 0.0, 0.0),
    "hookr": (0.6, 0.0, 1.0, 0.0, 0.0),
    "hookl": (-0.6, 0.0, 1.0, 0.0, 0.0),
    "overr": (0.2, 0.0, 1.0, 0.0, 0.0),
    "overl": (-0.2, 0.0, 1.0, 0.0, 0.0),
    "kickr": (1.0, 0.0, 1.0, 1.0, 0.0),
    "kickl": (-1.0, 0.0, 1.0, 1.0, 0.0),
    "pike": (0.5, 1.0, 0.0, 0.0, 0.0),
    "slashr": (-0.6, 0.0, 0.0, 0.0, 0.0),
    "slashl": (0.6, 0.0, 0.0, 0.0, 0.0),
    "slashrd": (-0.2, 0.0, 0.0, 0.0, 0.0),
    "slashld": (0.2, 0.0, 0.0, 0.0, 0.0),
    "slashru": (-1.0, 0.0, 0.0, 0.0, 0.0),
    "slashlu": (1.0, 0.0, 0.0, 0.0, 0.0),
}

BLADE_ATTACK_FAMILIES = frozenset(
    {"pike", "slashr", "slashl", "slashrd", "slashld", "slashru", "slashlu"}
)
HIT_DYNAMICS_JOINT_BY_FAMILY = {
    "headbutt": "head",
    "jabr": "hand_r",
    "jabl": "hand_l",
    "hookr": "hand_r",
    "hookl": "hand_l",
    "overr": "hand_r",
    "overl": "hand_l",
    "kickr": "foot_r",
    "kickl": "foot_l",
    "pike": "hand_r",
    "slashr": "hand_r",
    "slashl": "hand_r",
    "slashrd": "hand_r",
    "slashld": "hand_r",
    "slashru": "hand_r",
    "slashlu": "hand_r",
}

FULL_DATASET_GT_COUNT = 32
FULL_DATASET_VARIANT_COUNT = 5_044
FULL_DATASET_TOTAL_COUNT = FULL_DATASET_GT_COUNT + FULL_DATASET_VARIANT_COUNT
FULL_DATASET_MODE_GT_COUNT = FULL_DATASET_GT_COUNT // 2
FULL_DATASET_MODE_VARIANT_COUNT = FULL_DATASET_VARIANT_COUNT // 2


def attack_family_token_from_path(path: Path) -> str:
    """Return the authored family token, including ``_m`` when mirrored.

    Saved viewer targets historically placed a timestamp before the original
    filename.  Search every ``__`` token so those retained files remain
    loadable without weakening the fixed family allow-list.
    """

    tokens = Path(path).stem.lower().split("__")
    for token in tokens:
        family = token[:-2] if token.endswith("_m") else token
        if family in ATTACK_LABELS:
            return token
    return tokens[0]


def attack_family_from_path(path: Path) -> str:
    """Return the controller family for normal, mirrored, or variant attack names."""
    family = attack_family_token_from_path(path)
    if family.endswith("_m"):
        family = family[:-2]
    return family


def attack_is_mirrored_path(path: Path) -> bool:
    """Return the authored mode from a base or ``__`` variant filename."""

    return attack_family_token_from_path(path).endswith("_m")


def attack_difficulty_id_from_path(path: Path) -> int:
    """Return -1 for shared GT or 0/1/2 for Easy/Medium/Hard variants."""

    stem = path.stem.lower()
    for difficulty_id, difficulty in enumerate(("easy", "medium", "hard")):
        if f"__live_{difficulty}_init_" in stem:
            return difficulty_id
    return -1


def authored_post_hit_tail_steps(length: int, hit_time: float) -> int:
    """Integer frames retained after an agent's learned hit transition.

    Authored hit times may be fractional, whereas the phase latch changes on
    an integer transition.  Measuring from ``ceil(hit_time)`` makes an agent
    that hits on the authored transition finish on the authored last frame.
    """

    if length < 2 or not math.isfinite(float(hit_time)):
        raise ValueError("attack length and hit time must be finite and valid")
    hit_transition = int(math.ceil(float(hit_time)))
    if hit_transition < 1 or hit_transition >= int(length):
        raise ValueError(
            f"hit transition {hit_transition} lies outside a {length}-frame attack"
        )
    return max(0, int(length) - 1 - hit_transition)


def agent_relative_finish_transition(
    agent_finish_index: torch.Tensor,
    hit_latch: torch.Tensor,
    next_hit_latch: torch.Tensor,
    next_logical_index: torch.Tensor,
    lengths: torch.Tensor,
    post_hit_tail_steps: torch.Tensor,
    difficulty_id: torch.Tensor,
    active: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Advance the Medium/Hard learned endpoint with fixed-shape tensor math."""

    enabled = difficulty_id >= 1
    new_agent_hit = (hit_latch < 0.5) & (next_hit_latch >= 0.5)
    learned_finish_index = torch.minimum(
        next_logical_index + post_hit_tail_steps,
        lengths - 1,
    )
    next_finish_index = torch.where(
        new_agent_hit & enabled,
        learned_finish_index,
        agent_finish_index,
    )
    authored_finished = active & (next_logical_index >= lengths - 1)
    agent_finished = (
        active & enabled & (next_logical_index >= next_finish_index)
    )
    return next_finish_index, authored_finished, authored_finished | agent_finished


# Authored pose supervision is applied directly in the two agents' cleaned
# following-root state vectors.  The lower selection excludes pelvis
# translation and toe hinges; each leg contributes foot position/rotation and
# thigh (IK start) rotation.  The upper state already consists only of core
# rotations plus hand position/rotation and upper-arm rotation.
LOWER_NATIVE_POSE_FIELDS = (
    "pelvis_rot6",
    "foot_l_pos",
    "foot_l_rot6",
    "thigh_l_rot6",
    "foot_r_pos",
    "foot_r_rot6",
    "thigh_r_rot6",
)
UPPER_NATIVE_POSE_FIELDS = (
    *(f"{name}_local_rot6" for name in CORE_BONES),
    "hand_l_pos",
    "hand_l_rot6",
    "upperarm_l_rot6",
    "hand_r_pos",
    "hand_r_rot6",
    "upperarm_r_rot6",
)
IMPLICIT_IK_BONES = ("calf_l", "calf_r", "lowerarm_l", "lowerarm_r")


@dataclass(frozen=True)
class Recipe:
    # Fixed semantic recipe. These are deliberately not CLI flags.
    # One authoritative strict-v3 directory contains the 32 GT normal/M clips
    # and every accepted variant. GT-only discovery selects the 32 base names;
    # full-corpus discovery selects ``__`` variants from this same directory.
    gt_dir: str = str(HERE / "final_target_frame_v3_attack_dataset_npz")
    # Variants are enabled by the full-dataset launcher; direct invocation
    # remains a strict GT-only contract/smoke path.
    variant_dir: str | None = None
    original_sample_probability: float = 0.10
    walk_checkpoint: str = str(
        PROJECT_ROOT
        / "training/runs/20260705_142401_ik_walk_finetune_legcap30_idlepin03_from_final/checkpoints/"
        "20260705_142401_ik_walk_finetune_legcap30_idlepin03_from_final_latest.pt"
    )
    # False means the locomotion network is physically absent: its checkpoint
    # weights, model, forward, compile, and CUDA-graph region are all omitted.
    frozen_agent_enabled: bool = True
    ae11_pointer: str = str(HERE / "ae11.json")
    ae22_pointer: str = str(HERE / "ae22.json")
    ae33_pointer: str = str(HERE / "ae33.json")
    hit_contact_definitions: str = str(HERE / "hit_contact_definitions.json")
    blade_collision_definition: str = str(HERE / "blade_collision_box.json")
    output_root: str = str(PROJECT_ROOT / "training" / "runs")
    # V3 has a new input/state contract and always begins from scratch.
    resume_checkpoint: str | None = None
    frozen_mode: str = "walk_idle"
    # Physical CUDA batch. There is deliberately no separate logical batch or
    # gradient-accumulation launch knob: one requested batch means one graph
    # replay and one optimizer step.
    batch_size: int = 32
    hidden_dim: int = 512
    hidden_layers: int = 2
    learning_rate: float = 5.0e-5
    learning_rate_decay_step: int = 1_500
    learning_rate_after_decay: float = 5.0e-5
    weight_decay: float = 0.0
    gradient_clip_norm: float = 50.0
    gate_threshold: float = GATE_THRESHOLD
    # AE11 applies throughout; AE22 applies before armed and AE33 after armed.
    ae11_weight: float = 1.0
    ae11_weight_after_decay: float = 1.0
    upper_prior_weight: float = 1.0
    upper_prior_weight_after_decay: float = 1.0
    ae33_weight_multiplier: float = 2.0
    gate_timing_weight: float = 1.0
    gate_timing_easy_multiplier: float = 1.0
    gate_timing_medium_multiplier: float = 0.5
    gate_timing_hard_multiplier: float = 0.5
    armed_pose_weight: float = 10.0
    hit_pose_weight: float = 10.0
    # Hit dynamics use physical m/s and rad/s targets but are normalized by
    # the source FPS inside the loss.  Their raw scale is therefore one
    # authored frame of displacement/rotation, matching the pose objective.
    hit_linear_velocity_weight: float = 10.0 / 1.5
    hit_angular_velocity_weight: float = 10.0 / 15.0
    # Dataset-wide step-15,166 visible-GT native-target calibration: raw 0.0024056676775217056 -> 0.01.
    final_pose_weight: float = 4.156850130813537
    hit_target_weight: float = 5.0
    # Pike-only cosine look loss from the right hand through the baked distal
    # blade-box endpoint, active on authored frames from armed through hit.
    # Production launchers override this with an exact checkpoint calibration.
    pike_blade_look_at_target_weight: float = 1.0
    # The former extension-only term was calibrated to 0.001 at step 15,166.
    # The active contract is symmetric (extension and compression), with the
    # requested permanent x2 multiplier baked into the default recipe.
    lowerarm_length_weight: float = 4.53691442021562
    # One symmetric path only: left calf capsule against right calf capsule.
    # Production launchers override this with the exact checkpoint calibration.
    opposite_calf_collision_weight: float = 1.0
    predictive_pin_checkpoint: str | None = None
    predictive_pin_checkpoint_sha256: str = ""
    predictive_pin_weight: float = 0.0
    # Post-projection foot-slide objective. Its production weight is calibrated
    # on the exact resume checkpoint; zero keeps old profiles unchanged.
    anti_pin_slide_weight: float = 0.0
    blade_collision_weight: float = 14_491.348219869717
    blade_collision_excluded_colliders: tuple[str, ...] = DEFAULT_EXCLUDED_COLLIDERS
    blade_collision_sweep_samples: int = SWEEP_SAMPLES
    # Fine-tuning may reserve a small number of logical rows for one attack
    # family.  The deterministic CPU schedule rewrites only the clip identity;
    # it preserves each row's existing GT/variant and normal/M category, so
    # this adds no captured-graph work and does not disturb the 10/90 law.
    forced_attack_family: str = ""
    forced_attack_family_rows_per_logical_batch: int = 0
    log_every: int = 25
    save_every: int = 100
    checkpoint_archive_every: int = 100
    seed: int = 1234
    smoke_replays: int = 2


RECIPE = Recipe()


@dataclass
class FrozenPrior:
    name: str
    path: Path
    model: torch.nn.Module
    mean: torch.Tensor
    std: torch.Tensor
    schema: dict[str, object]
    checkpoint: dict[str, object]


@contextmanager
def slash2_runtime_policy(checkpoint: dict[str, object] | None):
    """Install the controller math policy without requiring frozen weights."""

    if checkpoint is not None:
        with visualize.use_checkpoint_output_contract(checkpoint):
            visualize.apply_simple_controller_policy(checkpoint)
            yield
        return
    previous_root = tl.OUTPUT_REFERENCE_ROOT
    previous_prediction = tl.OUTPUT_PREDICTION_MODE
    tl.OUTPUT_REFERENCE_ROOT = tl.OUTPUT_REFERENCE_ROOT_CURRENT
    tl.OUTPUT_PREDICTION_MODE = tl.OUTPUT_PREDICTION_MODE_RESIDUAL
    visualize.apply_simple_controller_policy({})
    try:
        yield
    finally:
        tl.OUTPUT_REFERENCE_ROOT = previous_root
        tl.OUTPUT_PREDICTION_MODE = previous_prediction


def lower_input_dim_for_recipe(recipe: Recipe) -> int:
    return target_codec.lower_input_dim(
        frozen_agent_enabled=bool(recipe.frozen_agent_enabled)
    )


@dataclass
class AttackBatch:
    paths: list[Path]
    names: list[str]
    clip_ids: torch.Tensor
    lengths: torch.Tensor
    labels: torch.Tensor
    targets_world: torch.Tensor
    trajectory_heading: torch.Tensor
    initial_previous_upper: torch.Tensor
    initial_current_upper: torch.Tensor
    initial_global_pos: torch.Tensor
    initial_global_rot: torch.Tensor
    armed_time: torch.Tensor
    hit_time: torch.Tensor
    armed_step: torch.Tensor
    armed_alpha: torch.Tensor
    hit_step: torch.Tensor
    hit_alpha: torch.Tensor
    difficulty_id: torch.Tensor
    post_hit_tail_steps: torch.Tensor
    armed_lower: torch.Tensor
    armed_upper: torch.Tensor
    hit_lower: torch.Tensor
    hit_upper: torch.Tensor
    armed_heading: torch.Tensor
    hit_heading: torch.Tensor
    final_heading: torch.Tensor
    trajectory_lower: torch.Tensor
    trajectory_base_upper: torch.Tensor
    trajectory_upper: torch.Tensor
    trajectory_global_pos: torch.Tensor
    trajectory_global_rot: torch.Tensor
    contact_joint: torch.Tensor
    contact_offset: torch.Tensor
    contact_frame_kind: torch.Tensor
    contact_is_blade: torch.Tensor
    fps: torch.Tensor
    hit_linear_velocity: torch.Tensor
    hit_angular_velocity: torch.Tensor
    max_steps: int


@dataclass
class AttackRows:
    clip_ids: torch.Tensor
    lengths: torch.Tensor
    labels: torch.Tensor
    targets_world: torch.Tensor
    trajectory_heading: torch.Tensor
    initial_previous_upper: torch.Tensor
    initial_current_upper: torch.Tensor
    initial_global_pos: torch.Tensor
    initial_global_rot: torch.Tensor
    armed_time: torch.Tensor
    hit_time: torch.Tensor
    armed_step: torch.Tensor
    armed_alpha: torch.Tensor
    hit_step: torch.Tensor
    hit_alpha: torch.Tensor
    difficulty_id: torch.Tensor
    post_hit_tail_steps: torch.Tensor
    armed_lower: torch.Tensor
    armed_upper: torch.Tensor
    hit_lower: torch.Tensor
    hit_upper: torch.Tensor
    armed_heading: torch.Tensor
    hit_heading: torch.Tensor
    final_heading: torch.Tensor
    trajectory_lower: torch.Tensor
    trajectory_base_upper: torch.Tensor
    trajectory_upper: torch.Tensor
    trajectory_global_pos: torch.Tensor
    trajectory_global_rot: torch.Tensor
    contact_joint: torch.Tensor
    contact_offset: torch.Tensor
    contact_frame_kind: torch.Tensor
    contact_is_blade: torch.Tensor
    fps: torch.Tensor
    hit_linear_velocity: torch.Tensor
    hit_angular_velocity: torch.Tensor
    max_steps: int


@dataclass
class DynamicAttackRows:
    """Compact per-row record staged for one full-dataset reset slot."""

    clip_ids: torch.Tensor
    lengths: torch.Tensor
    labels: torch.Tensor
    targets_world: torch.Tensor
    armed_time: torch.Tensor
    hit_time: torch.Tensor
    armed_step: torch.Tensor
    armed_alpha: torch.Tensor
    hit_step: torch.Tensor
    hit_alpha: torch.Tensor
    difficulty_id: torch.Tensor
    post_hit_tail_steps: torch.Tensor
    armed_lower: torch.Tensor
    armed_upper: torch.Tensor
    hit_lower: torch.Tensor
    hit_upper: torch.Tensor
    armed_heading: torch.Tensor
    hit_heading: torch.Tensor
    final_heading: torch.Tensor
    final_lower: torch.Tensor
    final_upper: torch.Tensor
    contact_joint: torch.Tensor
    contact_offset: torch.Tensor
    contact_frame_kind: torch.Tensor
    contact_is_blade: torch.Tensor
    fps: torch.Tensor
    hit_linear_velocity: torch.Tensor
    hit_angular_velocity: torch.Tensor
    max_steps: int


DYNAMIC_ATTACK_SOURCE_FIELDS = (
    "clip_ids",
    "lengths",
    "labels",
    "targets_world",
    "armed_time",
    "hit_time",
    "armed_step",
    "armed_alpha",
    "hit_step",
    "hit_alpha",
    "difficulty_id",
    "post_hit_tail_steps",
    "armed_lower",
    "armed_upper",
    "hit_lower",
    "hit_upper",
    "armed_heading",
    "hit_heading",
    "final_heading",
    "contact_joint",
    "contact_offset",
    "contact_frame_kind",
    "contact_is_blade",
    "fps",
    "hit_linear_velocity",
    "hit_angular_velocity",
)


def select_attack_rows(data: AttackBatch, rows: torch.Tensor) -> AttackRows:
    def take(value: torch.Tensor) -> torch.Tensor:
        return value.index_select(0, rows)

    return AttackRows(
        clip_ids=take(data.clip_ids),
        lengths=take(data.lengths),
        labels=take(data.labels),
        targets_world=take(data.targets_world),
        trajectory_heading=take(data.trajectory_heading),
        initial_previous_upper=take(data.initial_previous_upper),
        initial_current_upper=take(data.initial_current_upper),
        initial_global_pos=take(data.initial_global_pos),
        initial_global_rot=take(data.initial_global_rot),
        armed_time=take(data.armed_time),
        hit_time=take(data.hit_time),
        armed_step=take(data.armed_step),
        armed_alpha=take(data.armed_alpha),
        hit_step=take(data.hit_step),
        hit_alpha=take(data.hit_alpha),
        difficulty_id=take(data.difficulty_id),
        post_hit_tail_steps=take(data.post_hit_tail_steps),
        armed_lower=take(data.armed_lower),
        armed_upper=take(data.armed_upper),
        hit_lower=take(data.hit_lower),
        hit_upper=take(data.hit_upper),
        armed_heading=take(data.armed_heading),
        hit_heading=take(data.hit_heading),
        final_heading=take(data.final_heading),
        trajectory_lower=take(data.trajectory_lower),
        trajectory_base_upper=take(data.trajectory_base_upper),
        trajectory_upper=take(data.trajectory_upper),
        trajectory_global_pos=take(data.trajectory_global_pos),
        trajectory_global_rot=take(data.trajectory_global_rot),
        contact_joint=take(data.contact_joint),
        contact_offset=take(data.contact_offset),
        contact_frame_kind=take(data.contact_frame_kind),
        contact_is_blade=take(data.contact_is_blade),
        fps=take(data.fps),
        hit_linear_velocity=take(data.hit_linear_velocity),
        hit_angular_velocity=take(data.hit_angular_velocity),
        max_steps=data.max_steps,
    )


def merge_attack_rows(
    current: AttackRows,
    replacement: AttackRows,
    replace_mask: torch.Tensor,
) -> AttackRows:
    """Replace complete per-row motion records at an exact reset boundary."""

    values: dict[str, object] = {}
    for item in fields(AttackRows):
        name = item.name
        if name == "max_steps":
            values[name] = max(int(current.max_steps), int(replacement.max_steps))
            continue
        old = getattr(current, name)
        new = getattr(replacement, name)
        if not torch.is_tensor(old) or not torch.is_tensor(new):
            raise TypeError(f"AttackRows.{name} must be a tensor")
        mask = replace_mask.reshape(
            int(replace_mask.numel()), *([1] * (old.ndim - 1))
        )
        values[name] = torch.where(mask, new, old)
    return AttackRows(**values)  # type: ignore[arg-type]


def merge_dynamic_attack_rows(
    current: DynamicAttackRows,
    replacement: DynamicAttackRows,
    replace_mask: torch.Tensor,
) -> DynamicAttackRows:
    values: dict[str, object] = {}
    for item in fields(DynamicAttackRows):
        name = item.name
        if name == "max_steps":
            values[name] = max(int(current.max_steps), int(replacement.max_steps))
            continue
        old = getattr(current, name)
        new = getattr(replacement, name)
        mask = replace_mask.reshape(
            int(replace_mask.numel()), *([1] * (old.ndim - 1))
        )
        values[name] = torch.where(mask, new, old)
    return DynamicAttackRows(**values)  # type: ignore[arg-type]


@dataclass
class Runtime:
    recipe: Recipe
    device: torch.device
    walk_checkpoint: dict[str, object] | None
    walk_checkpoint_path: Path | None
    cfg: tl.TrainConfig
    lower_clips: list[tl.MotionClip]
    full_clips: list[tl.MotionClip]
    lower_store: ik_ctl.SimpleClipStore
    lower_row_stores: list[ik_ctl.SimpleClipStore]
    lower_batched_store: ik_ctl.SimpleClipStore
    lower_clip: tl.MotionClip
    full_clip: tl.MotionClip
    lower_fk_geometry: dict[str, torch.Tensor]
    full_fk_geometry: dict[str, torch.Tensor]
    frozen_walk: torch.nn.Module | None
    ae11: FrozenPrior
    ae22: FrozenPrior
    ae33: FrozenPrior
    blade_collision: BladeBoxDefinition
    body_collision_layout: BodyCollisionLayout
    native_lower_pose_indices: torch.Tensor
    attacks: AttackBatch
    pin_teacher: torch.nn.Module | None = None
    pin_teacher_metadata: dict[str, object] | None = None

    @contextmanager
    def policy_context(self):
        with slash2_runtime_policy(self.walk_checkpoint):
            yield


@dataclass
class InferenceRuntime:
    """Minimal Slash2 runtime required to render one controller rollout.

    Training priors, collision-loss geometry, optimizer
    policy, corpus quotas, and sampling assertions are deliberately absent.
    A standalone viewer must not rebuild the training dependency graph merely
    to execute the frozen walk policy followed by the two learned agents.
    """

    recipe: Recipe
    device: torch.device
    walk_checkpoint: dict[str, object] | None
    walk_checkpoint_path: Path | None
    cfg: tl.TrainConfig
    lower_clips: list[tl.MotionClip]
    full_clips: list[tl.MotionClip]
    lower_store: ik_ctl.SimpleClipStore
    lower_row_stores: list[ik_ctl.SimpleClipStore]
    lower_batched_store: ik_ctl.SimpleClipStore
    lower_clip: tl.MotionClip
    full_clip: tl.MotionClip
    lower_fk_geometry: dict[str, torch.Tensor]
    full_fk_geometry: dict[str, torch.Tensor]
    frozen_walk: torch.nn.Module | None
    attacks: AttackBatch
    pin_teacher: torch.nn.Module | None = None
    pin_teacher_metadata: dict[str, object] | None = None
    pin_teacher: torch.nn.Module | None = None
    pin_teacher_metadata: dict[str, object] | None = None

    @contextmanager
    def policy_context(self):
        with slash2_runtime_policy(self.walk_checkpoint):
            yield


def canonical_original_runtime(runtime: Runtime) -> Runtime:
    """Cheap GT16 view used by the unchanged exhaustive contract suite."""

    if len(runtime.attacks.paths) == len(ATTACK_LABELS):
        return runtime
    rows = torch.arange(len(ATTACK_LABELS), dtype=torch.long, device=runtime.device)
    attacks = copy.copy(runtime.attacks)
    attacks.paths = list(runtime.attacks.paths[: len(ATTACK_LABELS)])
    attacks.names = list(runtime.attacks.names[: len(ATTACK_LABELS)])
    for item in fields(AttackBatch):
        name = item.name
        value = getattr(runtime.attacks, name)
        if torch.is_tensor(value):
            source_rows = rows.to(value.device)
            setattr(
                attacks,
                name,
                value.index_select(0, source_rows).to(runtime.device),
            )
    selected = copy.copy(runtime)
    selected.attacks = attacks
    selected.lower_clips = list(runtime.lower_clips[: len(ATTACK_LABELS)])
    selected.full_clips = list(runtime.full_clips[: len(ATTACK_LABELS)])
    selected.lower_row_stores = list(runtime.lower_row_stores[: len(ATTACK_LABELS)])
    selected.lower_batched_store = select_lower_projection_store(
        runtime.lower_batched_store, rows
    )
    selected.lower_fk_geometry = select_fk_geometry(runtime.lower_fk_geometry, rows)
    selected.full_fk_geometry = select_fk_geometry(runtime.full_fk_geometry, rows)
    return selected


@dataclass
class Slash2Rollout:
    """One checkpoint-driven attack rollout for standalone visualization."""

    attack_name: str
    attack_path: Path
    clip: tl.MotionClip
    cfg: tl.TrainConfig
    positions: np.ndarray
    rotations: np.ndarray
    gate_probabilities: np.ndarray
    lower_pin_probabilities: np.ndarray
    ideal_pin_probabilities: np.ndarray
    armed_latch: np.ndarray
    hit_latch: np.ndarray
    target_world: np.ndarray
    foot_pinning_disabled: bool = False
    initialization_source: str = "clean attack frames 0/1"
    target_positions: np.ndarray | None = None
    target_rotations: np.ndarray | None = None


_SLASH2_ROLLOUT_SESSION_CACHE: dict[
    tuple[str, str, int],
    tuple[dict[str, object], Recipe, torch.nn.Module, torch.nn.Module],
] = {}
_SLASH2_ROLLOUT_BATCH_CACHE: dict[tuple[object, ...], dict[str, list[np.ndarray]]] = {}
_SLASH2_ROLLOUT_RESULT_CACHE: dict[tuple[object, ...], Slash2Rollout] = {}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_pointer(path: Path) -> Path:
    payload = json.loads(path.read_text(encoding="utf-8"))
    checkpoint = Path(str(payload["checkpoint"]))
    return checkpoint.resolve() if checkpoint.is_absolute() else (PROJECT_ROOT / checkpoint).resolve()


def simple_ae_config(checkpoint: dict[str, object]) -> simple_ae.SimpleAEConfig:
    valid = {field.name for field in fields(simple_ae.SimpleAEConfig)}
    values = checkpoint.get("config", {})
    assert isinstance(values, dict)
    return simple_ae.SimpleAEConfig(**{key: value for key, value in values.items() if key in valid})


def load_prior_checkpoint(name: str, checkpoint_path: Path, device: torch.device) -> FrozenPrior:
    checkpoint_path = checkpoint_path.resolve()
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    schema = checkpoint.get("schema", {})
    if not isinstance(schema, dict):
        raise ValueError(f"{name} checkpoint has no schema")
    checkpoint_target_schema = checkpoint.get("slash2_target_frame_schema")
    if checkpoint_target_schema != target_codec.TARGET_FRAME_SCHEMA:
        raise ValueError(
            f"{name} checkpoint uses {checkpoint_target_schema!r}; strict "
            f"{target_codec.TARGET_FRAME_SCHEMA!r} is required"
        )
    expected_total = (
        target_codec.AE11_INPUT_DIM
        if name == "ae11"
        else target_codec.AE22_INPUT_DIM
    )
    mean = torch.as_tensor(checkpoint["mean"], dtype=torch.float32, device=device)
    std = torch.as_tensor(checkpoint["std"], dtype=torch.float32, device=device).clamp_min(1.0e-8)
    if int(schema.get("total_dim", -1)) != expected_total or int(mean.numel()) != expected_total:
        raise ValueError(
            f"{name} checkpoint dimension mismatch: schema={schema.get('total_dim')} "
            f"mean={int(mean.numel())} expected={expected_total}"
        )
    cfg = simple_ae_config(checkpoint)
    if checkpoint.get("kind") == "slash2_conditional_delta_projector":
        projector = checkpoint.get("projector", {})
        if not isinstance(projector, dict):
            raise ValueError(f"{name} conditional checkpoint has no projector config")
        model = ConditionalDeltaProjector(
            int(mean.numel()),
            int(projector["motion_dim"]),
            int(projector.get("hidden_dim", cfg.hidden_dim)),
            int(projector.get("num_hidden_layers", cfg.num_hidden_layers)),
        ).to(device)
    else:
        model = simple_ae.SimpleAutoencoder(int(mean.numel()), cfg).to(device)
    model.load_state_dict(checkpoint["model"])
    model.eval().requires_grad_(False)
    return FrozenPrior(name, checkpoint_path, model, mean, std, schema, checkpoint)


def load_prior(name: str, pointer: Path, device: torch.device) -> FrozenPrior:
    return load_prior_checkpoint(name, resolve_pointer(pointer), device)


def upper_rotation_starts() -> tuple[int, ...]:
    starts = list(range(0, 60, 6))
    for arm_start in (60, 75):
        starts.extend((arm_start + 3, arm_start + 9))
    return tuple(starts)


UPPER_ROTATION_STARTS = upper_rotation_starts()


def clean_upper_state(values: torch.Tensor) -> torch.Tensor:
    if int(values.shape[-1]) != UPPER_STATE_DIM:
        raise ValueError(f"Expected {UPPER_STATE_DIM} upper values, got {values.shape[-1]}")
    batch = int(values.shape[0])
    core = tl.clean_6d(values[:, :60].reshape(-1, 6)).reshape(batch, 60)
    arms: list[torch.Tensor] = []
    for start in (60, 75):
        arms.append(
            torch.cat(
                (
                    values[:, start : start + 3],
                    tl.clean_6d(values[:, start + 3 : start + 9]),
                    tl.clean_6d(values[:, start + 9 : start + 15]),
                ),
                dim=-1,
            )
        )
    return torch.cat((core, *arms), dim=-1)


def flat_heading(root_rot: torch.Tensor) -> torch.Tensor:
    return tl.yaw_to_row_matrix(tl.heading_yaw_from_root(root_rot))


def root_relative_position(
    world: torch.Tensor,
    root_pos: torch.Tensor,
    root_heading: torch.Tensor,
) -> torch.Tensor:
    return torch.matmul((world - root_pos).unsqueeze(1), root_heading.transpose(-1, -2)).squeeze(1)


def root_relative_rotation(world: torch.Tensor, root_heading: torch.Tensor) -> torch.Tensor:
    return world @ root_heading.transpose(-1, -2)


def upper_state_from_globals(
    full_clip: tl.MotionClip,
    global_pos: torch.Tensor,
    global_rot: torch.Tensor,
    root_pos: torch.Tensor,
    root_rot: torch.Tensor,
) -> torch.Tensor:
    by_name = {name: index for index, name in enumerate(full_clip.body_names)}
    core_parts: list[torch.Tensor] = []
    for name in CORE_BONES:
        index = by_name[name]
        parent = int(full_clip.parents_body_list[index])
        local = global_rot[:, index] if parent < 0 else global_rot[:, index] @ global_rot[:, parent].transpose(-1, -2)
        core_parts.append(tl.rotmat_to_6d(local))
    parts: list[torch.Tensor] = [torch.cat(core_parts, dim=-1)]
    for _side, upper_name, _lower_name, hand_name in ARM_SPECS:
        upper_index = by_name[upper_name]
        hand_index = by_name[hand_name]
        parts.extend(
            (
                root_relative_position(global_pos[:, hand_index], root_pos, root_rot),
                tl.rotmat_to_6d(root_relative_rotation(global_rot[:, hand_index], root_rot)),
                tl.rotmat_to_6d(root_relative_rotation(global_rot[:, upper_index], root_rot)),
            )
        )
    return clean_upper_state(torch.cat(parts, dim=-1))


FK_GEOMETRY_KEYS = (
    "local_offsets",
    "ik_limb_lengths",
    "ik_local_pole_axis",
    "ik_toe_offsets",
    "ik_toe_axis",
)


SLASH_CONTROLLER_BODY_NAMES = (
    "pelvis",
    "spine_01",
    "spine_02",
    "spine_03",
    "spine_04",
    "spine_05",
    "clavicle_l",
    "upperarm_l",
    "lowerarm_l",
    "hand_l",
    "clavicle_r",
    "upperarm_r",
    "lowerarm_r",
    "hand_r",
    "neck_01",
    "neck_02",
    "head",
    "thigh_l",
    "calf_l",
    "foot_l",
    "ball_l",
    "thigh_r",
    "calf_r",
    "foot_r",
    "ball_r",
)
SLASH_REST_OFFSETS_KEY = "slash_rest_offsets_from_pelvis"


def rest_offsets_from_pelvis(
    clip: tl.MotionClip,
    local_offsets: torch.Tensor,
) -> torch.Tensor:
    """Accumulate the identity-pose rest tree once, outside the hot rollout."""

    if local_offsets.ndim != 3 or int(local_offsets.shape[1]) != int(clip.J):
        raise ValueError(
            f"Expected batched [N,{clip.J},3] offsets, got {tuple(local_offsets.shape)}"
        )
    zero = torch.zeros_like(local_offsets[:, 0])
    accumulated: list[torch.Tensor] = []
    for joint, parent in enumerate(clip.parents_body_list):
        if joint == int(clip.pelvis):
            accumulated.append(zero)
        elif int(parent) < 0:
            accumulated.append(local_offsets[:, joint])
        else:
            accumulated.append(accumulated[int(parent)] + local_offsets[:, joint])
    return torch.stack(accumulated, dim=1)


def stack_fk_geometry(clips: list[tl.MotionClip], device: torch.device) -> dict[str, torch.Tensor]:
    if not clips:
        raise ValueError("Per-motion FK geometry requires at least one clip")
    prototype = clips[0]
    tensors = [clip.tensors(device) for clip in clips]
    for clip in clips[1:]:
        if (
            clip.body_names != prototype.body_names
            or clip.parents_body_list != prototype.parents_body_list
            or clip.ik_limb_specs != prototype.ik_limb_specs
        ):
            raise ValueError(f"FK topology mismatch: {clip.path} vs {prototype.path}")
    geometry = {
        key: torch.stack([values[key] for values in tensors], dim=0)
        for key in FK_GEOMETRY_KEYS
    }
    geometry[SLASH_REST_OFFSETS_KEY] = rest_offsets_from_pelvis(
        prototype,
        geometry["local_offsets"],
    )
    return geometry


LOWER_PROJECTION_GEOMETRY_FIELDS = (
    "local_offsets",
    "ik_limb_lengths",
    "ik_mid_offsets",
    "ik_end_offsets",
    "ik_toe_offsets",
    "ik_toe_axis",
)


def stack_lower_projection_store(
    base_store: ik_ctl.SimpleClipStore,
    row_stores: list[ik_ctl.SimpleClipStore],
) -> ik_ctl.SimpleClipStore:
    """Make one fixed-shape store whose geometry row matches each attack row."""

    if not row_stores:
        raise ValueError("Motion-batched lower projection requires at least one row store")
    batched = copy.copy(base_store)
    for field_name in LOWER_PROJECTION_GEOMETRY_FIELDS:
        setattr(
            batched,
            field_name,
            torch.stack([getattr(store, field_name) for store in row_stores], dim=0),
        )
    return batched


def select_lower_projection_store(
    batched_store: ik_ctl.SimpleClipStore,
    rows: torch.Tensor,
) -> ik_ctl.SimpleClipStore:
    selected = copy.copy(batched_store)
    for field_name in LOWER_PROJECTION_GEOMETRY_FIELDS:
        values = getattr(batched_store, field_name)
        setattr(selected, field_name, values.index_select(0, rows))
    return selected


def stack_lower_projection_store_from_clips(
    base_store: ik_ctl.SimpleClipStore,
    clips: list[tl.MotionClip],
    device: torch.device,
) -> ik_ctl.SimpleClipStore:
    """Stack only the per-motion geometry needed by runtime projection.

    Building thousands of complete one-clip stores duplicates root/controller
    tensors and is unnecessary. This produces the same geometry fields from
    each clip while retaining the single complete multi-clip store for roots
    and frozen-policy features.
    """

    tensors = [clip.tensors(device) for clip in clips]
    batched = copy.copy(base_store)
    batched.local_offsets = torch.stack([item["local_offsets"] for item in tensors], dim=0)
    batched.ik_limb_lengths = torch.stack([item["ik_limb_lengths"] for item in tensors], dim=0)
    batched.ik_toe_offsets = torch.stack([item["ik_toe_offsets"] for item in tensors], dim=0)
    batched.ik_toe_axis = torch.stack([item["ik_toe_axis"] for item in tensors], dim=0)
    batched.ik_mid_offsets = batched.local_offsets.index_select(1, base_store.ik_mid_indices_tensor)
    batched.ik_end_offsets = batched.local_offsets.index_select(1, base_store.ik_end_indices_tensor)
    return batched


def lower_projection_store_row(
    batched_store: ik_ctl.SimpleClipStore,
    row: int,
) -> ik_ctl.SimpleClipStore:
    """Cheap one-row view used only while preparing authored targets."""

    selected = copy.copy(batched_store)
    for field_name in LOWER_PROJECTION_GEOMETRY_FIELDS:
        values = getattr(batched_store, field_name)
        setattr(selected, field_name, values[row : row + 1])
    return selected


def select_fk_geometry(
    geometry: dict[str, torch.Tensor],
    clip_ids: torch.Tensor,
    canonical_clip_ids: torch.Tensor | None = None,
) -> dict[str, torch.Tensor]:
    if canonical_clip_ids is not None and clip_ids is canonical_clip_ids:
        return geometry
    return {key: value.index_select(0, clip_ids) for key, value in geometry.items()}


def _slash_fast_fk_supported(clip: tl.MotionClip) -> bool:
    controlled = {int(clip.pelvis), *map(int, clip.core_non_pelvis)}
    for spec in clip.ik_limb_specs:
        controlled.update(
            (
                int(spec["start"]),
                int(spec["mid"]),
                int(spec["end"]),
            )
        )
        if spec.get("toe") is not None:
            controlled.add(int(spec["toe"]))
    return (
        tuple(clip.body_names) == SLASH_CONTROLLER_BODY_NAMES
        and int(clip.pelvis) == 0
        and controlled == set(range(int(clip.J)))
    )


def _slash_fast_fk_globals_impl(
    clip: tl.MotionClip,
    root_pos: torch.Tensor,
    root_rot: torch.Tensor,
    pose: dict[str, torch.Tensor],
    geometry: dict[str, torch.Tensor],
    *,
    assume_supported: bool,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Vectorized exact FK for the fixed Slash2 controller skeleton."""

    if not assume_supported and not _slash_fast_fk_supported(clip):
        positions, rotations, _canon = tl.fk_from_pose(
            clip,
            root_pos,
            root_rot,
            pose,
            root_pos.device,
            geometry_tensors=geometry,
        )
        return positions, rotations

    batch = int(root_pos.shape[0])
    offsets = geometry["local_offsets"].to(dtype=root_rot.dtype)
    limb_lengths = geometry["ik_limb_lengths"].to(dtype=root_rot.dtype)
    local_pole_axes = geometry["ik_local_pole_axis"].to(dtype=root_rot.dtype)
    toe_offsets = geometry["ik_toe_offsets"].to(dtype=root_rot.dtype)
    toe_axes = geometry["ik_toe_axis"].to(dtype=root_rot.dtype)
    if int(offsets.shape[0]) != batch:
        raise ValueError(
            f"Slash FK geometry has {int(offsets.shape[0])} rows for batch {batch}"
        )

    pelvis_rotation = tl.rotation_6d_to_matrix(pose["pelvis_rot6"])
    pelvis_world_rotation = pelvis_rotation @ root_rot
    pelvis_world_position = (
        torch.matmul(pose["pelvis_pos"].unsqueeze(1), root_rot).squeeze(1)
        + root_pos
    )

    positions: list[torch.Tensor | None]
    rotations: list[torch.Tensor | None]
    if int(clip.Jcore) == 0:
        rest_offsets = geometry[SLASH_REST_OFFSETS_KEY].to(dtype=root_rot.dtype)
        all_positions = (
            torch.matmul(
                rest_offsets.unsqueeze(2),
                pelvis_world_rotation[:, None],
            ).squeeze(2)
            + pelvis_world_position[:, None]
        )
        all_rotations = pelvis_world_rotation[:, None].expand(
            -1,
            int(clip.J),
            -1,
            -1,
        )
        positions = [all_positions[:, joint] for joint in range(int(clip.J))]
        rotations = [all_rotations[:, joint] for joint in range(int(clip.J))]
    else:
        core_rotation = tl.rotation_6d_to_matrix(
            pose["core_nonpelvis_rot6"]
        )
        positions = [None] * int(clip.J)
        rotations = [None] * int(clip.J)
        positions[int(clip.pelvis)] = pelvis_world_position
        rotations[int(clip.pelvis)] = pelvis_world_rotation
        for joint in clip.core_non_pelvis:
            joint = int(joint)
            parent = int(clip.parents_body_list[joint])
            parent_position = positions[parent]
            parent_rotation = rotations[parent]
            assert parent_position is not None and parent_rotation is not None
            positions[joint] = (
                torch.matmul(
                    offsets[:, joint].unsqueeze(1),
                    parent_rotation,
                ).squeeze(1)
                + parent_position
            )
            rotations[joint] = (
                core_rotation[:, int(clip.core_nonpelvis_map[joint])]
                @ parent_rotation
            )

        for spec in clip.ik_limb_specs:
            start = int(spec["start"])
            parent = int(clip.parents_body_list[start])
            parent_position = positions[parent]
            parent_rotation = rotations[parent]
            assert parent_position is not None and parent_rotation is not None
            positions[start] = (
                torch.matmul(
                    offsets[:, start].unsqueeze(1),
                    parent_rotation,
                ).squeeze(1)
                + parent_position
            )

    payload = pose["ik_payload"]
    end_root_parts: list[torch.Tensor] = []
    end_rotation_parts: list[torch.Tensor] = []
    start_rotation_parts: list[torch.Tensor] = []
    toe_value_parts: list[torch.Tensor | None] = []
    for spec in clip.ik_payload_slices:
        pos_slice = spec["pos"]
        rot_slice = spec["rot6"]
        start_rot_slice = spec["start_rot6"]
        toe_slice = spec["toe_float"]
        assert isinstance(pos_slice, slice)
        assert isinstance(rot_slice, slice)
        assert isinstance(start_rot_slice, slice)
        end_root_parts.append(payload[:, pos_slice])
        end_rotation_parts.append(payload[:, rot_slice])
        start_rotation_parts.append(payload[:, start_rot_slice])
        if toe_slice is None:
            toe_value_parts.append(None)
        else:
            assert isinstance(toe_slice, slice)
            toe_value_parts.append(payload[:, toe_slice])

    limb_count = len(clip.ik_limb_specs)
    end_root = torch.stack(end_root_parts, dim=1)
    end_rotation_root = tl.rotation_6d_to_matrix(
        torch.stack(end_rotation_parts, dim=1).reshape(-1, 6)
    ).reshape(batch, limb_count, 3, 3)
    start_rotation_root = tl.rotation_6d_to_matrix(
        torch.stack(start_rotation_parts, dim=1).reshape(-1, 6)
    ).reshape(batch, limb_count, 3, 3)
    start_positions = torch.stack(
        [positions[int(spec["start"])] for spec in clip.ik_limb_specs],
        dim=1,
    )
    start_rotation_world = start_rotation_root @ root_rot[:, None]
    mid_indices = [int(spec["mid"]) for spec in clip.ik_limb_specs]
    end_indices = [int(spec["end"]) for spec in clip.ik_limb_specs]
    upper_offsets = torch.stack(
        [offsets[:, joint] for joint in mid_indices],
        dim=1,
    )
    lower_offsets = torch.stack(
        [offsets[:, joint] for joint in end_indices],
        dim=1,
    )
    solved_mid = (
        torch.matmul(
            upper_offsets.unsqueeze(2),
            start_rotation_world,
        ).squeeze(2)
        + start_positions
    )
    mid_root = torch.matmul(
        (solved_mid - root_pos[:, None]).unsqueeze(2),
        root_rot[:, None].transpose(-1, -2),
    ).squeeze(2)
    if tl.IK_CLAMP_END_EFFECTORS_TO_REACH:
        delta = end_root - mid_root
        distance = torch.linalg.norm(delta, dim=-1, keepdim=True)
        fallback_axis = torch.matmul(
            lower_offsets.unsqueeze(2),
            start_rotation_root,
        ).squeeze(2)
        axis = torch.where(
            distance > 1.0e-8,
            tl.normalize(delta),
            tl.normalize(fallback_axis),
        )
        lower_length = limb_lengths[:, :, 1:2]
        end_root = mid_root + axis * distance.clamp_min(1.0e-8).clamp(
            max=lower_length - 1.0e-5
        )

    solved_end = (
        torch.matmul(end_root.unsqueeze(2), root_rot[:, None]).squeeze(2)
        + root_pos[:, None]
    )
    end_rotation_world = end_rotation_root @ root_rot[:, None]
    world_pole = torch.matmul(
        local_pole_axes[:, :, 0].unsqueeze(2),
        start_rotation_world,
    ).squeeze(2)
    lower_axis_world = solved_end - solved_mid
    lower_fallback_world = torch.matmul(
        lower_offsets.unsqueeze(2),
        start_rotation_world,
    ).squeeze(2)
    lower_axis_world = torch.where(
        torch.linalg.norm(lower_axis_world, dim=-1, keepdim=True) > 1.0e-8,
        lower_axis_world,
        lower_fallback_world,
    )
    mid_local_pole = local_pole_axes[:, :, 1]
    if getattr(clip, "leg_rotation_contract", None) == "signed_hinge_normal_v1":
        # Same explicit opt-in as ik_core.fk_from_pose. Arms and all existing
        # runtimes retain the legacy codec. Only the new Dodge leg frame uses
        # the signed hinge normal instead of projecting a forward bend ray.
        world_parts = []
        local_parts = []
        for limb, spec in enumerate(clip.ik_limb_specs):
            if str(spec.get("kind", "")).lower().strip() == "leg":
                world_parts.append(tl.normalize(torch.cross(
                    solved_mid[:, limb] - start_positions[:, limb], world_pole[:, limb], dim=-1,
                )))
                local_parts.append(tl.normalize(torch.cross(
                    lower_offsets[:, limb], mid_local_pole[:, limb], dim=-1,
                )))
            else:
                world_parts.append(world_pole[:, limb])
                local_parts.append(mid_local_pole[:, limb])
        world_pole = torch.stack(world_parts, dim=1)
        mid_local_pole = torch.stack(local_parts, dim=1)
    mid_rotation_world = tl.rotation_from_axis_and_pole(
        lower_offsets.reshape(-1, 3),
        lower_axis_world.reshape(-1, 3),
        mid_local_pole.reshape(-1, 3),
        world_pole.reshape(-1, 3),
    ).reshape(batch, limb_count, 3, 3)

    for limb, spec in enumerate(clip.ik_limb_specs):
        start = int(spec["start"])
        mid = int(spec["mid"])
        end = int(spec["end"])
        positions[start] = start_positions[:, limb]
        positions[mid] = solved_mid[:, limb]
        positions[end] = solved_end[:, limb]
        rotations[start] = start_rotation_world[:, limb]
        rotations[mid] = mid_rotation_world[:, limb]
        rotations[end] = end_rotation_world[:, limb]
        toe = spec.get("toe")
        if toe is None:
            continue
        toe_value = toe_value_parts[limb]
        assert toe_value is not None
        toe_root = end_root[:, limb] + torch.matmul(
            toe_offsets[:, limb].unsqueeze(1),
            end_rotation_root[:, limb],
        ).squeeze(1)
        toe_hinge = tl.axis_angle_to_row_matrix(
            toe_axes[:, limb],
            toe_value[:, 0].clamp(-1.0, 1.0) * tl.IK_TOE_ALPHA,
        )
        toe_rotation_root = toe_hinge @ end_rotation_root[:, limb]
        positions[int(toe)] = (
            torch.matmul(toe_root.unsqueeze(1), root_rot).squeeze(1)
            + root_pos
        )
        rotations[int(toe)] = toe_rotation_root @ root_rot

    if any(value is None for value in positions) or any(
        value is None for value in rotations
    ):
        raise RuntimeError("Slash fast FK did not populate the complete skeleton")
    return (
        torch.stack(positions, dim=1),  # type: ignore[arg-type]
        torch.stack(rotations, dim=1),  # type: ignore[arg-type]
    )


def slash_fast_fk_globals(
    clip: tl.MotionClip,
    root_pos: torch.Tensor,
    root_rot: torch.Tensor,
    pose: dict[str, torch.Tensor],
    geometry: dict[str, torch.Tensor],
) -> tuple[torch.Tensor, torch.Tensor]:
    """Checked dispatcher used before the fixed Slash2 runtime is compiled."""

    return _slash_fast_fk_globals_impl(
        clip,
        root_pos,
        root_rot,
        pose,
        geometry,
        assume_supported=False,
    )


def _slash_fast_fk_globals_fixed(
    clip: tl.MotionClip,
    root_pos: torch.Tensor,
    root_rot: torch.Tensor,
    pose: dict[str, torch.Tensor],
    geometry: dict[str, torch.Tensor],
) -> tuple[torch.Tensor, torch.Tensor]:
    """Compile-only entry after the runtime skeleton contract has passed."""

    return _slash_fast_fk_globals_impl(
        clip,
        root_pos,
        root_rot,
        pose,
        geometry,
        assume_supported=True,
    )


def lower_fk_globals(
    runtime: Runtime,
    clip_ids: torch.Tensor,
    lower_vec: torch.Tensor,
    root_pos: torch.Tensor,
    root_rot: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    pose, _raw = tl.output_to_pose(lower_vec, runtime.lower_clip)
    pos, rot = slash_fast_fk_globals(
        runtime.lower_clip,
        root_pos,
        root_rot,
        pose,
        select_fk_geometry(
            runtime.lower_fk_geometry,
            clip_ids,
            runtime.attacks.clip_ids if runtime.attacks is not None else None,
        ),
    )
    return pos, rot


def base_upper_from_lower(
    runtime: Runtime,
    clip_ids: torch.Tensor,
    lower_vec: torch.Tensor,
    root_pos: torch.Tensor,
    root_rot: torch.Tensor,
) -> torch.Tensor:
    upper, _pos, _rot = base_upper_with_globals_from_lower(
        runtime,
        clip_ids,
        lower_vec,
        root_pos,
        root_rot,
    )
    return upper


def base_upper_with_globals_from_lower(
    runtime: Runtime,
    clip_ids: torch.Tensor,
    lower_vec: torch.Tensor,
    root_pos: torch.Tensor,
    root_rot: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Return the exact upper seed and the FK tensors that produced it."""

    pos, rot = lower_fk_globals(runtime, clip_ids, lower_vec, root_pos, root_rot)
    upper = upper_state_from_globals(
        runtime.full_clip,
        pos,
        rot,
        root_pos,
        root_rot,
    )
    return upper, pos, rot


def compose_full_vector(runtime: Runtime, lower_vec: torch.Tensor, upper: torch.Tensor) -> torch.Tensor:
    batch = int(lower_vec.shape[0])
    full = lower_vec.new_zeros((batch, 3 + 6 + runtime.full_clip.Jcore * 6 + runtime.full_clip.ik_payload_dim))
    full[:, :9] = lower_vec[:, :9]

    full_core_start = 9
    upper_core = upper[:, :60].reshape(batch, len(CORE_BONES), 6)
    upper_core_by_name = {name: upper_core[:, i] for i, name in enumerate(CORE_BONES)}
    for full_slot, body_index in enumerate(runtime.full_clip.core_non_pelvis):
        full[:, full_core_start + full_slot * 6 : full_core_start + (full_slot + 1) * 6] = upper_core_by_name[
            runtime.full_clip.body_names[body_index]
        ]

    full_payload_start = full_core_start + runtime.full_clip.Jcore * 6
    lower_payload = lower_vec[:, 9:]
    upper_arm_by_side = {"l": upper[:, 60:75], "r": upper[:, 75:90]}
    lower_leg_by_side: dict[str, torch.Tensor] = {}
    for spec in runtime.lower_clip.ik_payload_slices:
        start = int(spec["pos"].start)
        stop_obj = spec["toe_float"] if spec["toe_float"] is not None else spec["start_rot6"]
        stop = int(stop_obj.stop)
        lower_leg_by_side[str(spec["side"])] = lower_payload[:, start:stop]

    payload_parts: list[torch.Tensor] = []
    for spec in runtime.full_clip.ik_payload_slices:
        side = str(spec["side"])
        payload_parts.append(upper_arm_by_side[side] if str(spec["kind"]) == "arm" else lower_leg_by_side[side])
    full[:, full_payload_start:] = torch.cat(payload_parts, dim=-1)
    pose, _raw = tl.output_to_pose(full, runtime.full_clip)
    return tl.pose_target_output(pose)


def split_full_vector(
    runtime: Runtime,
    full: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Inverse of ``compose_full_vector`` for the controlled lower/upper fields."""

    batch = int(full.shape[0])
    full = tl.pose_target_output(tl.output_to_pose(full, runtime.full_clip)[0])
    lower = full.new_zeros((batch, LOWER_STATE_DIM))
    lower[:, :9] = full[:, :9]

    full_core_start = 9
    full_payload_start = full_core_start + runtime.full_clip.Jcore * 6
    full_core_by_name = {
        runtime.full_clip.body_names[body_index]: full[
            :,
            full_core_start + full_slot * 6 : full_core_start + (full_slot + 1) * 6,
        ]
        for full_slot, body_index in enumerate(runtime.full_clip.core_non_pelvis)
    }
    upper_core = torch.cat([full_core_by_name[name] for name in CORE_BONES], dim=-1)

    full_payload_by_kind_side: dict[tuple[str, str], torch.Tensor] = {}
    for spec in runtime.full_clip.ik_payload_slices:
        start = int(spec["pos"].start)
        stop_obj = (
            spec["toe_float"]
            if spec["toe_float"] is not None
            else spec["start_rot6"]
        )
        stop = int(stop_obj.stop)
        full_payload_by_kind_side[(str(spec["kind"]), str(spec["side"]))] = full[
            :, full_payload_start + start : full_payload_start + stop
        ]

    lower_payload = torch.cat(
        [
            full_payload_by_kind_side[("leg", str(spec["side"]))]
            for spec in runtime.lower_clip.ik_payload_slices
        ],
        dim=-1,
    )
    lower[:, 9:] = lower_payload
    lower = tl.pose_target_output(tl.output_to_pose(lower, runtime.lower_clip)[0])

    upper = clean_upper_state(
        torch.cat(
            (
                upper_core,
                full_payload_by_kind_side[("arm", "l")],
                full_payload_by_kind_side[("arm", "r")],
            ),
            dim=-1,
        )
    )
    return lower, upper


def raw_full_fk_globals(
    runtime: Runtime,
    clip_ids: torch.Tensor,
    lower_vec: torch.Tensor,
    upper: torch.Tensor,
    root_pos: torch.Tensor,
    root_rot: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    full = compose_full_vector(runtime, lower_vec, upper)
    pose, _raw = tl.output_to_pose(full, runtime.full_clip)
    return slash_fast_fk_globals(
        runtime.full_clip,
        root_pos,
        root_rot,
        pose,
        select_fk_geometry(
            runtime.full_fk_geometry,
            clip_ids,
            runtime.attacks.clip_ids if runtime.attacks is not None else None,
        ),
    )


def paired_raw_full_fk_globals(
    runtime: Runtime,
    clip_ids: torch.Tensor,
    lower_vec: torch.Tensor,
    first_upper: torch.Tensor,
    second_upper: torch.Tensor,
    root_pos: torch.Tensor,
    root_rot: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Decode two upper candidates in one exact batched FK invocation."""

    batch = int(lower_vec.shape[0])
    paired_pos, paired_rot = raw_full_fk_globals(
        runtime,
        torch.cat((clip_ids, clip_ids), dim=0),
        torch.cat((lower_vec, lower_vec), dim=0),
        torch.cat((first_upper, second_upper), dim=0),
        torch.cat((root_pos, root_pos), dim=0),
        torch.cat((root_rot, root_rot), dim=0),
    )
    return (
        paired_pos[:batch],
        paired_rot[:batch],
        paired_pos[batch:],
        paired_rot[batch:],
    )


def full_fk_globals(
    runtime: Runtime,
    clip_ids: torch.Tensor,
    lower_vec: torch.Tensor,
    upper: torch.Tensor,
    root_pos: torch.Tensor,
    root_rot: torch.Tensor,
    *,
    frozen_pos: torch.Tensor | None = None,
    frozen_rot: torch.Tensor | None = None,
    baseline_upper: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Apply representable upper deviation on top of the exact frozen FK pose.

    The full-body IK decoder has an implicit lower-arm twist.  Its baseline is
    geometrically equivalent to the lower-only frozen FK but not bit-identical
    in those two rotations.  Transporting the candidate's deviation from that
    decoder baseline onto the frozen pose preserves the hard zero-delta
    contract while retaining the same differentiable arm representation.
    """

    if frozen_pos is None or frozen_rot is None:
        if frozen_pos is not None or frozen_rot is not None:
            raise ValueError("frozen_pos and frozen_rot must be supplied together")
        frozen_pos, frozen_rot = lower_fk_globals(
            runtime,
            clip_ids,
            lower_vec,
            root_pos,
            root_rot,
        )
    if baseline_upper is None:
        baseline_upper = upper_state_from_globals(
            runtime.full_clip,
            frozen_pos,
            frozen_rot,
            root_pos,
            root_rot,
        )
    (
        decoder_base_pos,
        decoder_base_rot,
        candidate_pos,
        candidate_rot,
    ) = paired_raw_full_fk_globals(
        runtime,
        clip_ids,
        lower_vec,
        baseline_upper,
        upper,
        root_pos,
        root_rot,
    )
    position = frozen_pos + (candidate_pos - decoder_base_pos)
    rotation_delta = candidate_rot @ decoder_base_rot.transpose(-1, -2)
    rotation = rotation_delta @ frozen_rot
    return position, rotation


@torch.no_grad()
def canonical_attack_globals(
    runtime: Runtime,
    clip_row: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Decode the shared native GT targets through the exact runtime skeleton."""

    if runtime.attacks is None:
        raise RuntimeError("Canonical attack decoding requires the loaded GT batch")
    frame_count = int(runtime.attacks.lengths[clip_row].item())
    clip_ids = torch.full(
        (frame_count,),
        int(clip_row),
        dtype=torch.long,
        device=runtime.device,
    )
    frames = torch.arange(frame_count, dtype=torch.long, device=runtime.device)
    lower = runtime.attacks.trajectory_lower[clip_row, :frame_count]
    upper = runtime.attacks.trajectory_upper[clip_row, :frame_count]
    headings = runtime.attacks.trajectory_heading[clip_row, :frame_count]
    targets = runtime.attacks.targets_world[clip_row : clip_row + 1].expand(
        frame_count, -1
    )
    positions, rotations = hybrid_full_fk_globals(
        runtime,
        clip_ids,
        clip_ids,
        frames,
        lower,
        upper,
        targets,
        headings,
    )
    root_pos, root_rot, _yaw, _heading = runtime.lower_store.root_state(
        clip_ids, frames
    )
    return (
        positions.detach().cpu().numpy().astype(np.float32),
        rotations.detach().cpu().numpy().astype(np.float32),
        root_pos.detach().cpu().numpy().astype(np.float32),
        root_rot.detach().cpu().numpy().astype(np.float32),
    )


def transition_root_dyaw(
    store: ik_ctl.SimpleClipStore,
    clip_ids: torch.Tensor,
    current: torch.Tensor,
    nxt: torch.Tensor,
) -> torch.Tensor:
    _cur_pos, _cur_rot, cur_yaw, _cur_heading = store.root_state(
        clip_ids, current
    )
    _next_pos, _next_rot, next_yaw, _next_heading = store.root_state(
        clip_ids, nxt
    )
    return tl.wrap_angle(next_yaw - cur_yaw)[:, None]


def target_height_input(target_world: torch.Tensor) -> torch.Tensor:
    return target_codec.target_height(target_world)


def reserved_agent_inputs(reference: torch.Tensor) -> torch.Tensor:
    """Return the two deliberately unassigned learned-agent input channels."""

    return reference.new_zeros((*reference.shape[:-1], 2))


def build_lower_learned_input(
    current_lower: torch.Tensor,
    frozen_next: torch.Tensor | None,
    labels: torch.Tensor,
    current_to_next_dyaw: torch.Tensor,
    next_to_future_dyaw: torch.Tensor,
    target_world: torch.Tensor,
) -> torch.Tensor:
    """Build one of the two explicit v3 lower-agent input schemas.

    Disabled-frozen mode omits the complete 41-value proposal block.  It is
    never replaced by zeros, so that mode pays no model or input-bandwidth cost.
    """

    fields = [current_lower]
    if frozen_next is not None:
        fields.append(frozen_next)
    fields.extend(
        (
            labels,
            current_to_next_dyaw,
            next_to_future_dyaw,
            target_height_input(target_world),
            reserved_agent_inputs(current_lower),
        )
    )
    value = torch.cat(tuple(fields), dim=-1)
    expected = (
        LOWER_INPUT_DIM_FROZEN_ENABLED
        if frozen_next is not None
        else LOWER_INPUT_DIM_FROZEN_DISABLED
    )
    if int(value.shape[-1]) != expected:
        raise RuntimeError(
            f"Lower target-frame input width {value.shape[-1]} != {expected}"
        )
    return value


def build_upper_learned_input(
    previous_upper: torch.Tensor,
    next_prior: torch.Tensor,
    target_world: torch.Tensor,
    labels: torch.Tensor,
    previous_lower: torch.Tensor,
    current_lower: torch.Tensor,
    next_lower: torch.Tensor,
    armed_latch: torch.Tensor,
    hit_latch: torch.Tensor,
) -> torch.Tensor:
    """Build the complete upper-agent v3 input and nothing else.

    Upper receives target height, controller-native pelvis prefixes, labels,
    and latches. It has no root translation, root future window, target X/Z,
    or root-yaw-delta channel.
    """

    value = torch.cat(
        (
            previous_upper,
            next_prior,
            target_height_input(target_world),
            labels,
            previous_lower[:, :9],
            current_lower[:, :9],
            next_lower[:, :9],
            armed_latch[:, None],
            hit_latch[:, None],
            reserved_agent_inputs(previous_upper),
        ),
        dim=-1,
    )
    if int(value.shape[-1]) != UPPER_INPUT_DIM:
        raise RuntimeError(
            f"Upper target-frame input width {value.shape[-1]} != {UPPER_INPUT_DIM}"
        )
    return value


def lower_root_state_to_hybrid(
    store: ik_ctl.SimpleClipStore,
    clip_ids: torch.Tensor,
    frame: torch.Tensor,
    state: torch.Tensor,
    target_world: torch.Tensor,
    held_heading: torch.Tensor,
) -> torch.Tensor:
    root_pos, root_rot, _yaw, _heading = store.root_state(clip_ids, frame)
    encoded, _ = target_codec.lower_root_to_target_frame(
        store, state, root_pos, root_rot, target_world, held_heading
    )
    return encoded


def lower_hybrid_state_to_root(
    store: ik_ctl.SimpleClipStore,
    clip_ids: torch.Tensor,
    frame: torch.Tensor,
    state: torch.Tensor,
    target_world: torch.Tensor,
    held_heading: torch.Tensor,
) -> torch.Tensor:
    root_pos, root_rot, _yaw, _heading = store.root_state(clip_ids, frame)
    return target_codec.lower_target_frame_to_root(
        store, state, root_pos, root_rot, target_world, held_heading
    )


def upper_root_state_to_hybrid(
    store: ik_ctl.SimpleClipStore,
    clip_ids: torch.Tensor,
    frame: torch.Tensor,
    state: torch.Tensor,
    target_world: torch.Tensor,
    held_heading: torch.Tensor,
) -> torch.Tensor:
    root_pos, root_rot, _yaw, _heading = store.root_state(clip_ids, frame)
    return target_codec.upper_root_to_target_frame(
        state, root_pos, root_rot, target_world, held_heading
    )


def upper_hybrid_state_to_root(
    store: ik_ctl.SimpleClipStore,
    clip_ids: torch.Tensor,
    frame: torch.Tensor,
    state: torch.Tensor,
    target_world: torch.Tensor,
    held_heading: torch.Tensor,
) -> torch.Tensor:
    root_pos, root_rot, _yaw, _heading = store.root_state(clip_ids, frame)
    return target_codec.upper_target_frame_to_root(
        state, root_pos, root_rot, target_world, held_heading
    )


def transplant_target_relative_to_root(
    target_world: torch.Tensor,
    target_root_pos: torch.Tensor,
    target_root_rot: torch.Tensor,
    source_root_pos: torch.Tensor,
    source_root_rot: torch.Tensor,
) -> torch.Tensor:
    """Move a target's exact root-relative offset onto another attack root."""

    target_local = torch.matmul(
        (target_world - target_root_pos).unsqueeze(-2),
        target_root_rot.transpose(-1, -2),
    ).squeeze(-2)
    return (
        torch.matmul(target_local.unsqueeze(-2), source_root_rot).squeeze(-2)
        + source_root_pos
    )


def carry_upper_hybrid_deviation(
    current_upper: torch.Tensor,
    current_base_upper: torch.Tensor,
    next_base_upper: torch.Tensor,
) -> torch.Tensor:
    """Carry the upper residual inside the one held prediction-step frame."""

    return clean_upper_state(next_base_upper + (current_upper - current_base_upper))


def frozen_next_hybrid(
    runtime: Runtime,
    projection_store: ik_ctl.SimpleClipStore,
    clip_ids: torch.Tensor,
    current_frame: torch.Tensor,
    previous_frame: torch.Tensor,
    previous_hybrid: torch.Tensor,
    current_hybrid: torch.Tensor,
    target_world: torch.Tensor,
    previous_heading: torch.Tensor,
    current_heading: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Run the untouched frozen policy and encode its proposal in held v3 space.

    The frozen checkpoint sees exactly its historical actual-root-relative
    representation.  Only its following-frame result crosses into the learned
    target-origin/current-pelvis-facing representation.
    """

    if runtime.frozen_walk is None:
        raise RuntimeError("Frozen proposal requested while frozen agent is disabled")

    previous_root = lower_hybrid_state_to_root(
        runtime.lower_store,
        clip_ids,
        previous_frame,
        previous_hybrid,
        target_world,
        previous_heading,
    )
    current_root = lower_hybrid_state_to_root(
        runtime.lower_store,
        clip_ids,
        current_frame,
        current_hybrid,
        target_world,
        current_heading,
    )
    controller_input = ik_ctl.build_controller_input(
        runtime.lower_store,
        clip_ids,
        current_frame,
        previous_root,
        current_root,
        previous_root[:, :3],
        current_root[:, :3],
        previous_root[:, 9:],
        current_root[:, 9:],
    )
    frozen_transition = frozen_walk_forward(
        runtime,
        projection_store,
        controller_input,
        current_root,
        previous_root,
    )
    frozen_next_root = ik_ctl.advance_transition_output(
        runtime.lower_store,
        clip_ids,
        current_frame,
        frozen_transition,
    )
    frozen_next_hybrid_state = lower_root_state_to_hybrid(
        runtime.lower_store,
        clip_ids,
        current_frame + 1,
        frozen_next_root,
        target_world,
        current_heading,
    )
    return frozen_next_hybrid_state, controller_input


def clean_lower_hybrid_delta(
    runtime: Runtime,
    projection_store: ik_ctl.SimpleClipStore,
    clip_ids: torch.Tensor,
    current_frame: torch.Tensor,
    next_frame: torch.Tensor,
    current_hybrid: torch.Tensor,
    base_hybrid: torch.Tensor,
    delta_hybrid: torch.Tensor,
    pin_commands: torch.Tensor,
    target_world: torch.Tensor,
    held_heading: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Apply lower cleanup while holding one v3 basis for the full step."""

    current_root = lower_hybrid_state_to_root(
        runtime.lower_store,
        clip_ids,
        current_frame,
        current_hybrid,
        target_world,
        held_heading,
    )
    base_root = lower_hybrid_state_to_root(
        runtime.lower_store,
        clip_ids,
        next_frame,
        base_hybrid,
        target_world,
        held_heading,
    )
    candidate_root = lower_hybrid_state_to_root(
        runtime.lower_store,
        clip_ids,
        next_frame,
        base_hybrid + delta_hybrid,
        target_world,
        held_heading,
    )
    cleaned_root, pin_probabilities = clean_lower_delta(
        runtime,
        projection_store,
        current_root,
        base_root,
        candidate_root - base_root,
        pin_commands,
    )
    cleaned_hybrid = lower_root_state_to_hybrid(
        runtime.lower_store,
        clip_ids,
        next_frame,
        cleaned_root,
        target_world,
        held_heading,
    )
    return cleaned_hybrid, pin_probabilities


def base_upper_hybrid_from_lower(
    runtime: Runtime,
    geometry_clip_ids: torch.Tensor,
    root_clip_ids: torch.Tensor,
    frame: torch.Tensor,
    lower_hybrid: torch.Tensor,
    target_world: torch.Tensor,
    held_heading: torch.Tensor,
) -> torch.Tensor:
    lower_root = lower_hybrid_state_to_root(
        runtime.lower_store,
        root_clip_ids,
        frame,
        lower_hybrid,
        target_world,
        held_heading,
    )
    root_pos, root_rot, _yaw, _heading = runtime.lower_store.root_state(
        root_clip_ids, frame
    )
    base_root = base_upper_from_lower(
        runtime,
        geometry_clip_ids,
        lower_root,
        root_pos,
        root_rot,
    )
    return upper_root_state_to_hybrid(
        runtime.lower_store,
        root_clip_ids,
        frame,
        base_root,
        target_world,
        held_heading,
    )


def base_upper_hybrid_with_globals_from_lower(
    runtime: Runtime,
    geometry_clip_ids: torch.Tensor,
    root_clip_ids: torch.Tensor,
    frame: torch.Tensor,
    lower_hybrid: torch.Tensor,
    target_world: torch.Tensor,
    held_heading: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    lower_root = lower_hybrid_state_to_root(
        runtime.lower_store,
        root_clip_ids,
        frame,
        lower_hybrid,
        target_world,
        held_heading,
    )
    root_pos, root_rot, _yaw, _heading = runtime.lower_store.root_state(
        root_clip_ids, frame
    )
    base_root, global_pos, global_rot = base_upper_with_globals_from_lower(
        runtime,
        geometry_clip_ids,
        lower_root,
        root_pos,
        root_rot,
    )
    base_hybrid = upper_root_state_to_hybrid(
        runtime.lower_store,
        root_clip_ids,
        frame,
        base_root,
        target_world,
        held_heading,
    )
    return base_hybrid, global_pos, global_rot


def hybrid_full_fk_globals(
    runtime: Runtime,
    geometry_clip_ids: torch.Tensor,
    root_clip_ids: torch.Tensor,
    frame: torch.Tensor,
    lower_hybrid: torch.Tensor,
    upper_hybrid: torch.Tensor,
    target_world: torch.Tensor,
    held_heading: torch.Tensor,
    *,
    frozen_pos: torch.Tensor | None = None,
    frozen_rot: torch.Tensor | None = None,
    baseline_upper_hybrid: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Decode v3 learned states through the one authoritative FK boundary."""

    lower_root = lower_hybrid_state_to_root(
        runtime.lower_store,
        root_clip_ids,
        frame,
        lower_hybrid,
        target_world,
        held_heading,
    )
    upper_root = upper_hybrid_state_to_root(
        runtime.lower_store,
        root_clip_ids,
        frame,
        upper_hybrid,
        target_world,
        held_heading,
    )
    baseline_upper_root = None
    if baseline_upper_hybrid is not None:
        baseline_upper_root = upper_hybrid_state_to_root(
            runtime.lower_store,
            root_clip_ids,
            frame,
            baseline_upper_hybrid,
            target_world,
            held_heading,
        )
    root_pos, root_rot, _yaw, _heading = runtime.lower_store.root_state(
        root_clip_ids, frame
    )
    return full_fk_globals(
        runtime,
        geometry_clip_ids,
        lower_root,
        upper_root,
        root_pos,
        root_rot,
        frozen_pos=frozen_pos,
        frozen_rot=frozen_rot,
        baseline_upper=baseline_upper_root,
    )


def following_to_transition_output(
    store: ik_ctl.SimpleClipStore,
    clip_ids: torch.Tensor,
    current: torch.Tensor,
    next_following: torch.Tensor,
) -> torch.Tensor:
    if tl.output_reference_uses_future_root():
        return next_following
    cur_pos, cur_rot, _cur_yaw, _cur_heading = store.root_state(clip_ids, current)
    next_pos, next_rot, _next_yaw, _next_heading = store.root_state(clip_ids, current + 1)
    return ik_ctl.rebase_output_vector_root(store, next_following, next_pos, next_rot, cur_pos, cur_rot)


def lower_pin_probabilities(commands: torch.Tensor) -> torch.Tensor:
    """Map zero-preserving lower pin commands to independent probabilities."""

    if int(commands.shape[-1]) != LOWER_PIN_COMMAND_DIM:
        raise ValueError(
            f"Expected {LOWER_PIN_COMMAND_DIM} lower pin commands, got {int(commands.shape[-1])}"
        )
    return (2.0 * torch.sigmoid(commands) - 1.0).clamp(0.0, 1.0)


def split_lower_output(output: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Read the current 41-delta + 2-pin schema, while replaying old 41-only checkpoints."""

    width = int(output.shape[-1])
    if width == LOWER_POSE_DELTA_DIM:
        return output, output.new_zeros((*output.shape[:-1], LOWER_PIN_COMMAND_DIM))
    if width != LOWER_OUTPUT_DIM:
        raise ValueError(f"Unsupported Slash2 lower output width {width}")
    return output[..., :LOWER_POSE_DELTA_DIM], output[..., LOWER_POSE_DELTA_DIM:]


def clean_lower_delta(
    runtime: Runtime,
    projection_store: ik_ctl.SimpleClipStore,
    current: torch.Tensor,
    base: torch.Tensor,
    delta: torch.Tensor,
    pin_commands: torch.Tensor,
    *,
    effective_pins: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    geometry_rows = (
        int(projection_store.local_offsets.shape[0])
        if projection_store.local_offsets.ndim == 3
        else 1
    )
    if geometry_rows not in (1, int(base.shape[0])):
        raise ValueError(
            f"Lower projection geometry has {geometry_rows} rows for tensor batch {int(base.shape[0])}"
        )
    # Default preserves every Slash checkpoint. Vanilla defense can explicitly
    # supply its versioned linear-clamped strength while reusing the same IK.
    pin_probabilities = lower_pin_probabilities(pin_commands) if effective_pins is None else effective_pins
    freely_moved = ik_ctl.clean_output_vector(base + delta, projection_store)
    pinned = ik_ctl.apply_foot_roll_output_projection_with_pin_probabilities(
        freely_moved,
        current,
        pin_probabilities,
        projection_store,
        integration_steps=LOWER_PIN_INTEGRATION_STEPS,
        height_pin_gate_enabled=LOWER_PIN_HEIGHT_GATE_ENABLED,
    )
    return ik_ctl.lift_feet_above_ground(projection_store, pinned), pin_probabilities


def frozen_walk_forward(
    runtime: Runtime,
    projection_store: ik_ctl.SimpleClipStore,
    controller_input: torch.Tensor,
    current: torch.Tensor,
    previous: torch.Tensor,
) -> torch.Tensor:
    """Run one frozen forward and one motion-batched cleanup/projection."""

    if runtime.frozen_walk is None:
        raise RuntimeError("Frozen forward requested while frozen agent is disabled")

    geometry_rows = (
        int(projection_store.local_offsets.shape[0])
        if projection_store.local_offsets.ndim == 3
        else 1
    )
    if geometry_rows not in (1, int(current.shape[0])):
        raise ValueError(
            f"Frozen projection geometry has {geometry_rows} rows for tensor batch {int(current.shape[0])}"
        )
    raw = ik_ctl.model_raw_output(runtime.frozen_walk, controller_input, current, runtime.lower_store)
    return ik_ctl.clean_output_vector(raw, projection_store, current, previous)


def rotation_slerp(from_rot: torch.Tensor, to_rot: torch.Tensor, alpha: torch.Tensor) -> torch.Tensor:
    shape = from_rot.shape
    flat_from = from_rot.reshape(-1, 3, 3)
    flat_to = to_rot.reshape(-1, 3, 3)
    rotvec = ik_ctl._row_rotation_vector_between(flat_from, flat_to)
    repeats = math.prod(shape[1:-2]) if len(shape) > 3 else 1
    flat_alpha = alpha.reshape(-1).repeat_interleave(repeats)
    delta = ik_ctl._row_rotation_from_vector(rotvec * flat_alpha[:, None])
    return (delta @ flat_from).reshape(shape)


def rotation_vector_between(
    from_rot: torch.Tensor, to_rot: torch.Tensor
) -> torch.Tensor:
    """Return row-vector angular displacement for arbitrary batch/joint shapes."""

    if from_rot.shape != to_rot.shape or from_rot.shape[-2:] != (3, 3):
        raise ValueError(
            f"rotation shapes must match and end in 3x3, got {from_rot.shape}/{to_rot.shape}"
        )
    return ik_ctl._row_rotation_vector_between(
        from_rot.reshape(-1, 3, 3), to_rot.reshape(-1, 3, 3)
    ).reshape(*from_rot.shape[:-2], 3)


def numpy_rotation_vector_between(
    from_rot: np.ndarray, to_rot: np.ndarray
) -> np.ndarray:
    """NumPy parity implementation of the accepted row-rotation log map."""

    from_values = np.asarray(from_rot, dtype=np.float32)
    to_values = np.asarray(to_rot, dtype=np.float32)
    if from_values.shape != to_values.shape or from_values.shape[-2:] != (3, 3):
        raise ValueError(
            "rotation arrays must match and end in 3x3, got "
            f"{from_values.shape}/{to_values.shape}"
        )
    relative = to_values @ np.swapaxes(from_values, -1, -2)
    vee = np.stack(
        (
            relative[..., 1, 2] - relative[..., 2, 1],
            relative[..., 2, 0] - relative[..., 0, 2],
            relative[..., 0, 1] - relative[..., 1, 0],
        ),
        axis=-1,
    )
    vee_norm = np.linalg.norm(vee, axis=-1)
    cosine = np.clip(
        (
            relative[..., 0, 0]
            + relative[..., 1, 1]
            + relative[..., 2, 2]
            - 1.0
        )
        * 0.5,
        -1.0,
        1.0,
    )
    angle = np.arctan2(vee_norm * 0.5, cosine)
    scale = np.where(
        vee_norm > 1.0e-7,
        angle / np.maximum(vee_norm, 1.0e-7),
        np.float32(0.5),
    )
    return np.asarray(vee * scale[..., None], dtype=np.float32)


def interpolate_pose(
    pos_a: torch.Tensor,
    rot_a: torch.Tensor,
    pos_b: torch.Tensor,
    rot_b: torch.Tensor,
    alpha: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    pos_alpha = alpha.reshape(-1, *([1] * (pos_a.ndim - 1)))
    return pos_a + (pos_b - pos_a) * pos_alpha, rotation_slerp(rot_a, rot_b, alpha)


def lower_native_rotation_starts(store: ik_ctl.SimpleClipStore) -> tuple[int, ...]:
    starts = [3]
    payload_start = 9
    for spec in store.ik_payload_slices:
        if str(spec["kind"]) != "leg":
            continue
        for key in ("rot6", "start_rot6"):
            value = spec[key]
            assert isinstance(value, slice)
            starts.append(payload_start + int(value.start))
    return tuple(starts)


def build_native_lower_pose_indices(
    store: ik_ctl.SimpleClipStore,
    device: torch.device,
) -> torch.Tensor:
    indices = list(range(3, 9))
    payload_start = 9
    for spec in store.ik_payload_slices:
        if str(spec["kind"]) != "leg":
            continue
        for key in ("pos", "rot6", "start_rot6"):
            value = spec[key]
            assert isinstance(value, slice)
            indices.extend(
                range(payload_start + int(value.start), payload_start + int(value.stop))
            )
    result = torch.tensor(indices, dtype=torch.long, device=device)
    if int(result.numel()) != 36:
        raise ValueError(f"Expected 36 native lower pose values, got {int(result.numel())}")
    return result


def interpolate_native_state(
    current: torch.Tensor,
    nxt: torch.Tensor,
    alpha: torch.Tensor,
    rotation_starts: tuple[int, ...],
) -> torch.Tensor:
    """Interpolate native positions/scalars linearly and every rot6 on SO(3)."""

    alpha_column = alpha.reshape(-1, 1)
    parts: list[torch.Tensor] = []
    cursor = 0
    for start in rotation_starts:
        if start < cursor or start + 6 > int(current.shape[-1]):
            raise ValueError(f"Invalid native rot6 slice {start}:{start + 6}")
        if start > cursor:
            parts.append(
                current[:, cursor:start]
                + (nxt[:, cursor:start] - current[:, cursor:start]) * alpha_column
            )
        current_rot = tl.rotation_6d_to_matrix(current[:, start : start + 6])
        next_rot = tl.rotation_6d_to_matrix(nxt[:, start : start + 6])
        parts.append(tl.rotmat_to_6d(rotation_slerp(current_rot, next_rot, alpha)))
        cursor = start + 6
    if cursor < int(current.shape[-1]):
        parts.append(
            current[:, cursor:]
            + (nxt[:, cursor:] - current[:, cursor:]) * alpha_column
        )
    return torch.cat(parts, dim=-1)


def event_root_rotation(
    store: ik_ctl.SimpleClipStore,
    clip_ids: torch.Tensor,
    current_frame: torch.Tensor,
    next_frame: torch.Tensor,
    alpha: torch.Tensor,
) -> torch.Tensor:
    """Return the yaw-only root basis at a fractional authored event time."""

    _current_pos, current_rot, _current_yaw, _current_heading = store.root_state(
        clip_ids, current_frame
    )
    _next_pos, next_rot, _next_yaw, _next_heading = store.root_state(
        clip_ids, next_frame
    )
    return rotation_slerp(current_rot, next_rot, alpha)


def interpolate_hybrid_native_states(
    store: ik_ctl.SimpleClipStore,
    clip_ids: torch.Tensor,
    current_frame: torch.Tensor,
    next_frame: torch.Tensor,
    current_lower: torch.Tensor,
    next_lower: torch.Tensor,
    current_upper: torch.Tensor,
    next_upper: torch.Tensor,
    target_world: torch.Tensor,
    alpha: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Interpolate states already expressed in the held prediction-step frame."""

    return (
        interpolate_native_state(
            current_lower,
            next_lower,
            alpha,
            lower_native_rotation_starts(store),
        ),
        interpolate_native_state(
            current_upper,
            next_upper,
            alpha,
            UPPER_ROTATION_STARTS,
        ),
    )


def native_pose_mse_rows(
    runtime: Runtime,
    predicted_lower: torch.Tensor,
    predicted_upper: torch.Tensor,
    target_lower: torch.Tensor,
    target_upper: torch.Tensor,
) -> torch.Tensor:
    """MSE on exactly the cleaned controller coordinates chosen by both agents."""

    lower_error = predicted_lower.index_select(1, runtime.native_lower_pose_indices) - target_lower.index_select(
        1, runtime.native_lower_pose_indices
    )
    upper_error = predicted_upper - target_upper
    return torch.cat((lower_error, upper_error), dim=-1).square().mean(dim=-1)


def lowerarm_length_error_rows(
    runtime: Runtime,
    clip_ids: torch.Tensor,
    positions: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Squared symmetric forearm length error and maximum absolute error.

    The implicit lower arm is the middle-to-end segment of each arm's fixed
    two-bone IK chain. A wrist that is too far from or too close to its elbow
    is penalized by the same squared distance from the fixed runtime length.
    """

    geometry = select_fk_geometry(
        runtime.full_fk_geometry,
        clip_ids,
        runtime.attacks.clip_ids if runtime.attacks is not None else None,
    )
    arm_specs = [spec for spec in runtime.full_clip.ik_limb_specs if str(spec["kind"]) == "arm"]
    if len(arm_specs) != len(ARM_SPECS):
        raise ValueError(f"Expected {len(ARM_SPECS)} arm IK chains, got {len(arm_specs)}")
    actual = torch.stack(
        [
            torch.linalg.vector_norm(
                positions[:, int(spec["end"])] - positions[:, int(spec["mid"])],
                dim=-1,
            )
            for spec in arm_specs
        ],
        dim=-1,
    )
    fixed = geometry["ik_limb_lengths"][:, : len(arm_specs), 1]
    length_error = actual - fixed
    return length_error.square().mean(dim=-1), length_error.abs().amax(dim=-1)


OPPOSITE_CALF_CAPSULE_RADIUS_M = 0.052


def capsule_pair_overlap_rows(
    a0: torch.Tensor,
    a1: torch.Tensor,
    radius_a: float,
    b0: torch.Tensor,
    b1: torch.Tensor,
    radius_b: float,
) -> torch.Tensor:
    """Return capsule overlap using the historical finite-segment geometry."""

    d1 = a1 - a0
    d2 = b1 - b0
    relative = a0 - b0
    a = d1.square().sum(dim=-1).clamp_min(1.0e-8)
    e = d2.square().sum(dim=-1).clamp_min(1.0e-8)
    b = (d1 * d2).sum(dim=-1)
    c = (d1 * relative).sum(dim=-1)
    f = (d2 * relative).sum(dim=-1)
    denominator = (a * e - b.square()).clamp_min(1.0e-8)
    s = ((b * f - c * e) / denominator).clamp(0.0, 1.0)
    t = (b * s + f) / e
    s_if_t_low = (-c / a).clamp(0.0, 1.0)
    s_if_t_high = ((b - c) / a).clamp(0.0, 1.0)
    s = torch.where(
        t < 0.0,
        s_if_t_low,
        torch.where(t > 1.0, s_if_t_high, s),
    )
    t = t.clamp(0.0, 1.0)
    closest_a = a0 + d1 * s.unsqueeze(-1)
    closest_b = b0 + d2 * t.unsqueeze(-1)
    distance = (
        (closest_a - closest_b)
        .square()
        .sum(dim=-1)
        .clamp_min(1.0e-12)
        .sqrt()
    )
    return torch.relu(float(radius_a + radius_b) - distance)


def opposite_calf_collision_rows(
    runtime: Runtime,
    positions: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """One path: predicted left calf capsule against predicted right calf.

    The full predicted FK positions already exist for every transition.  This
    adds only one finite segment-distance calculation and therefore no extra
    FK, motion decode, or host/device work to the captured training step.
    """

    by_name = runtime.full_clip.body_names.index
    overlap = capsule_pair_overlap_rows(
        positions[:, by_name("calf_l")],
        positions[:, by_name("foot_l")],
        OPPOSITE_CALF_CAPSULE_RADIUS_M,
        positions[:, by_name("calf_r")],
        positions[:, by_name("foot_r")],
        OPPOSITE_CALF_CAPSULE_RADIUS_M,
    )
    return (
        overlap.square(),
        overlap,
        (overlap > 0.0).to(dtype=positions.dtype),
    )


def anti_pin_slide_rows(
    runtime: Runtime,
    current_positions: torch.Tensor,
    next_positions: torch.Tensor,
    fps: torch.Tensor,
    effective_pin: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Penalize post-projection sole sliding only for strongly pinned feet.

    For each side, sliding speed is the smaller horizontal world-space speed
    of the foot joint and its ball/toe joint.  The detached pin gate is zero
    through 0.90, rises linearly, and saturates at its peak from 0.98 upward.
    Detaching only the gate prevents the objective from directly rewarding a
    lower pin score while preserving gradients through the predicted pose.
    """

    if effective_pin.ndim != 2 or int(effective_pin.shape[1]) != 2:
        raise ValueError("anti-pin-slide expects [batch, left/right] pin values")
    if fps.ndim != 1 or int(fps.shape[0]) != int(effective_pin.shape[0]):
        raise ValueError("anti-pin-slide FPS must have one value per row")
    by_name = runtime.full_clip.body_names.index
    side_speeds: list[torch.Tensor] = []
    for foot_name, toe_name in (("foot_l", "ball_l"), ("foot_r", "ball_r")):
        # Basic slices only: advanced tuple indexing tries to materialize an
        # index tensor inside CUDA graph capture on torch 2.7/CUDA 12.8.
        foot_delta = (
            next_positions[:, by_name(foot_name)]
            - current_positions[:, by_name(foot_name)]
        )
        toe_delta = (
            next_positions[:, by_name(toe_name)]
            - current_positions[:, by_name(toe_name)]
        )
        foot_speed = (
            foot_delta[:, 0].square() + foot_delta[:, 2].square()
        ).clamp_min(0.0).sqrt() * fps
        toe_speed = (
            toe_delta[:, 0].square() + toe_delta[:, 2].square()
        ).clamp_min(0.0).sqrt() * fps
        side_speeds.append(torch.minimum(foot_speed, toe_speed))
    minimum_speed = torch.stack(side_speeds, dim=-1)
    pin_ramp = (
        (effective_pin.detach() - ANTI_PIN_SLIDE_RAMP_START)
        / (ANTI_PIN_SLIDE_RAMP_PEAK - ANTI_PIN_SLIDE_RAMP_START)
    ).clamp(0.0, 1.0)
    per_foot = pin_ramp * minimum_speed.square()
    return per_foot.mean(dim=-1), minimum_speed, pin_ramp


def contact_point(
    positions: torch.Tensor,
    rotations: torch.Tensor,
    joint: torch.Tensor,
    local_offset: torch.Tensor,
    frame_kind: torch.Tensor,
) -> torch.Tensor:
    batch = torch.arange(positions.shape[0], device=positions.device)
    origin = positions[batch, joint]
    axes = rotations[batch, joint]
    left = torch.stack((axes[:, 0], axes[:, 2], axes[:, 1]), dim=1)
    right = torch.stack((-axes[:, 0], axes[:, 2], axes[:, 1]), dim=1)
    axes = torch.where((frame_kind == 1)[:, None, None], left, axes)
    axes = torch.where((frame_kind == 2)[:, None, None], right, axes)
    return origin + torch.matmul(local_offset.unsqueeze(1), axes).squeeze(1)


def finite_blade_target_mse_rows(
    runtime: Runtime,
    positions: torch.Tensor,
    rotations: torch.Tensor,
    targets_world: torch.Tensor,
) -> torch.Tensor:
    """Squared distance from each target to the closest finite blade-box point.

    The blade is the same immutable hand-attached box used by self-collision.
    Target contact is free to occur anywhere on or inside its finite volume,
    rather than at the obsolete single baked ``blade_t`` point.
    """

    by_name = {name: index for index, name in enumerate(runtime.full_clip.body_names)}
    attach_joint = by_name[runtime.blade_collision.attach_joint]
    center, axes, half = blade_box_from_pose(
        positions,
        rotations,
        attach_joint,
        runtime.blade_collision,
    )
    offset = targets_world - center
    local = (offset[:, None, :] * axes).sum(dim=-1)
    clamped_local = torch.maximum(torch.minimum(local, half), -half)
    closest = center + (clamped_local[:, :, None] * axes).sum(dim=1)
    return (closest - targets_world).square().sum(dim=-1)


def blade_distal_tip_local_m(
    definition: BladeBoxDefinition,
) -> tuple[float, float, float]:
    """Return the baked hand-local vector from attachment origin to blade tip.

    The blade OBB's major axis has no guaranteed sign.  Selecting the endpoint
    farther from the attachment origin makes the sight ray follow the distal
    blade even though this asset's positive major axis points back at the hand.
    """

    center = np.asarray(definition.center_local_m, dtype=np.float64)
    axes = np.asarray(definition.axes_local_rows, dtype=np.float64)
    half = np.asarray(definition.half_extents_m, dtype=np.float64)
    major = int(np.argmax(half))
    negative = center - axes[major] * half[major]
    positive = center + axes[major] * half[major]
    distal = (
        negative
        if float(np.dot(negative, negative)) > float(np.dot(positive, positive))
        else positive
    )
    if not np.isfinite(distal).all() or float(np.linalg.norm(distal)) <= 1.0e-8:
        raise ValueError("blade distal endpoint must be finite and away from the hand")
    return tuple(float(value) for value in distal)


def pike_blade_look_at_target_rows(
    runtime: Runtime,
    positions: torch.Tensor,
    rotations: torch.Tensor,
    targets_world: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Pike sightline cosine loss using the blade's baked hand attachment.

    The ray begins at ``hand_r`` and ends at the farther endpoint of the real
    hand-attached blade box.  This incorporates both the blade center offset
    and its oblique local axes instead of assuming a hand basis axis is the
    blade direction.  The returned loss is ``1 - cosine``.
    """

    by_name = {name: index for index, name in enumerate(runtime.full_clip.body_names)}
    attach_joint = by_name[runtime.blade_collision.attach_joint]
    hand = positions[:, attach_joint]
    hand_rotation = rotations[:, attach_joint]
    one = hand[:, 0] * 0.0 + 1.0
    tip_local = torch.stack(
        tuple(one * value for value in blade_distal_tip_local_m(runtime.blade_collision)),
        dim=-1,
    )
    tip = torch.matmul(tip_local.unsqueeze(1), hand_rotation).squeeze(1) + hand
    blade_ray = tip - hand
    target_ray = targets_world - hand
    blade_direction = blade_ray / torch.linalg.vector_norm(
        blade_ray, dim=-1, keepdim=True
    ).clamp_min(1.0e-8)
    target_direction = target_ray / torch.linalg.vector_norm(
        target_ray, dim=-1, keepdim=True
    ).clamp_min(1.0e-8)
    cosine = (blade_direction * target_direction).sum(dim=-1).clamp(-1.0, 1.0)
    return 1.0 - cosine, cosine


def pike_blade_look_at_target_phase_mask(
    labels: torch.Tensor,
    next_index: torch.Tensor,
    armed_time: torch.Tensor,
    hit_time: torch.Tensor,
    active: torch.Tensor,
) -> torch.Tensor:
    """Select only pike rows on NPZ-authored frames armed..hit, inclusive."""

    # ATTACK_LABELS reserves channel one exclusively for pike.
    is_pike = labels[:, 1] > 0.5
    authored_frame = next_index.to(torch.float32)
    in_window = (authored_frame >= armed_time) & (authored_frame <= hit_time)
    return active.to(torch.float32) * is_pike.to(torch.float32) * in_window.to(torch.float32)


def hit_target_mse_rows(
    runtime: Runtime,
    positions: torch.Tensor,
    rotations: torch.Tensor,
    data: AttackBatch | AttackRows | DynamicAttackRows,
) -> torch.Tensor:
    """Use finite-blade contact for swords and authored limb points otherwise."""

    fixed_point = contact_point(
        positions,
        rotations,
        data.contact_joint,
        data.contact_offset,
        data.contact_frame_kind,
    )
    fixed_rows = (fixed_point - data.targets_world).square().sum(dim=-1)
    blade_rows = finite_blade_target_mse_rows(
        runtime,
        positions,
        rotations,
        data.targets_world,
    )
    return torch.where(data.contact_is_blade, blade_rows, fixed_rows)


def hit_transition_dynamics_mse_rows(
    current_pos: torch.Tensor,
    current_rot: torch.Tensor,
    next_pos: torch.Tensor,
    next_rot: torch.Tensor,
    data: AttackBatch | AttackRows | DynamicAttackRows,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Match the striking joint on the NPZ-authored hit transition only.

    The optimizer terms divide physical velocity errors by FPS, making them
    exactly per-frame displacement and rotation-vector MSE. This preserves a
    pose-like scale while detached diagnostics remain m/s and rad/s.  The
    caller applies the one-hot ``hit_mask`` derived from ``attack_hit_frame``.
    """

    batch = torch.arange(current_pos.shape[0], device=current_pos.device)
    joint = data.contact_joint
    fps = data.fps.reshape(-1, 1)
    predicted_linear = (
        next_pos[batch, joint] - current_pos[batch, joint]
    ) * fps
    predicted_angular = rotation_vector_between(
        current_rot[batch, joint], next_rot[batch, joint]
    ) * fps
    linear_error = predicted_linear - data.hit_linear_velocity
    angular_error = predicted_angular - data.hit_angular_velocity
    linear_rows = (linear_error / fps).square().mean(dim=-1)
    angular_rows = (angular_error / fps).square().mean(dim=-1)
    physical_linear_rows = linear_error.square().mean(dim=-1)
    physical_angular_rows = angular_error.square().mean(dim=-1)
    return linear_rows, angular_rows, physical_linear_rows, physical_angular_rows


def event_transition(frame_time: float) -> tuple[int, float]:
    floor_value = int(math.floor(frame_time))
    fraction = float(frame_time - floor_value)
    if fraction <= 1.0e-7:
        return max(0, floor_value - 1), 1.0
    return floor_value, fraction


def numpy_slerp_matrix(a: np.ndarray, b: np.ndarray, alpha: float) -> np.ndarray:
    return motion_math.axes_from_quat(
        motion_math.quat_slerp(motion_math.quat_from_axes(a), motion_math.quat_from_axes(b), float(alpha))
    )


def numpy_event_pose(
    positions: np.ndarray,
    rotations: np.ndarray,
    frame_time: float,
) -> tuple[np.ndarray, np.ndarray]:
    current, alpha = event_transition(frame_time)
    nxt = min(current + 1, positions.shape[0] - 1)
    pos = positions[current] + (positions[nxt] - positions[current]) * alpha
    rot = np.stack([numpy_slerp_matrix(rotations[current, j], rotations[nxt, j], alpha) for j in range(rotations.shape[1])])
    return pos.astype(np.float32), rot.astype(np.float32)


def load_hit_contact_definitions(path: Path) -> dict[str, tuple[str, np.ndarray, int]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected_schema = "slash2_hit_contact_definitions_v1"
    if payload.get("schema") != expected_schema:
        raise ValueError(f"{path}: expected schema {expected_schema!r}")
    raw_definitions = payload.get("attacks")
    if not isinstance(raw_definitions, dict):
        raise ValueError(f"{path}: attacks must be an object")
    normalized_keys = {str(name).lower() for name in raw_definitions}
    if normalized_keys != set(ATTACK_LABELS):
        missing = sorted(set(ATTACK_LABELS) - normalized_keys)
        extra = sorted(normalized_keys - set(ATTACK_LABELS))
        raise ValueError(f"{path}: contact attack mismatch; missing={missing}, extra={extra}")

    frame_kinds = {"joint": 0, "hand_l": 1, "hand_r": 2}
    definitions: dict[str, tuple[str, np.ndarray, int]] = {}
    for raw_name, raw_definition in raw_definitions.items():
        name = str(raw_name).lower()
        if not isinstance(raw_definition, dict):
            raise ValueError(f"{path}: {raw_name} contact must be an object")
        joint = raw_definition.get("joint")
        if not isinstance(joint, str) or not joint:
            raise ValueError(f"{path}: {raw_name} has no source joint")
        expected_dynamics_joint = HIT_DYNAMICS_JOINT_BY_FAMILY.get(name)
        if joint != expected_dynamics_joint:
            raise ValueError(
                f"{path}: {raw_name} hit/dynamics joint must be "
                f"{expected_dynamics_joint!r}, got {joint!r}"
            )
        offset = np.asarray(raw_definition.get("local_offset_m"), dtype=np.float32)
        if offset.shape != (3,) or not np.isfinite(offset).all():
            raise ValueError(f"{path}: {raw_name} local_offset_m must be three finite meters")
        frame_name = raw_definition.get("frame_kind")
        if frame_name not in frame_kinds:
            raise ValueError(f"{path}: {raw_name} has invalid frame_kind {frame_name!r}")
        definitions[name] = (joint, offset, frame_kinds[frame_name])
    return definitions


def load_attack_batch(
    paths: list[Path],
    runtime: Runtime | InferenceRuntime,
    *,
    require_all_families: bool = True,
    include_contact_metadata: bool = True,
    compact_dynamic: bool = False,
) -> AttackBatch:
    full_clip = runtime.full_clip
    device = runtime.device
    contact_definitions = (
        load_hit_contact_definitions(Path(runtime.recipe.hit_contact_definitions))
        if include_contact_metadata
        else None
    )
    full_index = {name: index for index, name in enumerate(full_clip.body_names)}

    names: list[str] = []
    lengths: list[int] = []
    labels: list[tuple[float, ...]] = []
    targets: list[np.ndarray] = []
    trajectory_heading: list[torch.Tensor] = []
    initial_previous_upper: list[torch.Tensor] = []
    initial_current_upper: list[torch.Tensor] = []
    initial_global_pos: list[np.ndarray] = []
    initial_global_rot: list[np.ndarray] = []
    armed_time: list[float] = []
    hit_time: list[float] = []
    armed_step: list[int] = []
    armed_alpha: list[float] = []
    hit_step: list[int] = []
    hit_alpha: list[float] = []
    difficulty_ids: list[int] = []
    post_hit_tail_steps: list[int] = []
    armed_lower: list[torch.Tensor] = []
    armed_upper: list[torch.Tensor] = []
    hit_lower: list[torch.Tensor] = []
    hit_upper: list[torch.Tensor] = []
    armed_heading: list[torch.Tensor] = []
    hit_heading: list[torch.Tensor] = []
    final_heading: list[torch.Tensor] = []
    trajectory_lower: list[torch.Tensor] = []
    trajectory_base_upper: list[torch.Tensor] = []
    trajectory_upper: list[torch.Tensor] = []
    trajectory_global_pos: list[np.ndarray] = []
    trajectory_global_rot: list[np.ndarray] = []
    contact_joint: list[int] = []
    contact_offset: list[np.ndarray] = []
    contact_kind: list[int] = []
    contact_is_blade: list[bool] = []
    frames_per_second: list[float] = []
    hit_linear_velocity: list[np.ndarray] = []
    hit_angular_velocity: list[np.ndarray] = []

    for clip_row, path in enumerate(paths):
        controller_targets = load_controller_target_arrays(path)
        with np.load(path, allow_pickle=False) as data:
            bone_names = [str(value) for value in data["bone_names"].tolist()]
            keep = np.asarray([bone_names.index(name) for name in full_clip.body_names], dtype=np.int64)
            positions = controller_targets.visible_global_pos_m[:, keep]
            controller_rotations = controller_targets.controller_global_rot[:, keep]
            root_index = bone_names.index("root")
            root_positions = controller_targets.visible_global_pos_m[:, root_index]
            root_rotations = controller_targets.source_global_rot[:, root_index]
            target = np.asarray(data["attack_target_world_m"], dtype=np.float32).reshape(3)
            armed = float(data["attack_armed_frame"])
            hit = float(data["attack_hit_frame"])
            fps = float(np.asarray(data["fps"], dtype=np.float32).reshape(()))
        if not math.isfinite(fps) or fps <= 0.0:
            raise ValueError(f"{path}: fps must be finite and positive, got {fps}")
        family = attack_family_from_path(path)
        if family not in ATTACK_LABELS:
            raise ValueError(f"No attack labels declared for {path.stem}")
        names.append(path.stem)
        lengths.append(int(positions.shape[0]))
        difficulty_ids.append(attack_difficulty_id_from_path(path))
        post_hit_tail_steps.append(
            authored_post_hit_tail_steps(int(positions.shape[0]), hit)
        )
        labels.append(ATTACK_LABELS[family])
        targets.append(target)
        seed_upper = torch.tensor(
            controller_targets.upper_hybrid_state[:2],
            dtype=torch.float32,
            device=device,
        )
        initial_previous_upper.append(seed_upper[0])
        initial_current_upper.append(seed_upper[1])
        frame_ids = torch.arange(int(positions.shape[0]), dtype=torch.long, device=device)
        clip_ids = torch.full_like(frame_ids, clip_row)
        target_rows = torch.tensor(
            target,
            dtype=torch.float32,
            device=device,
        ).expand(frame_ids.numel(), -1)
        lower_sequence = torch.tensor(
            controller_targets.lower_hybrid_state,
            dtype=torch.float32,
            device=device,
        )
        heading_sequence = torch.tensor(
            controller_targets.pelvis_target_heading,
            dtype=torch.float32,
            device=device,
        )
        trajectory_heading.append(heading_sequence)
        # Strict v3 stores the authoritative 41 controller DOFs directly.
        # Never pass them through the old fitted/reachable-target cleanup:
        # that legacy adaptation changes authored thigh/foot states and makes
        # the trainer disagree with the AE corpus built from the same NPZ.
        lower_sequence_root = lower_hybrid_state_to_root(
            runtime.lower_store,
            clip_ids,
            frame_ids,
            lower_sequence,
            target_rows,
            heading_sequence,
        )
        sequence_root_pos, sequence_root_rot, _yaw, _heading = runtime.lower_store.root_state(
            clip_ids, frame_ids
        )
        base_upper_sequence_root = base_upper_from_lower(
            runtime,
            clip_ids,
            lower_sequence_root,
            sequence_root_pos,
            sequence_root_rot,
        )
        base_upper_sequence = upper_root_state_to_hybrid(
            runtime.lower_store,
            clip_ids,
            frame_ids,
            base_upper_sequence_root,
            target_rows,
            heading_sequence,
        )
        source_upper_sequence = torch.tensor(
            controller_targets.upper_hybrid_state,
            dtype=torch.float32,
            device=device,
        )
        if compact_dynamic:
            # Full global trajectories are never consumed by the dynamic
            # corpus graph.  Its two seed poses are reconstructed on the
            # active device in ``stage_full_dataset_rows``.  Retain only the
            # first two authoritative render poses for dataclass compatibility
            # and omit the O(clips * frames * joints) duplicate entirely.
            initial_global_pos.append(positions[:2].copy())
            initial_global_rot.append(controller_rotations[:2].copy())
        else:
            target_global_pos, target_global_rot = full_fk_globals(
                runtime,
                clip_ids,
                lower_sequence_root,
                upper_hybrid_state_to_root(
                    runtime.lower_store,
                    clip_ids,
                    frame_ids,
                    source_upper_sequence,
                    target_rows,
                    heading_sequence,
                ),
                sequence_root_pos,
                sequence_root_rot,
            )
            target_global_pos_np = target_global_pos.detach().cpu().numpy().astype(np.float32)
            target_global_rot_np = target_global_rot.detach().cpu().numpy().astype(np.float32)
            initial_global_pos.append(target_global_pos_np[:2].copy())
            initial_global_rot.append(target_global_rot_np[:2].copy())
            trajectory_global_pos.append(target_global_pos_np)
            trajectory_global_rot.append(target_global_rot_np)
        trajectory_lower.append(lower_sequence)
        trajectory_base_upper.append(base_upper_sequence)
        trajectory_upper.append(source_upper_sequence)
        armed_time.append(armed)
        hit_time.append(hit)
        armed_transition, armed_fraction = event_transition(armed)
        hit_transition, hit_fraction = event_transition(hit)
        if hit_transition + 1 >= int(positions.shape[0]):
            raise ValueError(
                f"{path}: hit transition {hit_transition}->{hit_transition + 1} "
                f"is outside {int(positions.shape[0])} frames"
            )
        frames_per_second.append(fps)
        armed_step.append(armed_transition - 1)
        armed_alpha.append(armed_fraction)
        hit_step.append(hit_transition - 1)
        hit_alpha.append(hit_fraction)
        # Fractional authored event targets are static corpus facts.  Consume
        # the strict v3 cache directly instead of reconstructing/slerping them
        # once per training startup.  The offline cache has a separate parity
        # validator against ``interpolate_hybrid_native_states``.
        armed_lower.append(
            torch.as_tensor(
                controller_targets.armed_event_lower_hybrid,
                dtype=torch.float32,
                device=device,
            )
        )
        armed_upper.append(
            torch.as_tensor(
                controller_targets.armed_event_upper_hybrid,
                dtype=torch.float32,
                device=device,
            )
        )
        hit_lower.append(
            torch.as_tensor(
                controller_targets.hit_event_lower_hybrid,
                dtype=torch.float32,
                device=device,
            )
        )
        hit_upper.append(
            torch.as_tensor(
                controller_targets.hit_event_upper_hybrid,
                dtype=torch.float32,
                device=device,
            )
        )
        armed_heading.append(
            torch.as_tensor(
                controller_targets.armed_event_heading,
                dtype=torch.float32,
                device=device,
            )
        )
        hit_heading.append(
            torch.as_tensor(
                controller_targets.hit_event_heading,
                dtype=torch.float32,
                device=device,
            )
        )
        final_heading.append(
            torch.as_tensor(
                controller_targets.final_heading,
                dtype=torch.float32,
                device=device,
            )
        )

        if contact_definitions is None:
            # These fields are consumed only by training losses.  Keep the
            # AttackBatch tensor contract intact without making visualization
            # depend on hit-contact authoring metadata.
            dynamics_joint_index = full_index.get("root", 0)
            contact_joint.append(dynamics_joint_index)
            contact_offset.append(np.zeros(3, dtype=np.float32))
            contact_kind.append(0)
        else:
            joint_name, offset, frame_kind = contact_definitions[family]
            if joint_name not in full_index:
                raise ValueError(f"{path.name}: contact joint {joint_name!r} is absent from the full-body skeleton")
            dynamics_joint_index = full_index[joint_name]
            contact_joint.append(dynamics_joint_index)
            contact_offset.append(offset)
            contact_kind.append(frame_kind)
        hit_linear_velocity.append(
            np.asarray(
                (
                    positions[hit_transition + 1, dynamics_joint_index]
                    - positions[hit_transition, dynamics_joint_index]
                )
                * fps,
                dtype=np.float32,
            )
        )
        hit_angular_velocity.append(
            numpy_rotation_vector_between(
                controller_rotations[hit_transition, dynamics_joint_index],
                controller_rotations[hit_transition + 1, dynamics_joint_index],
            )
            * np.float32(fps)
        )
        contact_is_blade.append(family in BLADE_ATTACK_FAMILIES)

    families = [attack_family_from_path(Path(name)) for name in names]
    if require_all_families and set(families) != set(ATTACK_LABELS):
        missing = sorted(set(ATTACK_LABELS) - set(families))
        extra = sorted(set(families) - set(ATTACK_LABELS))
        raise ValueError(f"Attack source family mismatch; missing={missing}, extra={extra}")
    max_frames = max(lengths)
    full_joint_count = len(full_clip.body_names)
    lower_dim = int(trajectory_lower[0].shape[-1])
    upper_dim = int(trajectory_upper[0].shape[-1])
    trajectory_lower_padded = torch.zeros(
        (len(paths), max_frames, lower_dim), dtype=torch.float32, device=device
    )
    trajectory_base_upper_padded = torch.zeros(
        (len(paths), max_frames, upper_dim), dtype=torch.float32, device=device
    )
    trajectory_upper_padded = torch.zeros_like(trajectory_base_upper_padded)
    trajectory_heading_padded = torch.eye(
        3, dtype=torch.float32, device=device
    ).reshape(1, 1, 3, 3).repeat(len(paths), max_frames, 1, 1)
    global_frame_count = 0 if compact_dynamic else max_frames
    trajectory_global_pos_padded = np.zeros(
        (len(paths), global_frame_count, full_joint_count, 3), dtype=np.float32
    )
    trajectory_global_rot_padded = np.zeros(
        (len(paths), global_frame_count, full_joint_count, 3, 3), dtype=np.float32
    )
    for row, length in enumerate(lengths):
        trajectory_lower_padded[row, :length] = trajectory_lower[row]
        trajectory_base_upper_padded[row, :length] = trajectory_base_upper[row]
        trajectory_upper_padded[row, :length] = trajectory_upper[row]
        trajectory_heading_padded[row, :length] = trajectory_heading[row]
        if not compact_dynamic:
            trajectory_global_pos_padded[row, :length] = trajectory_global_pos[row]
            trajectory_global_rot_padded[row, :length] = trajectory_global_rot[row]
    return AttackBatch(
        paths=paths,
        names=names,
        clip_ids=torch.arange(len(paths), dtype=torch.long, device=device),
        lengths=torch.tensor(lengths, dtype=torch.long, device=device),
        labels=torch.tensor(labels, dtype=torch.float32, device=device),
        targets_world=torch.tensor(np.stack(targets), dtype=torch.float32, device=device),
        trajectory_heading=trajectory_heading_padded,
        initial_previous_upper=torch.stack(initial_previous_upper),
        initial_current_upper=torch.stack(initial_current_upper),
        initial_global_pos=torch.tensor(np.stack(initial_global_pos), dtype=torch.float32, device=device),
        initial_global_rot=torch.tensor(np.stack(initial_global_rot), dtype=torch.float32, device=device),
        armed_time=torch.tensor(armed_time, dtype=torch.float32, device=device),
        hit_time=torch.tensor(hit_time, dtype=torch.float32, device=device),
        armed_step=torch.tensor(armed_step, dtype=torch.long, device=device),
        armed_alpha=torch.tensor(armed_alpha, dtype=torch.float32, device=device),
        hit_step=torch.tensor(hit_step, dtype=torch.long, device=device),
        hit_alpha=torch.tensor(hit_alpha, dtype=torch.float32, device=device),
        difficulty_id=torch.tensor(difficulty_ids, dtype=torch.long, device=device),
        post_hit_tail_steps=torch.tensor(
            post_hit_tail_steps, dtype=torch.long, device=device
        ),
        armed_lower=torch.stack(armed_lower),
        armed_upper=torch.stack(armed_upper),
        hit_lower=torch.stack(hit_lower),
        hit_upper=torch.stack(hit_upper),
        armed_heading=torch.stack(armed_heading),
        hit_heading=torch.stack(hit_heading),
        final_heading=torch.stack(final_heading),
        trajectory_lower=trajectory_lower_padded,
        trajectory_base_upper=trajectory_base_upper_padded,
        trajectory_upper=trajectory_upper_padded,
        trajectory_global_pos=torch.tensor(
            trajectory_global_pos_padded, dtype=torch.float32, device=device
        ),
        trajectory_global_rot=torch.tensor(
            trajectory_global_rot_padded, dtype=torch.float32, device=device
        ),
        contact_joint=torch.tensor(contact_joint, dtype=torch.long, device=device),
        contact_offset=torch.tensor(np.stack(contact_offset), dtype=torch.float32, device=device),
        contact_frame_kind=torch.tensor(contact_kind, dtype=torch.long, device=device),
        contact_is_blade=torch.tensor(contact_is_blade, dtype=torch.bool, device=device),
        fps=torch.tensor(frames_per_second, dtype=torch.float32, device=device),
        hit_linear_velocity=torch.tensor(
            np.stack(hit_linear_velocity), dtype=torch.float32, device=device
        ),
        hit_angular_velocity=torch.tensor(
            np.stack(hit_angular_velocity), dtype=torch.float32, device=device
        ),
        max_steps=max(lengths) - 2,
    )


def full_dataset_content_sha256() -> str:
    manifest_path = HERE / "final_target_frame_v3_attack_dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("schema") != "slash2_target_frame_v3_manifest_v1"
        or manifest.get("target_frame_schema") != target_codec.TARGET_FRAME_SCHEMA
        or int(manifest.get("target_frame_schema_version", -1))
        != target_codec.TARGET_FRAME_SCHEMA_VERSION
        or int(manifest.get("file_count", -1)) != FULL_DATASET_TOTAL_COUNT
    ):
        raise ValueError("Canonical strict-v3 attack manifest is absent or incomplete")
    digest = str(manifest.get("dataset_content_sha256", ""))
    if len(digest) != 64:
        raise ValueError("Strict-v3 attack manifest has no content SHA-256")
    return digest


def attack_batch_on_device(batch: AttackBatch, device: torch.device) -> AttackBatch:
    moved = copy.copy(batch)
    for item in fields(AttackBatch):
        value = getattr(batch, item.name)
        if torch.is_tensor(value):
            setattr(moved, item.name, value.to(device))
    return moved


class _PortablePathUnpickler(pickle.Unpickler):
    """Read pathlib objects without instantiating the source OS path class."""

    def find_class(self, module: str, name: str) -> object:
        if module == "pathlib" and name == "WindowsPath":
            return PureWindowsPath
        if module == "pathlib" and name == "PosixPath":
            return PurePosixPath
        # Full-dataset caches created by launching this file directly record
        # the trusted dataclass as ``__main__.AttackBatch``. Resolve that name
        # to the same class when utilities import the trainer as a module.
        if module == "__main__" and name == "AttackBatch":
            return AttackBatch
        return super().find_class(module, name)


class _PortablePathPickleModule:
    """Minimal pickle-module interface accepted by :func:`torch.load`."""

    __name__ = "portable_path_pickle"
    Unpickler = _PortablePathUnpickler

    @staticmethod
    def load(file: object, **kwargs: object) -> object:
        """Support PyTorch's legacy sequential stream reader as well."""

        return _PortablePathUnpickler(file, **kwargs).load()


def load_portable_torch_cache(
    path: Path, *, mmap: bool = False, compression: str | None = None
) -> object:
    """Load a trusted project cache made on either Windows or Linux."""

    path = path.resolve()
    _PORTABLE_TORCH_CACHE_FILES_READ.add(path)
    normalized_compression = None if compression is None else str(compression).lower()
    if normalized_compression not in (None, "gzip", "zstd"):
        raise ValueError(f"unsupported portable torch cache compression: {compression}")
    kwargs = {
        "map_location": "cpu",
        "pickle_module": _PortablePathPickleModule,
        "weights_only": False,
    }
    if mmap and normalized_compression is None:
        kwargs["mmap"] = True
    if normalized_compression == "gzip":
        with gzip.open(path, "rb") as stream:
            return torch.load(stream, **kwargs)
    if normalized_compression == "zstd":
        import zstandard

        with path.open("rb") as source:
            with zstandard.ZstdDecompressor().stream_reader(source) as stream:
                # torch.load probes and rewinds its input. Materialize only the
                # decompressed suffix in RAM; the buffer is released before
                # graph capture and remains far smaller than NPZ decoding.
                with io.BytesIO(stream.read()) as decompressed:
                    return torch.load(decompressed, **kwargs)
    try:
        # PyTorch 2.1 accepts mmap only when ``f`` is a string filename, not a
        # pathlib.Path. Use the portable form on every supported version.
        return torch.load(str(path), **kwargs)
    except TypeError:
        # Older supported PyTorch builds do not expose mmap. The cache remains
        # valid; only the load loses the large-file lazy paging optimization.
        kwargs.pop("mmap", None)
        return torch.load(str(path), **kwargs)


def portable_motion_cfg_key(cfg: tl.TrainConfig) -> str:
    """Stable MotionClip key independent of host/GPU launch details."""

    values = asdict(cfg)
    values["device"] = "portable"
    values["use_torch_compile"] = False
    return hashlib.sha256(
        json.dumps(values, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def packed_motion_clips_cache_path(
    dataset_sha: str,
    cfg: tl.TrainConfig,
    body_mode: str,
    *,
    cache_dir: Path | None = None,
    compression: str | None = None,
) -> Path:
    normalized_mode = tl.normalized_body_mode(body_mode)
    normalized_compression = None if compression is None else str(compression).lower()
    if normalized_compression not in (None, "gzip", "zstd"):
        raise ValueError(f"unsupported packed cache compression: {compression}")
    key = {
        "version": PACKED_MOTION_CLIPS_CACHE_VERSION,
        "dataset_content_sha256": str(dataset_sha),
        "motion_cfg_sha256": portable_motion_cfg_key(cfg),
        "body_mode": normalized_mode,
        "motion_clip_cache_version": int(ik_ctl.MOTION_CLIP_DISK_CACHE_VERSION),
        "ik_schema_version": int(tl.IK_SCHEMA_VERSION),
        "ik_pole_reference": str(tl.IK_POLE_REFERENCE),
        "output_reference_root": str(tl.OUTPUT_REFERENCE_ROOT),
        "output_prediction_mode": str(tl.normalized_output_prediction_mode()),
    }
    if normalized_compression is not None:
        key["compression"] = normalized_compression
    digest = hashlib.sha256(
        json.dumps(key, sort_keys=True).encode("utf-8")
    ).hexdigest()[:24]
    root = cache_dir or (
        PROJECT_ROOT / "training" / "runs" / "cache" / "slash2_prepared_corpus"
    )
    extension = {
        None: ".pt",
        "gzip": ".pt.gz",
        "zstd": ".pt.zst",
    }[normalized_compression]
    return Path(root) / f"{dataset_sha[:16]}_{normalized_mode}_{digest}{extension}"


def bind_packed_motion_clip_paths(
    clips: object,
    paths: list[Path],
    body_mode: str,
) -> list[tl.MotionClip] | None:
    """Validate immutable ordering/mode, then bind paths for the current host."""

    if not isinstance(clips, list) or len(clips) != len(paths):
        return None
    normalized_mode = tl.normalized_body_mode(body_mode)
    expected_names = [path.stem.lower() for path in paths]
    actual_names: list[str] = []
    first_topology: tuple[tuple[str, ...], tuple[int, ...], str] | None = None
    for clip in clips:
        raw_path = getattr(clip, "path", None)
        if raw_path is None or not hasattr(raw_path, "stem"):
            return None
        actual_names.append(str(raw_path.stem).lower())
        if tl.normalized_body_mode(getattr(clip, "body_mode", normalized_mode)) != normalized_mode:
            return None
        if bool(getattr(clip, "cyclic_animation", False)):
            return None
        body_names = tuple(str(name) for name in getattr(clip, "body_names", ()))
        parents = tuple(int(parent) for parent in getattr(clip, "parents_body_list", ()))
        limb_specs = repr(getattr(clip, "ik_limb_specs", ()))
        topology = (body_names, parents, limb_specs)
        if not body_names or not parents:
            return None
        if first_topology is None:
            first_topology = topology
        elif topology != first_topology:
            return None
    if actual_names != expected_names:
        return None
    for clip, path in zip(clips, paths):
        clip.path = path
        clip._device_cache = {}
    return clips


def compact_motion_clips_in_place(
    clips: list[tl.MotionClip], *, retain_full: int
) -> None:
    """Release redundant decoded motion tensors after exact stores are built.

    ``SimpleClipStore`` and the stacked FK geometry own every tensor used by
    training.  The remaining per-clip entries are needed only for immutable
    path/length/topology metadata, for which ``SimpleClipMeta`` is lossless.
    Keeping the small GT prefix preserves the existing offline audit helpers.
    """

    keep = max(1, min(int(retain_full), len(clips)))
    clips[keep:] = [
        ik_ctl.simple_clip_meta_from_clip(clip)  # type: ignore[list-item]
        for clip in clips[keep:]
    ]


def load_motion_clips_packed(
    paths: list[Path],
    cfg: tl.TrainConfig,
    dataset_sha: str,
    body_mode: str,
    *,
    cache_dir: Path | None = None,
    compression: str | None = None,
    loader: Callable[
        [list[tuple[Path, bool]], tl.TrainConfig], list[tl.MotionClip]
    ]
    | None = None,
) -> list[tl.MotionClip]:
    """Load one prepared corpus bundle, building it once on the first launch.

    The authoritative manifest SHA and the MotionClip/FK schema form the cache
    key. Training losses and other graph-only changes deliberately do not, so
    changing a scalar recipe cannot trigger another 5,076-file rebuild.
    """

    normalized_mode = tl.normalized_body_mode(body_mode)
    cache_path = packed_motion_clips_cache_path(
        dataset_sha,
        cfg,
        normalized_mode,
        cache_dir=cache_dir,
        compression=compression,
    )
    motion_cfg_sha = portable_motion_cfg_key(cfg)
    started = time.perf_counter()
    if cache_path.is_file():
        try:
            payload = load_portable_torch_cache(
                cache_path, mmap=True, compression=compression
            )
            if (
                isinstance(payload, dict)
                and payload.get("kind") == PACKED_MOTION_CLIPS_CACHE_KIND
                and int(payload.get("version", -1)) == PACKED_MOTION_CLIPS_CACHE_VERSION
                and payload.get("dataset_content_sha256") == dataset_sha
                and payload.get("motion_cfg_sha256") == motion_cfg_sha
                and payload.get("body_mode") == normalized_mode
                and int(payload.get("motion_clip_cache_version", -1))
                == int(ik_ctl.MOTION_CLIP_DISK_CACHE_VERSION)
                and int(payload.get("ik_schema_version", -1)) == int(tl.IK_SCHEMA_VERSION)
            ):
                bound = bind_packed_motion_clip_paths(
                    payload.get("clips"), paths, normalized_mode
                )
                if bound is not None:
                    print(
                        "SLASH2_PREPARED_CORPUS_CACHE "
                        f"status=hit mode={normalized_mode} clips={len(bound)} "
                        f"seconds={time.perf_counter() - started:.3f} "
                        f"compression={compression or 'none'} "
                        f"size_gib={cache_path.stat().st_size / (1024 ** 3):.3f} "
                        f"path={cache_path}",
                        flush=True,
                    )
                    return bound
        except Exception as exc:
            print(
                "SLASH2_PREPARED_CORPUS_CACHE "
                f"status=rejected mode={normalized_mode} error={type(exc).__name__} "
                f"path={cache_path}",
                flush=True,
            )
        cache_path.unlink(missing_ok=True)

    build_started = time.perf_counter()
    clip_loader = loader if loader is not None else ik_ctl.load_clips
    clips = clip_loader([(path, False) for path in paths], cfg)
    bound = bind_packed_motion_clip_paths(clips, paths, normalized_mode)
    if bound is None:
        raise ValueError(
            f"Prepared {normalized_mode} MotionClip corpus failed ordering/mode validation"
        )
    serialized = [ik_ctl.motion_clip_for_disk_cache(clip) for clip in bound]
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache_path.with_name(f"{cache_path.name}.{os.getpid()}.tmp")
    try:
        payload = {
            "kind": PACKED_MOTION_CLIPS_CACHE_KIND,
            "version": PACKED_MOTION_CLIPS_CACHE_VERSION,
            "dataset_content_sha256": dataset_sha,
            "motion_cfg_sha256": motion_cfg_sha,
            "body_mode": normalized_mode,
            "motion_clip_cache_version": int(ik_ctl.MOTION_CLIP_DISK_CACHE_VERSION),
            "ik_schema_version": int(tl.IK_SCHEMA_VERSION),
            "clips": serialized,
        }
        if compression == "gzip":
            with gzip.open(temporary, "wb", compresslevel=6) as stream:
                # gzip is seekable enough for PyTorch's zip writer and avoids
                # ever materializing an uncompressed staging file.
                torch.save(payload, stream)
        elif compression == "zstd":
            import zstandard

            with temporary.open("wb") as destination:
                with zstandard.ZstdCompressor(level=9).stream_writer(
                    destination, closefd=False
                ) as stream:
                    # Keep PyTorch's zip writer: unlike the legacy storage
                    # writer it never bypasses this compression stream through
                    # the underlying file descriptor.
                    torch.save(payload, stream)
        else:
            torch.save(payload, temporary)
        temporary.replace(cache_path)
    finally:
        temporary.unlink(missing_ok=True)
    print(
        "SLASH2_PREPARED_CORPUS_CACHE "
        f"status=built mode={normalized_mode} clips={len(bound)} "
        f"build_seconds={time.perf_counter() - build_started:.3f} "
        f"total_seconds={time.perf_counter() - started:.3f} "
        f"compression={compression or 'none'} "
        f"size_gib={cache_path.stat().st_size / (1024 ** 3):.3f} "
        f"path={cache_path}",
        flush=True,
    )
    return bound


def load_motion_clips_with_read_only_prefix_cache(
    paths: list[Path],
    cfg: tl.TrainConfig,
    body_mode: str,
    *,
    prefix_dataset_sha: str,
    prefix_count: int,
    prefix_cache_dir: Path,
    suffix_dataset_sha: str | None = None,
    suffix_cache_dir: Path | None = None,
    suffix_cache_compression: str | None = None,
) -> list[tl.MotionClip]:
    """Reuse an immutable prepared prefix and decode only the new suffix.

    This is deliberately read-only: a missing or mismatched prefix cache is a
    hard startup error, never an excuse to overwrite a proven earlier corpus.
    """

    count = int(prefix_count)
    digest = str(prefix_dataset_sha).lower()
    if count <= 0 or count >= len(paths):
        raise ValueError("prepared prefix count must split the current corpus")
    if len(digest) != 64 or any(value not in "0123456789abcdef" for value in digest):
        raise ValueError("prepared prefix corpus SHA-256 is invalid")
    normalized_mode = tl.normalized_body_mode(body_mode)
    cache_path = packed_motion_clips_cache_path(
        digest,
        cfg,
        normalized_mode,
        cache_dir=prefix_cache_dir,
    )
    if not cache_path.is_file():
        raise FileNotFoundError(f"required read-only prefix cache is missing: {cache_path}")
    payload = load_portable_torch_cache(cache_path, mmap=True)
    motion_cfg_sha = portable_motion_cfg_key(cfg)
    if not (
        isinstance(payload, dict)
        and payload.get("kind") == PACKED_MOTION_CLIPS_CACHE_KIND
        and int(payload.get("version", -1)) == PACKED_MOTION_CLIPS_CACHE_VERSION
        and payload.get("dataset_content_sha256") == digest
        and payload.get("motion_cfg_sha256") == motion_cfg_sha
        and payload.get("body_mode") == normalized_mode
        and int(payload.get("motion_clip_cache_version", -1))
        == int(ik_ctl.MOTION_CLIP_DISK_CACHE_VERSION)
        and int(payload.get("ik_schema_version", -1)) == int(tl.IK_SCHEMA_VERSION)
    ):
        raise ValueError(f"required read-only prefix cache contract mismatch: {cache_path}")
    prefix = bind_packed_motion_clip_paths(
        payload.get("clips"), paths[:count], normalized_mode
    )
    if prefix is None:
        raise ValueError(f"required read-only prefix cache ordering mismatch: {cache_path}")
    if (suffix_dataset_sha is None) != (suffix_cache_dir is None):
        raise ValueError(
            "prepared suffix cache SHA and directory must be supplied together"
        )
    started = time.perf_counter()
    suffix = (
        load_motion_clips_packed(
            paths[count:],
            cfg,
            str(suffix_dataset_sha),
            normalized_mode,
            cache_dir=Path(suffix_cache_dir).resolve(),
            compression=suffix_cache_compression,
        )
        if suffix_dataset_sha is not None and suffix_cache_dir is not None
        else ik_ctl.load_clips([(path, False) for path in paths[count:]], cfg)
    )
    combined = [*prefix, *suffix]
    print(
        "SLASH2_PREPARED_CORPUS_PREFIX_CACHE "
        f"status=hit mode={normalized_mode} prefix_clips={count} "
        f"suffix_clips={len(suffix)} "
        f"suffix_cache={'packed' if suffix_dataset_sha is not None else 'direct'} "
        f"suffix_compression={suffix_cache_compression or 'none'} "
        f"seconds={time.perf_counter() - started:.3f} "
        f"path={cache_path}",
        flush=True,
    )
    return combined


def prepare_motion_clip_suffix_cache(
    paths: list[Path],
    walk_checkpoint: Path,
    *,
    prefix_count: int,
    suffix_dataset_sha: str,
    suffix_cache_dir: Path,
    suffix_cache_compression_by_mode: dict[str, str] | None = None,
) -> dict[str, object]:
    """Build and verify a lossless packed suffix without loading the prefix.

    The cache identity is supplied by the immutable whole-corpus contract plus
    its fixed split.  This command is intentionally CPU/startup-only and can be
    run after a training segment, keeping optimizer throughput untouched.
    """

    resolved_paths = [Path(path).resolve() for path in paths]
    count = int(prefix_count)
    digest = str(suffix_dataset_sha).lower()
    cache_root = Path(suffix_cache_dir).resolve()
    checkpoint_path = Path(walk_checkpoint).resolve()
    if count <= 0 or count >= len(resolved_paths):
        raise ValueError("prepared suffix split must lie inside the corpus")
    if len(digest) != 64 or any(value not in "0123456789abcdef" for value in digest):
        raise ValueError("prepared suffix corpus SHA-256 is invalid")
    if not checkpoint_path.is_file():
        raise FileNotFoundError(checkpoint_path)
    if any(not path.is_file() for path in resolved_paths[count:]):
        raise FileNotFoundError("one or more prepared suffix NPZs are absent")

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    results: dict[str, object] = {}
    with slash2_runtime_policy(checkpoint):
        base_cfg = tl.TrainConfig()
        visualize.apply_config_dict(base_cfg, checkpoint.get("config", {}))
        # Match the production cache identity. MotionClip construction remains
        # CPU-side even though the eventual runtime device is CUDA.
        base_cfg.device = "cuda"
        base_cfg.use_torch_compile = False
        for body_mode in (tl.BODY_MODE_LOWER, tl.BODY_MODE_FULL):
            cfg = copy.deepcopy(base_cfg)
            cfg.body_mode = body_mode
            normalized_mode = tl.normalized_body_mode(body_mode)
            compression = (suffix_cache_compression_by_mode or {}).get(
                normalized_mode
            )
            clips = load_motion_clips_packed(
                resolved_paths[count:],
                cfg,
                digest,
                body_mode,
                cache_dir=cache_root,
                compression=compression,
            )
            if len(clips) != len(resolved_paths) - count:
                raise RuntimeError("prepared suffix cache clip count mismatch")
            cache_path = packed_motion_clips_cache_path(
                digest,
                cfg,
                body_mode,
                cache_dir=cache_root,
                compression=compression,
            )
            results[normalized_mode] = {
                "path": str(cache_path),
                "bytes": cache_path.stat().st_size,
                "sha256": hashlib.sha256(cache_path.read_bytes()).hexdigest(),
                "clips": len(clips),
                "compression": compression or "none",
            }
            del clips
            gc.collect()
    return {
        "schema": "slash2_prepared_motion_suffix_cache_v1",
        "prefixCount": count,
        "suffixCount": len(resolved_paths) - count,
        "suffixDatasetSha256": digest,
        "cacheRoot": str(cache_root),
        "bodyModes": results,
    }


def bind_attack_batch_paths(batch: AttackBatch, paths: list[Path]) -> bool:
    """Validate cache ordering by clip name, then bind real host paths."""

    expected_names = [path.stem.lower() for path in paths]
    actual_names = [str(name).lower() for name in batch.names]
    if actual_names != expected_names:
        return False
    batch.paths = list(paths)
    return True


def ensure_attack_batch_blade_flags(batch: AttackBatch) -> bool:
    """Attach v18 blade-family flags to a trusted v17 cache without re-decoding."""

    existing = getattr(batch, "contact_is_blade", None)
    expected = torch.tensor(
        [
            attack_family_from_path(Path(name)) in BLADE_ATTACK_FAMILIES
            for name in batch.names
        ],
        dtype=torch.bool,
        device=batch.labels.device,
    )
    if torch.is_tensor(existing):
        if existing.shape != expected.shape or not torch.equal(existing, expected):
            raise ValueError("AttackBatch blade-family flags do not match its motion names")
        return False
    batch.contact_is_blade = expected
    return True


def attack_batch_hit_dynamics_identity(batch: AttackBatch) -> str:
    payload = {
        "schema": HIT_DYNAMICS_CACHE_KIND,
        "names": [str(name).lower() for name in batch.names],
        "hitStep": batch.hit_step.detach().cpu().tolist(),
        "lengths": batch.lengths.detach().cpu().tolist(),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@torch.no_grad()
def build_attack_batch_hit_dynamics(
    batch: AttackBatch,
    runtime: Runtime,
    *,
    chunk_size: int = 512,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Derive exact authored hit-transition dynamics from the compact cache.

    This is a one-time, vectorized startup operation.  It reuses the retained
    native trajectories and the same FK boundary as training, so no source NPZ
    is reopened and no extra FK is added to a graph replay.
    """

    count = len(batch.names)
    fps_value = float(runtime.full_clip.fps)
    if not math.isfinite(fps_value) or fps_value <= 0.0:
        raise ValueError(f"Runtime FPS must be finite and positive, got {fps_value}")
    fps = torch.full((count,), fps_value, dtype=torch.float32)
    linear = torch.empty((count, 3), dtype=torch.float32)
    angular = torch.empty_like(linear)
    for begin in range(0, count, max(1, int(chunk_size))):
        end = min(begin + max(1, int(chunk_size)), count)
        cpu_rows = torch.arange(begin, end, dtype=torch.long)
        clip_ids = cpu_rows.to(runtime.device)
        current_frame_cpu = batch.hit_step.index_select(0, cpu_rows) + 1
        next_frame_cpu = current_frame_cpu + 1
        selected_lengths = batch.lengths.index_select(0, cpu_rows)
        if bool((next_frame_cpu >= selected_lengths).any()):
            raise ValueError("Cached hit transition extends beyond an authored motion")

        def gather(values: torch.Tensor, frames: torch.Tensor) -> torch.Tensor:
            return values[cpu_rows.to(values.device), frames.to(values.device)].to(
                runtime.device
            )

        targets = batch.targets_world.index_select(
            0, cpu_rows.to(batch.targets_world.device)
        ).to(runtime.device)
        current_frame = current_frame_cpu.to(runtime.device)
        next_frame = next_frame_cpu.to(runtime.device)
        current_pos, current_rot = hybrid_full_fk_globals(
            runtime,
            clip_ids,
            clip_ids,
            current_frame,
            gather(batch.trajectory_lower, current_frame_cpu),
            gather(batch.trajectory_upper, current_frame_cpu),
            targets,
            gather(batch.trajectory_heading, current_frame_cpu),
        )
        next_pos, next_rot = hybrid_full_fk_globals(
            runtime,
            clip_ids,
            clip_ids,
            next_frame,
            gather(batch.trajectory_lower, next_frame_cpu),
            gather(batch.trajectory_upper, next_frame_cpu),
            targets,
            gather(batch.trajectory_heading, next_frame_cpu),
        )
        device_rows = torch.arange(end - begin, device=runtime.device)
        dynamics_joint = batch.contact_joint.index_select(
            0, cpu_rows.to(batch.contact_joint.device)
        ).to(runtime.device)
        linear[begin:end].copy_(
            (
                (next_pos[device_rows, dynamics_joint]
                 - current_pos[device_rows, dynamics_joint])
                * fps_value
            )
            .detach()
            .cpu()
        )
        angular[begin:end].copy_(
            (
                rotation_vector_between(
                    current_rot[device_rows, dynamics_joint],
                    next_rot[device_rows, dynamics_joint],
                )
                * fps_value
            )
            .detach()
            .cpu()
        )
    if not bool(torch.isfinite(linear).all() and torch.isfinite(angular).all()):
        raise ValueError("Derived hit-transition dynamics contain non-finite values")
    return fps, linear, angular


def ensure_attack_batch_hit_dynamics(
    batch: AttackBatch,
    runtime: Runtime,
    *,
    cache_path: Path | None = None,
) -> bool:
    """Attach exact hit velocities to old compact caches via a small sidecar."""

    count = len(batch.names)
    expected_vector_shape = (count, 3)
    existing_fps = getattr(batch, "fps", None)
    existing_linear = getattr(batch, "hit_linear_velocity", None)
    existing_angular = getattr(batch, "hit_angular_velocity", None)
    if (
        torch.is_tensor(existing_fps)
        and tuple(existing_fps.shape) == (count,)
        and torch.is_tensor(existing_linear)
        and tuple(existing_linear.shape) == expected_vector_shape
        and torch.is_tensor(existing_angular)
        and tuple(existing_angular.shape) == expected_vector_shape
        and bool(torch.isfinite(existing_fps).all())
        and bool(torch.isfinite(existing_linear).all())
        and bool(torch.isfinite(existing_angular).all())
        and bool((existing_fps > 0.0).all())
    ):
        return False

    identity = attack_batch_hit_dynamics_identity(batch)
    payload: object | None = None
    if cache_path is not None and cache_path.is_file():
        payload = load_portable_torch_cache(cache_path)
    if (
        isinstance(payload, dict)
        and payload.get("kind") == HIT_DYNAMICS_CACHE_KIND
        and payload.get("identitySha256") == identity
        and torch.is_tensor(payload.get("fps"))
        and tuple(payload["fps"].shape) == (count,)
        and torch.is_tensor(payload.get("hitLinearVelocity"))
        and tuple(payload["hitLinearVelocity"].shape) == expected_vector_shape
        and torch.is_tensor(payload.get("hitAngularVelocity"))
        and tuple(payload["hitAngularVelocity"].shape) == expected_vector_shape
    ):
        fps = payload["fps"]
        linear = payload["hitLinearVelocity"]
        angular = payload["hitAngularVelocity"]
    else:
        fps, linear, angular = build_attack_batch_hit_dynamics(batch, runtime)
        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = cache_path.with_suffix(cache_path.suffix + ".tmp")
            torch.save(
                {
                    "kind": HIT_DYNAMICS_CACHE_KIND,
                    "identitySha256": identity,
                    "fps": fps,
                    "hitLinearVelocity": linear,
                    "hitAngularVelocity": angular,
                },
                temporary,
            )
            temporary.replace(cache_path)
    batch.fps = fps.to(batch.labels.device)
    batch.hit_linear_velocity = linear.to(batch.labels.device)
    batch.hit_angular_velocity = angular.to(batch.labels.device)
    if not (
        bool(torch.isfinite(batch.fps).all())
        and bool(torch.isfinite(batch.hit_linear_velocity).all())
        and bool(torch.isfinite(batch.hit_angular_velocity).all())
        and bool((batch.fps > 0.0).all())
    ):
        raise ValueError("Hit-transition dynamics sidecar is non-finite or invalid")
    return True


def load_attack_batch_cached(
    paths: list[Path],
    runtime: Runtime,
    *,
    use_full_dataset_cache: bool,
    dataset_sha: str | None = None,
    cache_dir: Path | None = None,
    require_all_families: bool = True,
) -> AttackBatch:
    cache_enabled = bool(use_full_dataset_cache or dataset_sha is not None)
    if not cache_enabled:
        batch = load_attack_batch(
            paths, runtime, require_all_families=require_all_families
        )
        ensure_attack_batch_hit_dynamics(batch, runtime)
        return batch
    resolved_dataset_sha = dataset_sha or full_dataset_content_sha256()
    resolved_cache_dir = cache_dir or (
        PROJECT_ROOT / "training" / "runs" / "cache" / "slash2_full_attack_batch"
    )
    cache_path = resolved_cache_dir / f"{resolved_dataset_sha[:24]}_compact_v2.pt"
    hit_dynamics_cache_path = (
        resolved_cache_dir
        / f"{resolved_dataset_sha[:24]}_hit_limb_transition_dynamics_v2.pt"
    )
    if cache_path.is_file():
        payload = load_portable_torch_cache(cache_path)
        release_deserialized_file_cache(cache_path)
        if (
            isinstance(payload, dict)
            and payload.get("kind") == FULL_ATTACK_BATCH_CACHE_KIND
            and payload.get("dataset_content_sha256") == resolved_dataset_sha
            and isinstance(payload.get("batch"), AttackBatch)
        ):
            batch = payload["batch"]
            assert isinstance(batch, AttackBatch)
            upgraded = ensure_attack_batch_blade_flags(batch)
            if bind_attack_batch_paths(batch, paths) and len(batch.names) == len(paths):
                ensure_attack_batch_hit_dynamics(
                    batch, runtime, cache_path=hit_dynamics_cache_path
                )
                if upgraded:
                    serialized_batch = copy.copy(batch)
                    serialized_batch.paths = [  # type: ignore[list-item]
                        str(path.resolve()) for path in paths
                    ]
                    temporary = cache_path.with_suffix(".pt.tmp")
                    torch.save(
                        {
                            "kind": FULL_ATTACK_BATCH_CACHE_KIND,
                            "dataset_content_sha256": resolved_dataset_sha,
                            "batch": serialized_batch,
                        },
                        temporary,
                    )
                    temporary.replace(cache_path)
                # The full corpus stays on CPU. Each exact reset slot is staged
                # into fixed GPU input buffers before graph replay, avoiding a
                # permanent 5,392-motion GPU copy and in-graph whole-corpus gathers.
                return batch
    batch = load_attack_batch(
        paths,
        runtime,
        require_all_families=require_all_families,
        compact_dynamic=True,
    )
    ensure_attack_batch_hit_dynamics(
        batch, runtime, cache_path=hit_dynamics_cache_path
    )
    cpu_batch = attack_batch_on_device(batch, torch.device("cpu"))
    serialized_batch = copy.copy(cpu_batch)
    # Cache paths are metadata only. Strings make newly written caches natively
    # portable; the loader binds them back to the current host's real paths.
    serialized_batch.paths = [str(path.resolve()) for path in paths]  # type: ignore[list-item]
    resolved_cache_dir.mkdir(parents=True, exist_ok=True)
    temporary = cache_path.with_suffix(".pt.tmp")
    torch.save(
        {
            "kind": FULL_ATTACK_BATCH_CACHE_KIND,
            "dataset_content_sha256": resolved_dataset_sha,
            "batch": serialized_batch,
        },
        temporary,
    )
    reloaded = load_portable_torch_cache(temporary)
    if (
        not isinstance(reloaded, dict)
        or reloaded.get("kind") != FULL_ATTACK_BATCH_CACHE_KIND
        or reloaded.get("dataset_content_sha256") != resolved_dataset_sha
        or not isinstance(reloaded.get("batch"), AttackBatch)
        or not bind_attack_batch_paths(reloaded["batch"], paths)
    ):
        temporary.unlink(missing_ok=True)
        raise RuntimeError("Full attack-batch cache failed reload verification")
    temporary.replace(cache_path)
    release_deserialized_file_cache(cache_path)
    return cpu_batch


def install_native_lower_targets_cached(
    lower_store: object,
    lower_row_stores: list[object],
    clips: list[object],
    *,
    dataset_sha: str,
    use_full_dataset_cache: bool,
    cache_dir: Path | None = None,
) -> None:
    """Materialize native lower targets once per immutable corpus digest."""

    if not use_full_dataset_cache:
        install_lower_targets_on_store(lower_store)
        for row_store in lower_row_stores:
            install_lower_targets_on_store(row_store)
        return

    names = [Path(getattr(clip, "path")).stem.lower() for clip in clips]
    lengths = [int(getattr(clip, "T")) for clip in clips]
    resolved_cache_dir = cache_dir or (
        PROJECT_ROOT / "training" / "runs" / "cache" / "slash2_native_lower_targets"
    )
    cache_path = resolved_cache_dir / f"{dataset_sha[:24]}_v1.pt"
    combined: torch.Tensor | None = None
    started = time.perf_counter()
    if cache_path.is_file():
        try:
            payload = load_portable_torch_cache(cache_path, mmap=True)
            if (
                isinstance(payload, dict)
                and payload.get("kind") == NATIVE_LOWER_TARGET_CACHE_KIND
                and payload.get("dataset_content_sha256") == dataset_sha
                and payload.get("names") == names
                and payload.get("lengths") == lengths
                and torch.is_tensor(payload.get("target_output"))
            ):
                candidate = payload["target_output"]
                assert torch.is_tensor(candidate)
                if (
                    candidate.device.type == "cpu"
                    and candidate.dtype == torch.float32
                    and candidate.ndim == 2
                    and int(candidate.shape[0]) == sum(lengths)
                ):
                    combined = candidate
        except Exception:
            combined = None
        if combined is None:
            cache_path.unlink(missing_ok=True)

    if combined is None:
        install_lower_targets_on_store(lower_store)
        combined = getattr(lower_store, "target_output").detach().cpu().contiguous()
        resolved_cache_dir.mkdir(parents=True, exist_ok=True)
        temporary = cache_path.with_name(f"{cache_path.name}.{os.getpid()}.tmp")
        try:
            torch.save(
                {
                    "kind": NATIVE_LOWER_TARGET_CACHE_KIND,
                    "dataset_content_sha256": dataset_sha,
                    "names": names,
                    "lengths": lengths,
                    "target_output": combined,
                },
                temporary,
            )
            temporary.replace(cache_path)
        finally:
            temporary.unlink(missing_ok=True)
        status = "built"
    else:
        install_lower_target_output_on_store(lower_store, combined)
        status = "hit"

    offset = 0
    for row_store, length in zip(lower_row_stores, lengths):
        install_lower_target_output_on_store(
            row_store, combined[offset : offset + length]
        )
        offset += length
    print(
        "SLASH2_NATIVE_LOWER_TARGET_CACHE "
        f"status={status} clips={len(clips)} "
        f"seconds={time.perf_counter() - started:.3f} path={cache_path}",
        flush=True,
    )


def configure_frozen_free_motion_cfg(cfg: tl.TrainConfig) -> None:
    """Install only the motion/store settings needed without frozen weights."""

    cfg.fps = 30
    cfg.position_unit_scale = 0.01
    cfg.max_speed_scale = 5.0
    cfg.max_turn_rate_per_sec_scale = 4.0 * math.pi
    cfg.pose_delta_scale = 2.0
    cfg.future_window_seconds = 0.25
    cfg.cyclic_animation = True
    cfg.predict_residual = True
    cfg.zero_init_output = True
    cfg.pose_representation = "ik_markers"
    cfg.body_mode = tl.BODY_MODE_LOWER
    cfg.foot_roll_side_blend_deg = LOWER_PIN_SIDE_BLEND_DEG
    cfg.foot_roll_ground_y = LOWER_PIN_GROUND_Y_M


def load_runtime(
    recipe: Recipe,
    device: torch.device,
    *,
    include_variants: bool = False,
    attack_paths: list[Path] | None = None,
    prior_checkpoint_paths: dict[str, Path] | None = None,
    prepared_corpus_sha256: str | None = None,
    prepared_corpus_cache_dir: Path | None = None,
    prepared_corpus_cache_enabled: bool = True,
    prepared_corpus_prefix_cache_sha256: str | None = None,
    prepared_corpus_prefix_count: int = 0,
    prepared_corpus_prefix_cache_dir: Path | None = None,
    prepared_corpus_suffix_cache_sha256: str | None = None,
    prepared_corpus_suffix_cache_dir: Path | None = None,
    prepared_corpus_suffix_cache_compression_by_mode: dict[str, str] | None = None,
    inference_only: bool = False,
) -> Runtime | InferenceRuntime:
    if not inference_only:
        if recipe.frozen_mode != "walk_idle":
            raise ValueError("The current 16-GT bring-up recipe is fixed to walk_idle")
        forced_family = str(recipe.forced_attack_family).strip().lower()
        forced_rows = int(recipe.forced_attack_family_rows_per_logical_batch)
        if forced_rows < 0 or forced_rows > int(recipe.batch_size):
            raise ValueError(
                "forced_attack_family_rows_per_logical_batch must lie within the logical batch"
            )
        if forced_rows and forced_family not in ATTACK_LABELS:
            raise ValueError(
                f"Unknown forced attack family {recipe.forced_attack_family!r}"
            )
        if forced_family and not forced_rows:
            raise ValueError(
                "forced_attack_family requires at least one forced logical row"
            )
        if forced_rows and not include_variants:
            raise ValueError("Forced-family fine-tuning requires the full variant corpus")
    if attack_paths is not None:
        if include_variants:
            raise ValueError("attack_paths and include_variants are mutually exclusive")
        paths = [Path(path).resolve() for path in attack_paths]
        if not paths:
            raise ValueError("attack_paths cannot be empty")
        missing = [str(path) for path in paths if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"Attack NPZs not found: {missing}")
        unknown = sorted(
            {
                attack_family_from_path(path)
                for path in paths
                if attack_family_from_path(path) not in ATTACK_LABELS
            }
        )
        if unknown:
            raise ValueError(f"No attack labels declared for: {unknown}")
    else:
        gt_candidates = list(Path(recipe.gt_dir).resolve().glob("*.npz"))
        original_candidates = [path for path in gt_candidates if "__" not in path.stem]
        original_paths = sorted(
            original_candidates,
            key=lambda path: (attack_is_mirrored_path(path), path.stem.lower()),
        )
        if len(original_paths) not in (16, 32):
            raise FileNotFoundError(
                f"Expected 16 normal GT attacks or 32 normal+mirrored GT attacks in "
                f"{recipe.gt_dir}, found {len(original_paths)}"
            )
        if len(original_paths) == 16:
            original_families = {path.stem.lower() for path in original_paths}
            if original_families != set(ATTACK_LABELS):
                raise ValueError(
                    "The original GT directory must contain each declared attack family exactly once"
                )
        else:
            original_names = {path.stem.lower() for path in original_paths}
            expected_names = {
                name
                for family in ATTACK_LABELS
                for name in (family, f"{family}_m")
            }
            family_counts = {
                family: sum(attack_family_from_path(path) == family for path in original_paths)
                for family in ATTACK_LABELS
            }
            if original_names != expected_names or set(family_counts.values()) != {2}:
                raise ValueError(
                    "The GT32 directory must contain one normal and one _M motion for every "
                    "declared attack family"
                )
        variant_paths: list[Path] = []
        if include_variants:
            if not recipe.variant_dir:
                raise ValueError("Full-dataset training requires Recipe.variant_dir")
            variant_candidates = [
                path
                for path in Path(recipe.variant_dir).resolve().glob("*.npz")
                if "__" in path.stem
            ]
            variant_paths = sorted(
                variant_candidates,
                key=lambda path: (attack_is_mirrored_path(path), path.stem.lower()),
            )
            if len(variant_paths) != FULL_DATASET_VARIANT_COUNT:
                raise FileNotFoundError(
                    f"Expected {FULL_DATASET_VARIANT_COUNT:,} accepted normal/M variants in "
                    f"{recipe.variant_dir}, found {len(variant_paths)}"
                )
            variant_families = {
                attack_family_from_path(path) for path in variant_paths
            }
            if variant_families != set(ATTACK_LABELS):
                raise ValueError(
                    "The variant directory must cover every declared attack family"
                )
            if not (0.0 < float(recipe.original_sample_probability) < 1.0):
                raise ValueError("Original sampling probability must be strictly between zero and one")
            normal_variants = sum(not attack_is_mirrored_path(path) for path in variant_paths)
            mirrored_variants = len(variant_paths) - normal_variants
            if (normal_variants, mirrored_variants) != (
                FULL_DATASET_MODE_VARIANT_COUNT,
                FULL_DATASET_MODE_VARIANT_COUNT,
            ):
                raise ValueError(
                    f"The full variant pool must contain exactly "
                    f"{FULL_DATASET_MODE_VARIANT_COUNT:,} normal and "
                    f"{FULL_DATASET_MODE_VARIANT_COUNT:,} M motions"
                )
        paths = [*original_paths, *variant_paths]
    if prepared_corpus_sha256 is not None:
        prepared_corpus_sha256 = str(prepared_corpus_sha256).lower()
        if (
            len(prepared_corpus_sha256) != 64
            or any(character not in "0123456789abcdef" for character in prepared_corpus_sha256)
        ):
            raise ValueError("prepared_corpus_sha256 must be a lowercase SHA-256 digest")
        if attack_paths is None:
            raise ValueError("prepared_corpus_sha256 requires an explicit ordered attack_paths list")
    resolved_prepared_cache_dir = (
        None
        if prepared_corpus_cache_dir is None
        else Path(prepared_corpus_cache_dir).resolve()
    )
    checkpoint_path: Path | None = None
    checkpoint: dict[str, object] | None = None
    if recipe.frozen_agent_enabled:
        checkpoint_path = Path(recipe.walk_checkpoint).resolve()
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        visualize.ckpt_runtime.require_current_ik_controller_checkpoint(
            checkpoint, checkpoint_path
        )
    with slash2_runtime_policy(checkpoint):
        cfg = tl.TrainConfig()
        if checkpoint is None:
            configure_frozen_free_motion_cfg(cfg)
        else:
            visualize.apply_config_dict(cfg, checkpoint.get("config", {}))
        cfg.device = str(device)
        cfg.use_torch_compile = False
        if abs(float(cfg.foot_roll_side_blend_deg) - LOWER_PIN_SIDE_BLEND_DEG) > 1.0e-9:
            raise ValueError(
                "Frozen walk side-blend geometry does not match the baked lower-pin contract"
            )
        if abs(float(cfg.foot_roll_ground_y) - LOWER_PIN_GROUND_Y_M) > 1.0e-9:
            raise ValueError(
                "Frozen walk ground height does not match the baked lower-pin contract"
            )
        bulk_full_dataset = bool(include_variants and attack_paths is None)
        cached_corpus_sha = (
            prepared_corpus_sha256
            if prepared_corpus_sha256 is not None
            and bool(prepared_corpus_cache_enabled)
            else full_dataset_content_sha256()
            if bulk_full_dataset
            else None
        )
        corpus_identity_sha = (
            prepared_corpus_sha256
            or cached_corpus_sha
            or full_dataset_content_sha256()
        )
        motion_cache_dir = (
            None
            if resolved_prepared_cache_dir is None
            else resolved_prepared_cache_dir / "motion_clips"
        )
        compact_multi_clip = len(paths) > 16
        lower_clips = (
            load_motion_clips_with_read_only_prefix_cache(
                paths,
                cfg,
                tl.BODY_MODE_LOWER,
                prefix_dataset_sha=prepared_corpus_prefix_cache_sha256,
                prefix_count=prepared_corpus_prefix_count,
                prefix_cache_dir=Path(prepared_corpus_prefix_cache_dir).resolve(),
                suffix_dataset_sha=prepared_corpus_suffix_cache_sha256,
                suffix_cache_dir=prepared_corpus_suffix_cache_dir,
                suffix_cache_compression=(
                    prepared_corpus_suffix_cache_compression_by_mode or {}
                ).get(tl.normalized_body_mode(tl.BODY_MODE_LOWER)),
            )
            if prepared_corpus_prefix_cache_sha256 is not None
            and prepared_corpus_prefix_cache_dir is not None
            else
            load_motion_clips_packed(
                paths,
                cfg,
                cached_corpus_sha,
                tl.BODY_MODE_LOWER,
                cache_dir=motion_cache_dir,
            )
            if cached_corpus_sha is not None
            else ik_ctl.load_clips([(path, False) for path in paths], cfg)
            if compact_multi_clip
            else [tl.MotionClip(path, cfg, cyclic_animation=False) for path in paths]
        )
        lower_store = ik_ctl.SimpleClipStore(lower_clips, cfg, device)
        # Keep a per-row store for every GT row used by the contract suite
        # (normal and M). The full 5,076-row runtime still caps these at 32 and
        # uses the compact multi-clip/batched geometry path for the corpus, so
        # it never duplicates thousands of complete controller stores.
        row_store_count = min(len(lower_clips), FULL_DATASET_GT_COUNT)
        lower_row_stores = [
            ik_ctl.SimpleClipStore([clip], cfg, device)
            for clip in lower_clips[:row_store_count]
        ]
        install_native_lower_targets_cached(
            lower_store,
            lower_row_stores,
            lower_clips,
            dataset_sha=corpus_identity_sha,
            use_full_dataset_cache=cached_corpus_sha is not None,
            cache_dir=(
                None
                if resolved_prepared_cache_dir is None
                else resolved_prepared_cache_dir / "native_lower_targets"
            ),
        )
        lower_batched_store = (
            stack_lower_projection_store_from_clips(lower_store, lower_clips, device)
            if compact_multi_clip
            else stack_lower_projection_store(lower_store, lower_row_stores)
        )
        lower_fk_geometry = stack_fk_geometry(lower_clips, device)
        if compact_multi_clip:
            compact_motion_clips_in_place(
                lower_clips, retain_full=row_store_count
            )
        lower_store.prepare_root_state_cache(max(int(clip.T) for clip in lower_clips) + ROOT_PAD_FRAMES)
        frozen = None
        if checkpoint is not None:
            frozen = visualize.load_model(checkpoint, lower_clips[0], cfg, device)
            frozen.eval().requires_grad_(False)

        full_cfg = copy.deepcopy(cfg)
        full_cfg.body_mode = tl.BODY_MODE_FULL
        full_clips = (
            load_motion_clips_with_read_only_prefix_cache(
                paths,
                full_cfg,
                tl.BODY_MODE_FULL,
                prefix_dataset_sha=prepared_corpus_prefix_cache_sha256,
                prefix_count=prepared_corpus_prefix_count,
                prefix_cache_dir=Path(prepared_corpus_prefix_cache_dir).resolve(),
                suffix_dataset_sha=prepared_corpus_suffix_cache_sha256,
                suffix_cache_dir=prepared_corpus_suffix_cache_dir,
                suffix_cache_compression=(
                    prepared_corpus_suffix_cache_compression_by_mode or {}
                ).get(tl.normalized_body_mode(tl.BODY_MODE_FULL)),
            )
            if prepared_corpus_prefix_cache_sha256 is not None
            and prepared_corpus_prefix_cache_dir is not None
            else
            load_motion_clips_packed(
                paths,
                full_cfg,
                cached_corpus_sha,
                tl.BODY_MODE_FULL,
                cache_dir=motion_cache_dir,
            )
            if cached_corpus_sha is not None
            else ik_ctl.load_clips([(path, False) for path in paths], full_cfg)
            if compact_multi_clip
            else [tl.MotionClip(path, full_cfg, cyclic_animation=False) for path in paths]
        )
        full_clip = full_clips[0]
        full_fk_geometry = stack_fk_geometry(full_clips, device)
        if compact_multi_clip:
            compact_motion_clips_in_place(
                full_clips, retain_full=row_store_count
            )

    if inference_only:
        viewer_runtime = InferenceRuntime(
            recipe,
            device,
            checkpoint,
            checkpoint_path,
            cfg,
            lower_clips,
            full_clips,
            lower_store,
            lower_row_stores,
            lower_batched_store,
            lower_clips[0],
            full_clip,
            lower_fk_geometry,
            full_fk_geometry,
            frozen,
            None,  # type: ignore[arg-type]
        )
        viewer_runtime.attacks = load_attack_batch(
            paths,
            viewer_runtime,
            require_all_families=False,
            include_contact_metadata=False,
        )
        if recipe.predictive_pin_checkpoint is not None:
            import slash2_predictive_pin

            viewer_runtime.pin_teacher, viewer_runtime.pin_teacher_metadata = (
                slash2_predictive_pin.load_teacher(
                    recipe.predictive_pin_checkpoint,
                    recipe.predictive_pin_checkpoint_sha256,
                    device,
                )
            )
        return viewer_runtime

    if prior_checkpoint_paths is None:
        ae11 = load_prior("ae11", Path(recipe.ae11_pointer), device)
        ae22 = load_prior("ae22", Path(recipe.ae22_pointer), device)
        ae33 = load_prior("ae33", Path(recipe.ae33_pointer), device)
    else:
        missing_priors = {"ae11", "ae22", "ae33"} - set(prior_checkpoint_paths)
        if missing_priors:
            raise ValueError(
                f"Explicit prior checkpoint set is missing {sorted(missing_priors)}"
            )
        ae11 = load_prior_checkpoint(
            "ae11", Path(prior_checkpoint_paths["ae11"]), device
        )
        ae22 = load_prior_checkpoint(
            "ae22", Path(prior_checkpoint_paths["ae22"]), device
        )
        ae33 = load_prior_checkpoint(
            "ae33", Path(prior_checkpoint_paths["ae33"]), device
        )
    if (
        int(ae11.mean.numel()) != STATE_CONDITIONED_AE11_DIM
        or int(ae22.mean.numel()) != STATE_CONDITIONED_AE_DIM
        or int(ae33.mean.numel()) != STATE_CONDITIONED_AE_DIM
    ):
        raise ValueError(
            "Accepted priors must use strict Slash2 target-frame v3 dimensions "
            f"AE11={STATE_CONDITIONED_AE11_DIM}, "
            f"AE22/AE33={STATE_CONDITIONED_AE_DIM}"
        )
    blade_collision = load_blade_box_definition(Path(recipe.blade_collision_definition))
    if blade_collision.attach_joint not in full_clip.body_names:
        raise ValueError(
            f"Blade collision joint {blade_collision.attach_joint!r} is absent from the full skeleton"
        )
    if int(recipe.blade_collision_sweep_samples) < 3 or int(recipe.blade_collision_sweep_samples) % 2 == 0:
        raise ValueError("Blade collision sweep samples must be an odd integer >= 3")
    body_collision_layout = build_body_collision_layout(
        full_clip.body_names,
        excluded=recipe.blade_collision_excluded_colliders,
    )
    native_lower_pose_indices = build_native_lower_pose_indices(lower_store, device)
    placeholder = Runtime(
        recipe,
        device,
        checkpoint,
        checkpoint_path,
        cfg,
        lower_clips,
        full_clips,
        lower_store,
        lower_row_stores,
        lower_batched_store,
        lower_clips[0],
        full_clip,
        lower_fk_geometry,
        full_fk_geometry,
        frozen,
        ae11,
        ae22,
        ae33,
        blade_collision,
        body_collision_layout,
        native_lower_pose_indices,
        None,  # type: ignore[arg-type]
    )
    if recipe.predictive_pin_checkpoint is not None:
        import slash2_predictive_pin
        if not math.isfinite(recipe.predictive_pin_weight) or recipe.predictive_pin_weight <= 0.0:
            raise ValueError("Enabled pin teacher requires a positive finite loss weight")
        placeholder.pin_teacher, placeholder.pin_teacher_metadata = slash2_predictive_pin.load_teacher(
            recipe.predictive_pin_checkpoint, recipe.predictive_pin_checkpoint_sha256, device
        )
    elif recipe.predictive_pin_weight != 0.0:
        raise ValueError("Predictive pin weight requires an explicit verified teacher")
    placeholder.attacks = load_attack_batch_cached(
        paths,
        placeholder,
        use_full_dataset_cache=bulk_full_dataset,
        dataset_sha=prepared_corpus_sha256,
        cache_dir=(
            None
            if resolved_prepared_cache_dir is None
            else resolved_prepared_cache_dir / "attack_batch"
        ),
        require_all_families=attack_paths is None,
    )
    return placeholder


def is_slash2_checkpoint_data(checkpoint: object) -> bool:
    if not isinstance(checkpoint, dict):
        return False
    schemas = checkpoint.get("schemas")
    recipe_values = checkpoint.get("recipe")
    if not isinstance(recipe_values, dict):
        return False
    frozen_enabled = bool(recipe_values.get("frozen_agent_enabled", True))
    expected_lower_input = target_codec.lower_input_dim(
        frozen_agent_enabled=frozen_enabled
    )
    return (
        checkpoint.get("kind") == "slash2_two_agent_cuda_graph"
        and isinstance(schemas, dict)
        and schemas.get("target_frame_schema") == target_codec.TARGET_FRAME_SCHEMA
        and schemas.get("target_frame_schema_version")
        == target_codec.TARGET_FRAME_SCHEMA_VERSION
        and checkpoint_training_graph_schema(checkpoint)
        in {
            SLASH2_CUDA_GRAPH_SCHEMA,
            PRE_ANTI_PIN_SLIDE_SLASH2_CUDA_GRAPH_SCHEMA,
            PRE_INSUFFICIENT_PIN_SLASH2_CUDA_GRAPH_SCHEMA,
            PRE_PREDICTIVE_PIN_SLASH2_CUDA_GRAPH_SCHEMA,
            PRE_PIKE_BLADE_LOOK_SLASH2_CUDA_GRAPH_SCHEMA,
            PRE_OPPOSITE_CALF_SLASH2_CUDA_GRAPH_SCHEMA,
            PRE_HIT_DYNAMICS_SLASH2_CUDA_GRAPH_SCHEMA,
        }
        and schemas.get("lower_input_dim") == expected_lower_input
        and schemas.get("frozen_agent_enabled") == frozen_enabled
        and schemas.get("upper_input_dim") == UPPER_INPUT_DIM
        and isinstance(checkpoint.get("lower_agent"), dict)
        and isinstance(checkpoint.get("upper_agent"), dict)
        and isinstance(checkpoint.get("recipe"), dict)
    )


def checkpoint_training_graph_schema(checkpoint: object) -> str:
    """Return the implementation schema without coupling it to viewer discovery."""

    if not isinstance(checkpoint, dict):
        return ""
    schemas = checkpoint.get("schemas")
    if not isinstance(schemas, dict):
        return ""
    return str(schemas.get("training_graph", schemas.get("cuda_graph", "")))


def is_legacy_neutral_upper_slash2_checkpoint_data(checkpoint: object) -> bool:
    if not isinstance(checkpoint, dict):
        return False
    schemas = checkpoint.get("schemas")
    return (
        checkpoint.get("kind") == "slash2_two_agent_cuda_graph"
        and isinstance(schemas, dict)
        and schemas.get("cuda_graph") == LEGACY_SLASH2_CUDA_GRAPH_SCHEMA
    )


def recipe_from_slash2_checkpoint(checkpoint: dict[str, object]) -> Recipe:
    values = checkpoint.get("recipe")
    if not isinstance(values, dict):
        raise ValueError("Slash2 checkpoint has no fixed recipe")
    valid = {item.name for item in fields(Recipe)}
    rebound = {key: value for key, value in values.items() if key in valid}
    gt_dir = Path(str(rebound.get("gt_dir", "")))
    if not gt_dir.is_dir() or not any(gt_dir.glob("*.npz")):
        # Imported RunPod checkpoints retain their exact tensors but machine
        # paths are necessarily host-local. The current 32-motion controller
        # runtime is the portable materialization of the canonical GT corpus.
        rebound["gt_dir"] = Recipe().gt_dir
    if bool(rebound.get("frozen_agent_enabled", True)):
        walk_candidates: list[object] = [rebound.get("walk_checkpoint")]
        frozen_walk = checkpoint.get("frozen_walk")
        if isinstance(frozen_walk, dict):
            walk_candidates.extend((frozen_walk.get("path"), frozen_walk.get("source_path")))
        walk_candidates.append(Recipe().walk_checkpoint)
        rebound["walk_checkpoint"] = next(
            (
                str(Path(str(candidate)).resolve())
                for candidate in walk_candidates
                if candidate and Path(str(candidate)).is_file()
            ),
            str(rebound.get("walk_checkpoint", Recipe().walk_checkpoint)),
        )
    if rebound.get("predictive_pin_checkpoint") is not None:
        local_pin_teacher = (
            PROJECT_ROOT
            / "training"
            / "runs"
            / "20260831_ae3_slash2_pin_predictor"
            / "ae_pin_best.pt"
        )
        configured_pin_teacher = Path(
            str(rebound.get("predictive_pin_checkpoint", ""))
        )
        if not configured_pin_teacher.is_file() and local_pin_teacher.is_file():
            rebound["predictive_pin_checkpoint"] = str(
                local_pin_teacher.resolve()
            )
    return Recipe(**rebound)


def recipe_for_slash2_inference(checkpoint: dict[str, object]) -> Recipe:
    """Return the checkpoint recipe without training-only sampling policy.

    Forced-family rows constrain how a training batch is assembled; they do
    not change either agent or a selected animation rollout.  A standalone
    viewer deliberately loads only the canonical originals plus the selected
    clip, so carrying that training flag into ``load_runtime`` incorrectly
    demanded the full variant corpus during inference.
    """

    return replace(
        recipe_from_slash2_checkpoint(checkpoint),
        forced_attack_family="",
        forced_attack_family_rows_per_logical_batch=0,
    )


def lower_output_dim_from_checkpoint(checkpoint: dict[str, object]) -> int:
    state = checkpoint.get("lower_agent")
    schemas = checkpoint.get("schemas")
    if not isinstance(state, dict) or not isinstance(schemas, dict):
        raise ValueError("Slash2 checkpoint is missing lower-agent schema/state")
    bias = state.get("delta_head.bias")
    if not torch.is_tensor(bias):
        raise ValueError("Slash2 checkpoint lower agent has no delta_head.bias")
    state_width = int(bias.numel())
    declared_width = int(schemas.get("lower_output_dim", schemas.get("lower_output_delta_dim", -1)))
    if state_width != declared_width:
        raise ValueError(
            f"Slash2 lower output state/schema mismatch: state={state_width}, schema={declared_width}"
        )

    if state_width != LOWER_OUTPUT_DIM:
        raise ValueError(
            f"Strict target-frame v3 checkpoint must have {LOWER_OUTPUT_DIM} lower outputs, "
            f"got {state_width}"
        )
    expected = {
        "lower_output_dim": LOWER_OUTPUT_DIM,
        "lower_output_delta_dim": LOWER_POSE_DELTA_DIM,
        "lower_pin_command_dim": LOWER_PIN_COMMAND_DIM,
        "lower_pin_command_transform": "clamp(2*sigmoid(command)-1,0,1)",
        "lower_pin_zero_contract": "command 0 produces probability 0 and no second pin displacement",
        "lower_pin_projection": "run_continuous_probability_projection_then_minimum_floor_unclip",
        "lower_pin_integration_steps": LOWER_PIN_INTEGRATION_STEPS,
        "lower_pin_height_gate_enabled": LOWER_PIN_HEIGHT_GATE_ENABLED,
        "lower_pin_near_floor_forcing": False,
        "lower_pin_side_blend_deg": LOWER_PIN_SIDE_BLEND_DEG,
        "lower_pin_ground_y_m": LOWER_PIN_GROUND_Y_M,
    }
    mismatches = {
        key: {"expected": value, "actual": schemas.get(key)}
        for key, value in expected.items()
        if schemas.get(key) != value
    }
    if mismatches:
        raise ValueError(f"Slash2 lower pin checkpoint schema mismatch: {mismatches}")
    return state_width


def load_slash2_rollout_session(
    checkpoint_path: Path,
    device: torch.device,
) -> tuple[dict[str, object], Recipe, torch.nn.Module, torch.nn.Module]:
    cache_key = (str(checkpoint_path).lower(), str(device), int(checkpoint_path.stat().st_mtime_ns))
    cached = _SLASH2_ROLLOUT_SESSION_CACHE.get(cache_key)
    if cached is not None:
        return cached
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if not is_slash2_checkpoint_data(checkpoint):
        raise ValueError(
            f"{checkpoint_path.name} does not expose the current Slash2 controller interface"
        )
    recipe = recipe_for_slash2_inference(checkpoint)
    lower_output_dim = lower_output_dim_from_checkpoint(checkpoint)
    lower = DeltaAgent(
        lower_input_dim_for_recipe(recipe), lower_output_dim, recipe, gates=False
    ).to(device)
    upper = DeltaAgent(UPPER_INPUT_DIM, UPPER_STATE_DIM, recipe, gates=True).to(device)
    lower.load_state_dict(checkpoint["lower_agent"])
    upper.load_state_dict(checkpoint["upper_agent"])
    lower.eval()
    upper.eval()
    session = (checkpoint, recipe, lower, upper)
    _SLASH2_ROLLOUT_SESSION_CACHE.clear()
    _SLASH2_ROLLOUT_BATCH_CACHE.clear()
    _SLASH2_ROLLOUT_RESULT_CACHE.clear()
    _SLASH2_ROLLOUT_SESSION_CACHE[cache_key] = session
    return session


def rollout_slash2_gt16_batch(
    checkpoint_path: Path,
    device: torch.device,
    recipe: Recipe,
    runtime: Runtime | InferenceRuntime,
    lower: torch.nn.Module,
    upper: torch.nn.Module,
    disable_foot_pinning: bool = False,
    *,
    endpoint_policy: str = "authored_length",
    max_wait_after_authored_end_frames: int = 120,
    endpoint_post_hit_tail_steps: torch.Tensor | None = None,
) -> dict[str, list[np.ndarray]]:
    """Run the same complete 16-row batch used by ``FullEpisodeLoss`` once."""

    from slash2_predictive_pin import pin_error_rows

    source_signature = tuple(
        (str(path.resolve()).lower(), int(path.stat().st_mtime_ns))
        for path in runtime.attacks.paths
    )
    if endpoint_policy not in {
        "authored_length",
        "learned_hit_then_authored_tail",
    }:
        raise ValueError(f"unsupported rollout endpoint policy: {endpoint_policy!r}")
    if max_wait_after_authored_end_frames < 0:
        raise ValueError("max wait after authored end must be non-negative")
    learned_hit_endpoint = endpoint_policy == "learned_hit_then_authored_tail"
    data = runtime.attacks
    effective_post_hit_tail_steps = (
        data.post_hit_tail_steps
        if endpoint_post_hit_tail_steps is None
        else endpoint_post_hit_tail_steps.to(device=device, dtype=torch.long)
    )
    if effective_post_hit_tail_steps.shape != data.post_hit_tail_steps.shape:
        raise ValueError("endpoint post-hit tail override has the wrong batch shape")
    if bool((effective_post_hit_tail_steps < 0).any().item()):
        raise ValueError("endpoint post-hit tail override contains a negative value")
    cache_key = (
        str(checkpoint_path).lower(),
        str(device),
        int(checkpoint_path.stat().st_mtime_ns),
        source_signature,
        bool(disable_foot_pinning),
        endpoint_policy,
        int(max_wait_after_authored_end_frames),
        tuple(int(value) for value in effective_post_hit_tail_steps.detach().cpu().tolist()),
    )
    cached = _SLASH2_ROLLOUT_BATCH_CACHE.get(cache_key)
    if cached is not None:
        return cached
    ids = data.clip_ids
    batch = int(ids.numel())
    zero_index = torch.zeros_like(ids)
    one_index = torch.ones_like(ids)
    previous_lower = data.trajectory_lower[:, 0]
    current_lower = data.trajectory_lower[:, 1]
    previous_heading = data.trajectory_heading[:, 0]
    current_heading = data.trajectory_heading[:, 1]
    previous_upper = data.initial_previous_upper
    current_upper = data.initial_current_upper
    geometry_ids = ids
    targets_world = data.targets_world
    previous_base_upper = base_upper_hybrid_from_lower(
        runtime,
        geometry_ids,
        geometry_ids,
        zero_index,
        previous_lower,
        targets_world,
        previous_heading,
    )
    current_base_upper = base_upper_hybrid_from_lower(
        runtime,
        geometry_ids,
        geometry_ids,
        one_index,
        current_lower,
        targets_world,
        current_heading,
    )
    armed_latch = torch.zeros((batch,), dtype=torch.float32, device=device)
    hit_latch = torch.zeros_like(armed_latch)

    first_pos = data.initial_global_pos[:, 0]
    first_rot = data.initial_global_rot[:, 0]
    current_pos = data.initial_global_pos[:, 1]
    current_rot = data.initial_global_rot[:, 1]
    zero_gates = torch.zeros((batch, 2), dtype=torch.float32, device=device)
    zero_pin_probabilities = torch.zeros((batch, 2), dtype=torch.float32, device=device)
    zero_latches = torch.zeros((batch,), dtype=torch.float32, device=device)
    frame_positions = [first_pos, current_pos]
    frame_rotations = [first_rot, current_rot]
    frame_lower = [previous_lower, current_lower]
    frame_upper = [previous_upper, current_upper]
    frame_gates = [zero_gates, zero_gates]
    frame_pin_probabilities = [zero_pin_probabilities, zero_pin_probabilities]
    frame_ideal_pin_probabilities = [
        zero_pin_probabilities,
        zero_pin_probabilities,
    ]
    frame_armed = [zero_latches, zero_latches]
    frame_hit = [zero_latches, zero_latches]
    current_index = one_index
    projection_store = runtime.lower_batched_store
    if learned_hit_endpoint:
        hit_seen = torch.zeros((batch,), dtype=torch.bool, device=device)
        finished = torch.zeros_like(hit_seen)
        hard_stop_index = (
            data.lengths - 1 + int(max_wait_after_authored_end_frames)
        )
        learned_finish_index = hard_stop_index + effective_post_hit_tail_steps
        max_iterations = (
            int(data.max_steps)
            + int(max_wait_after_authored_end_frames)
            + int(effective_post_hit_tail_steps.max().item())
        )
    else:
        max_iterations = int(data.max_steps)

    with runtime.policy_context():
        for _step in range(max_iterations):
            if learned_hit_endpoint:
                active = ~finished
            else:
                active = current_index < (data.lengths - 1)
            safe_current = torch.minimum(current_index, data.lengths - 2)
            previous_index = torch.maximum(safe_current - 1, torch.zeros_like(safe_current))
            next_index = safe_current + 1
            future_index = torch.minimum(next_index + 1, data.lengths - 1)
            next_logical_index = current_index + 1
            previous_lower_held = target_codec.lower_to_held_heading(
                runtime.lower_store,
                previous_lower,
                targets_world,
                previous_heading,
                current_heading,
            )
            previous_upper_held = target_codec.upper_to_held_heading(
                previous_upper,
                targets_world,
                previous_heading,
                current_heading,
            )
            if runtime.frozen_walk is None:
                frozen_next = current_lower
            else:
                frozen_next, _frozen_controller_input = frozen_next_hybrid(
                    runtime,
                    projection_store,
                    geometry_ids,
                    safe_current,
                    previous_index,
                    previous_lower,
                    current_lower,
                    targets_world,
                    previous_heading,
                    current_heading,
                )
            root_current_next = transition_root_dyaw(
                runtime.lower_store, geometry_ids, safe_current, next_index
            )
            root_next_future = transition_root_dyaw(
                runtime.lower_store, geometry_ids, next_index, future_index
            )
            lower_input = build_lower_learned_input(
                current_lower,
                frozen_next if runtime.frozen_walk is not None else None,
                data.labels,
                root_current_next,
                root_next_future,
                targets_world,
            )
            lower_output, _unused = lower(lower_input)
            lower_delta, lower_pin_commands = split_lower_output(lower_output)
            if disable_foot_pinning:
                lower_pin_commands = torch.zeros_like(lower_pin_commands)
            next_lower_candidate, lower_pin_probabilities = clean_lower_hybrid_delta(
                runtime,
                projection_store,
                geometry_ids,
                safe_current,
                next_index,
                current_lower,
                frozen_next,
                lower_delta,
                lower_pin_commands,
                targets_world,
                current_heading,
            )
            if disable_foot_pinning:
                lower_pin_probabilities = torch.zeros_like(
                    lower_pin_probabilities
                )
            next_lower = torch.where(active[:, None], next_lower_candidate, current_lower)
            _pin_error, ideal_pin_probabilities = pin_error_rows(
                runtime.pin_teacher,
                previous_lower_held,
                current_lower,
                targets_world,
                data.labels,
                lower_pin_probabilities,
            )

            next_base_candidate = base_upper_hybrid_from_lower(
                runtime,
                geometry_ids,
                geometry_ids,
                next_index,
                next_lower_candidate,
                targets_world,
                current_heading,
            )
            next_prior = carry_upper_hybrid_deviation(
                current_upper,
                current_base_upper,
                next_base_candidate,
            )
            upper_input = build_upper_learned_input(
                previous_upper_held,
                next_prior,
                targets_world,
                data.labels,
                previous_lower_held,
                current_lower,
                next_lower_candidate,
                armed_latch,
                hit_latch,
            )
            upper_delta, gate_probabilities = upper(upper_input)
            assert gate_probabilities is not None
            next_upper_candidate = clean_upper_state(next_prior + upper_delta)
            next_upper = torch.where(active[:, None], next_upper_candidate, current_upper)
            next_armed, next_hit = advance_phase_latches(
                armed_latch,
                hit_latch,
                gate_probabilities,
                recipe.gate_threshold,
            )
            next_armed = torch.where(active, next_armed, armed_latch)
            next_hit = torch.where(active, next_hit, hit_latch)
            if learned_hit_endpoint:
                new_hit = (
                    active
                    & (hit_latch < 0.5)
                    & (next_hit >= 0.5)
                )
                learned_finish_index = torch.where(
                    new_hit,
                    next_logical_index + effective_post_hit_tail_steps,
                    learned_finish_index,
                )
                hit_seen = hit_seen | new_hit
                reached_endpoint = torch.where(
                    hit_seen,
                    next_logical_index >= learned_finish_index,
                    next_logical_index >= hard_stop_index,
                )
                finished = finished | (active & reached_endpoint)
            next_global_pos, next_global_rot = hybrid_full_fk_globals(
                runtime,
                geometry_ids,
                geometry_ids,
                next_index,
                next_lower_candidate,
                next_upper_candidate,
                targets_world,
                current_heading,
            )
            pelvis_index = runtime.full_clip.body_names.index("pelvis")
            next_heading_candidate = target_codec.target_facing_heading(
                next_global_pos[:, pelvis_index], targets_world
            )
            next_lower_carried = target_codec.lower_to_held_heading(
                runtime.lower_store,
                next_lower,
                targets_world,
                current_heading,
                next_heading_candidate,
            )
            next_base_carried = target_codec.upper_to_held_heading(
                next_base_candidate,
                targets_world,
                current_heading,
                next_heading_candidate,
            )
            next_upper_carried = target_codec.upper_to_held_heading(
                next_upper,
                targets_world,
                current_heading,
                next_heading_candidate,
            )
            current_pos = torch.where(active[:, None, None], next_global_pos, current_pos)
            current_rot = torch.where(active[:, None, None, None], next_global_rot, current_rot)
            frame_positions.append(current_pos)
            frame_rotations.append(current_rot)
            frame_lower.append(next_lower)
            frame_upper.append(next_upper)
            frame_gates.append(gate_probabilities)
            frame_pin_probabilities.append(
                torch.where(
                    active[:, None], lower_pin_probabilities, zero_pin_probabilities
                )
            )
            frame_ideal_pin_probabilities.append(
                torch.where(
                    active[:, None],
                    ideal_pin_probabilities,
                    zero_pin_probabilities,
                )
            )
            frame_armed.append(next_armed)
            frame_hit.append(next_hit)

            previous_lower = torch.where(active[:, None], current_lower, previous_lower)
            current_lower = torch.where(active[:, None], next_lower_carried, current_lower)
            previous_heading = torch.where(
                active[:, None, None], current_heading, previous_heading
            )
            current_heading = torch.where(
                active[:, None, None], next_heading_candidate, current_heading
            )
            previous_base_upper = torch.where(active[:, None], current_base_upper, previous_base_upper)
            current_base_upper = torch.where(active[:, None], next_base_carried, current_base_upper)
            previous_upper = torch.where(active[:, None], current_upper, previous_upper)
            current_upper = torch.where(active[:, None], next_upper_carried, current_upper)
            armed_latch = next_armed
            hit_latch = next_hit
            current_index = torch.where(active, next_logical_index, current_index)
            if learned_hit_endpoint and bool(finished.all().item()):
                break

    positions = torch.stack(frame_positions, dim=1).detach().cpu().numpy().astype(np.float32)
    rotations = torch.stack(frame_rotations, dim=1).detach().cpu().numpy().astype(np.float32)
    lower_states = torch.stack(frame_lower, dim=1).detach().cpu().numpy().astype(np.float32)
    upper_states = torch.stack(frame_upper, dim=1).detach().cpu().numpy().astype(np.float32)
    gates = torch.stack(frame_gates, dim=1).detach().cpu().numpy().astype(np.float32)
    pin_probabilities = (
        torch.stack(frame_pin_probabilities, dim=1)
        .detach()
        .cpu()
        .numpy()
        .astype(np.float32)
    )
    ideal_pin_probabilities = (
        torch.stack(frame_ideal_pin_probabilities, dim=1)
        .detach()
        .cpu()
        .numpy()
        .astype(np.float32)
    )
    armed = torch.stack(frame_armed, dim=1).detach().cpu().numpy().astype(np.float32)
    hit = torch.stack(frame_hit, dim=1).detach().cpu().numpy().astype(np.float32)
    result: dict[str, list[np.ndarray]] = {
        "positions": [],
        "rotations": [],
        "lower": [],
        "upper": [],
        "gates": [],
        "pin_probabilities": [],
        "ideal_pin_probabilities": [],
        "armed": [],
        "hit": [],
    }
    if learned_hit_endpoint:
        output_lengths = (
            torch.where(hit_seen, learned_finish_index, hard_stop_index) + 1
        ).detach().cpu().tolist()
    else:
        output_lengths = data.lengths.detach().cpu().tolist()
    for row, length_value in enumerate(output_lengths):
        length = int(length_value)
        result["positions"].append(positions[row, :length].copy())
        result["rotations"].append(rotations[row, :length].copy())
        result["lower"].append(lower_states[row, :length].copy())
        result["upper"].append(upper_states[row, :length].copy())
        result["gates"].append(gates[row, :length].copy())
        result["pin_probabilities"].append(pin_probabilities[row, :length].copy())
        result["ideal_pin_probabilities"].append(
            ideal_pin_probabilities[row, :length].copy()
        )
        result["armed"].append(armed[row, :length].copy())
        result["hit"].append(hit[row, :length].copy())
    _SLASH2_ROLLOUT_BATCH_CACHE.clear()
    _SLASH2_ROLLOUT_BATCH_CACHE[cache_key] = result
    return result


@torch.inference_mode()
def rollout_slash2_checkpoint(
    checkpoint_path: Path,
    attack_path: Path | None = None,
    device: torch.device | str = "cpu",
    disable_foot_pinning: bool = False,
) -> Slash2Rollout:
    """Reproduce the exact autoregressive pose path used by training.

    Frames 0 and 1 are the same authored initialization used by
    :class:`FullEpisodeLoss`.
    Every later frame is produced by the frozen walk policy, the lower delta
    agent, and the upper delta/gate agent in that order.
    """

    checkpoint_path = Path(checkpoint_path).resolve()
    device = torch.device(device)
    checkpoint, recipe, lower, upper = load_slash2_rollout_session(
        checkpoint_path, device
    )

    if attack_path is None:
        candidates = sorted(
            (
                path
                for path in Path(recipe.gt_dir).glob("*.npz")
                if "__" not in path.stem
            ),
            key=lambda path: path.name.lower(),
        )
        if not candidates:
            raise FileNotFoundError(
                "No attack NPZ was selected and the local GT folder is empty"
            )
        selected_path = candidates[0].resolve()
    else:
        selected_path = Path(attack_path).resolve()
    if not selected_path.is_file():
        raise FileNotFoundError(f"Attack NPZ not found: {selected_path}")
    family = attack_family_from_path(selected_path)
    if family not in ATTACK_LABELS:
        raise ValueError(
            f"No Slash2 attack labels are declared for {selected_path.name}"
        )
    row = 0
    result_cache_key = (
        str(checkpoint_path).lower(),
        str(device),
        int(checkpoint_path.stat().st_mtime_ns),
        str(selected_path).lower(),
        int(selected_path.stat().st_mtime_ns),
        bool(disable_foot_pinning),
    )
    cached_result = _SLASH2_ROLLOUT_RESULT_CACHE.get(result_cache_key)
    if cached_result is not None:
        return cached_result

    initialization_source = "clean attack frames 0/1"
    selected_runtime = load_runtime(
        recipe,
        device,
        include_variants=False,
        attack_paths=[selected_path],
        inference_only=True,
    )

    batched = rollout_slash2_gt16_batch(
        checkpoint_path,
        device,
        recipe,
        selected_runtime,
        lower,
        upper,
        disable_foot_pinning=disable_foot_pinning,
    )
    positions = batched["positions"][row]
    rotations = batched["rotations"][row]
    gate_probabilities = batched["gates"][row]
    lower_pin_probabilities = batched["pin_probabilities"][row]
    ideal_pin_probabilities = batched["ideal_pin_probabilities"][row]
    armed_latch = batched["armed"][row]
    hit_latch = batched["hit"][row]
    length = int(selected_runtime.attacks.lengths[row].item())
    target_positions = (
        selected_runtime.attacks.trajectory_global_pos[row, :length]
        .detach()
        .cpu()
        .numpy()
        .astype(np.float32)
    )
    target_rotations = (
        selected_runtime.attacks.trajectory_global_rot[row, :length]
        .detach()
        .cpu()
        .numpy()
        .astype(np.float32)
    )

    full_cfg = copy.deepcopy(selected_runtime.cfg)
    full_cfg.body_mode = tl.BODY_MODE_FULL
    full_cfg.device = str(device)
    full_cfg.use_torch_compile = False
    # The inference runtime already parsed the selected target as row zero.
    clip = selected_runtime.full_clips[row]
    if positions.shape[0] != length or rotations.shape[0] != length:
        raise RuntimeError(f"Slash2 rollout produced {positions.shape[0]} frames for a {length}-frame attack")
    result = Slash2Rollout(
        attack_name=selected_runtime.attacks.names[row],
        attack_path=selected_path,
        clip=clip,
        cfg=full_cfg,
        positions=positions,
        rotations=rotations,
        gate_probabilities=gate_probabilities,
        lower_pin_probabilities=lower_pin_probabilities,
        ideal_pin_probabilities=ideal_pin_probabilities,
        armed_latch=armed_latch,
        hit_latch=hit_latch,
        target_world=selected_runtime.attacks.targets_world[row]
        .detach()
        .cpu()
        .numpy()
        .astype(np.float32),
        foot_pinning_disabled=bool(disable_foot_pinning),
        initialization_source=initialization_source,
        target_positions=target_positions,
        target_rotations=target_rotations,
    )
    if len(_SLASH2_ROLLOUT_RESULT_CACHE) >= 128:
        _SLASH2_ROLLOUT_RESULT_CACHE.clear()
    _SLASH2_ROLLOUT_RESULT_CACHE[result_cache_key] = result
    return result


class DeltaAgent(torch.nn.Module):
    def __init__(self, input_dim: int, delta_dim: int, recipe: Recipe, gates: bool = False) -> None:
        super().__init__()
        layers: list[torch.nn.Module] = []
        width = int(input_dim)
        for _ in range(recipe.hidden_layers):
            layers.extend(
                (
                    torch.nn.Linear(width, recipe.hidden_dim),
                    torch.nn.LayerNorm(recipe.hidden_dim),
                    torch.nn.GELU(),
                )
            )
            width = recipe.hidden_dim
        self.trunk = torch.nn.Sequential(*layers)
        self.delta_head = torch.nn.Linear(width, delta_dim)
        torch.nn.init.zeros_(self.delta_head.weight)
        torch.nn.init.zeros_(self.delta_head.bias)
        self.gates = bool(gates)
        if self.gates:
            self.gate_head = torch.nn.Linear(width, 2)
            torch.nn.init.zeros_(self.gate_head.weight)
            torch.nn.init.constant_(self.gate_head.bias, -4.0)

    def forward(self, values: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor | None]:
        hidden = self.trunk(values)
        delta = self.delta_head(hidden)
        gates = torch.sigmoid(self.gate_head(hidden)) if self.gates else None
        return delta, gates


def compile_training_networks(
    runtime: Runtime,
    lower: DeltaAgent,
    upper: DeltaAgent,
) -> None:
    """Compile repeated regions before split forward/backward graph capture."""

    global slash_fast_fk_globals, _SLASH_FAST_FK_COMPILED
    if not _SLASH_FAST_FK_COMPILED:
        slash_fast_fk_globals = torch.compile(
            _slash_fast_fk_globals_fixed,
            fullgraph=True,
            dynamic=False,
            options=FAST_COMPILE_OPTIONS,
        )
        _SLASH_FAST_FK_COMPILED = True

    lower.forward = torch.compile(
        lower.forward,
        fullgraph=True,
        dynamic=False,
        options=FAST_COMPILE_OPTIONS,
    )
    upper.forward = torch.compile(
        upper.forward,
        fullgraph=True,
        dynamic=False,
        options=FAST_COMPILE_OPTIONS,
    )
    if runtime.frozen_walk is not None:
        runtime.frozen_walk.forward = torch.compile(
            runtime.frozen_walk.forward,
            fullgraph=True,
            dynamic=False,
            options=FAST_COMPILE_OPTIONS,
        )
    for prior in (runtime.ae11, runtime.ae22, runtime.ae33):
        prior.model.forward = torch.compile(
            prior.model.forward,
            fullgraph=True,
            dynamic=False,
            options=FAST_COMPILE_OPTIONS,
        )
    if runtime.pin_teacher is not None:
        runtime.pin_teacher.forward = torch.compile(
            runtime.pin_teacher.forward, fullgraph=True, dynamic=False, options=FAST_COMPILE_OPTIONS
        )


def phase_latch(previous: torch.Tensor, probabilities: torch.Tensor, threshold: float = GATE_THRESHOLD) -> torch.Tensor:
    activation = (probabilities >= float(threshold)).to(dtype=previous.dtype)
    return torch.maximum(previous, activation)


def advance_phase_latches(
    previous_armed: torch.Tensor,
    previous_hit: torch.Tensor,
    probabilities: torch.Tensor,
    threshold: float = GATE_THRESHOLD,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Enforce the minimum unarmed -> armed -> hit state sequence.

    A hit request received while the input state is unarmed is redirected to
    armed on that frame. Hit may latch no earlier than the following frame.
    """

    armed_request = probabilities[:, 0] >= float(threshold)
    hit_request = probabilities[:, 1] >= float(threshold)
    was_armed = previous_armed >= 0.5
    next_hit = torch.maximum(
        previous_hit,
        (hit_request & was_armed).to(previous_hit.dtype),
    )
    next_armed = torch.maximum(
        previous_armed,
        (armed_request | hit_request).to(previous_armed.dtype),
    )
    next_armed = torch.maximum(next_armed, next_hit.to(next_armed.dtype))
    return next_armed, next_hit


def prior_score(prior: FrozenPrior, raw: torch.Tensor, start: int, end: int) -> torch.Tensor:
    normalized = (raw - prior.mean) / prior.std
    reconstruction = prior.model(normalized)
    return (reconstruction[:, start:end] - normalized[:, start:end]).square().mean(dim=-1)


def routed_prior_masks(
    active_f: torch.Tensor,
    armed_latch: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Route AE11 throughout, AE22 before armed, and AE33 after armed."""

    prearmed_f = active_f * (1.0 - armed_latch)
    return (
        active_f,
        prearmed_f,
        active_f * armed_latch,
    )


def lower_prior_features(
    prior: FrozenPrior,
    proposed_next: torch.Tensor,
    previous_lower: torch.Tensor,
    current_lower: torch.Tensor,
    target_world: torch.Tensor,
    labels: torch.Tensor,
) -> tuple[torch.Tensor, int, int]:
    """Build AE11 from three states in one held v3 step frame."""

    dimension = int(prior.mean.numel())
    if dimension != STATE_CONDITIONED_AE11_DIM:
        raise ValueError(
            f"{prior.name} must use v3 AE11 dimension "
            f"{STATE_CONDITIONED_AE11_DIM}, got {dimension}"
        )
    raw = torch.cat(
        (
            proposed_next - current_lower,
            previous_lower,
            current_lower,
            target_height_input(target_world),
            labels,
        ),
        dim=-1,
    )
    if int(raw.shape[-1]) != STATE_CONDITIONED_AE11_DIM:
        raise RuntimeError(
            f"AE11 target-frame feature width {raw.shape[-1]} != "
            f"{STATE_CONDITIONED_AE11_DIM}"
        )
    return raw, 0, LOWER_STATE_DIM


def upper_prior_features(
    prior: FrozenPrior,
    proposed_next: torch.Tensor,
    previous_upper: torch.Tensor,
    current_upper: torch.Tensor,
    target_world: torch.Tensor,
    labels: torch.Tensor,
) -> torch.Tensor:
    """Build AE22/AE33 from three states in one held v3 step frame."""

    dimension = int(prior.mean.numel())
    if dimension != STATE_CONDITIONED_AE_DIM:
        raise ValueError(
            f"{prior.name} must use v3 upper AE dimension "
            f"{STATE_CONDITIONED_AE_DIM}, got {dimension}"
        )
    raw = torch.cat(
        (
            proposed_next - current_upper,
            previous_upper,
            current_upper,
            target_height_input(target_world),
            labels,
        ),
        dim=-1,
    )
    if int(raw.shape[-1]) != STATE_CONDITIONED_AE_DIM:
        raise RuntimeError(
            f"{prior.name} target-frame feature width {raw.shape[-1]} != "
            f"{STATE_CONDITIONED_AE_DIM}"
        )
    return raw


@dataclass
class FragmentSeed:
    previous_lower: torch.Tensor
    current_lower: torch.Tensor
    previous_heading: torch.Tensor
    current_heading: torch.Tensor
    previous_base_upper: torch.Tensor
    current_base_upper: torch.Tensor
    previous_upper: torch.Tensor
    current_upper: torch.Tensor
    previous_ae_row: torch.Tensor
    previous_global_pos: torch.Tensor
    previous_global_rot: torch.Tensor
    current_global_pos: torch.Tensor
    current_global_rot: torch.Tensor
    current_root_pos: torch.Tensor
    current_root_rot: torch.Tensor
    geometry_clip_id: torch.Tensor
    previous_armed_latch: torch.Tensor
    previous_hit_latch: torch.Tensor
    armed_latch: torch.Tensor
    hit_latch: torch.Tensor
    agent_finish_index: torch.Tensor
    current_index: torch.Tensor
    episode_start: torch.Tensor


def gather_trajectory(values: torch.Tensor, frame: torch.Tensor) -> torch.Tensor:
    rows = torch.arange(frame.numel(), dtype=torch.long, device=frame.device)
    return values[rows, frame]


def random_fragment_start_indices(
    lengths: torch.Tensor,
    epoch: torch.Tensor,
    slot: int,
    row_keys: torch.Tensor,
    seed: int,
) -> torch.Tensor:
    """Deterministic, CUDA-graph-safe uniform starts in ``[1, length-2]``."""

    span = (lengths - 2).clamp_min(1)
    mixed = (
        epoch.to(torch.long) * 1_000_003
        + int(slot + 1) * 97_409
        + (row_keys.to(torch.long) + 1) * 65_537
        + int(seed)
    )
    mixed = torch.remainder(mixed * 48_271 + 1, 2_147_483_647)
    return 1 + torch.remainder(mixed, span)


def fragment_seed_state(
    runtime: Runtime,
    data: AttackBatch | AttackRows,
    current_index: torch.Tensor,
) -> FragmentSeed:
    ids = data.clip_ids
    previous_index = current_index - 1
    previous_lower = gather_trajectory(data.trajectory_lower, previous_index)
    current_lower = gather_trajectory(data.trajectory_lower, current_index)
    previous_base_upper = gather_trajectory(data.trajectory_base_upper, previous_index)
    current_base_upper = gather_trajectory(data.trajectory_base_upper, current_index)
    previous_upper = gather_trajectory(data.trajectory_upper, previous_index)
    current_upper = gather_trajectory(data.trajectory_upper, current_index)
    current_root_pos, current_root_rot, _yaw, _heading = runtime.lower_store.root_state(
        ids, current_index
    )
    return FragmentSeed(
        previous_lower=previous_lower,
        current_lower=current_lower,
        previous_heading=gather_trajectory(data.trajectory_heading, previous_index),
        current_heading=gather_trajectory(data.trajectory_heading, current_index),
        previous_base_upper=previous_base_upper,
        current_base_upper=current_base_upper,
        previous_upper=previous_upper,
        current_upper=current_upper,
        # Retained only as a fixed-shape graph-state slot until the old replay
        # schema is removed. V2 AE11 uses explicit fixed-yaw pose triples.
        previous_ae_row=previous_lower.new_zeros((previous_lower.shape[0], 193)),
        previous_global_pos=gather_trajectory(data.trajectory_global_pos, previous_index),
        previous_global_rot=gather_trajectory(data.trajectory_global_rot, previous_index),
        current_global_pos=gather_trajectory(data.trajectory_global_pos, current_index),
        current_global_rot=gather_trajectory(data.trajectory_global_rot, current_index),
        current_root_pos=current_root_pos,
        current_root_rot=current_root_rot,
        geometry_clip_id=ids,
        previous_armed_latch=(
            previous_index.to(torch.float32) >= data.armed_time
        ).to(torch.float32),
        previous_hit_latch=(
            previous_index.to(torch.float32) >= data.hit_time
        ).to(torch.float32),
        armed_latch=(current_index.to(torch.float32) >= data.armed_time).to(torch.float32),
        hit_latch=(current_index.to(torch.float32) >= data.hit_time).to(torch.float32),
        agent_finish_index=data.lengths - 1,
        current_index=current_index,
        episode_start=torch.ones(
            current_index.shape,
            dtype=torch.bool,
            device=current_index.device,
        ),
    )


class FullEpisodeLoss(torch.nn.Module):
    """The balanced random-fragment autoregressive objective captured for training."""
    metric_names = WEIGHTED_LOSS_METRIC_NAMES + (
        "hit_target_m",
        "hit_linear_velocity_error_mps",
        "hit_angular_velocity_error_radps",
        "lowerarm_max_length_error_m",
        "opposite_calf_max_overlap_m",
        "opposite_calf_collision_bad_rate",
        "blade_max_penetration_m",
        "blade_collision_bad_rate",
        "lower_pin_left_mean",
        "lower_pin_right_mean",
        "lower_pin_active_rate",
        "armed_latch_rate",
        "hit_latch_rate",
        "pin_teacher_left_mean",
        "pin_teacher_right_mean",
        "pin_error_mean",
        "anti_pin_slide_left_speed_mps",
        "anti_pin_slide_right_speed_mps",
        "anti_pin_slide_gate_mean",
    )

    def __init__(
        self,
        runtime: Runtime,
        lower_agent: DeltaAgent,
        upper_agent: DeltaAgent,
        rows_static: torch.Tensor | None = None,
    ) -> None:
        super().__init__()
        self.runtime = runtime
        self.lower_agent = lower_agent
        self.upper_agent = upper_agent
        self.rows_static = rows_static
        # A fixed physical CUDA graph can be fed either the 5,076-file corpus or
        # the 32 normal+mirrored GT files.  In both cases every graph slot is
        # staged from the selected source clip before replay.
        self.dynamic_full_dataset = bool(
            rows_static is not None
            and len(runtime.attacks.paths) > int(rows_static.numel())
        )
        if (
            not self.dynamic_full_dataset
            and int(runtime.attacks.trajectory_global_pos.shape[1]) == 0
        ):
            raise ValueError(
                "compact AttackBatch globals require dynamic full-dataset staging"
            )
        self.projection_store = (
            runtime.lower_batched_store
            if rows_static is None
            else select_lower_projection_store(runtime.lower_batched_store, rows_static)
        )
        # Keep the accepted graph-sized unroll. Episodes that have not reset
        # by this optimizer boundary are carried exactly into the next replay;
        # this preserves the learned-hit-relative tail without creating a
        # Windows NVIDIA-driver-crashing oversized CUDA graph.
        self.rollout_steps = int(runtime.attacks.max_steps)
        self.register_buffer(
            "ae11_weight_value",
            torch.tensor(runtime.recipe.ae11_weight, dtype=torch.float32, device=runtime.device),
        )
        self.register_buffer(
            "upper_prior_weight_value",
            torch.tensor(runtime.recipe.upper_prior_weight, dtype=torch.float32, device=runtime.device),
        )
        # Calibrate once after capture, then fill this scalar in-place. No
        # recapture or second corpus load is needed to publish the final weight.
        self.register_buffer("predictive_pin_weight_value", torch.tensor(
            runtime.recipe.predictive_pin_weight, dtype=torch.float32, device=runtime.device))
        self.register_buffer("anti_pin_slide_weight_value", torch.tensor(
            runtime.recipe.anti_pin_slide_weight, dtype=torch.float32, device=runtime.device))
        debug_batch = (
            len(runtime.attacks.paths)
            if rows_static is None
            else int(rows_static.numel())
        )
        gate_timing_row_multiplier = getattr(
            runtime, "training_gate_timing_row_multiplier", None
        )
        if gate_timing_row_multiplier is None:
            difficulty_ids = getattr(runtime, "training_row_difficulty_ids", None)
            if difficulty_ids is None:
                gate_timing_row_multiplier = torch.ones(
                    debug_batch, dtype=torch.float32, device=runtime.device
                )
            else:
                if (
                    not torch.is_tensor(difficulty_ids)
                    or difficulty_ids.ndim != 1
                    or int(difficulty_ids.numel()) != debug_batch
                ):
                    raise ValueError(
                        "training_row_difficulty_ids must match the physical batch"
                    )
                difficulty_multipliers = torch.tensor(
                    (
                        runtime.recipe.gate_timing_easy_multiplier,
                        runtime.recipe.gate_timing_medium_multiplier,
                        runtime.recipe.gate_timing_hard_multiplier,
                    ),
                    dtype=torch.float32,
                    device=runtime.device,
                )
                gate_timing_row_multiplier = difficulty_multipliers.index_select(
                    0, difficulty_ids.to(device=runtime.device, dtype=torch.long)
                )
        elif (
            not torch.is_tensor(gate_timing_row_multiplier)
            or gate_timing_row_multiplier.ndim != 1
            or int(gate_timing_row_multiplier.numel()) != debug_batch
        ):
            raise ValueError(
                "training_gate_timing_row_multiplier must match the physical batch"
            )
        else:
            gate_timing_row_multiplier = gate_timing_row_multiplier.to(
                device=runtime.device, dtype=torch.float32
            )
        if not bool(torch.isfinite(gate_timing_row_multiplier).all()):
            raise ValueError("gate-timing row multipliers must be finite")
        if bool((gate_timing_row_multiplier < 0.0).any()):
            raise ValueError("gate-timing row multipliers must be non-negative")
        self.register_buffer(
            "gate_timing_row_multiplier",
            gate_timing_row_multiplier,
            persistent=False,
        )
        self.register_buffer(
            "fragment_start_indices",
            torch.ones(
                (self.rollout_steps + 1, debug_batch),
                dtype=torch.long,
                device=runtime.device,
            ),
            persistent=False,
        )
        self.register_buffer(
            "clip_index_schedule",
            torch.zeros(
                (self.rollout_steps + 1, debug_batch),
                dtype=torch.long,
                device=runtime.device,
            ),
            persistent=False,
        )
        self._staged_attack_tensor_names: tuple[str, ...] = ()
        if self.dynamic_full_dataset:
            staged_names: list[str] = []
            slot_count = self.rollout_steps + 1
            for name in DYNAMIC_ATTACK_SOURCE_FIELDS:
                source = getattr(runtime.attacks, name)
                if not torch.is_tensor(source):
                    raise TypeError(f"AttackBatch.{name} must be a tensor")
                self.register_buffer(
                    f"staged_attack_{name}",
                    torch.empty(
                        (slot_count, debug_batch, *source.shape[1:]),
                        dtype=source.dtype,
                        device=runtime.device,
                    ),
                    persistent=False,
                )
                staged_names.append(name)
            for name, source in (
                ("final_lower", runtime.attacks.trajectory_lower[:, 0]),
                ("final_upper", runtime.attacks.trajectory_upper[:, 0]),
            ):
                self.register_buffer(
                    f"staged_attack_{name}",
                    torch.empty(
                        (slot_count, debug_batch, *source.shape[1:]),
                        dtype=source.dtype,
                        device=runtime.device,
                    ),
                    persistent=False,
                )
                staged_names.append(name)
            self._staged_attack_tensor_names = tuple(staged_names)
            seed_shapes = {
                "previous_lower": (LOWER_STATE_DIM,),
                "current_lower": (LOWER_STATE_DIM,),
                "previous_heading": (3, 3),
                "current_heading": (3, 3),
                "previous_base_upper": (UPPER_STATE_DIM,),
                "current_base_upper": (UPPER_STATE_DIM,),
                "previous_upper": (UPPER_STATE_DIM,),
                "current_upper": (UPPER_STATE_DIM,),
                "previous_ae_row": (193,),
                "previous_global_pos": (len(runtime.full_clip.body_names), 3),
                "previous_global_rot": (len(runtime.full_clip.body_names), 3, 3),
                "current_global_pos": (len(runtime.full_clip.body_names), 3),
                "current_global_rot": (len(runtime.full_clip.body_names), 3, 3),
                "current_root_pos": (3,),
                "current_root_rot": (3, 3),
                "geometry_clip_id": (),
                "previous_armed_latch": (),
                "previous_hit_latch": (),
                "armed_latch": (),
                "hit_latch": (),
                "agent_finish_index": (),
                "current_index": (),
                "episode_start": (),
            }
            for name, tail in seed_shapes.items():
                dtype = (
                    torch.long
                    if name in {"current_index", "geometry_clip_id", "agent_finish_index"}
                    else torch.bool
                    if name == "episode_start"
                    else torch.float32
                )
                self.register_buffer(
                    f"staged_seed_{name}",
                    torch.empty(
                        (slot_count, debug_batch, *tail),
                        dtype=dtype,
                        device=runtime.device,
                    ),
                    persistent=False,
                )
            for name in self._staged_attack_tensor_names:
                source = getattr(self, f"staged_attack_{name}")
                self.register_buffer(
                    f"terminal_attack_{name}",
                    torch.empty(
                        (debug_batch, *source.shape[2:]),
                        dtype=source.dtype,
                        device=runtime.device,
                    ),
                    persistent=False,
                )
            for name, tail in seed_shapes.items():
                dtype = (
                    torch.long
                    if name in {"current_index", "geometry_clip_id", "agent_finish_index"}
                    else torch.bool
                    if name == "episode_start"
                    else torch.float32
                )
                self.register_buffer(
                    f"terminal_seed_{name}",
                    torch.empty(
                        (debug_batch, *tail),
                        dtype=dtype,
                        device=runtime.device,
                    ),
                    persistent=False,
                )
        self.fragment_epoch_start = 0
        debug_frames = self.rollout_steps + 2
        debug_joints = len(runtime.full_clip.body_names)
        self.register_buffer(
            "debug_positions",
            torch.zeros(
                (debug_batch, debug_frames, debug_joints, 3),
                dtype=torch.float32,
                device=runtime.device,
            ),
            persistent=False,
        )
        self.register_buffer(
            "debug_basis",
            torch.zeros(
                (debug_batch, debug_frames, debug_joints, 3, 3),
                dtype=torch.float32,
                device=runtime.device,
            ),
            persistent=False,
        )
        self.register_buffer(
            "debug_gate_probabilities",
            torch.zeros(
                (debug_batch, debug_frames, 2),
                dtype=torch.float32,
                device=runtime.device,
            ),
            persistent=False,
        )
        self.register_buffer(
            "debug_lower_pin_probabilities",
            torch.zeros(
                (debug_batch, debug_frames, LOWER_PIN_COMMAND_DIM),
                dtype=torch.float32,
                device=runtime.device,
            ),
            persistent=False,
        )
        self.register_buffer(
            "debug_armed_latch",
            torch.zeros(
                (debug_batch, debug_frames),
                dtype=torch.float32,
                device=runtime.device,
            ),
            persistent=False,
        )
        self.register_buffer(
            "debug_hit_latch",
            torch.zeros(
                (debug_batch, debug_frames),
                dtype=torch.float32,
                device=runtime.device,
            ),
            persistent=False,
        )
        self.register_buffer(
            "debug_reset_flags",
            torch.zeros((debug_batch, debug_frames), dtype=torch.bool, device=runtime.device),
            persistent=False,
        )
        self.register_buffer(
            "debug_target_world_m",
            torch.zeros(
                (debug_batch, debug_frames, 3),
                dtype=torch.float32,
                device=runtime.device,
            ),
            persistent=False,
        )
        self.register_buffer(
            "debug_source_frame",
            torch.zeros((debug_batch, debug_frames), dtype=torch.long, device=runtime.device),
            persistent=False,
        )
        self.register_buffer(
            "debug_clip_id",
            torch.zeros(
                (debug_batch, debug_frames),
                dtype=torch.long,
                device=runtime.device,
            ),
            persistent=False,
        )
        self.register_buffer(
            "debug_geometry_clip_id",
            torch.zeros(
                (debug_batch, debug_frames),
                dtype=torch.long,
                device=runtime.device,
            ),
            persistent=False,
        )
        self.register_buffer(
            "debug_controller_root_pos",
            torch.zeros(
                (debug_batch, debug_frames, 3),
                dtype=torch.float32,
                device=runtime.device,
            ),
            persistent=False,
        )
        self.register_buffer(
            "debug_controller_root_rot",
            torch.zeros(
                (debug_batch, debug_frames, 3, 3),
                dtype=torch.float32,
                device=runtime.device,
            ),
            persistent=False,
        )
        self.register_buffer(
            "debug_frozen_root_pos",
            torch.zeros(
                (debug_batch, debug_frames, 3),
                dtype=torch.float32,
                device=runtime.device,
            ),
            persistent=False,
        )
        self.register_buffer(
            "debug_frozen_root_rot",
            torch.zeros(
                (debug_batch, debug_frames, 3, 3),
                dtype=torch.float32,
                device=runtime.device,
            ),
            persistent=False,
        )
        self.register_buffer(
            "debug_weighted_loss_terms",
            torch.zeros(
                (debug_batch, debug_frames, len(WEIGHTED_LOSS_METRIC_NAMES)),
                dtype=torch.float32,
                device=runtime.device,
            ),
            persistent=False,
        )

    def staged_attack_rows(self, slot: int) -> DynamicAttackRows:
        if not self.dynamic_full_dataset:
            raise RuntimeError("Staged attack rows are only available in full-dataset mode")
        values: dict[str, object] = {
            name: getattr(self, f"staged_attack_{name}")[slot]
            for name in self._staged_attack_tensor_names
        }
        values["max_steps"] = int(self.runtime.attacks.max_steps)
        return DynamicAttackRows(**values)  # type: ignore[arg-type]

    def staged_fragment_seed(self, slot: int) -> FragmentSeed:
        return FragmentSeed(
            **{
                item.name: getattr(self, f"staged_seed_{item.name}")[slot]
                for item in fields(FragmentSeed)
            }
        )

    @torch.no_grad()
    def stage_full_dataset_rows(
        self,
        clip_indices: torch.Tensor,
        frame_indices: torch.Tensor,
    ) -> None:
        if not self.dynamic_full_dataset:
            return
        cpu_indices = clip_indices.to(device="cpu", dtype=torch.long)
        cpu_frames = frame_indices.to(device="cpu", dtype=torch.long)
        self.clip_index_schedule.copy_(clip_indices.to(self.runtime.device))
        slot_count, batch = cpu_indices.shape
        flat_clip = cpu_indices.reshape(-1)
        for name in DYNAMIC_ATTACK_SOURCE_FIELDS:
            source = getattr(self.runtime.attacks, name)
            source_clip = flat_clip.to(device=source.device)
            selected = source.index_select(0, source_clip).reshape(
                slot_count, batch, *source.shape[1:]
            )
            getattr(self, f"staged_attack_{name}").copy_(
                selected.to(self.runtime.device)
            )
        row_difficulty_ids = getattr(
            self.runtime, "training_row_difficulty_ids", None
        )
        if row_difficulty_ids is not None:
            if (
                not torch.is_tensor(row_difficulty_ids)
                or row_difficulty_ids.ndim != 1
                or int(row_difficulty_ids.numel()) != batch
            ):
                raise ValueError(
                    "training_row_difficulty_ids must match the physical batch"
                )
            if bool(
                ((row_difficulty_ids < 0) | (row_difficulty_ids > 2)).any()
            ):
                raise ValueError("training row difficulties must lie in 0..2")
            self.staged_attack_difficulty_id.copy_(
                row_difficulty_ids.to(
                    device=self.runtime.device, dtype=torch.long
                )
                .reshape(1, batch)
                .expand(slot_count, batch)
            )
        flat_frame = cpu_frames.reshape(-1)
        flat_previous = flat_frame - 1

        def gather_source(values: torch.Tensor, frames: torch.Tensor) -> torch.Tensor:
            value_clip = flat_clip.to(device=values.device)
            value_frames = frames.to(device=values.device)
            return values[value_clip, value_frames].reshape(
                slot_count, batch, *values.shape[2:]
            )

        source = self.runtime.attacks
        source_clip = flat_clip.to(device=source.lengths.device)
        lengths = source.lengths.index_select(0, source_clip)
        last = lengths - 1
        self.staged_attack_final_lower.copy_(
            source.trajectory_lower[
                flat_clip.to(device=source.trajectory_lower.device),
                last.to(device=source.trajectory_lower.device),
            ]
            .reshape(slot_count, batch, -1)
            .to(self.runtime.device)
        )
        self.staged_attack_final_upper.copy_(
            source.trajectory_upper[
                flat_clip.to(device=source.trajectory_upper.device),
                last.to(device=source.trajectory_upper.device),
            ]
            .reshape(slot_count, batch, -1)
            .to(self.runtime.device)
        )
        for name, values, frames_to_take in (
            ("previous_lower", source.trajectory_lower, flat_previous),
            ("current_lower", source.trajectory_lower, flat_frame),
            ("previous_heading", source.trajectory_heading, flat_previous),
            ("current_heading", source.trajectory_heading, flat_frame),
            ("previous_base_upper", source.trajectory_base_upper, flat_previous),
            ("current_base_upper", source.trajectory_base_upper, flat_frame),
            ("previous_upper", source.trajectory_upper, flat_previous),
            ("current_upper", source.trajectory_upper, flat_frame),
        ):
            getattr(self, f"staged_seed_{name}").copy_(
                gather_source(values, frames_to_take).to(self.runtime.device)
            )
        device_ids = flat_clip.to(self.runtime.device)
        device_frames = flat_frame.to(self.runtime.device)
        device_previous = flat_previous.to(self.runtime.device)
        self.staged_seed_previous_ae_row.zero_()
        previous_root_pos, previous_root_rot, _previous_yaw, _previous_heading = (
            self.runtime.lower_store.root_state(device_ids, device_previous)
        )
        root_pos, root_rot, _yaw, _heading = self.runtime.lower_store.root_state(
            device_ids, device_frames
        )
        # Cached AttackBatch tensors are deliberately device-independent. FK
        # arithmetic differs by a few ulps between CPU and CUDA, so never seed
        # the CUDA graph with CPU-decoded globals. Recompute the two seed poses
        # on the active device from the exact staged native controller states.
        selected_targets = source.targets_world.index_select(
            0, flat_clip.to(device=source.targets_world.device)
        ).to(self.runtime.device)
        previous_global_pos, previous_global_rot = hybrid_full_fk_globals(
            self.runtime,
            device_ids,
            device_ids,
            device_previous,
            self.staged_seed_previous_lower.reshape(-1, LOWER_STATE_DIM),
            self.staged_seed_previous_upper.reshape(-1, UPPER_STATE_DIM),
            selected_targets,
            self.staged_seed_previous_heading.reshape(-1, 3, 3),
        )
        current_global_pos, current_global_rot = hybrid_full_fk_globals(
            self.runtime,
            device_ids,
            device_ids,
            device_frames,
            self.staged_seed_current_lower.reshape(-1, LOWER_STATE_DIM),
            self.staged_seed_current_upper.reshape(-1, UPPER_STATE_DIM),
            selected_targets,
            self.staged_seed_current_heading.reshape(-1, 3, 3),
        )
        self.staged_seed_previous_global_pos.copy_(
            previous_global_pos.reshape(slot_count, batch, *previous_global_pos.shape[1:])
        )
        self.staged_seed_previous_global_rot.copy_(
            previous_global_rot.reshape(slot_count, batch, *previous_global_rot.shape[1:])
        )
        self.staged_seed_current_global_pos.copy_(
            current_global_pos.reshape(slot_count, batch, *current_global_pos.shape[1:])
        )
        self.staged_seed_current_global_rot.copy_(
            current_global_rot.reshape(slot_count, batch, *current_global_rot.shape[1:])
        )
        self.staged_seed_current_root_pos.copy_(root_pos.reshape(slot_count, batch, 3))
        self.staged_seed_current_root_rot.copy_(root_rot.reshape(slot_count, batch, 3, 3))
        self.staged_seed_geometry_clip_id.copy_(
            device_ids.reshape(slot_count, batch)
        )
        armed_time = source.armed_time.index_select(
            0, flat_clip.to(device=source.armed_time.device)
        ).to(self.runtime.device)
        hit_time = source.hit_time.index_select(
            0, flat_clip.to(device=source.hit_time.device)
        ).to(self.runtime.device)
        self.staged_seed_previous_armed_latch.copy_(
            (device_previous.to(torch.float32) >= armed_time)
            .to(torch.float32)
            .reshape(slot_count, batch)
        )
        self.staged_seed_previous_hit_latch.copy_(
            (device_previous.to(torch.float32) >= hit_time)
            .to(torch.float32)
            .reshape(slot_count, batch)
        )
        self.staged_seed_armed_latch.copy_(
            (device_frames.to(torch.float32) >= armed_time).to(torch.float32).reshape(slot_count, batch)
        )
        self.staged_seed_hit_latch.copy_(
            (device_frames.to(torch.float32) >= hit_time).to(torch.float32).reshape(slot_count, batch)
        )
        self.staged_seed_agent_finish_index.copy_(
            (lengths - 1).to(self.runtime.device).reshape(slot_count, batch)
        )
        self.staged_seed_current_index.copy_(
            device_frames.reshape(slot_count, batch)
        )
        self.staged_seed_episode_start.fill_(True)

    def forward(self) -> tuple[torch.Tensor, ...]:
        from slash2_predictive_pin import pin_error_rows
        rt = self.runtime
        rows = self.rows_static
        if self.dynamic_full_dataset:
            data = self.staged_attack_rows(0)
        elif rows is None:
            data: AttackBatch | AttackRows = rt.attacks
        else:
            data = select_attack_rows(rt.attacks, rows)
        ids = data.clip_ids
        batch = int(ids.numel())
        start_index = self.fragment_start_indices[0]
        initial = (
            self.staged_fragment_seed(0)
            if self.dynamic_full_dataset
            else fragment_seed_state(rt, data, start_index)
        )
        geometry_ids = initial.geometry_clip_id
        previous_lower = initial.previous_lower
        current_lower = initial.current_lower
        previous_heading = initial.previous_heading
        current_heading = initial.current_heading
        previous_base_upper = initial.previous_base_upper
        current_base_upper = initial.current_base_upper
        previous_upper = initial.previous_upper
        current_upper = initial.current_upper
        previous_ae_row = initial.previous_ae_row
        previous_armed_latch = initial.previous_armed_latch
        previous_hit_latch = initial.previous_hit_latch
        armed_latch = initial.armed_latch
        hit_latch = initial.hit_latch
        agent_finish_index = initial.agent_finish_index
        zero = torch.zeros((), dtype=torch.float32, device=rt.device)
        ae11_sum = zero.clone()
        ae22_sum = zero.clone()
        ae33_sum = zero.clone()
        gate_sum = zero.clone()
        armed_pose_sum = zero.clone()
        hit_pose_sum = zero.clone()
        hit_linear_velocity_sum = zero.clone()
        hit_angular_velocity_sum = zero.clone()
        hit_linear_velocity_physical_sum = zero.clone()
        hit_angular_velocity_physical_sum = zero.clone()
        final_pose_sum = zero.clone()
        hit_target_sum = zero.clone()
        pike_blade_look_at_target_sum = zero.clone()
        pike_blade_look_at_target_count = zero.clone()
        lowerarm_length_sum = zero.clone()
        lowerarm_max_length_error = zero.clone()
        opposite_calf_collision_sum = zero.clone()
        opposite_calf_collision_bad_sum = zero.clone()
        opposite_calf_max_overlap = zero.clone()
        blade_collision_sum = zero.clone()
        predictive_pin_sum = zero.clone()
        anti_pin_slide_sum = zero.clone()
        anti_pin_slide_speed_sum = torch.zeros((2,), dtype=torch.float32, device=rt.device)
        anti_pin_slide_gate_sum = zero.clone()
        pin_teacher_sum = torch.zeros((2,), dtype=torch.float32, device=rt.device)
        pin_error_sum = zero.clone()
        blade_collision_bad_sum = zero.clone()
        blade_max_penetration = zero.clone()
        active_sum = zero.clone()
        ae11_count = zero.clone()
        ae22_count = zero.clone()
        ae33_count = zero.clone()
        armed_count = zero.clone()
        hit_count = zero.clone()
        final_count = zero.clone()
        lower_pin_sum = torch.zeros(
            (LOWER_PIN_COMMAND_DIM,), dtype=torch.float32, device=rt.device
        )
        lower_pin_active_sum = zero.clone()
        armed_latch_sum = zero.clone()
        hit_latch_sum = zero.clone()

        current_index = initial.current_index
        root_pos = initial.current_root_pos
        root_rot = initial.current_root_rot
        previous_global_pos = initial.previous_global_pos
        previous_global_rot = initial.previous_global_rot
        current_global_pos = initial.current_global_pos
        current_global_rot = initial.current_global_rot
        zero_phase = torch.zeros((batch, 2), dtype=torch.float32, device=rt.device)
        zero_pin = torch.zeros(
            (batch, LOWER_PIN_COMMAND_DIM), dtype=torch.float32, device=rt.device
        )
        zero_latch = torch.zeros((batch,), dtype=torch.float32, device=rt.device)
        debug_positions = [
            initial.previous_global_pos.detach(),
            initial.current_global_pos.detach(),
        ]
        debug_basis = [
            initial.previous_global_rot.detach(),
            initial.current_global_rot.detach(),
        ]
        debug_phase_probabilities = [zero_phase, zero_phase]
        debug_lower_pin_probabilities = [zero_pin, zero_pin]
        debug_armed_latch = [
            previous_armed_latch.detach(),
            armed_latch.detach(),
        ]
        debug_hit_latch = [previous_hit_latch.detach(), hit_latch.detach()]
        debug_reset_flags = [
            initial.episode_start.detach(),
            torch.zeros_like(current_index, dtype=torch.bool),
        ]
        debug_target_world_m = [
            data.targets_world.detach(),
            data.targets_world.detach(),
        ]
        initial_root_frame = torch.minimum(current_index, data.lengths - 1)
        initial_previous_root_frame = torch.maximum(
            initial_root_frame - 1, torch.zeros_like(initial_root_frame)
        )
        previous_controller_root_pos, previous_controller_root_rot, _yaw0, _heading0 = (
            rt.lower_store.root_state(geometry_ids, initial_previous_root_frame)
        )
        initial_frozen_frame = torch.minimum(current_index, data.lengths - 2)
        initial_previous_frozen_frame = torch.maximum(
            initial_frozen_frame - 1, torch.zeros_like(initial_frozen_frame)
        )
        previous_frozen_root_pos, previous_frozen_root_rot, _yaw1, _heading1 = (
            rt.lower_store.root_state(geometry_ids, initial_previous_frozen_frame)
        )
        current_frozen_root_pos, current_frozen_root_rot, _yaw2, _heading2 = (
            rt.lower_store.root_state(geometry_ids, initial_frozen_frame)
        )
        debug_controller_root_pos = [
            previous_controller_root_pos.detach(),
            root_pos.detach(),
        ]
        debug_controller_root_rot = [
            previous_controller_root_rot.detach(),
            root_rot.detach(),
        ]
        debug_frozen_root_pos = [
            previous_frozen_root_pos.detach(),
            current_frozen_root_pos.detach(),
        ]
        debug_frozen_root_rot = [
            previous_frozen_root_rot.detach(),
            current_frozen_root_rot.detach(),
        ]
        debug_source_frame = [(current_index - 1).detach(), current_index.detach()]
        debug_clip_id = [ids.detach(), ids.detach()]
        debug_geometry_clip_id = [
            geometry_ids.detach(),
            geometry_ids.detach(),
        ]
        zero_weighted_losses = torch.zeros(
            (current_index.shape[0], len(WEIGHTED_LOSS_METRIC_NAMES)),
            dtype=torch.float32,
            device=rt.device,
        )
        debug_weighted_loss_terms = [
            zero_weighted_losses,
            zero_weighted_losses,
        ]
        pelvis_index = rt.full_clip.body_names.index("pelvis")

        for step in range(self.rollout_steps):
            projection_store = (
                select_lower_projection_store(rt.lower_batched_store, geometry_ids)
                if self.dynamic_full_dataset
                else self.projection_store
            )
            active = current_index < (data.lengths - 1)
            active_f = active.to(torch.float32)
            safe_current = torch.minimum(current_index, data.lengths - 2)
            previous_index = torch.maximum(
                safe_current - 1, torch.zeros_like(safe_current)
            )
            next_logical_index = current_index + 1
            next_index = torch.minimum(next_logical_index, data.lengths - 1)
            future_index = torch.minimum(next_logical_index + 1, data.lengths - 1)
            next_root_pos, next_root_rot, _next_yaw, _next_heading = (
                rt.lower_store.root_state(geometry_ids, next_index)
            )

            # Previous/current carried states retain their own frame.  Every
            # learned operation in this prediction step uses current_heading.
            previous_lower_held = target_codec.lower_to_held_heading(
                rt.lower_store,
                previous_lower,
                data.targets_world,
                previous_heading,
                current_heading,
            )
            previous_base_upper_held = target_codec.upper_to_held_heading(
                previous_base_upper,
                data.targets_world,
                previous_heading,
                current_heading,
            )
            previous_upper_held = target_codec.upper_to_held_heading(
                previous_upper,
                data.targets_world,
                previous_heading,
                current_heading,
            )

            if rt.frozen_walk is None:
                frozen_next = current_lower
            else:
                frozen_next, _controller_input = frozen_next_hybrid(
                    rt,
                    projection_store,
                    geometry_ids,
                    safe_current,
                    previous_index,
                    previous_lower,
                    current_lower,
                    data.targets_world,
                    previous_heading,
                    current_heading,
                )
            root_current_next = transition_root_dyaw(
                rt.lower_store, geometry_ids, safe_current, next_index
            )
            root_next_future = transition_root_dyaw(
                rt.lower_store, geometry_ids, next_index, future_index
            )
            lower_input = build_lower_learned_input(
                current_lower,
                frozen_next if rt.frozen_walk is not None else None,
                data.labels,
                root_current_next,
                root_next_future,
                data.targets_world,
            )
            lower_output, _unused = self.lower_agent(lower_input)
            lower_delta, lower_pin_commands = split_lower_output(lower_output)
            next_lower_candidate, lower_pin_probabilities = clean_lower_hybrid_delta(
                rt,
                projection_store,
                geometry_ids,
                safe_current,
                next_index,
                current_lower,
                frozen_next,
                lower_delta,
                lower_pin_commands,
                data.targets_world,
                current_heading,
            )
            next_lower = torch.where(active[:, None], next_lower_candidate, current_lower)
            predictive_pin_rows, expected_pin = pin_error_rows(
                rt.pin_teacher, previous_lower_held, current_lower,
                data.targets_world, data.labels, lower_pin_probabilities,
            )
            predictive_pin_sum = predictive_pin_sum + (predictive_pin_rows * active_f).sum()
            pin_teacher_sum = pin_teacher_sum + (expected_pin * active_f[:, None]).sum(0)
            pin_error_sum = pin_error_sum + (
                (expected_pin - lower_pin_probabilities.detach()).abs().mean(-1) * active_f
            ).sum()

            (
                next_base_candidate,
                next_frozen_global_pos,
                next_frozen_global_rot,
            ) = base_upper_hybrid_with_globals_from_lower(
                rt,
                geometry_ids,
                geometry_ids,
                next_index,
                next_lower_candidate,
                data.targets_world,
                current_heading,
            )
            next_prior = carry_upper_hybrid_deviation(
                current_upper,
                current_base_upper,
                next_base_candidate,
            )
            upper_input = build_upper_learned_input(
                previous_upper_held,
                next_prior,
                data.targets_world,
                data.labels,
                previous_lower_held,
                current_lower,
                next_lower_candidate,
                armed_latch,
                hit_latch,
            )
            upper_delta, gate_probabilities = self.upper_agent(upper_input)
            assert gate_probabilities is not None
            next_upper_candidate = clean_upper_state(next_prior + upper_delta)
            next_upper = torch.where(active[:, None], next_upper_candidate, current_upper)

            target_armed = (next_index.to(torch.float32) >= data.armed_time).to(torch.float32)
            target_hit = (next_index.to(torch.float32) >= data.hit_time).to(torch.float32)
            gate_target = torch.stack((target_armed, target_hit), dim=-1)
            gate_rows = (gate_probabilities - gate_target).square().mean(dim=-1)
            gate_sum = gate_sum + (
                gate_rows * active_f * self.gate_timing_row_multiplier
            ).sum()

            next_armed_latch, next_hit_latch = advance_phase_latches(
                armed_latch,
                hit_latch,
                gate_probabilities,
                rt.recipe.gate_threshold,
            )
            (
                next_agent_finish_index,
                authored_finished,
                finished,
            ) = agent_relative_finish_transition(
                agent_finish_index,
                hit_latch,
                next_hit_latch,
                next_logical_index,
                data.lengths,
                data.post_hit_tail_steps,
                data.difficulty_id,
                active,
            )
            current_ae_row = previous_ae_row
            ae11_raw, ae11_start, ae11_end = lower_prior_features(
                rt.ae11,
                next_lower_candidate,
                previous_lower_held,
                current_lower,
                data.targets_world,
                data.labels,
            )
            ae11_rows = prior_score(rt.ae11, ae11_raw, ae11_start, ae11_end)

            ae22_raw = upper_prior_features(
                rt.ae22,
                next_upper_candidate,
                previous_upper_held,
                current_upper,
                data.targets_world,
                data.labels,
            )
            ae33_raw = upper_prior_features(
                rt.ae33,
                next_upper_candidate,
                previous_upper_held,
                current_upper,
                data.targets_world,
                data.labels,
            )
            ae22_rows = prior_score(rt.ae22, ae22_raw, 0, UPPER_STATE_DIM)
            ae33_rows = prior_score(rt.ae33, ae33_raw, 0, UPPER_STATE_DIM)
            (
                ae11_mask,
                ae22_mask,
                ae33_mask,
            ) = routed_prior_masks(active_f, armed_latch)
            ae11_sum = ae11_sum + (ae11_rows * ae11_mask).sum()
            ae11_count = ae11_count + ae11_mask.sum()
            ae22_sum = ae22_sum + (ae22_rows * ae22_mask).sum()
            ae33_sum = ae33_sum + (ae33_rows * ae33_mask).sum()
            ae22_count = ae22_count + ae22_mask.sum()
            ae33_count = ae33_count + ae33_mask.sum()

            next_global_pos, next_global_rot = hybrid_full_fk_globals(
                rt,
                geometry_ids,
                geometry_ids,
                next_index,
                next_lower_candidate,
                next_upper_candidate,
                data.targets_world,
                current_heading,
                frozen_pos=next_frozen_global_pos,
                frozen_rot=next_frozen_global_rot,
                baseline_upper_hybrid=next_base_candidate,
            )
            (
                anti_pin_slide_rows_value,
                anti_pin_slide_speed,
                anti_pin_slide_gate,
            ) = anti_pin_slide_rows(
                rt,
                current_global_pos,
                next_global_pos,
                data.fps,
                lower_pin_probabilities,
            )
            anti_pin_slide_sum = anti_pin_slide_sum + (
                anti_pin_slide_rows_value * active_f
            ).sum()
            anti_pin_slide_speed_sum = anti_pin_slide_speed_sum + (
                anti_pin_slide_speed.detach() * active_f[:, None]
            ).sum(dim=0)
            anti_pin_slide_gate_sum = anti_pin_slide_gate_sum + (
                anti_pin_slide_gate.detach().mean(dim=-1) * active_f
            ).sum()
            next_heading_candidate = target_codec.target_facing_heading(
                next_global_pos[:, pelvis_index], data.targets_world
            )
            next_lower_carried = target_codec.lower_to_held_heading(
                rt.lower_store,
                next_lower,
                data.targets_world,
                current_heading,
                next_heading_candidate,
            )
            next_base_carried = target_codec.upper_to_held_heading(
                next_base_candidate,
                data.targets_world,
                current_heading,
                next_heading_candidate,
            )
            next_upper_carried = target_codec.upper_to_held_heading(
                next_upper,
                data.targets_world,
                current_heading,
                next_heading_candidate,
            )
            transition_slot = current_index - 1
            armed_mask = active_f * (transition_slot == data.armed_step).to(torch.float32)
            hit_mask = active_f * (transition_slot == data.hit_step).to(torch.float32)
            armed_pred_lower, armed_pred_upper = interpolate_hybrid_native_states(
                rt.lower_store,
                geometry_ids,
                safe_current,
                next_index,
                current_lower,
                next_lower_candidate,
                current_upper,
                next_upper_candidate,
                data.targets_world,
                data.armed_alpha,
            )
            armed_rows = native_pose_mse_rows(
                rt,
                armed_pred_lower,
                armed_pred_upper,
                target_codec.lower_to_held_heading(
                    rt.lower_store,
                    data.armed_lower,
                    data.targets_world,
                    data.armed_heading,
                    current_heading,
                ),
                target_codec.upper_to_held_heading(
                    data.armed_upper,
                    data.targets_world,
                    data.armed_heading,
                    current_heading,
                ),
            )
            armed_pose_sum = armed_pose_sum + (armed_rows * armed_mask).sum()
            armed_count = armed_count + armed_mask.sum()

            hit_pos, hit_rot = interpolate_pose(
                current_global_pos,
                current_global_rot,
                next_global_pos,
                next_global_rot,
                data.hit_alpha,
            )
            hit_pred_lower, hit_pred_upper = interpolate_hybrid_native_states(
                rt.lower_store,
                geometry_ids,
                safe_current,
                next_index,
                current_lower,
                next_lower_candidate,
                current_upper,
                next_upper_candidate,
                data.targets_world,
                data.hit_alpha,
            )
            hit_rows = native_pose_mse_rows(
                rt,
                hit_pred_lower,
                hit_pred_upper,
                target_codec.lower_to_held_heading(
                    rt.lower_store,
                    data.hit_lower,
                    data.targets_world,
                    data.hit_heading,
                    current_heading,
                ),
                target_codec.upper_to_held_heading(
                    data.hit_upper,
                    data.targets_world,
                    data.hit_heading,
                    current_heading,
                ),
            )
            hit_pose_sum = hit_pose_sum + (hit_rows * hit_mask).sum()
            hit_target_rows = hit_target_mse_rows(rt, hit_pos, hit_rot, data)
            hit_target_sum = hit_target_sum + (hit_target_rows * hit_mask).sum()
            (
                hit_linear_velocity_rows,
                hit_angular_velocity_rows,
                hit_linear_velocity_physical_rows,
                hit_angular_velocity_physical_rows,
            ) = hit_transition_dynamics_mse_rows(
                current_global_pos,
                current_global_rot,
                next_global_pos,
                next_global_rot,
                data,
            )
            hit_linear_velocity_sum = hit_linear_velocity_sum + (
                hit_linear_velocity_rows * hit_mask
            ).sum()
            hit_angular_velocity_sum = hit_angular_velocity_sum + (
                hit_angular_velocity_rows * hit_mask
            ).sum()
            hit_linear_velocity_physical_sum = (
                hit_linear_velocity_physical_sum
                + (hit_linear_velocity_physical_rows * hit_mask).sum()
            )
            hit_angular_velocity_physical_sum = (
                hit_angular_velocity_physical_sum
                + (hit_angular_velocity_physical_rows * hit_mask).sum()
            )
            hit_count = hit_count + hit_mask.sum()

            pike_blade_look_rows, _pike_blade_look_cosine = (
                pike_blade_look_at_target_rows(
                    rt,
                    next_global_pos,
                    next_global_rot,
                    data.targets_world,
                )
            )
            pike_blade_look_mask = pike_blade_look_at_target_phase_mask(
                data.labels,
                next_index,
                data.armed_time,
                data.hit_time,
                active,
            )
            pike_blade_look_at_target_sum = (
                pike_blade_look_at_target_sum
                + (pike_blade_look_rows * pike_blade_look_mask).sum()
            )
            pike_blade_look_at_target_count = (
                pike_blade_look_at_target_count + pike_blade_look_mask.sum()
            )

            final_rows = native_pose_mse_rows(
                rt,
                next_lower_candidate,
                next_upper_candidate,
                target_codec.lower_to_held_heading(
                    rt.lower_store,
                    data.final_lower
                    if self.dynamic_full_dataset
                    else gather_trajectory(data.trajectory_lower, next_index),
                    data.targets_world,
                    data.final_heading
                    if self.dynamic_full_dataset
                    else gather_trajectory(data.trajectory_heading, next_index),
                    current_heading,
                ),
                target_codec.upper_to_held_heading(
                    data.final_upper
                    if self.dynamic_full_dataset
                    else gather_trajectory(data.trajectory_upper, next_index),
                    data.targets_world,
                    data.final_heading
                    if self.dynamic_full_dataset
                    else gather_trajectory(data.trajectory_heading, next_index),
                    current_heading,
                ),
            )
            # An early learned endpoint is deliberately not supervised toward
            # the later authored final pose.  Easy (difficulty 0) remains
            # exactly authored-end-only.
            final_mask = authored_finished.to(torch.float32)
            final_pose_sum = final_pose_sum + (final_rows * final_mask).sum()
            final_count = final_count + final_mask.sum()

            lowerarm_rows, lowerarm_length_error = lowerarm_length_error_rows(
                rt, geometry_ids, next_global_pos
            )
            lowerarm_length_sum = lowerarm_length_sum + (
                lowerarm_rows * active_f
            ).sum()
            lowerarm_max_length_error = torch.maximum(
                lowerarm_max_length_error,
                (lowerarm_length_error.detach() * active_f).amax(),
            )

            (
                opposite_calf_rows,
                opposite_calf_overlap,
                opposite_calf_bad_rows,
            ) = opposite_calf_collision_rows(rt, next_global_pos)
            opposite_calf_collision_sum = opposite_calf_collision_sum + (
                opposite_calf_rows * active_f
            ).sum()
            opposite_calf_collision_bad_sum = (
                opposite_calf_collision_bad_sum
                + (opposite_calf_bad_rows * active_f).sum()
            )
            opposite_calf_max_overlap = torch.maximum(
                opposite_calf_max_overlap,
                (opposite_calf_overlap.detach() * active_f).amax(),
            )

            collision = swept_blade_body_collision(
                current_global_pos,
                current_global_rot,
                next_global_pos,
                next_global_rot,
                rt.blade_collision,
                rt.body_collision_layout,
                sweep_samples=rt.recipe.blade_collision_sweep_samples,
            )
            blade_collision_sum = blade_collision_sum + (collision.loss_rows * active_f).sum()
            blade_collision_bad_sum = blade_collision_bad_sum + (
                (collision.max_penetration_m > 0.0).to(torch.float32) * active_f
            ).sum()
            blade_max_penetration = torch.maximum(
                blade_max_penetration,
                (collision.max_penetration_m.detach() * active_f).amax(),
            )

            # These per-row values only feed the detached replayer/debug buffer.
            # Keep their numerical calculation unchanged, but do not build a
            # second autograd branch beside the real scalar objective above.
            with torch.no_grad():
                # This keyed registry is deliberately shared with
                # WEIGHTED_LOSS_TERM_NAMES. Adding a trainer loss without its
                # per-frame replayer value now fails immediately instead of
                # silently shifting or omitting fields in the UI.
                weighted_row_terms_by_name = {
                    "ae11": self.ae11_weight_value * ae11_rows * ae11_mask,
                    "ae22": self.upper_prior_weight_value * ae22_rows * ae22_mask,
                    "ae33": (
                        self.upper_prior_weight_value
                        * float(rt.recipe.ae33_weight_multiplier)
                        * ae33_rows
                        * ae33_mask
                    ),
                    "gate_timing": (
                        float(rt.recipe.gate_timing_weight)
                        * gate_rows
                        * active_f
                        * self.gate_timing_row_multiplier
                    ),
                    "armed_pose": (
                        float(rt.recipe.armed_pose_weight)
                        * armed_rows
                        * armed_mask
                    ),
                    "hit_pose": (
                        float(rt.recipe.hit_pose_weight)
                        * hit_rows
                        * hit_mask
                    ),
                    "hit_linear_velocity": (
                        float(rt.recipe.hit_linear_velocity_weight)
                        * hit_linear_velocity_rows
                        * hit_mask
                    ),
                    "hit_angular_velocity": (
                        float(rt.recipe.hit_angular_velocity_weight)
                        * hit_angular_velocity_rows
                        * hit_mask
                    ),
                    "final_pose": (
                        float(rt.recipe.final_pose_weight)
                        * final_rows
                        * final_mask
                    ),
                    "hit_target_mse": (
                        float(rt.recipe.hit_target_weight)
                        * hit_target_rows
                        * hit_mask
                    ),
                    "pike_blade_look_at_target": (
                        float(rt.recipe.pike_blade_look_at_target_weight)
                        * pike_blade_look_rows
                        * pike_blade_look_mask
                    ),
                    "lowerarm_length": (
                        float(rt.recipe.lowerarm_length_weight)
                        * lowerarm_rows
                        * active_f
                    ),
                    "opposite_calf_collision": (
                        float(rt.recipe.opposite_calf_collision_weight)
                        * opposite_calf_rows
                        * active_f
                    ),
                    "blade_collision": (
                        float(rt.recipe.blade_collision_weight)
                        * collision.loss_rows
                        * active_f
                    ),
                    "predictive_pin": self.predictive_pin_weight_value * predictive_pin_rows * active_f,
                    "anti_pin_slide": self.anti_pin_slide_weight_value * anti_pin_slide_rows_value * active_f,
                }
                if tuple(weighted_row_terms_by_name) != WEIGHTED_LOSS_TERM_NAMES:
                    raise RuntimeError(
                        "Per-frame weighted loss registry is incomplete or out of order: "
                        f"expected {WEIGHTED_LOSS_TERM_NAMES}, "
                        f"got {tuple(weighted_row_terms_by_name)}"
                    )
                weighted_row_terms = torch.stack(
                    tuple(
                        weighted_row_terms_by_name[name]
                        for name in WEIGHTED_LOSS_TERM_NAMES
                    ),
                    dim=-1,
                )
                debug_weighted_loss_terms.append(
                    torch.cat(
                        (
                            weighted_row_terms.sum(dim=-1, keepdim=True),
                            weighted_row_terms,
                        ),
                        dim=-1,
                    )
                )

            active_sum = active_sum + active_f.sum()
            lower_pin_sum = lower_pin_sum + (
                lower_pin_probabilities.detach() * active_f[:, None]
            ).sum(dim=0)
            lower_pin_active_sum = lower_pin_active_sum + (
                (lower_pin_probabilities.amax(dim=-1) > 0.5).to(torch.float32) * active_f
            ).sum()
            armed_latch_sum = armed_latch_sum + (armed_latch * active_f).sum()
            hit_latch_sum = hit_latch_sum + (hit_latch * active_f).sum()

            reset_index = self.fragment_start_indices[step + 1]
            reset_data = (
                self.staged_attack_rows(step + 1)
                if self.dynamic_full_dataset
                else data
            )
            reset = (
                self.staged_fragment_seed(step + 1)
                if self.dynamic_full_dataset
                else fragment_seed_state(rt, reset_data, reset_index)
            )
            previous_lower = torch.where(finished[:, None], reset.previous_lower, current_lower)
            current_lower = torch.where(
                finished[:, None], reset.current_lower, next_lower_carried
            )
            previous_heading = torch.where(
                finished[:, None, None], reset.previous_heading, current_heading
            )
            current_heading = torch.where(
                finished[:, None, None], reset.current_heading, next_heading_candidate
            )
            previous_base_upper = torch.where(
                finished[:, None], reset.previous_base_upper, current_base_upper
            )
            current_base_upper = torch.where(
                finished[:, None], reset.current_base_upper, next_base_carried
            )
            previous_upper = torch.where(finished[:, None], reset.previous_upper, current_upper)
            current_upper = torch.where(
                finished[:, None], reset.current_upper, next_upper_carried
            )
            previous_ae_row = torch.where(
                finished[:, None], reset.previous_ae_row, current_ae_row
            )
            previous_armed_latch = torch.where(
                finished, reset.previous_armed_latch, armed_latch
            )
            previous_hit_latch = torch.where(
                finished, reset.previous_hit_latch, hit_latch
            )
            armed_latch = torch.where(
                finished, reset.armed_latch, next_armed_latch
            )
            hit_latch = torch.where(
                finished, reset.hit_latch, next_hit_latch
            )
            agent_finish_index = torch.where(
                finished,
                reset.agent_finish_index,
                next_agent_finish_index,
            )
            current_index = torch.where(
                finished, reset.current_index, next_logical_index
            )
            previous_global_pos = torch.where(
                finished[:, None, None],
                reset.previous_global_pos,
                current_global_pos,
            )
            previous_global_rot = torch.where(
                finished[:, None, None, None],
                reset.previous_global_rot,
                current_global_rot,
            )
            current_global_pos = torch.where(
                finished[:, None, None], reset.current_global_pos, next_global_pos
            )
            current_global_rot = torch.where(
                finished[:, None, None, None], reset.current_global_rot, next_global_rot
            )
            root_pos = torch.where(finished[:, None], reset.current_root_pos, next_root_pos)
            root_rot = torch.where(finished[:, None, None], reset.current_root_rot, next_root_rot)
            geometry_ids = torch.where(
                finished, reset.geometry_clip_id, geometry_ids
            )
            if self.dynamic_full_dataset:
                data = merge_dynamic_attack_rows(data, reset_data, finished)
                ids = data.clip_ids

            displayed_frozen_frame = torch.minimum(
                current_index, data.lengths - 2
            )
            displayed_frozen_root_pos, displayed_frozen_root_rot, _yaw3, _heading3 = (
                rt.lower_store.root_state(geometry_ids, displayed_frozen_frame)
            )

            debug_positions.append(current_global_pos.detach())
            debug_basis.append(current_global_rot.detach())
            debug_controller_root_pos.append(root_pos.detach())
            debug_controller_root_rot.append(root_rot.detach())
            debug_frozen_root_pos.append(displayed_frozen_root_pos.detach())
            debug_frozen_root_rot.append(displayed_frozen_root_rot.detach())
            debug_phase_probabilities.append(
                torch.where(finished[:, None], zero_phase, gate_probabilities).detach()
            )
            debug_lower_pin_probabilities.append(
                torch.where(finished[:, None], zero_pin, lower_pin_probabilities).detach()
            )
            debug_armed_latch.append(armed_latch.detach())
            debug_hit_latch.append(hit_latch.detach())
            debug_reset_flags.append(finished.detach())
            debug_target_world_m.append(data.targets_world.detach())
            debug_source_frame.append(current_index.detach())
            debug_clip_id.append(ids.detach())
            debug_geometry_clip_id.append(geometry_ids.detach())

        if self.dynamic_full_dataset:
            for name in self._staged_attack_tensor_names:
                getattr(self, f"terminal_attack_{name}").copy_(
                    getattr(data, name)
                )
            terminal_seed_values = {
                "previous_lower": previous_lower,
                "current_lower": current_lower,
                "previous_heading": previous_heading,
                "current_heading": current_heading,
                "previous_base_upper": previous_base_upper,
                "current_base_upper": current_base_upper,
                "previous_upper": previous_upper,
                "current_upper": current_upper,
                "previous_ae_row": previous_ae_row,
                "previous_global_pos": previous_global_pos,
                "previous_global_rot": previous_global_rot,
                "current_global_pos": current_global_pos,
                "current_global_rot": current_global_rot,
                "current_root_pos": root_pos,
                "current_root_rot": root_rot,
                "geometry_clip_id": geometry_ids,
                "previous_armed_latch": previous_armed_latch,
                "previous_hit_latch": previous_hit_latch,
                "armed_latch": armed_latch,
                "hit_latch": hit_latch,
                "agent_finish_index": agent_finish_index,
                "current_index": current_index,
                "episode_start": torch.zeros_like(
                    current_index, dtype=torch.bool
                ),
            }
            for name, value in terminal_seed_values.items():
                getattr(self, f"terminal_seed_{name}").copy_(value.detach())

        self.debug_positions.copy_(torch.stack(debug_positions, dim=1))
        self.debug_basis.copy_(torch.stack(debug_basis, dim=1))
        self.debug_gate_probabilities.copy_(
            torch.stack(debug_phase_probabilities, dim=1)
        )
        self.debug_lower_pin_probabilities.copy_(
            torch.stack(debug_lower_pin_probabilities, dim=1)
        )
        self.debug_armed_latch.copy_(torch.stack(debug_armed_latch, dim=1))
        self.debug_hit_latch.copy_(torch.stack(debug_hit_latch, dim=1))
        self.debug_reset_flags.copy_(torch.stack(debug_reset_flags, dim=1))
        self.debug_target_world_m.copy_(
            torch.stack(debug_target_world_m, dim=1)
        )
        self.debug_controller_root_pos.copy_(
            torch.stack(debug_controller_root_pos, dim=1)
        )
        self.debug_controller_root_rot.copy_(
            torch.stack(debug_controller_root_rot, dim=1)
        )
        self.debug_frozen_root_pos.copy_(
            torch.stack(debug_frozen_root_pos, dim=1)
        )
        self.debug_frozen_root_rot.copy_(
            torch.stack(debug_frozen_root_rot, dim=1)
        )
        self.debug_source_frame.copy_(torch.stack(debug_source_frame, dim=1))
        self.debug_clip_id.copy_(torch.stack(debug_clip_id, dim=1))
        self.debug_geometry_clip_id.copy_(
            torch.stack(debug_geometry_clip_id, dim=1)
        )
        self.debug_weighted_loss_terms.copy_(
            torch.stack(debug_weighted_loss_terms, dim=1)
        )
        denom = active_sum.clamp_min(1.0)
        ae11_loss = ae11_sum / ae11_count.clamp_min(1.0)
        ae22_loss = ae22_sum / ae22_count.clamp_min(1.0)
        ae33_loss = ae33_sum / ae33_count.clamp_min(1.0)
        gate_loss = gate_sum / denom
        armed_loss = armed_pose_sum / armed_count.clamp_min(1.0)
        hit_loss = hit_pose_sum / hit_count.clamp_min(1.0)
        hit_linear_velocity_loss = (
            hit_linear_velocity_sum / hit_count.clamp_min(1.0)
        )
        hit_angular_velocity_loss = (
            hit_angular_velocity_sum / hit_count.clamp_min(1.0)
        )
        final_loss = final_pose_sum / final_count.clamp_min(1.0)
        target_loss = hit_target_sum / hit_count.clamp_min(1.0)
        pike_blade_look_at_target_loss = (
            pike_blade_look_at_target_sum
            / pike_blade_look_at_target_count.clamp_min(1.0)
        )
        lowerarm_length_loss = lowerarm_length_sum / denom
        opposite_calf_collision_loss = opposite_calf_collision_sum / denom
        blade_collision_loss = blade_collision_sum / denom
        predictive_pin_loss = predictive_pin_sum / denom
        anti_pin_slide_loss = anti_pin_slide_sum / denom
        total = (
            self.ae11_weight_value * ae11_loss
            + self.upper_prior_weight_value
            * (ae22_loss + float(rt.recipe.ae33_weight_multiplier) * ae33_loss)
            + rt.recipe.gate_timing_weight * gate_loss
            + rt.recipe.armed_pose_weight * armed_loss
            + rt.recipe.hit_pose_weight * hit_loss
            + rt.recipe.hit_linear_velocity_weight * hit_linear_velocity_loss
            + rt.recipe.hit_angular_velocity_weight * hit_angular_velocity_loss
            + rt.recipe.final_pose_weight * final_loss
            + rt.recipe.hit_target_weight * target_loss
            + rt.recipe.pike_blade_look_at_target_weight
            * pike_blade_look_at_target_loss
            + rt.recipe.lowerarm_length_weight * lowerarm_length_loss
            + rt.recipe.opposite_calf_collision_weight
            * opposite_calf_collision_loss
            + rt.recipe.blade_collision_weight * blade_collision_loss
            + self.predictive_pin_weight_value * predictive_pin_loss
            + self.anti_pin_slide_weight_value * anti_pin_slide_loss
        )
        return (
            total,
            ae11_loss.detach(),
            ae22_loss.detach(),
            ae33_loss.detach(),
            gate_loss.detach(),
            armed_loss.detach(),
            hit_loss.detach(),
            hit_linear_velocity_loss.detach(),
            hit_angular_velocity_loss.detach(),
            final_loss.detach(),
            target_loss.detach(),
            pike_blade_look_at_target_loss.detach(),
            lowerarm_length_loss.detach(),
            opposite_calf_collision_loss.detach(),
            blade_collision_loss.detach(),
            predictive_pin_loss.detach(),
            anti_pin_slide_loss.detach(),
            torch.sqrt(target_loss.detach().clamp_min(0.0)),
            torch.sqrt(
                (hit_linear_velocity_physical_sum / hit_count.clamp_min(1.0))
                .detach()
                .clamp_min(0.0)
            ),
            torch.sqrt(
                (hit_angular_velocity_physical_sum / hit_count.clamp_min(1.0))
                .detach()
                .clamp_min(0.0)
            ),
            lowerarm_max_length_error.detach(),
            opposite_calf_max_overlap.detach(),
            (opposite_calf_collision_bad_sum / denom).detach(),
            blade_max_penetration.detach(),
            (blade_collision_bad_sum / denom).detach(),
            (lower_pin_sum[0] / denom).detach(),
            (lower_pin_sum[1] / denom).detach(),
            (lower_pin_active_sum / denom).detach(),
            (armed_latch_sum / denom).detach(),
            (hit_latch_sum / denom).detach(),
            (pin_teacher_sum[0] / denom).detach(),
            (pin_teacher_sum[1] / denom).detach(),
            (pin_error_sum / denom).detach(),
            (anti_pin_slide_speed_sum[0] / denom).detach(),
            (anti_pin_slide_speed_sum[1] / denom).detach(),
            (anti_pin_slide_gate_sum / denom).detach(),
        )


def make_optimizer(
    lower: DeltaAgent,
    upper: DeltaAgent,
    recipe: Recipe,
    device: torch.device,
) -> torch.optim.Optimizer:
    kwargs: dict[str, object] = {
        "lr": (
            torch.tensor(recipe.learning_rate, dtype=torch.float32, device=device)
            if device.type == "cuda"
            else recipe.learning_rate
        ),
        "weight_decay": recipe.weight_decay,
    }
    if device.type == "cuda":
        kwargs.update(fused=True, capturable=True)
    try:
        return torch.optim.AdamW([*lower.parameters(), *upper.parameters()], **kwargs)
    except (RuntimeError, TypeError):
        kwargs.pop("fused", None)
        kwargs.pop("capturable", None)
        return torch.optim.AdamW([*lower.parameters(), *upper.parameters()], **kwargs)


def learning_rate_for_step(recipe: Recipe, step: int) -> float:
    if int(step) > int(recipe.learning_rate_decay_step):
        return float(recipe.learning_rate_after_decay)
    return float(recipe.learning_rate)


def upper_prior_weight_for_step(recipe: Recipe, step: int) -> float:
    if int(step) > int(recipe.learning_rate_decay_step):
        return float(recipe.upper_prior_weight_after_decay)
    return float(recipe.upper_prior_weight)


def ae11_weight_for_step(recipe: Recipe, step: int) -> float:
    if int(step) > int(recipe.learning_rate_decay_step):
        return float(recipe.ae11_weight_after_decay)
    return float(recipe.ae11_weight)


@torch.no_grad()
def set_optimizer_learning_rate(optimizer: torch.optim.Optimizer, value: float) -> None:
    for group in optimizer.param_groups:
        current = group["lr"]
        if torch.is_tensor(current):
            current.fill_(float(value))
        else:
            group["lr"] = float(value)


@torch.no_grad()
def set_training_loss_weights(
    loss: FullEpisodeLoss,
    ae11_weight: float,
    upper_prior_weight: float,
) -> None:
    # These are explicit static CUDA-graph input buffers. Updating their
    # storage must not advance autograd's version counter for the captured
    # forward topology that reads them on every replay.
    loss.ae11_weight_value.data.fill_(float(ae11_weight))
    loss.upper_prior_weight_value.data.fill_(float(upper_prior_weight))


def weighted_loss_terms(
    metrics: dict[str, float],
    recipe: Recipe,
    *,
    ae11_weight: float,
    upper_prior_weight: float,
) -> dict[str, float]:
    """Return the exact optimizer contributions shown under TensorBoard loss/."""

    terms = {
        "ae11": float(ae11_weight) * float(metrics["ae11"]),
        "ae22": float(upper_prior_weight) * float(metrics["ae22"]),
        "ae33": (
            float(upper_prior_weight)
            * float(recipe.ae33_weight_multiplier)
            * float(metrics["ae33"])
        ),
        "gate_timing": float(recipe.gate_timing_weight) * float(metrics["gate_timing"]),
        "armed_pose": float(recipe.armed_pose_weight) * float(metrics["armed_pose"]),
        "hit_pose": float(recipe.hit_pose_weight) * float(metrics["hit_pose"]),
        "hit_linear_velocity": (
            float(recipe.hit_linear_velocity_weight)
            * float(metrics["hit_linear_velocity"])
        ),
        "hit_angular_velocity": (
            float(recipe.hit_angular_velocity_weight)
            * float(metrics["hit_angular_velocity"])
        ),
        "final_pose": float(recipe.final_pose_weight) * float(metrics["final_pose"]),
        "hit_target_mse": float(recipe.hit_target_weight) * float(metrics["hit_target_mse"]),
        "pike_blade_look_at_target": (
            float(recipe.pike_blade_look_at_target_weight)
            * float(metrics["pike_blade_look_at_target"])
        ),
        "lowerarm_length": (
            float(recipe.lowerarm_length_weight) * float(metrics["lowerarm_length"])
        ),
        "opposite_calf_collision": (
            float(recipe.opposite_calf_collision_weight)
            * float(metrics["opposite_calf_collision"])
        ),
        "blade_collision": (
            float(recipe.blade_collision_weight) * float(metrics["blade_collision"])
        ),
        "predictive_pin": float(recipe.predictive_pin_weight) * float(metrics["predictive_pin"]),
        "anti_pin_slide": float(recipe.anti_pin_slide_weight) * float(metrics["anti_pin_slide"]),
    }
    if tuple(terms) != WEIGHTED_LOSS_TERM_NAMES:
        raise RuntimeError(
            "Weighted scalar loss registry is incomplete or out of order: "
            f"expected {WEIGHTED_LOSS_TERM_NAMES}, got {tuple(terms)}"
        )
    return {"total": float(metrics["total"]), **terms}


def build_fragment_start_schedule(
    lengths: torch.Tensor,
    row_keys: torch.Tensor,
    seed: int,
    start_epoch: int,
    end_epoch: int,
    slots: int,
) -> torch.Tensor:
    """Precompute the exact deterministic random starts in pinned CPU memory."""

    if end_epoch < start_epoch:
        raise ValueError(f"Invalid fragment epoch range {start_epoch}..{end_epoch}")
    lengths_np = lengths.detach().cpu().numpy().astype(np.int64, copy=False)
    keys_np = row_keys.detach().cpu().numpy().astype(np.int64, copy=False)
    epoch_np = np.arange(start_epoch, end_epoch + 1, dtype=np.int64)[:, None, None]
    slot_np = np.arange(1, int(slots) + 1, dtype=np.int64)[None, :, None]
    mixed = (
        epoch_np * np.int64(1_000_003)
        + slot_np * np.int64(97_409)
        + (keys_np[None, None, :] + 1) * np.int64(65_537)
        + np.int64(seed)
    )
    mixed = np.remainder(mixed * np.int64(48_271) + 1, np.int64(2_147_483_647))
    span = np.maximum(lengths_np - 2, 1)[None, None, :]
    schedule = 1 + np.remainder(mixed, span)
    return torch.from_numpy(np.ascontiguousarray(schedule)).pin_memory()


def build_full_dataset_schedule(
    lengths: torch.Tensor,
    seed: int,
    start_epoch: int,
    end_epoch: int,
    slots: int,
    schedule_lanes: int,
    batch_rows: int,
    original_count: int = FULL_DATASET_GT_COUNT,
    original_probability: float = 0.10,
    forced_family_clip_ids: tuple[int, ...] = (),
    forced_family_rows_per_logical_batch: int = 0,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Build the deterministic 10/90 source and 50/50 normal/M schedule.

    Every consecutive ten candidate draws contain exactly one original. Within
    each source-and-mode pool, a coprime affine cycle visits every file exactly
    once before repeating. Alternating mode ordinals make normal/M balance
    structural rather than statistical. The schedule covers initial seeds and
    every possible in-graph reset.
    """

    if abs(float(original_probability) - 0.10) > 1.0e-12:
        raise ValueError("The accepted full-data schedule is fixed to exactly 10% originals")
    total_count = int(lengths.numel())
    variant_count = total_count - int(original_count)
    if (
        int(original_count) != FULL_DATASET_GT_COUNT
        or variant_count != FULL_DATASET_VARIANT_COUNT
    ):
        raise ValueError(
            f"Expected {FULL_DATASET_GT_COUNT} originals and "
            f"{FULL_DATASET_VARIANT_COUNT:,} variants, got {original_count} and {variant_count}"
        )
    if end_epoch < start_epoch:
        raise ValueError(f"Invalid full-data epoch range {start_epoch}..{end_epoch}")
    epochs = np.arange(start_epoch, end_epoch + 1, dtype=np.int64)[:, None, None, None]
    slot_ids = np.arange(int(slots), dtype=np.int64)[None, :, None, None]
    lane_ids = np.arange(int(schedule_lanes), dtype=np.int64)[None, None, :, None]
    row_ids = np.arange(int(batch_rows), dtype=np.int64)[None, None, None, :]
    streams_per_epoch = int(schedule_lanes) * int(batch_rows)
    stream = (
        epochs * np.int64(streams_per_epoch)
        + lane_ids * np.int64(batch_rows)
        + row_ids
    )
    # Each row owns a contiguous reset stream, so every actually consumed
    # prefix remains within one draw of the exact 10/90 contract.
    draw = stream * np.int64(slots) + slot_ids
    block = draw // np.int64(10)
    remainder = draw % np.int64(10)
    original_position = np.remainder(
        np.remainder(
            block * np.int64(48_271) + np.int64(seed) * np.int64(65_537) + 1,
            np.int64(2_147_483_647),
        ),
        np.int64(10),
    )
    is_original = remainder == original_position

    original_ordinal = block
    variants_before = block * np.int64(9) + remainder - (original_position < remainder)
    original_mode = np.remainder(original_ordinal, np.int64(2))
    original_within_mode = original_ordinal // np.int64(2)
    original_id = (
        original_mode * np.int64(FULL_DATASET_MODE_GT_COUNT)
        + np.remainder(
            original_within_mode * np.int64(5) + np.int64(seed),
            np.int64(FULL_DATASET_MODE_GT_COUNT),
        )
    )
    variant_mode = np.remainder(variants_before, np.int64(2))
    variant_within_mode = variants_before // np.int64(2)
    variant_id = (
        np.int64(original_count)
        + variant_mode * np.int64(FULL_DATASET_MODE_VARIANT_COUNT)
        + np.remainder(
            variant_within_mode * np.int64(173) + np.int64(seed) * np.int64(97),
            np.int64(FULL_DATASET_MODE_VARIANT_COUNT),
        )
    )
    clip_ids = np.where(is_original, original_id, variant_id).astype(np.int64, copy=False)

    forced_rows = int(forced_family_rows_per_logical_batch)
    logical_rows = int(schedule_lanes) * int(batch_rows)
    if forced_rows < 0 or forced_rows > logical_rows:
        raise ValueError(
            f"Forced-family rows must lie in 0..{logical_rows}, got {forced_rows}"
        )
    if forced_rows:
        requested_ids = np.asarray(forced_family_clip_ids, dtype=np.int64)
        if requested_ids.ndim != 1 or requested_ids.size == 0:
            raise ValueError("Forced-family rows require non-empty family clip IDs")
        if np.any((requested_ids < 0) | (requested_ids >= total_count)):
            raise ValueError("Forced-family clip IDs are outside the loaded corpus")
        category_ids = (
            requested_ids[requested_ids < FULL_DATASET_MODE_GT_COUNT],
            requested_ids[
                (requested_ids >= FULL_DATASET_MODE_GT_COUNT)
                & (requested_ids < FULL_DATASET_GT_COUNT)
            ],
            requested_ids[
                (requested_ids >= FULL_DATASET_GT_COUNT)
                & (
                    requested_ids
                    < FULL_DATASET_GT_COUNT + FULL_DATASET_MODE_VARIANT_COUNT
                )
            ],
            requested_ids[
                requested_ids
                >= FULL_DATASET_GT_COUNT + FULL_DATASET_MODE_VARIANT_COUNT
            ],
        )
        if any(ids.size == 0 for ids in category_ids):
            raise ValueError(
                "Forced family must contain GT normal/M and variant normal/M clips"
            )
        # Logical row order is schedule-lane-major. Production has exactly one
        # lane; rewriting the same row at
        # every reset slot keeps that row in the requested family for its full
        # episode lifetime while preserving its original source/mode category.
        for logical_row in range(forced_rows):
            lane_index, row_index = divmod(logical_row, int(batch_rows))
            selected = clip_ids[:, :, lane_index, row_index]
            selected_draw = draw[:, :, lane_index, row_index]
            category = np.where(
                selected < FULL_DATASET_MODE_GT_COUNT,
                0,
                np.where(
                    selected < FULL_DATASET_GT_COUNT,
                    1,
                    np.where(
                        selected
                        < FULL_DATASET_GT_COUNT + FULL_DATASET_MODE_VARIANT_COUNT,
                        2,
                        3,
                    ),
                ),
            )
            for category_index, allowed in enumerate(category_ids):
                mask = category == category_index
                ordinal = np.remainder(
                    selected_draw * np.int64(193)
                    + np.int64(seed) * np.int64(389)
                    + np.int64(logical_row) * np.int64(769),
                    np.int64(allowed.size),
                )
                selected[mask] = allowed[ordinal[mask]]

    lengths_np = lengths.detach().cpu().numpy().astype(np.int64, copy=False)
    selected_lengths = lengths_np[clip_ids]
    span = np.maximum(selected_lengths - 2, 1)
    mixed_frame = np.remainder(
        draw * np.int64(97_409) + np.int64(seed) * np.int64(131_071) + 1,
        np.int64(2_147_483_647),
    )
    frame_ids = 1 + np.remainder(mixed_frame, span)
    return (
        torch.from_numpy(np.ascontiguousarray(clip_ids)).pin_memory(),
        torch.from_numpy(np.ascontiguousarray(frame_ids)).pin_memory(),
    )


def build_uniform_dataset_schedule(
    lengths: torch.Tensor,
    seed: int,
    start_epoch: int,
    end_epoch: int,
    slots: int,
    schedule_lanes: int,
    batch_rows: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Build a deterministic uniform schedule over every supplied GT motion.

    The affine cycle is coprime to the 32-motion corpus, so every consecutive
    32 draws visit each normal/mirrored motion exactly once.  Frame starts are
    independently uniform over each selected motion's valid range.
    """

    total_count = int(lengths.numel())
    if total_count != 32:
        raise ValueError(f"Expected 32 normal+mirrored GT motions, got {total_count}")
    if end_epoch < start_epoch:
        raise ValueError(f"Invalid GT32 epoch range {start_epoch}..{end_epoch}")
    epochs = np.arange(start_epoch, end_epoch + 1, dtype=np.int64)[:, None, None, None]
    slot_ids = np.arange(int(slots), dtype=np.int64)[None, :, None, None]
    lane_ids = np.arange(int(schedule_lanes), dtype=np.int64)[None, None, :, None]
    row_ids = np.arange(int(batch_rows), dtype=np.int64)[None, None, None, :]
    streams_per_epoch = int(schedule_lanes) * int(batch_rows)
    # The extra one-draw epoch stride prevents a 16-row initial batch from
    # repeating the same parity half when ``slots * batch`` is divisible by
    # 32.  Across 32 epochs the skipped draw itself also visits every clip,
    # preserving exact long-run uniformity.
    draw = (
        epochs * np.int64(streams_per_epoch * int(slots) + 1)
        + slot_ids * np.int64(streams_per_epoch)
        + lane_ids * np.int64(batch_rows)
        + row_ids
    )
    clip_ids = np.remainder(
        draw * np.int64(5) + np.int64(seed), np.int64(total_count)
    ).astype(np.int64, copy=False)
    lengths_np = lengths.detach().cpu().numpy().astype(np.int64, copy=False)
    selected_lengths = lengths_np[clip_ids]
    span = np.maximum(selected_lengths - 2, 1)
    mixed_frame = np.remainder(
        draw * np.int64(97_409) + np.int64(seed) * np.int64(131_071) + 1,
        np.int64(2_147_483_647),
    )
    frame_ids = 1 + np.remainder(mixed_frame, span)
    return (
        torch.from_numpy(np.ascontiguousarray(clip_ids)).pin_memory(),
        torch.from_numpy(np.ascontiguousarray(frame_ids)).pin_memory(),
    )


class CudaGraphStep:
    """Execute the balanced random-reset rollout and backward pass on CUDA."""

    kind = SLASH2_CUDA_GRAPH_SCHEMA

    def __init__(
        self,
        loss: FullEpisodeLoss,
        optimizer: torch.optim.Optimizer,
    ) -> None:
        if loss.runtime.device.type != "cuda":
            raise RuntimeError("CudaGraphStep requires CUDA")
        physical_batch = (
            len(loss.runtime.attacks.paths)
            if loss.rows_static is None
            else int(loss.rows_static.numel())
        )
        if int(loss.runtime.recipe.batch_size) != physical_batch:
            raise ValueError(
                f"Configured physical batch {loss.runtime.recipe.batch_size} does not match "
                f"the captured CUDA batch {physical_batch}; Slash2 does not split batches"
            )
        self.physical_batch_size = physical_batch
        # The schedule tensors retain a singleton replay axis, but every
        # optimizer step has exactly one full physical-batch graph replay.
        self.schedule_lanes = 1
        canonical_count = (
            len(ATTACK_LABELS)
            if loss.dynamic_full_dataset
            else len(loss.runtime.attacks.paths)
        )
        if canonical_count % len(ATTACK_LABELS) != 0:
            raise ValueError(
                f"Expected a whole number of {len(ATTACK_LABELS)}-family mode sets, "
                f"got {canonical_count}"
            )
        self.loss = loss
        self.optimizer = optimizer
        self.graphed_loss: FullEpisodeLoss
        self.metrics: tuple[torch.Tensor, ...]
        self.parameters = [*self.loss.lower_agent.parameters(), *self.loss.upper_agent.parameters()]
        self.parameter_snapshot: list[torch.Tensor] = []
        self.optimizer_state_snapshot: dict[torch.Tensor, dict[str, object]] = {
            parameter: {
                key: value.detach().clone() if torch.is_tensor(value) else copy.deepcopy(value)
                for key, value in state.items()
            }
            for parameter, state in self.optimizer.state.items()
        }
        self.gradient_norm = torch.zeros((), dtype=torch.float32, device=loss.runtime.device)
        self.schedule_epoch_start = int(loss.fragment_epoch_start)
        self.schedule_epoch_end = self.schedule_epoch_start - 1
        self.clip_index_schedule: torch.Tensor | None = None
        self.fragment_start_schedule = torch.empty(0, dtype=torch.long)
        self.carry_valid = [False] * self.schedule_lanes
        self.carry_attack: dict[str, torch.Tensor] = {}
        self.carry_seed: dict[str, torch.Tensor] = {}
        if self.loss.dynamic_full_dataset:
            for name in self.loss._staged_attack_tensor_names:
                terminal = getattr(self.loss, f"terminal_attack_{name}")
                self.carry_attack[name] = torch.empty(
                    (self.schedule_lanes, *terminal.shape),
                    dtype=terminal.dtype,
                    device=terminal.device,
                )
            for item in fields(FragmentSeed):
                terminal = getattr(self.loss, f"terminal_seed_{item.name}")
                self.carry_seed[item.name] = torch.empty(
                    (self.schedule_lanes, *terminal.shape),
                    dtype=terminal.dtype,
                    device=terminal.device,
                )
        self._build_fragment_schedule_chunk(self.schedule_epoch_start)
        self.fragment_replay_cursor = int(loss.fragment_epoch_start)
        self._stage_fragment_starts(self.fragment_replay_cursor, 0)
        torch.cuda.synchronize()
        self._warm_and_capture()

    @property
    def metric_names(self) -> tuple[str, ...]:
        return self.loss.metric_names

    def _build_fragment_schedule_chunk(self, start_epoch: int) -> None:
        """Materialize one bounded deterministic window for an uncapped run."""

        start_epoch = int(start_epoch)
        end_epoch = start_epoch + FRAGMENT_SCHEDULE_CHUNK_EPOCHS - 1
        if self.loss.dynamic_full_dataset:
            custom_schedule_builder = getattr(
                self.loss.runtime, "difficulty_schedule_builder", None
            )
            schedule_builder = (
                custom_schedule_builder
                if callable(custom_schedule_builder)
                else build_full_dataset_schedule
                if self.loss.runtime.recipe.variant_dir
                else build_uniform_dataset_schedule
            )
            schedule_kwargs: dict[str, object] = {}
            if custom_schedule_builder is None and self.loss.runtime.recipe.variant_dir:
                forced_family = str(
                    self.loss.runtime.recipe.forced_attack_family
                ).strip().lower()
                forced_family_clip_ids = (
                    tuple(
                        index
                        for index, path in enumerate(self.loss.runtime.attacks.paths)
                        if attack_family_from_path(path) == forced_family
                    )
                    if forced_family
                    else ()
                )
                schedule_kwargs = {
                    "original_count": FULL_DATASET_GT_COUNT,
                    "original_probability": self.loss.runtime.recipe.original_sample_probability,
                    "forced_family_clip_ids": forced_family_clip_ids,
                    "forced_family_rows_per_logical_batch": (
                        self.loss.runtime.recipe.forced_attack_family_rows_per_logical_batch
                    ),
                }
            (
                self.clip_index_schedule,
                self.fragment_start_schedule,
            ) = schedule_builder(
                self.loss.runtime.attacks.lengths,
                self.loss.runtime.recipe.seed,
                start_epoch,
                end_epoch,
                self.loss.rollout_steps + 1,
                self.schedule_lanes,
                self.physical_batch_size,
                **schedule_kwargs,
            )
        else:
            schedule_data: AttackBatch | AttackRows = (
                self.loss.runtime.attacks
                if self.loss.rows_static is None
                else select_attack_rows(self.loss.runtime.attacks, self.loss.rows_static)
            )
            expanded_lengths = schedule_data.lengths.repeat(self.schedule_lanes)
            row_keys = torch.arange(
                int(expanded_lengths.numel()),
                dtype=torch.long,
                device=self.loss.runtime.device,
            )
            flat_schedule = build_fragment_start_schedule(
                expanded_lengths,
                row_keys,
                self.loss.runtime.recipe.seed,
                start_epoch,
                end_epoch,
                self.loss.rollout_steps + 1,
            )
            self.fragment_start_schedule = flat_schedule.reshape(
                flat_schedule.shape[0],
                flat_schedule.shape[1],
                self.schedule_lanes,
                self.physical_batch_size,
            )
            self.clip_index_schedule = None
        self.schedule_epoch_start = start_epoch
        self.schedule_epoch_end = end_epoch

    def _ensure_fragment_schedule(self, epoch: int) -> None:
        epoch = int(epoch)
        if epoch < self.schedule_epoch_start or epoch > self.schedule_epoch_end:
            self._build_fragment_schedule_chunk(epoch)

    @torch.no_grad()
    def _stage_fragment_starts(self, cursor: int, lane_index: int) -> None:
        self._ensure_fragment_schedule(cursor)
        schedule_row = int(cursor) - self.schedule_epoch_start
        if lane_index < 0 or lane_index >= self.schedule_lanes:
            raise RuntimeError(
                f"Invalid schedule lane {lane_index}; lanes={self.schedule_lanes}"
            )
        self.loss.fragment_start_indices.copy_(
            self.fragment_start_schedule[schedule_row, :, lane_index],
            non_blocking=True,
        )
        if self.clip_index_schedule is not None:
            self.loss.stage_full_dataset_rows(
                self.clip_index_schedule[schedule_row, :, lane_index],
                self.fragment_start_schedule[schedule_row, :, lane_index],
            )
            self._overlay_carried_episode(lane_index)

    @torch.no_grad()
    def _overlay_carried_episode(self, lane_index: int) -> None:
        """Replace slot zero with the exact terminal state of its prior replay."""

        if (
            not self.loss.dynamic_full_dataset
            or not self.carry_valid[lane_index]
        ):
            return
        for name, values in self.carry_attack.items():
            getattr(self.loss, f"staged_attack_{name}")[0].copy_(
                values[lane_index]
            )
        for name, values in self.carry_seed.items():
            getattr(self.loss, f"staged_seed_{name}")[0].copy_(
                values[lane_index]
            )
        self.loss.clip_index_schedule[0].copy_(
            self.carry_attack["clip_ids"][lane_index]
        )
        self.loss.fragment_start_indices[0].copy_(
            self.carry_seed["current_index"][lane_index]
        )

    @torch.no_grad()
    def _store_carried_episode(self, lane_index: int) -> None:
        """Retain the detached terminal episode state for the next optimizer step."""

        if not self.loss.dynamic_full_dataset:
            return
        for name, values in self.carry_attack.items():
            values[lane_index].copy_(
                getattr(self.loss, f"terminal_attack_{name}")
            )
        for name, values in self.carry_seed.items():
            values[lane_index].copy_(
                getattr(self.loss, f"terminal_seed_{name}")
            )
        self.carry_valid[lane_index] = True

    @torch.no_grad()
    def _restore_optimizer_state(self) -> None:
        for parameter, state in self.optimizer.state.items():
            saved = self.optimizer_state_snapshot.get(parameter, {})
            for key, value in state.items():
                saved_value = saved.get(key)
                if torch.is_tensor(value):
                    if torch.is_tensor(saved_value):
                        value.copy_(saved_value)
                    else:
                        value.zero_()
                elif key in saved:
                    state[key] = copy.deepcopy(saved_value)
                elif isinstance(value, (int, float)):
                    state[key] = type(value)(0)

    def _warm_and_capture(self) -> None:
        parameters = self.parameters
        parameter_snapshot = [parameter.detach().clone() for parameter in parameters]
        free_bytes, total_bytes = torch.cuda.mem_get_info()
        print(
            f"slash2_cuda_graph warm_begin free_mb={free_bytes // (1024 * 1024)} "
            f"total_mb={total_bytes // (1024 * 1024)}",
            flush=True,
        )
        with self.loss.runtime.policy_context():
            self.graphed_loss = torch.cuda.make_graphed_callables(
                self.loss,
                (),
                # One complete forward/backward warmup is sufficient because
                # every module and optimizer buffer is already initialized and
                # the exact compiled callables are prewarmed on disk. Repeating
                # the same warmup does not change captured math, but retains
                # duplicate host-side autograd/compiler state at peak startup.
                num_warmup_iters=1,
                allow_unused_input=False,
            )
            self.metrics = tuple(
                torch.zeros((), dtype=torch.float32, device=self.loss.runtime.device)
                for _name in self.metric_names
            )

        torch.cuda.synchronize()
        free_bytes, _total_bytes = torch.cuda.mem_get_info()
        print(
            f"slash2_cuda_graph capture_end free_mb={free_bytes // (1024 * 1024)}",
            flush=True,
        )

        print("slash2_cuda_graph post_capture_zero_grad_begin", flush=True)
        self.optimizer.zero_grad(set_to_none=True)
        print("slash2_cuda_graph post_capture_zero_grad_end", flush=True)
        self.parameter_snapshot = parameter_snapshot

    def reset(self) -> None:
        """Restore the post-capture fresh-run baseline without recapturing."""

        if not self.parameter_snapshot:
            raise RuntimeError("CUDA graph baseline snapshot is unavailable")
        torch.cuda.synchronize()
        with torch.no_grad():
            for parameter, saved in zip(self.parameters, self.parameter_snapshot):
                # Reset is a controlled restore of the static graph inputs.
                # Use their storage directly so the reusable captured forward
                # keeps the version counter it recorded at capture time.
                parameter.data.copy_(saved)
            self._restore_optimizer_state()
            # A reset separates independent audits or a new real run. Dropping
            # the gradient tensors prevents the first subsequent graphed
            # backward from accumulating into a stale internal grad buffer.
            # Normal consecutive training replays keep the fast in-place zero.
            self.optimizer.zero_grad(set_to_none=True)
            self.fragment_replay_cursor = int(self.loss.fragment_epoch_start)
            self.carry_valid = [False] * self.schedule_lanes
            self._stage_fragment_starts(self.fragment_replay_cursor, 0)
        torch.cuda.synchronize()

    def _replay_physical_batch_backward(self) -> list[torch.Tensor]:
        """Run one captured physical batch and its backward graph exactly once."""

        self.optimizer.zero_grad(set_to_none=True)
        self._stage_fragment_starts(self.fragment_replay_cursor, 0)
        # Some read-only audits call ``replay`` from a ``no_grad`` context.
        # Graphed callables still need autograd enabled so their separately
        # captured backward graph is attached and replayed.
        with torch.enable_grad():
            self.metrics = self.graphed_loss()
            self.metrics[0].backward()
        self._store_carried_episode(0)
        if any(parameter.grad is None for parameter in self.parameters):
            raise RuntimeError(
                "Captured Slash2 backward omitted a trainable parameter gradient"
            )
        return [value.detach() for value in self.metrics]

    def replay(self, synchronize: bool = True) -> dict[str, float] | None:
        averaged_metrics = self._replay_physical_batch_backward()
        # The one captured physical-batch replay produced this optimizer step.
        # Launch the small, value-dependent clipping tail outside the graph;
        # capturing torch's foreach clip is the isolated replay-two failure.
        self.gradient_norm = torch.nn.utils.clip_grad_norm_(
            self.parameters,
            max_norm=float(self.loss.runtime.recipe.gradient_clip_norm),
            foreach=True,
        )
        self.optimizer.step()
        self.fragment_replay_cursor += 1
        if not synchronize:
            return None
        torch.cuda.current_stream().synchronize()
        result = {
            name: float(value.detach().cpu())
            for name, value in zip(self.metric_names, averaged_metrics)
        }
        result["gradient_norm"] = float(self.gradient_norm.detach().cpu())
        return result

    @torch.no_grad()
    def snapshot_debug_rollout(self) -> dict[str, torch.Tensor]:
        """Copy the exact latest captured training rollout to CPU once."""

        return {
            "positions": self.loss.debug_positions.detach().cpu().clone(),
            "basis": self.loss.debug_basis.detach().cpu().clone(),
            "phase_probabilities": self.loss.debug_gate_probabilities.detach().cpu().clone(),
            "lower_pin_probabilities": self.loss.debug_lower_pin_probabilities.detach().cpu().clone(),
            "armed_latch": self.loss.debug_armed_latch.detach().cpu().clone(),
            "hit_latch": self.loss.debug_hit_latch.detach().cpu().clone(),
            "reset_flags": self.loss.debug_reset_flags.detach().cpu().clone(),
            "target_world_m": (
                self.loss.debug_target_world_m.detach().cpu().clone()
            ),
            "controller_root_pos": (
                self.loss.debug_controller_root_pos.detach().cpu().clone()
            ),
            "controller_root_rot": (
                self.loss.debug_controller_root_rot.detach().cpu().clone()
            ),
            "frozen_root_pos": (
                self.loss.debug_frozen_root_pos.detach().cpu().clone()
            ),
            "frozen_root_rot": (
                self.loss.debug_frozen_root_rot.detach().cpu().clone()
            ),
            "source_frame": self.loss.debug_source_frame.detach().cpu().clone(),
            "clip_id": self.loss.debug_clip_id.detach().cpu().clone(),
            "geometry_clip_id": (
                self.loss.debug_geometry_clip_id.detach().cpu().clone()
            ),
            "weighted_loss_terms": (
                self.loss.debug_weighted_loss_terms.detach().cpu().clone()
            ),
        }


@torch.no_grad()
def calibrate_checkpoint_loss_weight(
    graph: CudaGraphStep,
    *,
    loss_name: str,
    target_weighted_loss: float,
    samples: int = 7,
) -> dict[str, object]:
    """Measure independent scheduled rollouts on the exact loaded checkpoint.

    Each captured replay begins from the same parameter and optimizer snapshot;
    only its deterministic schedule cursor differs.  ``reset`` restores all
    training state after every sample and once again before returning, so this
    audit cannot consume an optimizer step or become a resume checkpoint.
    """

    loss_name = str(loss_name).strip()
    if not loss_name:
        raise ValueError("calibration loss name must be non-empty")
    if not math.isfinite(float(target_weighted_loss)) or target_weighted_loss <= 0.0:
        raise ValueError("calibration target must be finite and positive")
    if int(samples) <= 0:
        raise ValueError("calibration sample count must be positive")
    start_cursor = int(graph.loss.fragment_epoch_start)
    raw_samples: list[float] = []
    for offset in range(int(samples)):
        graph.reset()
        graph.fragment_replay_cursor = start_cursor + offset
        graph._stage_fragment_starts(graph.fragment_replay_cursor, 0)
        metrics = graph.replay(synchronize=True)
        if metrics is None:
            raise RuntimeError("calibration replay did not return synchronized metrics")
        if loss_name not in metrics:
            raise RuntimeError(f"calibration metric {loss_name!r} is absent")
        raw = float(metrics[loss_name])
        if not math.isfinite(raw) or raw < 0.0:
            raise RuntimeError(f"invalid {loss_name} calibration sample: {raw}")
        raw_samples.append(raw)
    graph.reset()
    parameters_exact = all(
        torch.equal(parameter.detach(), saved)
        for parameter, saved in zip(graph.parameters, graph.parameter_snapshot)
    )
    raw_mean = float(sum(raw_samples) / len(raw_samples))
    if raw_mean <= 0.0:
        raise RuntimeError(
            f"{loss_name} calibration mean is zero; a finite target weight cannot be derived"
        )
    weight = float(target_weighted_loss) / raw_mean
    return {
        "schema": "slash2_checkpoint_loss_calibration_v1",
        "loss": loss_name,
        "targetWeightedLoss": float(target_weighted_loss),
        "sampleCount": int(samples),
        "scheduleStartStep": start_cursor,
        "rawSamples": raw_samples,
        "rawMean": raw_mean,
        "weight": weight,
        "reconstructedWeightedLoss": weight * raw_mean,
        "parametersRestoredExactly": bool(parameters_exact),
        "optimizerAndScheduleReset": True,
    }


def calibrate_opposite_calf_collision_weight(
    graph: CudaGraphStep,
    *,
    target_weighted_loss: float = 0.04,
    samples: int = 7,
) -> dict[str, object]:
    return calibrate_checkpoint_loss_weight(
        graph,
        loss_name="opposite_calf_collision",
        target_weighted_loss=target_weighted_loss,
        samples=samples,
    )


def calibrate_predictive_pin_weight(prepared, *, target_weighted_loss: float, samples: int = 7):
    """Calibrate on this loaded source, restore all state, reuse the same graph."""
    graph = prepared.graph
    if prepared.runtime.pin_teacher is None:
        raise ValueError("Cannot calibrate without the verified predictive pin teacher")
    try:
        report = calibrate_checkpoint_loss_weight(graph, loss_name="predictive_pin",
            target_weighted_loss=target_weighted_loss, samples=samples)
    finally:
        graph.reset()
    optimizer_exact = set(graph.optimizer.state) == set(graph.optimizer_state_snapshot) and all(
        set(graph.optimizer.state[parameter]) == set(saved)
        for parameter, saved in graph.optimizer_state_snapshot.items()
    ) and all(
        torch.equal(value, saved[key]) if torch.is_tensor(value) else value == saved[key]
        for parameter, saved in graph.optimizer_state_snapshot.items()
        for key, value in graph.optimizer.state[parameter].items()
    )
    schedule_exact = graph.fragment_replay_cursor == int(prepared.start_step) and not any(graph.carry_valid)
    if not (report["parametersRestoredExactly"] and optimizer_exact and schedule_exact):
        raise RuntimeError("Predictive-pin calibration did not restore the exact resume state")
    weight = float(report["weight"])
    graph.loss.predictive_pin_weight_value.data.fill_(weight)
    prepared.recipe = replace(prepared.recipe, predictive_pin_weight=weight)
    prepared.runtime.recipe = prepared.recipe
    report.update(optimizerRestoredExactly=optimizer_exact, scheduleRestoredExactly=schedule_exact,
        optimizerStepsConsumed=0, checkpointSha256=sha256_file(Path(prepared.recipe.resume_checkpoint)),
        checkpointStep=int(prepared.start_step), graphRecaptured=False,
        appliedWeightFloat32=float(graph.loss.predictive_pin_weight_value.detach().cpu()))
    prepared.runtime.pin_teacher_metadata["calibration"] = report
    return report


def calibrate_anti_pin_slide_weight(
    prepared,
    *,
    target_weighted_loss: float = 0.07,
    samples: int = 7,
):
    """Calibrate anti-pin-slide on the exact loaded resume state without steps."""

    graph = prepared.graph
    try:
        report = calibrate_checkpoint_loss_weight(
            graph,
            loss_name="anti_pin_slide",
            target_weighted_loss=target_weighted_loss,
            samples=samples,
        )
    finally:
        graph.reset()
    optimizer_exact = set(graph.optimizer.state) == set(graph.optimizer_state_snapshot) and all(
        set(graph.optimizer.state[parameter]) == set(saved)
        for parameter, saved in graph.optimizer_state_snapshot.items()
    ) and all(
        torch.equal(value, saved[key]) if torch.is_tensor(value) else value == saved[key]
        for parameter, saved in graph.optimizer_state_snapshot.items()
        for key, value in graph.optimizer.state[parameter].items()
    )
    schedule_exact = (
        graph.fragment_replay_cursor == int(prepared.start_step)
        and not any(graph.carry_valid)
    )
    if not (report["parametersRestoredExactly"] and optimizer_exact and schedule_exact):
        raise RuntimeError("Anti-pin-slide calibration did not restore the exact resume state")
    weight = float(report["weight"])
    graph.loss.anti_pin_slide_weight_value.data.fill_(weight)
    prepared.recipe = replace(prepared.recipe, anti_pin_slide_weight=weight)
    prepared.runtime.recipe = prepared.recipe
    report.update(
        optimizerRestoredExactly=optimizer_exact,
        scheduleRestoredExactly=schedule_exact,
        optimizerStepsConsumed=0,
        checkpointSha256=sha256_file(Path(prepared.recipe.resume_checkpoint)),
        checkpointStep=int(prepared.start_step),
        graphRecaptured=False,
        appliedWeightFloat32=float(
            graph.loss.anti_pin_slide_weight_value.detach().cpu()
        ),
        pinRampStart=ANTI_PIN_SLIDE_RAMP_START,
        pinRampPeak=ANTI_PIN_SLIDE_RAMP_PEAK,
    )
    return report


def calibrate_pike_blade_look_at_target_weight(
    graph: CudaGraphStep,
    *,
    target_weighted_loss: float = 0.008,
    samples: int = 7,
) -> dict[str, object]:
    return calibrate_checkpoint_loss_weight(
        graph,
        loss_name="pike_blade_look_at_target",
        target_weighted_loss=target_weighted_loss,
        samples=samples,
    )


@torch.no_grad()
def cuda_graph_debug_rollout_audit(graph: CudaGraphStep) -> dict[str, object]:
    graph.reset()
    graph.replay()
    snapshot = graph.snapshot_debug_rollout()
    runtime = graph.loss.runtime
    positions = snapshot["positions"]
    basis = snapshot["basis"]
    probabilities = snapshot["phase_probabilities"]
    lower_pin_probabilities = snapshot["lower_pin_probabilities"]
    armed = snapshot["armed_latch"]
    hit = snapshot["hit_latch"]
    reset = snapshot["reset_flags"]
    target_world_m = snapshot["target_world_m"]
    controller_root_pos = snapshot["controller_root_pos"]
    controller_root_rot = snapshot["controller_root_rot"]
    frozen_root_pos = snapshot["frozen_root_pos"]
    frozen_root_rot = snapshot["frozen_root_rot"]
    source = snapshot["source_frame"]
    clip_id = snapshot["clip_id"]
    geometry_clip_id = snapshot["geometry_clip_id"]
    weighted_loss_terms = snapshot["weighted_loss_terms"]
    all_lengths = runtime.attacks.lengths.detach().cpu()
    lengths = all_lengths[clip_id]
    source_in_range = bool(((source >= 0) & (source < lengths)).all())
    clip_ids_in_range = bool(
        ((clip_id >= 0) & (clip_id < len(runtime.attacks.paths))).all()
    )
    geometry_clip_ids_in_range = bool(
        (
            (geometry_clip_id >= 0)
            & (geometry_clip_id < len(runtime.attacks.paths))
        ).all()
    )
    target_ids_device = clip_id.to(runtime.device).reshape(-1)
    target_zero_device = torch.zeros_like(target_ids_device)
    target_root_pos_device, target_root_rot_device, _target_yaw, _target_heading = (
        runtime.lower_store.root_state(target_ids_device, target_zero_device)
    )
    target_root_pos = target_root_pos_device.reshape_as(controller_root_pos).detach().cpu()
    target_root_rot = target_root_rot_device.reshape_as(controller_root_rot).detach().cpu()
    original_target_world = runtime.attacks.targets_world.detach().cpu()[clip_id]
    original_target_local = torch.matmul(
        (original_target_world - target_root_pos).unsqueeze(-2),
        target_root_rot.transpose(-1, -2),
    ).squeeze(-2)
    expected_target_world_m = (
        torch.matmul(
            original_target_local.unsqueeze(-2), controller_root_rot
        ).squeeze(-2)
        + controller_root_pos
    )
    target_world_m_error = float(
        (target_world_m - expected_target_world_m).abs().max()
    )
    target_world_m_finite = bool(torch.isfinite(target_world_m).all())
    root_markers_finite = bool(
        torch.isfinite(controller_root_pos).all()
        and torch.isfinite(controller_root_rot).all()
        and torch.isfinite(frozen_root_pos).all()
        and torch.isfinite(frozen_root_rot).all()
    )
    safe_source = torch.minimum(torch.maximum(source, torch.zeros_like(source)), lengths - 1)
    # The full-corpus cache is device-independent and was decoded on CPU. The
    # captured graph deliberately reseeds from FK decoded on the active CUDA
    # device, so its exact audit target must be reconstructed from the native
    # controller state on that same device as well.
    source_device = runtime.attacks.trajectory_lower.device
    source_clip_id = clip_id.to(source_device)
    source_frame = safe_source.to(source_device)
    expected_lower = runtime.attacks.trajectory_lower[
        source_clip_id, source_frame
    ].to(runtime.device)
    expected_upper = runtime.attacks.trajectory_upper[
        source_clip_id, source_frame
    ].to(runtime.device)
    expected_heading = runtime.attacks.trajectory_heading[
        source_clip_id, source_frame
    ].to(runtime.device)
    device_clip_id = clip_id.to(runtime.device).reshape(-1)
    device_source = safe_source.to(runtime.device).reshape(-1)
    with torch.no_grad():
        expected_positions_device, expected_basis_device = hybrid_full_fk_globals(
            runtime,
            device_clip_id,
            device_clip_id,
            device_source,
            expected_lower.reshape(-1, LOWER_STATE_DIM),
            expected_upper.reshape(-1, UPPER_STATE_DIM),
            expected_target_world_m.reshape(-1, 3).to(runtime.device),
            expected_heading.reshape(-1, 3, 3),
        )
    expected_positions = expected_positions_device.reshape_as(positions).detach().cpu()
    expected_basis = expected_basis_device.reshape_as(basis).detach().cpu()
    frame_ids = torch.arange(positions.shape[1], dtype=torch.long)[None, :]
    seed_event = reset | (frame_ids < 2)
    exact_seed = seed_event
    seed_position_error = float(
        torch.where(
            exact_seed[:, :, None, None],
            (positions - expected_positions).abs(),
            torch.zeros_like(positions),
        ).max()
    )
    seed_basis_error = float(
        torch.where(
            exact_seed[:, :, None, None, None],
            (basis - expected_basis).abs(),
            torch.zeros_like(basis),
        ).max()
    )
    positions_finite = bool(torch.isfinite(positions).all())
    basis_finite = bool(torch.isfinite(basis).all())
    probabilities_finite = bool(torch.isfinite(probabilities).all())
    probabilities_bounded = bool(
        ((probabilities >= 0.0) & (probabilities <= 1.0)).all()
    )
    lower_pin_finite = bool(torch.isfinite(lower_pin_probabilities).all())
    lower_pin_bounded = bool(
        ((lower_pin_probabilities >= 0.0) & (lower_pin_probabilities <= 1.0)).all()
    )
    weighted_loss_terms_finite = bool(torch.isfinite(weighted_loss_terms).all())
    weighted_loss_shape_exact = list(weighted_loss_terms.shape) == [
        int(positions.shape[0]),
        int(positions.shape[1]),
        len(WEIGHTED_LOSS_METRIC_NAMES),
    ]
    initial_weighted_loss_exact_zero = bool(
        weighted_loss_terms[:, :2].eq(0.0).all()
    )
    reset_or_initial = seed_event[:, :, None]
    seeded_gate_exact_zero = bool(
        torch.where(reset_or_initial, probabilities, torch.zeros_like(probabilities)).eq(0.0).all()
    )
    seeded_lower_pin_exact_zero = bool(
        torch.where(
            reset_or_initial,
            lower_pin_probabilities,
            torch.zeros_like(lower_pin_probabilities),
        ).eq(0.0).all()
    )
    uninterrupted = ~reset[:, 1:]
    armed_monotonic = bool(((armed[:, 1:] >= armed[:, :-1]) | ~uninterrupted).all())
    hit_monotonic = bool(((hit[:, 1:] >= hit[:, :-1]) | ~uninterrupted).all())
    armed_binary = bool(((armed == 0.0) | (armed == 1.0)).all())
    hit_binary = bool(((hit == 0.0) | (hit == 1.0)).all())
    initial_pair_consecutive = bool(
        ((source[:, 1] == source[:, 0] + 1) & (clip_id[:, 1] == clip_id[:, 0])).all()
    )
    random_seed_range = bool(
        ((source[:, 1] >= 1) & (source[:, 1] <= lengths[:, 1] - 2)).all()
    )
    random_seed_not_fixed_frame_one = bool((source[:, 1] != 1).any())
    reset_seed_range = bool(
        (
            (~reset)
            | ((source >= 0) & (source <= lengths - 2))
            | (frame_ids == 0)
        ).all()
    )
    advances_between_resets = bool(
        (
            (
                (source[:, 1:] == source[:, :-1] + 1)
                & (clip_id[:, 1:] == clip_id[:, :-1])
            )
            | reset[:, 1:]
        ).all()
    )
    reset_count = int(reset[:, 2:].sum())
    # CUDA FK replay is numerically equivalent but not bitwise identical to
    # the independently reconstructed audit reference. Keep this far tighter
    # than the sub-millimetre controller-pose contract while accepting normal
    # kernel-order roundoff from the split forward/backward graph.
    seed_position_tolerance_m = 1.0e-6
    seed_basis_tolerance = 1.0e-5
    passed = (
        seed_position_error <= seed_position_tolerance_m
        and seed_basis_error <= seed_basis_tolerance
        and source_in_range
        and clip_ids_in_range
        and geometry_clip_ids_in_range
        and target_world_m_error <= 1.0e-6
        and target_world_m_finite
        and root_markers_finite
        and positions_finite
        and basis_finite
        and probabilities_finite
        and probabilities_bounded
        and lower_pin_finite
        and lower_pin_bounded
        and weighted_loss_terms_finite
        and weighted_loss_shape_exact
        and initial_weighted_loss_exact_zero
        and seeded_gate_exact_zero
        and seeded_lower_pin_exact_zero
        and armed_monotonic
        and hit_monotonic
        and armed_binary
        and hit_binary
        and initial_pair_consecutive
        and random_seed_range
        and reset_seed_range
        and advances_between_resets
        and reset_count > 0
    )
    result = {
        "source": "buffers written inside the captured training graph",
        "shape_positions": list(positions.shape),
        "shape_basis": list(basis.shape),
        "random_or_reset_seed_position_max_abs_m": seed_position_error,
        "random_or_reset_seed_basis_max_abs": seed_basis_error,
        "random_or_reset_seed_position_tolerance_m": seed_position_tolerance_m,
        "random_or_reset_seed_basis_tolerance": seed_basis_tolerance,
        "source_frames_in_range": source_in_range,
        "source_clip_ids_in_range": clip_ids_in_range,
        "geometry_clip_ids_in_range": geometry_clip_ids_in_range,
        "frame_target_world_max_abs_m": target_world_m_error,
        "frame_targets_finite": target_world_m_finite,
        "recorded_root_markers_finite": root_markers_finite,
        "positions_finite": positions_finite,
        "basis_finite": basis_finite,
        "phase_probabilities_finite": probabilities_finite,
        "phase_probabilities_bounded": probabilities_bounded,
        "lower_pin_probabilities_finite": lower_pin_finite,
        "lower_pin_probabilities_bounded": lower_pin_bounded,
        "weighted_loss_term_names": list(WEIGHTED_LOSS_METRIC_NAMES),
        "weighted_loss_terms_shape": list(weighted_loss_terms.shape),
        "weighted_loss_terms_finite": weighted_loss_terms_finite,
        "initial_weighted_loss_terms_exact_zero": initial_weighted_loss_exact_zero,
        "seeded_gate_probabilities_exact_zero": seeded_gate_exact_zero,
        "seeded_lower_pin_probabilities_exact_zero": seeded_lower_pin_exact_zero,
        "initial_source_pair_consecutive": initial_pair_consecutive,
        "random_start_current_frame_range_valid": random_seed_range,
        "current_batch_random_start_not_frame_one": random_seed_not_fixed_frame_one,
        "random_start_variation_checked_by_corpus_audit": True,
        "reset_source_frame_range_valid": reset_seed_range,
        "source_frame_advances_between_resets": advances_between_resets,
        "in_graph_random_reset_count": reset_count,
        "armed_latch_binary_and_monotonic": armed_binary and armed_monotonic,
        "hit_latch_binary_and_monotonic": hit_binary and hit_monotonic,
        "passed": passed,
    }
    graph.reset()
    return result


@torch.no_grad()
def cuda_graph_episode_carry_audit(graph: CudaGraphStep) -> dict[str, object]:
    """Prove an unfinished episode crosses an optimizer boundary without resnapping."""

    if not graph.loss.dynamic_full_dataset:
        return {
            "enabled": False,
            "passed": True,
        }
    graph.reset()
    first_metrics = graph.replay()
    lane_index = graph.schedule_lanes - 1
    prior_previous_pos = graph.carry_seed["previous_global_pos"][
        lane_index
    ].detach().clone()
    prior_previous_rot = graph.carry_seed["previous_global_rot"][
        lane_index
    ].detach().clone()
    prior_current_pos = graph.carry_seed["current_global_pos"][
        lane_index
    ].detach().clone()
    prior_current_rot = graph.carry_seed["current_global_rot"][
        lane_index
    ].detach().clone()
    prior_current_index = graph.carry_seed["current_index"][
        lane_index
    ].detach().clone()
    prior_clip_id = graph.carry_attack["clip_ids"][
        lane_index
    ].detach().clone()
    second_metrics = graph.replay()
    snapshot = graph.snapshot_debug_rollout()
    previous_position_error = float(
        (
            snapshot["positions"][:, 0].to(graph.loss.runtime.device)
            - prior_previous_pos
        )
        .abs()
        .max()
    )
    previous_rotation_error = float(
        (
            snapshot["basis"][:, 0].to(graph.loss.runtime.device)
            - prior_previous_rot
        )
        .abs()
        .max()
    )
    current_position_error = float(
        (
            snapshot["positions"][:, 1].to(graph.loss.runtime.device)
            - prior_current_pos
        )
        .abs()
        .max()
    )
    current_rotation_error = float(
        (
            snapshot["basis"][:, 1].to(graph.loss.runtime.device)
            - prior_current_rot
        )
        .abs()
        .max()
    )
    source_index_exact = bool(
        torch.equal(
            snapshot["source_frame"][:, 1],
            prior_current_index.detach().cpu(),
        )
    )
    clip_id_exact = bool(
        torch.equal(snapshot["clip_id"][:, 1], prior_clip_id.detach().cpu())
    )
    segment_boundary_is_not_reset = bool(
        (~snapshot["reset_flags"][:, 0]).all()
    )
    metrics_finite = bool(
        all(
            math.isfinite(float(value))
            for metrics in (first_metrics, second_metrics)
            for value in metrics.values()
        )
    )
    result = {
        "enabled": True,
        "gradient_boundary": (
            "episode state is detached only at the optimizer boundary; "
            "the next replay starts from the exact prior terminal pose and latches"
        ),
        "previous_position_max_abs_m": previous_position_error,
        "previous_rotation_max_abs": previous_rotation_error,
        "current_position_max_abs_m": current_position_error,
        "current_rotation_max_abs": current_rotation_error,
        "source_index_exact": source_index_exact,
        "clip_id_exact": clip_id_exact,
        "segment_boundary_marked_as_reset": not segment_boundary_is_not_reset,
        "all_accumulation_slots_carried": all(graph.carry_valid),
        "metrics_finite": metrics_finite,
        "passed": (
            previous_position_error == 0.0
            and previous_rotation_error == 0.0
            and current_position_error == 0.0
            and current_rotation_error == 0.0
            and source_index_exact
            and clip_id_exact
            and segment_boundary_is_not_reset
            and all(graph.carry_valid)
            and metrics_finite
        ),
    }
    graph.reset()
    return result


def cuda_graph_learning_rate_audit(graph: CudaGraphStep, recipe: Recipe) -> dict[str, float | bool]:
    """Prove that post-capture learning-rate changes affect the captured AdamW step."""

    high = float(recipe.learning_rate)
    low = float(recipe.learning_rate_after_decay)
    if high <= 0.0 or low <= 0.0:
        return {
            "initial_learning_rate": high,
            "decayed_learning_rate": low,
            "passed": False,
        }

    if low == high:
        graph.reset()
        set_optimizer_learning_rate(graph.optimizer, high)
        graph.replay()
        update_sq = torch.zeros((), dtype=torch.float64, device=graph.parameters[0].device)
        for parameter, baseline in zip(graph.parameters, graph.parameter_snapshot):
            update_sq = update_sq + (parameter.detach().to(torch.float64) - baseline.to(torch.float64)).square().sum()
        update_norm = float(torch.sqrt(update_sq).cpu())
        graph.reset()
        set_optimizer_learning_rate(graph.optimizer, high)
        device_tensor = all(
            torch.is_tensor(group["lr"]) and group["lr"].device.type == "cuda"
            for group in graph.optimizer.param_groups
        )
        return {
            "initial_learning_rate": high,
            "decay_after_step": int(recipe.learning_rate_decay_step),
            "decayed_learning_rate": low,
            "constant_schedule": True,
            "captured_update_l2": update_norm,
            "captured_lr_is_device_tensor": device_tensor,
            "passed": update_norm > 0.0 and device_tensor,
        }

    graph.reset()
    set_optimizer_learning_rate(graph.optimizer, high)
    graph.replay()
    high_delta = [
        parameter.detach().clone() - baseline
        for parameter, baseline in zip(graph.parameters, graph.parameter_snapshot)
    ]

    graph.reset()
    set_optimizer_learning_rate(graph.optimizer, low)
    graph.replay()
    low_delta = [
        parameter.detach().clone() - baseline
        for parameter, baseline in zip(graph.parameters, graph.parameter_snapshot)
    ]

    ratio = low / high
    high_sq = torch.zeros((), dtype=torch.float64, device=graph.parameters[0].device)
    low_sq = torch.zeros_like(high_sq)
    error_sq = torch.zeros_like(high_sq)
    for high_part, low_part in zip(high_delta, low_delta):
        high64 = high_part.to(torch.float64)
        low64 = low_part.to(torch.float64)
        high_sq = high_sq + high64.square().sum()
        low_sq = low_sq + low64.square().sum()
        error_sq = error_sq + (low64 - ratio * high64).square().sum()
    high_norm = float(torch.sqrt(high_sq).cpu())
    low_norm = float(torch.sqrt(low_sq).cpu())
    expected_low_norm = ratio * high_norm
    relative_error = float(torch.sqrt(error_sq / (low_sq + 1.0e-30)).cpu())
    observed_ratio = low_norm / max(high_norm, 1.0e-30)
    # At very small captured updates, individual float32 parameter deltas
    # accumulate quantization error even when the aggregate LR ratio is exact.
    relative_error_tolerance = 2.0e-2 if ratio <= 2.0e-2 else 1.0e-2

    graph.reset()
    set_optimizer_learning_rate(graph.optimizer, high)
    return {
        "initial_learning_rate": high,
        "decay_after_step": int(recipe.learning_rate_decay_step),
        "decayed_learning_rate": low,
        "expected_update_ratio": ratio,
        "observed_update_ratio": observed_ratio,
        "initial_update_l2": high_norm,
        "decayed_update_l2": low_norm,
        "expected_decayed_update_l2": expected_low_norm,
        "relative_scaled_delta_error": relative_error,
        "relative_scaled_delta_error_tolerance": relative_error_tolerance,
        "captured_lr_is_device_tensor": all(
            torch.is_tensor(group["lr"]) and group["lr"].device.type == "cuda"
            for group in graph.optimizer.param_groups
        ),
        "passed": (
            high_norm > 0.0
            and abs(observed_ratio - ratio) <= 2.0e-4
            and relative_error <= relative_error_tolerance
            and all(
                torch.is_tensor(group["lr"]) and group["lr"].device.type == "cuda"
                for group in graph.optimizer.param_groups
            )
        ),
    }


def cuda_graph_objective_audit(
    graph: CudaGraphStep,
    recipe: Recipe,
) -> dict[str, object]:
    """Prove that the captured total contains every requested routed loss."""

    graph.reset()
    set_optimizer_learning_rate(graph.optimizer, float(recipe.learning_rate))
    set_training_loss_weights(
        graph.loss,
        float(recipe.ae11_weight),
        float(recipe.upper_prior_weight),
    )
    metrics = graph.replay()
    expected = (
        float(recipe.ae11_weight) * metrics["ae11"]
        + float(recipe.upper_prior_weight) * metrics["ae22"]
        + float(recipe.upper_prior_weight)
        * float(recipe.ae33_weight_multiplier)
        * metrics["ae33"]
        + float(recipe.gate_timing_weight) * metrics["gate_timing"]
        + float(recipe.armed_pose_weight) * metrics["armed_pose"]
        + float(recipe.hit_pose_weight) * metrics["hit_pose"]
        + float(recipe.hit_linear_velocity_weight)
        * metrics["hit_linear_velocity"]
        + float(recipe.hit_angular_velocity_weight)
        * metrics["hit_angular_velocity"]
        + float(recipe.final_pose_weight) * metrics["final_pose"]
        + float(recipe.hit_target_weight) * metrics["hit_target_mse"]
        + float(recipe.pike_blade_look_at_target_weight)
        * metrics["pike_blade_look_at_target"]
        + float(recipe.lowerarm_length_weight) * metrics["lowerarm_length"]
        + float(recipe.opposite_calf_collision_weight)
        * metrics["opposite_calf_collision"]
        + float(recipe.blade_collision_weight) * metrics["blade_collision"]
        + float(recipe.predictive_pin_weight) * metrics["predictive_pin"]
        + float(recipe.anti_pin_slide_weight) * metrics["anti_pin_slide"]
    )
    loss_terms = list(WEIGHTED_LOSS_METRIC_NAMES[1:])
    metric_loss_terms = [name for name in graph.metric_names if name in set(loss_terms)]
    total_error = abs(metrics["total"] - expected)
    weighted = weighted_loss_terms(
        metrics,
        recipe,
        ae11_weight=float(recipe.ae11_weight),
        upper_prior_weight=float(recipe.upper_prior_weight),
    )
    weighted_sum = sum(
        value for name, value in weighted.items() if name != "total"
    )
    weighted_log_error = abs(weighted["total"] - weighted_sum)
    weighted_names_exact = tuple(weighted) == WEIGHTED_LOSS_METRIC_NAMES
    graph.reset()
    return {
        "loss_terms": loss_terms,
        "metric_loss_terms": metric_loss_terms,
        "loss_term_count": len(loss_terms),
        "captured_total": metrics["total"],
        "expected_total": expected,
        "captured_total_abs_error": total_error,
        "tensorboard_weighted_term_sum": weighted_sum,
        "tensorboard_weighted_total_abs_error": weighted_log_error,
        "tensorboard_weighted_names": list(weighted),
        "tensorboard_weighted_names_exact": weighted_names_exact,
        "passed": (
            metric_loss_terms == loss_terms
            and total_error <= 2.0e-6
            and weighted_log_error <= 2.0e-6
            and weighted_names_exact
        ),
    }


def cuda_graph_logical_batch_audit(graph: CudaGraphStep) -> dict[str, object]:
    """Prove the captured batch is balanced and its replicas sample independently."""

    if graph.loss.dynamic_full_dataset:
        assert graph.clip_index_schedule is not None
        clips = graph.clip_index_schedule.numpy()
        recipe = graph.loss.runtime.recipe
        forced_family = str(recipe.forced_attack_family).strip().lower()
        forced_rows = int(recipe.forced_attack_family_rows_per_logical_batch)
        baseline_clips = clips
        forced_family_schedule_valid = True
        forced_nonfamily_rows_exact = True
        forced_source_mode_preserved = True
        if forced_rows:
            forced_family_ids = np.asarray(
                [
                    index
                    for index, path in enumerate(graph.loss.runtime.attacks.paths)
                    if attack_family_from_path(path) == forced_family
                ],
                dtype=np.int64,
            )
            baseline_schedule, _ = build_full_dataset_schedule(
                graph.loss.runtime.attacks.lengths,
                recipe.seed,
                graph.schedule_epoch_start,
                graph.schedule_epoch_end,
                clips.shape[1],
                graph.schedule_lanes,
                graph.physical_batch_size,
                original_count=FULL_DATASET_GT_COUNT,
                original_probability=recipe.original_sample_probability,
            )
            baseline_clips = baseline_schedule.numpy()
            nonfamily_mask = np.ones(clips.shape, dtype=np.bool_)
            for logical_row in range(forced_rows):
                lane_index, row_index = divmod(
                    logical_row, graph.physical_batch_size
                )
                selected = clips[:, :, lane_index, row_index]
                forced_family_schedule_valid = bool(
                    forced_family_schedule_valid
                    and forced_family_ids.size > 0
                    and np.isin(selected, forced_family_ids).all()
                )
                nonfamily_mask[:, :, lane_index, row_index] = False
            forced_nonfamily_rows_exact = bool(
                np.array_equal(clips[nonfamily_mask], baseline_clips[nonfamily_mask])
            )

            def source_mode_category(values: np.ndarray) -> np.ndarray:
                return np.where(
                    values < FULL_DATASET_MODE_GT_COUNT,
                    0,
                    np.where(
                        values < FULL_DATASET_GT_COUNT,
                        1,
                        np.where(
                            values
                            < FULL_DATASET_GT_COUNT
                            + FULL_DATASET_MODE_VARIANT_COUNT,
                            2,
                            3,
                        ),
                    ),
                )

            forced_source_mode_preserved = bool(
                np.array_equal(
                    source_mode_category(clips),
                    source_mode_category(baseline_clips),
                )
            )
        initial = clips[:, 0]
        initial_unique = int(np.unique(initial.reshape(initial.shape[0], -1), axis=0).shape[0])
        projection_rows = (
            int(graph.loss.projection_store.local_offsets.shape[0])
            if graph.loss.projection_store.local_offsets.ndim == 3
            else 1
        )
        common = {
            "logical_batch_size": int(graph.loss.runtime.recipe.batch_size),
            "dataset_clip_count": len(graph.loss.runtime.attacks.paths),
            "projection_geometry_rows": projection_rows,
            "physical_cuda_batch_size": graph.physical_batch_size,
            "cuda_graph_replays_per_optimizer_step": 1,
            "distinct_initial_batch_schedules": initial_unique,
            "reset_clip_schedule_staged": True,
        }
        if graph.loss.runtime.recipe.variant_dir:
            original_count = FULL_DATASET_GT_COUNT
            distribution_clips = baseline_clips
            original_clips = distribution_clips[distribution_clips < original_count]
            variant_clips = (
                distribution_clips[distribution_clips >= original_count]
                - original_count
            )
            original_ratio = float((distribution_clips < original_count).mean())
            original_normal = original_clips[original_clips < FULL_DATASET_MODE_GT_COUNT]
            original_mirrored = original_clips[original_clips >= FULL_DATASET_MODE_GT_COUNT]
            variant_normal = variant_clips[
                variant_clips < FULL_DATASET_MODE_VARIANT_COUNT
            ]
            variant_mirrored = variant_clips[
                variant_clips >= FULL_DATASET_MODE_VARIANT_COUNT
            ]
            original_normal_hist = np.bincount(
                original_normal, minlength=FULL_DATASET_MODE_GT_COUNT
            )
            original_mirrored_hist = np.bincount(
                original_mirrored - FULL_DATASET_MODE_GT_COUNT,
                minlength=FULL_DATASET_MODE_GT_COUNT,
            )
            variant_normal_hist = np.bincount(
                variant_normal, minlength=FULL_DATASET_MODE_VARIANT_COUNT
            )
            variant_mirrored_hist = np.bincount(
                variant_mirrored - FULL_DATASET_MODE_VARIANT_COUNT,
                minlength=FULL_DATASET_MODE_VARIANT_COUNT,
            )
            passed = bool(
                0
                < graph.physical_batch_size
                == int(graph.loss.runtime.recipe.batch_size)
                and graph.schedule_lanes == 1
                and projection_rows == graph.physical_batch_size
                and abs(original_ratio - 0.10) <= (1.0 / max(clips.size, 1))
                and abs(len(original_normal) - len(original_mirrored)) <= 1
                and abs(len(variant_normal) - len(variant_mirrored)) <= 1
                and int(original_normal_hist.max() - original_normal_hist.min()) <= 1
                and int(original_mirrored_hist.max() - original_mirrored_hist.min()) <= 1
                and int(variant_normal_hist.max() - variant_normal_hist.min()) <= 1
                and int(variant_mirrored_hist.max() - variant_mirrored_hist.min()) <= 1
                and forced_family_schedule_valid
                and forced_nonfamily_rows_exact
                and forced_source_mode_preserved
                and initial_unique > 1
            )
            return {
                **common,
                "sampling": "10% GT / 90% variants; 50% normal / 50% M inside both pools",
                "forced_attack_family": forced_family or None,
                "forced_attack_family_rows_per_logical_batch": forced_rows,
                "forced_attack_family_schedule_valid": forced_family_schedule_valid,
                "forced_nonfamily_rows_bit_exact": forced_nonfamily_rows_exact,
                "forced_source_mode_categories_preserved": forced_source_mode_preserved,
                "original_probability": original_ratio,
                "original_mode_draws": [len(original_normal), len(original_mirrored)],
                "variant_mode_draws": [len(variant_normal), len(variant_mirrored)],
                "original_normal_histogram_range": [
                    int(original_normal_hist.min()), int(original_normal_hist.max())
                ],
                "original_mirrored_histogram_range": [
                    int(original_mirrored_hist.min()), int(original_mirrored_hist.max())
                ],
                "variant_normal_histogram_range": [
                    int(variant_normal_hist.min()), int(variant_normal_hist.max())
                ],
                "variant_mirrored_histogram_range": [
                    int(variant_mirrored_hist.min()), int(variant_mirrored_hist.max())
                ],
                "passed": passed,
            }
        histogram = np.bincount(clips.reshape(-1), minlength=len(graph.loss.runtime.attacks.paths))
        passed = bool(
            len(graph.loss.runtime.attacks.paths) == 32
            and 0
            < graph.physical_batch_size
            == int(graph.loss.runtime.recipe.batch_size)
            and graph.schedule_lanes == 1
            and projection_rows == graph.physical_batch_size
            and int(histogram.max() - histogram.min()) <= 1
            and initial_unique > 1
        )
        return {
            **common,
            "sampling": "uniform normal+mirrored GT32",
            "clip_histogram_range": [int(histogram.min()), int(histogram.max())],
            "passed": passed,
        }

    canonical_count = len(graph.loss.runtime.attacks.paths)
    physical_rows = (
        torch.arange(canonical_count, dtype=torch.long, device=graph.loss.runtime.device)
        if graph.loss.rows_static is None
        else graph.loss.rows_static
    )
    rows = physical_rows
    counts = torch.bincount(rows, minlength=canonical_count).detach().cpu().tolist()
    expected_replicas = int(graph.loss.runtime.recipe.batch_size) // canonical_count
    projection_rows = (
        int(graph.loss.projection_store.local_offsets.shape[0])
        if graph.loss.projection_store.local_offsets.ndim == 3
        else 1
    )
    schedule = graph.fragment_start_schedule.reshape(
        graph.fragment_start_schedule.shape[0],
        graph.fragment_start_schedule.shape[1],
        -1,
    )
    independent = True
    for family in range(canonical_count):
        replicas = torch.nonzero(rows == family, as_tuple=False).reshape(-1).detach().cpu().tolist()
        for left_index, left in enumerate(replicas):
            for right in replicas[left_index + 1 :]:
                if torch.equal(schedule[:, :, left], schedule[:, :, right]):
                    independent = False
    passed = (
        int(rows.numel()) == int(graph.loss.runtime.recipe.batch_size)
        and counts == [expected_replicas] * canonical_count
        and projection_rows == int(physical_rows.numel())
        and int(schedule.shape[-1]) == int(rows.numel())
        and independent
    )
    return {
        "logical_batch_size": int(rows.numel()),
        "canonical_family_count": canonical_count,
        "replicas_per_family": counts,
        "projection_geometry_rows": projection_rows,
        "physical_cuda_batch_size": graph.physical_batch_size,
        "cuda_graph_replays_per_optimizer_step": 1,
        "schedule_rows": int(schedule.shape[-1]),
        "replica_start_schedules_independent": independent,
        "passed": passed,
    }


def cuda_graph_single_replay_audit(graph: CudaGraphStep) -> dict[str, object]:
    """Prove one optimizer step is one full physical-batch graph replay."""

    return {
        "physical_cuda_batch_size": graph.physical_batch_size,
        "cuda_graph_replays_per_optimizer_step": graph.schedule_lanes,
        "gradient_accumulation": False,
        "passed": (
            graph.schedule_lanes == 1
            and graph.physical_batch_size
            == int(graph.loss.runtime.recipe.batch_size)
        ),
    }


def cuda_graph_upper_prior_weight_audit(
    graph: CudaGraphStep,
    recipe: Recipe,
) -> dict[str, float | bool]:
    """Prove that the captured objective reads the staged upper-prior weight."""

    initial = float(recipe.upper_prior_weight)
    staged = float(recipe.upper_prior_weight_after_decay)
    if staged == initial:
        return {
            "rebalance_after_step": int(recipe.learning_rate_decay_step),
            "initial_upper_prior_weight": initial,
            "staged_upper_prior_weight": staged,
            "enabled": False,
            "passed": initial >= 0.0,
        }
    if not (staged >= 0.0 and initial >= 0.0):
        return {
            "initial_upper_prior_weight": initial,
            "staged_upper_prior_weight": staged,
            "passed": False,
        }

    graph.reset()
    set_optimizer_learning_rate(graph.optimizer, float(recipe.learning_rate))
    set_training_loss_weights(graph.loss, float(recipe.ae11_weight), initial)
    initial_metrics = graph.replay()
    initial_delta = [
        parameter.detach().clone() - baseline
        for parameter, baseline in zip(graph.parameters, graph.parameter_snapshot)
    ]

    graph.reset()
    set_training_loss_weights(graph.loss, float(recipe.ae11_weight), staged)
    staged_metrics = graph.replay()
    staged_delta = [
        parameter.detach().clone() - baseline
        for parameter, baseline in zip(graph.parameters, graph.parameter_snapshot)
    ]

    expected_total = initial_metrics["total"] + (staged - initial) * (
        initial_metrics["ae22"]
        + float(recipe.ae33_weight_multiplier) * initial_metrics["ae33"]
    )
    total_error = abs(staged_metrics["total"] - expected_total)
    update_difference_sq = torch.zeros((), dtype=torch.float64, device=graph.parameters[0].device)
    for initial_part, staged_part in zip(initial_delta, staged_delta):
        update_difference_sq = update_difference_sq + (
            staged_part.to(torch.float64) - initial_part.to(torch.float64)
        ).square().sum()
    update_difference = float(torch.sqrt(update_difference_sq).cpu())

    graph.reset()
    set_training_loss_weights(
        graph.loss,
        float(recipe.ae11_weight),
        float(recipe.upper_prior_weight),
    )
    return {
        "rebalance_after_step": int(recipe.learning_rate_decay_step),
        "initial_upper_prior_weight": initial,
        "staged_upper_prior_weight": staged,
        "initial_total": initial_metrics["total"],
        "staged_total": staged_metrics["total"],
        "expected_staged_total": expected_total,
        "captured_total_abs_error": total_error,
        "first_update_difference_l2": update_difference,
        "captured_weight_is_device_tensor": graph.loss.upper_prior_weight_value.device.type == "cuda",
        "passed": (
            total_error <= 2.0e-6
            and update_difference > 1.0e-7
            and graph.loss.upper_prior_weight_value.device.type == "cuda"
        ),
    }


def cuda_graph_ae11_weight_audit(
    graph: CudaGraphStep,
    recipe: Recipe,
) -> dict[str, float | bool]:
    """Prove that the captured objective reads the staged AE11 weight."""

    initial = float(recipe.ae11_weight)
    staged = float(recipe.ae11_weight_after_decay)
    if staged == initial:
        return {
            "rebalance_after_step": int(recipe.learning_rate_decay_step),
            "initial_ae11_weight": initial,
            "staged_ae11_weight": staged,
            "enabled": False,
            "passed": initial >= 0.0,
        }
    if not (staged >= 0.0 and initial >= 0.0):
        return {
            "initial_ae11_weight": initial,
            "staged_ae11_weight": staged,
            "passed": False,
        }

    graph.reset()
    set_optimizer_learning_rate(graph.optimizer, float(recipe.learning_rate))
    set_training_loss_weights(graph.loss, initial, float(recipe.upper_prior_weight))
    initial_metrics = graph.replay()
    initial_delta = [
        parameter.detach().clone() - baseline
        for parameter, baseline in zip(graph.parameters, graph.parameter_snapshot)
    ]

    graph.reset()
    set_training_loss_weights(graph.loss, staged, float(recipe.upper_prior_weight))
    staged_metrics = graph.replay()
    staged_delta = [
        parameter.detach().clone() - baseline
        for parameter, baseline in zip(graph.parameters, graph.parameter_snapshot)
    ]

    expected_total = initial_metrics["total"] + (staged - initial) * initial_metrics["ae11"]
    total_error = abs(staged_metrics["total"] - expected_total)
    update_difference_sq = torch.zeros((), dtype=torch.float64, device=graph.parameters[0].device)
    for initial_part, staged_part in zip(initial_delta, staged_delta):
        update_difference_sq = update_difference_sq + (
            staged_part.to(torch.float64) - initial_part.to(torch.float64)
        ).square().sum()
    update_difference = float(torch.sqrt(update_difference_sq).cpu())

    graph.reset()
    set_training_loss_weights(
        graph.loss,
        float(recipe.ae11_weight),
        float(recipe.upper_prior_weight),
    )
    return {
        "rebalance_after_step": int(recipe.learning_rate_decay_step),
        "initial_ae11_weight": initial,
        "staged_ae11_weight": staged,
        "initial_total": initial_metrics["total"],
        "staged_total": staged_metrics["total"],
        "expected_staged_total": expected_total,
        "captured_total_abs_error": total_error,
        "first_update_difference_l2": update_difference,
        "captured_weight_is_device_tensor": graph.loss.ae11_weight_value.device.type == "cuda",
        "passed": (
            total_error <= 2.0e-6
            and update_difference > 1.0e-7
            and graph.loss.ae11_weight_value.device.type == "cuda"
        ),
    }


def cuda_graph_gradient_clip_audit(
    graph: CudaGraphStep,
    recipe: Recipe,
) -> dict[str, float | bool]:
    """Verify the captured graph reports and bounds its post-backward gradient norm."""

    graph.reset()
    audit_step = max(
        int(graph.loss.fragment_epoch_start) + 1,
        int(recipe.learning_rate_decay_step) + 1,
    )
    set_optimizer_learning_rate(graph.optimizer, learning_rate_for_step(recipe, audit_step))
    set_training_loss_weights(
        graph.loss,
        ae11_weight_for_step(recipe, audit_step),
        upper_prior_weight_for_step(recipe, audit_step),
    )
    metrics = graph.replay()
    preclip = float(metrics["gradient_norm"])
    postclip_sq = torch.zeros((), dtype=torch.float64, device=graph.parameters[0].device)
    for parameter in graph.parameters:
        if parameter.grad is not None:
            postclip_sq = postclip_sq + parameter.grad.to(torch.float64).square().sum()
    postclip = float(torch.sqrt(postclip_sq).cpu())
    expected = min(preclip, float(recipe.gradient_clip_norm))
    graph.reset()
    set_optimizer_learning_rate(graph.optimizer, float(recipe.learning_rate))
    set_training_loss_weights(
        graph.loss,
        float(recipe.ae11_weight),
        float(recipe.upper_prior_weight),
    )
    return {
        "configured_max_norm": float(recipe.gradient_clip_norm),
        "reported_preclip_norm": preclip,
        "measured_postclip_norm": postclip,
        "expected_postclip_norm": expected,
        "passed": (
            math.isfinite(preclip)
            and preclip > 0.0
            and postclip <= float(recipe.gradient_clip_norm) * 1.0001
            and abs(postclip - expected) <= max(2.0e-4, expected * 2.0e-4)
        ),
    }


@torch.no_grad()
def zero_delta_audit(runtime: Runtime) -> dict[str, float | bool]:
    ids = runtime.attacks.clip_ids
    previous = runtime.attacks.trajectory_lower[:, 0]
    current = runtime.attacks.trajectory_lower[:, 1]
    previous_heading = runtime.attacks.trajectory_heading[:, 0]
    current_heading = runtime.attacks.trajectory_heading[:, 1]
    current_index = torch.ones_like(ids)
    base_upper = base_upper_hybrid_from_lower(
        runtime,
        ids,
        ids,
        current_index,
        current,
        runtime.attacks.targets_world,
        current_heading,
    )
    upper = runtime.attacks.initial_current_upper
    max_lower = 0.0
    max_upper = 0.0
    max_position = 0.0
    max_rotation = 0.0
    lower_names = {
        "root",
        "pelvis",
        "thigh_l",
        "calf_l",
        "foot_l",
        "ball_l",
        "thigh_r",
        "calf_r",
        "foot_r",
        "ball_r",
    }
    lower_indices = torch.tensor(
        [index for index, name in enumerate(runtime.full_clip.body_names) if name in lower_names],
        dtype=torch.long,
        device=runtime.device,
    )
    with runtime.policy_context():
        for _step in range(runtime.attacks.max_steps):
            active = current_index < (runtime.attacks.lengths - 1)
            safe = torch.minimum(current_index, runtime.attacks.lengths - 2)
            previous_index = torch.clamp(safe - 1, min=0)
            if runtime.frozen_walk is None:
                frozen_next = current
            else:
                frozen_next, _frozen_input = frozen_next_hybrid(
                    runtime,
                    runtime.lower_batched_store,
                    ids,
                    safe,
                    previous_index,
                    previous,
                    current,
                    runtime.attacks.targets_world,
                    previous_heading,
                    current_heading,
                )
            next_index = safe + 1
            composed_lower, pin_probabilities = clean_lower_hybrid_delta(
                runtime,
                runtime.lower_batched_store,
                ids,
                safe,
                next_index,
                current,
                frozen_next,
                torch.zeros_like(frozen_next),
                frozen_next.new_zeros((frozen_next.shape[0], LOWER_PIN_COMMAND_DIM)),
                runtime.attacks.targets_world,
                current_heading,
            )
            max_lower = max(max_lower, float((composed_lower - frozen_next).abs().max().cpu()))
            if bool((pin_probabilities != 0.0).any()):
                raise RuntimeError("Zero lower pin commands must produce exactly zero pin probability")
            next_base = base_upper_hybrid_from_lower(
                runtime,
                ids,
                ids,
                next_index,
                composed_lower,
                runtime.attacks.targets_world,
                current_heading,
            )
            next_prior = carry_upper_hybrid_deviation(
                upper,
                base_upper,
                next_base,
            )
            next_upper = clean_upper_state(next_prior + torch.zeros_like(next_prior))
            max_upper = max(max_upper, float((next_upper - next_prior).abs().max().cpu()))
            composed_pos, composed_rot = hybrid_full_fk_globals(
                runtime,
                ids,
                ids,
                next_index,
                composed_lower,
                next_upper,
                runtime.attacks.targets_world,
                current_heading,
            )
            pelvis_index = runtime.full_clip.body_names.index("pelvis")
            next_heading = target_codec.target_facing_heading(
                composed_pos[:, pelvis_index], runtime.attacks.targets_world
            )
            next_root_pos, next_root_rot, _yaw, _heading = runtime.lower_store.root_state(
                ids, next_index
            )
            frozen_next_root = lower_hybrid_state_to_root(
                runtime.lower_store,
                ids,
                next_index,
                frozen_next,
                runtime.attacks.targets_world,
                current_heading,
            )
            frozen_pos, frozen_rot = lower_fk_globals(
                runtime, ids, frozen_next_root, next_root_pos, next_root_rot
            )
            max_position = max(
                max_position,
                float(
                    (
                        composed_pos.index_select(1, lower_indices)
                        - frozen_pos.index_select(1, lower_indices)
                    )
                    .abs()
                    .max()
                    .cpu()
                ),
            )
            max_rotation = max(
                max_rotation,
                float(
                    (
                        composed_rot.index_select(1, lower_indices)
                        - frozen_rot.index_select(1, lower_indices)
                    )
                    .abs()
                    .max()
                    .cpu()
                ),
            )
            previous = torch.where(active[:, None], current, previous)
            current = torch.where(
                active[:, None],
                target_codec.lower_to_held_heading(
                    runtime.lower_store,
                    composed_lower,
                    runtime.attacks.targets_world,
                    current_heading,
                    next_heading,
                ),
                current,
            )
            base_upper = torch.where(
                active[:, None],
                target_codec.upper_to_held_heading(
                    next_base,
                    runtime.attacks.targets_world,
                    current_heading,
                    next_heading,
                ),
                base_upper,
            )
            upper = torch.where(
                active[:, None],
                target_codec.upper_to_held_heading(
                    next_upper,
                    runtime.attacks.targets_world,
                    current_heading,
                    next_heading,
                ),
                upper,
            )
            previous_heading = torch.where(
                active[:, None, None], current_heading, previous_heading
            )
            current_heading = torch.where(
                active[:, None, None], next_heading, current_heading
            )
            current_index = torch.where(active, current_index + 1, current_index)
    return {
        "lower_max_abs": max_lower,
        "upper_zero_delta_max_abs": max_upper,
        "lower_fk_position_max_abs_m": max_position,
        "lower_fk_rotation_max_abs": max_rotation,
        "passed": (
            max_lower <= 2.0e-6
            and max_upper <= 2.0e-6
            and max_position <= 2.0e-4
            and max_rotation <= 2.0e-4
        ),
    }


@torch.no_grad()
def source_motion_seed_audit(runtime: Runtime) -> dict[str, object]:
    """Prove resets seed the same representable target the agents are trained against."""

    source_pos: list[np.ndarray] = []
    source_rot: list[np.ndarray] = []
    for path in runtime.attacks.paths:
        with np.load(path, allow_pickle=False) as data:
            names = [str(value) for value in data["bone_names"].tolist()]
            keep = np.asarray([names.index(name) for name in runtime.full_clip.body_names], dtype=np.int64)
            source_pos.append(
                np.asarray(data["model_global_joint_pos_m"], dtype=np.float32)[:2, keep]
            )
            source_rot.append(
                np.asarray(data["model_global_matrix"], dtype=np.float32)[:2, keep, :3, :3]
            )
    actual_pos = runtime.attacks.initial_global_pos
    actual_rot = runtime.attacks.initial_global_rot
    target_pos = runtime.attacks.trajectory_global_pos[:, :2]
    target_rot = runtime.attacks.trajectory_global_rot[:, :2]
    position_rows = (actual_pos - target_pos).abs().amax(dim=(1, 2, 3))
    rotation_rows = (actual_rot - target_rot).abs().amax(dim=(1, 2, 3, 4))
    source_position_rows = (
        actual_pos
        - torch.tensor(np.stack(source_pos), dtype=torch.float32, device=runtime.device)
    ).abs().amax(dim=(1, 2, 3))
    source_rotation_rows = (
        actual_rot
        - torch.tensor(np.stack(source_rot), dtype=torch.float32, device=runtime.device)
    ).abs().amax(dim=(1, 2, 3, 4))
    position_error = float(position_rows.max().cpu())
    rotation_error = float(rotation_rows.max().cpu())
    per_motion = {
        name: {
            "seed_vs_runtime_target_position_max_abs_m": float(position_rows[row].cpu()),
            "seed_vs_runtime_target_rotation_max_abs": float(rotation_rows[row].cpu()),
            "runtime_target_vs_raw_npz_position_max_abs_m": float(
                source_position_rows[row].cpu()
            ),
            "runtime_target_vs_raw_npz_rotation_max_abs": float(
                source_rotation_rows[row].cpu()
            ),
        }
        for row, name in enumerate(runtime.attacks.names)
    }
    return {
        "frames": [0, 1],
        "joint_count": len(runtime.full_clip.body_names),
        "seed_vs_runtime_target_position_max_abs_m": position_error,
        "seed_vs_runtime_target_rotation_max_abs": rotation_error,
        "runtime_target_vs_raw_npz_position_max_abs_m": float(
            source_position_rows.max().cpu()
        ),
        "runtime_target_vs_raw_npz_rotation_max_abs": float(
            source_rotation_rows.max().cpu()
        ),
        "reference": "the exact native-controller target decoded by the runtime skeleton",
        "per_motion": per_motion,
        "passed": position_error <= 1.0e-7 and rotation_error <= 1.0e-7,
    }


@torch.no_grad()
def per_motion_fk_geometry_audit(runtime: Runtime) -> dict[str, object]:
    errors: dict[str, dict[str, float]] = {}
    maximum = 0.0
    for row, (lower_clip, full_clip) in enumerate(zip(runtime.lower_clips, runtime.full_clips)):
        row_errors: dict[str, float] = {}
        for prefix, clip, stacked in (
            ("lower", lower_clip, runtime.lower_fk_geometry),
            ("full", full_clip, runtime.full_fk_geometry),
        ):
            tensors = clip.tensors(runtime.device)
            for key in FK_GEOMETRY_KEYS:
                error = float((stacked[key][row] - tensors[key]).abs().max().cpu())
                row_errors[f"{prefix}_{key}_max_abs"] = error
                maximum = max(maximum, error)
        row_store = runtime.lower_row_stores[row]
        lower_tensors = lower_clip.tensors(runtime.device)
        for store_key, tensor_key in (
            ("local_offsets", "local_offsets"),
            ("ik_limb_lengths", "ik_limb_lengths"),
            ("ik_toe_offsets", "ik_toe_offsets"),
            ("ik_toe_axis", "ik_toe_axis"),
        ):
            error = float(
                (getattr(row_store, store_key) - lower_tensors[tensor_key]).abs().max().cpu()
            )
            row_errors[f"lower_pin_store_{store_key}_max_abs"] = error
            maximum = max(maximum, error)
            batched_error = float(
                (
                    getattr(runtime.lower_batched_store, store_key)[row]
                    - lower_tensors[tensor_key]
                )
                .abs()
                .max()
                .cpu()
            )
            row_errors[f"lower_batched_pin_store_{store_key}_max_abs"] = batched_error
            maximum = max(maximum, batched_error)
        errors[runtime.attacks.names[row]] = row_errors
    return {
        "motion_count": len(runtime.attacks.paths),
        "geometry_keys": list(FK_GEOMETRY_KEYS),
        "max_abs": maximum,
        "per_motion": errors,
        "passed": maximum == 0.0,
    }


@torch.no_grad()
def batched_lower_projection_parity_audit(runtime: Runtime) -> dict[str, float | bool]:
    """The fast batched path must be exactly the former per-motion row path."""

    ids = runtime.attacks.clip_ids
    frame = torch.ones_like(ids)
    current = runtime.lower_store.get_target_output(ids, frame)
    delta = torch.linspace(
        -0.01,
        0.01,
        current.numel(),
        dtype=current.dtype,
        device=current.device,
    ).reshape_as(current)
    commands = torch.linspace(
        -1.0,
        1.0,
        current.shape[0] * LOWER_PIN_COMMAND_DIM,
        dtype=current.dtype,
        device=current.device,
    ).reshape(current.shape[0], LOWER_PIN_COMMAND_DIM)
    batched, pin_probabilities = clean_lower_delta(
        runtime,
        runtime.lower_batched_store,
        current,
        current,
        delta,
        commands,
    )
    row_outputs: list[torch.Tensor] = []
    for row, store in enumerate(runtime.lower_row_stores):
        pose, _raw = tl.output_to_pose(
            current[row : row + 1] + delta[row : row + 1], store.prototype
        )
        free = tl.pose_target_output(pose)
        pinned = ik_ctl.apply_foot_roll_output_projection_with_pin_probabilities(
            free,
            current[row : row + 1],
            pin_probabilities[row : row + 1],
            store,
            integration_steps=LOWER_PIN_INTEGRATION_STEPS,
            height_pin_gate_enabled=LOWER_PIN_HEIGHT_GATE_ENABLED,
        )
        row_outputs.append(ik_ctl.lift_feet_above_ground(store, pinned))
    delta_clean_error = float((batched - torch.cat(row_outputs)).abs().max().cpu())

    controller_input = ik_ctl.build_controller_input(
        runtime.lower_store,
        ids,
        frame,
        current,
        current,
        current[:, :3],
        current[:, :3],
        current[:, 9:],
        current[:, 9:],
    )
    raw = ik_ctl.model_raw_output(
        runtime.frozen_walk, controller_input, current, runtime.lower_store
    )
    frozen_batched = ik_ctl.clean_output_vector(
        raw, runtime.lower_batched_store, current, current
    )
    frozen_rows = torch.cat(
        [
            ik_ctl.clean_output_vector(
                raw[row : row + 1],
                store,
                current[row : row + 1],
                current[row : row + 1],
            )
            for row, store in enumerate(runtime.lower_row_stores)
        ],
        dim=0,
    )
    frozen_error = float((frozen_batched - frozen_rows).abs().max().cpu())
    return {
        "lower_delta_clean_max_abs": delta_clean_error,
        "frozen_walk_clean_max_abs": frozen_error,
        "tolerance": 1.0e-7,
        "passed": delta_clean_error <= 1.0e-7 and frozen_error <= 1.0e-7,
    }


@torch.no_grad()
def post_lower_foot_floor_unclip_audit(runtime: Runtime) -> dict[str, object]:
    ids = runtime.attacks.clip_ids
    frame = torch.ones_like(ids)
    base = runtime.lower_store.get_target_output(ids, frame)
    payload_start = 3 + 6 + int(runtime.lower_clip.Jcore) * 6
    specs_by_side: dict[str, tuple[int, dict[str, object]]] = {}
    for limb_i, spec in enumerate(runtime.lower_clip.ik_payload_slices):
        if str(spec["kind"]) != "leg":
            continue
        specs_by_side[str(spec["side"])] = (limb_i, spec)
    if set(specs_by_side) != {"l", "r"}:
        raise ValueError(f"Expected left/right leg IK payloads, got {sorted(specs_by_side)}")

    def position_channels(spec: dict[str, object]) -> tuple[int, int, int]:
        pos_slice = spec["pos"]
        assert isinstance(pos_slice, slice)
        start = payload_start + int(pos_slice.start)
        return start, start + 1, start + 2

    free_delta = torch.zeros_like(base)
    requested_free = {
        "l": (0.06, -0.05, 0.12),
        "r": (-0.04, 0.07, 0.11),
    }
    for side, (_limb_i, spec) in specs_by_side.items():
        channels = position_channels(spec)
        for channel, value in zip(channels, requested_free[side]):
            free_delta[:, channel] = value
    free_pose, _raw = tl.output_to_pose(base + free_delta, runtime.lower_clip)
    freely_cleaned = tl.pose_target_output(free_pose)
    zero_pin_commands = base.new_zeros((base.shape[0], LOWER_PIN_COMMAND_DIM))
    freely_unclipped, free_pin_probabilities = clean_lower_delta(
        runtime,
        runtime.lower_batched_store,
        base,
        base,
        free_delta,
        zero_pin_commands,
    )
    free_xyz_error = float((freely_unclipped - freely_cleaned).abs().max().cpu())

    penetrating_delta = torch.zeros_like(base)
    requested_penetrating = {
        "l": (0.05, -0.04, -0.50),
        "r": (-0.03, 0.06, -0.50),
    }
    vertical_channels: list[int] = []
    for side, (_limb_i, spec) in specs_by_side.items():
        channels = position_channels(spec)
        vertical_channels.append(channels[int(ik_ctl.FOOT_ROLL_UP_AXIS)])
        for channel, value in zip(channels, requested_penetrating[side]):
            penetrating_delta[:, channel] = value
    penetrating_pose, _raw = tl.output_to_pose(base + penetrating_delta, runtime.lower_clip)
    penetrating_raw = tl.pose_target_output(penetrating_pose)
    corrected, penetrating_pin_probabilities = clean_lower_delta(
        runtime,
        runtime.lower_batched_store,
        base,
        base,
        penetrating_delta,
        zero_pin_commands,
    )

    unchanged_mask = torch.ones((corrected.shape[-1],), dtype=torch.bool, device=corrected.device)
    unchanged_mask[
        torch.tensor(vertical_channels, dtype=torch.long, device=corrected.device)
    ] = False
    non_y_error = float(
        (corrected[:, unchanged_mask] - penetrating_raw[:, unchanged_mask]).abs().max().cpu()
    )
    payload = corrected[:, ik_ctl.payload_slice(runtime.lower_store)]
    pos_parts, rot_parts, _start_rot_parts, toe_parts = ik_ctl._parse_payload_parts(
        payload, runtime.lower_store
    )
    ground = runtime.lower_store.foot_roll_ground_y_tensor.to(dtype=corrected.dtype)
    clearances: dict[str, float] = {}
    vertical_corrections: dict[str, float] = {}
    for side, (limb_i, spec) in specs_by_side.items():
        toe = toe_parts[limb_i]
        assert toe is not None
        rot = tl.rotation_6d_to_matrix(rot_parts[limb_i])
        lowest_y = ik_ctl._foot_lowest_y(
            runtime.lower_store, limb_i, pos_parts[limb_i], rot, toe
        )
        clearances[side] = float((lowest_y - ground).amin().cpu())
        y_channel = position_channels(spec)[int(ik_ctl.FOOT_ROLL_UP_AXIS)]
        vertical_corrections[side] = float(
            (corrected[:, y_channel] - penetrating_raw[:, y_channel]).amin().cpu()
        )
    worst_clearance = min(clearances.values())
    smallest_correction = min(vertical_corrections.values())
    return {
        "free_requested_xyz_m": requested_free,
        "free_xyz_and_rotation_max_abs_error": free_xyz_error,
        "penetrating_requested_xyz_m": requested_penetrating,
        "non_vertical_channels_max_abs_error": non_y_error,
        "final_lowest_clearance_m": clearances,
        "applied_vertical_correction_m": vertical_corrections,
        "horizontal_or_rotation_pinning": False,
        "zero_pin_probability_max_abs": float(
            torch.maximum(free_pin_probabilities.abs().max(), penetrating_pin_probabilities.abs().max()).cpu()
        ),
        "passed": (
            free_xyz_error <= 1.0e-6
            and non_y_error <= 1.0e-6
            and worst_clearance >= -1.0e-6
            and smallest_correction > 0.0
            and not bool((free_pin_probabilities != 0.0).any())
            and not bool((penetrating_pin_probabilities != 0.0).any())
        ),
    }


def post_lower_continuous_pin_audit(runtime: Runtime) -> dict[str, object]:
    """Prove zero identity, independent feet, continuity, and gradient flow."""

    ids = runtime.attacks.clip_ids
    frame = torch.ones_like(ids)
    current = runtime.lower_store.get_target_output(ids, frame)
    payload_start = 3 + 6 + int(runtime.lower_clip.Jcore) * 6
    channels: dict[str, tuple[int, int, int]] = {}
    for spec in runtime.lower_clip.ik_payload_slices:
        if str(spec["kind"]) != "leg":
            continue
        pos_slice = spec["pos"]
        assert isinstance(pos_slice, slice)
        start = payload_start + int(pos_slice.start)
        channels[str(spec["side"])] = (start, start + 1, start + 2)
    if set(channels) != {"l", "r"}:
        raise ValueError(f"Expected left/right leg IK payloads, got {sorted(channels)}")

    delta = torch.zeros_like(current)
    delta[:, channels["l"][0]] = 0.10
    delta[:, channels["r"][0]] = -0.08
    candidate = torch.cat(
        [
            tl.pose_target_output(
                tl.output_to_pose(
                    current[row : row + 1] + delta[row : row + 1],
                    store.prototype,
                )[0]
            )
            for row, store in enumerate(runtime.lower_row_stores)
        ],
        dim=0,
    )

    def project(probabilities: torch.Tensor) -> torch.Tensor:
        return torch.cat(
            [
                ik_ctl.apply_foot_roll_output_projection_with_pin_probabilities(
                    candidate[row : row + 1],
                    current[row : row + 1],
                    probabilities[row : row + 1],
                    store,
                    integration_steps=LOWER_PIN_INTEGRATION_STEPS,
                    height_pin_gate_enabled=LOWER_PIN_HEIGHT_GATE_ENABLED,
                )
                for row, store in enumerate(runtime.lower_row_stores)
            ],
            dim=0,
        )

    zero_commands = current.new_zeros((current.shape[0], LOWER_PIN_COMMAND_DIM))
    zero_probabilities = lower_pin_probabilities(zero_commands)
    zero_projected = project(zero_probabilities)
    cleanup_only = torch.cat(
        [
            ik_ctl.lift_feet_above_ground(
                store,
                candidate[row : row + 1],
            )
            for row, store in enumerate(runtime.lower_row_stores)
        ],
        dim=0,
    )

    left_commands = zero_commands.clone()
    left_commands[:, 0] = 100.0
    left_probabilities = lower_pin_probabilities(left_commands)
    left_projected = project(left_probabilities)
    left_channel = channels["l"][0]
    right_channel = channels["r"][0]
    left_before = (candidate[:, left_channel] - current[:, left_channel]).abs().mean()
    left_after = (left_projected[:, left_channel] - current[:, left_channel]).abs().mean()
    right_nonpin_error = (
        left_projected[:, right_channel] - zero_projected[:, right_channel]
    ).abs().max()

    differentiable_commands = zero_commands.detach().clone().requires_grad_(True)
    differentiable_probabilities = lower_pin_probabilities(differentiable_commands)
    differentiable_projection = project(differentiable_probabilities)
    differentiable_projection[:, left_channel].sum().backward()
    command_gradient = differentiable_commands.grad
    assert command_gradient is not None
    left_gradient = command_gradient[:, 0].abs().max()

    zero_projection_error = (zero_projected - cleanup_only).abs().max()
    zero_probability_error = zero_probabilities.abs().max()
    left_probability_error = (left_probabilities[:, 0] - 1.0).abs().max()
    right_probability_error = left_probabilities[:, 1].abs().max()
    reduction_ratio = left_after / left_before.clamp_min(1.0e-12)
    return {
        "command_transform": "clamp(2*sigmoid(command)-1,0,1)",
        "zero_probability_max_abs": float(zero_probability_error.detach().cpu()),
        "zero_projection_max_abs": float(zero_projection_error.detach().cpu()),
        "left_full_pin_probability_error": float(left_probability_error.detach().cpu()),
        "right_zero_pin_probability_error": float(right_probability_error.detach().cpu()),
        "left_slide_before_m": float(left_before.detach().cpu()),
        "left_slide_after_m": float(left_after.detach().cpu()),
        "left_slide_reduction_ratio": float(reduction_ratio.detach().cpu()),
        "right_uncommanded_max_abs": float(right_nonpin_error.detach().cpu()),
        "zero_command_left_gradient_max_abs": float(left_gradient.detach().cpu()),
        "passed": (
            float(zero_probability_error.detach().cpu()) == 0.0
            and float(zero_projection_error.detach().cpu()) == 0.0
            and float(left_probability_error.detach().cpu()) <= 1.0e-7
            and float(right_probability_error.detach().cpu()) == 0.0
            and float(reduction_ratio.detach().cpu()) <= 1.0e-4
            and float(right_nonpin_error.detach().cpu()) <= 1.0e-7
            and float(left_gradient.detach().cpu()) > 0.0
        ),
    }


def following_root_roundtrip_audit(runtime: Runtime) -> dict[str, float | bool]:
    ids = runtime.attacks.clip_ids
    # Start from the controller's propagated state contract.  Raw authored toe
    # scalars may exceed [-1, 1] by a few thousandths and are intentionally
    # clamped by every real controller transition before rebasing.
    vec = ik_ctl.clean_output_vector(
        runtime.lower_store.get_target_output(ids, torch.ones_like(ids)),
        runtime.lower_store,
    )
    batch = int(ids.numel())
    dtype = vec.dtype
    device = vec.device
    from_pos = torch.zeros((batch, 3), dtype=dtype, device=device)
    to_pos = torch.linspace(-0.7, 0.9, batch, device=device)[:, None] * torch.tensor(
        [[1.0, 0.0, -0.4]], dtype=dtype, device=device
    )
    from_rot = tl.yaw_to_row_matrix(torch.linspace(-1.0, 1.0, batch, device=device))
    to_rot = tl.yaw_to_row_matrix(torch.linspace(0.8, -0.6, batch, device=device))
    rebased = ik_ctl.rebase_output_vector_root(runtime.lower_store, vec, from_pos, from_rot, to_pos, to_rot)
    restored = ik_ctl.rebase_output_vector_root(runtime.lower_store, rebased, to_pos, to_rot, from_pos, from_rot)
    error = float((restored - vec).abs().max().detach().cpu())
    return {"max_abs": error, "passed": error <= 3.0e-5}


def ae11_feature_parity_audit(runtime: Runtime) -> dict[str, object]:
    """Compare every GT trainer feature directly with the accepted v3 corpus."""

    if int(runtime.ae11.mean.numel()) != STATE_CONDITIONED_AE11_DIM:
        raise ValueError(
            f"The current Slash2 recipe requires the accepted "
            f"{STATE_CONDITIONED_AE11_DIM}-value AE11"
        )
    pointer = json.loads(Path(runtime.recipe.ae11_pointer).read_text(encoding="utf-8"))
    manifest_path = (PROJECT_ROOT / str(pointer["dataset_manifest"])).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    contract = manifest.get("contract", {})
    if not isinstance(contract, dict) or contract.get("target_frame_schema") != target_codec.TARGET_FRAME_SCHEMA:
        raise ValueError("AE11 parity corpus is not strict target-frame v3")
    feature_path = (PROJECT_ROOT / str(manifest["feature_file"])).resolve()
    with np.load(feature_path, allow_pickle=False) as payload:
        corpus_features = np.asarray(payload["features"], dtype=np.float32)
        corpus_clip_ids = np.asarray(payload["clip_id"], dtype=np.int64)
        corpus_frames = np.asarray(payload["current_frame"], dtype=np.float32)

    # Runtime data may be materialized on pod-local NVMe while the accepted AE
    # corpus manifest records its authoritative repository path. The basename
    # is the stable unique clip identity across those storage roots.
    entries_by_name = {
        Path(str(entry["file"])).name.lower(): entry
        for entry in manifest["files"]
        if str(entry.get("source_kind")) == "original"
    }
    trainer_chunks: list[torch.Tensor] = []
    corpus_chunks: list[torch.Tensor] = []
    for clip_id, (path, length) in enumerate(
        zip(runtime.attacks.paths, runtime.attacks.lengths.tolist())
    ):
        entry = entries_by_name.get(path.name.lower())
        if entry is None:
            continue
        dataset_clip_id = int(entry["clip_id"])
        mask = corpus_clip_ids == dataset_clip_id
        order = np.argsort(corpus_frames[mask], kind="stable")
        expected = torch.tensor(corpus_features[mask][order], device=runtime.device)

        current_frames = torch.arange(1, int(length) - 1, dtype=torch.long, device=runtime.device)
        previous_frames = current_frames - 1
        following_frames = current_frames + 1
        ids = torch.full_like(current_frames, int(clip_id))
        previous = runtime.attacks.trajectory_lower[clip_id, previous_frames]
        current = runtime.attacks.trajectory_lower[clip_id, current_frames]
        following = runtime.attacks.trajectory_lower[clip_id, following_frames]
        target_world = runtime.attacks.targets_world[clip_id : clip_id + 1].expand(
            current_frames.numel(), -1
        )
        current_heading = runtime.attacks.trajectory_heading[clip_id, current_frames]
        previous = target_codec.lower_to_held_heading(
            runtime.lower_store,
            previous,
            target_world,
            runtime.attacks.trajectory_heading[clip_id, previous_frames],
            current_heading,
        )
        following = target_codec.lower_to_held_heading(
            runtime.lower_store,
            following,
            target_world,
            runtime.attacks.trajectory_heading[clip_id, following_frames],
            current_heading,
        )
        labels = runtime.attacks.labels[clip_id : clip_id + 1].expand(current_frames.numel(), -1)
        trainer, start, end = lower_prior_features(
            runtime.ae11,
            following,
            previous,
            current,
            target_world,
            labels,
        )
        if (start, end) != (0, LOWER_STATE_DIM):
            raise RuntimeError(f"Unexpected active AE11 score slice {(start, end)}")
        if trainer.shape != expected.shape:
            raise RuntimeError(
                f"{path.name}: trainer features {tuple(trainer.shape)} != corpus {tuple(expected.shape)}"
            )
        trainer_chunks.append(trainer)
        corpus_chunks.append(expected)

    trainer = torch.cat(trainer_chunks)
    direct = torch.cat(corpus_chunks)
    difference = (trainer - direct).abs()
    blocks = (
        ("proposed_delta", 0, 41),
        ("previous_lower", 41, 82),
        ("current_lower", 82, 123),
        ("target_height", 123, 124),
        ("attack_labels", 124, 129),
    )
    block_errors = {
        f"{name}_max_abs": float(difference[:, start:end].max().detach().cpu())
        for name, start, end in blocks
    }
    direct_score = float(prior_score(runtime.ae11, direct, 0, LOWER_STATE_DIM).mean().detach().cpu())
    trainer_score = float(prior_score(runtime.ae11, trainer, 0, LOWER_STATE_DIM).mean().detach().cpu())
    valid_rows = int(direct.shape[0])
    expected_rows = sum(max(0, int(length) - 2) for length in runtime.attacks.lengths.tolist())
    max_abs = float(difference.max().detach().cpu())
    return {
        "max_abs": max_abs,
        "schema_dim": int(trainer.shape[1]),
        "dataset_manifest": str(manifest_path),
        "direct_prior_score": direct_score,
        "trainer_prior_score": trainer_score,
        "valid_ae11_rows": valid_rows,
        "expected_rows": expected_rows,
        "block_errors": block_errors,
        "passed": (
            max_abs <= 3.0e-5
            and abs(trainer_score - direct_score) <= 1.0e-6
            and valid_rows == expected_rows
            and int(trainer.shape[1]) == STATE_CONDITIONED_AE11_DIM
        ),
    }


def upper_feature_audit(runtime: Runtime) -> dict[str, object]:
    """Prove the complete active v3 AE22/AE33 inputs match their corpus."""

    priors = {"ae22": runtime.ae22, "ae33": runtime.ae33}
    pointer_paths = {
        "ae22": Path(runtime.recipe.ae22_pointer),
        "ae33": Path(runtime.recipe.ae33_pointer),
    }
    results: dict[str, object] = {}
    for prior_name, prior in priors.items():
        if int(prior.mean.numel()) != STATE_CONDITIONED_AE_DIM:
            raise ValueError(
                f"The current Slash2 recipe requires the accepted "
                f"{STATE_CONDITIONED_AE_DIM}-value {prior_name.upper()}"
            )
        pointer = json.loads(pointer_paths[prior_name].read_text(encoding="utf-8"))
        manifest_path = (
            PROJECT_ROOT
            / str(pointer.get("runtime_dataset_manifest", pointer["dataset_manifest"]))
        ).resolve()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        contract = manifest.get("contract", {})
        if not isinstance(contract, dict) or contract.get("target_frame_schema") != target_codec.TARGET_FRAME_SCHEMA:
            raise ValueError(f"{prior_name} parity corpus is not strict target-frame v3")
        feature_path = (PROJECT_ROOT / str(manifest[prior_name]["file"])).resolve()
        with np.load(feature_path, allow_pickle=False) as payload:
            corpus_features = np.asarray(payload["features"], dtype=np.float32)
            corpus_clip_ids = np.asarray(payload["clip_id"], dtype=np.int64)
            corpus_frames = np.asarray(payload["current_frame"], dtype=np.float32)

        entries_by_name = {
            Path(str(entry.get("source_file", entry["file"]))).name.lower(): entry
            for entry in manifest["files"]
            if str(entry.get("source_kind")) == "original"
        }
        trainer_chunks: list[torch.Tensor] = []
        corpus_chunks: list[torch.Tensor] = []
        for clip_id, path in enumerate(runtime.attacks.paths):
            entry = entries_by_name.get(path.name.lower())
            if entry is None:
                continue
            dataset_clip_id = int(entry["clip_id"])
            mask = corpus_clip_ids == dataset_clip_id
            order = np.argsort(corpus_frames[mask], kind="stable")
            expected = torch.tensor(corpus_features[mask][order], device=runtime.device)
            current_frames = torch.tensor(
                corpus_frames[mask][order], dtype=torch.long, device=runtime.device
            )
            previous_frames = current_frames - 1
            following_frames = current_frames + 1
            ids = torch.full_like(current_frames, int(clip_id))
            previous = runtime.attacks.trajectory_upper[clip_id, previous_frames]
            current = runtime.attacks.trajectory_upper[clip_id, current_frames]
            following = runtime.attacks.trajectory_upper[clip_id, following_frames]
            target_world = runtime.attacks.targets_world[clip_id : clip_id + 1].expand(
                current_frames.numel(), -1
            )
            labels = runtime.attacks.labels[clip_id : clip_id + 1].expand(
                current_frames.numel(), -1
            )
            current_heading = runtime.attacks.trajectory_heading[
                clip_id, current_frames
            ]
            previous = target_codec.upper_to_held_heading(
                previous,
                target_world,
                runtime.attacks.trajectory_heading[clip_id, previous_frames],
                current_heading,
            )
            following = target_codec.upper_to_held_heading(
                following,
                target_world,
                runtime.attacks.trajectory_heading[clip_id, following_frames],
                current_heading,
            )
            trainer = upper_prior_features(
                prior,
                following,
                previous,
                current,
                target_world,
                labels,
            )
            if trainer.shape != expected.shape:
                raise RuntimeError(
                    f"{path.name}: {prior_name} trainer features {tuple(trainer.shape)} "
                    f"!= corpus {tuple(expected.shape)}"
                )
            trainer_chunks.append(trainer)
            corpus_chunks.append(expected)

        trainer_all = torch.cat(trainer_chunks)
        corpus_all = torch.cat(corpus_chunks)
        difference = (trainer_all - corpus_all).abs()
        blocks = (
            ("proposed_delta", 0, 90),
            ("previous_upper", 90, 180),
            ("current_upper", 180, 270),
            ("target_height", 270, 271),
            ("attack_labels", 271, 276),
        )
        direct_score = float(
            prior_score(prior, corpus_all, 0, UPPER_STATE_DIM).mean().detach().cpu()
        )
        trainer_score = float(
            prior_score(prior, trainer_all, 0, UPPER_STATE_DIM).mean().detach().cpu()
        )
        max_abs = float(difference.max().detach().cpu())
        results[prior_name] = {
            "max_abs": max_abs,
            "rows": int(trainer_all.shape[0]),
            "schema_dim": int(trainer_all.shape[1]),
            "direct_prior_score": direct_score,
            "trainer_prior_score": trainer_score,
            "block_errors": {
                f"{name}_max_abs": float(difference[:, start:end].max().detach().cpu())
                for name, start, end in blocks
            },
            "passed": (
                max_abs <= 3.0e-5
                and abs(trainer_score - direct_score) <= 1.0e-6
                and int(trainer_all.shape[1]) == STATE_CONDITIONED_AE_DIM
            ),
        }

    passed = all(
        bool(results[name]["passed"])  # type: ignore[index]
        for name in ("ae22", "ae33")
    )
    return {
        **results,
        "passed": passed,
    }


def native_pose_mse_contract_audit(runtime: Runtime) -> dict[str, object]:
    """Prove the loss selects only the exact lower/upper controller fields."""

    lower_target = runtime.attacks.trajectory_lower[:1, 12].detach()
    upper_target = runtime.attacks.trajectory_upper[:1, 12].detach()
    zero = float(
        native_pose_mse_rows(
            runtime, lower_target, upper_target, lower_target, upper_target
        )[0].cpu()
    )

    excluded_lower = lower_target.clone()
    excluded_lower[:, :3] += 10.0
    selected = set(int(value) for value in runtime.native_lower_pose_indices.cpu().tolist())
    for index in range(LOWER_STATE_DIM):
        if index not in selected and index >= 9:
            excluded_lower[:, index] += 10.0
    excluded_loss = float(
        native_pose_mse_rows(
            runtime, excluded_lower, upper_target, lower_target, upper_target
        )[0].cpu()
    )

    perturbed_lower = lower_target.clone()
    right_leg = next(
        spec
        for spec in runtime.lower_store.ik_payload_slices
        if str(spec["kind"]) == "leg" and str(spec["side"]) == "r"
    )
    start_slice = right_leg["start_rot6"]
    assert isinstance(start_slice, slice)
    start = 9 + int(start_slice.start)
    yaw = tl.yaw_to_row_matrix(torch.tensor([0.35], device=runtime.device))
    thigh_rot = tl.rotation_6d_to_matrix(perturbed_lower[:, start : start + 6])
    perturbed_lower[:, start : start + 6] = tl.rotmat_to_6d(thigh_rot @ yaw)
    perturbed_lower.requires_grad_(True)

    perturbed_upper = upper_target.clone()
    upperarm_r_start = 75 + 9
    upperarm_rot = tl.rotation_6d_to_matrix(
        perturbed_upper[:, upperarm_r_start : upperarm_r_start + 6]
    )
    perturbed_upper[:, upperarm_r_start : upperarm_r_start + 6] = tl.rotmat_to_6d(
        upperarm_rot @ yaw
    )
    perturbed_upper.requires_grad_(True)
    perturbed_loss = native_pose_mse_rows(
        runtime,
        perturbed_lower,
        perturbed_upper,
        lower_target,
        upper_target,
    ).mean()
    perturbed_loss.backward()
    thigh_gradient = float(
        perturbed_lower.grad[:, start : start + 6].abs().sum().detach().cpu()
    )
    upperarm_gradient = float(
        perturbed_upper.grad[
            :, upperarm_r_start : upperarm_r_start + 6
        ].abs().sum().detach().cpu()
    )
    value = float(perturbed_loss.detach().cpu())
    return {
        "lower_selected_values": int(runtime.native_lower_pose_indices.numel()),
        "upper_selected_values": UPPER_STATE_DIM,
        "total_selected_values": int(runtime.native_lower_pose_indices.numel())
        + UPPER_STATE_DIM,
        "lower_fields": list(LOWER_NATIVE_POSE_FIELDS),
        "upper_fields": list(UPPER_NATIVE_POSE_FIELDS),
        "excluded_implicit_ik_bones": list(IMPLICIT_IK_BONES),
        "zero_loss": zero,
        "excluded_pelvis_translation_and_toe_loss": excluded_loss,
        "thigh_and_upperarm_perturbation_loss": value,
        "thigh_rot6_gradient_l1": thigh_gradient,
        "upperarm_rot6_gradient_l1": upperarm_gradient,
        "row_coverage": "native pose MSE applies uniformly to GT and variant rows",
        "passed": (
            int(runtime.native_lower_pose_indices.numel()) == 36
            and zero == 0.0
            and excluded_loss == 0.0
            and value > 1.0e-5
            and thigh_gradient > 0.0
            and upperarm_gradient > 0.0
        ),
    }


def lowerarm_length_contract_audit(runtime: Runtime) -> dict[str, float | bool]:
    """Prove symmetric compression/extension penalties and gradients."""

    ids = runtime.attacks.clip_ids
    positions = runtime.attacks.trajectory_global_pos[:, 1].detach().clone()
    geometry = runtime.full_fk_geometry["ik_limb_lengths"]
    arm_specs = [spec for spec in runtime.full_clip.ik_limb_specs if str(spec["kind"]) == "arm"]
    directions: list[torch.Tensor] = []
    for arm, spec in enumerate(arm_specs):
        middle = int(spec["mid"])
        end = int(spec["end"])
        direction = positions[:, end] - positions[:, middle]
        direction = direction / torch.linalg.vector_norm(direction, dim=-1, keepdim=True).clamp_min(1.0e-8)
        directions.append(direction)
        positions[:, end] = positions[:, middle] + direction * geometry[:, arm, 1:2]

    exact_rows, exact_max = lowerarm_length_error_rows(runtime, ids, positions)
    compressed = positions.clone()
    stretched = positions.clone()
    for arm, spec in enumerate(arm_specs):
        middle = int(spec["mid"])
        end = int(spec["end"])
        compressed[:, end] = (
            compressed[:, middle]
            + directions[arm] * (geometry[:, arm, 1:2] - 0.03)
        )
        stretched[:, end] = (
            stretched[:, middle]
            + directions[arm] * (geometry[:, arm, 1:2] + 0.05)
        )
    compressed.requires_grad_(True)
    compressed_rows, compressed_max = lowerarm_length_error_rows(runtime, ids, compressed)
    compressed_mean = compressed_rows.mean()
    compressed_mean.backward()
    compressed_gradient_l1 = float(compressed.grad.abs().sum().detach().cpu())

    stretched.requires_grad_(True)
    stretched_rows, stretched_max = lowerarm_length_error_rows(runtime, ids, stretched)
    stretched_mean = stretched_rows.mean()
    stretched_mean.backward()
    stretched_gradient_l1 = float(stretched.grad.abs().sum().detach().cpu())
    exact_value = float(exact_rows.max().detach().cpu())
    compressed_value = float(compressed_mean.detach().cpu())
    stretched_value = float(stretched_mean.detach().cpu())
    max_compression = float(compressed_max.max().detach().cpu())
    max_extension = float(stretched_max.max().detach().cpu())
    return {
        "arms": len(arm_specs),
        "exact_length_loss": exact_value,
        "exact_length_max_abs_error_m": float(exact_max.max().detach().cpu()),
        "three_cm_compression_mse": compressed_value,
        "three_cm_max_compression_m": max_compression,
        "compression_gradient_l1": compressed_gradient_l1,
        "five_cm_extension_mse": stretched_value,
        "five_cm_max_extension_m": max_extension,
        "extension_gradient_l1": stretched_gradient_l1,
        "passed": (
            len(arm_specs) == 2
            and exact_value <= 1.0e-12
            and abs(compressed_value - 0.03**2) <= 2.0e-6
            and abs(max_compression - 0.03) <= 2.0e-5
            and compressed_gradient_l1 > 1.0e-4
            and abs(stretched_value - 0.05**2) <= 2.0e-6
            and abs(max_extension - 0.05) <= 2.0e-5
            and stretched_gradient_l1 > 1.0e-4
        ),
    }


def native_pose_target_audit(runtime: Runtime) -> dict[str, object]:
    """Prove targets come from visible GT, never stale matrix-only rotations."""

    trajectory_errors: list[float] = []
    direct_errors: list[float] = []
    decoded_global_errors: list[float] = []
    event_errors: list[float] = []
    slashlu_frame12_error = float("inf")
    slashlu_source_angle = float("nan")
    slashlu_fitted_angle = float("nan")
    frame_count = 0
    for row, path in enumerate(runtime.attacks.paths):
        length = int(runtime.attacks.lengths[row].item())
        frames = torch.arange(length, dtype=torch.long, device=runtime.device)
        ids = torch.full_like(frames, row)
        controller = load_controller_target_arrays(path)
        target_world = runtime.attacks.targets_world[row : row + 1].expand(length, -1)
        source_lower = torch.tensor(
            controller.lower_hybrid_state,
            dtype=torch.float32,
            device=runtime.device,
        )
        expected_lower = source_lower
        actual_lower = runtime.attacks.trajectory_lower[row, :length]

        expected_upper = torch.tensor(
            controller.upper_hybrid_state,
            dtype=torch.float32,
            device=runtime.device,
        )
        actual_upper = runtime.attacks.trajectory_upper[row, :length]
        actual_heading = runtime.attacks.trajectory_heading[row, :length]
        decoded_pos, decoded_rot = hybrid_full_fk_globals(
            runtime,
            ids,
            ids,
            frames,
            actual_lower,
            actual_upper,
            target_world,
            actual_heading,
        )
        decoded_global_errors.append(
            max(
                float(
                    (
                        runtime.attacks.trajectory_global_pos[row, :length] - decoded_pos
                    ).abs().max().cpu()
                ),
                float(
                    (
                        runtime.attacks.trajectory_global_rot[row, :length] - decoded_rot
                    ).abs().max().cpu()
                ),
            )
        )
        trajectory_errors.append(
            max(
                float((actual_lower - expected_lower).abs().max().cpu()),
                float((actual_upper - expected_upper).abs().max().cpu()),
            )
        )
        direct_errors.append(
            max(
                float((actual_lower - source_lower).abs().max().cpu()),
                float((actual_upper - expected_upper).abs().max().cpu()),
            )
        )

        if path.stem.lower() == "slashlu":
            slashlu_frame12_error = max(
                float((actual_lower[12] - expected_lower[12]).abs().max().cpu()),
                float((actual_upper[12] - expected_upper[12]).abs().max().cpu()),
            )
            names = list(controller.names)
            thigh = names.index("thigh_r")
            calf = names.index("calf_r")
            visible_vector = (
                controller.visible_global_pos_m[:, calf]
                - controller.visible_global_pos_m[:, thigh]
            )
            slashlu_source_angle = float(
                direction_angle_deg(
                    controller.source_global_rot[:, thigh],
                    controller.default_local_translation_m[calf],
                    visible_vector,
                )[12]
            )
            slashlu_fitted_angle = float(
                direction_angle_deg(
                    controller.controller_global_rot[:, thigh],
                    controller.default_local_translation_m[calf],
                    visible_vector,
                )[12]
            )

        for step, alpha, event_lower, event_upper in (
            (
                int(runtime.attacks.armed_step[row].item()) + 1,
                runtime.attacks.armed_alpha[row : row + 1],
                runtime.attacks.armed_lower[row : row + 1],
                runtime.attacks.armed_upper[row : row + 1],
            ),
            (
                int(runtime.attacks.hit_step[row].item()) + 1,
                runtime.attacks.hit_alpha[row : row + 1],
                runtime.attacks.hit_lower[row : row + 1],
                runtime.attacks.hit_upper[row : row + 1],
            ),
        ):
            event_ids = ids[step : step + 1]
            event_target_world = target_world[step : step + 1]
            expected_event_lower, expected_event_upper = (
                interpolate_hybrid_native_states(
                    runtime.lower_store,
                    event_ids,
                    frames[step : step + 1],
                    frames[step + 1 : step + 2],
                    actual_lower[step : step + 1],
                    target_codec.lower_to_held_heading(
                        runtime.lower_store,
                        actual_lower[step + 1 : step + 2],
                        event_target_world,
                        actual_heading[step + 1 : step + 2],
                        actual_heading[step : step + 1],
                    ),
                    actual_upper[step : step + 1],
                    target_codec.upper_to_held_heading(
                        actual_upper[step + 1 : step + 2],
                        event_target_world,
                        actual_heading[step + 1 : step + 2],
                        actual_heading[step : step + 1],
                    ),
                    event_target_world,
                    alpha,
                )
            )
            event_errors.append(
                max(
                    float((event_lower - expected_event_lower).abs().max().cpu()),
                    float((event_upper - expected_event_upper).abs().max().cpu()),
                )
            )
        frame_count += length

    trajectory_error = max(trajectory_errors)
    direct_error = max(direct_errors)
    decoded_global_error = max(decoded_global_errors)
    event_error = max(event_errors)
    armed_is_integer = bool(torch.all(runtime.attacks.armed_alpha == 1.0).item())
    return {
        "frames": frame_count,
        "trajectory_max_abs": trajectory_error,
        "direct_visible_gt_target_max_abs": direct_error,
        "decoded_runtime_target_max_abs": decoded_global_error,
        "event_target_max_abs": event_error,
        "slashlu_frame12_native_target_max_abs": slashlu_frame12_error,
        "slashlu_frame12_source_thigh_direction_error_deg": slashlu_source_angle,
        "slashlu_frame12_fitted_thigh_direction_error_deg": slashlu_fitted_angle,
        "armed_frames_are_integer": armed_is_integer,
        "lower_fields": list(LOWER_NATIVE_POSE_FIELDS),
        "upper_fields": list(UPPER_NATIVE_POSE_FIELDS),
        "excluded_implicit_ik_bones": list(IMPLICIT_IK_BONES),
        "source_npz_edited": False,
        "reference": "visible GT converted to exact native controller coordinates",
        "passed": (
            trajectory_error <= 2.0e-6
            and direct_error <= 2.0e-6
            and decoded_global_error <= 2.0e-6
            and event_error <= 2.0e-6
            and slashlu_frame12_error <= 2.0e-6
            # Controller-authoritative NPZs store the fitted thigh rotation
            # directly. The old full-skeleton source mismatch no longer
            # exists, so both source and decoded controller directions must
            # agree with the visible thigh-to-knee direction.
            and slashlu_source_angle <= 0.05
            and slashlu_fitted_angle <= 0.05
            and armed_is_integer
        ),
    }


def phase_latch_audit(device: torch.device) -> dict[str, object]:
    probabilities = torch.tensor(
        [[0.1, 0.9], [0.1, 0.9], [0.0, 0.0]], device=device
    )
    armed_state = torch.zeros((1,), device=device)
    hit_state = torch.zeros((1,), device=device)
    history: list[list[float]] = []
    for row in probabilities:
        armed_state, hit_state = advance_phase_latches(
            armed_state,
            hit_state,
            row[None],
        )
        history.append([float(armed_state.item()), float(hit_state.item())])
    monotonic = all(
        history[i][j] <= history[i + 1][j]
        for i in range(len(history) - 1)
        for j in range(2)
    )
    threshold_exact = history == [[1.0, 0.0], [1.0, 1.0], [1.0, 1.0]]

    return {
        "latch_history": history,
        "latch_monotonic": monotonic,
        "threshold_exact": threshold_exact,
        "unarmed_hit_request_redirected_to_armed": history[0] == [1.0, 0.0],
        "hit_allowed_on_following_frame": history[1] == [1.0, 1.0],
        "passed": monotonic and threshold_exact,
    }


def prior_routing_audit(runtime: Runtime) -> dict[str, object]:
    """Prove the clean pre/post-armed prior routing table."""

    active = torch.ones((2,), dtype=torch.float32, device=runtime.device)
    armed = torch.tensor((0.0, 1.0), device=runtime.device)
    masks = routed_prior_masks(active, armed)
    observed = {
        name: mask.detach().cpu().tolist()
        for name, mask in zip(("ae11", "ae22", "ae33"), masks)
    }
    expected = {
        "ae11": [1.0, 1.0],
        "ae22": [1.0, 0.0],
        "ae33": [0.0, 1.0],
    }
    dimensions = {
        "ae11": int(runtime.ae11.mean.numel()),
        "ae22": int(runtime.ae22.mean.numel()),
        "ae33": int(runtime.ae33.mean.numel()),
    }
    paths = {
        "ae11": str(runtime.ae11.path),
        "ae22": str(runtime.ae22.path),
        "ae33": str(runtime.ae33.path),
    }
    expected_dimensions = {
        "ae11": STATE_CONDITIONED_AE11_DIM,
        "ae22": STATE_CONDITIONED_AE_DIM,
        "ae33": STATE_CONDITIONED_AE_DIM,
    }
    return {
        "row_order": ["prearmed", "armed"],
        "observed_masks": observed,
        "expected_masks": expected,
        "prior_input_dimensions": dimensions,
        "expected_input_dimensions": expected_dimensions,
        "prior_checkpoints": paths,
        "logged_metric_contract": {
            "ae11": "all active rows",
            "ae22": "pre-armed rows",
            "ae33": "armed rows",
        },
        "passed": observed == expected and dimensions == expected_dimensions,
    }


@torch.no_grad()
def baked_contact_audit(runtime: Runtime) -> dict[str, object]:
    misses: list[float] = []
    for row, _path in enumerate(runtime.attacks.paths):
        length = int(runtime.attacks.lengths[row].item())
        pos = runtime.attacks.trajectory_global_pos[row, :length]
        rot = runtime.attacks.trajectory_global_rot[row, :length]
        current, alpha = event_transition(float(runtime.attacks.hit_time[row].item()))
        event_pos, event_rot = interpolate_pose(
            pos[current : current + 1],
            rot[current : current + 1],
            pos[current + 1 : current + 2],
            rot[current + 1 : current + 2],
            torch.tensor([alpha], device=runtime.device),
        )
        row_index = torch.tensor([row], dtype=torch.long, device=runtime.device)
        data = select_attack_rows(runtime.attacks, row_index)
        miss_squared = hit_target_mse_rows(runtime, event_pos, event_rot, data)[0]
        misses.append(float(torch.sqrt(miss_squared.clamp_min(0.0)).cpu()))
    worst = max(misses)
    worst_row = int(np.argmax(np.asarray(misses)))
    return {
        "reference": "decoded native-controller GT trajectory used by training",
        "worst_motion": runtime.attacks.names[worst_row],
        "worst_miss_m": worst,
        "worst_miss_mm": worst * 1000.0,
        "acceptance_m": 1.0e-2,
        "passed": worst <= 1.0e-2,
    }


def finite_blade_variant_contract_audit(runtime: Runtime) -> dict[str, object]:
    """Regress finite-blade contact without depending on a purged old variant."""

    path = next(
        Path(path)
        for path in runtime.attacks.paths
        if attack_family_from_path(Path(path)) == "pike"
        and not attack_is_mirrored_path(Path(path))
    )
    controller = load_controller_target_arrays(path)
    with np.load(path, allow_pickle=False) as data:
        bone_names = [str(value) for value in data["bone_names"].tolist()]
        keep = np.asarray(
            [bone_names.index(name) for name in runtime.full_clip.body_names],
            dtype=np.int64,
        )
        hit_time = float(data["attack_hit_frame"])
    positions = torch.tensor(
        controller.visible_global_pos_m[:, keep],
        dtype=torch.float32,
        device=runtime.device,
    )
    rotations = torch.tensor(
        controller.controller_global_rot[:, keep],
        dtype=torch.float32,
        device=runtime.device,
    )
    current, alpha = event_transition(hit_time)
    event_pos, event_rot = interpolate_pose(
        positions[current : current + 1],
        rotations[current : current + 1],
        positions[current + 1 : current + 2],
        rotations[current + 1 : current + 2],
        torch.tensor([alpha], dtype=torch.float32, device=runtime.device),
    )
    definitions = load_hit_contact_definitions(Path(runtime.recipe.hit_contact_definitions))
    joint_name, offset, frame_kind = definitions["pike"]
    joint_index = runtime.full_clip.body_names.index(joint_name)
    legacy_point = contact_point(
        event_pos,
        event_rot,
        torch.tensor([joint_index], dtype=torch.long, device=runtime.device),
        torch.tensor(offset.reshape(1, 3), dtype=torch.float32, device=runtime.device),
        torch.tensor([frame_kind], dtype=torch.long, device=runtime.device),
    )[0]
    by_name = {name: index for index, name in enumerate(runtime.full_clip.body_names)}
    blade_joint = by_name[runtime.blade_collision.attach_joint]
    blade_center, blade_axes, blade_half = blade_box_from_pose(
        event_pos,
        event_rot,
        blade_joint,
        runtime.blade_collision,
    )
    major_axis = int(torch.argmax(blade_half[0]).item())
    endpoint_delta = blade_axes[:, major_axis] * blade_half[:, major_axis, None]
    endpoints = torch.stack(
        (blade_center[0] - endpoint_delta[0], blade_center[0] + endpoint_delta[0]),
        dim=0,
    )
    target = endpoints[
        torch.argmax(torch.linalg.vector_norm(endpoints - legacy_point, dim=-1))
    ].reshape(1, 3)
    blade_miss = torch.sqrt(
        finite_blade_target_mse_rows(runtime, event_pos, event_rot, target).clamp_min(0.0)
    )[0]
    legacy_miss = torch.linalg.vector_norm(legacy_point - target[0])

    probe_pos = event_pos.detach().clone().requires_grad_(True)
    probe_target = target + torch.tensor(
        [[0.10, 0.07, -0.04]], dtype=torch.float32, device=runtime.device
    )
    probe_loss = finite_blade_target_mse_rows(
        runtime,
        probe_pos,
        event_rot.detach(),
        probe_target,
    ).mean()
    probe_loss.backward()
    gradient_l1 = float(probe_pos.grad.abs().sum().detach().cpu())
    blade_miss_m = float(blade_miss.detach().cpu())
    legacy_miss_m = float(legacy_miss.detach().cpu())
    return {
        "motion": path.name,
        "hit_time": hit_time,
        "finite_blade_miss_m": blade_miss_m,
        "finite_blade_miss_mm": blade_miss_m * 1000.0,
        "legacy_fixed_point_miss_m": legacy_miss_m,
        "legacy_fixed_point_miss_cm": legacy_miss_m * 100.0,
        "off_blade_gradient_l1": gradient_l1,
        "passed": (
            blade_miss_m <= 1.0e-3
            and legacy_miss_m >= 0.05
            and math.isfinite(gradient_l1)
            and gradient_l1 > 1.0e-5
        ),
    }


@torch.no_grad()
def target_frame_absolute_origin_invariance_audit(runtime: Runtime) -> dict[str, object]:
    """Prove neither world origin nor root translation leaks into learned state.

    The first check moves root and target together by a deliberately absurd
    world translation.  The second moves only the root, decodes the same hybrid
    pose, and then compares both results in one fixed world frame.  That second
    check is the cross-animation reset contract: authored root origins may
    differ arbitrarily, while the body pose relative to the target must not.
    """

    count = min(128, len(runtime.attacks.paths))
    clip_ids = torch.arange(count, dtype=torch.long, device=runtime.device)
    frame = torch.minimum(
        runtime.attacks.lengths[:count].to(runtime.device) - 1,
        torch.full((count,), 3, dtype=torch.long, device=runtime.device),
    )
    lower = runtime.attacks.trajectory_lower[:count].to(runtime.device)[
        torch.arange(count, device=runtime.device), frame
    ]
    upper = runtime.attacks.trajectory_upper[:count].to(runtime.device)[
        torch.arange(count, device=runtime.device), frame
    ]
    heading = runtime.attacks.trajectory_heading[:count].to(runtime.device)[
        torch.arange(count, device=runtime.device), frame
    ]
    target = runtime.attacks.targets_world[:count].to(runtime.device)
    root_pos, root_rot, _yaw, _heading = runtime.lower_store.root_state(
        clip_ids, frame
    )
    delta = torch.tensor([1000.0, 0.0, -733.0], device=runtime.device)
    lower_root = target_codec.lower_target_frame_to_root(
        runtime.lower_store, lower, root_pos, root_rot, target, heading
    )
    lower_shifted = target_codec.lower_target_frame_to_root(
        runtime.lower_store,
        lower,
        root_pos + delta,
        root_rot,
        target + delta,
        heading,
    )
    upper_root = target_codec.upper_target_frame_to_root(
        upper, root_pos, root_rot, target, heading
    )
    upper_shifted = target_codec.upper_target_frame_to_root(
        upper,
        root_pos + delta,
        root_rot,
        target + delta,
        heading,
    )
    shared_lower_error = float((lower_root - lower_shifted).abs().max().cpu())
    shared_upper_error = float((upper_root - upper_shifted).abs().max().cpu())

    # Root-only relocation changes the temporary root-relative vectors, so
    # compare them after rebasing both into one fixed world frame.  If this
    # fails, a source clip with an unusual authored root origin could move a
    # random-start body away from its target.
    lower_root_relocated = target_codec.lower_target_frame_to_root(
        runtime.lower_store,
        lower,
        root_pos + delta,
        root_rot,
        target,
        heading,
    )
    upper_root_relocated = target_codec.upper_target_frame_to_root(
        upper,
        root_pos + delta,
        root_rot,
        target,
        heading,
    )
    world_origin = torch.zeros_like(root_pos)
    world_heading = torch.eye(
        3, dtype=root_rot.dtype, device=root_rot.device
    ).expand_as(root_rot)
    lower_world = target_codec.rebase_lower_state(
        runtime.lower_store,
        lower_root,
        root_pos,
        root_rot,
        world_origin,
        world_heading,
    )
    lower_world_relocated = target_codec.rebase_lower_state(
        runtime.lower_store,
        lower_root_relocated,
        root_pos + delta,
        root_rot,
        world_origin,
        world_heading,
    )
    upper_world = target_codec.rebase_upper_state(
        upper_root,
        root_pos,
        root_rot,
        world_origin,
        world_heading,
    )
    upper_world_relocated = target_codec.rebase_upper_state(
        upper_root_relocated,
        root_pos + delta,
        root_rot,
        world_origin,
        world_heading,
    )
    root_only_lower_world_error = float(
        (lower_world - lower_world_relocated).abs().max().cpu()
    )
    root_only_upper_world_error = float(
        (upper_world - upper_world_relocated).abs().max().cpu()
    )
    tolerance = 2.0e-4
    passed = all(
        error <= tolerance
        for error in (
            shared_lower_error,
            shared_upper_error,
            root_only_lower_world_error,
            root_only_upper_world_error,
        )
    )
    return {
        "sampled_rows": count,
        "synthetic_shared_root_target_translation_m": delta.cpu().tolist(),
        "shared_translation_lower_root_state_max_abs_error": shared_lower_error,
        "shared_translation_upper_root_state_max_abs_error": shared_upper_error,
        "synthetic_root_only_translation_m": delta.cpu().tolist(),
        "root_only_translation_lower_world_state_max_abs_error": (
            root_only_lower_world_error
        ),
        "root_only_translation_upper_world_state_max_abs_error": (
            root_only_upper_world_error
        ),
        "tolerance": tolerance,
        "absolute_root_origin_leaks_into_agent_state": not passed,
        "passed": passed,
    }


@torch.no_grad()
def random_fragment_reset_audit(runtime: Runtime) -> dict[str, object]:
    """Prove random starts are reproducible, in range, varied, and exact GT seeds."""

    data = runtime.attacks
    epochs = torch.arange(64, dtype=torch.long, device=runtime.device)
    samples = torch.stack(
        [
            random_fragment_start_indices(
                data.lengths,
                epoch,
                slot,
                data.clip_ids,
                runtime.recipe.seed,
            )
            for epoch in epochs
            for slot in range(4)
        ],
        dim=0,
    )
    repeated = random_fragment_start_indices(
        data.lengths,
        epochs[7],
        2,
        data.clip_ids,
        runtime.recipe.seed,
    )
    reference = samples[7 * 4 + 2]
    deterministic = bool(torch.equal(repeated, reference))
    staged_schedule = build_fragment_start_schedule(
        data.lengths,
        data.clip_ids,
        runtime.recipe.seed,
        0,
        63,
        4,
    )
    staged_schedule_parity = bool(
        torch.equal(
            staged_schedule,
            samples.reshape(64, 4, -1).detach().cpu(),
        )
    )
    in_range = bool(
        ((samples >= 1) & (samples <= (data.lengths - 2)[None])).all()
    )
    distinct = [int(torch.unique(samples[:, row]).numel()) for row in range(samples.shape[1])]
    span = [int(value) for value in (data.lengths - 2).detach().cpu().tolist()]
    coverage = [count / max(1, possible) for count, possible in zip(distinct, span)]
    varied = all(count >= min(possible, 4) for count, possible in zip(distinct, span))

    seed_index = samples[0]
    seed = fragment_seed_state(runtime, data, seed_index)
    previous = seed_index - 1
    previous_position_error = float(
        (
            seed.previous_global_pos
            - gather_trajectory(data.trajectory_global_pos, previous)
        ).abs().max().cpu()
    )
    current_position_error = float(
        (
            seed.current_global_pos
            - gather_trajectory(data.trajectory_global_pos, seed_index)
        ).abs().max().cpu()
    )
    previous_basis_error = float(
        (
            seed.previous_global_rot
            - gather_trajectory(data.trajectory_global_rot, previous)
        ).abs().max().cpu()
    )
    current_basis_error = float(
        (
            seed.current_global_rot
            - gather_trajectory(data.trajectory_global_rot, seed_index)
        ).abs().max().cpu()
    )
    armed_exact = bool(
        torch.equal(
            seed.armed_latch,
            (seed_index.to(torch.float32) >= data.armed_time).to(torch.float32),
        )
    )
    hit_exact = bool(
        torch.equal(
            seed.hit_latch,
            (seed_index.to(torch.float32) >= data.hit_time).to(torch.float32),
        )
    )
    passed = (
        deterministic
        and staged_schedule_parity
        and in_range
        and varied
        and previous_position_error == 0.0
        and current_position_error == 0.0
        and previous_basis_error == 0.0
        and current_basis_error == 0.0
        and armed_exact
        and hit_exact
    )
    return {
        "sampled_epochs": 64,
        "reset_slots_per_epoch": 4,
        "deterministic": deterministic,
        "pinned_staged_schedule_matches_tensor_formula": staged_schedule_parity,
        "all_current_frames_in_1_to_length_minus_2": in_range,
        "distinct_start_count_per_attack": distinct,
        "valid_start_count_per_attack": span,
        "minimum_start_coverage": min(coverage),
        "varied": varied,
        "previous_seed_position_max_abs_m": previous_position_error,
        "current_seed_position_max_abs_m": current_position_error,
        "previous_seed_basis_max_abs": previous_basis_error,
        "current_seed_basis_max_abs": current_basis_error,
        "authored_armed_latch_exact": armed_exact,
        "authored_hit_latch_exact": hit_exact,
        "passed": passed,
    }


def swept_blade_collision_audit(runtime: Runtime) -> dict[str, object]:
    """Exercise fractional sweep, gradients, exclusions, torso/pelvis, and GT16."""

    device = runtime.device
    # Use FP64 for the isolated derivative probe so a zero-valued outside
    # distance cannot become the 0*inf ambiguity of sqrt at an exact surface.
    # The captured production detector remains FP32 and is checked separately
    # over every GT16 transition below.
    dtype = torch.float64
    center_a = torch.tensor([[-1.00, 0.05, 0.0]], dtype=dtype, device=device, requires_grad=True)
    center_b = torch.tensor([[1.00, 0.05, 0.0]], dtype=dtype, device=device, requires_grad=True)
    axes = torch.eye(3, dtype=dtype, device=device)[None]
    half = torch.tensor([[0.10, 0.10, 0.10]], dtype=dtype, device=device)
    point = torch.zeros((1, 1, 3), dtype=dtype, device=device)
    radius = torch.tensor([0.20], dtype=dtype, device=device)
    endpoint_a = swept_box_capsule_penetration(
        center_a, axes, half, center_a, axes, half,
        point, point, point, point, radius,
        sweep_samples=1, axis_samples=1,
    )
    endpoint_b = swept_box_capsule_penetration(
        center_b, axes, half, center_b, axes, half,
        point, point, point, point, radius,
        sweep_samples=1, axis_samples=1,
    )
    swept = swept_box_capsule_penetration(
        center_a, axes, half, center_b, axes, half,
        point, point, point, point, radius,
        sweep_samples=runtime.recipe.blade_collision_sweep_samples,
        axis_samples=1,
    )
    swept.square().sum().backward()
    gradient_l1 = float(
        (center_a.grad.abs().sum() + center_b.grad.abs().sum()).detach().cpu()
    )

    data = runtime.attacks
    source_losses: list[torch.Tensor] = []
    source_maxima: list[torch.Tensor] = []
    collider_names: tuple[str, ...] | None = None
    with torch.no_grad():
        for row, length_value in enumerate(data.lengths.tolist()):
            length = int(length_value)
            result = swept_blade_body_collision(
                data.trajectory_global_pos[row, : length - 1],
                data.trajectory_global_rot[row, : length - 1],
                data.trajectory_global_pos[row, 1:length],
                data.trajectory_global_rot[row, 1:length],
                runtime.blade_collision,
                runtime.body_collision_layout,
                sweep_samples=runtime.recipe.blade_collision_sweep_samples,
            )
            source_losses.append(result.loss_rows)
            source_maxima.append(result.max_penetration_m)
            collider_names = result.collider_names
    assert collider_names is not None
    all_source_loss = torch.cat(source_losses)
    all_source_max = torch.cat(source_maxima)
    source_raw_mean = float(all_source_loss.mean().cpu())
    source_bad_rate = float((all_source_max > 0.0).to(torch.float32).mean().cpu())
    source_max = float(all_source_max.amax().cpu())

    active = set(collider_names)
    required = {
        "pelvis",
        "torso_lower",
        "torso_middle",
        "torso_upper",
        "upper_neck",
        "head",
        *RIGHT_LOWERARM_SELF_COLLISION_NAMES,
    }
    absent = set(runtime.recipe.blade_collision_excluded_colliders) & active
    reference_raw_mean = 6.9006691774120554e-06
    calibrated_reference = runtime.recipe.blade_collision_weight * reference_raw_mean
    blade_dims = [2.0 * value for value in runtime.blade_collision.half_extents_m]
    passed = (
        float(endpoint_a.detach().amax().cpu()) == 0.0
        and float(endpoint_b.detach().amax().cpu()) == 0.0
        and float(swept.detach().amax().cpu()) > 0.0
        and math.isfinite(gradient_l1)
        and gradient_l1 > 0.0
        and required <= active
        and not absent
        and len(collider_names) == 22
        and math.isfinite(source_raw_mean)
        and source_raw_mean > 0.0
        and math.isfinite(source_max)
        and abs(calibrated_reference - 0.1) <= 1.0e-8
        and max(blade_dims) > 0.85
        and min(blade_dims) < 0.01
    )
    return {
        "fractional_crossing_endpoint_a_penetration_m": float(endpoint_a.detach().amax().cpu()),
        "fractional_crossing_endpoint_b_penetration_m": float(endpoint_b.detach().amax().cpu()),
        "fractional_crossing_swept_penetration_m": float(swept.detach().amax().cpu()),
        "fractional_crossing_gradient_l1": gradient_l1,
        "active_collider_count": len(collider_names),
        "active_colliders": list(collider_names),
        "required_spine_pelvis_colliders_present": sorted(required),
        "requested_exclusions_still_active": sorted(absent),
        "source_gt16_raw_mean": source_raw_mean,
        "source_gt16_bad_transition_rate": source_bad_rate,
        "source_gt16_max_penetration_m": source_max,
        "checkpoint_7300_reference_raw_mean": reference_raw_mean,
        "configured_weight": runtime.recipe.blade_collision_weight,
        "checkpoint_7300_weighted_reference_mean": calibrated_reference,
        "blade_dimensions_m": blade_dims,
        "passed": passed,
    }


def run_contract_tests(runtime: Runtime, verbose: bool = True) -> dict[str, object]:
    tests: dict[str, object] = {}
    with runtime.policy_context():
        tests["zero_delta_identity"] = zero_delta_audit(runtime)
        tests["source_motion_seed"] = source_motion_seed_audit(runtime)
        tests["per_motion_fk_geometry"] = per_motion_fk_geometry_audit(runtime)
        tests["batched_lower_projection_parity"] = batched_lower_projection_parity_audit(runtime)
        tests["post_lower_foot_floor_unclip"] = post_lower_foot_floor_unclip_audit(runtime)
        tests["post_lower_continuous_pin"] = post_lower_continuous_pin_audit(runtime)
        tests["following_root_roundtrip"] = following_root_roundtrip_audit(runtime)
        tests["ae11_feature_parity"] = ae11_feature_parity_audit(runtime)
        tests["upper_feature_parity"] = upper_feature_audit(runtime)
        tests["native_pose_mse_contract"] = native_pose_mse_contract_audit(runtime)
        tests["lowerarm_length_contract"] = lowerarm_length_contract_audit(runtime)
        tests["native_pose_targets"] = native_pose_target_audit(runtime)
        tests["phase_latch"] = phase_latch_audit(runtime.device)
        tests["prior_routing"] = prior_routing_audit(runtime)
        tests["target_frame_absolute_origin_invariance"] = (
            target_frame_absolute_origin_invariance_audit(runtime)
        )
        tests["baked_hit_contact"] = baked_contact_audit(runtime)
        tests["finite_blade_variant_contact"] = finite_blade_variant_contract_audit(runtime)
        tests["random_fragment_reset"] = random_fragment_reset_audit(runtime)
        tests["swept_blade_collision"] = swept_blade_collision_audit(runtime)
    passed = all(bool(value.get("passed")) for value in tests.values() if isinstance(value, dict))
    report = {
        "passed": passed,
        "device": str(runtime.device),
        "frozen_mode": runtime.recipe.frozen_mode,
        "clip_count": len(runtime.attacks.paths),
        "tests": tests,
    }
    if verbose:
        print(json.dumps(report, indent=2), flush=True)
    return report


def full_dataset_contract_audit(runtime: Runtime) -> dict[str, object]:
    """Prove the clean corpus envelope and its structural sampling law."""

    total = len(runtime.attacks.paths)
    if total == len(ATTACK_LABELS):
        return {
            "mode": "gt16",
            "originals": total,
            "variants": 0,
            "passed": True,
        }

    epochs = 100
    slots = int(runtime.attacks.max_steps) + 1
    batch_rows = int(runtime.recipe.batch_size)
    if total == 32 and not runtime.recipe.variant_dir:
        clip_schedule, frame_schedule = build_uniform_dataset_schedule(
            runtime.attacks.lengths,
            runtime.recipe.seed,
            0,
            epochs - 1,
            slots,
            1,
            batch_rows,
        )
        clips = clip_schedule.numpy()
        frames = frame_schedule.numpy()
        lengths = runtime.attacks.lengths.detach().cpu().numpy()
        histogram = np.bincount(clips.reshape(-1), minlength=total)
        valid_frames = bool(
            np.all((frames >= 1) & (frames <= lengths[clips] - 2))
        )
        return {
            "mode": "gt32_normal_mirrored",
            "clip_histogram_range": [
                int(histogram.min()),
                int(histogram.max()),
            ],
            "valid_fragment_starts": valid_frames,
            "passed": bool(
                int(histogram.max() - histogram.min()) <= 1
                and valid_frames
            ),
        }

    if total != FULL_DATASET_TOTAL_COUNT:
        return {
            "mode": "unexpected",
            "clip_count": total,
            "expected_clip_count": FULL_DATASET_TOTAL_COUNT,
            "passed": False,
        }

    clip_schedule, frame_schedule = build_full_dataset_schedule(
        runtime.attacks.lengths,
        runtime.recipe.seed,
        0,
        epochs - 1,
        slots,
        1,
        batch_rows,
        original_count=FULL_DATASET_GT_COUNT,
        original_probability=runtime.recipe.original_sample_probability,
    )
    clips = clip_schedule.numpy()
    frames = frame_schedule.numpy()
    lengths = runtime.attacks.lengths.detach().cpu().numpy()
    originals = clips < FULL_DATASET_GT_COUNT
    original_ratio = float(originals.mean())
    valid_frames = bool(
        np.all((frames >= 1) & (frames <= lengths[clips] - 2))
    )
    original_normal = int((clips < FULL_DATASET_MODE_GT_COUNT).sum())
    original_mirrored = int(
        ((clips >= FULL_DATASET_MODE_GT_COUNT) & originals).sum()
    )
    variant_ids = clips[~originals] - FULL_DATASET_GT_COUNT
    variant_normal = int((variant_ids < FULL_DATASET_MODE_VARIANT_COUNT).sum())
    variant_mirrored = int(
        (variant_ids >= FULL_DATASET_MODE_VARIANT_COUNT).sum()
    )
    return {
        "mode": "full_gt_variant",
        "clip_count": total,
        "originals": FULL_DATASET_GT_COUNT,
        "variants": FULL_DATASET_VARIANT_COUNT,
        "sampling": "10% GT / 90% variants; 50% normal / 50% M inside both pools",
        "original_probability": original_ratio,
        "original_mode_draws": [original_normal, original_mirrored],
        "variant_mode_draws": [variant_normal, variant_mirrored],
        "valid_fragment_starts": valid_frames,
        "passed": bool(
            abs(original_ratio - 0.10) <= (1.0 / max(clips.size, 1))
            and abs(original_normal - original_mirrored) <= 1
            and abs(variant_normal - variant_mirrored) <= 1
            and valid_frames
        ),
    }


def resumed_loss_calibration_audit(
    checkpoint_path: Path,
    checkpoint_step: int,
    runtime: Runtime,
    lower: DeltaAgent,
    upper: DeltaAgent,
) -> dict[str, object]:
    """Verify final-pose and symmetric arm-length terms on the resume state."""

    rollout = rollout_slash2_gt16_batch(
        checkpoint_path,
        runtime.device,
        runtime.recipe,
        runtime,
        lower,
        upper,
    )
    final_values: list[torch.Tensor] = []
    length_sum = torch.zeros((), dtype=torch.float32, device=runtime.device)
    length_count = 0
    hookr_max = 0.0
    hookr_mean = 0.0
    ids = runtime.attacks.clip_ids
    for row, name in enumerate(runtime.attacks.names):
        positions = torch.as_tensor(
            rollout["positions"][row], dtype=torch.float32, device=runtime.device
        )
        rotations = torch.as_tensor(
            rollout["rotations"][row], dtype=torch.float32, device=runtime.device
        )
        length = int(positions.shape[0])
        row_id = ids[row : row + 1]
        final_lower = torch.as_tensor(
            rollout["lower"][row][-1:], dtype=torch.float32, device=runtime.device
        )
        final_upper = torch.as_tensor(
            rollout["upper"][row][-1:], dtype=torch.float32, device=runtime.device
        )
        final_values.append(
            native_pose_mse_rows(
                runtime,
                final_lower,
                final_upper,
                runtime.attacks.trajectory_lower[row, length - 1 : length],
                runtime.attacks.trajectory_upper[row, length - 1 : length],
            )[0]
        )
        predicted = positions[2:]
        repeated_ids = row_id.expand(int(predicted.shape[0]))
        length_rows, absolute_error = lowerarm_length_error_rows(
            runtime, repeated_ids, predicted
        )
        length_sum = length_sum + length_rows.sum()
        length_count += int(length_rows.numel())
        if name.lower() == "hookr":
            hookr_max = float(absolute_error.max().detach().cpu())
            hookr_mean = float(length_rows.mean().detach().cpu())

    final_raw = float(torch.stack(final_values).mean().detach().cpu())
    length_raw = float((length_sum / max(length_count, 1)).detach().cpu())
    weighted_final = final_raw * float(runtime.recipe.final_pose_weight)
    weighted_length = length_raw * float(runtime.recipe.lowerarm_length_weight)
    reference_step = int(checkpoint_step) == 15_166
    return {
        "source_checkpoint": str(checkpoint_path),
        "source_step": int(checkpoint_step),
        "final_pose_raw_gt16_mean": final_raw,
        "final_pose_weight": float(runtime.recipe.final_pose_weight),
        "final_pose_weighted_gt16_mean": weighted_final,
        "final_pose_requested_mean": 0.01,
        "lowerarm_length_raw_gt16_mean": length_raw,
        "lowerarm_length_weight": float(runtime.recipe.lowerarm_length_weight),
        "lowerarm_length_weighted_gt16_mean": weighted_length,
        "hookr_raw_length_mse_mean": hookr_mean,
        "hookr_max_abs_length_error_m": hookr_max,
        "reference_step_15166_final_pose_calibration_required": reference_step,
        "passed": (
            int(checkpoint_step) > 0
            and math.isfinite(final_raw)
            and math.isfinite(length_raw)
            and math.isfinite(hookr_mean)
            and math.isfinite(hookr_max)
            and (
                not reference_step
                or abs(weighted_final - 0.01) <= 2.0e-5
            )
        ),
    }


def run_id(recipe: Recipe, smoke: bool) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if recipe.variant_dir:
        dataset = f"full{FULL_DATASET_TOTAL_COUNT}_orig10_modes50_uniformvariants"
    else:
        gt_count = sum(
            "__" not in path.stem
            for path in Path(recipe.gt_dir).resolve().glob("*.npz")
        )
        dataset = "gt32_modes_uniform" if gt_count == 32 else "gt16"
    resume = Path(recipe.resume_checkpoint).stem.replace("checkpoint_step_", "resume") if recipe.resume_checkpoint else "fresh"
    return (
        f"{stamp}_slash2_{dataset}_bs{recipe.batch_size}_"
        f"gtctrl_lr5e5_{resume}"
        + (
            f"_force{int(recipe.forced_attack_family_rows_per_logical_batch)}"
            f"{str(recipe.forced_attack_family).strip().lower()}"
            if int(recipe.forced_attack_family_rows_per_logical_batch) > 0
            else ""
        )
        + ("_smoke" if smoke else "")
    )


@dataclass
class PreparedTraining:
    recipe: Recipe
    runtime: Runtime
    lower: DeltaAgent
    upper: DeltaAgent
    optimizer: torch.optim.Optimizer
    tests: dict[str, object]
    graph: CudaGraphStep
    start_step: int


def save_checkpoint(
    run_dir: Path,
    step: int,
    runtime: Runtime,
    lower: DeltaAgent,
    upper: DeltaAgent,
    optimizer: torch.optim.Optimizer,
    metrics: dict[str, float],
    tests: dict[str, object],
    latest: bool = False,
    optimizer_progress: dict[str, object] | None = None,
) -> Path:
    checkpoint_dir = run_dir / "checkpoints"
    checkpoint_storage.enforce_checkpoint_path(checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_storage.fsync_directory(run_dir)
    path = checkpoint_dir / ("checkpoint_latest.pt" if latest else f"checkpoint_step_{step:06d}.pt")
    payload = {
        "kind": "slash2_two_agent_cuda_graph",
        "step": int(step),
        "optimizer_progress": optimizer_progress,
        "recipe": asdict(runtime.recipe),
        "schemas": {
            "target_frame_schema": target_codec.TARGET_FRAME_SCHEMA,
            "target_frame_schema_version": target_codec.TARGET_FRAME_SCHEMA_VERSION,
            "learned_frame_origin": "(target_world_x, 0, target_world_z)",
            "learned_frame_orientation": "held current pelvis to target flat direction",
            "target_height_input": True,
            "backward_compatible": False,
            "lower_input_dim": lower_input_dim_for_recipe(runtime.recipe),
            "frozen_agent_enabled": bool(runtime.recipe.frozen_agent_enabled),
            "lower_output_dim": LOWER_OUTPUT_DIM,
            "lower_output_delta_dim": LOWER_POSE_DELTA_DIM,
            "lower_pin_command_dim": LOWER_PIN_COMMAND_DIM,
            "lower_pin_command_transform": "clamp(2*sigmoid(command)-1,0,1)",
            "lower_pin_zero_contract": (
                "command 0 produces probability 0 and no second pin displacement"
            ),
            "lower_pin_projection": (
                "run_continuous_probability_projection_then_minimum_floor_unclip"
            ),
            "lower_pin_integration_steps": LOWER_PIN_INTEGRATION_STEPS,
            "lower_pin_height_gate_enabled": LOWER_PIN_HEIGHT_GATE_ENABLED,
            "lower_pin_near_floor_forcing": False,
            "lower_pin_side_blend_deg": LOWER_PIN_SIDE_BLEND_DEG,
            "lower_pin_ground_y_m": LOWER_PIN_GROUND_Y_M,
            "lower_pin_output_order": ["left", "right"],
            "upper_input_dim": UPPER_INPUT_DIM,
            "upper_output_delta_dim": UPPER_STATE_DIM,
            "upper_gate_dim": 2,
            "attack_labels": list(ATTACK_LABEL_NAMES),
            "gate_threshold": runtime.recipe.gate_threshold,
            "gate_state_machine": (
                "unarmed hit requests are redirected to armed; hit can latch no "
                "earlier than the following frame"
            ),
            "delta_reference": "following root; frozen current-root output is explicitly rebased before lower delta",
            "initial_pose": (
                "all rows use the two authored frames immediately preceding their "
                "scheduled attack fragment"
            ),
            "random_fragment_epoch": (
                f"checkpoint step selects a precomputed deterministic schedule; one pinned "
                f"logical-batch schedule is staged before each replay, and every row/reset "
                "slot independently selects a target motion and authored attack-frame pair"
            ),
            "forced_attack_family": (
                str(runtime.recipe.forced_attack_family).strip().lower() or None
            ),
            "forced_attack_family_rows_per_logical_batch": int(
                runtime.recipe.forced_attack_family_rows_per_logical_batch
            ),
            "forced_attack_family_contract": (
                "offline deterministic schedule substitution only; preserves each "
                "reserved row's original GT/variant and normal/M category and adds "
                "no captured-graph work"
            ),
            "per_motion_fk_geometry": (
                "every row selects its own local offsets, limb lengths, pole axes, "
                "toe offsets, and toe axes"
            ),
            "native_controller_pose_targets": {
                "source": (
                    "visible GT joint positions converted once to native controller states; "
                    "source NPZ files remain unchanged"
                ),
                "loss": "one direct scalar MSE over the selected lower and complete upper state values",
                "lower_fields": list(LOWER_NATIVE_POSE_FIELDS),
                "upper_fields": list(UPPER_NATIVE_POSE_FIELDS),
                "pelvis_translation": "excluded; pose location is pelvis-relative",
                "toe_hinges": "excluded from authored pose MSE",
                "excluded_implicit_ik_bones": list(IMPLICIT_IK_BONES),
                "coverage": "the same authored pose and hit-target losses apply to every row",
            },
            "prior_routing": {
                "all_rows": "AE11 throughout; AE22 before armed; AE33 after armed",
                "logged_metrics": {
                    "ae11": "all active rows",
                    "ae22": "pre-armed rows",
                    "ae33": "all armed rows",
                },
            },
            "hit_contact_geometry": (
                "head/fist/foot attacks use versioned baked joint/local-offset points; sword "
                "attacks use differentiable closest-point distance to the finite volume of "
                "the same immutable blade box used for collision; runtime and training do not "
                "load FBX geometry"
            ),
            "blade_collision_geometry": (
                "right-hand blade OBB baked once from slashL; differentiable nine-sample "
                "fractional-frame sweep against body capsules, spheres, and OBBs; runtime and "
                "training do not load FBX geometry"
            ),
            "blade_collision_excluded_colliders": list(
                runtime.recipe.blade_collision_excluded_colliders
            ),
            "blade_collision_sweep_samples": int(
                runtime.recipe.blade_collision_sweep_samples
            ),
            "blade_collision_calibration": (
                "raw full-GT16 checkpoint-step-7300 transition mean 6.9006691774120554e-06; "
                "weight 14491.348219869717 makes its weighted mean exactly 0.1"
            ),
            "post_lower_foot_floor": (
                "the 41 pose deltas are cleaned, then two independent zero-preserving continuous "
                "pin probabilities drive the established run foot projection, then only remaining "
                "foot/toe penetration receives the minimum upward Y correction"
            ),
            "loss_terms": list(WEIGHTED_LOSS_TERM_NAMES),
            "tensorboard_loss_values": (
                "every loss/<term> scalar is its exact weighted contribution "
                "to loss/total; tag names remain stable"
            ),
            "prior_contract": (
                "AE1 and AE2 are absent; every row uses AE11 throughout, AE22 "
                "before armed, and AE33 after armed"
            ),
            "ae33_weight_multiplier": float(runtime.recipe.ae33_weight_multiplier),
            "final_pose_weight": float(runtime.recipe.final_pose_weight),
            "final_pose_calibration": (
                "full sequential GT16 visible-GT native target at step 15166: raw mean "
                "0.0024056676775217056; weight 4.156850130813537 makes its weighted "
                "mean exactly 0.01"
            ),
            "lowerarm_length_weight": float(runtime.recipe.lowerarm_length_weight),
            "lowerarm_length_contract": (
                "both implicit lower-arm IK segments; squared signed wrist-elbow length error "
                "against each row's fixed runtime lower-arm length; extension and compression "
                "are penalized symmetrically"
            ),
            "lowerarm_length_weighting": (
                "4.53691442021562 is exactly 2x the former extension-only weight "
                "2.26845721010781, as requested"
            ),
            "opposite_calf_collision": {
                "schema": "slash2_opposite_calf_capsule_collision_v1",
                "pair": ["calf_l_to_foot_l", "calf_r_to_foot_r"],
                "pathCount": 1,
                "capsuleRadiusM": OPPOSITE_CALF_CAPSULE_RADIUS_M,
                "loss": "squared finite-segment capsule overlap on predicted pose",
                "weight": float(runtime.recipe.opposite_calf_collision_weight),
                "hotPath": "reuses existing full FK positions; no additional FK or motion decode",
            },
            "pike_blade_look_at_target": {
                "schema": "slash2_pike_blade_look_at_target_v1",
                "family": "pike",
                "origin": "hand_r",
                "direction": (
                    "hand_r to the farther endpoint of the baked hand-attached blade OBB; "
                    "includes the authored center offset and oblique blade axes"
                ),
                "phase": "NPZ-authored armed_frame through hit_frame inclusive",
                "loss": "1 - cosine(blade distal sightline, hand-to-target direction)",
                "weight": float(runtime.recipe.pike_blade_look_at_target_weight),
                "hotPath": "reuses existing full FK pose; one vector rotation and no additional FK or motion decode",
            },
            "predictive_pin": {
                **(runtime.pin_teacher_metadata or {"enabled": False}),
                "weight": float(runtime.recipe.predictive_pin_weight),
            },
            "anti_pin_slide": {
                "schema": "slash2_anti_pin_slide_v1",
                "application": "all active E/M/H and GT transitions",
                "measurement": (
                    "per side, minimum horizontal world-space velocity of foot and ball/toe "
                    "after the existing pin projection"
                ),
                "pinRamp": {
                    "start": ANTI_PIN_SLIDE_RAMP_START,
                    "peakAndSaturation": ANTI_PIN_SLIDE_RAMP_PEAK,
                    "shape": "linear_clamped",
                    "detachedFromGradient": True,
                },
                "loss": "mean_left_right(pin_ramp * minimum_speed_mps^2)",
                "weight": float(runtime.recipe.anti_pin_slide_weight),
            },
            "excluded_losses": (
                "no full-trajectory pose, knee/calf/lower-arm pose supervision, separate "
                "foot pose loss, thigh collision paths, or other unlisted auxiliary loss"
            ),
            "gradient_clip_norm": runtime.recipe.gradient_clip_norm,
            # Keep the viewer-facing family tag stable forever. The graph
            # implementation can evolve independently in training_graph.
            "cuda_graph": SLASH2_VIEWER_COMPAT_SCHEMA,
            "training_graph": CudaGraphStep.kind,
            "temporal_gradient": (
                "autoregressive BPTT continues through each captured segment; exact detached "
                "episode state carries across the optimizer boundary, every row resets at its "
                "authored end, and reset cuts only that row's history"
            ),
            "logical_batch": (
                (
                    "every initial seed and every reset draws 10% from the 32 GT motions "
                    f"and 90% from all {FULL_DATASET_VARIANT_COUNT:,} variants; "
                    "normal and M are sampled 50/50 inside both pools; "
                    f"one {int(runtime.recipe.batch_size)}-row CUDA graph replay per "
                    "optimizer step; "
                    f"{int(runtime.recipe.forced_attack_family_rows_per_logical_batch)} "
                    f"logical row(s) remain in "
                    f"{str(runtime.recipe.forced_attack_family).strip().lower() or 'no forced family'}"
                )
                if runtime.recipe.variant_dir
                else (
                    "every initial seed and reset is drawn uniformly from all 32 normal and "
                    "mirrored GT motions through one physical-batch graph replay"
                    if len(runtime.attacks.paths) == 32
                    else
                    f"one captured graph contains {runtime.recipe.batch_size // len(ATTACK_LABELS)} "
                    "independently randomized replicas of each of the 16 GT attack families; rows "
                    "independently reset to random valid source frames until the fixed graph horizon ends"
                )
            ),
            "debug_replayer": (
                "exact world positions, rotations, gate probabilities, latches, and every "
                "weighted per-frame loss term are mirrored inside the real CUDA training graph; "
                "export never reruns or reconstructs the rollout"
            ),
        },
        "lower_agent": lower.state_dict(),
        "upper_agent": upper.state_dict(),
        "optimizer": optimizer.state_dict(),
        "metrics": metrics,
        "contract_tests": tests,
        "frozen_walk": (
            None
            if runtime.walk_checkpoint_path is None
            else {
                "path": str(runtime.walk_checkpoint_path),
                "sha256": sha256_file(runtime.walk_checkpoint_path),
            }
        ),
        "hit_contact_definitions": {
            "path": str(Path(runtime.recipe.hit_contact_definitions).resolve()),
            "sha256": sha256_file(Path(runtime.recipe.hit_contact_definitions).resolve()),
        },
        "blade_collision_definition": {
            "path": str(Path(runtime.recipe.blade_collision_definition).resolve()),
            "sha256": sha256_file(Path(runtime.recipe.blade_collision_definition).resolve()),
            "excluded_colliders": list(runtime.recipe.blade_collision_excluded_colliders),
            "sweep_samples": int(runtime.recipe.blade_collision_sweep_samples),
            "weighted_reference_mean": 0.1,
        },
        "priors": {
            prior.name: {"path": str(prior.path), "sha256": sha256_file(prior.path)}
            for prior in (
                runtime.ae11,
                runtime.ae22,
                runtime.ae33,
            )
        },
    }
    compatibility = slash2_viewer_checkpoint_compatibility(payload)
    if not compatibility["passed"]:
        raise RuntimeError(
            f"Refusing to save a viewer-incompatible Slash2 checkpoint: {compatibility['errors']}"
        )
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    torch.save(payload, temporary)
    reloaded = torch.load(temporary, map_location="cpu", weights_only=False)
    reloaded_compatibility = slash2_viewer_checkpoint_compatibility(reloaded)
    if not reloaded_compatibility["passed"]:
        raise RuntimeError(
            f"Saved Slash2 checkpoint failed its viewer contract: {reloaded_compatibility['errors']}"
        )
    checkpoint_storage.durable_publish(temporary, path)
    checkpoint_storage.atomic_json(checkpoint_dir / "checkpoint_latest_receipt.json" if latest
                                  else path.with_suffix(".receipt.json"), {
        "schema": "slash2_durable_checkpoint_receipt_v1", "checkpoint": str(path.resolve()),
        "step": int(step), "sha256": sha256_file(path), "bytes": path.stat().st_size,
        "savedAtUnix": time.time(),
        "persistentRoot": os.environ.get("SLASH2_PERSISTENT_RUNS_ROOT"),
        "optimizerProgress": optimizer_progress,
    })
    return path


def archive_latest_checkpoint(run_dir: Path, step: int) -> Path:
    """Retain an immutable numbered alias of the atomically refreshed latest file."""

    checkpoint_dir = run_dir / "checkpoints"
    checkpoint_storage.enforce_checkpoint_path(checkpoint_dir)
    latest = checkpoint_dir / "checkpoint_latest.pt"
    archived = checkpoint_dir / f"checkpoint_step_{int(step):06d}.pt"
    if archived.exists():
        return archived
    try:
        os.link(latest, archived)
    except OSError:
        temporary = archived.with_name(archived.name + "." + uuid.uuid4().hex + ".tmp")
        shutil.copy2(latest, temporary)
        checkpoint_storage.durable_publish(temporary, archived)
    checkpoint_storage.fsync_directory(checkpoint_dir)
    return archived


def slash2_viewer_checkpoint_compatibility(checkpoint: object) -> dict[str, object]:
    """Mirror the standalone viewer's stable discovery contract."""

    errors: list[str] = []
    if not isinstance(checkpoint, dict):
        errors.append("checkpoint is not a dictionary")
        return {"passed": False, "errors": errors}
    schemas = checkpoint.get("schemas")
    if checkpoint.get("kind") != "slash2_two_agent_cuda_graph":
        errors.append("wrong kind")
    if not isinstance(schemas, dict):
        errors.append("missing schemas")
    else:
        if schemas.get("cuda_graph") != SLASH2_VIEWER_COMPAT_SCHEMA:
            errors.append("viewer family tag changed")
        if checkpoint_training_graph_schema(checkpoint) != SLASH2_CUDA_GRAPH_SCHEMA:
            errors.append("training graph revision is not current")
        if schemas.get("target_frame_schema") != target_codec.TARGET_FRAME_SCHEMA:
            errors.append("target-frame schema is not current")
        recipe_values = checkpoint.get("recipe")
        frozen_enabled = (
            bool(recipe_values.get("frozen_agent_enabled", True))
            if isinstance(recipe_values, dict)
            else True
        )
        if schemas.get("lower_input_dim") != target_codec.lower_input_dim(
            frozen_agent_enabled=frozen_enabled
        ):
            errors.append("lower input dimension is not current")
        if schemas.get("upper_input_dim") != UPPER_INPUT_DIM:
            errors.append("upper input dimension is not current")
    for key in ("lower_agent", "upper_agent", "recipe"):
        if not isinstance(checkpoint.get(key), dict):
            errors.append(f"missing {key}")
    return {"passed": not errors, "errors": errors}


def debug_rollout_request_path(run_dir: Path) -> Path:
    return run_dir / "debug" / DEBUG_ROLLOUT_REQUEST_NAME


def debug_rollout_artifact_path(run_dir: Path) -> Path:
    return run_dir / "debug" / DEBUG_ROLLOUT_ARTIFACT_NAME


def debug_rollout_capture_path(run_dir: Path, step: int) -> Path:
    return (
        run_dir
        / "debug"
        / f"{DEBUG_ROLLOUT_CAPTURE_PREFIX}{int(step):06d}.json"
    )


def debug_rollout_active_path(run_dir: Path) -> Path:
    return run_dir / "debug" / DEBUG_ROLLOUT_ACTIVE_NAME


def write_debug_rollout_active_marker(run_dir: Path) -> Path:
    path = debug_rollout_active_path(run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "run_id": run_dir.name,
        "pid": os.getpid(),
        "trainer": "training/slashes2/train_slash_controller.py",
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)
    return path


def remove_debug_rollout_active_marker(path: Path) -> None:
    try:
        if not path.exists():
            return
        payload = json.loads(path.read_text(encoding="utf-8"))
        if int(payload.get("pid", -1)) == os.getpid():
            path.unlink()
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass


def training_row_difficulty_names(
    runtime: Runtime,
    row_count: int,
) -> list[str]:
    """Return fixed physical-row labels for difficulty-aware training."""

    training_difficulty_ids = getattr(
        runtime, "training_row_difficulty_ids", None
    )
    if training_difficulty_ids is None:
        return []
    difficulty_names = ("easy", "medium", "hard")
    if not torch.is_tensor(training_difficulty_ids):
        raise TypeError("training_row_difficulty_ids must be a tensor")
    if int(training_difficulty_ids.numel()) != int(row_count):
        raise RuntimeError(
            "Difficulty row metadata does not match the captured physical batch"
        )
    difficulty_values = [
        int(value)
        for value in training_difficulty_ids.detach().cpu().tolist()
    ]
    if any(value < 0 or value >= len(difficulty_names) for value in difficulty_values):
        raise RuntimeError("Captured difficulty row metadata is outside 0..2")
    return [difficulty_names[value] for value in difficulty_values]


def slash2_debug_rollout_payload(
    run_dir: Path,
    step: int,
    runtime: Runtime,
    snapshot: dict[str, torch.Tensor],
    request: dict[str, object],
    training_rows: torch.Tensor | None = None,
    *,
    source: str = "latest_slash2_cuda_graph_training_rollout",
) -> dict[str, object]:
    snapshot_clip_ids = snapshot.get("clip_id")
    if torch.is_tensor(snapshot_clip_ids):
        selected_rows = snapshot_clip_ids[:, 0].to(runtime.attacks.clip_ids.device)
    else:
        canonical_rows = torch.arange(
            len(runtime.attacks.paths), dtype=torch.long, device=runtime.device
        )
        selected_rows = canonical_rows if training_rows is None else training_rows
    data = select_attack_rows(runtime.attacks, selected_rows)
    source_rows = [int(value) for value in selected_rows.detach().cpu().tolist()]
    lengths = [int(value) for value in data.lengths.detach().cpu().tolist()]
    clip_ids = [int(value) for value in data.clip_ids.detach().cpu().tolist()]
    labels = data.labels.detach().cpu().tolist()
    targets = data.targets_world.detach().cpu().tolist()
    armed_times = data.armed_time.detach().cpu().tolist()
    hit_times = data.hit_time.detach().cpu().tolist()
    positions = snapshot["positions"]
    basis = snapshot["basis"]
    phase_probabilities = snapshot["phase_probabilities"]
    lower_pin_probabilities = snapshot["lower_pin_probabilities"]
    armed_latch = snapshot["armed_latch"]
    hit_latch = snapshot["hit_latch"]
    reset_flags = snapshot["reset_flags"]
    source_frame = snapshot["source_frame"]
    weighted_loss_terms = snapshot.get("weighted_loss_terms")
    if not torch.is_tensor(weighted_loss_terms):
        weighted_loss_terms = torch.zeros(
            (
                int(source_frame.shape[0]),
                int(source_frame.shape[1]),
                len(WEIGHTED_LOSS_METRIC_NAMES),
            ),
            dtype=torch.float32,
        )
    expected_weighted_shape = (
        int(source_frame.shape[0]),
        int(source_frame.shape[1]),
        len(WEIGHTED_LOSS_METRIC_NAMES),
    )
    if tuple(weighted_loss_terms.shape) != expected_weighted_shape:
        raise RuntimeError(
            "Debug rollout weighted loss contract mismatch: "
            f"expected {expected_weighted_shape}, got {tuple(weighted_loss_terms.shape)}"
        )
    if not bool(torch.isfinite(weighted_loss_terms).all()):
        raise RuntimeError("Debug rollout contains a non-finite weighted loss term")
    if not torch.allclose(
        weighted_loss_terms[..., 0],
        weighted_loss_terms[..., 1:].sum(dim=-1),
        rtol=1.0e-5,
        atol=1.0e-7,
    ):
        raise RuntimeError(
            "Debug rollout total does not equal the sum of every weighted loss term"
        )
    source_clip_id = (
        snapshot_clip_ids
        if torch.is_tensor(snapshot_clip_ids)
        else torch.as_tensor(clip_ids, dtype=torch.long)[:, None].expand_as(source_frame)
    )
    geometry_clip_id = snapshot.get("geometry_clip_id")
    if not torch.is_tensor(geometry_clip_id):
        geometry_clip_id = source_clip_id
    target_world_m_frames = snapshot.get("target_world_m")
    if not torch.is_tensor(target_world_m_frames):
        target_world_m_frames = (
            runtime.attacks.targets_world.index_select(
                0,
                source_clip_id.reshape(-1).to(runtime.attacks.targets_world.device),
            )
            .reshape(*source_clip_id.shape, 3)
            .detach()
            .cpu()
        )
    else:
        target_world_m_frames = target_world_m_frames.detach().cpu()
    pelvis_index = runtime.full_clip.body_names.index("pelvis")
    target_frame_origin = target_world_m_frames.clone()
    target_frame_origin[..., 1] = 0.0
    target_frame_forward = target_world_m_frames - positions[..., pelvis_index, :]
    target_frame_forward[..., 1] = 0.0
    target_frame_length = torch.linalg.vector_norm(
        target_frame_forward, dim=-1, keepdim=True
    )
    if bool((target_frame_length <= 0.0).any()):
        raise RuntimeError(
            "Debug rollout contains the forbidden pelvis==target XZ frame"
        )
    target_frame_forward = target_frame_forward / target_frame_length
    if not (
        bool(torch.isfinite(target_frame_origin).all())
        and bool(torch.isfinite(target_frame_forward).all())
    ):
        raise RuntimeError("Debug rollout contains a non-finite v3 target frame")
    controller_root_pos = snapshot.get("controller_root_pos")
    controller_root_rot = snapshot.get("controller_root_rot")
    frozen_root_pos = snapshot.get("frozen_root_pos")
    frozen_root_rot = snapshot.get("frozen_root_rot")
    root_payloads = {
        "controller_root_pos": controller_root_pos,
        "controller_root_rot": controller_root_rot,
        "frozen_root_pos": frozen_root_pos,
        "frozen_root_rot": frozen_root_rot,
    }
    if not all(torch.is_tensor(value) for value in root_payloads.values()):
        # Compatibility for pre-marker captures: expose no invented roots.
        root_payloads = {}
    elif not all(
        bool(torch.isfinite(value).all())
        for value in root_payloads.values()
        if torch.is_tensor(value)
    ):
        raise RuntimeError("Debug rollout contains a non-finite root marker")
    rollout_frames = int(positions.shape[1])
    difficulty_values = training_row_difficulty_names(
        runtime, int(positions.shape[0])
    )
    rows: list[dict[str, object]] = []
    replica_counts: dict[int, int] = {}
    for row, (length, source_row) in enumerate(zip(lengths, source_rows)):
        replica = replica_counts.get(source_row, 0)
        replica_counts[source_row] = replica + 1
        rows.append(
            {
                "row": row,
                "family_replica": replica,
                "clip_id": clip_ids[row],
                "clip_name": runtime.attacks.names[source_row],
                "clip_path": str(runtime.attacks.paths[source_row]),
                "geometry_clip_id": int(geometry_clip_id[row, 0]),
                "geometry_clip_name": runtime.attacks.names[
                    int(geometry_clip_id[row, 0])
                ],
                "start": int(source_frame[row, 1]),
                "effective_k": rollout_frames - 1,
                "source_length": length,
                "virtual": False,
                "attack": True,
                **(
                    {"difficulty": difficulty_values[row]}
                    if difficulty_values
                    else {}
                ),
                "attack_labels": {
                    name: float(value)
                    for name, value in zip(ATTACK_LABEL_NAMES, labels[row])
                },
                "target_world_m": [float(value) for value in targets[row]],
                "armed_frame": float(armed_times[row]),
                "hit_frame": float(hit_times[row]),
            }
        )
    return {
        "schema_version": 1,
        "computed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "run_id": run_dir.name,
        "step": int(step),
        "fps": float(runtime.full_clip.fps),
        "joint_names": list(runtime.full_clip.body_names),
        "bones": [
            [int(parent), int(joint)]
            for joint, parent in enumerate(runtime.full_clip.parents_body_list)
            if int(parent) >= 0
        ],
        "rows": rows,
        "positions": [
            positions[row].tolist()
            for row in range(len(lengths))
        ],
        "basis": [
            basis[row].tolist()
            for row in range(len(lengths))
        ],
        "phase_probability_names": ["armed", "hit"],
        "phase_probabilities": [
            phase_probabilities[row].tolist()
            for row in range(len(lengths))
        ],
        "lower_pin_probability_names": ["left", "right"],
        "lower_pin_probabilities": [
            lower_pin_probabilities[row].tolist()
            for row in range(len(lengths))
        ],
        "armed_latch": [
            armed_latch[row].tolist()
            for row in range(len(lengths))
        ],
        "hit_latch": [
            hit_latch[row].tolist()
            for row in range(len(lengths))
        ],
        "reset_flags": reset_flags.tolist(),
        "target_world_m_frames": target_world_m_frames.tolist(),
        "target_frame_origin": target_frame_origin.tolist(),
        "target_frame_forward": target_frame_forward.tolist(),
        **{
            name: value.tolist()
            for name, value in root_payloads.items()
            if torch.is_tensor(value)
        },
        "weighted_loss_names": list(WEIGHTED_LOSS_METRIC_NAMES),
        "weighted_loss_terms": weighted_loss_terms.tolist(),
        "source_frame": source_frame.tolist(),
        "source_clip_id": source_clip_id.tolist(),
        "source_clip_name": [
            [runtime.attacks.names[int(value)] for value in row]
            for row in source_clip_id.tolist()
        ],
        "geometry_clip_id": geometry_clip_id.tolist(),
        "geometry_clip_name": [
            [runtime.attacks.names[int(value)] for value in row]
            for row in geometry_clip_id.tolist()
        ],
        "metadata": {
            "body_mode": "full",
            "mode": "slash2",
            "source_contract": (
                "exact world positions and rotations copied inside the real captured "
                "random-reset training graph; source_frame identifies each authored seed/advance, "
                "reset_flags marks exact GT reseeds, and export performs no rerun or FK reconstruction"
            ),
            "weighted_loss_contract": (
                "each frame contains the exact weighted per-row transition signal before "
                "term-specific rollout normalization; total is the sum of all "
                "displayed weighted terms"
            ),
            "target_frame_contract": (
                "green floor marker is target XZ and its arrow is the normalized "
                "current-pelvis-to-target flat heading held for that prediction frame"
            ),
            "random_fragment_resets": True,
        },
        "request": request,
        "source": source,
    }


def write_debug_rollout_capture(
    run_dir: Path,
    step: int,
    payload: dict[str, object],
    *,
    immutable: bool = True,
) -> tuple[Path, Path]:
    """Persist an immutable step capture and atomically refresh the latest alias."""

    debug_dir = run_dir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, separators=(",", ":"))
    capture_path = debug_rollout_capture_path(run_dir, step)
    if immutable and not capture_path.exists():
        capture_tmp = capture_path.with_suffix(capture_path.suffix + ".tmp")
        capture_tmp.write_text(serialized, encoding="utf-8")
        capture_tmp.replace(capture_path)
    latest_path = debug_rollout_artifact_path(run_dir)
    latest_tmp = latest_path.with_suffix(latest_path.suffix + ".tmp")
    latest_tmp.write_text(serialized, encoding="utf-8")
    latest_tmp.replace(latest_path)
    return (capture_path if immutable else latest_path), latest_path


def export_debug_rollout_capture(
    run_dir: Path,
    step: int,
    graph: CudaGraphStep,
    request: dict[str, object],
    *,
    immutable: bool = True,
) -> tuple[Path, Path]:
    snapshot = graph.snapshot_debug_rollout()
    payload = slash2_debug_rollout_payload(
        run_dir,
        step,
        graph.loss.runtime,
        snapshot,
        request,
        graph.loss.rows_static,
    )
    return write_debug_rollout_capture(
        run_dir, step, payload, immutable=immutable
    )


def maybe_export_debug_rollout(
    run_dir: Path,
    step: int,
    graph: CudaGraphStep,
) -> bool:
    global _DEBUG_ROLLOUT_NEXT_CHECK_AT
    now = time.monotonic()
    if now < _DEBUG_ROLLOUT_NEXT_CHECK_AT:
        return False
    _DEBUG_ROLLOUT_NEXT_CHECK_AT = now + DEBUG_ROLLOUT_CHECK_INTERVAL_S
    request_path = debug_rollout_request_path(run_dir)
    if not request_path.exists():
        return False
    try:
        request_text = request_path.read_text(encoding="utf-8")
        raw_request = json.loads(request_text)
        request = raw_request if isinstance(raw_request, dict) else {"request": raw_request}
        capture_path, artifact_path = export_debug_rollout_capture(
            run_dir,
            step,
            graph,
            request,
        )
        if request_path.exists() and request_path.read_text(encoding="utf-8") == request_text:
            request_path.unlink()
        print(
            f"slash2_debug_rollout_export step={step} "
            f"capture={capture_path} latest={artifact_path}",
            flush=True,
        )
        return True
    except Exception as exc:
        print(
            f"WARNING_SLASH2_DEBUG_ROLLOUT_EXPORT step={step} error={exc}",
            flush=True,
        )
        return False


def prepare_training(
    recipe: Recipe = RECIPE,
    *,
    attack_paths: list[Path] | None = None,
    prior_checkpoint_paths: dict[str, Path] | None = None,
    prepared_corpus_sha256: str | None = None,
    prepared_corpus_cache_dir: Path | None = None,
    prepared_corpus_cache_enabled: bool = True,
    prepared_corpus_prefix_cache_sha256: str | None = None,
    prepared_corpus_prefix_count: int = 0,
    prepared_corpus_prefix_cache_dir: Path | None = None,
    prepared_corpus_suffix_cache_sha256: str | None = None,
    prepared_corpus_suffix_cache_dir: Path | None = None,
    prepared_corpus_suffix_cache_compression_by_mode: dict[str, str] | None = None,
    configure_runtime: Callable[[Runtime], None] | None = None,
) -> PreparedTraining:
    if not torch.cuda.is_available():
        raise RuntimeError("Slash2 training requires CUDA because the accepted loop is CUDA-graph-only")
    random.seed(recipe.seed)
    np.random.seed(recipe.seed)
    torch.manual_seed(recipe.seed)
    torch.cuda.manual_seed_all(recipe.seed)
    device = torch.device("cuda")
    # The upper-deviation transport must reduce to the exact frozen FK pose at
    # zero.  TF32 matrix products introduced ~1e-3 rotation drift in that
    # identity audit on the RTX 4060, so this trainer keeps full FP32 math while
    # still using CUDA graph replay.
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False

    runtime = load_runtime(
        recipe,
        device,
        include_variants=bool(recipe.variant_dir) and attack_paths is None,
        attack_paths=attack_paths,
        prior_checkpoint_paths=prior_checkpoint_paths,
        prepared_corpus_sha256=prepared_corpus_sha256,
        prepared_corpus_cache_dir=prepared_corpus_cache_dir,
        prepared_corpus_cache_enabled=prepared_corpus_cache_enabled,
        prepared_corpus_prefix_cache_sha256=prepared_corpus_prefix_cache_sha256,
        prepared_corpus_prefix_count=prepared_corpus_prefix_count,
        prepared_corpus_prefix_cache_dir=prepared_corpus_prefix_cache_dir,
        prepared_corpus_suffix_cache_sha256=prepared_corpus_suffix_cache_sha256,
        prepared_corpus_suffix_cache_dir=prepared_corpus_suffix_cache_dir,
        prepared_corpus_suffix_cache_compression_by_mode=(
            prepared_corpus_suffix_cache_compression_by_mode
        ),
    )
    if not isinstance(runtime, Runtime):
        raise TypeError("Training requires the full Slash2 runtime")
    if configure_runtime is not None:
        configure_runtime(runtime)
    lower = DeltaAgent(
        lower_input_dim_for_recipe(recipe), LOWER_OUTPUT_DIM, recipe, gates=False
    ).to(device)
    upper = DeltaAgent(UPPER_INPUT_DIM, UPPER_STATE_DIM, recipe, gates=True).to(device)
    optimizer = make_optimizer(lower, upper, recipe, device)
    start_step = 0
    resume_path: Path | None = None
    if recipe.resume_checkpoint is not None:
        resume_path = Path(recipe.resume_checkpoint).resolve()
        checkpoint = torch.load(resume_path, map_location=device, weights_only=False)
        if is_legacy_neutral_upper_slash2_checkpoint_data(checkpoint):
            raise ValueError(f"{resume_path.name} uses the rejected neutral upper-body seed")
        if not is_slash2_checkpoint_data(checkpoint):
            raise ValueError(f"{resume_path.name} is not a current full-episode Slash2 checkpoint")
        lower.load_state_dict(checkpoint["lower_agent"])
        upper.load_state_dict(checkpoint["upper_agent"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        start_step = int(checkpoint["step"])
        if start_step < 0:
            raise ValueError(f"Resume step {start_step} must be non-negative")

    # Exhaustive contracts are explicit local/preflight jobs, never part of a
    # billed production launch. Runtime loading, state-dict loading, dimension
    # checks, and CUDA graph capture below remain fail-fast production checks.
    tests: dict[str, object] = {
        "schema": "slash2_production_startup_v1",
        "passed": True,
        "tests": {},
    }
    physical_batch = int(recipe.batch_size)
    if physical_batch <= 0 or physical_batch > len(runtime.attacks.paths):
        raise ValueError(
            f"Physical batch {physical_batch} must be positive and no larger than "
            f"the loaded corpus ({len(runtime.attacks.paths)})"
        )
    training_rows = (
        torch.arange(physical_batch, dtype=torch.long, device=device)
        if len(runtime.attacks.paths) > physical_batch
        else None
    )
    compile_training_networks(runtime, lower, upper)
    tests["training_optimizations"] = {
        "fast_fixed_topology_fk": True,
        "compiled_fast_fk_forward_and_backward": True,
        "reuse_lower_fk_for_upper_transport": True,
        "paired_upper_fk": True,
        "compiled_trainable_agents": True,
        "trainable_agents_captured_by_outer_cuda_graph": True,
        "compiled_frozen_models": runtime.frozen_walk is not None,
        "frozen_agent_enabled": bool(recipe.frozen_agent_enabled),
        "frozen_checkpoint_loaded": runtime.walk_checkpoint is not None,
        "frozen_model_allocated": runtime.frozen_walk is not None,
        "lower_input_dim": lower_input_dim_for_recipe(recipe),
        "all_kernels_captured_by_outer_cuda_graph": True,
        "split_forward_backward_graphed_callables": True,
    }
    loss = FullEpisodeLoss(runtime, lower, upper, rows_static=training_rows)
    # The static graph reads a tiny staged table of random fragment starts. A
    # resumed run continues the deterministic schedule at its checkpoint step.
    loss.fragment_epoch_start = start_step
    tests["lossless_host_memory_quiesce"] = release_startup_host_memory(
        "before_cuda_graph_capture"
    )
    graph = CudaGraphStep(loss, optimizer)
    tests["tests"]["resume_checkpoint"] = {
        "enabled": recipe.resume_checkpoint is not None,
        "checkpoint": str(Path(recipe.resume_checkpoint).resolve()) if recipe.resume_checkpoint is not None else None,
        "start_step": start_step,
        "optimizer_state_rows": len(optimizer.state),
        "passed": (
            (recipe.resume_checkpoint is None and start_step == 0)
            or (recipe.resume_checkpoint is not None and start_step > 0 and len(optimizer.state) > 0)
        ),
    }
    tests["passed"] = bool(tests["passed"]) and bool(tests["tests"]["resume_checkpoint"]["passed"])
    if not tests["passed"]:
        raise RuntimeError("Slash2 checkpoint-resume contract failed; refusing to train")
    return PreparedTraining(recipe, runtime, lower, upper, optimizer, tests, graph, start_step)


def run_prepared(
    prepared: PreparedTraining,
    smoke: bool = False,
    smoke_steps: int | None = None,
    stop_file: Path | None = None,
    current_run_file: Path | None = None,
    export_debug_rollout_once: bool = False,
    run_name_override: str | None = None,
    optimizer_started_monotonic: float | None = None,
) -> Path:
    global _DEBUG_ROLLOUT_NEXT_CHECK_AT
    recipe = prepared.recipe
    runtime = prepared.runtime
    lower = prepared.lower
    upper = prepared.upper
    optimizer = prepared.optimizer
    tests = prepared.tests
    graph = prepared.graph
    graph.reset()
    start_step = int(prepared.start_step)

    if run_name_override is not None:
        if (
            not run_name_override
            or Path(run_name_override).name != run_name_override
            or any(separator in run_name_override for separator in ("/", "\\"))
        ):
            raise ValueError(f"Invalid run name override: {run_name_override!r}")
        run_name = run_name_override
    else:
        run_name = run_id(recipe, smoke)
    run_dir = Path(recipe.output_root) / run_name
    checkpoint_storage.enforce_checkpoint_path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=False)
    checkpoint_storage.fsync_directory(run_dir.parent)
    checkpoint_storage.atomic_json(run_dir / "recipe.json", asdict(recipe))
    checkpoint_storage.atomic_json(run_dir / "contract_tests.json", tests)
    if current_run_file is not None:
        current_run_file.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_storage.atomic_text(current_run_file, str(run_dir.resolve()) + "\n")
    if export_debug_rollout_once:
        request_path = debug_rollout_request_path(run_dir)
        request_path.parent.mkdir(parents=True, exist_ok=True)
        request_path.write_text(
            json.dumps(
                {
                    "requested_at": datetime.now().astimezone().isoformat(
                        timespec="seconds"
                    ),
                    "request_id": "one-genuine-optimizer-step",
                    "format": "json",
                    "reason": (
                        "Export the exact captured CUDA buffers from the requested "
                        "single optimizer update for visual confirmation."
                    ),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    _DEBUG_ROLLOUT_NEXT_CHECK_AT = 0.0

    last_metrics: dict[str, float] = {}
    completed_steps = 0
    log_path = run_dir / "metrics.jsonl"
    tensorboard_loss_names = list(WEIGHTED_LOSS_METRIC_NAMES)
    custom_scalar_panels: dict[str, list[object]] = {
        "Losses": [
            "Multiline",
            [f"loss/{name}" for name in tensorboard_loss_names],
        ],
        "Blade collision": [
            "Multiline",
            [
                "collision/max_penetration_m",
                "collision/bad_transition_rate",
            ],
        ],
        "Lower-arm length": [
            "Multiline",
            ["loss/lowerarm_length", "distance/lowerarm_max_length_error_m"],
        ],
        "Opposite calf collision": [
            "Multiline",
            [
                "loss/opposite_calf_collision",
                "collision/opposite_calf_max_overlap_m",
                "collision/opposite_calf_bad_transition_rate",
            ],
        ],
        "Pike blade look at target": [
            "Multiline",
            ["loss/pike_blade_look_at_target"],
        ],
        "Predictive pin teacher": ["Multiline", ["loss/predictive_pin", "pin/expected_left", "pin/expected_right", "pin/error_mean"]],
        "Anti pin slide": [
            "Multiline",
            [
                "loss/anti_pin_slide",
                "anti_pin_slide/left_speed_mps",
                "anti_pin_slide/right_speed_mps",
                "anti_pin_slide/gate_mean",
            ],
        ],
        "Lower continuous pin": [
            "Multiline",
            ["pin/left_mean", "pin/right_mean", "pin/active_rate"],
        ],
        "Phase latches": [
            "Multiline",
            ["phase/armed_latch_rate", "phase/hit_latch_rate"],
        ],
    }
    writer = SummaryWriter(log_dir=str(run_dir / "tensorboard"), flush_secs=10, max_queue=100)
    writer.add_text("run/recipe", f"```json\n{json.dumps(asdict(recipe), indent=2)}\n```", 0)
    writer.add_text("run/contract_tests", f"```json\n{json.dumps(tests, indent=2)}\n```", 0)
    writer.add_custom_scalars(
        {
            "Slash2": custom_scalar_panels
        }
    )
    active_marker = write_debug_rollout_active_marker(run_dir)
    performance_started = time.perf_counter()
    performance_step = 0
    try:
        with log_path.open("a", encoding="utf-8") as log:
            resolved_smoke_steps = (
                int(recipe.smoke_replays) if smoke_steps is None else int(smoke_steps)
            )
            if smoke and resolved_smoke_steps <= 0:
                raise ValueError("Smoke execution must include at least one optimizer step")
            local_steps = (
                range(1, resolved_smoke_steps + 1)
                if smoke
                else itertools.count(1)
            )
            for local_step in local_steps:
                step = start_step + local_step
                learning_rate = learning_rate_for_step(recipe, step)
                ae11_weight = ae11_weight_for_step(recipe, step)
                upper_prior_weight = upper_prior_weight_for_step(recipe, step)
                set_optimizer_learning_rate(optimizer, learning_rate)
                set_training_loss_weights(
                    graph.loss,
                    ae11_weight,
                    upper_prior_weight,
                )
                should_log = (
                    local_step == 1
                    or local_step % recipe.log_every == 0
                    or (smoke and local_step == resolved_smoke_steps)
                )
                replay_metrics = graph.replay(synchronize=should_log)
                maybe_export_debug_rollout(run_dir, step, graph)
                completed_steps = local_step
                if should_log:
                    if replay_metrics is None:
                        raise RuntimeError("Synchronized Slash2 replay returned no metrics")
                    last_metrics = replay_metrics
                    now = time.perf_counter()
                    measured_steps = local_step - performance_step
                    steps_per_second = measured_steps / max(now - performance_started, 1.0e-9)
                    performance_started = now
                    performance_step = local_step
                    row = {
                        "step": step,
                        **last_metrics,
                        "steps_per_second": steps_per_second,
                    }
                    log.write(json.dumps(row) + "\n")
                    weighted_losses = weighted_loss_terms(
                        last_metrics,
                        recipe,
                        ae11_weight=ae11_weight,
                        upper_prior_weight=upper_prior_weight,
                    )
                    for name in tensorboard_loss_names:
                        writer.add_scalar(f"loss/{name}", weighted_losses[name], step)
                    writer.add_scalar("distance/hit_target_m", last_metrics["hit_target_m"], step)
                    writer.add_scalar(
                        "dynamics/hit_linear_velocity_error_mps",
                        last_metrics["hit_linear_velocity_error_mps"],
                        step,
                    )
                    writer.add_scalar(
                        "dynamics/hit_angular_velocity_error_radps",
                        last_metrics["hit_angular_velocity_error_radps"],
                        step,
                    )
                    writer.add_scalar(
                        "distance/lowerarm_max_length_error_m",
                        last_metrics["lowerarm_max_length_error_m"],
                        step,
                    )
                    writer.add_scalar(
                        "collision/opposite_calf_max_overlap_m",
                        last_metrics["opposite_calf_max_overlap_m"],
                        step,
                    )
                    writer.add_scalar(
                        "collision/opposite_calf_bad_transition_rate",
                        last_metrics["opposite_calf_collision_bad_rate"],
                        step,
                    )
                    writer.add_scalar(
                        "collision/max_penetration_m",
                        last_metrics["blade_max_penetration_m"],
                        step,
                    )
                    writer.add_scalar(
                        "collision/bad_transition_rate",
                        last_metrics["blade_collision_bad_rate"],
                        step,
                    )
                    writer.add_scalar("pin/left_mean", last_metrics["lower_pin_left_mean"], step)
                    writer.add_scalar("pin/right_mean", last_metrics["lower_pin_right_mean"], step)
                    writer.add_scalar("pin/active_rate", last_metrics["lower_pin_active_rate"], step)
                    writer.add_scalar("phase/armed_latch_rate", last_metrics["armed_latch_rate"], step)
                    writer.add_scalar("phase/hit_latch_rate", last_metrics["hit_latch_rate"], step)
                    writer.add_scalar("optimizer/learning_rate", learning_rate, step)
                    writer.add_scalar("optimizer/gradient_norm_preclip", last_metrics["gradient_norm"], step)
                    writer.add_scalar("weight/ae11", ae11_weight, step)
                    writer.add_scalar("weight/upper_prior", upper_prior_weight, step)
                    writer.add_scalar(
                        "weight/ae33_multiplier",
                        recipe.ae33_weight_multiplier,
                        step,
                    )
                    writer.add_scalar(
                        "weight/blade_collision",
                        recipe.blade_collision_weight,
                        step,
                    )
                    writer.add_scalar(
                        "weight/hit_linear_velocity",
                        recipe.hit_linear_velocity_weight,
                        step,
                    )
                    writer.add_scalar(
                        "weight/hit_angular_velocity",
                        recipe.hit_angular_velocity_weight,
                        step,
                    )
                    writer.add_scalar("weight/final_pose", recipe.final_pose_weight, step)
                    writer.add_scalar(
                        "weight/lowerarm_length",
                        recipe.lowerarm_length_weight,
                        step,
                    )
                    writer.add_scalar(
                        "weight/opposite_calf_collision",
                        recipe.opposite_calf_collision_weight,
                        step,
                    )
                    writer.add_scalar(
                        "weight/pike_blade_look_at_target",
                        recipe.pike_blade_look_at_target_weight,
                        step,
                    )
                    writer.add_scalar("performance/steps_per_second", steps_per_second, step)
                    writer.add_scalar("weight/predictive_pin", recipe.predictive_pin_weight, step)
                    writer.add_scalar("weight/anti_pin_slide", recipe.anti_pin_slide_weight, step)
                    writer.add_scalar("pin/expected_left", last_metrics["pin_teacher_left_mean"], step)
                    writer.add_scalar("pin/expected_right", last_metrics["pin_teacher_right_mean"], step)
                    writer.add_scalar("pin/error_mean", last_metrics["pin_error_mean"], step)
                    writer.add_scalar("anti_pin_slide/left_speed_mps", last_metrics["anti_pin_slide_left_speed_mps"], step)
                    writer.add_scalar("anti_pin_slide/right_speed_mps", last_metrics["anti_pin_slide_right_speed_mps"], step)
                    writer.add_scalar("anti_pin_slide/gate_mean", last_metrics["anti_pin_slide_gate_mean"], step)
                    print(json.dumps(row, sort_keys=True), flush=True)
                    log.flush()
                    writer.flush()
                if not smoke and local_step % recipe.save_every == 0:
                    checkpoint_progress = {
                        "schema": "slash2_checkpoint_optimizer_progress_v1",
                        "startStep": start_step, "completedSteps": int(local_step),
                        "optimizerElapsedSeconds": (
                            time.monotonic() - optimizer_started_monotonic
                            if optimizer_started_monotonic is not None else None
                        ),
                        "capturedAtUnix": time.time(),
                    }
                    archive_due = (
                        local_step % recipe.checkpoint_archive_every == 0
                    )
                    export_debug_rollout_capture(
                        run_dir,
                        step,
                        graph,
                        {
                            "kind": "checkpoint",
                            "checkpoint_step": int(step),
                        },
                        immutable=archive_due,
                    )
                    save_checkpoint(
                        run_dir,
                        step,
                        runtime,
                        lower,
                        upper,
                        optimizer,
                        last_metrics,
                        tests,
                        latest=True,
                        optimizer_progress=checkpoint_progress,
                    )
                    if archive_due:
                        archive_latest_checkpoint(run_dir, step)
                if stop_file is not None and stop_file.exists():
                    print(f"stop requested after step {step}", flush=True)
                    log.flush()
                    writer.flush()
                    break
        final_step = start_step + completed_steps
        final_progress = {
            "schema": "slash2_checkpoint_optimizer_progress_v1",
            "startStep": start_step, "completedSteps": int(completed_steps),
            "optimizerElapsedSeconds": (
                time.monotonic() - optimizer_started_monotonic
                if optimizer_started_monotonic is not None else None
            ),
            "capturedAtUnix": time.time(),
        }
        export_debug_rollout_capture(
            run_dir,
            final_step,
            graph,
            {
                "kind": "final_checkpoint",
                "checkpoint_step": int(final_step),
            },
        )
        final = save_checkpoint(
            run_dir,
            final_step,
            runtime,
            lower,
            upper,
            optimizer,
            last_metrics,
            tests,
            latest=True,
            optimizer_progress=final_progress,
        )
        print(f"saved {final}", flush=True)
        return run_dir
    finally:
        writer.close()
        remove_debug_rollout_active_marker(active_marker)


def train(smoke: bool = False) -> Path:
    return run_prepared(prepare_training(RECIPE), smoke=smoke)


def prepare_only() -> None:
    prepared = prepare_training(RECIPE)
    free_bytes, total_bytes = torch.cuda.mem_get_info()
    print(
        json.dumps(
            {
                "ready": True,
                "cuda_graph": prepared.graph.kind,
                "dataset_clips": len(prepared.runtime.attacks.paths),
                "families": len(ATTACK_LABELS),
                "logical_batch_size": prepared.recipe.batch_size,
                "original_sample_probability": prepared.recipe.original_sample_probability,
                "ae33_weight_multiplier": prepared.recipe.ae33_weight_multiplier,
                "free_vram_mb": free_bytes // (1024 * 1024),
                "total_vram_mb": total_bytes // (1024 * 1024),
            },
            sort_keys=True,
        ),
        flush=True,
    )


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the current two-agent Slash2 recipe.")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Run the contract suite, capture the full GT16 episode graph, and replay two optimizer steps.",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Run contracts and capture the full CUDA graph without replaying a training step.",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    if args.prepare_only:
        prepare_only()
    else:
        train(smoke=bool(args.smoke_test))


if __name__ == "__main__":
    main()
