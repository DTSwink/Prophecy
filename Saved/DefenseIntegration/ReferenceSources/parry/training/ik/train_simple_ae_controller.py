from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import random
import subprocess
import threading
import time
import traceback
from dataclasses import asdict, dataclass, fields, replace
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.tensorboard import SummaryWriter

try:
    from .bootstrap import PROJECT_ROOT, ensure_paths
    from .naming import checkpoint_path, ik_run_id
    from .dataset_contract import audit_npz_folder
    from . import checkpoint_runtime as ckpt_runtime
    from . import contact_physics as cp
    from . import excess_envelope as env
    from . import ik_core as tl
    from . import pose_bank_projector as posebank
    from .rl_loss import RL_TERM_NAMES, RLLossConfig, compute_rl_loss
    from .train_simple_autoencoder import (
        AE_SCORE_SCOPE_FULL_WINDOW,
        AE_SCORE_SCOPE_OUTPUT,
        SimpleAEConfig,
        SimpleAutoencoder,
        normalized_ae_score_scope,
        transform_ae_feature_space,
    )
except ImportError:
    from bootstrap import PROJECT_ROOT, ensure_paths
    from naming import checkpoint_path, ik_run_id
    from dataset_contract import audit_npz_folder
    import checkpoint_runtime as ckpt_runtime
    import contact_physics as cp
    import excess_envelope as env
    import ik_core as tl
    import pose_bank_projector as posebank
    from rl_loss import RL_TERM_NAMES, RLLossConfig, compute_rl_loss
    from train_simple_autoencoder import (
        AE_SCORE_SCOPE_FULL_WINDOW,
        AE_SCORE_SCOPE_OUTPUT,
        SimpleAEConfig,
        SimpleAutoencoder,
        normalized_ae_score_scope,
        transform_ae_feature_space,
    )

ensure_paths()


DEFAULT_WALK_F = PROJECT_ROOT / "ue5" / "animations_omni_only" / "npz_final" / "M_Neutral_Walk_Loop_F.npz"
DEFAULT_SYNTHETIC_CONTROLLER_DIR = PROJECT_ROOT / "ue5" / "animations_synthetic" / "npz_final"
DEFAULT_VIRTUAL_CONTROLLER_DIR = PROJECT_ROOT / "ue5" / "animations_virtual_controller" / "npz_final"
DEFAULT_SIMPLE_AE_CHECKPOINT = (
    PROJECT_ROOT
    / "training"
    / "runs"
    / "20260610_004104_ik_ae_harshness_sweep_vanilla_grid_12k"
    / "checkpoints"
    / "h1024_l3_ld128_n0_best.pt"
)
OFFICIAL_RUNNING_AE1_VARIANT = "h1024_l3_ld128_n0"
OFFICIAL_RUNNING_AE1_AGENT_SWEEP_GT64_MEAN_M = 0.1219027116894722
OFFICIAL_RUNNING_AE1_AGENT_SWEEP_ONE_STEP64_MEAN_M = 0.005477728322148323
OFFICIAL_RUNNING_AE1_AGENT_SWEEP_RANK = 1
DEFAULT_AE4_PROJECTOR_DIR = posebank.DEFAULT_CHECKPOINT_DIR
LEGACY_AE4_PROJECTOR_DIR = PROJECT_ROOT.parent / "New folder" / "checkpoints"
LEGACY_OUTPUT_POSE_AE4_FEATURES = {
    "ae4_root_context_output_pose_to_full_ik",
    "ae4_root_context_full_output_pose_to_full_ik",
    "ae4_root_context_to_full_ik_pose",
    "ae4_root_context_masked_pelvis_height_full_output_pose_to_full_ik",
}
RUNS_DIR = PROJECT_ROOT / "training" / "runs"
DEFAULT_AE_GLOB = "*_ik_simple_ae_*"
SIMPLE_CONTROLLER_AE_KIND = "simple_controller_io_autoencoder"
LEGACY_SIMPLE_AE_KIND = "simple_" + "ag" + "ent_io_autoencoder"
FOOT_ROLL_FOOT_DIMS_M = (0.175, 0.120, 0.051)
FOOT_ROLL_TOE_DIMS_M = (0.048, 0.120, 0.049)
FOOT_ROLL_SOLE_VERTICAL_OFFSET_M = -0.006
FOOT_ROLL_PIN_STE_SCALE = 8.0
DEFAULT_FOOT_ROLL_INTEGRATION_STEPS = 60
FOOT_ROLL_INTEGRATION_STEPS = int(DEFAULT_FOOT_ROLL_INTEGRATION_STEPS)
FOOT_ROLL_UP_AXIS = 2
FOOT_ROLL_HEIGHT_AXIS = FOOT_ROLL_UP_AXIS
FOOT_ROLL_PIN_MODE_LEGACY_LOGIT_SELECTED = "legacy_logit_selected"
FOOT_ROLL_PIN_MODE_CONTINUOUS_SIGMOID = "continuous_sigmoid"
FOOT_ROLL_PIN_MODE_VALUES = (
    FOOT_ROLL_PIN_MODE_LEGACY_LOGIT_SELECTED,
    FOOT_ROLL_PIN_MODE_CONTINUOUS_SIGMOID,
)
DEFAULT_FOOT_ROLL_PIN_MODE = FOOT_ROLL_PIN_MODE_CONTINUOUS_SIGMOID
FOOT_ROLL_PIN_MODE = DEFAULT_FOOT_ROLL_PIN_MODE
DEFAULT_FOOT_ROLL_NEAR_FLOOR_PIN_FULL_HEIGHT_M = 0.015
DEFAULT_FOOT_ROLL_NEAR_FLOOR_PIN_FADE_HEIGHT_M = 0.020
DEFAULT_FOOT_ROLL_NEAR_FLOOR_PIN_MIN_PROB = 1.0
FOOT_ROLL_NEAR_FLOOR_PIN_FULL_HEIGHT_M = float(DEFAULT_FOOT_ROLL_NEAR_FLOOR_PIN_FULL_HEIGHT_M)
FOOT_ROLL_NEAR_FLOOR_PIN_FADE_HEIGHT_M = float(DEFAULT_FOOT_ROLL_NEAR_FLOOR_PIN_FADE_HEIGHT_M)
FOOT_ROLL_NEAR_FLOOR_PIN_MIN_PROB = float(DEFAULT_FOOT_ROLL_NEAR_FLOOR_PIN_MIN_PROB)
FOOT_HEIGHT_PIN_THRESHOLD_M = 0.005
FOOT_CONTACT_MIN_HEIGHT_LOSS_FULL_M = 0.010
FOOT_CONTACT_MIN_HEIGHT_LOSS_MAX = 0.0
DEFAULT_FAKE_GRAVITY_ENABLED = 0.0
FAKE_GRAVITY_ENABLED = float(DEFAULT_FAKE_GRAVITY_ENABLED)
DEFAULT_FAKE_GRAVITY_MPS2 = 9.80665
FAKE_GRAVITY_MPS2 = float(DEFAULT_FAKE_GRAVITY_MPS2)
DEFAULT_FAKE_GRAVITY_USES_HEIGHT_GATE = True
FAKE_GRAVITY_USES_HEIGHT_GATE = bool(DEFAULT_FAKE_GRAVITY_USES_HEIGHT_GATE)
DEFAULT_AE_FOOT_LOCATION_MULTIPLIER = 1.0
AE_FOOT_LOCATION_MULTIPLIER = float(DEFAULT_AE_FOOT_LOCATION_MULTIPLIER)
DEFAULT_AE_FOOT_ROTATION_MULTIPLIER = 1.0
AE_FOOT_ROTATION_MULTIPLIER = float(DEFAULT_AE_FOOT_ROTATION_MULTIPLIER)
SIMPLE_AE_WINDOW_FRAMES = 2
DEFAULT_AE_TERMINAL_ONLY = False
AE_TERMINAL_ONLY = bool(DEFAULT_AE_TERMINAL_ONLY)
DEFAULT_FOOT_ROLL_HEIGHT_PIN_GATE = False
FOOT_ROLL_HEIGHT_PIN_GATE = bool(DEFAULT_FOOT_ROLL_HEIGHT_PIN_GATE)
DEFAULT_FOOT_UNPIN_PENALTY_WEIGHT = 0.0
FOOT_UNPIN_PENALTY_WEIGHT = float(DEFAULT_FOOT_UNPIN_PENALTY_WEIGHT)
FOOT_UNPIN_PENALTY_TERM_NAME = "foot_unpin_penalty_weighted"
FOOT_UNPIN_SOFT_RATE_TERM_NAME = "foot_unpin_soft_any_rate"
DEFAULT_PINNED_FOOT_INTENT_PENALTY_WEIGHT = 0.0
PINNED_FOOT_INTENT_PENALTY_WEIGHT = float(DEFAULT_PINNED_FOOT_INTENT_PENALTY_WEIGHT)
PINNED_FOOT_INTENT_TERM_NAME = "pinned_foot_intent_penalty_weighted"
PINNED_FOOT_INTENT_RAW_TERM_NAME = "pinned_foot_intent_mps2"
PINNED_FOOT_INTENT_MPS_TERM_NAME = "pinned_foot_intent_mps"
DEFAULT_SLIDE_TENTATIVE_LOSS_WEIGHT = 0.0
SLIDE_TENTATIVE_TERM_NAME = "slide_tentative_weighted"
SLIDE_TENTATIVE_RAW_TERM_NAME = "slide_tentative_m"
SLIDE_TENTATIVE_PIN_RATE_TERM_NAME = "slide_tentative_pin_rate"
PIN_BEHAVIOR_TERM_NAMES = (
    "pin_double_rate",
    "pin_single_rate",
    "pin_switch_rate",
    "pin_unpin_after_double_rate",
    "pin_stationary_amount",
)
FOOT_CONTACT_HEIGHT_LOSS_TERM_NAME = "foot_contact_min_height_weighted"
FOOT_CONTACT_HEIGHT_METRIC_NAMES = (
    "foot_contact_min_height_m",
    "foot_contact_any_pinned_rate",
    "foot_contact_left_pinned_rate",
    "foot_contact_right_pinned_rate",
)
DEFAULT_PINNED_FOOT_HEIGHT_LOSS_WEIGHT = 0.0
PINNED_FOOT_HEIGHT_TERM_NAME = "pinned_foot_height_weighted"
PINNED_FOOT_HEIGHT_RAW_TERM_NAME = "pinned_foot_height_excess_m"
PINNED_FOOT_HEIGHT_MAX_TERM_NAME = "pinned_foot_height_max_m"
DEFAULT_LEG_CROSSING_CAPSULE_LOSS_WEIGHT = 0.0
LEG_CROSSING_CAPSULE_TERM_NAME = "leg_crossing_capsule_weighted"
LEG_CROSSING_CAPSULE_RAW_TERM_NAME = "leg_crossing_capsule_overlap_m"
LEG_CROSSING_CAPSULE_RATE_TERM_NAME = "leg_crossing_capsule_bad_rate"
LEG_CROSSING_CAPSULE_LOSS_WEIGHT = DEFAULT_LEG_CROSSING_CAPSULE_LOSS_WEIGHT
DEFAULT_DEDICATED_REAL_LOSS_MULTIPLIER = 1.0
PINNED_FOOT_HEIGHT_REFERENCE_EXCESS_M = 0.010758483782410622
PINNED_FOOT_HEIGHT_ZERO_FRACTION = 0.01
PINNED_FOOT_HEIGHT_REFERENCE_LOSS = 0.01
PINNED_FOOT_HEIGHT_LOSS_CAP = 0.02
DEFAULT_IDLE_FOOT_FLATNESS_LOSS_WEIGHT = 0.0
IDLE_FOOT_FLATNESS_TERM_NAME = "idle_foot_flatness_weighted"
IDLE_FOOT_FLATNESS_RAW_TERM_NAME = "idle_foot_flatness_excess_m"
IDLE_FOOT_FLATNESS_MAX_TERM_NAME = "idle_foot_flatness_max_m"
IDLE_FOOT_FLATNESS_REFERENCE_EXCESS_M = 0.023510390892624855
IDLE_FOOT_FLATNESS_ZERO_FRACTION = 0.25
IDLE_FOOT_FLATNESS_REFERENCE_LOSS = 0.01
IDLE_FOOT_FLATNESS_LOSS_CAP = 0.02
FORCED_IDLE_CLIP_STEM = "m_neutral_stand_idle_loop"
DEFAULT_FORCED_IDLE_BATCH_FRACTION: float | None = None
FORCED_TURN45_CLIP_STEMS = ("m_neutral_stand_turn_045_l", "m_neutral_stand_turn_045_r")
DEFAULT_FORCED_TURN45_BATCH_FRACTION: float | None = None
AE2_WEIGHTED_TERM_NAME = "ae2_score_weighted"
AE3_PIN_WEIGHTED_TERM_NAME = "ae3_pin_score_weighted"
AE3_EXPECTED_PIN_HEIGHT_PUSH_SCALE = 0.25
AE3_LOGIT_ALIGNMENT_SCALE = 1.0
PIN_LOGIT_GAP_WEIGHTED_TERM_NAME = "pin_logit_gap_weighted"
PIN_LOGIT_GAP_RAW_TERM_NAME = "pin_logit_gap_hinge"
PIN_LOGIT_GAP_BAD_RATE_TERM_NAME = "pin_logit_gap_bad_rate"
PIN_LOGIT_GAP_MARGIN = 0.5
DEFAULT_PIN_LOGIT_GAP_LOSS_WEIGHT = 0.0
DEFAULT_INERTIA_ACCELERATION_LOSS_WEIGHT = 0.0
INERTIA_ACCELERATION_REFERENCE_LOSS = 0.01
INERTIA_ACCELERATION_REFERENCE_RAW = 0.008300782763399184
INERTIA_ACCELERATION_LOSS_SCALE = INERTIA_ACCELERATION_REFERENCE_LOSS / INERTIA_ACCELERATION_REFERENCE_RAW
INERTIA_ACCELERATION_WEIGHTED_TERM_NAME = "inertia_accel_weighted"
INERTIA_ACCELERATION_RAW_TERM_NAME = "inertia_accel_excess_ratio"
INERTIA_LINEAR_ACCELERATION_RAW_TERM_NAME = "inertia_linear_accel_excess"
INERTIA_ANGULAR_ACCELERATION_RAW_TERM_NAME = "inertia_angular_accel_excess"
INERTIA_ACCELERATION_BAD_RATE_TERM_NAME = "inertia_accel_bad_rate"
DEFAULT_ROOT_ACCEL_PIN_LOSS_RATIO = 0.0
ROOT_ACCEL_PIN_FIXED_LOSS_WEIGHT = 0.0006039192325934142
ROOT_ACCEL_PIN_ACCEL_THRESHOLD_MPS2 = 10.0
ROOT_ACCEL_PIN_ACCEL_GATE_WIDTH_MPS2 = 2.0
ROOT_ACCEL_PIN_TARGET_PROB = 0.9
ROOT_ACCEL_PIN_HEIGHT_THRESHOLD_M = 0.005
ROOT_ACCEL_PIN_SOFTMAX_SCALE = 24.0
ROOT_ACCEL_PIN_WEIGHTED_TERM_NAME = "root_accel_pin_weighted"
ROOT_ACCEL_PIN_RAW_TERM_NAME = "root_accel_pin_raw"
ROOT_ACCEL_PIN_SCALE_TERM_NAME = "root_accel_pin_scale"
ROOT_ACCEL_PIN_ACCEL_TERM_NAME = "root_accel_pin_root_acc_mps2"
ROOT_ACCEL_PIN_ACTIVE_RATE_TERM_NAME = "root_accel_pin_active_rate"
ROOT_ACCEL_PIN_BAD_RATE_TERM_NAME = "root_accel_pin_bad_rate"
ROOT_ACCEL_PIN_MAX_PROB_TERM_NAME = "root_accel_pin_max_prob"
ROOT_ACCEL_PIN_HEIGHT_TERM_NAME = "root_accel_pin_height_m"
DEFAULT_AE2_LOSS_WEIGHT = 0.006772103486342108
AE2_BAKED_NORMAL_LOSS_WEIGHT = 0.3386051743171054
DEFAULT_AE3_LOSS_WEIGHT = 0.1
AE4_POSE_SCORE_TERM_NAME = "ae4_pose_score"
AE4_POSE_HINGE_TERM_NAME = "ae4_pose_hinge"
AE4_POSE_WEIGHTED_TERM_NAME = "ae4_pose_score_weighted"
AE4_POSE_DISTANCE_DEADZONE_M = 0.05 / 6.0
AE4_POSE_REFERENCE_EXCESS_M = 0.015781253576278687
AE4_POSE_REFERENCE_LOSS = 0.01
AE4_POSE_SCORE_DEADZONE = AE4_POSE_DISTANCE_DEADZONE_M
AE4_POSE_REFERENCE_SCORE = AE4_POSE_REFERENCE_EXCESS_M
DEFAULT_AE4_LOSS_WEIGHT = AE4_POSE_REFERENCE_LOSS / AE4_POSE_REFERENCE_EXCESS_M
AE4_POSE_ROTATION_DEADZONE_DEG = 20.0
AE4_POSE_ROTATION_REFERENCE_DEG = 45.0
AE4_POSE_ROTATION_REFERENCE_LOSS = 0.01
AE4_POSE_ROTATION_EXCESS_TO_HINGE = (
    (AE4_POSE_ROTATION_REFERENCE_LOSS / DEFAULT_AE4_LOSS_WEIGHT)
    / math.radians(AE4_POSE_ROTATION_REFERENCE_DEG - AE4_POSE_ROTATION_DEADZONE_DEG)
)
AE4_BANK_PIN_WEIGHTED_TERM_NAME = "ae4_bank_pin_score_weighted"
AE4_BANK_PIN_RAW_TERM_NAME = "ae4_bank_pin_mistake_prob"
AE4_BANK_PIN_ROOT_SCALE_TERM_NAME = "ae4_bank_pin_root_scale"
DEFAULT_AE4_BANK_PIN_LOSS_WEIGHT = 0.0
AE4_BANK_PIN_LOGIT_MISTAKE_LOSS = 0.01
AE4_BANK_PIN_WALKF_SPEED_FRACTION = 0.2
AE4_BANK_PIN_TURN45L_YAW_FRACTION = 0.2
AE3_BANK_PIN_PHASE_START_HOLD_FRACTION = 0.2
AE3_BANK_PIN_PHASE_END_HOLD_FRACTION = 0.4
POSE_BANK_PIN_SLIDE_DISTANCE_THRESHOLD_M = 0.0115
POSE_BANK_PIN_CONTACT_GEOMETRY = cp.ContactGeometryConfig(
    foot_length=FOOT_ROLL_FOOT_DIMS_M[0],
    foot_width=FOOT_ROLL_FOOT_DIMS_M[1],
    foot_height=FOOT_ROLL_FOOT_DIMS_M[2],
    toe_length=FOOT_ROLL_TOE_DIMS_M[0],
    toe_width=FOOT_ROLL_TOE_DIMS_M[1],
    toe_height=FOOT_ROLL_TOE_DIMS_M[2],
    sole_vertical_offset=FOOT_ROLL_SOLE_VERTICAL_OFFSET_M,
    ground_y=0.0,
    height_threshold_m=0.025,
    speed_threshold_mps=0.350,
)
STATIONARY_DOUBLE_PIN_REFERENCE_FRACTION = 0.1
SYNTHETIC_ROLLOUT_START_FRAME = 1
DEFAULT_SYNTHETIC_BATCH_FRACTION = 0.25
DEFAULT_SYNTHETIC_RESERVED_ROWS = 0
DEFAULT_VIRTUAL_RESERVED_ROWS = 0
DEBUG_ROLLOUT_REQUEST_NAME = "export_last_rollout.request.json"
DEBUG_ROLLOUT_ARTIFACT_NAME = "last_batch_rollout.json"
DEBUG_ROLLOUT_CHECK_INTERVAL_S = 0.5
TRAIN_PAUSE_REQUEST_NAME = "pause.request"
TRAIN_PAUSED_STATE_NAME = "paused.state.json"
TRAIN_PAUSE_CHECK_INTERVAL_S = 0.5
ENVELOPE_TERM_NAMES = ("linear_slide_weighted", "angular_slide_weighted", "foot_height_weighted")
ALTERNATING_FEET_TERM_NAMES = (
    "alternating_feet_weighted",
    "both_feet_moving_rate",
    "both_feet_overlap_mps",
    "root_still_gate",
)
ALTERNATING_FEET_LOSS_TERM_NAMES = ("alternating_feet_weighted",)
FOOT_LIFT_SLIDE_TERM_NAMES = (
    "foot_lift_slide_weighted",
    "foot_lift_slide_violation_rate",
    "foot_lift_slide_excess_mps",
    "foot_lift_moving_rate",
    "foot_lift_moving_clearance_m",
    "foot_lift_allowed_speed_mps",
    "foot_lift_root_still_gate",
    "grounded_foot_slide_weighted",
    "grounded_foot_slide_rate",
    "grounded_foot_slide_mps",
    "grounded_foot_clearance_m",
    "foot_speed_deadzone_weighted",
    "foot_speed_deadzone_rate",
    "foot_speed_deadzone_mps",
    "foot_speed_overspeed_weighted",
    "foot_speed_overspeed_rate",
    "foot_speed_overspeed_mps",
    "terminal_foot_stillness_weighted",
    "terminal_foot_horizontal_mps",
    "terminal_foot_vertical_mps",
    "terminal_foot_stillness_rate",
)
FOOT_LIFT_SLIDE_LOSS_TERM_NAMES = (
    "foot_lift_slide_weighted",
    "grounded_foot_slide_weighted",
    "foot_speed_deadzone_weighted",
    "foot_speed_overspeed_weighted",
    "terminal_foot_stillness_weighted",
)
IK_LOWER_LENGTH_TERM_NAMES = (
    "ik_lower_length_weighted",
    "leg_lower_length_excess_m",
    "leg_lower_length_bad_rate",
    "leg_lower_length_max_excess_m",
    "arm_lower_length_excess_m",
    "arm_lower_length_bad_rate",
)
IK_LOWER_LENGTH_LOSS_TERM_NAMES = ("ik_lower_length_weighted",)
FOOT_HEIGHT_LOSS_SCALE = 0.7
BOTH_FEET_MOVING_THRESHOLD_MPS = 0.03
FOOT_LIFT_FULL_HEIGHT_M = 0.04
FOOT_LIFT_FULL_SPEED_MPS = 0.70
GROUNDED_FOOT_SLIDE_LOSS_SCALE = 10.0
GROUNDED_FOOT_SLIDE_RELEASE_M = 0.025
FOOT_SPEED_DEADZONE_LOW_MPS = 0.03
FOOT_SPEED_DEADZONE_FAST_MPS = 0.35
FOOT_SPEED_DEADZONE_LOSS_SCALE = 4.0
FOOT_SPEED_OVERSPEED_MAX_MPS = 0.535
FOOT_SPEED_OVERSPEED_LOSS_SCALE = 1.0
TERMINAL_FOOT_STILLNESS_FRAMES = 7
TERMINAL_FOOT_STILLNESS_LOSS_SCALE = 20.0
IK_LOWER_LENGTH_LOSS_WEIGHT = 0.0
IK_LOWER_LENGTH_LEG_TOLERANCE_M = 0.005
IK_LOWER_LENGTH_ARM_TOLERANCE_M = 0.020
DUPLICATE_ROLLOUT_INIT_CONTEXT = True
IDENTITY_TERM_NAME = "identity_output"
IDENTITY_MAXABS_TERM_NAME = "identity_output_maxabs"
IDENTITY_WORLD_POS_TERM_NAME = "identity_world_pos"
IDENTITY_PELVIS_POS_TERM_NAME = "identity_pelvis_pos"
AE_POSE_TERM_NAME = "ae_p_score"
AE_VELOCITY_TERM_NAME = "ae_v_score"
PRIMARY_LOSS_MODE_AE1 = "ae1"
PRIMARY_LOSS_MODE_GT_MSE = "gt_mse"
PRIMARY_LOSS_MODE_AE1_GT_MSE = "ae1_gt_mse"
PRIMARY_LOSS_MODE_VALUES = (PRIMARY_LOSS_MODE_AE1, PRIMARY_LOSS_MODE_GT_MSE, PRIMARY_LOSS_MODE_AE1_GT_MSE)
PRIMARY_LOSS_MODE = PRIMARY_LOSS_MODE_AE1
DEFAULT_PRIMARY_LOSS_MODE = PRIMARY_LOSS_MODE
GT_MSE_LOSS_SCALE = 0.03
DEFAULT_GT_MSE_LOSS_SCALE = GT_MSE_LOSS_SCALE
GT_MSE_WEIGHTED_TERM_NAME = "gt_mse_weighted"
GT_MSE_RAW_TERM_NAME = "gt_mse_raw"
GT_MSE_POS_TERM_NAME = "gt_mse_pos"
GT_MSE_ROT_TERM_NAME = "gt_mse_rot"
GT_MSE_LINVEL_TERM_NAME = "gt_mse_linvel"
GT_MSE_ANGVEL_TERM_NAME = "gt_mse_angvel"
GT_MSE_ROW_SCOPE_ALL = "all"
GT_MSE_ROW_SCOPE_DEDICATED_PERIODIC = "dedicated_periodic"
GT_MSE_ROW_SCOPE_VALUES = (GT_MSE_ROW_SCOPE_ALL, GT_MSE_ROW_SCOPE_DEDICATED_PERIODIC)
GT_MSE_ROW_SCOPE = GT_MSE_ROW_SCOPE_ALL
AE5_SCORE_TERM_NAME = "ae5_score"
AE5_WEIGHTED_TERM_NAME = "ae5_score_weighted"
AE5_ACTIVE_RATE_TERM_NAME = "ae5_active_rate"


def primary_loss_uses_ae1() -> bool:
    return PRIMARY_LOSS_MODE in (PRIMARY_LOSS_MODE_AE1, PRIMARY_LOSS_MODE_AE1_GT_MSE)


def primary_loss_uses_gt_mse() -> bool:
    return PRIMARY_LOSS_MODE in (PRIMARY_LOSS_MODE_GT_MSE, PRIMARY_LOSS_MODE_AE1_GT_MSE)
AE6_CONTACT_SCORE_TERM_NAME = "ae6_contact_score"
AE6_CONTACT_WEIGHTED_TERM_NAME = "ae6_contact_score_weighted"
AE6_CONTACT_MAE_TERM_NAME = "ae6_contact_mae"
AE6_CONTACT_ACC_TERM_NAME = "ae6_contact_binary_acc"
AE6_ROW_SCOPE = GT_MSE_ROW_SCOPE_ALL

BATCH_SIZE = 4096
SMALL_CUDA_K64_BATCH_SIZE = 3328
ROLLOUT_SCHEDULE = (1, 2, 8, 16, 32, 64)
ROLLOUT_STAGE_STEPS = (3000, 1000, 1500, 1500, 2500, 2500)
ROLLOUT_K = 64
MIXED_ROLLOUT_AT_MAX = True
USE_CUDA_GRAPH = True
CUDA_GRAPH_WARMUP_STEPS = 1
LEARNING_RATE = 1e-4
STAGE_LEARNING_RATES = {
    1: 1e-4,
    2: 8e-5,
    8: 5e-5,
    16: 2e-5,
    32: 7.5e-6,
    64: 7.5e-6,
}
DEFAULT_TRAINER_BATCH_SIZE = BATCH_SIZE
DEFAULT_IK_LOWER_LENGTH_LOSS_WEIGHT = IK_LOWER_LENGTH_LOSS_WEIGHT
DEFAULT_ROLLOUT_SCHEDULE = ROLLOUT_SCHEDULE
DEFAULT_ROLLOUT_STAGE_STEPS = ROLLOUT_STAGE_STEPS
DEFAULT_ROLLOUT_K = ROLLOUT_K
DEFAULT_MIXED_ROLLOUT_AT_MAX = MIXED_ROLLOUT_AT_MAX
DEFAULT_STAGE_LEARNING_RATES = dict(STAGE_LEARNING_RATES)
LOG_EVERY = 250
DEFAULT_LOG_EVERY = LOG_EVERY
LOSS_REFRESH_RATE = 1
DEFAULT_LOSS_REFRESH_RATE = LOSS_REFRESH_RATE
VALIDATION_ROWS = 256
RUN_FK_DIAGNOSTIC = False
AE_SCORE_OUTPUT_ONLY = True
NAN_METRIC = float("nan")
POSE_NOISE_POS_SIGMA_M_AT_1 = 0.12
POSE_NOISE_ROT_SIGMA_DEG_AT_1 = 25.0
POSE_NOISE_SCALAR_SIGMA_AT_1 = 1.0
INIT_NOISE_FIXED_POSITION_AMOUNT = 0.40
INIT_NOISE_FIXED_ROTATION_AMOUNT = 1.00
INIT_NOISE_FIXED_GLOBAL_YAW_DEG = 66.0
DEFAULT_INIT_NOISE_AMOUNT = 0.0
DEFAULT_INIT_NOISE_CLEAN_FRACTION = 1.0
RL_GRAD_CLIP_NORM = 1.0
ZERO_LOSS_STOP_THRESHOLD = 0.0
PRETRAIN_RELEASE_EVENT: threading.Event | None = None
PRETRAIN_CANCEL_EVENT: threading.Event | None = None
PRETRAIN_READY_CALLBACK = None
PRETRAIN_ARM_STARTED_AT: float | None = None
PRETRAIN_LOSS_PROFILE_EMITTED = False
PRETRAIN_DETAILED_LOSS_PROFILE = False
ACTIVE_STEPPER_LOCK = threading.Lock()
ACTIVE_PURE_AE_STEPPER = None
ACTIVE_CHECKPOINT_CONTEXT: dict[str, object] | None = None
TRAIN_STOP_REQUEST_EVENT = threading.Event()
TRAIN_RESUME_EVENT = threading.Event()
TRAIN_HOT_STOP_REQUEST_EVENT = threading.Event()
TRAIN_HOT_STOPPED_EVENT = threading.Event()

MUTABLE_LOSS_WEIGHT_FIELDS = (
    "ae_loss_weight",
    "identity_loss_weight",
    "identity_maxabs_weight",
    "identity_world_pos_weight",
    "identity_pelvis_pos_weight",
    "linear_slide_weight",
    "angular_slide_weight",
    "foot_height_weight",
    "alternating_feet_weight",
    "foot_lift_slide_weight",
    "ik_lower_length_loss_weight",
    "ae4_loss_weight",
    "ae4_bank_pin_loss_weight",
    "pin_logit_gap_loss_weight",
    "inertia_acceleration_loss_weight",
    "leg_crossing_capsule_loss_weight",
    "pinned_foot_height_weight",
    "idle_foot_flatness_weight",
    *RLLossConfig._weight_fields(),
)


class PretrainCancelled(RuntimeError):
    pass


def emit_pretrain_arm_timing(phase: str, phase_started: float, **extra: object) -> float:
    if PRETRAIN_RELEASE_EVENT is None or PRETRAIN_ARM_STARTED_AT is None:
        return time.perf_counter()
    now = time.perf_counter()
    emit_pretrain_arm_delta(phase, now - phase_started, now=now, **extra)
    return now


def emit_pretrain_arm_delta(phase: str, delta_s: float, now: float | None = None, **extra: object) -> None:
    if PRETRAIN_RELEASE_EVENT is None or PRETRAIN_ARM_STARTED_AT is None:
        return
    if now is None:
        now = time.perf_counter()
    tokens = [
        f"phase={str(phase).replace(' ', '_')}",
        f"delta_s={float(delta_s):.3f}",
        f"elapsed_s={now - PRETRAIN_ARM_STARTED_AT:.3f}",
    ]
    for key, value in extra.items():
        safe_key = str(key).replace(" ", "_")
        safe_value = str(value).replace(" ", "_").replace("\\", "/")
        tokens.append(f"{safe_key}={safe_value}")
    print("TRAINER_WORKER_ARM_TIMING " + " ".join(tokens), flush=True)


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


@dataclass(frozen=True)
class StartPool:
    clip_ids: torch.Tensor
    starts: torch.Tensor

    @property
    def row_count(self) -> int:
        return int(self.starts.numel())


@dataclass(frozen=True)
class SimpleClipMeta:
    path: Path
    cyclic_animation: bool
    cyclic_period: int
    T: int
    body_names: list[str]
    parents_body_list: list[int]
    fps: float


@dataclass(frozen=True)
class ControllerLossResult:
    total: torch.Tensor
    terms: dict[str, torch.Tensor]
    row_losses: torch.Tensor | None = None


def detach_loss_result(result: ControllerLossResult) -> ControllerLossResult:
    return ControllerLossResult(
        total=result.total.detach(),
        terms={key: value.detach() for key, value in result.terms.items()},
        row_losses=None if result.row_losses is None else result.row_losses.detach(),
    )


def maybe_clip_rl_gradients(model: torch.nn.Module, rl_cfg: RLLossConfig) -> None:
    if rl_cfg.enabled:
        torch.nn.utils.clip_grad_norm_(model.parameters(), float(RL_GRAD_CLIP_NORM))


def envelope_loss_enabled(linear_weight: float, angular_weight: float, foot_height_weight: float = 0.0) -> bool:
    return float(linear_weight) != 0.0 or float(angular_weight) != 0.0 or float(foot_height_weight) != 0.0


def alternating_feet_loss_enabled(weight: float) -> bool:
    return float(weight) != 0.0


def foot_lift_slide_loss_enabled(weight: float) -> bool:
    return float(weight) != 0.0


def ik_lower_length_loss_enabled() -> bool:
    return bool(float(IK_LOWER_LENGTH_LOSS_WEIGHT) != 0.0)


def wake_on_zero_loss(run_id: str, step: int, loss: float) -> None:
    print(f"\a\a\aZERO_LOSS_STOP run={run_id} step={step} loss={loss:.6g}", flush=True)
    try:
        import winsound

        for _ in range(3):
            winsound.Beep(880, 350)
            winsound.Beep(1175, 350)
    except Exception:
        pass


def wait_for_prearmed_launch() -> bool:
    global PRETRAIN_ARM_STARTED_AT, PRETRAIN_CANCEL_EVENT, PRETRAIN_READY_CALLBACK, PRETRAIN_RELEASE_EVENT

    event = PRETRAIN_RELEASE_EVENT
    if event is None:
        return False
    cancel_event = PRETRAIN_CANCEL_EVENT
    callback = PRETRAIN_READY_CALLBACK
    if callback is not None:
        callback()
    PRETRAIN_ARM_STARTED_AT = None
    while not event.wait(0.05):
        if cancel_event is not None and cancel_event.is_set():
            PRETRAIN_RELEASE_EVENT = None
            PRETRAIN_CANCEL_EVENT = None
            PRETRAIN_READY_CALLBACK = None
            raise PretrainCancelled()
    PRETRAIN_RELEASE_EVENT = None
    PRETRAIN_CANCEL_EVENT = None
    PRETRAIN_READY_CALLBACK = None
    return True


def reset_training_globals() -> None:
    global AE6_ROW_SCOPE, AE_FOOT_LOCATION_MULTIPLIER, AE_FOOT_ROTATION_MULTIPLIER, AE_TERMINAL_ONLY, BATCH_SIZE, FAKE_GRAVITY_ENABLED, FAKE_GRAVITY_MPS2, FAKE_GRAVITY_USES_HEIGHT_GATE, FOOT_ROLL_HEIGHT_PIN_GATE, FOOT_ROLL_INTEGRATION_STEPS, FOOT_ROLL_PIN_MODE, FOOT_UNPIN_PENALTY_WEIGHT, GT_MSE_LOSS_SCALE, GT_MSE_ROW_SCOPE, IK_LOWER_LENGTH_LOSS_WEIGHT, LEG_CROSSING_CAPSULE_LOSS_WEIGHT, LOG_EVERY, LOSS_REFRESH_RATE, MIXED_ROLLOUT_AT_MAX, PINNED_FOOT_INTENT_PENALTY_WEIGHT, PRIMARY_LOSS_MODE, ROLLOUT_K, ROLLOUT_SCHEDULE, ROLLOUT_STAGE_STEPS, STAGE_LEARNING_RATES
    global FOOT_ROLL_NEAR_FLOOR_PIN_FADE_HEIGHT_M, FOOT_ROLL_NEAR_FLOOR_PIN_FULL_HEIGHT_M, FOOT_ROLL_NEAR_FLOOR_PIN_MIN_PROB

    AE_FOOT_LOCATION_MULTIPLIER = float(DEFAULT_AE_FOOT_LOCATION_MULTIPLIER)
    AE_FOOT_ROTATION_MULTIPLIER = float(DEFAULT_AE_FOOT_ROTATION_MULTIPLIER)
    AE_TERMINAL_ONLY = bool(DEFAULT_AE_TERMINAL_ONLY)
    FOOT_ROLL_PIN_MODE = str(DEFAULT_FOOT_ROLL_PIN_MODE)
    FOOT_ROLL_INTEGRATION_STEPS = int(DEFAULT_FOOT_ROLL_INTEGRATION_STEPS)
    FOOT_ROLL_HEIGHT_PIN_GATE = bool(DEFAULT_FOOT_ROLL_HEIGHT_PIN_GATE)
    FOOT_ROLL_NEAR_FLOOR_PIN_FULL_HEIGHT_M = float(DEFAULT_FOOT_ROLL_NEAR_FLOOR_PIN_FULL_HEIGHT_M)
    FOOT_ROLL_NEAR_FLOOR_PIN_FADE_HEIGHT_M = float(DEFAULT_FOOT_ROLL_NEAR_FLOOR_PIN_FADE_HEIGHT_M)
    FOOT_ROLL_NEAR_FLOOR_PIN_MIN_PROB = float(DEFAULT_FOOT_ROLL_NEAR_FLOOR_PIN_MIN_PROB)
    FAKE_GRAVITY_ENABLED = float(DEFAULT_FAKE_GRAVITY_ENABLED)
    FAKE_GRAVITY_MPS2 = float(DEFAULT_FAKE_GRAVITY_MPS2)
    FAKE_GRAVITY_USES_HEIGHT_GATE = bool(DEFAULT_FAKE_GRAVITY_USES_HEIGHT_GATE)
    FOOT_UNPIN_PENALTY_WEIGHT = float(DEFAULT_FOOT_UNPIN_PENALTY_WEIGHT)
    PINNED_FOOT_INTENT_PENALTY_WEIGHT = float(DEFAULT_PINNED_FOOT_INTENT_PENALTY_WEIGHT)
    LEG_CROSSING_CAPSULE_LOSS_WEIGHT = float(DEFAULT_LEG_CROSSING_CAPSULE_LOSS_WEIGHT)
    PRIMARY_LOSS_MODE = str(DEFAULT_PRIMARY_LOSS_MODE)
    GT_MSE_LOSS_SCALE = float(DEFAULT_GT_MSE_LOSS_SCALE)
    GT_MSE_ROW_SCOPE = str(GT_MSE_ROW_SCOPE_ALL)
    AE6_ROW_SCOPE = str(GT_MSE_ROW_SCOPE_ALL)
    BATCH_SIZE = int(DEFAULT_TRAINER_BATCH_SIZE)
    IK_LOWER_LENGTH_LOSS_WEIGHT = float(DEFAULT_IK_LOWER_LENGTH_LOSS_WEIGHT)
    LOG_EVERY = int(DEFAULT_LOG_EVERY)
    LOSS_REFRESH_RATE = int(DEFAULT_LOSS_REFRESH_RATE)
    MIXED_ROLLOUT_AT_MAX = bool(DEFAULT_MIXED_ROLLOUT_AT_MAX)
    ROLLOUT_K = int(DEFAULT_ROLLOUT_K)
    ROLLOUT_SCHEDULE = tuple(DEFAULT_ROLLOUT_SCHEDULE)
    ROLLOUT_STAGE_STEPS = tuple(DEFAULT_ROLLOUT_STAGE_STEPS)
    STAGE_LEARNING_RATES = dict(DEFAULT_STAGE_LEARNING_RATES)


def normalized_foot_roll_pin_mode(value: object) -> str | None:
    text = str(value).strip().lower()
    aliases = {
        "legacy_lowest": FOOT_ROLL_PIN_MODE_LEGACY_LOGIT_SELECTED,
        "legacy_logit_selected": FOOT_ROLL_PIN_MODE_LEGACY_LOGIT_SELECTED,
        "continuous_sigmoid": FOOT_ROLL_PIN_MODE_CONTINUOUS_SIGMOID,
    }
    mode = aliases.get(text)
    return mode if mode in FOOT_ROLL_PIN_MODE_VALUES else None


def apply_foot_roll_runtime_policy_from_checkpoint(checkpoint: dict | None) -> None:
    """Reset and restore checkpoint-specific foot projection behavior.

    Old walk checkpoints predate the explicit ``pin_mode`` field. Their saved
    rule text is the compatibility marker for the hard logit-selected path.
    Newer run checkpoints store ``continuous_sigmoid`` explicitly.
    """

    global FOOT_ROLL_HEIGHT_PIN_GATE, FOOT_ROLL_INTEGRATION_STEPS, FOOT_ROLL_PIN_MODE
    global FOOT_ROLL_NEAR_FLOOR_PIN_FADE_HEIGHT_M, FOOT_ROLL_NEAR_FLOOR_PIN_FULL_HEIGHT_M, FOOT_ROLL_NEAR_FLOOR_PIN_MIN_PROB

    FOOT_ROLL_HEIGHT_PIN_GATE = bool(DEFAULT_FOOT_ROLL_HEIGHT_PIN_GATE)
    FOOT_ROLL_INTEGRATION_STEPS = int(DEFAULT_FOOT_ROLL_INTEGRATION_STEPS)
    FOOT_ROLL_PIN_MODE = str(DEFAULT_FOOT_ROLL_PIN_MODE)
    FOOT_ROLL_NEAR_FLOOR_PIN_FULL_HEIGHT_M = float(DEFAULT_FOOT_ROLL_NEAR_FLOOR_PIN_FULL_HEIGHT_M)
    FOOT_ROLL_NEAR_FLOOR_PIN_FADE_HEIGHT_M = float(DEFAULT_FOOT_ROLL_NEAR_FLOOR_PIN_FADE_HEIGHT_M)
    FOOT_ROLL_NEAR_FLOOR_PIN_MIN_PROB = float(DEFAULT_FOOT_ROLL_NEAR_FLOOR_PIN_MIN_PROB)

    metadata = checkpoint.get("metadata", {}) if isinstance(checkpoint, dict) else {}
    policy = metadata.get("policy", {}) if isinstance(metadata, dict) else {}
    foot_policy = policy.get("foot_roll_output_projection", {}) if isinstance(policy, dict) else {}
    if not isinstance(foot_policy, dict):
        return

    if "height_pin_gate_enabled" in foot_policy:
        FOOT_ROLL_HEIGHT_PIN_GATE = bool(foot_policy["height_pin_gate_enabled"])
    if "integration_steps" in foot_policy:
        try:
            FOOT_ROLL_INTEGRATION_STEPS = max(1, int(foot_policy["integration_steps"]))
        except (TypeError, ValueError):
            pass

    mode = normalized_foot_roll_pin_mode(foot_policy.get("pin_mode", ""))
    if mode is None:
        rule = str(foot_policy.get("rule", "")).strip().lower()
        if (
            "logit-selected" in rule
            or "lowest-logit" in rule
            or "pin/project regardless" in rule
        ):
            mode = FOOT_ROLL_PIN_MODE_LEGACY_LOGIT_SELECTED
    if mode is not None:
        FOOT_ROLL_PIN_MODE = mode

    near_floor = foot_policy.get("near_floor_forced_pin", {})
    if isinstance(near_floor, dict):
        try:
            if "full_height_m" in near_floor:
                FOOT_ROLL_NEAR_FLOOR_PIN_FULL_HEIGHT_M = max(0.0, float(near_floor["full_height_m"]))
            if "fade_height_m" in near_floor:
                FOOT_ROLL_NEAR_FLOOR_PIN_FADE_HEIGHT_M = max(
                    FOOT_ROLL_NEAR_FLOOR_PIN_FULL_HEIGHT_M,
                    float(near_floor["fade_height_m"]),
                )
            if "minimum_pin_probability" in near_floor:
                FOOT_ROLL_NEAR_FLOOR_PIN_MIN_PROB = min(
                    1.0,
                    max(0.0, float(near_floor["minimum_pin_probability"])),
                )
        except (TypeError, ValueError):
            pass


def apply_training_args(args: argparse.Namespace) -> None:
    global AE6_ROW_SCOPE, AE_FOOT_LOCATION_MULTIPLIER, AE_FOOT_ROTATION_MULTIPLIER, AE_TERMINAL_ONLY, BATCH_SIZE, FAKE_GRAVITY_ENABLED, FAKE_GRAVITY_MPS2, FAKE_GRAVITY_USES_HEIGHT_GATE, FOOT_ROLL_HEIGHT_PIN_GATE, FOOT_ROLL_INTEGRATION_STEPS, FOOT_ROLL_PIN_MODE, FOOT_UNPIN_PENALTY_WEIGHT, GT_MSE_LOSS_SCALE, GT_MSE_ROW_SCOPE, IK_LOWER_LENGTH_LOSS_WEIGHT, LEG_CROSSING_CAPSULE_LOSS_WEIGHT, LOG_EVERY, LOSS_REFRESH_RATE, MIXED_ROLLOUT_AT_MAX, PINNED_FOOT_INTENT_PENALTY_WEIGHT, PRIMARY_LOSS_MODE, ROLLOUT_K, ROLLOUT_SCHEDULE, ROLLOUT_STAGE_STEPS, STAGE_LEARNING_RATES

    reset_training_globals()
    AE_FOOT_LOCATION_MULTIPLIER = max(
        0.0,
        float(getattr(args, "ae_foot_location_multiplier", DEFAULT_AE_FOOT_LOCATION_MULTIPLIER)),
    )
    AE_FOOT_ROTATION_MULTIPLIER = max(
        0.0,
        float(getattr(args, "ae_foot_rotation_multiplier", DEFAULT_AE_FOOT_ROTATION_MULTIPLIER)),
    )
    AE_TERMINAL_ONLY = bool(getattr(args, "ae_terminal_only", DEFAULT_AE_TERMINAL_ONLY))
    FOOT_ROLL_PIN_MODE = str(DEFAULT_FOOT_ROLL_PIN_MODE)
    FOOT_ROLL_INTEGRATION_STEPS = max(
        1,
        int(getattr(args, "foot_roll_integration_steps", DEFAULT_FOOT_ROLL_INTEGRATION_STEPS)),
    )
    FOOT_ROLL_HEIGHT_PIN_GATE = bool(
        getattr(args, "foot_roll_height_pin_gate", DEFAULT_FOOT_ROLL_HEIGHT_PIN_GATE)
    )
    FAKE_GRAVITY_ENABLED = min(1.0, max(0.0, float(getattr(args, "fake_gravity", DEFAULT_FAKE_GRAVITY_ENABLED))))
    FAKE_GRAVITY_MPS2 = max(0.0, float(getattr(args, "fake_gravity_mps2", DEFAULT_FAKE_GRAVITY_MPS2)))
    FAKE_GRAVITY_USES_HEIGHT_GATE = bool(
        getattr(args, "fake_gravity_uses_height_gate", DEFAULT_FAKE_GRAVITY_USES_HEIGHT_GATE)
    )
    FOOT_UNPIN_PENALTY_WEIGHT = max(
        0.0,
        float(getattr(args, "foot_unpin_penalty_weight", DEFAULT_FOOT_UNPIN_PENALTY_WEIGHT)),
    )
    PINNED_FOOT_INTENT_PENALTY_WEIGHT = max(
        0.0,
        float(getattr(args, "pinned_foot_intent_penalty_weight", DEFAULT_PINNED_FOOT_INTENT_PENALTY_WEIGHT)),
    )
    LEG_CROSSING_CAPSULE_LOSS_WEIGHT = max(
        0.0,
        float(
            getattr(
                args,
                "leg_crossing_capsule_loss_weight",
                DEFAULT_LEG_CROSSING_CAPSULE_LOSS_WEIGHT,
            )
        ),
    )
    requested_primary_loss_mode = str(getattr(args, "primary_loss_mode", DEFAULT_PRIMARY_LOSS_MODE))
    if requested_primary_loss_mode not in PRIMARY_LOSS_MODE_VALUES:
        raise ValueError(
            f"Unknown primary loss mode {requested_primary_loss_mode!r}; expected one of {PRIMARY_LOSS_MODE_VALUES}"
        )
    PRIMARY_LOSS_MODE = requested_primary_loss_mode
    GT_MSE_LOSS_SCALE = max(0.0, float(getattr(args, "gt_mse_loss_scale", DEFAULT_GT_MSE_LOSS_SCALE)))
    requested_gt_mse_row_scope = str(getattr(args, "gt_mse_row_scope", GT_MSE_ROW_SCOPE_ALL))
    if requested_gt_mse_row_scope not in GT_MSE_ROW_SCOPE_VALUES:
        raise ValueError(
            f"Unknown GT MSE row scope {requested_gt_mse_row_scope!r}; expected one of {GT_MSE_ROW_SCOPE_VALUES}"
        )
    GT_MSE_ROW_SCOPE = requested_gt_mse_row_scope
    requested_ae6_row_scope = str(getattr(args, "ae6_row_scope", GT_MSE_ROW_SCOPE_ALL))
    if requested_ae6_row_scope not in GT_MSE_ROW_SCOPE_VALUES:
        raise ValueError(
            f"Unknown AE6 row scope {requested_ae6_row_scope!r}; expected one of {GT_MSE_ROW_SCOPE_VALUES}"
        )
    AE6_ROW_SCOPE = requested_ae6_row_scope
    if getattr(args, "batch_size", None) is not None:
        BATCH_SIZE = max(1, int(args.batch_size))
    if args.rollout_schedule is not None:
        ROLLOUT_SCHEDULE = tuple(max(1, int(k)) for k in args.rollout_schedule)
        if args.rollout_k is None:
            ROLLOUT_K = int(ROLLOUT_SCHEDULE[-1])
    if args.rollout_stage_steps is not None:
        ROLLOUT_STAGE_STEPS = tuple(max(1, int(n)) for n in args.rollout_stage_steps)
    if args.rollout_k is not None:
        ROLLOUT_K = max(1, int(args.rollout_k))
    if len(ROLLOUT_SCHEDULE) != len(ROLLOUT_STAGE_STEPS):
        raise ValueError(
            f"rollout schedule length {len(ROLLOUT_SCHEDULE)} must match stage steps length {len(ROLLOUT_STAGE_STEPS)}"
        )
    if int(ROLLOUT_K) not in {int(k) for k in ROLLOUT_SCHEDULE}:
        raise ValueError(f"rollout_k {ROLLOUT_K} must appear in rollout_schedule {ROLLOUT_SCHEDULE}")
    if args.mixed_rollout_at_max is not None:
        MIXED_ROLLOUT_AT_MAX = bool(args.mixed_rollout_at_max)
    if args.stage_learning_rate is not None:
        STAGE_LEARNING_RATES = {int(k): float(args.stage_learning_rate) for k in ROLLOUT_SCHEDULE}
    elif args.rollout_schedule is not None:
        STAGE_LEARNING_RATES = default_stage_learning_rates_for_schedule(ROLLOUT_SCHEDULE)
    if getattr(args, "stage_learning_rate_map", None):
        STAGE_LEARNING_RATES = apply_stage_learning_rate_overrides(
            STAGE_LEARNING_RATES,
            args.stage_learning_rate_map,
            ROLLOUT_SCHEDULE,
        )
    if args.log_every is not None:
        LOG_EVERY = max(1, int(args.log_every))
    if getattr(args, "loss_refresh_rate", None) is not None:
        LOSS_REFRESH_RATE = max(1, int(args.loss_refresh_rate))
    IK_LOWER_LENGTH_LOSS_WEIGHT = float(args.ik_lower_length_loss_weight)


def require_slide_tentative_disabled(args: argparse.Namespace) -> None:
    value = float(getattr(args, "slide_tentative_loss_weight", 0.0) or 0.0)
    if value != 0.0:
        raise ValueError(
            "slide_tentative_loss_weight has been removed from IK training; "
            "leave it at 0.0 and use AE/pose-bank losses instead."
        )


def loss_weight_values_from_args(args: argparse.Namespace) -> dict[str, float]:
    ae4_path = resolve_ae4_checkpoint_arg(args)
    return {
        "ae_loss_weight": float(args.ae_loss_weight),
        "identity_loss_weight": float(args.identity_output_loss_weight),
        "identity_maxabs_weight": float(args.identity_output_maxabs_loss_weight),
        "identity_world_pos_weight": float(args.identity_world_pos_loss_weight),
        "identity_pelvis_pos_weight": float(args.identity_pelvis_pos_loss_weight),
        "linear_slide_weight": float(args.linear_slide_loss_weight),
        "angular_slide_weight": float(args.angular_slide_loss_weight),
        "foot_height_weight": float(args.foot_height_loss_weight),
        "alternating_feet_weight": float(args.alternating_feet_loss_weight),
        "foot_lift_slide_weight": float(args.foot_lift_slide_loss_weight),
        "ik_lower_length_loss_weight": float(args.ik_lower_length_loss_weight),
        "pinned_foot_height_weight": float(args.pinned_foot_height_loss_weight),
        "idle_foot_flatness_weight": float(args.idle_foot_flatness_loss_weight),
        "slide_tentative_loss_weight": float(args.slide_tentative_loss_weight),
        "pin_logit_gap_loss_weight": float(args.pin_logit_gap_loss_weight),
        "inertia_acceleration_loss_weight": float(args.inertia_acceleration_loss_weight),
        "root_accel_pin_loss_ratio": float(
            getattr(args, "root_accel_pin_loss_ratio", DEFAULT_ROOT_ACCEL_PIN_LOSS_RATIO)
        ),
        "leg_crossing_capsule_loss_weight": float(
            getattr(args, "leg_crossing_capsule_loss_weight", DEFAULT_LEG_CROSSING_CAPSULE_LOSS_WEIGHT)
        ),
        "ae4_loss_weight": float(
            args.ae4_loss_weight
            if args.ae4_loss_weight is not None
            else (DEFAULT_AE4_LOSS_WEIGHT if ae4_path is not None else 0.0)
        ),
        "ae4_bank_pin_loss_weight": float(args.ae4_bank_pin_loss_weight),
        "ae5_loss_weight": float(getattr(args, "ae5_loss_weight", 0.0)),
        "pelvis_root_horizontal_weight": float(args.pelvis_root_horizontal_loss_weight),
        "pelvis_root_rotation_weight": float(args.pelvis_root_rotation_loss_weight),
        "end_effector_location_weight": float(args.end_effector_location_loss_weight),
        "end_effector_rotation_weight": float(args.end_effector_rotation_loss_weight),
        "end_effector_velocity_weight": float(args.end_effector_velocity_loss_weight),
        "end_effector_angular_velocity_weight": float(args.end_effector_angular_velocity_loss_weight),
        "pelvis_velocity_weight": float(args.pelvis_velocity_loss_weight),
        "pelvis_angular_velocity_weight": float(args.pelvis_angular_velocity_loss_weight),
        "core_angular_velocity_weight": float(args.core_angular_velocity_loss_weight),
    }


def loss_weight_values_from_argv(argv: list[str]) -> dict[str, float]:
    args, _unknown = warm_arg_parser().parse_known_args(argv)
    return loss_weight_values_from_args(args)


def weight_scale(
    weight_tensors: dict[str, torch.Tensor] | None,
    key: str,
    fallback: float,
    dtype: torch.dtype | None = None,
) -> float | torch.Tensor:
    if weight_tensors is not None and key in weight_tensors:
        tensor = weight_tensors[key]
        return tensor.to(dtype=dtype) if dtype is not None and tensor.dtype != dtype else tensor
    return float(fallback)


def make_loss_weight_tensors(values: dict[str, float], device: torch.device) -> dict[str, torch.Tensor]:
    return {
        key: torch.tensor(float(values.get(key, 0.0)), dtype=torch.float32, device=device)
        for key in MUTABLE_LOSS_WEIGHT_FIELDS
    }


def loss_weight_shape_compatible(current: dict[str, float], updates: dict[str, float]) -> tuple[bool, str]:
    for key in MUTABLE_LOSS_WEIGHT_FIELDS:
        old_active = float(current.get(key, 0.0)) != 0.0
        new_active = float(updates.get(key, current.get(key, 0.0))) != 0.0
        if old_active != new_active:
            return False, f"{key} crossed zero"
    return True, ""


def set_active_stepper(stepper: object | None) -> None:
    global ACTIVE_PURE_AE_STEPPER
    with ACTIVE_STEPPER_LOCK:
        ACTIVE_PURE_AE_STEPPER = stepper


def clear_active_stepper(stepper: object | None = None) -> None:
    global ACTIVE_PURE_AE_STEPPER
    with ACTIVE_STEPPER_LOCK:
        if stepper is None or ACTIVE_PURE_AE_STEPPER is stepper:
            ACTIVE_PURE_AE_STEPPER = None


def set_active_checkpoint_context(**context: object) -> None:
    global ACTIVE_CHECKPOINT_CONTEXT
    with ACTIVE_STEPPER_LOCK:
        ACTIVE_CHECKPOINT_CONTEXT = dict(context)


def update_active_checkpoint_context(**updates: object) -> None:
    with ACTIVE_STEPPER_LOCK:
        if ACTIVE_CHECKPOINT_CONTEXT is not None:
            ACTIVE_CHECKPOINT_CONTEXT.update(updates)


def clear_active_checkpoint_context() -> None:
    global ACTIVE_CHECKPOINT_CONTEXT
    with ACTIVE_STEPPER_LOCK:
        ACTIVE_CHECKPOINT_CONTEXT = None


def write_training_failure_marker(error_text: str, *, error_type: str | None = None) -> dict[str, object]:
    with ACTIVE_STEPPER_LOCK:
        ctx = dict(ACTIVE_CHECKPOINT_CONTEXT or {})
    run_dir_raw = ctx.get("run_dir")
    if run_dir_raw is None:
        return {"ok": False, "reason": "no_active_training_context"}
    run_dir = Path(run_dir_raw)
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "failed_at": datetime.now().isoformat(timespec="seconds"),
        "run_id": str(ctx.get("run_id", run_dir.name)),
        "step": int(ctx.get("step", -1)),
        "last_stage_k": int(ctx.get("last_stage_k", -1)),
        "last_loss": float(ctx.get("last_loss", float("nan"))),
        "error_type": str(error_type or "Exception"),
        "traceback": str(error_text),
    }
    failed_json = run_dir / "FAILED.json"
    failed_txt = run_dir / "FAILED.txt"
    failed_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    failed_txt.write_text(
        f"{payload['failed_at']} {payload['error_type']} step={payload['step']} loss={payload['last_loss']}\n\n"
        f"{payload['traceback']}\n",
        encoding="utf-8",
    )
    print(f"TRAINING_FAILED_MARKER {failed_txt}", flush=True)
    return {"ok": True, "path": str(failed_txt)}


def save_active_checkpoint_now(tag: str = "latest") -> dict[str, object]:
    with ACTIVE_STEPPER_LOCK:
        ctx = ACTIVE_CHECKPOINT_CONTEXT
        if ctx is None:
            return {"ok": False, "reason": "no_active_training_context"}
        path = save_controller_checkpoint(
            Path(ctx["run_dir"]),
            str(ctx["run_id"]),
            str(tag),
            ctx["model"],  # type: ignore[arg-type]
            ctx["optimizer"],  # type: ignore[arg-type]
            int(ctx["step"]),
            float(ctx["last_loss"]),
            int(ctx["last_stage_k"]),
            ctx["cfg"],  # type: ignore[arg-type]
            ctx["metadata"],  # type: ignore[arg-type]
            adaptive_sampler=ctx.get("adaptive_sampler"),  # type: ignore[arg-type]
        )
        return {"ok": True, "path": str(path), "step": int(ctx["step"])}


def update_active_loss_weights(updates: dict[str, float]) -> dict[str, object]:
    with ACTIVE_STEPPER_LOCK:
        stepper = ACTIVE_PURE_AE_STEPPER
        if stepper is None or not hasattr(stepper, "update_loss_weights"):
            return {"ok": False, "requires_rearm": True, "reason": "no active stepper"}
        return stepper.update_loss_weights(updates)  # type: ignore[no-any-return, attr-defined]


def update_active_loss_weights_from_argv(argv: list[str]) -> dict[str, object]:
    return update_active_loss_weights(loss_weight_values_from_argv(argv))


def request_training_pause() -> None:
    TRAIN_STOP_REQUEST_EVENT.set()
    TRAIN_RESUME_EVENT.clear()


def request_training_stop() -> None:
    TRAIN_HOT_STOP_REQUEST_EVENT.set()
    TRAIN_STOP_REQUEST_EVENT.clear()
    TRAIN_RESUME_EVENT.set()


def request_training_resume() -> None:
    TRAIN_STOP_REQUEST_EVENT.clear()
    TRAIN_HOT_STOPPED_EVENT.clear()
    TRAIN_RESUME_EVENT.set()


def is_training_paused() -> bool:
    return TRAIN_STOP_REQUEST_EVENT.is_set()


def is_training_hot_stopped() -> bool:
    return TRAIN_HOT_STOPPED_EVENT.is_set()


def clone_module_tensors(module: torch.nn.Module) -> dict[str, torch.Tensor]:
    return {key: value.detach().clone() for key, value in module.state_dict().items()}


def restore_module_tensors(module: torch.nn.Module, snapshot: dict[str, torch.Tensor]) -> None:
    current = module.state_dict()
    with torch.no_grad():
        for key, saved in snapshot.items():
            if key in current:
                current[key].copy_(saved)


def clone_optimizer_tensors(optimizer: torch.optim.Optimizer) -> dict[str, object]:
    groups = [{key: copy.deepcopy(value) for key, value in group.items() if key != "params"} for group in optimizer.param_groups]
    states: list[tuple[torch.nn.Parameter, dict[str, object]]] = []
    for param, state in optimizer.state.items():
        states.append(
            (
                param,
                {
                    key: value.detach().clone() if torch.is_tensor(value) else copy.deepcopy(value)
                    for key, value in state.items()
                },
            )
        )
    return {"groups": groups, "states": states}


def restore_optimizer_tensors(optimizer: torch.optim.Optimizer, snapshot: dict[str, object]) -> None:
    groups = snapshot.get("groups", [])
    if isinstance(groups, list):
        for group, saved_group in zip(optimizer.param_groups, groups):
            if isinstance(saved_group, dict):
                for key, value in saved_group.items():
                    group[key] = copy.deepcopy(value)
    states = snapshot.get("states", [])
    if isinstance(states, list):
        with torch.no_grad():
            for param, saved_state in states:
                if not isinstance(saved_state, dict):
                    continue
                state = optimizer.state[param]
                for key, value in saved_state.items():
                    if torch.is_tensor(value):
                        if key in state and torch.is_tensor(state[key]):
                            state[key].copy_(value)
                        else:
                            state[key] = value.detach().clone()
                    else:
                        state[key] = copy.deepcopy(value)


def clone_rng_state(device: torch.device) -> dict[str, torch.Tensor]:
    state = {"cpu": torch.get_rng_state().clone()}
    if device.type == "cuda":
        state["cuda"] = torch.cuda.get_rng_state(device).clone()
    return state


def restore_rng_state(snapshot: dict[str, torch.Tensor], device: torch.device) -> None:
    if "cpu" in snapshot:
        torch.set_rng_state(snapshot["cpu"])
    if device.type == "cuda" and "cuda" in snapshot:
        torch.cuda.set_rng_state(snapshot["cuda"], device)


def checkpoint_rng_state() -> dict[str, object]:
    state: dict[str, object] = {
        "schema_version": 1,
        "python_random": random.getstate(),
        "numpy_random": np.random.get_state(),
        "torch_cpu": torch.get_rng_state().detach().cpu().clone(),
    }
    if torch.cuda.is_available() and torch.cuda.is_initialized():
        state["torch_cuda_all"] = [rng.detach().cpu().clone() for rng in torch.cuda.get_rng_state_all()]
    return state


def restore_checkpoint_rng_state(snapshot: object, device: torch.device) -> bool:
    if not isinstance(snapshot, dict):
        return False
    restored = False
    python_state = snapshot.get("python_random")
    if python_state is not None:
        random.setstate(python_state)  # type: ignore[arg-type]
        restored = True
    numpy_state = snapshot.get("numpy_random")
    if numpy_state is not None:
        np.random.set_state(numpy_state)  # type: ignore[arg-type]
        restored = True
    torch_cpu = snapshot.get("torch_cpu")
    if torch.is_tensor(torch_cpu):
        torch.set_rng_state(torch_cpu.cpu())
        restored = True
    cuda_all = snapshot.get("torch_cuda_all")
    if torch.cuda.is_available() and isinstance(cuda_all, list) and cuda_all:
        cuda_states = [state.cpu() for state in cuda_all if torch.is_tensor(state)]
        if cuda_states:
            if len(cuda_states) == torch.cuda.device_count():
                torch.cuda.set_rng_state_all(cuda_states)
            elif device.type == "cuda":
                index = device.index if device.index is not None else torch.cuda.current_device()
                torch.cuda.set_rng_state(cuda_states[min(index, len(cuda_states) - 1)], device)
            restored = True
    return restored


_CLIP_CACHE: dict[tuple, list[tl.MotionClip]] = {}
_CLIP_FAST_CACHE: dict[tuple, list[tl.MotionClip]] = {}
_AE_CACHE: dict[tuple, tuple[SimpleAutoencoder, torch.Tensor, torch.Tensor, dict]] = {}
_AE2_CACHE: dict[tuple, tuple[torch.nn.Module, torch.Tensor, torch.Tensor, dict]] = {}
_AE3_CACHE: dict[tuple, tuple[torch.nn.Module, torch.Tensor, torch.Tensor, torch.Tensor | None, dict]] = {}
_AE4_CACHE: dict[tuple, tuple[object, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, dict]] = {}
_AE6_CACHE: dict[tuple, tuple[torch.nn.Module, torch.Tensor, torch.Tensor, dict]] = {}
IK_MOTION_AE_FEATURE_POSE_WINDOW = "ae5_lower_body_ik_pose_window"
IK_MOTION_AE_FEATURE_ROOT_POSE_WINDOW = "ae5_lower_body_ik_root_conditioned_pose_window"
AE5_SIMPLE_DELTA_FEATURE_MODES = {"velocity", "velocity_commanded"}
_STORE_CACHE: dict[tuple, "SimpleClipStore"] = {}
_STORE_FAST_CACHE: dict[tuple, "SimpleClipStore"] = {}
_TRAINING_START_POOLS_CACHE: dict[tuple, dict[int, "StartPool"]] = {}
_FULL_WINDOW_START_POOLS_CACHE: dict[tuple, dict[int, "StartPool"]] = {}
_FIXED_START_POOL_CACHE: dict[tuple, "StartPool"] = {}
_CONTROLLER_CKPT_CACHE: dict[tuple, dict] = {}
_ROOT_SPEED_CACHE: dict[tuple, float] = {}
_MOTION_CLIP_OBJECT_CACHE: dict[tuple, tl.MotionClip] = {}
_NPZ_TEXT_CACHE: dict[str, list[Path]] = {}
_RESOLVED_CLIP_SPECS_CACHE: dict[tuple[str, str, str], list[tuple[Path, bool]]] = {}
_AE_METADATA_SPECS_CACHE: dict[tuple, list[tuple[Path, bool]]] = {}
_FOOT_ROLL_STEP_T_CACHE: dict[tuple[str, int, str, int], torch.Tensor] = {}
MOTION_CLIP_DISK_CACHE_VERSION = 3
SIMPLE_CLIP_STORE_DISK_CACHE_KIND = "ik_simple_clip_store_bundle"
SIMPLE_CLIP_STORE_DISK_CACHE_VERSION = 2


def path_signature(path: Path) -> tuple[str, int, int]:
    resolved = path.resolve()
    stat = resolved.stat()
    return str(resolved).lower(), int(stat.st_mtime_ns), int(stat.st_size)


def ae4_projector_signature(path: Path) -> tuple[str, tuple[tuple[str, int, int], ...]]:
    resolved = path.resolve()
    required = ("best_model.pt", "stats.npz", "pose_bank.npz")
    return str(resolved).lower(), tuple(path_signature(resolved / name) for name in required)


def is_ae4_projector_dir(path: Path) -> bool:
    return path.is_dir() and all((path / name).is_file() for name in ("best_model.pt", "stats.npz", "pose_bank.npz"))


def ae4_uses_pose_bank_projector(ae4: object | None) -> bool:
    return isinstance(ae4, IKPoseBankProjectorPrior)


def cfg_cache_key(cfg: tl.TrainConfig) -> str:
    return json.dumps(asdict(cfg), sort_keys=True, default=str)


def specs_cache_key(specs: list[tuple[Path, bool]], cfg: tl.TrainConfig) -> tuple:
    return tuple((path_signature(path), bool(cyclic)) for path, cyclic in specs), cfg_cache_key(cfg)


def specs_fast_cache_key(specs: list[tuple[Path, bool]], cfg: tl.TrainConfig) -> tuple:
    return tuple((path_signature(path), bool(cyclic)) for path, cyclic in specs), cfg_cache_key(cfg)


def motion_clip_cache_key(path: Path, cfg: tl.TrainConfig, cyclic: bool) -> tuple:
    return (
        MOTION_CLIP_DISK_CACHE_VERSION,
        path_signature(path),
        bool(cyclic),
        cfg_cache_key(cfg),
        int(tl.IK_SCHEMA_VERSION),
        str(tl.IK_POLE_REFERENCE),
        str(tl.OUTPUT_REFERENCE_ROOT),
        str(tl.normalized_output_prediction_mode()),
    )


def motion_clip_disk_cache_path(key: tuple) -> Path:
    digest = hashlib.sha256(json.dumps(key, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:24]
    return PROJECT_ROOT / "training" / "runs" / "cache" / "motion_clips" / f"{digest}.pt"


def simple_clip_store_cache_key_from_specs(
    specs: list[tuple[Path, bool]],
    cfg: tl.TrainConfig,
    device: torch.device,
) -> tuple:
    return (
        SIMPLE_CLIP_STORE_DISK_CACHE_VERSION,
        tuple((path_signature(path), bool(cyclic)) for path, cyclic in specs),
        cfg_cache_key(cfg),
        str(device),
        int(tl.IK_SCHEMA_VERSION),
        str(tl.IK_POLE_REFERENCE),
        str(tl.OUTPUT_REFERENCE_ROOT),
        str(tl.normalized_output_prediction_mode()),
    )


def simple_clip_store_fast_cache_key_from_specs(
    specs: list[tuple[Path, bool]],
    cfg: tl.TrainConfig,
    device: torch.device,
) -> tuple:
    return (
        tuple((path_signature(path), bool(cyclic)) for path, cyclic in specs),
        cfg_cache_key(cfg),
        str(device),
        int(tl.IK_SCHEMA_VERSION),
        str(tl.IK_POLE_REFERENCE),
        str(tl.OUTPUT_REFERENCE_ROOT),
        str(tl.normalized_output_prediction_mode()),
    )


def simple_clip_store_fast_cache_key_from_clips(
    clips: list[tl.MotionClip],
    cfg: tl.TrainConfig,
    device: torch.device,
) -> tuple:
    return simple_clip_store_fast_cache_key_from_specs(
        [(clip.path, bool(clip.cyclic_animation)) for clip in clips],
        cfg,
        device,
    )


def simple_clip_store_cache_key_from_clips(
    clips: list[tl.MotionClip],
    cfg: tl.TrainConfig,
    device: torch.device,
) -> tuple:
    return simple_clip_store_cache_key_from_specs(
        [(clip.path, bool(clip.cyclic_animation)) for clip in clips],
        cfg,
        device,
    )


def simple_clip_store_disk_cache_path(key: tuple) -> Path:
    digest = hashlib.sha256(json.dumps(key, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:24]
    return PROJECT_ROOT / "training" / "runs" / "cache" / "simple_clip_stores" / f"{digest}.pt"


def torch_load_cache(path: Path, map_location: torch.device | str) -> object:
    try:
        return torch.load(path, map_location=map_location, weights_only=False, mmap=True)
    except TypeError:
        return torch.load(path, map_location=map_location, weights_only=False)
    except RuntimeError:
        return torch.load(path, map_location=map_location, weights_only=False)


def simple_clip_meta_from_clip(clip: tl.MotionClip | SimpleClipMeta) -> SimpleClipMeta:
    return SimpleClipMeta(
        path=Path(clip.path),
        cyclic_animation=bool(clip.cyclic_animation),
        cyclic_period=int(clip.cyclic_period),
        T=int(clip.T),
        body_names=list(clip.body_names),
        parents_body_list=[int(parent) for parent in clip.parents_body_list],
        fps=float(clip.fps),
    )


def is_synthetic_clip_path(path: str | Path) -> bool:
    text = str(path).replace("\\", "/").lower()
    stem = Path(path).stem.lower()
    generated_dataset_markers = (
        "animations_synthetic",
        "animations_virtual_controller",
        "virtual_controller",
    )
    return any(marker in text for marker in generated_dataset_markers) or stem.startswith(("synthetic_", "virtual_"))


def is_virtual_clip_path(path: str | Path) -> bool:
    text = str(path).replace("\\", "/").lower()
    stem = Path(path).stem.lower()
    return "animations_virtual_controller" in text or "virtual_controller" in text or stem.startswith("virtual_")


def is_synthetic_only_clip_path(path: str | Path) -> bool:
    text = str(path).replace("\\", "/").lower()
    stem = Path(path).stem.lower()
    if is_virtual_clip_path(path):
        return False
    return "animations_synthetic" in text or stem.startswith("synthetic_")


def motion_clip_for_disk_cache(clip: tl.MotionClip) -> tl.MotionClip:
    cached_clip = copy.copy(clip)
    cached_clip._device_cache = {}
    return cached_clip


def simple_clip_store_disk_payload(store: "SimpleClipStore") -> dict[str, object]:
    skip = {
        "clips",
        "cfg",
        "device",
        "prototype",
        "store_cache_key",
        "root_cache_max_idx",
        "root_cache_pos",
        "root_cache_rot",
        "root_cache_yaw",
        "root_cache_heading",
    }
    state: dict[str, object] = {}
    for name, value in store.__dict__.items():
        if name in skip:
            continue
        if isinstance(value, torch.Tensor):
            state[name] = value.detach().cpu()
        else:
            state[name] = value
    return {
        "kind": SIMPLE_CLIP_STORE_DISK_CACHE_KIND,
        "version": SIMPLE_CLIP_STORE_DISK_CACHE_VERSION,
        "clips": [simple_clip_meta_from_clip(clip) for clip in store.clips],
        "prototype": motion_clip_for_disk_cache(store.prototype),
        "state": state,
    }


def simple_clip_store_from_disk_payload(
    payload: object,
    cfg: tl.TrainConfig,
    device: torch.device,
    key: tuple,
) -> "SimpleClipStore | None":
    if not isinstance(payload, dict):
        return None
    if payload.get("kind") != SIMPLE_CLIP_STORE_DISK_CACHE_KIND:
        return None
    if int(payload.get("version", -1)) != SIMPLE_CLIP_STORE_DISK_CACHE_VERSION:
        return None
    raw_clips = payload.get("clips")
    state = payload.get("state")
    prototype = payload.get("prototype")
    if not isinstance(raw_clips, list) or not isinstance(state, dict) or not isinstance(prototype, tl.MotionClip):
        return None

    store = SimpleClipStore.__new__(SimpleClipStore)
    store.clips = [
        clip if isinstance(clip, SimpleClipMeta) else simple_clip_meta_from_clip(clip)  # type: ignore[arg-type]
        for clip in raw_clips
    ]
    store.cfg = cfg
    store.device = device
    store.prototype = prototype
    for name, value in state.items():
        if isinstance(value, torch.Tensor):
            setattr(store, name, value.to(device=device))
        else:
            setattr(store, name, value)
    return sanitize_loaded_simple_clip_store(store, device, key)


def load_motion_clip_cached(path: Path, cfg: tl.TrainConfig, cyclic: bool) -> tl.MotionClip:
    key = motion_clip_cache_key(path, cfg, cyclic)
    cached = _MOTION_CLIP_OBJECT_CACHE.get(key)
    if cached is not None:
        return cached

    cache_path = motion_clip_disk_cache_path(key)
    if cache_path.exists():
        try:
            clip = torch_load_cache(cache_path, "cpu")
            if isinstance(clip, tl.MotionClip):
                clip.path = path
                clip._device_cache = {}
                _MOTION_CLIP_OBJECT_CACHE[key] = clip
                return clip
        except Exception:
            pass

    clip = tl.MotionClip(path, cfg, cyclic_animation=cyclic)
    clip._device_cache = {}
    _MOTION_CLIP_OBJECT_CACHE[key] = clip
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
        torch.save(clip, tmp_path)
        tmp_path.replace(cache_path)
    except Exception:
        pass
    return clip


def sanitize_loaded_simple_clip_store(store: "SimpleClipStore", device: torch.device, key: tuple | None = None) -> "SimpleClipStore":
    store.device = device
    if not hasattr(store, "body_mode"):
        store.body_mode = tl.normalized_body_mode(getattr(store.cfg, "body_mode", tl.BODY_MODE_LOWER))
    if not hasattr(store, "ik_payload_slices") and hasattr(store, "prototype"):
        store.ik_payload_slices = tuple(getattr(store.prototype, "ik_payload_slices", tl.IK_PAYLOAD_SLICES))
    if not hasattr(store, "ik_payload_leg_limb_indices") and hasattr(store, "ik_payload_slices"):
        store.ik_payload_leg_limb_indices = tuple(
            i for i, spec in enumerate(store.ik_payload_slices) if str(spec.get("kind", "")).lower().strip() == "leg"
        )
    if not hasattr(store, "ik_payload_leg_limb_indices_tensor") and hasattr(store, "ik_payload_leg_limb_indices"):
        store.ik_payload_leg_limb_indices_tensor = torch.tensor(
            store.ik_payload_leg_limb_indices,
            dtype=torch.long,
            device=device,
        )
    if not hasattr(store, "ik_base_start_indices") and hasattr(store, "prototype"):
        store.ik_base_start_indices = tuple(int(spec["start"]) for spec in store.prototype.ik_limb_specs)
    if not hasattr(store, "ik_end_indices") and hasattr(store, "prototype"):
        store.ik_end_indices = tuple(int(spec["end"]) for spec in store.prototype.ik_limb_specs)
    if not hasattr(store, "ik_base_start_indices_tensor") and hasattr(store, "ik_base_start_indices"):
        store.ik_base_start_indices_tensor = torch.tensor(store.ik_base_start_indices, dtype=torch.long, device=device)
    if not hasattr(store, "ik_end_indices_tensor") and hasattr(store, "ik_end_indices"):
        store.ik_end_indices_tensor = torch.tensor(store.ik_end_indices, dtype=torch.long, device=device)
    if not hasattr(store, "ik_mid_offsets") and hasattr(store, "local_offsets") and hasattr(store, "ik_mid_indices_tensor"):
        store.ik_mid_offsets = store.local_offsets.index_select(0, store.ik_mid_indices_tensor)
    if not hasattr(store, "ik_end_offsets") and hasattr(store, "local_offsets") and hasattr(store, "ik_end_indices_tensor"):
        store.ik_end_offsets = store.local_offsets.index_select(0, store.ik_end_indices_tensor)
    if not hasattr(store, "ik_toe_offsets") and hasattr(store, "prototype"):
        try:
            store.ik_toe_offsets = store.prototype.tensors(device)["ik_toe_offsets"]
        except Exception:
            store.ik_toe_offsets = torch.empty((0, 3), dtype=torch.float32, device=device)
    if not hasattr(store, "ik_toe_axis") and hasattr(store, "prototype"):
        try:
            store.ik_toe_axis = store.prototype.tensors(device)["ik_toe_axis"]
        except Exception:
            store.ik_toe_axis = torch.empty((0, 3), dtype=torch.float32, device=device)
    store.foot_roll_foot_half_dims = torch.tensor(
        FOOT_ROLL_FOOT_DIMS_M,
        dtype=torch.float32,
        device=device,
    ) * 0.5
    store.foot_roll_toe_half_dims = torch.tensor(
        FOOT_ROLL_TOE_DIMS_M,
        dtype=torch.float32,
        device=device,
    ) * 0.5
    store.foot_roll_ground_y_tensor = torch.tensor(
        float(getattr(store.cfg, "foot_roll_ground_y", 0.0)),
        dtype=torch.float32,
        device=device,
    )
    if not hasattr(store, "max_training_starts") and hasattr(store, "cyclic"):
        horizon = int(transition_feature_horizon(store.cfg))
        noncyclic_max = (store.lengths - horizon - 1).clamp_min(1)
        store.max_training_starts = torch.where(store.cyclic, store.periods.clamp_min(1) - 1, noncyclic_max).clamp_min(1)
    if (
        not hasattr(store, "synthetic")
        or not isinstance(getattr(store, "synthetic"), torch.Tensor)
        or int(store.synthetic.numel()) != len(getattr(store, "clips", []))
    ):
        store.synthetic = torch.tensor(
            [is_synthetic_clip_path(clip.path) for clip in getattr(store, "clips", [])],
            dtype=torch.bool,
            device=device,
        )
    else:
        store.synthetic = store.synthetic.to(device=device, dtype=torch.bool)
    if key is not None:
        store.store_cache_key = key
    store.root_cache_max_idx = -1
    store.root_cache_pos = None
    store.root_cache_rot = None
    store.root_cache_yaw = None
    store.root_cache_heading = None
    for clip in getattr(store, "clips", []):
        if hasattr(clip, "_device_cache"):
            clip._device_cache = {}
    if hasattr(store, "prototype") and hasattr(store.prototype, "_device_cache"):
        store.prototype._device_cache = {}
    return store


def load_simple_clip_store_from_disk(key: tuple, cfg: tl.TrainConfig, device: torch.device) -> "SimpleClipStore | None":
    cache_path = simple_clip_store_disk_cache_path(key)
    if not cache_path.exists():
        return None
    phase_started = time.perf_counter()
    try:
        store = torch_load_cache(cache_path, device)
        loaded_started = emit_pretrain_arm_timing(
            "simple_store_disk_torch_load",
            phase_started,
            size_mb=f"{cache_path.stat().st_size / (1024.0 * 1024.0):.1f}",
        )
        bundled_store = simple_clip_store_from_disk_payload(store, cfg, device, key)
        if bundled_store is not None:
            emit_pretrain_arm_timing("simple_store_disk_restore_bundle", loaded_started)
            return bundled_store
        if isinstance(store, SimpleClipStore):
            store.cfg = cfg
            sanitized = sanitize_loaded_simple_clip_store(store, device, key)
            emit_pretrain_arm_timing("simple_store_disk_sanitize", loaded_started)
            return sanitized
        emit_pretrain_arm_timing("simple_store_disk_rejected", loaded_started, type=type(store).__name__)
    except Exception as exc:
        emit_pretrain_arm_timing("simple_store_disk_failed", phase_started, error=type(exc).__name__)
        return None
    return None


def save_simple_clip_store_to_disk(key: tuple, store: "SimpleClipStore") -> None:
    cache_path = simple_clip_store_disk_cache_path(key)
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
        torch.save(simple_clip_store_disk_payload(store), tmp_path)
        tmp_path.replace(cache_path)
    except Exception:
        pass


def cached_simple_clip_store(clips: list[tl.MotionClip], cfg: tl.TrainConfig, device: torch.device) -> "SimpleClipStore":
    fast_key = simple_clip_store_fast_cache_key_from_clips(clips, cfg, device)
    fast_cached = _STORE_FAST_CACHE.get(fast_key)
    if fast_cached is not None:
        return fast_cached
    key = simple_clip_store_cache_key_from_clips(clips, cfg, device)
    cached = _STORE_CACHE.get(key)
    if cached is not None:
        cached.store_cache_key = key
        _STORE_FAST_CACHE[fast_key] = cached
        return cached
    disk_cached = load_simple_clip_store_from_disk(key, cfg, device)
    if disk_cached is not None:
        disk_cached.store_cache_key = key
        _STORE_CACHE[key] = disk_cached
        _STORE_FAST_CACHE[fast_key] = disk_cached
        return disk_cached
    store = SimpleClipStore(clips, cfg, device)
    store.store_cache_key = key
    _STORE_CACHE[key] = store
    _STORE_FAST_CACHE[fast_key] = store
    save_simple_clip_store_to_disk(key, store)
    return store


def cached_simple_clip_store_from_specs(
    specs: list[tuple[Path, bool]],
    cfg: tl.TrainConfig,
    device: torch.device,
) -> "SimpleClipStore":
    fast_key = simple_clip_store_fast_cache_key_from_specs(specs, cfg, device)
    fast_cached = _STORE_FAST_CACHE.get(fast_key)
    if fast_cached is not None:
        return fast_cached
    key = simple_clip_store_cache_key_from_specs(specs, cfg, device)
    cached = _STORE_CACHE.get(key)
    if cached is not None:
        cached.store_cache_key = key
        _STORE_FAST_CACHE[fast_key] = cached
        return cached
    disk_cached = load_simple_clip_store_from_disk(key, cfg, device)
    if disk_cached is not None:
        disk_cached.store_cache_key = key
        _STORE_CACHE[key] = disk_cached
        _STORE_FAST_CACHE[fast_key] = disk_cached
        return disk_cached
    return cached_simple_clip_store(load_clips(specs, cfg), cfg, device)


def load_controller_checkpoint(path: Path) -> dict:
    key = path_signature(path)
    cached = _CONTROLLER_CKPT_CACHE.get(key)
    if cached is not None:
        return cached
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    _CONTROLLER_CKPT_CACHE[key] = ckpt
    return ckpt


class SimpleClipStore:
    def __init__(self, clips: list[tl.MotionClip], cfg: tl.TrainConfig, device: torch.device):
        if not clips:
            raise ValueError("SimpleClipStore needs at least one clip")
        first = clips[0]
        for clip in clips[1:]:
            if clip.body_names != first.body_names or clip.parents_body_list != first.parents_body_list:
                raise ValueError(f"Skeleton mismatch: {clip.path} vs {first.path}")

        self.clips = clips
        self.cfg = cfg
        self.device = device
        self.prototype = first
        self.J = int(first.J)
        self.Jcore = int(first.Jcore)
        self.ik_payload_dim = int(getattr(first, "ik_payload_dim", 0))
        self.body_mode = tl.normalized_body_mode(getattr(first, "body_mode", getattr(cfg, "body_mode", tl.BODY_MODE_LOWER)))
        self.ik_payload_slices = tuple(getattr(first, "ik_payload_slices", tl.IK_PAYLOAD_SLICES))
        self.ik_payload_leg_limb_indices = tuple(
            i for i, spec in enumerate(self.ik_payload_slices) if str(spec.get("kind", "")).lower().strip() == "leg"
        )
        self.ik_payload_leg_limb_indices_tensor = torch.tensor(
            self.ik_payload_leg_limb_indices,
            dtype=torch.long,
            device=device,
        )
        self.pelvis = int(first.pelvis)
        prototype_tensors = first.tensors(device)
        self.local_offsets = prototype_tensors["local_offsets"]
        self.ik_limb_lengths = prototype_tensors["ik_limb_lengths"]
        self.ik_rest_axis = prototype_tensors["ik_rest_axis"]
        self.ik_ee_pole_ref = prototype_tensors["ik_ee_pole_ref"]
        self.ik_pole_alpha = prototype_tensors["ik_pole_alpha"]
        self.ik_toe_offsets = prototype_tensors["ik_toe_offsets"]
        self.ik_toe_axis = prototype_tensors["ik_toe_axis"]
        self.foot_roll_foot_half_dims = torch.tensor(
            FOOT_ROLL_FOOT_DIMS_M,
            dtype=torch.float32,
            device=device,
        ) * 0.5
        self.foot_roll_toe_half_dims = torch.tensor(
            FOOT_ROLL_TOE_DIMS_M,
            dtype=torch.float32,
            device=device,
        ) * 0.5
        self.foot_roll_ground_y_tensor = torch.tensor(
            float(getattr(cfg, "foot_roll_ground_y", 0.0)),
            dtype=torch.float32,
            device=device,
        )
        self.ik_base_start_indices = tuple(int(spec["start"]) for spec in first.ik_limb_specs)
        self.ik_mid_indices = tuple(int(spec["mid"]) for spec in first.ik_limb_specs)
        self.ik_end_indices = tuple(int(spec["end"]) for spec in first.ik_limb_specs)
        self.ik_base_start_indices_tensor = torch.tensor(self.ik_base_start_indices, dtype=torch.long, device=device)
        self.ik_mid_indices_tensor = torch.tensor(self.ik_mid_indices, dtype=torch.long, device=device)
        self.ik_end_indices_tensor = torch.tensor(self.ik_end_indices, dtype=torch.long, device=device)
        self.ik_mid_offsets = self.local_offsets.index_select(0, self.ik_mid_indices_tensor)
        self.ik_end_offsets = self.local_offsets.index_select(0, self.ik_end_indices_tensor)
        self.ik_limb_is_leg = torch.tensor(
            [str(spec["kind"]).lower().strip() == "leg" for spec in first.ik_limb_specs],
            dtype=torch.bool,
            device=device,
        )
        self.ik_leg_count = sum(1 for spec in first.ik_limb_specs if str(spec["kind"]).lower().strip() == "leg")
        self.ik_arm_count = len(first.ik_limb_specs) - self.ik_leg_count
        self.ik_leg_indices_tensor = torch.tensor(
            [i for i, spec in enumerate(first.ik_limb_specs) if str(spec["kind"]).lower().strip() == "leg"],
            dtype=torch.long,
            device=device,
        )
        self.ik_arm_indices_tensor = torch.tensor(
            [i for i, spec in enumerate(first.ik_limb_specs) if str(spec["kind"]).lower().strip() != "leg"],
            dtype=torch.long,
            device=device,
        )
        self.ik_lower_length_tolerance_m = torch.tensor(
            [
                IK_LOWER_LENGTH_LEG_TOLERANCE_M
                if str(spec["kind"]).lower().strip() == "leg"
                else IK_LOWER_LENGTH_ARM_TOLERANCE_M
                for spec in first.ik_limb_specs
            ],
            dtype=torch.float32,
            device=device,
        )
        needed_bones: set[int] = set()
        for start in self.ik_base_start_indices:
            bone = int(start)
            while bone >= 0:
                needed_bones.add(bone)
                bone = int(first.parents_body_list[bone])
        self.ik_base_eval_order = tuple(bone for bone in range(first.J) if bone in needed_bones)
        fast_base_names = (
            "spine_01",
            "spine_02",
            "spine_03",
            "spine_04",
            "spine_05",
            "clavicle_l",
            "clavicle_r",
            "upperarm_l",
            "upperarm_r",
            "thigh_l",
            "thigh_r",
        )
        self.ik_fast_base_indices = (
            {name: first.body_names.index(name) for name in fast_base_names}
            if all(name in first.body_names for name in fast_base_names)
            else None
        )

        tensors = [clip.tensors(device) for clip in clips]
        lengths = [int(clip.T) for clip in clips]
        offsets = [0]
        for length in lengths:
            offsets.append(offsets[-1] + length)

        self.frame_offsets = torch.tensor(offsets[:-1], dtype=torch.long, device=device)
        self.lengths = torch.tensor(lengths, dtype=torch.long, device=device)
        self.periods = torch.tensor([int(clip.cyclic_period) for clip in clips], dtype=torch.long, device=device)
        self.cyclic = torch.tensor([bool(clip.cyclic_animation) for clip in clips], dtype=torch.bool, device=device)
        self.synthetic = torch.tensor(
            [is_synthetic_clip_path(clip.path) for clip in clips],
            dtype=torch.bool,
            device=device,
        )
        horizon = int(transition_feature_horizon(cfg))
        noncyclic_max = (self.lengths - horizon - 1).clamp_min(1)
        self.max_training_starts = torch.where(self.cyclic, self.periods.clamp_min(1) - 1, noncyclic_max).clamp_min(1)

        self.root_pos = torch.cat([t["root_pos"] for t in tensors], dim=0)
        self.root_rot = torch.cat([t["root_rot"] for t in tensors], dim=0)
        self.pelvis_local_pos = torch.cat([t["pelvis_local_pos"] for t in tensors], dim=0)
        self.pelvis_rot6 = torch.cat([t["pelvis_rot6"] for t in tensors], dim=0)
        self.non_pelvis_rot6 = torch.cat([t["non_pelvis_rot6"] for t in tensors], dim=0)
        self.core_non_pelvis_rot6 = torch.cat([t["core_non_pelvis_rot6"] for t in tensors], dim=0)
        self.canonical_pos = torch.cat([t["canonical_pos"] for t in tensors], dim=0)
        self.ik_payload = torch.cat([t["ik_payload"] for t in tensors], dim=0)

        self.root0_pos = torch.stack([t["root_pos"][0] for t in tensors], dim=0)
        self.root0_rot = torch.stack([t["root_rot"][0] for t in tensors], dim=0)
        self.root0_inv = self.root0_rot.transpose(-1, -2)
        self.end_pos = torch.stack([t["root_pos"][clip.cyclic_period] for clip, t in zip(clips, tensors)], dim=0)
        self.end_rot = torch.stack([t["root_rot"][clip.cyclic_period] for clip, t in zip(clips, tensors)], dim=0)
        self.cycle_pos = torch.matmul((self.end_pos - self.root0_pos).unsqueeze(1), self.root0_inv).squeeze(1)
        self.cycle_rot = self.end_rot @ self.root0_inv
        self.root_cache_max_idx = -1
        self.root_cache_pos: torch.Tensor | None = None
        self.root_cache_rot: torch.Tensor | None = None
        self.root_cache_yaw: torch.Tensor | None = None
        self.root_cache_heading: torch.Tensor | None = None

        self.target_output = self._build_target_output()
        self.input_root_features = self._build_input_root_features()
        (
            self.stationary_double_pin_speed_cutoff_mps,
            self.stationary_double_pin_yaw_cutoff_rad,
        ) = self._stationary_double_pin_cutoffs(tensors)

    def _adjacent_motion_stats(self, clip: tl.MotionClip, tensors: dict[str, torch.Tensor]) -> tuple[torch.Tensor, torch.Tensor]:
        frame_count = int(clip.cyclic_period) + 1 if bool(clip.cyclic_animation) else int(clip.T)
        frame_count = max(0, min(frame_count, int(tensors["root_pos"].shape[0])))
        if frame_count < 2:
            zero = torch.zeros((0,), dtype=torch.float32, device=self.device)
            return zero, zero
        root_pos = tensors["root_pos"][:frame_count]
        root_rot = tensors["root_rot"][:frame_count]
        speed = torch.linalg.vector_norm(root_pos[1:, [0, 2]] - root_pos[:-1, [0, 2]], dim=-1) * float(self.prototype.fps)
        yaw = tl.heading_yaw_from_root(root_rot)
        yaw_delta = tl.wrap_angle(yaw[1:] - yaw[:-1]).abs()
        return speed, yaw_delta

    def _stationary_double_pin_cutoffs(self, tensors: list[dict[str, torch.Tensor]]) -> tuple[float, float]:
        walk_speeds: list[torch.Tensor] = []
        turn_yaw_deltas: list[torch.Tensor] = []
        all_speeds: list[torch.Tensor] = []
        all_yaw_deltas: list[torch.Tensor] = []
        for clip, clip_tensors in zip(self.clips, tensors):
            name = Path(str(clip.path)).stem.lower()
            speed, yaw_delta = self._adjacent_motion_stats(clip, clip_tensors)
            if speed.numel():
                all_speeds.append(speed)
            if yaw_delta.numel():
                all_yaw_deltas.append(yaw_delta)
            if name == "m_neutral_walk_loop_f" and speed.numel():
                walk_speeds.append(speed)
            if "turn_045" in name and yaw_delta.numel():
                turn_yaw_deltas.append(yaw_delta)
        speed_source = torch.cat(walk_speeds) if walk_speeds else (torch.cat(all_speeds) if all_speeds else None)
        yaw_source = (
            torch.cat(turn_yaw_deltas)
            if turn_yaw_deltas
            else (torch.cat(all_yaw_deltas) if all_yaw_deltas else None)
        )
        if speed_source is not None and speed_source.numel():
            speed_ref = float(speed_source.mean().detach().cpu())
        else:
            speed_ref = float(self.cfg.max_speed_scale)
        if yaw_source is not None and yaw_source.numel():
            yaw_ref = float(yaw_source.max().detach().cpu())
        else:
            yaw_ref = float(self.cfg.max_turn_rate_scale_final)
        frac = float(STATIONARY_DOUBLE_PIN_REFERENCE_FRACTION)
        speed_cutoff = max(1e-6, speed_ref * frac)
        yaw_cutoff = max(1e-6, yaw_ref * frac)
        return speed_cutoff, yaw_cutoff

    def _build_target_output(self) -> torch.Tensor:
        b = self.pelvis_local_pos.shape[0]
        return torch.cat(
            (
                self.pelvis_local_pos,
                self.pelvis_rot6,
                self.core_non_pelvis_rot6.reshape(b, -1),
                self.ik_payload,
            ),
            dim=-1,
        )

    def _build_input_root_features(self) -> torch.Tensor:
        chunks: list[torch.Tensor] = []
        future_steps = int(self.cfg.future_window)
        feature_dim = 3 + future_steps * 4
        for clip_id, clip in enumerate(self.clips):
            features = torch.zeros((int(clip.T), feature_dim), dtype=torch.float32, device=self.device)
            if int(clip.T) <= 1:
                chunks.append(features)
                continue

            if clip.cyclic_animation:
                period = max(1, int(clip.cyclic_period))
                rows = torch.arange(period, dtype=torch.long, device=self.device)
                cur_idx = rows.clone()
                cur_idx[0] = period
            else:
                # The canonical controller feature builder includes frame 0
                # with a clamped frame-0 predecessor.  Its root delta is zero,
                # but its future-root commands are real and must not be
                # replaced by the all-zero allocation above.
                rows = torch.arange(0, int(clip.T), dtype=torch.long, device=self.device)
                cur_idx = rows

            clip_ids = torch.full((cur_idx.numel(),), clip_id, dtype=torch.long, device=self.device)
            prev_idx = cur_idx - 1 if clip.cyclic_animation else (cur_idx - 1).clamp_min(0)
            prev_pos, _prev_rot, prev_yaw, prev_heading = self.root_state(clip_ids, prev_idx)
            cur_pos, _cur_rot, cur_yaw, cur_heading = self.root_state(clip_ids, cur_idx)
            delta_local = torch.matmul((cur_pos - prev_pos).unsqueeze(1), prev_heading).squeeze(1)
            root_feat = torch.stack(
                (
                    delta_local[:, 0] / self.cfg.max_speed_scale_final,
                    delta_local[:, 2] / self.cfg.max_speed_scale_final,
                    tl.wrap_angle(cur_yaw - prev_yaw) / self.cfg.max_turn_rate_scale_final,
                ),
                dim=-1,
            )

            future_offsets = torch.arange(1, future_steps + 1, device=self.device, dtype=cur_idx.dtype)
            flat_clip_ids = clip_ids.reshape(-1, 1).expand(-1, future_steps).reshape(-1)
            flat_idx = (cur_idx.reshape(-1, 1) + future_offsets.reshape(1, future_steps)).reshape(-1)
            if not clip.cyclic_animation:
                flat_idx = flat_idx.clamp(max=int(clip.T) - 1)
            fut_pos, _fut_rot, fut_yaw, _fut_heading = self.root_state(flat_clip_ids, flat_idx)
            fut_pos = fut_pos.reshape(cur_idx.numel(), future_steps, 3)
            fut_yaw = fut_yaw.reshape(cur_idx.numel(), future_steps)
            fut_local = torch.matmul((fut_pos - cur_pos[:, None, :]).unsqueeze(-2), cur_heading[:, None]).squeeze(-2)
            scale = future_offsets.to(dtype=fut_local.dtype).reshape(1, future_steps) * self.cfg.max_speed_scale_final
            dyaw = tl.wrap_angle(fut_yaw - cur_yaw[:, None])
            future_feat = torch.stack(
                (
                    torch.clamp(fut_local[:, :, 0] / scale, -2.0, 2.0),
                    torch.clamp(fut_local[:, :, 2] / scale, -2.0, 2.0),
                    torch.cos(dyaw),
                    torch.sin(dyaw),
                ),
                dim=-1,
            ).reshape(cur_idx.numel(), future_steps * 4)
            features[rows] = torch.cat((root_feat, future_feat), dim=-1)
            chunks.append(features)
        return torch.cat(chunks, dim=0)

    def frame_index(self, clip_ids: torch.Tensor, idx: torch.Tensor) -> torch.Tensor:
        clip_ids = clip_ids.to(self.device).long()
        idx = idx.to(self.device).long()
        periods = self.periods.index_select(0, clip_ids).clamp_min(1)
        cyclic = self.cyclic.index_select(0, clip_ids)
        logical = torch.where(cyclic, torch.remainder(idx, periods), idx)
        return self.frame_offsets.index_select(0, clip_ids) + logical

    def _root_state_uncached(
        self, clip_ids: torch.Tensor, idx: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        clip_ids = clip_ids.to(self.device).long()
        idx = idx.to(self.device).long()
        frame = self.frame_index(clip_ids, idx)
        base_pos = self.root_pos.index_select(0, frame)
        base_rot = self.root_rot.index_select(0, frame)
        root0_pos = self.root0_pos.index_select(0, clip_ids)
        root0_rot = self.root0_rot.index_select(0, clip_ids)
        root0_inv = self.root0_inv.index_select(0, clip_ids)
        periods = self.periods.index_select(0, clip_ids).clamp_min(1)
        cyclic = self.cyclic.index_select(0, clip_ids)
        cycles = torch.where(cyclic, torch.div(idx, periods, rounding_mode="floor"), torch.zeros_like(idx))

        rel_pos = torch.matmul((base_pos - root0_pos).unsqueeze(1), root0_inv).squeeze(1)
        rel_rot = base_rot @ root0_inv
        cycle_pos = self.cycle_pos.index_select(0, clip_ids)
        cycle_rot = self.cycle_rot.index_select(0, clip_ids)
        acc_pos = torch.zeros_like(cycle_pos)
        identity = torch.eye(3, dtype=cycle_rot.dtype, device=self.device).expand_as(cycle_rot)
        acc_rot = identity
        base_pos = cycle_pos
        base_rot = cycle_rot
        for bit in range(16):
            use = torch.remainder(torch.div(cycles, 1 << bit, rounding_mode="floor"), 2).bool()
            use_pos = use.reshape(-1, 1)
            use_rot = use.reshape(-1, 1, 1)
            next_acc_pos = torch.matmul(acc_pos.unsqueeze(1), base_rot).squeeze(1) + base_pos
            next_acc_rot = acc_rot @ base_rot
            acc_pos = torch.where(use_pos, next_acc_pos, acc_pos)
            acc_rot = torch.where(use_rot, next_acc_rot, acc_rot)
            base_pos = torch.matmul(base_pos.unsqueeze(1), base_rot).squeeze(1) + base_pos
            base_rot = base_rot @ base_rot
        rel_pos = torch.matmul(rel_pos.unsqueeze(1), acc_rot).squeeze(1) + acc_pos
        rel_rot = rel_rot @ acc_rot

        pos = torch.matmul(rel_pos.unsqueeze(1), root0_rot).squeeze(1) + root0_pos
        rot = rel_rot @ root0_rot
        yaw = tl.heading_yaw_from_root(rot)
        heading = tl.yaw_to_row_matrix(yaw)
        return pos, rot, yaw, heading

    def root_state(self, clip_ids: torch.Tensor, idx: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        clip_ids = clip_ids.to(self.device).long()
        idx = idx.to(self.device).long()
        if self.root_cache_pos is None:
            return self._root_state_uncached(clip_ids, idx)
        flat = clip_ids * int(self.root_cache_max_idx + 1) + idx
        return (
            self.root_cache_pos.index_select(0, flat),
            self.root_cache_rot.index_select(0, flat),  # type: ignore[union-attr]
            self.root_cache_yaw.index_select(0, flat),  # type: ignore[union-attr]
            self.root_cache_heading.index_select(0, flat),  # type: ignore[union-attr]
        )

    def prepare_root_state_cache(self, rollout_k: int) -> None:
        max_idx = 0
        horizon = int(transition_feature_horizon(self.cfg))
        extra = max(1, int(rollout_k)) + horizon + 2
        for clip in self.clips:
            if bool(clip.cyclic_animation):
                max_idx = max(max_idx, int(clip.cyclic_period) + extra)
            else:
                max_idx = max(max_idx, int(clip.T) - 1)
        if self.root_cache_pos is not None and int(self.root_cache_max_idx) >= max_idx:
            return
        clip_count = len(self.clips)
        idx = torch.arange(max_idx + 1, dtype=torch.long, device=self.device).repeat(clip_count)
        clip_ids = torch.arange(clip_count, dtype=torch.long, device=self.device).repeat_interleave(max_idx + 1)
        lengths = self.lengths.index_select(0, clip_ids).clamp_min(1)
        cyclic = self.cyclic.index_select(0, clip_ids)
        cache_fill_idx = torch.where(cyclic, idx, torch.minimum(idx, lengths - 1))
        pos, rot, yaw, heading = self._root_state_uncached(clip_ids, cache_fill_idx)
        self.root_cache_max_idx = int(max_idx)
        self.root_cache_pos = pos.contiguous()
        self.root_cache_rot = rot.contiguous()
        self.root_cache_yaw = yaw.contiguous()
        self.root_cache_heading = heading.contiguous()

    def get_pose(self, clip_ids: torch.Tensor, idx: torch.Tensor) -> dict[str, torch.Tensor]:
        frame = self.frame_index(clip_ids, idx)
        return {
            "pelvis_pos": self.pelvis_local_pos.index_select(0, frame),
            "pelvis_rot6": self.pelvis_rot6.index_select(0, frame),
            "nonpelvis_rot6": self.non_pelvis_rot6.index_select(0, frame),
            "canon_pos": self.canonical_pos.index_select(0, frame),
            "core_nonpelvis_rot6": self.core_non_pelvis_rot6.index_select(0, frame),
            "ik_payload": self.ik_payload.index_select(0, frame),
        }

    def get_target_output(self, clip_ids: torch.Tensor, idx: torch.Tensor) -> torch.Tensor:
        return self.target_output.index_select(0, self.frame_index(clip_ids, idx))

    def get_input_root_features(self, clip_ids: torch.Tensor, idx: torch.Tensor) -> torch.Tensor:
        return self.input_root_features.index_select(0, self.frame_index(clip_ids, idx))


def apply_config_dict(cfg: tl.TrainConfig, values: dict) -> None:
    valid = {field.name for field in fields(tl.TrainConfig)}
    for key, value in values.items():
        if key not in valid:
            continue
        current = getattr(cfg, key)
        if isinstance(current, tuple) and isinstance(value, list):
            value = tuple(value)
        setattr(cfg, key, value)


def make_cfg(
    device: torch.device,
    ae_ckpt: dict,
    body_mode: str | None = None,
    hidden_dim: int | None = None,
    num_hidden_layers: int | None = None,
) -> tl.TrainConfig:
    cfg = tl.TrainConfig()
    apply_config_dict(cfg, ae_ckpt.get("locomotion_config", {}))
    if body_mode is not None:
        cfg.body_mode = tl.normalized_body_mode(body_mode)
    else:
        cfg.body_mode = tl.normalized_body_mode(getattr(cfg, "body_mode", tl.BODY_MODE_LOWER))
    cfg.pose_representation = tl.IK_POSE_REPRESENTATION
    cfg.predict_residual = tl.output_prediction_uses_residual()
    cfg.zero_init_output = tl.output_prediction_uses_residual()
    cfg.hidden_dim = int(hidden_dim) if hidden_dim is not None else 512
    cfg.num_hidden_layers = int(num_hidden_layers) if num_hidden_layers is not None else 2
    cfg.learning_rate = LEARNING_RATE
    cfg.batch_size = BATCH_SIZE
    cfg.rollout_schedule = tuple(int(k) for k in ROLLOUT_SCHEDULE)
    cfg.live_viewer = False
    cfg.visual_reporter = False
    cfg.update_comparison_on_exit = False
    cfg.use_torch_compile = False
    cfg.device = str(device)
    return cfg


def controller_timed_checkpoint_interval_minutes(args: argparse.Namespace) -> float:
    value = getattr(args, "timed_checkpoint_interval_minutes", None)
    if value is not None:
        return max(0.0, float(value))
    return float(tl.TrainConfig().timed_checkpoint_interval_minutes)


def initialize_controller_output_from_ae_mean(
    model: torch.nn.Module,
    mean: torch.Tensor,
    input_dim: int,
    output_dim: int,
) -> str:
    output_layer = getattr(model, "net", [None])[-1]
    if not isinstance(output_layer, torch.nn.Linear):
        raise TypeError("Expected MLPController final layer to be torch.nn.Linear.")
    target_mean = mean[int(input_dim) : int(input_dim) + int(output_dim)].to(
        device=output_layer.bias.device,
        dtype=output_layer.bias.dtype,
    )
    if int(target_mean.numel()) != int(output_dim):
        raise ValueError(f"AE feature mean output dim {target_mean.numel()} does not match controller output dim {output_dim}.")
    with torch.no_grad():
        output_layer.weight.zero_()
        output_layer.bias.zero_()
        output_layer.bias[: int(output_dim)].copy_(target_mean)
        if int(output_layer.bias.numel()) > int(output_dim):
            output_layer.bias[int(output_dim) :].fill_(-1.0)
    return "ae_feature_output_mean_bias_zero_weight"


def initialize_foot_roll_pin_logits(model: torch.nn.Module, value: float = -1.0) -> None:
    output_layer = getattr(model, "net", [None])[-1]
    if not isinstance(output_layer, torch.nn.Linear):
        return
    if int(output_layer.bias.numel()) < int(tl.FOOT_ROLL_PIN_OUTPUT_DIM):
        return
    with torch.no_grad():
        output_layer.weight[-int(tl.FOOT_ROLL_PIN_OUTPUT_DIM) :].zero_()
        output_layer.bias[-int(tl.FOOT_ROLL_PIN_OUTPUT_DIM) :].fill_(float(value))


def resolve_path(path_text: str | Path) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def normalize_ae4_checkpoint_path(path_text: str | Path) -> Path:
    path = Path(path_text)
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    try:
        legacy = LEGACY_AE4_PROJECTOR_DIR.resolve()
    except OSError:
        legacy = LEGACY_AE4_PROJECTOR_DIR
    if str(resolved).lower() == str(legacy).lower():
        return DEFAULT_AE4_PROJECTOR_DIR
    return resolved


def is_legacy_output_pose_ae4_checkpoint(path_text: str | Path) -> bool:
    path = Path(path_text)
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    if not resolved.is_file() or resolved.suffix.lower() != ".pt":
        return False
    try:
        raw = torch_load_cache(resolved, "cpu")
    except Exception:
        return False
    if not isinstance(raw, dict) or raw.get("kind") != "ik_pose_ae4":
        return False
    schema = raw.get("schema", {})
    if not isinstance(schema, dict):
        return False
    return str(schema.get("feature", "")) in LEGACY_OUTPUT_POSE_AE4_FEATURES


def canonical_viewer_ae4_checkpoint_path(path_text: str | Path) -> Path:
    resolved = normalize_ae4_checkpoint_path(path_text)
    default_path = default_ae4_checkpoint_path()
    if default_path is not None and is_legacy_output_pose_ae4_checkpoint(resolved):
        return default_path
    return resolved


def default_ae4_checkpoint_path() -> Path | None:
    resolved = normalize_ae4_checkpoint_path(DEFAULT_AE4_PROJECTOR_DIR)
    if is_ae4_projector_dir(resolved) or resolved.is_file():
        return resolved
    return None


def resolve_ae4_checkpoint_arg(args: argparse.Namespace) -> Path | None:
    raw = getattr(args, "ae4_checkpoint", None)
    if raw:
        return normalize_ae4_checkpoint_path(resolve_path(raw))
    raw_weight = getattr(args, "ae4_loss_weight", None)
    if raw_weight is None or float(raw_weight) == 0.0:
        return None
    return default_ae4_checkpoint_path()


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
    cache_key = (str(npz_text or ""), str(periodic_text or ""), str(nonperiodic_text or ""))
    cached = _RESOLVED_CLIP_SPECS_CACHE.get(cache_key)
    if cached is not None:
        return list(cached)
    specs: list[tuple[Path, bool]] = []
    for path in npz_paths_from_text(periodic_text or ""):
        specs.append((path, True))
    for path in npz_paths_from_text(nonperiodic_text or ""):
        specs.append((path, False))
    if specs:
        _RESOLVED_CLIP_SPECS_CACHE[cache_key] = list(specs)
        return specs
    if npz_text:
        specs = [(path, infer_cyclic_from_path(path)) for path in npz_paths_from_text(npz_text)]
        _RESOLVED_CLIP_SPECS_CACHE[cache_key] = list(specs)
        return specs
    if not DEFAULT_WALK_F.exists():
        raise FileNotFoundError(f"Default walk-forward NPZ not found: {DEFAULT_WALK_F}")
    specs = [(DEFAULT_WALK_F.resolve(), True)]
    _RESOLVED_CLIP_SPECS_CACHE[cache_key] = list(specs)
    return specs


def resolve_synthetic_clip_specs(npz_text: str | None, folder_text: str | None) -> list[tuple[Path, bool]]:
    paths: list[Path] = []
    if folder_text:
        paths.extend(npz_paths_from_text(folder_text))
    if npz_text:
        paths.extend(npz_paths_from_text(npz_text))
    seen: set[Path] = set()
    specs: list[tuple[Path, bool]] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        specs.append((resolved, False))
        seen.add(resolved)
    return specs


def resolve_clip_specs_from_checkpoint_metadata(ckpt: dict) -> list[tuple[Path, bool]]:
    metadata = ckpt.get("metadata", {})
    if not isinstance(metadata, dict):
        return []
    raw_paths = metadata.get("npz_paths", [])
    raw_folders = metadata.get("npz_folders", [])
    if not isinstance(raw_paths, list) or not raw_paths:
        return []
    if not isinstance(raw_folders, list) or len(raw_folders) != len(raw_paths):
        raise ValueError("AE metadata has npz_paths but no matching per-path cyclic npz_folders entries")
    cache_parts: list[tuple[str, bool]] = []
    for raw_path, raw_folder in zip(raw_paths, raw_folders):
        if not isinstance(raw_folder, dict) or "cyclic" not in raw_folder:
            raise ValueError("AE metadata npz_folders entries must include cyclic=true/false")
        cache_parts.append((str(raw_path), bool(raw_folder["cyclic"])))
    cache_key = tuple(cache_parts)
    cached = _AE_METADATA_SPECS_CACHE.get(cache_key)
    if cached is not None:
        return list(cached)
    specs: list[tuple[Path, bool]] = []
    seen: set[Path] = set()
    for raw_path, raw_folder in zip(raw_paths, raw_folders):
        if not isinstance(raw_folder, dict) or "cyclic" not in raw_folder:
            raise ValueError("AE metadata npz_folders entries must include cyclic=true/false")
        path = Path(str(raw_path)).resolve()
        if path in seen:
            continue
        if not path.exists():
            raise FileNotFoundError(f"AE metadata NPZ path does not exist: {path}")
        specs.append((path, bool(raw_folder["cyclic"])))
        seen.add(path)
    _AE_METADATA_SPECS_CACHE[cache_key] = list(specs)
    return specs


def load_clips(specs: list[tuple[Path, bool]], cfg: tl.TrainConfig) -> list[tl.MotionClip]:
    fast_key = specs_fast_cache_key(specs, cfg)
    fast_cached = _CLIP_FAST_CACHE.get(fast_key)
    if fast_cached is not None:
        return fast_cached
    key = specs_cache_key(specs, cfg)
    cached = _CLIP_CACHE.get(key)
    if cached is not None:
        _CLIP_FAST_CACHE[fast_key] = cached
        return cached
    clips = [load_motion_clip_cached(path, cfg, cyclic) for path, cyclic in specs]
    first_names = clips[0].body_names
    first_parents = clips[0].parents_body_list
    for clip in clips[1:]:
        if clip.body_names != first_names or clip.parents_body_list != first_parents:
            raise ValueError(f"Skeleton mismatch: {clip.path} vs {clips[0].path}")
    _CLIP_CACHE[key] = clips
    _CLIP_FAST_CACHE[fast_key] = clips
    return clips


def ensure_full_store_clips(store: SimpleClipStore) -> None:
    if all(isinstance(clip, tl.MotionClip) for clip in store.clips):
        return
    specs = [(Path(clip.path), bool(clip.cyclic_animation)) for clip in store.clips]
    clips = load_clips(specs, store.cfg)
    store.clips = clips
    store.prototype = clips[0]
    for clip in clips:
        clip._device_cache = {}


def mean_clip_root_speed_mps(clip: tl.MotionClip) -> float:
    root_pos = torch.as_tensor(clip.root_pos, dtype=torch.float32)
    period = int(getattr(clip, "cyclic_period", root_pos.shape[0] - 1))
    transition_count = min(int(root_pos.shape[0]) - 1, max(0, period))
    if transition_count <= 0:
        return 0.0
    delta_xz = root_pos[1 : transition_count + 1, [0, 2]] - root_pos[:transition_count, [0, 2]]
    return float(torch.linalg.vector_norm(delta_xz, dim=-1).mean().item() * float(clip.fps))


def default_walk_f_root_speed_mps(cfg: tl.TrainConfig) -> float:
    if not DEFAULT_WALK_F.exists():
        raise FileNotFoundError(f"Default walk-forward NPZ not found: {DEFAULT_WALK_F}")
    key = (path_signature(DEFAULT_WALK_F), cfg_cache_key(cfg))
    cached = _ROOT_SPEED_CACHE.get(key)
    if cached is not None:
        return cached
    speed = mean_clip_root_speed_mps(tl.MotionClip(DEFAULT_WALK_F, cfg, cyclic_animation=True))
    _ROOT_SPEED_CACHE[key] = speed
    return speed


def latest_simple_ae_checkpoint() -> Path:
    if DEFAULT_SIMPLE_AE_CHECKPOINT.is_file():
        return DEFAULT_SIMPLE_AE_CHECKPOINT.resolve()
    candidates: list[Path] = []
    for run_dir in RUNS_DIR.glob(DEFAULT_AE_GLOB):
        ckpt_dir = run_dir / "checkpoints"
        if ckpt_dir.exists():
            candidates.extend(sorted(ckpt_dir.glob("*_best.pt"), key=lambda p: p.stat().st_mtime, reverse=True))
    if not candidates:
        raise FileNotFoundError(f"No simple AE checkpoints found under {RUNS_DIR}")
    return sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0].resolve()


class IKMotionAE2(torch.nn.Module):
    def __init__(self, dim: int, cfg: dict[str, object]):
        super().__init__()
        latent_dim = int(cfg.get("latent_dim", 32))
        hidden_dim = int(cfg.get("hidden_dim", 256))
        num_hidden_layers = int(cfg.get("num_hidden_layers", 2))
        layers: list[torch.nn.Module] = []
        in_dim = int(dim)
        for _ in range(num_hidden_layers):
            layers.extend((torch.nn.Linear(in_dim, hidden_dim), torch.nn.LayerNorm(hidden_dim), torch.nn.GELU()))
            in_dim = hidden_dim
        layers.extend((torch.nn.Linear(in_dim, latent_dim), torch.nn.GELU()))
        in_dim = latent_dim
        for _ in range(num_hidden_layers):
            layers.extend((torch.nn.Linear(in_dim, hidden_dim), torch.nn.LayerNorm(hidden_dim), torch.nn.GELU()))
            in_dim = hidden_dim
        layers.append(torch.nn.Linear(in_dim, int(dim)))
        self.net = torch.nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class PinAwareAE3(torch.nn.Module):
    def __init__(self, input_dim: int, cfg: dict[str, object]):
        super().__init__()
        hidden_dim = int(cfg.get("hidden_dim", 256))
        num_hidden_layers = int(cfg.get("num_hidden_layers", 2))
        dropout = float(cfg.get("dropout", 0.0))
        layers: list[torch.nn.Module] = []
        dim = int(input_dim)
        for _ in range(max(1, num_hidden_layers)):
            layers.extend(
                (
                    torch.nn.Linear(dim, hidden_dim),
                    torch.nn.LayerNorm(hidden_dim),
                    torch.nn.GELU(),
                    torch.nn.Dropout(dropout),
                )
            )
            dim = hidden_dim
        layers.append(torch.nn.Linear(dim, 2))
        self.net = torch.nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class ContactPredictorAE6(torch.nn.Module):
    def __init__(self, input_dim: int, output_dim: int, cfg: dict[str, object]):
        super().__init__()
        hidden_dim = int(cfg.get("hidden_dim", 256))
        first_hidden_dim = int(cfg.get("first_hidden_dim", 0) or 0)
        num_hidden_layers = int(cfg.get("num_hidden_layers", 2))
        layers: list[torch.nn.Module] = []
        dim = int(input_dim)
        for layer_idx in range(max(0, num_hidden_layers)):
            out_dim = first_hidden_dim if layer_idx == 0 and first_hidden_dim > 0 else hidden_dim
            layers.extend((torch.nn.Linear(dim, out_dim), torch.nn.LayerNorm(out_dim), torch.nn.GELU()))
            dim = out_dim
        layers.append(torch.nn.Linear(dim, int(output_dim)))
        self.net = torch.nn.Sequential(*layers)
        self.output_mode = str(cfg.get("contact_output_mode", "sigmoid_logits"))

    def forward_raw(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        raw = self.forward_raw(x)
        if self.output_mode == "clamped_linear":
            return raw.clamp(0.0, 1.0)
        return torch.sigmoid(raw)


class IKPoseAE4Prior(torch.nn.Module):
    def __init__(self, input_dim: int, output_dim: int, cfg: dict[str, object]):
        super().__init__()
        latent_dim = int(cfg.get("latent_dim", 16))
        hidden_dim = int(cfg.get("hidden_dim", 192))
        num_hidden_layers = int(cfg.get("num_hidden_layers", 2))
        self.decoder_root_condition = bool(cfg.get("decoder_root_condition", False))
        self.root_motion_dim = int(cfg.get("root_motion_dim", 0))
        if self.decoder_root_condition and 0 < self.root_motion_dim < int(input_dim):
            enc_layers: list[torch.nn.Module] = []
            dim = int(input_dim)
            for _ in range(max(1, num_hidden_layers)):
                enc_layers.extend((torch.nn.Linear(dim, hidden_dim), torch.nn.LayerNorm(hidden_dim), torch.nn.GELU()))
                dim = hidden_dim
            enc_layers.append(torch.nn.Linear(dim, latent_dim))
            dec_layers: list[torch.nn.Module] = []
            dim = latent_dim + self.root_motion_dim
            for _ in range(max(1, num_hidden_layers)):
                dec_layers.extend((torch.nn.Linear(dim, hidden_dim), torch.nn.LayerNorm(hidden_dim), torch.nn.GELU()))
                dim = hidden_dim
            dec_layers.append(torch.nn.Linear(dim, int(output_dim)))
            self.encoder = torch.nn.Sequential(*enc_layers)
            self.decoder = torch.nn.Sequential(*dec_layers)
            self.net = None
            return
        self.decoder_root_condition = False
        layers: list[torch.nn.Module] = []
        in_dim = int(input_dim)
        for _ in range(max(1, num_hidden_layers)):
            layers.extend((torch.nn.Linear(in_dim, hidden_dim), torch.nn.LayerNorm(hidden_dim), torch.nn.GELU()))
            in_dim = hidden_dim
        layers.extend((torch.nn.Linear(in_dim, latent_dim), torch.nn.GELU()))
        in_dim = latent_dim
        for _ in range(max(1, num_hidden_layers)):
            layers.extend((torch.nn.Linear(in_dim, hidden_dim), torch.nn.LayerNorm(hidden_dim), torch.nn.GELU()))
            in_dim = hidden_dim
        layers.append(torch.nn.Linear(in_dim, int(output_dim)))
        self.net = torch.nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.decoder_root_condition:
            root = x[:, : self.root_motion_dim]
            latent = self.encoder(x)
            return self.decoder(torch.cat((latent, root), dim=-1))
        assert self.net is not None
        return self.net(x)


def load_simple_ae(
    path: Path,
    device: torch.device,
    expected_body_mode: str | None = None,
) -> tuple[SimpleAutoencoder, torch.Tensor, torch.Tensor, dict]:
    expected_key = tl.normalized_body_mode(expected_body_mode) if expected_body_mode is not None else ""
    key = (path_signature(path), str(device), expected_key)
    cached = _AE_CACHE.get(key)
    if cached is not None:
        return cached
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    if ckpt.get("kind") not in {SIMPLE_CONTROLLER_AE_KIND, LEGACY_SIMPLE_AE_KIND}:
        raise ValueError(f"Not a simple controller IO AE checkpoint: {path}")
    ae_cfg = SimpleAEConfig(**ckpt["config"])
    schema = dict(ckpt["schema"])
    if schema.get("output_reference_root") != tl.OUTPUT_REFERENCE_ROOT:
        raise ValueError(
            f"Simple AE checkpoint uses output_reference_root={schema.get('output_reference_root')!r}; "
            f"expected {tl.OUTPUT_REFERENCE_ROOT!r}: {path}"
        )
    checkpoint_prediction = str(schema.get("output_prediction_mode", tl.OUTPUT_PREDICTION_MODE_ABSOLUTE)).lower().strip()
    if checkpoint_prediction != tl.normalized_output_prediction_mode():
        raise ValueError(
            f"Simple AE checkpoint uses output_prediction_mode={checkpoint_prediction!r}; "
            f"expected {tl.normalized_output_prediction_mode()!r}: {path}"
        )
    if schema.get("ik_schema_version") != tl.IK_SCHEMA_VERSION or schema.get("ik_pole_reference") != tl.IK_POLE_REFERENCE:
        raise ValueError(
            "Simple AE checkpoint uses a legacy IK schema; retrain the AE with "
            f"ik_schema_version={tl.IK_SCHEMA_VERSION} and ik_pole_reference={tl.IK_POLE_REFERENCE!r}: {path}"
        )
    if expected_body_mode is not None:
        raw_body_mode = schema.get("body_mode")
        metadata = ckpt.get("metadata", {})
        if raw_body_mode is None and isinstance(metadata, dict):
            raw_body_mode = metadata.get("body_mode")
        if raw_body_mode is None:
            raise ValueError(f"Simple AE checkpoint is missing body_mode; expected {expected_body_mode!r}: {path}")
        checkpoint_body_mode = tl.normalized_body_mode(raw_body_mode)
        expected = tl.normalized_body_mode(expected_body_mode)
        if checkpoint_body_mode != expected:
            raise ValueError(f"Simple AE body_mode={checkpoint_body_mode!r}; expected {expected!r}: {path}")
    model = SimpleAutoencoder(int(schema["total_dim"]), ae_cfg).to(device)
    model.load_state_dict(ckpt["model"])
    model._simple_ae_schema = schema  # type: ignore[attr-defined]
    model._simple_ae_config = dict(ckpt["config"])  # type: ignore[attr-defined]
    model.eval()
    for param in model.parameters():
        param.requires_grad_(False)
    mean = ckpt["mean"].to(device=device, dtype=torch.float32)
    std = ckpt["std"].to(device=device, dtype=torch.float32).clamp_min(1e-8)
    cached_value = (model, mean, std, ckpt)
    _AE_CACHE[key] = cached_value
    return cached_value


def load_ik_motion_ae2(
    path: Path,
    device: torch.device,
    expected_body_mode: str | None = None,
) -> tuple[torch.nn.Module, torch.Tensor, torch.Tensor, dict]:
    expected_key = tl.normalized_body_mode(expected_body_mode) if expected_body_mode is not None else ""
    key = (path_signature(path), str(device), expected_key)
    cached = _AE2_CACHE.get(key)
    if cached is not None:
        return cached
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    schema = dict(ckpt.get("schema", {}))
    if schema.get("feature") != IK_MOTION_AE_FEATURE_ROOT_POSE_WINDOW:
        raise ValueError(
            f"AE5 must use root-conditioned pose-window feature={IK_MOTION_AE_FEATURE_ROOT_POSE_WINDOW!r}; "
            f"got {schema.get('feature')!r}: {path}"
        )
    if schema.get("output_reference_root") != tl.OUTPUT_REFERENCE_ROOT:
        raise ValueError(
            f"IK motion AE2 uses output_reference_root={schema.get('output_reference_root')!r}; "
            f"expected {tl.OUTPUT_REFERENCE_ROOT!r}: {path}"
        )
    if expected_body_mode is not None:
        checkpoint_body_mode = tl.normalized_body_mode(schema.get("body_mode"))
        expected = tl.normalized_body_mode(expected_body_mode)
        if checkpoint_body_mode != expected:
            raise ValueError(f"IK motion AE2 body_mode={checkpoint_body_mode!r}; expected {expected!r}: {path}")
    cfg = dict(ckpt.get("config", {}))
    model = IKMotionAE2(int(schema["total_dim"]), cfg).to(device)
    model.load_state_dict(ckpt["model"])
    model.eval()
    for param in model.parameters():
        param.requires_grad_(False)
    model._ik_motion_ae2_schema = schema  # type: ignore[attr-defined]
    model._ik_motion_ae2_config = cfg  # type: ignore[attr-defined]
    mean = ckpt["mean"].to(device=device, dtype=torch.float32)
    std = ckpt["std"].to(device=device, dtype=torch.float32).clamp_min(1e-8)
    cached_value = (model, mean, std, ckpt)
    _AE2_CACHE[key] = cached_value
    return cached_value


def load_ae5_checkpoint(
    path: Path,
    device: torch.device,
    expected_body_mode: str | None = None,
) -> tuple[torch.nn.Module, torch.Tensor, torch.Tensor, dict]:
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    schema = ckpt.get("schema", {}) if isinstance(ckpt, dict) else {}
    if isinstance(schema, dict) and schema.get("feature") == IK_MOTION_AE_FEATURE_ROOT_POSE_WINDOW:
        return load_ik_motion_ae2(path, device, expected_body_mode)
    if isinstance(schema, dict) and schema.get("ae_feature_mode") in AE5_SIMPLE_DELTA_FEATURE_MODES:
        if normalized_ae_score_scope(schema.get("ae_score_scope", AE_SCORE_SCOPE_OUTPUT)) != AE_SCORE_SCOPE_FULL_WINDOW:
            raise ValueError(
                "Temporal SimpleAE AE5 checkpoints must use ae_score_scope='full_window'; "
                f"got {schema.get('ae_score_scope')!r}: {path}"
            )
        return load_simple_ae(path, device, expected_body_mode)
    raise ValueError(
        "AE5 checkpoint must use either "
        f"root-conditioned pose-window feature={IK_MOTION_AE_FEATURE_ROOT_POSE_WINDOW!r} or a temporal "
        f"SimpleAE delta feature mode in {sorted(AE5_SIMPLE_DELTA_FEATURE_MODES)!r} with ae_score_scope='full_window'; "
        f"got feature={schema.get('feature') if isinstance(schema, dict) else None!r} "
        f"mode={schema.get('ae_feature_mode') if isinstance(schema, dict) else None!r} "
        f"scope={schema.get('ae_score_scope') if isinstance(schema, dict) else None!r}: {path}"
    )


def load_pin_aware_ae3(
    path: Path,
    device: torch.device,
    expected_body_mode: str | None = None,
) -> tuple[torch.nn.Module, torch.Tensor, torch.Tensor, torch.Tensor | None, dict]:
    expected_key = tl.normalized_body_mode(expected_body_mode) if expected_body_mode is not None else ""
    key = (path_signature(path), str(device), expected_key)
    cached = _AE3_CACHE.get(key)
    if cached is not None:
        return cached
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    if ckpt.get("kind") != "ik_pin_aware_ae":
        raise ValueError(f"Not an IK pin-aware AE3 checkpoint: {path}")
    schema = dict(ckpt.get("schema", {}))
    if schema.get("feature") != "controller_input_to_output_pin_logits":
        raise ValueError(f"AE3 checkpoint does not predict controller input -> pin logits: {path}")
    if schema.get("output_reference_root") != tl.OUTPUT_REFERENCE_ROOT:
        raise ValueError(
            f"AE3 uses output_reference_root={schema.get('output_reference_root')!r}; "
            f"expected {tl.OUTPUT_REFERENCE_ROOT!r}: {path}"
        )
    checkpoint_prediction = str(schema.get("output_prediction_mode", tl.OUTPUT_PREDICTION_MODE_ABSOLUTE)).lower().strip()
    if checkpoint_prediction != tl.normalized_output_prediction_mode():
        raise ValueError(
            f"AE3 uses output_prediction_mode={checkpoint_prediction!r}; "
            f"expected {tl.normalized_output_prediction_mode()!r}: {path}"
        )
    if expected_body_mode is not None:
        checkpoint_body_mode = tl.normalized_body_mode(schema.get("body_mode"))
        expected = tl.normalized_body_mode(expected_body_mode)
        if checkpoint_body_mode != expected:
            raise ValueError(f"AE3 body_mode={checkpoint_body_mode!r}; expected {expected!r}: {path}")
    if int(schema.get("output_dim", 0)) != 2:
        raise ValueError(f"AE3 output_dim must be 2 left/right pin logits: {path}")
    cfg = dict(ckpt.get("config", {}))
    model = PinAwareAE3(int(schema["input_dim"]), cfg).to(device)
    model.load_state_dict(ckpt["model"])
    model.eval()
    for param in model.parameters():
        param.requires_grad_(False)
    mean = ckpt["mean"].to(device=device, dtype=torch.float32)
    std = ckpt["std"].to(device=device, dtype=torch.float32).clamp_min(1e-8)
    pos_weight = None
    metadata = ckpt.get("metadata", {})
    raw_pos_weight = metadata.get("pos_weight") if isinstance(metadata, dict) else None
    if isinstance(raw_pos_weight, (list, tuple)) and len(raw_pos_weight) == 2:
        pos_weight = torch.tensor(raw_pos_weight, dtype=torch.float32, device=device).clamp_min(1e-8)
    cached_value = (model, mean, std, pos_weight, ckpt)
    _AE3_CACHE[key] = cached_value
    return cached_value


def load_contact_ae6(
    path: Path,
    device: torch.device,
    expected_body_mode: str | None = None,
) -> tuple[torch.nn.Module, torch.Tensor, torch.Tensor, dict]:
    expected_key = tl.normalized_body_mode(expected_body_mode) if expected_body_mode is not None else ""
    key = (path_signature(path), str(device), expected_key)
    cached = _AE6_CACHE.get(key)
    if cached is not None:
        return cached
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    if ckpt.get("kind") != "ae6_contact_predictor":
        raise ValueError(f"Not an AE6 contact predictor checkpoint: {path}")
    schema = dict(ckpt.get("schema", {}))
    cfg = dict(ckpt.get("config", {}))
    metadata = dict(ckpt.get("metadata", {}))
    if expected_body_mode is not None:
        checkpoint_body_mode = tl.normalized_body_mode(cfg.get("body_mode", metadata.get("body_mode")))
        expected = tl.normalized_body_mode(expected_body_mode)
        if checkpoint_body_mode != expected:
            raise ValueError(f"AE6 body_mode={checkpoint_body_mode!r}; expected {expected!r}: {path}")
    if schema.get("output_reference_root") != tl.OUTPUT_REFERENCE_ROOT:
        raise ValueError(
            f"AE6 uses output_reference_root={schema.get('output_reference_root')!r}; "
            f"expected {tl.OUTPUT_REFERENCE_ROOT!r}: {path}"
        )
    output_mode = str(cfg.get("contact_output_mode", "sigmoid_logits"))
    if output_mode != "sigmoid_logits":
        raise ValueError(f"AE6 contact_output_mode={output_mode!r}; this controller run expects 'sigmoid_logits': {path}")
    mean = ckpt["mean"].to(device=device, dtype=torch.float32)
    std = ckpt["std"].to(device=device, dtype=torch.float32).clamp_min(1.0e-8)
    contact_names = list(ckpt.get("contact_names", metadata.get("contact_names", ("contact_l", "contact_r"))))
    model = ContactPredictorAE6(int(mean.numel()), len(contact_names), cfg).to(device)
    model.load_state_dict(ckpt["model"])
    model.eval()
    for param in model.parameters():
        param.requires_grad_(False)
    model._ae6_schema = schema  # type: ignore[attr-defined]
    model._ae6_config = cfg  # type: ignore[attr-defined]
    model._ae6_contact_names = contact_names  # type: ignore[attr-defined]
    cached_value = (model, mean, std, ckpt)
    _AE6_CACHE[key] = cached_value
    return cached_value


class IKPoseBankProjectorPrior:
    """Training-side wrapper for the AE4 pose-bank projector used by the viz."""

    def __init__(self, checkpoint_dir: Path, device: torch.device) -> None:
        self.checkpoint_dir = Path(checkpoint_dir).resolve()
        self.projector = posebank.PoseBankProjector(self.checkpoint_dir)
        self.device = device
        ckpt = torch.load(self.checkpoint_dir / "best_model.pt", map_location="cpu", weights_only=False)
        stats = posebank.DatasetStats.load(self.checkpoint_dir / "stats.npz")
        self.model = posebank.RootConditionedPoseAE(
            latent_dim=int(ckpt["latent_dim"]),
            hidden_dim=int(ckpt.get("hidden_dim", 256)),
        ).to(device=device, dtype=torch.float32)
        self.model.load_state_dict(ckpt["model_state_dict"])
        self.model.eval()
        for parameter in self.model.parameters():
            parameter.requires_grad_(False)
        self.pose_mean = torch.as_tensor(stats.pose_mean, dtype=torch.float32, device=device)
        self.pose_std = torch.as_tensor(stats.pose_std, dtype=torch.float32, device=device).clamp_min(1.0e-8)
        self.root_mean = torch.as_tensor(stats.root_mean, dtype=torch.float32, device=device)
        self.root_std = torch.as_tensor(stats.root_std, dtype=torch.float32, device=device).clamp_min(1.0e-8)
        self.root_weight = 0.35
        self._prepared_store_banks: dict[tuple[str, ...], dict[str, torch.Tensor]] = {}
        self._ik_pose_ae4_schema = {
            "kind": "ik_pose_bank_projector",
            "feature": "root_conditioned_pose_bank_projection",
            "deadzone_m": float(AE4_POSE_DISTANCE_DEADZONE_M),
        }

    def _store_key(self, store: "SimpleClipStore") -> tuple[str, ...]:
        return tuple(str(Path(str(clip.path)).resolve()).lower() for clip in store.clips)

    def prepare_store(self, store: "SimpleClipStore") -> dict[str, torch.Tensor]:
        key = self._store_key(store)
        cached = self._prepared_store_banks.get(key)
        if cached is not None:
            return cached
        pose_dim = int(self.pose_mean.numel())
        root_dim = int(self.root_mean.numel())
        clip_banks: list[dict[str, np.ndarray]] = []
        max_frames = 1
        for clip in store.clips:
            clip_path = Path(str(clip.path))
            clip_arrays = self.projector.clip(clip_path)
            bank_np = self.projector.clip_pose_bank(clip_path, clip_arrays)
            clip_banks.append(bank_np)
            max_frames = max(max_frames, int(bank_np["poses"].shape[0]))
        clip_count = len(clip_banks)
        poses = torch.zeros((clip_count, max_frames, pose_dim), dtype=torch.float32, device=self.device)
        roots = torch.zeros((clip_count, max_frames, root_dim), dtype=torch.float32, device=self.device)
        pose_norm = torch.zeros((clip_count, max_frames, pose_dim), dtype=torch.float32, device=self.device)
        root_norm = torch.zeros((clip_count, max_frames, root_dim), dtype=torch.float32, device=self.device)
        pin_labels = torch.zeros(
            (clip_count, max_frames, int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)),
            dtype=torch.float32,
            device=self.device,
        )
        valid = torch.zeros((clip_count, max_frames), dtype=torch.bool, device=self.device)
        for clip_i, bank_np in enumerate(clip_banks):
            frame_count = int(bank_np["poses"].shape[0])
            valid[clip_i, :frame_count] = True
            poses[clip_i, :frame_count] = torch.as_tensor(bank_np["poses"], dtype=torch.float32, device=self.device)
            roots[clip_i, :frame_count] = torch.as_tensor(bank_np["roots"], dtype=torch.float32, device=self.device)
            pose_norm[clip_i, :frame_count] = torch.as_tensor(
                bank_np["pose_norm"], dtype=torch.float32, device=self.device
            )
            root_norm[clip_i, :frame_count] = torch.as_tensor(
                bank_np["root_norm"], dtype=torch.float32, device=self.device
            )
            if frame_count > 0:
                frame_idx = torch.arange(frame_count, dtype=torch.long, device=self.device)
                clip_ids = torch.full((frame_count,), int(clip_i), dtype=torch.long, device=self.device)
                if bool(store.clips[int(clip_i)].cyclic_animation):
                    prev_idx = frame_idx - 1
                else:
                    prev_idx = (frame_idx - 1).clamp_min(0)
                prev_vec, _prev_pelvis, _prev_payload = target_state(store, clip_ids, prev_idx)
                cur_vec, _cur_pelvis, _cur_payload = target_state(store, clip_ids, frame_idx)
                prev_root_pos, prev_root_rot, _prev_yaw, _prev_heading = store.root_state(clip_ids, prev_idx)
                cur_root_pos, cur_root_rot, _cur_yaw, _cur_heading = store.root_state(clip_ids, frame_idx)
                pin_labels[clip_i, :frame_count] = pose_bank_pin_labels_from_ik_vectors(
                    store,
                    prev_root_pos,
                    prev_root_rot,
                    prev_vec,
                    cur_root_pos,
                    cur_root_rot,
                    cur_vec,
                ).to(device=self.device, dtype=torch.float32)
        cached = {
            "poses": poses,
            "roots": roots,
            "pose_norm": pose_norm,
            "root_norm": root_norm,
            "pose_norm_sq": pose_norm.square().sum(dim=-1),
            "root_norm_sq": root_norm.square().sum(dim=-1),
            "pin_labels": pin_labels,
            "valid": valid,
        }
        self._prepared_store_banks[key] = cached
        return cached

    def _project_pose_vector(self, pose_vec: torch.Tensor) -> torch.Tensor:
        pose_vec = pose_vec.to(device=self.device, dtype=torch.float32)
        if int(pose_vec.shape[-1]) != int(posebank.POSE_DIM):
            raise ValueError(f"AE4 pose-bank query dim {int(pose_vec.shape[-1])}, expected {int(posebank.POSE_DIM)}")
        rot = tl.clean_6d(pose_vec[:, : posebank.ROT6D_DIM].reshape(-1, 6)).reshape(pose_vec.shape[0], posebank.ROT6D_DIM)
        return torch.cat((rot, pose_vec[:, posebank.ROT6D_DIM : posebank.ROT6D_DIM + 3]), dim=-1)

    def query_pose_vectors_from_output(
        self,
        store: "SimpleClipStore",
        pelvis_pos: torch.Tensor,
        global_rot: torch.Tensor,
        root_rot: torch.Tensor,
    ) -> torch.Tensor:
        if int(global_rot.shape[1]) != int(posebank.NUM_BONES - 1):
            raise ValueError(
                f"AE4 pose-bank expected {int(posebank.NUM_BONES - 1)} body bones, got {int(global_rot.shape[1])}"
            )
        local_rot_list: list[torch.Tensor] = [root_rot]
        for joint_index, parent in enumerate(store.prototype.parents_body_list):
            if parent < 0:
                local_rot_j = global_rot[:, joint_index] @ root_rot.transpose(-1, -2)
            else:
                local_rot_j = global_rot[:, joint_index] @ global_rot[:, parent].transpose(-1, -2)
            local_rot_list.append(local_rot_j)
        local_rot = torch.stack(local_rot_list, dim=1)
        rot6 = tl.rotmat_to_6d(local_rot).reshape(global_rot.shape[0], -1)
        return self._project_pose_vector(torch.cat((rot6, pelvis_pos.to(dtype=rot6.dtype)), dim=-1))

    def _pose_vectors_to_world_pose(
        self,
        store: "SimpleClipStore",
        pose_vec: torch.Tensor,
        root_pos: torch.Tensor,
        root_rot: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        b = int(pose_vec.shape[0])
        local_rot6 = pose_vec[:, : posebank.ROT6D_DIM].reshape(b, posebank.NUM_BONES, 6)
        local_rot = tl.rotation_6d_to_matrix(local_rot6.reshape(-1, 6)).reshape(b, posebank.NUM_BONES, 3, 3)
        body_local_rot = local_rot[:, 1:]
        offsets = store.local_offsets.to(device=pose_vec.device, dtype=pose_vec.dtype).unsqueeze(0).expand(b, -1, -1).clone()
        offsets[:, int(store.pelvis)] = pose_vec[:, posebank.ROT6D_DIM : posebank.ROT6D_DIM + 3]
        global_pos_list: list[torch.Tensor] = []
        global_rot_list: list[torch.Tensor] = []
        for joint_index, parent in enumerate(store.prototype.parents_body_list):
            local_rot_j = body_local_rot[:, joint_index]
            if parent < 0:
                rot_j = local_rot_j @ root_rot
                pos_j = torch.matmul(offsets[:, joint_index].unsqueeze(1), root_rot).squeeze(1) + root_pos
            else:
                parent_rot = global_rot_list[parent]
                parent_pos = global_pos_list[parent]
                rot_j = local_rot_j @ parent_rot
                pos_j = torch.matmul(offsets[:, joint_index].unsqueeze(1), parent_rot).squeeze(1) + parent_pos
            global_rot_list.append(rot_j)
            global_pos_list.append(pos_j)
        return torch.stack(global_pos_list, dim=1), torch.stack(global_rot_list, dim=1)

    def project_rows(
        self,
        pose_store: "SimpleClipStore",
        source_store: "SimpleClipStore",
        clip_ids: torch.Tensor,
        cur_idx: torch.Tensor,
        query_pose_vec: torch.Tensor,
        target_root_pos: torch.Tensor,
        target_root_rot: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        prepared = self.prepare_store(source_store)
        clip_ids = clip_ids.to(device=self.device, dtype=torch.long)
        frame_rows_t = source_store.frame_index(clip_ids, cur_idx) - source_store.frame_offsets.index_select(0, clip_ids)
        frame_rows = frame_rows_t.to(device=self.device, dtype=torch.long)
        query_pose_vec = self._project_pose_vector(query_pose_vec)
        query_root = prepared["roots"][clip_ids, frame_rows]
        query_pose_n = (query_pose_vec - self.pose_mean) / self.pose_std
        query_root_n = (query_root - self.root_mean) / self.root_std
        pred_pose_n = self.model(query_pose_n, query_root_n)
        ae_pose_vec = self._project_pose_vector(pred_pose_n * self.pose_std + self.pose_mean)
        ae_pose_n = (ae_pose_vec - self.pose_mean) / self.pose_std
        bank_pose_norm = prepared["pose_norm"].index_select(0, clip_ids)
        bank_root_norm = prepared["root_norm"].index_select(0, clip_ids)
        bank_pose_sq = prepared["pose_norm_sq"].index_select(0, clip_ids)
        bank_root_sq = prepared["root_norm_sq"].index_select(0, clip_ids)
        bank_valid = prepared["valid"].index_select(0, clip_ids)
        pose_d = (
            ae_pose_n.square().sum(dim=-1, keepdim=True)
            + bank_pose_sq
            - 2.0 * torch.einsum("bfd,bd->bf", bank_pose_norm, ae_pose_n)
        )
        root_d = (
            query_root_n.square().sum(dim=-1, keepdim=True)
            + bank_root_sq
            - 2.0 * torch.einsum("bfd,bd->bf", bank_root_norm, query_root_n)
        )
        dist = pose_d + float(self.root_weight) * root_d
        dist = dist.masked_fill(~bank_valid, 1.0e12)
        best_idx = dist.argmin(dim=-1)
        best_dist = dist.gather(1, best_idx.unsqueeze(-1)).squeeze(-1)
        dataset_pose = prepared["poses"][clip_ids, best_idx]
        world_pos, world_rot = self._pose_vectors_to_world_pose(
            pose_store,
            dataset_pose,
            target_root_pos.to(device=self.device, dtype=torch.float32),
            target_root_rot.to(device=self.device, dtype=torch.float32),
        )
        return {
            "query_pose_vec": query_pose_vec,
            "ae_pose_vec": ae_pose_vec,
            "target_pose_vec": dataset_pose,
            "bank_index": best_idx,
            "bank_distance": best_dist,
            "target_pin_labels": prepared["pin_labels"][clip_ids, best_idx].detach(),
            "world_pos": world_pos,
            "world_rot": world_rot,
        }

    def target_positions_for_rows(
        self,
        pose_store: "SimpleClipStore",
        source_store: "SimpleClipStore",
        clip_ids: torch.Tensor,
        cur_idx: torch.Tensor,
        query_pose_vec: torch.Tensor,
        target_root_pos: torch.Tensor,
        target_root_rot: torch.Tensor,
    ) -> torch.Tensor:
        return self.project_rows(
            pose_store,
            source_store,
            clip_ids,
            cur_idx,
            query_pose_vec,
            target_root_pos,
            target_root_rot,
        )["world_pos"]


def load_ik_pose_ae4(
    path: Path,
    device: torch.device,
    expected_body_mode: str | None = None,
) -> tuple[object, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, dict]:
    if is_ae4_projector_dir(path):
        key = (ae4_projector_signature(path), str(device), "pose_bank_projector")
        cached = _AE4_CACHE.get(key)
        if cached is not None:
            return cached
        model = IKPoseBankProjectorPrior(path, device)
        empty = torch.empty((0,), dtype=torch.float32, device=device)
        ckpt = {
            "kind": "ik_pose_bank_projector",
            "schema": dict(model._ik_pose_ae4_schema),
            "checkpoint_dir": str(Path(path).resolve()),
        }
        cached_value = (model, empty, empty, empty, empty, ckpt)
        _AE4_CACHE[key] = cached_value
        return cached_value
    expected_key = tl.normalized_body_mode(expected_body_mode) if expected_body_mode is not None else ""
    key = (path_signature(path), str(device), expected_key)
    cached = _AE4_CACHE.get(key)
    if cached is not None:
        return cached
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    if ckpt.get("kind") != "ik_pose_ae4":
        raise ValueError(f"Not an IK pose AE4 checkpoint: {path}")
    schema = dict(ckpt.get("schema", {}))
    if schema.get("feature") not in {
        "ae4_root_context_output_pose_to_full_ik",
        "ae4_root_context_full_output_pose_to_full_ik",
        "ae4_root_context_to_full_ik_pose",
        "ae4_root_context_masked_pelvis_height_full_output_pose_to_full_ik",
    }:
        raise ValueError(f"AE4 checkpoint is not the output-pose prior: {path}")
    if schema.get("output_reference_root") != tl.OUTPUT_REFERENCE_ROOT:
        raise ValueError(
            f"AE4 uses output_reference_root={schema.get('output_reference_root')!r}; "
            f"expected {tl.OUTPUT_REFERENCE_ROOT!r}: {path}"
        )
    checkpoint_prediction = str(schema.get("output_prediction_mode", tl.OUTPUT_PREDICTION_MODE_ABSOLUTE)).lower().strip()
    if checkpoint_prediction != tl.normalized_output_prediction_mode():
        raise ValueError(
            f"AE4 uses output_prediction_mode={checkpoint_prediction!r}; "
            f"expected {tl.normalized_output_prediction_mode()!r}: {path}"
        )
    if expected_body_mode is not None:
        checkpoint_body_mode = tl.normalized_body_mode(schema.get("body_mode"))
        expected = tl.normalized_body_mode(expected_body_mode)
        if checkpoint_body_mode != expected:
            raise ValueError(f"AE4 body_mode={checkpoint_body_mode!r}; expected {expected!r}: {path}")
    cfg = dict(ckpt.get("config", {}))
    model = IKPoseAE4Prior(int(schema["input_dim"]), int(schema["output_dim"]), cfg).to(device)
    model.load_state_dict(ckpt["model"])
    model.eval()
    for param in model.parameters():
        param.requires_grad_(False)
    input_mean = ckpt["input_mean"].to(device=device, dtype=torch.float32)
    input_std = ckpt["input_std"].to(device=device, dtype=torch.float32).clamp_min(1e-8)
    target_mean = ckpt["target_mean"].to(device=device, dtype=torch.float32)
    target_std = ckpt["target_std"].to(device=device, dtype=torch.float32).clamp_min(1e-8)
    model._ik_pose_ae4_schema = schema  # type: ignore[attr-defined]
    cached_value = (model, input_mean, input_std, target_mean, target_std, ckpt)
    _AE4_CACHE[key] = cached_value
    return cached_value


def transition_feature_horizon(cfg: tl.TrainConfig) -> int:
    root_lookahead_steps = max(0, int(getattr(cfg, "root_lookahead_steps", 0)))
    return max(int(cfg.future_window), root_lookahead_steps + 1)


def max_start_for_clip(clip: tl.MotionClip, cfg: tl.TrainConfig, rollout_k: int) -> int:
    if clip.cyclic_animation:
        return int(clip.cyclic_period) - 1
    return int(clip.T) - transition_feature_horizon(cfg) - max(1, int(rollout_k))


def max_training_start_for_clip(clip: tl.MotionClip, cfg: tl.TrainConfig, rollout_k: int = 1) -> int:
    if clip.cyclic_animation:
        return int(clip.cyclic_period) - 1
    one_step_max = int(clip.T) - transition_feature_horizon(cfg) - 1
    rollout_max = int(clip.T) - transition_feature_horizon(cfg) - max(1, int(rollout_k))
    return rollout_max if rollout_max >= 1 else one_step_max


def normalize_clip_id_filter(store: SimpleClipStore, clip_ids: tuple[int, ...] | None = None) -> tuple[int, ...]:
    if clip_ids is None:
        return tuple(range(len(store.clips)))
    return tuple(int(clip_id) for clip_id in clip_ids)


def build_start_pool(
    store: SimpleClipStore,
    rollout_k: int,
    min_start: int = 1,
    clip_ids: tuple[int, ...] | None = None,
) -> StartPool:
    min_start = max(1, int(min_start))
    clip_chunks: list[torch.Tensor] = []
    start_chunks: list[torch.Tensor] = []
    for clip_id in normalize_clip_id_filter(store, clip_ids):
        clip = store.clips[int(clip_id)]
        max_start = max_start_for_clip(clip, store.cfg, rollout_k)
        if max_start < min_start:
            continue
        starts = torch.arange(min_start, max_start + 1, dtype=torch.long, device=store.device)
        clip_chunks.append(torch.full_like(starts, int(clip_id)))
        start_chunks.append(starts)
    if not start_chunks:
        raise ValueError(f"No valid full-window rollout starts found for K={rollout_k}")
    return StartPool(torch.cat(clip_chunks, dim=0), torch.cat(start_chunks, dim=0))


def build_training_start_pool(
    store: SimpleClipStore,
    rollout_k: int,
    min_start: int = 1,
    clip_ids: tuple[int, ...] | None = None,
) -> StartPool:
    min_start = max(1, int(min_start))
    clip_chunks: list[torch.Tensor] = []
    start_chunks: list[torch.Tensor] = []
    for clip_id in normalize_clip_id_filter(store, clip_ids):
        clip = store.clips[int(clip_id)]
        max_start = max_training_start_for_clip(clip, store.cfg, rollout_k)
        if max_start < min_start:
            continue
        starts = torch.arange(min_start, max_start + 1, dtype=torch.long, device=store.device)
        clip_chunks.append(torch.full_like(starts, int(clip_id)))
        start_chunks.append(starts)
    if not start_chunks:
        raise ValueError(f"No valid rollout starts found for K={rollout_k}")
    return StartPool(torch.cat(clip_chunks, dim=0), torch.cat(start_chunks, dim=0))


def build_fixed_start_pool(
    store: SimpleClipStore,
    start_frame: int,
    clip_ids: tuple[int, ...] | None = None,
) -> StartPool:
    start = int(start_frame)
    if start < 0:
        raise ValueError(f"fixed init frame must be >= 0; got {start}")
    clip_chunks: list[torch.Tensor] = []
    start_chunks: list[torch.Tensor] = []
    for clip_id in normalize_clip_id_filter(store, clip_ids):
        clip = store.clips[int(clip_id)]
        max_start = max_training_start_for_clip(clip, store.cfg)
        if start > max_start:
            raise ValueError(f"fixed init frame {start} exceeds usable max start {max_start} for {clip.path}")
        clip_chunks.append(torch.tensor([clip_id], dtype=torch.long, device=store.device))
        start_chunks.append(torch.tensor([start], dtype=torch.long, device=store.device))
    if not start_chunks:
        raise ValueError(f"No clips available for fixed start frame {start}")
    return StartPool(torch.cat(clip_chunks, dim=0), torch.cat(start_chunks, dim=0))


def rollout_values_for(max_k: int) -> tuple[int, ...]:
    values: list[int] = []
    k = max(1, int(max_k))
    while k > 1:
        values.append(k)
        k = max(1, k // 2)
    values.append(1)
    return tuple(dict.fromkeys(values))


def mixed_rollout_enabled(rollout_k: int) -> bool:
    return bool(MIXED_ROLLOUT_AT_MAX) and int(rollout_k) > 1


def build_start_pools(
    store: SimpleClipStore,
    rollout_values: tuple[int, ...],
    min_start: int = 1,
    clip_ids: tuple[int, ...] | None = None,
) -> dict[int, StartPool]:
    return {int(k): build_start_pool(store, int(k), min_start, clip_ids) for k in rollout_values}


def build_training_start_pools(
    store: SimpleClipStore,
    rollout_values: tuple[int, ...],
    min_start: int = 1,
    clip_ids: tuple[int, ...] | None = None,
) -> dict[int, StartPool]:
    return {int(k): build_training_start_pool(store, int(k), min_start, clip_ids) for k in rollout_values}


def cached_training_start_pools(
    store: SimpleClipStore,
    rollout_values: tuple[int, ...],
    min_start: int = 1,
    clip_ids: tuple[int, ...] | None = None,
) -> dict[int, StartPool]:
    clip_filter = normalize_clip_id_filter(store, clip_ids)
    key = (
        id(store),
        tuple(int(k) for k in rollout_values),
        bool(MIXED_ROLLOUT_AT_MAX),
        max(1, int(min_start)),
        clip_filter,
    )
    cached = _TRAINING_START_POOLS_CACHE.get(key)
    if cached is not None:
        return cached
    pools = build_training_start_pools(store, rollout_values, min_start, clip_filter)
    _TRAINING_START_POOLS_CACHE[key] = pools
    return pools


def clip_ids_matching_path_stems(
    specs: list[tuple[Path, bool]],
    stems: tuple[str, ...],
    allowed_clip_ids: tuple[int, ...],
) -> tuple[int, ...]:
    wanted = tuple(str(stem).lower().strip() for stem in stems if str(stem).strip())
    if not wanted:
        return ()
    allowed = set(int(i) for i in allowed_clip_ids)
    out: list[int] = []
    for i, (path, _cyclic) in enumerate(specs):
        if int(i) not in allowed:
            continue
        name = Path(path).stem.lower()
        if name in wanted:
            out.append(int(i))
    return tuple(out)


def cached_full_window_start_pools(
    store: SimpleClipStore,
    rollout_values: tuple[int, ...],
    min_start: int = 1,
    clip_ids: tuple[int, ...] | None = None,
) -> dict[int, StartPool]:
    clip_filter = normalize_clip_id_filter(store, clip_ids)
    key = (
        id(store),
        tuple(int(k) for k in rollout_values),
        max(1, int(min_start)),
        clip_filter,
    )
    cached = _FULL_WINDOW_START_POOLS_CACHE.get(key)
    if cached is not None:
        return cached
    pools = build_start_pools(store, rollout_values, min_start, clip_filter)
    _FULL_WINDOW_START_POOLS_CACHE[key] = pools
    return pools


def cached_fixed_start_pool(
    store: SimpleClipStore,
    start_frame: int,
    clip_ids: tuple[int, ...] | None = None,
) -> StartPool:
    clip_filter = normalize_clip_id_filter(store, clip_ids)
    key = (id(store), int(start_frame), clip_filter)
    cached = _FIXED_START_POOL_CACHE.get(key)
    if cached is not None:
        return cached
    pool = build_fixed_start_pool(store, int(start_frame), clip_filter)
    _FIXED_START_POOL_CACHE[key] = pool
    return pool


def cached_fixed_start_pools(
    store: SimpleClipStore,
    rollout_values: tuple[int, ...],
    start_frame: int,
    clip_ids: tuple[int, ...] | None = None,
) -> dict[int, StartPool]:
    return {int(k): cached_fixed_start_pool(store, int(start_frame), clip_ids) for k in rollout_values}


def sample_from_pool(pool: StartPool, count: int) -> tuple[torch.Tensor, torch.Tensor]:
    count = max(1, int(count))
    if count == pool.row_count:
        order = torch.randperm(pool.row_count, device=pool.starts.device)
        return pool.clip_ids.index_select(0, order), pool.starts.index_select(0, order)
    rows = torch.randint(0, pool.row_count, (count,), device=pool.starts.device)
    return pool.clip_ids.index_select(0, rows), pool.starts.index_select(0, rows)


class AdaptiveAnimationSampler:
    def __init__(
        self,
        store: SimpleClipStore,
        adaptive_fraction: float = 0.5,
        update_interval_s: float = 120.0,
        ema_alpha: float = 0.35,
        eligible_clip_mask: torch.Tensor | None = None,
    ):
        self.store = store
        self.device = store.device
        self.num_clips = len(store.clips)
        self.adaptive_fraction = max(0.0, min(1.0, float(adaptive_fraction)))
        self.update_interval_s = max(1.0, float(update_interval_s))
        self.ema_alpha = max(0.0, min(1.0, float(ema_alpha)))
        if eligible_clip_mask is None:
            eligible_clip_mask = torch.ones(self.num_clips, dtype=torch.bool, device=self.device)
        self.eligible_clip_mask = eligible_clip_mask.to(device=self.device, dtype=torch.bool).reshape(-1)
        if int(self.eligible_clip_mask.numel()) != self.num_clips:
            raise ValueError(
                f"eligible_clip_mask has {int(self.eligible_clip_mask.numel())} entries for {self.num_clips} clips"
            )
        self.eligible_count = int(self.eligible_clip_mask.sum().detach().cpu())
        if self.eligible_count <= 0:
            raise ValueError("AdaptiveAnimationSampler needs at least one eligible clip")
        self.loss_ema = torch.ones(self.num_clips, dtype=torch.float32, device=self.device)
        self.probabilities = torch.zeros((self.num_clips,), dtype=torch.float32, device=self.device)
        self.probabilities[self.eligible_clip_mask] = 1.0 / float(max(1, self.eligible_count))
        self.pending_loss_sum = torch.zeros_like(self.loss_ema)
        self.pending_loss_count = torch.zeros_like(self.loss_ema)
        self.pick_counts = torch.zeros(self.num_clips, dtype=torch.float32, device=self.device)
        self.interval_pick_counts = torch.zeros_like(self.pick_counts)
        self.adaptive_ready = False
        self.pool_unique_cache: dict[int, torch.Tensor] = {}
        self.dataset_is_omni = torch.tensor(
            [bool(clip.cyclic_animation) for clip in store.clips],
            dtype=torch.bool,
            device=self.device,
        )
        self.last_update_time = time.perf_counter()
        self.last_log_time = self.last_update_time
        self.figure_warning_printed = False

    @torch.no_grad()
    def checkpoint_state_dict(self) -> dict[str, object]:
        now = time.perf_counter()
        return {
            "schema_version": 1,
            "num_clips": int(self.num_clips),
            "adaptive_fraction": float(self.adaptive_fraction),
            "update_interval_s": float(self.update_interval_s),
            "ema_alpha": float(self.ema_alpha),
            "eligible_clip_mask": self.eligible_clip_mask.detach().cpu().clone(),
            "loss_ema": self.loss_ema.detach().cpu().clone(),
            "probabilities": self.probabilities.detach().cpu().clone(),
            "pending_loss_sum": self.pending_loss_sum.detach().cpu().clone(),
            "pending_loss_count": self.pending_loss_count.detach().cpu().clone(),
            "pick_counts": self.pick_counts.detach().cpu().clone(),
            "interval_pick_counts": self.interval_pick_counts.detach().cpu().clone(),
            "adaptive_ready": bool(self.adaptive_ready),
            "seconds_until_update": max(0.0, float(self.update_interval_s) - (now - float(self.last_update_time))),
            "seconds_since_last_log": max(0.0, now - float(self.last_log_time)),
            "figure_warning_printed": bool(self.figure_warning_printed),
        }

    @torch.no_grad()
    def load_checkpoint_state_dict(self, state: object) -> bool:
        if not isinstance(state, dict):
            return False
        if int(state.get("num_clips", -1)) != int(self.num_clips):
            return False
        if abs(float(state.get("adaptive_fraction", self.adaptive_fraction)) - float(self.adaptive_fraction)) > 1e-9:
            return False
        if abs(float(state.get("update_interval_s", self.update_interval_s)) - float(self.update_interval_s)) > 1e-9:
            return False
        if abs(float(state.get("ema_alpha", self.ema_alpha)) - float(self.ema_alpha)) > 1e-9:
            return False
        saved_mask = state.get("eligible_clip_mask")
        if not torch.is_tensor(saved_mask) or tuple(saved_mask.shape) != tuple(self.eligible_clip_mask.shape):
            return False
        if not bool(torch.equal(saved_mask.to(dtype=torch.bool), self.eligible_clip_mask.detach().cpu())):
            return False

        def copy_tensor(name: str, target: torch.Tensor) -> bool:
            value = state.get(name)
            if not torch.is_tensor(value) or tuple(value.shape) != tuple(target.shape):
                return False
            target.copy_(value.to(device=self.device, dtype=target.dtype))
            return True

        for name, target in (
            ("loss_ema", self.loss_ema),
            ("probabilities", self.probabilities),
            ("pending_loss_sum", self.pending_loss_sum),
            ("pending_loss_count", self.pending_loss_count),
            ("pick_counts", self.pick_counts),
            ("interval_pick_counts", self.interval_pick_counts),
        ):
            if not copy_tensor(name, target):
                return False
        self.adaptive_ready = bool(state.get("adaptive_ready", self.adaptive_ready))
        now = time.perf_counter()
        seconds_until_update = max(
            0.0,
            min(float(self.update_interval_s), float(state.get("seconds_until_update", self.update_interval_s))),
        )
        self.last_update_time = now - (float(self.update_interval_s) - seconds_until_update)
        self.last_log_time = now - max(0.0, float(state.get("seconds_since_last_log", 0.0)))
        self.figure_warning_printed = bool(state.get("figure_warning_printed", self.figure_warning_printed))
        self.pool_unique_cache.clear()
        return True

    def unique_clips_for_pool(self, pool: StartPool) -> torch.Tensor:
        key = id(pool)
        cached = self.pool_unique_cache.get(key)
        if cached is not None:
            return cached
        unique = torch.unique(pool.clip_ids).long()
        unique = unique[self.eligible_clip_mask.index_select(0, unique)]
        self.pool_unique_cache[key] = unique
        return unique

    def sample_from_pool(
        self,
        pool: StartPool,
        count: int,
        min_start: int = 1,
        rollout_k: int = 1,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        count = max(1, int(count))
        adaptive_count = int(round(float(count) * self.adaptive_fraction))
        adaptive_count = max(0, min(count, adaptive_count))
        uniform_count = count - adaptive_count
        clip_parts: list[torch.Tensor] = []
        start_parts: list[torch.Tensor] = []
        if uniform_count:
            clip_ids, starts = sample_from_pool(pool, uniform_count)
            clip_parts.append(clip_ids)
            start_parts.append(starts)
        if adaptive_count:
            valid_clip_ids = self.unique_clips_for_pool(pool)
            if int(valid_clip_ids.numel()) == 0:
                clip_ids, starts = sample_from_pool(pool, adaptive_count)
                clip_parts.append(clip_ids)
                start_parts.append(starts)
                adaptive_count = 0
        if adaptive_count:
            valid_clip_ids = self.unique_clips_for_pool(pool)
            if self.adaptive_ready:
                probs = self.probabilities.index_select(0, valid_clip_ids).clamp_min(1e-8)
                probs = probs / probs.sum().clamp_min(1e-8)
                picked = valid_clip_ids.index_select(
                    0,
                    torch.multinomial(probs, adaptive_count, replacement=True),
                )
            else:
                picked = valid_clip_ids.index_select(
                    0,
                    torch.randint(0, int(valid_clip_ids.numel()), (adaptive_count,), device=self.device),
                )
            starts = sample_same_clip_training_starts(self.store, picked, min_start, rollout_k)
            clip_parts.append(picked)
            start_parts.append(starts)
        clip_ids = torch.cat(clip_parts, dim=0)
        starts = torch.cat(start_parts, dim=0)
        order = torch.randperm(int(clip_ids.numel()), device=self.device)
        return clip_ids.index_select(0, order), starts.index_select(0, order)

    @torch.no_grad()
    def record_batch(self, clip_ids: torch.Tensor, row_losses: torch.Tensor | None) -> None:
        if self.eligible_count <= 1:
            return
        if row_losses is None or int(clip_ids.numel()) == 0:
            return
        clip_ids = clip_ids.detach().to(self.device).long().reshape(-1)
        losses = row_losses.detach().to(self.device).float().reshape(-1).clamp_min(0.0)
        if int(losses.numel()) != int(clip_ids.numel()):
            return
        eligible = self.eligible_clip_mask.index_select(0, clip_ids)
        if not bool(eligible.any()):
            return
        clip_ids = clip_ids[eligible]
        losses = losses[eligible]
        self.pending_loss_sum.scatter_add_(0, clip_ids, losses)
        self.pending_loss_count.scatter_add_(0, clip_ids, torch.ones_like(losses))
        self.pick_counts.scatter_add_(0, clip_ids, torch.ones_like(losses))
        self.interval_pick_counts.scatter_add_(0, clip_ids, torch.ones_like(losses))

    @torch.no_grad()
    def maybe_update(self) -> bool:
        if self.eligible_count <= 1:
            return False
        now = time.perf_counter()
        if now - self.last_update_time < self.update_interval_s:
            return False
        covered = (self.pick_counts > 0) & self.eligible_clip_mask
        covered_count = int(covered.sum().detach().cpu())
        if covered_count < self.eligible_count:
            self.probabilities.fill_(1.0 / float(max(1, self.num_clips)))
            self.probabilities.zero_()
            self.probabilities[self.eligible_clip_mask] = 1.0 / float(max(1, self.eligible_count))
            self.adaptive_ready = False
            self.last_update_time = now
            print(
                f"adaptive_sampler_waiting_for_coverage sampled={covered_count}/{self.eligible_count} "
                f"probabilities=uniform",
                flush=True,
            )
            return True
        self.adaptive_ready = True
        seen = self.pending_loss_count > 0
        if bool(seen.any()):
            means = self.pending_loss_sum / self.pending_loss_count.clamp_min(1.0)
            self.loss_ema = torch.where(
                seen,
                self.loss_ema * (1.0 - self.ema_alpha) + means * self.ema_alpha,
                self.loss_ema,
            )
            probs = torch.where(self.eligible_clip_mask, self.loss_ema.clamp_min(1e-8), torch.zeros_like(self.loss_ema))
            self.probabilities = probs / probs.sum().clamp_min(1e-8)
        self.pending_loss_sum.zero_()
        self.pending_loss_count.zero_()
        self.last_update_time = now
        return True

    def log_figures(self, writer: SummaryWriter, step: int) -> None:
        def per_anim_bar_image(values: torch.Tensor, color: tuple[int, int, int]) -> torch.Tensor:
            values = values.detach().float().cpu().clamp_min(0.0)
            n = max(1, int(values.numel()))
            height, pad = 260, 22
            bar_w = 12 if n <= 20 else 3
            width = max(260, pad * 2 + n * bar_w)
            image = torch.full((3, height, width), 18, dtype=torch.uint8)
            image[:, height - pad : height - pad + 2, pad : width - pad] = 90
            image[:, pad : height - pad, pad : pad + 2] = 90
            rgb = torch.tensor(color, dtype=torch.uint8).view(3, 1, 1)
            slot = torch.tensor((42, 42, 42), dtype=torch.uint8).view(3, 1, 1)
            max_count = float(values.max().clamp_min(1.0).item())
            for i, count in enumerate(values.tolist()):
                x0 = pad + i * bar_w
                x1 = min(width - pad, x0 + max(1, bar_w - 1))
                if x0 < x1:
                    image[:, height - pad - 1 : height - pad, x0:x1] = slot
                bar_h = int(round((height - 2 * pad - 4) * float(count) / max_count))
                y0 = max(pad, height - pad - bar_h)
                y1 = height - pad
                if x0 < x1 and y0 < y1:
                    image[:, y0:y1, x0:x1] = rgb
            return image

        probs = self.probabilities.detach().float().cpu()
        interval_counts = self.interval_pick_counts.detach().float().cpu()
        lifetime_counts = self.pick_counts.detach().float().cpu()
        is_omni = self.dataset_is_omni.detach().cpu()
        eligible = self.eligible_clip_mask.detach().cpu()
        for name, mask in (("omni", is_omni), ("transition", ~is_omni)):
            mask = mask & eligible
            if not bool(mask.any()):
                continue
            writer.add_image(
                f"sampler/{name}_picked_by_anim_since_last_log",
                per_anim_bar_image(interval_counts[mask], (120, 255, 150)),
                global_step=step,
            )
            writer.add_image(
                f"sampler/{name}_picked_by_anim_lifetime",
                per_anim_bar_image(lifetime_counts[mask], (80, 220, 255)),
                global_step=step,
            )
        writer.add_scalar("sampler/prob_max", float(probs.max().item()), step)
        writer.add_scalar("sampler/prob_min", float(probs.min().item()), step)
        writer.add_scalar("sampler/loss_ema_mean", float(self.loss_ema.detach().float().mean().cpu().item()), step)
        writer.add_scalar("sampler/update_interval_s", float(self.update_interval_s), step)
        writer.add_scalar(
            "sampler/coverage_count",
            float(((self.pick_counts > 0) & self.eligible_clip_mask).sum().detach().cpu().item()),
            step,
        )
        writer.add_scalar("sampler/eligible_clip_count", float(self.eligible_count), step)
        writer.add_scalar("sampler/adaptive_ready", 1.0 if self.adaptive_ready else 0.0, step)
        writer.add_scalar("sampler/pending_loss_rows", float(self.pending_loss_count.sum().detach().cpu().item()), step)
        writer.add_scalar("sampler/interval_picked_rows", float(self.interval_pick_counts.sum().detach().cpu().item()), step)
        self.interval_pick_counts.zero_()


def sample_effective_rollout_k(batch_size: int, rollout_k: int, device: torch.device) -> torch.Tensor:
    batch_size = max(1, int(batch_size))
    rollout_k = max(1, int(rollout_k))
    if not mixed_rollout_enabled(rollout_k):
        return torch.full((batch_size,), rollout_k, dtype=torch.long, device=device)
    values = rollout_values_for(rollout_k)
    remaining = batch_size
    chunks: list[torch.Tensor] = []
    for value in values[:-1]:
        count = remaining // 2
        if count:
            chunks.append(torch.full((count,), int(value), dtype=torch.long, device=device))
        remaining -= count
    chunks.append(torch.full((remaining,), int(values[-1]), dtype=torch.long, device=device))
    effective_k = torch.cat(chunks, dim=0)
    return effective_k.index_select(0, torch.randperm(batch_size, device=device))


def sample_effective_rollout_k_with_reserved_rows(
    batch_size: int,
    rollout_k: int,
    device: torch.device,
    synthetic_reserved_rows: int = 0,
    virtual_reserved_rows: int = 0,
) -> torch.Tensor:
    batch_size = max(1, int(batch_size))
    synthetic_reserved_rows = max(0, min(batch_size, int(synthetic_reserved_rows)))
    virtual_reserved_rows = max(0, min(batch_size - synthetic_reserved_rows, int(virtual_reserved_rows)))
    real_rows = generated_reserved_real_batch_size(batch_size, synthetic_reserved_rows, virtual_reserved_rows)
    parts: list[torch.Tensor] = []
    if real_rows > 0:
        parts.append(sample_effective_rollout_k(real_rows, rollout_k, device))
    if synthetic_reserved_rows > 0:
        parts.append(sample_effective_rollout_k(synthetic_reserved_rows, rollout_k, device))
    if virtual_reserved_rows > 0:
        parts.append(sample_effective_rollout_k(virtual_reserved_rows, rollout_k, device))
    return torch.cat(parts, dim=0) if parts else torch.full((batch_size,), max(1, int(rollout_k)), dtype=torch.long, device=device)


def force_row_range_to_rollout_k_(
    effective_k: torch.Tensor,
    row_start: int,
    row_count: int,
    rollout_k: int,
) -> torch.Tensor:
    row_start = max(0, min(int(effective_k.numel()), int(row_start)))
    row_count = max(0, min(int(effective_k.numel()) - row_start, int(row_count)))
    if row_count > 0:
        effective_k[row_start : row_start + row_count].fill_(max(1, int(rollout_k)))
    return effective_k


def max_training_start_for_clip_ids(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    rollout_k: int | torch.Tensor = 1,
) -> torch.Tensor:
    clip_ids = clip_ids.to(store.device).long()
    cached = getattr(store, "max_training_starts", None)
    if cached is not None and not isinstance(rollout_k, torch.Tensor) and int(rollout_k) <= 1:
        return cached.index_select(0, clip_ids)
    rollout_steps = (
        torch.as_tensor(rollout_k, dtype=torch.long, device=store.device).reshape(-1)
        if isinstance(rollout_k, torch.Tensor)
        else torch.full((int(clip_ids.numel()),), max(1, int(rollout_k)), dtype=torch.long, device=store.device)
    )
    if int(rollout_steps.numel()) == 1 and int(clip_ids.numel()) != 1:
        rollout_steps = rollout_steps.expand_as(clip_ids)
    rollout_steps = rollout_steps.to(device=store.device, dtype=torch.long).clamp_min(1)
    cyclic = store.cyclic.index_select(0, clip_ids)
    periods = store.periods.index_select(0, clip_ids).clamp_min(1)
    lengths = store.lengths.index_select(0, clip_ids)
    horizon = int(transition_feature_horizon(store.cfg))
    one_step_max = lengths - horizon - 1
    rollout_max = lengths - horizon - rollout_steps
    noncyclic_max = torch.where(rollout_max >= 1, rollout_max, one_step_max).clamp_min(1)
    return torch.where(cyclic, periods - 1, noncyclic_max).clamp_min(1)


def sample_same_clip_training_starts(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    min_start: int = 1,
    rollout_k: int | torch.Tensor = 1,
) -> torch.Tensor:
    min_start = max(1, int(min_start))
    max_start = max_training_start_for_clip_ids(store, clip_ids, rollout_k)
    if min_start > 1:
        max_start = torch.maximum(max_start, torch.full_like(max_start, min_start))
        span = (max_start - min_start + 1).clamp_min(1)
        noise = torch.rand(span.shape, dtype=torch.float32, device=store.device)
        starts = (torch.floor(noise * span.float()).long() + min_start).clamp_min(min_start)
    else:
        noise = torch.rand(max_start.shape, dtype=torch.float32, device=store.device)
        starts = (torch.floor(noise * max_start.float()).long() + 1).clamp_min(1)
    return starts


def sample_same_clip_training_starts_by_step(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    steps: int,
    min_start: int = 1,
    rollout_k: int | torch.Tensor = 1,
) -> torch.Tensor:
    steps = max(1, int(steps))
    min_start = max(1, int(min_start))
    rollout_steps = (
        torch.as_tensor(rollout_k, dtype=torch.long, device=store.device).reshape(-1)
        if isinstance(rollout_k, torch.Tensor)
        else torch.full((int(clip_ids.numel()),), max(1, int(rollout_k)), dtype=torch.long, device=store.device)
    )
    if int(rollout_steps.numel()) == 1 and int(clip_ids.numel()) != 1:
        rollout_steps = rollout_steps.expand_as(clip_ids)
    step_offsets = torch.arange(0, steps, dtype=torch.long, device=store.device).reshape(steps, 1)
    remaining_steps = (rollout_steps.reshape(1, -1) - step_offsets - 1).clamp_min(1)
    expanded_clip_ids = clip_ids.reshape(1, -1).expand(steps, -1).reshape(-1)
    max_start_long = max_training_start_for_clip_ids(
        store,
        expanded_clip_ids,
        remaining_steps.reshape(-1),
    ).reshape(steps, -1)
    if min_start > 1:
        max_start_long = torch.maximum(max_start_long, torch.full_like(max_start_long, min_start))
        span = (max_start_long - min_start + 1).clamp_min(1).float().unsqueeze(0)
        if span.dim() == 3:
            span = span.squeeze(0)
        noise = torch.rand((steps, int(clip_ids.numel())), dtype=torch.float32, device=store.device)
        starts = (torch.floor(noise * span).long() + min_start).clamp_min(min_start)
    else:
        max_start = max_start_long.float()
        noise = torch.rand((steps, int(clip_ids.numel())), dtype=torch.float32, device=store.device)
        starts = (torch.floor(noise * max_start).long() + 1).clamp_min(1)
    return starts


def training_reset_rows(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
    continuing: torch.Tensor,
) -> torch.Tensor:
    cyclic = store.cyclic.index_select(0, clip_ids)
    max_start = max_training_start_for_clip_ids(store, clip_ids)
    return continuing & (~cyclic) & (cur_idx >= max_start)


def rollout_stat_summary(batch_size: int, rollout_k: int) -> dict[str, float]:
    values = rollout_values_for(rollout_k) if mixed_rollout_enabled(rollout_k) else (max(1, int(rollout_k)),)
    remaining = max(1, int(batch_size))
    counts: list[int] = []
    for _value in values[:-1]:
        count = remaining // 2
        counts.append(count)
        remaining -= count
    counts.append(remaining)
    total = float(sum(counts))
    return {
        "effective_k_mean": sum(float(k) * float(c) for k, c in zip(values, counts)) / total,
        "effective_k_max": float(max(values)),
    }


def generated_reserved_real_batch_size(batch_size: int, synthetic_rows: int, virtual_rows: int) -> int:
    return max(0, int(batch_size) - max(0, int(synthetic_rows)) - max(0, int(virtual_rows)))


def forced_tail_row_indices(
    batch_size: int,
    row_limit: int,
    force_idle_row: bool,
    forced_idle_batch_fraction: float | None,
    force_turn45_row: bool,
    forced_turn45_batch_fraction: float | None,
    device: torch.device,
) -> torch.Tensor:
    row_limit = max(0, min(int(batch_size), int(row_limit)))
    count = forced_tail_noisy_row_count(
        row_limit,
        force_idle_row,
        forced_idle_batch_fraction,
        force_turn45_row,
        forced_turn45_batch_fraction,
    )
    if row_limit <= 0 or count <= 0:
        return torch.empty((0,), dtype=torch.long, device=device)
    return torch.arange(row_limit - count, row_limit, dtype=torch.long, device=device)


def sample_rows_from_start_pools(
    start_pools: dict[int, StartPool] | None,
    effective_k: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    clip_ids = torch.empty_like(effective_k)
    starts = torch.empty_like(effective_k)
    if start_pools is None or int(effective_k.numel()) == 0:
        return clip_ids, starts
    fallback_pool = next(iter(start_pools.values()))
    for rollout_k in torch.unique(effective_k).detach().cpu().tolist():
        rows = (effective_k == int(rollout_k)).nonzero(as_tuple=False).flatten()
        if rows.numel() == 0:
            continue
        pool = start_pools.get(int(rollout_k), fallback_pool)
        row_clip_ids, row_starts = sample_from_pool(pool, int(rows.numel()))
        clip_ids[rows] = row_clip_ids
        starts[rows] = row_starts
    return clip_ids, starts


def sample_adjacent_init_rows_from_start_pools(
    start_pools: dict[int, StartPool],
    count: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    pool = start_pools.get(1)
    if pool is None:
        pool = next(iter(start_pools.values()))
    return sample_from_pool(pool, count)


def sample_rollout_rows(
    start_pools: dict[int, StartPool],
    effective_k: torch.Tensor,
    adaptive_sampler: AdaptiveAnimationSampler | None = None,
    min_start: int = 1,
    synthetic_start_pools: dict[int, StartPool] | None = None,
    synthetic_fraction: float = 0.0,
    full_window_start_pools: dict[int, StartPool] | None = None,
    full_window_rows: torch.Tensor | None = None,
    synthetic_reserved_start_pools: dict[int, StartPool] | None = None,
    synthetic_reserved_rows: int = 0,
    virtual_reserved_start_pools: dict[int, StartPool] | None = None,
    virtual_reserved_rows: int = 0,
    dedicated_real_start_pools: dict[int, StartPool] | None = None,
    dedicated_real_rows: int = 0,
    periodic_reserved_start_pools: dict[int, StartPool] | None = None,
    periodic_reserved_rows: int = 0,
) -> tuple[torch.Tensor, torch.Tensor]:
    clip_ids = torch.empty_like(effective_k)
    starts = torch.empty_like(effective_k)
    total_rows = int(effective_k.numel())
    synthetic_reserved_rows = max(0, min(total_rows, int(synthetic_reserved_rows)))
    virtual_reserved_rows = max(0, min(total_rows - synthetic_reserved_rows, int(virtual_reserved_rows)))
    real_row_count = generated_reserved_real_batch_size(total_rows, synthetic_reserved_rows, virtual_reserved_rows)
    dedicated_real_rows = (
        max(0, min(real_row_count, int(dedicated_real_rows)))
        if dedicated_real_start_pools is not None
        else 0
    )
    periodic_reserved_rows = (
        max(0, min(real_row_count - dedicated_real_rows, int(periodic_reserved_rows)))
        if periodic_reserved_start_pools is not None
        else 0
    )
    reserved_real_rows = dedicated_real_rows + periodic_reserved_rows
    regular_real_count = max(0, real_row_count - reserved_real_rows)
    regular_real_slice = slice(reserved_real_rows, real_row_count)
    synthetic_rows = torch.zeros_like(effective_k, dtype=torch.bool)
    if synthetic_start_pools and float(synthetic_fraction) > 0.0 and regular_real_count > 0:
        count = int(round(regular_real_count * max(0.0, min(1.0, float(synthetic_fraction)))))
        count = max(1, min(regular_real_count, count))
        rows = torch.randperm(regular_real_count, device=effective_k.device)[:count] + reserved_real_rows
        synthetic_rows[rows] = True
    for rollout_k, pool in start_pools.items():
        rows = (
            (effective_k[regular_real_slice] == int(rollout_k))
            & (~synthetic_rows[regular_real_slice])
        ).nonzero(as_tuple=False).flatten()
        rows = rows + reserved_real_rows
        if rows.numel() == 0:
            pass
        elif adaptive_sampler is None:
            row_clip_ids, row_starts = sample_from_pool(pool, int(rows.numel()))
            clip_ids[rows] = row_clip_ids
            starts[rows] = row_starts
        else:
            row_clip_ids, row_starts = adaptive_sampler.sample_from_pool(
                pool,
                int(rows.numel()),
                min_start,
                int(rollout_k),
            )
            clip_ids[rows] = row_clip_ids
            starts[rows] = row_starts
        if not synthetic_start_pools:
            continue
        synth_rows = (
            (effective_k[regular_real_slice] == int(rollout_k))
            & synthetic_rows[regular_real_slice]
        ).nonzero(as_tuple=False).flatten()
        synth_rows = synth_rows + reserved_real_rows
        if synth_rows.numel() == 0:
            continue
        synth_pool = synthetic_start_pools.get(int(rollout_k))
        if synth_pool is None:
            synth_pool = next(iter(synthetic_start_pools.values()))
        row_clip_ids, row_starts = sample_from_pool(synth_pool, int(synth_rows.numel()))
        clip_ids[synth_rows] = row_clip_ids
        starts[synth_rows] = row_starts
    if dedicated_real_rows > 0 and dedicated_real_start_pools is not None:
        dedicated_slice = slice(0, dedicated_real_rows)
        row_clip_ids, row_starts = sample_rows_from_start_pools(
            dedicated_real_start_pools,
            effective_k[dedicated_slice],
        )
        clip_ids[dedicated_slice] = row_clip_ids
        starts[dedicated_slice] = row_starts
    if periodic_reserved_rows > 0 and periodic_reserved_start_pools is not None:
        periodic_slice = slice(dedicated_real_rows, dedicated_real_rows + periodic_reserved_rows)
        row_clip_ids, row_starts = sample_rows_from_start_pools(
            periodic_reserved_start_pools,
            effective_k[periodic_slice],
        )
        clip_ids[periodic_slice] = row_clip_ids
        starts[periodic_slice] = row_starts
    if synthetic_reserved_rows > 0 and synthetic_reserved_start_pools is not None:
        synth_slice = slice(real_row_count, real_row_count + synthetic_reserved_rows)
        row_clip_ids, row_starts = sample_rows_from_start_pools(
            synthetic_reserved_start_pools,
            effective_k[synth_slice],
        )
        clip_ids[synth_slice] = row_clip_ids
        starts[synth_slice] = row_starts
    if virtual_reserved_rows > 0 and virtual_reserved_start_pools is not None:
        virtual_slice = slice(real_row_count + synthetic_reserved_rows, total_rows)
        row_clip_ids, row_starts = sample_rows_from_start_pools(
            virtual_reserved_start_pools,
            effective_k[virtual_slice],
        )
        clip_ids[virtual_slice] = row_clip_ids
        starts[virtual_slice] = row_starts
    return clip_ids, starts


def stage_for_step(step: int) -> tuple[int, int, int, int]:
    start = 1
    for stage_idx, (rollout_k, stage_steps) in enumerate(zip(ROLLOUT_SCHEDULE, ROLLOUT_STAGE_STEPS)):
        end = start + int(stage_steps) - 1
        if int(step) <= end:
            return stage_idx, int(rollout_k), start, end
        start = end + 1
    return len(ROLLOUT_SCHEDULE) - 1, int(ROLLOUT_SCHEDULE[-1]), start, start


def stage_learning_rate(rollout_k: int) -> float:
    return float(STAGE_LEARNING_RATES.get(int(rollout_k), LEARNING_RATE))


def default_stage_learning_rates_for_schedule(schedule: tuple[int, ...]) -> dict[int, float]:
    if max(int(k) for k in schedule) <= 32:
        return {
            1: 1e-4,
            2: 1e-4,
            8: 1e-4,
            16: 5e-5,
            32: 2e-5,
        }
    return dict(STAGE_LEARNING_RATES)


def apply_stage_learning_rate_overrides(
    base: dict[int, float],
    entries: list[str] | tuple[str, ...],
    schedule: tuple[int, ...],
) -> dict[int, float]:
    values = dict(base)
    valid = {int(k) for k in schedule}
    for raw_entry in entries:
        entry = str(raw_entry).strip()
        if not entry:
            continue
        if "=" in entry:
            key, value = entry.split("=", 1)
        elif ":" in entry:
            key, value = entry.split(":", 1)
        else:
            raise ValueError(f"stage learning rate override must look like K=LR, got {entry!r}")
        key = key.strip().lower()
        if key.startswith("k"):
            key = key[1:]
        rollout_k = int(key)
        if rollout_k not in valid:
            raise ValueError(f"stage learning rate override K={rollout_k} is not in rollout_schedule {schedule}")
        values[rollout_k] = float(value)
    return values


def set_optimizer_lr(optimizer: torch.optim.Optimizer, lr: float) -> None:
    for group in optimizer.param_groups:
        group["lr"] = float(lr)


def make_adamw(params, lr: float, device: torch.device, capturable: bool = False) -> torch.optim.Optimizer:
    kwargs = {"lr": lr, "weight_decay": 0.0}
    if device.type == "cuda":
        kwargs["fused"] = True
        if capturable:
            kwargs["capturable"] = True
    try:
        return torch.optim.AdamW(params, **kwargs)
    except (RuntimeError, TypeError):
        kwargs.pop("fused", None)
        kwargs.pop("capturable", None)
        return torch.optim.AdamW(params, **kwargs)


def move_optimizer_state_to_device(optimizer: torch.optim.Optimizer, device: torch.device) -> None:
    for state in optimizer.state.values():
        for key, value in list(state.items()):
            if torch.is_tensor(value):
                state[key] = value.to(device=device)


def batch_size_for_stage(store: SimpleClipStore, rollout_k: int, row_count: int) -> int:
    cap = int(BATCH_SIZE)
    if store.device.type == "cuda" and int(rollout_k) >= 64:
        total_gb = torch.cuda.get_device_properties(store.device).total_memory / float(1024**3)
        if total_gb <= 10.0:
            cap = min(cap, int(SMALL_CUDA_K64_BATCH_SIZE))
    if mixed_rollout_enabled(rollout_k):
        return max(1, min(int(row_count) * 2, cap))
    return max(1, min(int(row_count), cap))


def payload_slice(store: SimpleClipStore) -> slice:
    start = 3 + 6 + store.Jcore * 6
    return slice(start, start + store.ik_payload_dim)


def base_output_dim_for_store(store: SimpleClipStore) -> int:
    return int(payload_slice(store).stop)


def controller_output_dim_for_store(store: SimpleClipStore) -> int:
    base_dim = base_output_dim_for_store(store)
    return base_dim + int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)


def pose_bank_foot_toe_globals_from_vec(
    store: SimpleClipStore,
    root_pos: torch.Tensor,
    root_rot: torch.Tensor,
    vec: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    payload = vec[:, payload_slice(store)]
    b = int(vec.shape[0])
    positions: list[torch.Tensor] = []
    rotations: list[torch.Tensor] = []
    for limb_i in ik_pose_ae4_leg_limb_indices_by_side(store):
        spec = store.ik_payload_slices[int(limb_i)]
        pos_slice = spec["pos"]
        rot_slice = spec["rot6"]
        toe_slice = spec["toe_float"]
        if toe_slice is None:
            raise ValueError("Pose-bank pin labels need toe IK payloads for both legs.")
        assert isinstance(pos_slice, slice)
        assert isinstance(rot_slice, slice)
        assert isinstance(toe_slice, slice)
        foot_pos_root = payload[:, pos_slice]
        foot_rot_root = tl.rotation_6d_to_matrix(payload[:, rot_slice])
        toe_offset = store.ik_toe_offsets[int(limb_i)].to(dtype=vec.dtype, device=vec.device).reshape(1, 3).expand(b, 3)
        toe_pos_root = foot_pos_root + torch.matmul(toe_offset.unsqueeze(1), foot_rot_root).squeeze(1)
        toe_axis = store.ik_toe_axis[int(limb_i)].to(dtype=vec.dtype, device=vec.device).reshape(1, 3).expand(b, 3)
        toe_float = payload[:, toe_slice].squeeze(-1).clamp(-1.0, 1.0)
        toe_hinge = tl.axis_angle_to_row_matrix(toe_axis, toe_float * tl.IK_TOE_ALPHA)
        toe_rot_root = toe_hinge @ foot_rot_root
        positions.extend(
            (
                tl.root_relative_to_world(foot_pos_root.unsqueeze(1), root_pos, root_rot).squeeze(1),
                tl.root_relative_to_world(toe_pos_root.unsqueeze(1), root_pos, root_rot).squeeze(1),
            )
        )
        rotations.extend(
            (
                tl.root_relative_rot_to_world(foot_rot_root, root_rot),
                tl.root_relative_rot_to_world(toe_rot_root, root_rot),
            )
        )
    return torch.stack(positions, dim=1), torch.stack(rotations, dim=1)


def pose_bank_pin_labels_from_ik_vectors(
    store: SimpleClipStore,
    prev_root_pos: torch.Tensor,
    prev_root_rot: torch.Tensor,
    prev_vec: torch.Tensor,
    cur_root_pos: torch.Tensor,
    cur_root_rot: torch.Tensor,
    cur_vec: torch.Tensor,
    threshold_m: float = POSE_BANK_PIN_SLIDE_DISTANCE_THRESHOLD_M,
) -> torch.Tensor:
    prev_pos, prev_rot = pose_bank_foot_toe_globals_from_vec(store, prev_root_pos, prev_root_rot, prev_vec)
    cur_pos, cur_rot = pose_bank_foot_toe_globals_from_vec(store, cur_root_pos, cur_root_rot, cur_vec)
    speeds = cp.foot_slide_speeds(
        prev_pos,
        prev_rot,
        cur_pos,
        cur_rot,
        (0, 2),
        (1, 3),
        float(store.prototype.fps),
        POSE_BANK_PIN_CONTACT_GEOMETRY,
    )
    return (speeds / float(store.prototype.fps) <= float(threshold_m)).to(dtype=torch.float32)


def vector_position_slices(store: SimpleClipStore) -> list[slice]:
    slices = [slice(0, 3)]
    payload_start = payload_slice(store).start
    for spec in store.ik_payload_slices:
        pos_slice = spec["pos"]
        assert isinstance(pos_slice, slice)
        slices.append(slice(payload_start + pos_slice.start, payload_start + pos_slice.stop))
    return slices


def vector_rot6_slices(store: SimpleClipStore) -> list[slice]:
    slices = [slice(3, 9)]
    cursor = 9
    for _ in range(store.Jcore):
        slices.append(slice(cursor, cursor + 6))
        cursor += 6
    payload_start = cursor
    for spec in store.ik_payload_slices:
        rot_slice = spec["rot6"]
        start_rot_slice = spec["start_rot6"]
        assert isinstance(rot_slice, slice)
        assert isinstance(start_rot_slice, slice)
        slices.append(slice(payload_start + rot_slice.start, payload_start + rot_slice.stop))
        slices.append(slice(payload_start + start_rot_slice.start, payload_start + start_rot_slice.stop))
    return slices


def vector_scalar_slices(store: SimpleClipStore) -> list[slice]:
    slices: list[slice] = []
    payload_start = payload_slice(store).start
    for spec in store.ik_payload_slices:
        toe_slice = spec["toe_float"]
        if toe_slice is not None:
            assert isinstance(toe_slice, slice)
            slices.append(slice(payload_start + toe_slice.start, payload_start + toe_slice.stop))
    return slices


def ik_motion_ae2_horizontal_axes() -> tuple[int, int]:
    up = int(FOOT_ROLL_UP_AXIS)
    axes = [axis for axis in range(3) if axis != up]
    return int(axes[0]), int(axes[1])


def ik_motion_ae2_position_delta_features(cur_pos: torch.Tensor, out_pos: torch.Tensor) -> torch.Tensor:
    delta = out_pos - cur_pos
    h0, h1 = ik_motion_ae2_horizontal_axes()
    horizontal_sq = delta[:, h0 : h0 + 1].square() + delta[:, h1 : h1 + 1].square()
    horizontal = torch.sqrt(horizontal_sq + 1.0e-12) - 1.0e-6
    vertical = delta[:, int(FOOT_ROLL_UP_AXIS) : int(FOOT_ROLL_UP_AXIS) + 1]
    return torch.cat((horizontal, vertical), dim=-1)


def ik_motion_ae2_rotation_features(cur_rot6: torch.Tensor, out_rot6: torch.Tensor) -> torch.Tensor:
    cur_rot = tl.rotation_6d_to_matrix(tl.clean_6d(cur_rot6))
    out_rot = tl.rotation_6d_to_matrix(tl.clean_6d(out_rot6))
    rel = out_rot @ cur_rot.transpose(-1, -2)
    h0, h1 = ik_motion_ae2_horizontal_axes()
    twist = torch.atan2(rel[:, h0, h1], rel[:, h0, h0])
    twist_rot = ik_motion_ae2_up_axis_row_matrix(twist)
    residual = rel @ twist_rot.transpose(-1, -2)
    eye = ik_motion_ae2_identity_row_matrix(twist).expand_as(residual)
    swing = tl.geodesic_angles(residual, eye).unsqueeze(-1)
    return torch.cat((swing, twist.unsqueeze(-1)), dim=-1)


def ik_motion_ae2_identity_row_matrix(values: torch.Tensor) -> torch.Tensor:
    z = torch.zeros_like(values)
    o = torch.ones_like(values)
    return torch.stack(
        (
            torch.stack((o, z, z), dim=-1),
            torch.stack((z, o, z), dim=-1),
            torch.stack((z, z, o), dim=-1),
        ),
        dim=-2,
    )


def ik_motion_ae2_up_axis_row_matrix(angle: torch.Tensor) -> torch.Tensor:
    c = torch.cos(angle)
    s = torch.sin(angle)
    z = torch.zeros_like(angle)
    o = torch.ones_like(angle)
    up = int(FOOT_ROLL_UP_AXIS)
    if up == 0:
        row0 = torch.stack((o, z, z), dim=-1)
        row1 = torch.stack((z, c, s), dim=-1)
        row2 = torch.stack((z, -s, c), dim=-1)
    elif up == 1:
        row0 = torch.stack((c, z, s), dim=-1)
        row1 = torch.stack((z, o, z), dim=-1)
        row2 = torch.stack((-s, z, c), dim=-1)
    else:
        row0 = torch.stack((c, s, z), dim=-1)
        row1 = torch.stack((-s, c, z), dim=-1)
        row2 = torch.stack((z, z, o), dim=-1)
    return torch.stack((row0, row1, row2), dim=-2)


def ik_pose_window_feature_rows(store: SimpleClipStore, out_vec: torch.Tensor) -> torch.Tensor:
    return clean_output_vector(out_vec, store)


def ik_root_conditioned_pose_window_feature_rows(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
    out_vec: torch.Tensor,
) -> torch.Tensor:
    root_features = store.get_input_root_features(clip_ids, cur_idx)
    return torch.cat((root_features, clean_output_vector(out_vec, store)), dim=-1).float()


def ik_motion_ae2_feature_rows(
    store: SimpleClipStore,
    cur_vec: torch.Tensor,
    out_vec: torch.Tensor,
) -> torch.Tensor:
    payload_vec_slice = payload_slice(store)
    parts = [
        ik_motion_ae2_position_delta_features(cur_vec[:, 0:3], out_vec[:, 0:3]),
        ik_motion_ae2_rotation_features(cur_vec[:, 3:9], out_vec[:, 3:9]),
    ]
    cur_payload = cur_vec[:, payload_vec_slice]
    out_payload = out_vec[:, payload_vec_slice]
    for spec in store.ik_payload_slices:
        if str(spec.get("kind", "")).lower().strip() != "leg":
            continue
        pos_slice = spec["pos"]
        rot_slice = spec["rot6"]
        start_rot_slice = spec["start_rot6"]
        toe_slice = spec["toe_float"]
        assert isinstance(pos_slice, slice)
        assert isinstance(rot_slice, slice)
        assert isinstance(start_rot_slice, slice)
        parts.append(ik_motion_ae2_position_delta_features(cur_payload[:, pos_slice], out_payload[:, pos_slice]))
        parts.append(ik_motion_ae2_rotation_features(cur_payload[:, rot_slice], out_payload[:, rot_slice]))
        parts.append(ik_motion_ae2_rotation_features(cur_payload[:, start_rot_slice], out_payload[:, start_rot_slice]))
        if toe_slice is not None:
            assert isinstance(toe_slice, slice)
            parts.append(out_payload[:, toe_slice] - cur_payload[:, toe_slice])
    return torch.cat(parts, dim=-1)


def ik_motion_ae_window_feature_rows(
    ae: object | None,
    store: SimpleClipStore,
    cur_vec: torch.Tensor,
    out_vec: torch.Tensor,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
) -> torch.Tensor:
    return ik_root_conditioned_pose_window_feature_rows(store, clip_ids, cur_idx, out_vec)


def ik_motion_ae2_frame_feature_weights(
    store: SimpleClipStore,
    frame_feature_dim: int,
    ae2_loss_weight: float,
    *,
    dtype: torch.dtype,
    device: torch.device,
) -> torch.Tensor:
    nonfoot_scale = 1.0
    if float(ae2_loss_weight) > float(AE2_BAKED_NORMAL_LOSS_WEIGHT) > 0.0:
        nonfoot_scale = float(AE2_BAKED_NORMAL_LOSS_WEIGHT) / float(ae2_loss_weight)
    weights = torch.full((int(frame_feature_dim),), float(nonfoot_scale), dtype=dtype, device=device)
    cursor = 0
    cursor += 2  # pelvis position delta: flat magnitude + vertical
    cursor += 2  # pelvis rotation: swing + twist
    for spec in store.ik_payload_slices:
        if str(spec.get("kind", "")).lower().strip() != "leg":
            continue
        pos_slice = spec["pos"]
        rot_slice = spec["rot6"]
        start_rot_slice = spec["start_rot6"]
        toe_slice = spec["toe_float"]
        assert isinstance(pos_slice, slice)
        assert isinstance(rot_slice, slice)
        assert isinstance(start_rot_slice, slice)
        weights[cursor] = 1.0
        weights[cursor + 1] = 0.0
        cursor += 2
        weights[cursor : cursor + 2] = 1.0
        cursor += 2
        cursor += 2
        if toe_slice is not None:
            assert isinstance(toe_slice, slice)
            toe_dim = int(toe_slice.stop) - int(toe_slice.start)
            weights[cursor : cursor + toe_dim] = 1.0
            cursor += toe_dim
    if int(cursor) != int(frame_feature_dim):
        raise ValueError(f"AE2 feature weight cursor {cursor} does not match frame_feature_dim {frame_feature_dim}")
    return weights


def ik_motion_ae2_window_rows(
    context: torch.Tensor,
    row: torch.Tensor,
) -> torch.Tensor:
    return torch.cat((context, row[:, None, :]), dim=1).reshape(row.shape[0], -1)


def ik_motion_ae2_score_window_rows(
    ae2: torch.nn.Module,
    mean: torch.Tensor,
    std: torch.Tensor,
    window_rows: torch.Tensor,
    feature_weights: torch.Tensor | None = None,
) -> torch.Tensor:
    x = (window_rows - mean) / std
    recon = ae2(x)
    residual_sq = (recon - x).square()
    if feature_weights is not None:
        if int(feature_weights.numel()) != int(residual_sq.shape[-1]):
            raise ValueError(
                f"AE2 feature weights dim {int(feature_weights.numel())} does not match window dim {int(residual_sq.shape[-1])}"
            )
        residual_sq = residual_sq * feature_weights.to(dtype=residual_sq.dtype, device=residual_sq.device).reshape(1, -1)
    return residual_sq.mean(dim=-1)


def ik_motion_ae2_window_shape(ae2: torch.nn.Module) -> tuple[int, int]:
    schema = getattr(ae2, "_ik_motion_ae2_schema", None)
    if not isinstance(schema, dict):
        raise ValueError("IK motion AE2 is missing its schema.")
    return max(1, int(schema["window_frames"])), int(schema["frame_feature_dim"])


def is_ik_motion_window_ae(ae: object | None) -> bool:
    return isinstance(getattr(ae, "_ik_motion_ae2_schema", None), dict)


def ik_motion_ae2_sequence_windows(rows: torch.Tensor, window_frames: int) -> torch.Tensor:
    window_frames = max(1, int(window_frames))
    if int(rows.shape[0]) < window_frames:
        return rows.new_empty((0, window_frames * int(rows.shape[-1])))
    unfolded = rows.unfold(0, window_frames, 1).permute(0, 2, 1).contiguous()
    return unfolded.reshape(unfolded.shape[0], window_frames * int(rows.shape[-1]))


@torch.no_grad()
def ik_motion_ae_gt_score_mean(
    ae: torch.nn.Module,
    mean: torch.Tensor,
    std: torch.Tensor,
    store: SimpleClipStore,
    clip_ids: tuple[int, ...],
    _min_start: int,
    max_rows: int = 4096,
    batch_rows: int = 512,
) -> float:
    window_frames, _frame_dim = ik_motion_ae2_window_shape(ae)
    chunks: list[torch.Tensor] = []
    remaining = max(1, int(max_rows))
    for clip_i in clip_ids:
        max_cur = int(store.max_training_starts[int(clip_i)].detach().cpu())
        if max_cur < int(window_frames):
            continue
        idx = torch.arange(1, max_cur + 1, dtype=torch.long, device=store.device)
        row_clip_ids = torch.full_like(idx, int(clip_i))
        cur_vec = store.get_target_output(row_clip_ids, idx)
        out_vec = transition_target_output(store, row_clip_ids, idx)
        windows = ik_motion_ae2_sequence_windows(
            ik_motion_ae_window_feature_rows(ae, store, cur_vec, out_vec, row_clip_ids, idx),
            window_frames,
        )
        if int(windows.shape[0]) > remaining:
            windows = windows[:remaining]
        if int(windows.numel()) > 0:
            chunks.append(windows)
            remaining -= int(windows.shape[0])
        if remaining <= 0:
            break
    if not chunks:
        return float("nan")
    windows = torch.cat(chunks, dim=0)
    total = 0.0
    count = 0
    for start in range(0, int(windows.shape[0]), max(1, int(batch_rows))):
        batch = windows[start : start + int(batch_rows)]
        rows = ik_motion_ae2_score_window_rows(ae, mean, std, batch, None)
        total += float(rows.sum().detach().cpu())
        count += int(rows.numel())
    return total / float(max(1, count))


def ik_pose_ae4_leg_limb_indices_by_side(store: SimpleClipStore) -> tuple[int, int]:
    by_side: dict[str, int] = {}
    for limb_i, spec in enumerate(store.ik_payload_slices):
        if str(spec.get("kind", "")).lower().strip() != "leg":
            continue
        side = str(spec.get("side", "")).lower().strip()
        if side:
            by_side[side] = int(limb_i)
    if "l" not in by_side or "r" not in by_side:
        raise ValueError("AE4 needs left and right leg IK payloads.")
    return by_side["l"], by_side["r"]


def ik_pose_ae4_foot_positions_root_from_vec(store: SimpleClipStore, vec: torch.Tensor) -> torch.Tensor:
    payload = vec[:, payload_slice(store)]
    positions: list[torch.Tensor] = []
    for limb_i in ik_pose_ae4_leg_limb_indices_by_side(store):
        spec = store.ik_payload_slices[int(limb_i)]
        pos_slice = spec["pos"]
        assert isinstance(pos_slice, slice)
        positions.append(payload[:, pos_slice])
    return torch.stack(positions, dim=1)


def ik_pose_ae4_feature_rows(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
    current_vec: torch.Tensor,
    output_vec: torch.Tensor,
) -> torch.Tensor:
    root_features = store.get_input_root_features(clip_ids, cur_idx)
    root_pos, root_rot, _root_yaw, _root_heading = store.root_state(clip_ids, cur_idx)
    cur_foot_root = ik_pose_ae4_foot_positions_root_from_vec(store, current_vec)
    out_foot_root = ik_pose_ae4_foot_positions_root_from_vec(store, output_vec)
    cur_foot_world = tl.root_relative_to_world(cur_foot_root, root_pos, root_rot)
    out_foot_world = tl.root_relative_to_world(out_foot_root, root_pos, root_rot)
    foot_delta_xz = torch.stack(
        (
            out_foot_world[:, :, 0] - cur_foot_world[:, :, 0],
            out_foot_world[:, :, 2] - cur_foot_world[:, :, 2],
        ),
        dim=-1,
    )
    foot_speed = torch.linalg.vector_norm(foot_delta_xz, dim=-1) * float(store.prototype.fps)
    l_to_r = torch.stack(
        (
            out_foot_root[:, 1, 0] - out_foot_root[:, 0, 0],
            out_foot_root[:, 1, 2] - out_foot_root[:, 0, 2],
        ),
        dim=-1,
    )
    foot_mid = torch.stack((out_foot_root[:, :, 0].mean(dim=1), out_foot_root[:, :, 2].mean(dim=1)), dim=-1)
    pelvis = output_vec[:, 0:3]
    pelvis_rot = tl.clean_6d(output_vec[:, 3:9])
    return torch.cat((root_features, pelvis, pelvis_rot, foot_speed, l_to_r, foot_mid), dim=-1).float()


def ik_pose_ae4_full_output_feature_rows(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
    output_vec: torch.Tensor,
) -> torch.Tensor:
    root_features = store.get_input_root_features(clip_ids, cur_idx)
    return torch.cat((root_features, clean_output_vector(output_vec, store)), dim=-1).float()


def ik_pose_ae4_masked_pelvis_height_feature_rows(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
    output_vec: torch.Tensor,
) -> torch.Tensor:
    root_features = store.get_input_root_features(clip_ids, cur_idx)
    pose_vec = clean_output_vector(output_vec, store).clone()
    pose_vec[:, int(FOOT_ROLL_UP_AXIS)] = 0.0
    return torch.cat((root_features, pose_vec), dim=-1).float()


def ik_pose_ae4_root_context_feature_rows(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
) -> torch.Tensor:
    return store.get_input_root_features(clip_ids, cur_idx).float()


def ae4_pose_rotation_score_and_hinge_rows(
    output_rot: torch.Tensor,
    target_rot: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    if output_rot.numel() == 0 or target_rot.numel() == 0:
        rows = int(output_rot.shape[0]) if output_rot.ndim > 0 else 0
        empty = output_rot.new_zeros((rows,))
        return empty, empty
    out = output_rot.reshape(-1, 3, 3)
    target = target_rot.to(device=output_rot.device, dtype=output_rot.dtype).reshape(-1, 3, 3)
    angles = tl.geodesic_angles(out, target).reshape(output_rot.shape[:-2])
    scale = float(AE4_POSE_ROTATION_EXCESS_TO_HINGE)
    deadzone = math.radians(float(AE4_POSE_ROTATION_DEADZONE_DEG))
    score_rows = angles.mean(dim=-1) * scale
    hinge_rows = torch.relu(angles - deadzone).mean(dim=-1) * scale
    return score_rows, hinge_rows


def ik_pose_ae4_score_rows(
    ae4: object,
    input_mean: torch.Tensor,
    input_std: torch.Tensor,
    target_mean: torch.Tensor,
    target_std: torch.Tensor,
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
    current_vec: torch.Tensor,
    output_vec: torch.Tensor,
) -> torch.Tensor:
    if ae4_uses_pose_bank_projector(ae4):
        score_rows, _hinge_rows = ik_pose_ae4_distance_and_hinge_rows(
            ae4,
            input_mean,
            input_std,
            target_mean,
            target_std,
            store,
            clip_ids,
            cur_idx,
            current_vec,
            output_vec,
        )
        return score_rows
    if not isinstance(ae4, torch.nn.Module):
        raise TypeError(f"Unsupported AE4 prior type: {type(ae4).__name__}")
    schema = getattr(ae4, "_ik_pose_ae4_schema", {})
    feature = str(schema.get("feature", "")) if isinstance(schema, dict) else ""
    if feature == "ae4_root_context_to_full_ik_pose":
        rows = ik_pose_ae4_root_context_feature_rows(store, clip_ids, cur_idx)
    elif feature == "ae4_root_context_masked_pelvis_height_full_output_pose_to_full_ik":
        rows = ik_pose_ae4_masked_pelvis_height_feature_rows(store, clip_ids, cur_idx, output_vec)
    elif feature == "ae4_root_context_full_output_pose_to_full_ik":
        rows = ik_pose_ae4_full_output_feature_rows(store, clip_ids, cur_idx, output_vec)
    else:
        rows = ik_pose_ae4_feature_rows(store, clip_ids, cur_idx, current_vec, output_vec)
    expected_dim = int(schema.get("input_dim", 0)) if isinstance(schema, dict) else 0
    if expected_dim > 0 and int(rows.shape[-1]) != expected_dim:
        raise ValueError(f"AE4 row dim {int(rows.shape[-1])}, expected {expected_dim}")
    x = (rows - input_mean) / input_std
    pred_y = ae4(x)
    target_y = (output_vec - target_mean) / target_std
    return (pred_y - target_y).square().mean(dim=-1)


def ik_pose_ae4_distance_and_hinge_rows(
    ae4: object,
    input_mean: torch.Tensor,
    input_std: torch.Tensor,
    target_mean: torch.Tensor,
    target_std: torch.Tensor,
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
    current_vec: torch.Tensor,
    output_vec: torch.Tensor,
    ae4_source_store: SimpleClipStore | None = None,
    ae4_source_clip_ids: torch.Tensor | None = None,
    ae4_source_idx: torch.Tensor | None = None,
    deadzone_rows: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    if ae4_uses_pose_bank_projector(ae4):
        score_rows, hinge_rows, _target_pin_labels = ik_pose_ae4_posebank_projection_rows(
            ae4,
            store,
            clip_ids,
            cur_idx,
            output_vec,
            ae4_source_store=ae4_source_store,
            ae4_source_clip_ids=ae4_source_clip_ids,
            ae4_source_idx=ae4_source_idx,
            deadzone_rows=deadzone_rows,
        )
        return score_rows, hinge_rows

    if not isinstance(ae4, torch.nn.Module):
        raise TypeError(f"Unsupported AE4 prior type: {type(ae4).__name__}")

    def _hinge_from_joint_dist(joint_dist: torch.Tensor) -> torch.Tensor:
        if deadzone_rows is None:
            deadzone = float(AE4_POSE_DISTANCE_DEADZONE_M)
        else:
            deadzone = deadzone_rows.to(device=joint_dist.device, dtype=joint_dist.dtype)[:, None]
        return torch.relu(joint_dist - deadzone).mean(dim=-1)

    schema = getattr(ae4, "_ik_pose_ae4_schema", {})
    feature = str(schema.get("feature", "")) if isinstance(schema, dict) else ""
    if feature == "ae4_root_context_to_full_ik_pose":
        rows = ik_pose_ae4_root_context_feature_rows(store, clip_ids, cur_idx)
    elif feature == "ae4_root_context_masked_pelvis_height_full_output_pose_to_full_ik":
        rows = ik_pose_ae4_masked_pelvis_height_feature_rows(store, clip_ids, cur_idx, output_vec)
    elif feature == "ae4_root_context_full_output_pose_to_full_ik":
        rows = ik_pose_ae4_full_output_feature_rows(store, clip_ids, cur_idx, output_vec)
    else:
        rows = ik_pose_ae4_feature_rows(store, clip_ids, cur_idx, current_vec, output_vec)
    expected_dim = int(schema.get("input_dim", 0)) if isinstance(schema, dict) else 0
    if expected_dim > 0 and int(rows.shape[-1]) != expected_dim:
        raise ValueError(f"AE4 row dim {int(rows.shape[-1])}, expected {expected_dim}")
    x = (rows - input_mean) / input_std
    recon_vec = clean_output_vector(ae4(x) * target_std + target_mean, store)
    root_pos, root_rot = transition_output_root_state(store, clip_ids, cur_idx)
    output_pose, _raw_output_pose = tl.output_to_pose(output_vec, store.prototype)
    recon_pose, _raw_recon_pose = tl.output_to_pose(recon_vec, store.prototype)
    output_pos, output_rot, _output_canon = tl.fk_from_pose(
        store.prototype,
        root_pos,
        root_rot,
        output_pose,
        store.device,
    )
    recon_pos, recon_rot, _recon_canon = tl.fk_from_pose(
        store.prototype,
        root_pos,
        root_rot,
        recon_pose,
        store.device,
    )
    joint_dist = torch.sqrt((output_pos - recon_pos).square().sum(dim=-1).clamp_min(1.0e-12))
    rot_score_rows, rot_hinge_rows = ae4_pose_rotation_score_and_hinge_rows(output_rot, recon_rot.detach())
    score_rows = joint_dist.mean(dim=-1) + rot_score_rows
    hinge_rows = _hinge_from_joint_dist(joint_dist) + rot_hinge_rows
    return score_rows, hinge_rows


def ik_pose_ae4_posebank_projection_rows(
    ae4: object,
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
    output_vec: torch.Tensor,
    ae4_source_store: SimpleClipStore | None = None,
    ae4_source_clip_ids: torch.Tensor | None = None,
    ae4_source_idx: torch.Tensor | None = None,
    deadzone_rows: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    if not ae4_uses_pose_bank_projector(ae4):
        raise TypeError(f"AE4 bank pin targets require the pose-bank projector, got {type(ae4).__name__}")
    assert isinstance(ae4, IKPoseBankProjectorPrior)

    def _hinge_from_joint_dist(joint_dist: torch.Tensor) -> torch.Tensor:
        if deadzone_rows is None:
            deadzone = float(AE4_POSE_DISTANCE_DEADZONE_M)
        else:
            deadzone = deadzone_rows.to(device=joint_dist.device, dtype=joint_dist.dtype)[:, None]
        return torch.relu(joint_dist - deadzone).mean(dim=-1)

    output_pose, _raw_output_pose = tl.output_to_pose(output_vec, store.prototype)
    root_pos, root_rot = transition_output_root_state(store, clip_ids, cur_idx)
    output_pos, output_rot, _output_canon = tl.fk_from_pose(
        store.prototype,
        root_pos,
        root_rot,
        output_pose,
        store.device,
    )
    source_store = ae4_source_store if ae4_source_store is not None else store
    source_clip_ids = ae4_source_clip_ids if ae4_source_clip_ids is not None else clip_ids
    source_idx = ae4_source_idx if ae4_source_idx is not None else cur_idx
    query_pose_vec = ae4.query_pose_vectors_from_output(store, output_pose["pelvis_pos"], output_rot, root_rot)
    projection = ae4.project_rows(
        store,
        source_store,
        source_clip_ids,
        source_idx,
        query_pose_vec,
        root_pos,
        root_rot,
    )
    target_pos = projection["world_pos"]
    target_rot = projection["world_rot"]
    target_pin_labels = projection["target_pin_labels"].to(device=output_vec.device, dtype=output_vec.dtype).detach()
    joint_dist = torch.sqrt((output_pos - target_pos).square().sum(dim=-1).clamp_min(1.0e-12))
    rot_score_rows, rot_hinge_rows = ae4_pose_rotation_score_and_hinge_rows(output_rot, target_rot.detach())
    score_rows = joint_dist.mean(dim=-1) + rot_score_rows
    hinge_rows = _hinge_from_joint_dist(joint_dist) + rot_hinge_rows
    return score_rows, hinge_rows, target_pin_labels


def ae4_bank_pin_score_rows(pin_logits: torch.Tensor, target_pin_labels: torch.Tensor) -> torch.Tensor:
    pin_dim = int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)
    if int(pin_logits.shape[-1]) < pin_dim or int(target_pin_labels.shape[-1]) < pin_dim:
        return torch.zeros((*pin_logits.shape[:-1],), dtype=pin_logits.dtype, device=pin_logits.device)
    target = target_pin_labels[..., :pin_dim].to(device=pin_logits.device, dtype=pin_logits.dtype).detach()
    signed_logits = (target * 2.0 - 1.0) * pin_logits[..., :pin_dim]
    return torch.sigmoid(signed_logits).sum(dim=-1)


def ae4_bank_pin_row_scope_rows(
    effective_k: torch.Tensor,
    max_k: int,
    init_pose_noise_batch: "InitPoseNoiseBatch | None",
    dtype: torch.dtype,
) -> torch.Tensor:
    full_k_rows = (effective_k >= int(max_k)).to(dtype=dtype)
    return torch.ones_like(full_k_rows)


def forced_idle_tail_row_scope_rows(
    row_count: int,
    original_batch_size: int,
    forced_idle_batch_fraction: float | None,
    device: torch.device,
    dtype: torch.dtype,
) -> torch.Tensor:
    count = forced_idle_batch_row_count(int(original_batch_size), forced_idle_batch_fraction)
    count = min(max(0, int(count)), max(0, int(row_count)))
    scope = torch.zeros((max(0, int(row_count)),), dtype=dtype, device=device)
    if count > 0:
        rows = torch.arange(int(row_count) - count, int(row_count), device=device)
        scope.index_fill_(0, rows, 1.0)
    return scope


def ae4_bank_pin_root_delta_scale_rows(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
) -> torch.Tensor:
    cached = getattr(store, "ae4_bank_pin_root_delta_scale_by_frame", None)
    if cached is not None:
        return cached.index_select(0, store.frame_index(clip_ids, cur_idx))
    cutoff = max(float(getattr(store, "ae4_bank_pin_speed_cutoff_mps", 0.0)), 1.0e-6)
    cur_root_pos, _cur_root_rot, _cur_yaw, _cur_heading = store.root_state(clip_ids, cur_idx)
    next_root_pos, _next_root_rot, _next_yaw, _next_heading = store.root_state(clip_ids, cur_idx + 1)
    root_delta_xz = torch.stack(
        (next_root_pos[:, 0] - cur_root_pos[:, 0], next_root_pos[:, 2] - cur_root_pos[:, 2]),
        dim=-1,
    )
    root_speed = torch.linalg.vector_norm(root_delta_xz, dim=-1) * float(store.prototype.fps)
    translation_scale = torch.clamp(1.0 - root_speed / cutoff, min=0.0, max=1.0)
    yaw_cutoff = max(float(getattr(store, "ae4_bank_pin_yaw_cutoff_rad", 0.0)), 1.0e-6)
    yaw_delta = tl.wrap_angle(_next_yaw - _cur_yaw).abs()
    yaw_scale = torch.clamp(1.0 - yaw_delta / yaw_cutoff, min=0.0, max=1.0)
    return translation_scale * yaw_scale


def max_turn45l_root_yaw_delta_rad(store: SimpleClipStore) -> float:
    for clip_id, clip in enumerate(store.clips):
        if Path(str(clip.path)).stem.lower() != "m_neutral_stand_turn_045_l":
            continue
        if bool(clip.cyclic_animation):
            count = max(0, int(store.periods[int(clip_id)].detach().cpu().item()))
        else:
            count = max(0, int(store.lengths[int(clip_id)].detach().cpu().item()) - 1)
        if count <= 0:
            break
        idx = torch.arange(count, dtype=torch.long, device=store.device)
        ids = torch.full((count,), int(clip_id), dtype=torch.long, device=store.device)
        _cur_pos, _cur_rot, cur_yaw, _cur_heading = store.root_state(ids, idx)
        _next_pos, _next_rot, next_yaw, _next_heading = store.root_state(ids, idx + 1)
        yaw_delta = tl.wrap_angle(next_yaw - cur_yaw).abs()
        if int(yaw_delta.numel()) > 0:
            return float(yaw_delta.max().detach().cpu().item())
        break
    return 0.0


def ae3_bank_pin_phase_scale_rows(effective_k: torch.Tensor, step: int) -> tuple[torch.Tensor, torch.Tensor]:
    """Crossfade pin regularizers: AE3 early, pose-bank pin late."""
    k_minus_one = (effective_k.to(dtype=torch.float32) - 1.0).clamp(min=1.0)
    phase = (torch.full_like(k_minus_one, float(step)) / k_minus_one).clamp(min=0.0, max=1.0)
    start_hold = float(AE3_BANK_PIN_PHASE_START_HOLD_FRACTION)
    end_hold = float(AE3_BANK_PIN_PHASE_END_HOLD_FRACTION)
    blend_span = max(1.0e-6, 1.0 - start_hold - end_hold)
    bank_scale = ((phase - start_hold) / blend_span).clamp(min=0.0, max=1.0)
    ae3_scale = 1.0 - bank_scale
    return ae3_scale, bank_scale


def ae3_bank_pin_phase_scale_for_segment_rows(
    effective_k: torch.Tensor,
    segment_step: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Crossfade pin regularizers inside each reset-mixed rollout segment."""
    k_minus_one = (effective_k.to(dtype=torch.float32) - 1.0).clamp(min=1.0)
    phase = (segment_step.to(dtype=torch.float32) / k_minus_one).clamp(min=0.0, max=1.0)
    start_hold = float(AE3_BANK_PIN_PHASE_START_HOLD_FRACTION)
    end_hold = float(AE3_BANK_PIN_PHASE_END_HOLD_FRACTION)
    blend_span = max(1.0e-6, 1.0 - start_hold - end_hold)
    bank_scale = ((phase - start_hold) / blend_span).clamp(min=0.0, max=1.0)
    ae3_scale = 1.0 - bank_scale
    return ae3_scale, bank_scale


@torch.no_grad()
def prepare_ae4_bank_pin_root_delta_scale_cache(
    store: SimpleClipStore,
    cutoff_mps: float,
    yaw_cutoff_rad: float,
) -> None:
    cutoff = max(float(cutoff_mps), 1.0e-6)
    yaw_cutoff = max(float(yaw_cutoff_rad), 1.0e-6)
    scale_by_frame = torch.ones((int(store.root_pos.shape[0]),), dtype=torch.float32, device=store.device)
    for clip_id, clip in enumerate(store.clips):
        if bool(clip.cyclic_animation):
            count = max(0, int(store.periods[int(clip_id)].detach().cpu().item()))
        else:
            count = max(0, int(store.lengths[int(clip_id)].detach().cpu().item()) - 1)
        if count <= 0:
            continue
        idx = torch.arange(count, dtype=torch.long, device=store.device)
        ids = torch.full((count,), int(clip_id), dtype=torch.long, device=store.device)
        cur_root_pos, _cur_root_rot, cur_yaw, _cur_heading = store.root_state(ids, idx)
        next_root_pos, _next_root_rot, next_yaw, _next_heading = store.root_state(ids, idx + 1)
        root_delta_xz = torch.stack(
            (next_root_pos[:, 0] - cur_root_pos[:, 0], next_root_pos[:, 2] - cur_root_pos[:, 2]),
            dim=-1,
        )
        root_speed = torch.linalg.vector_norm(root_delta_xz, dim=-1) * float(store.prototype.fps)
        translation_scale = torch.clamp(1.0 - root_speed / cutoff, min=0.0, max=1.0)
        yaw_delta = tl.wrap_angle(next_yaw - cur_yaw).abs()
        yaw_scale = torch.clamp(1.0 - yaw_delta / yaw_cutoff, min=0.0, max=1.0)
        scale = translation_scale * yaw_scale
        scale_by_frame.scatter_(0, store.frame_index(ids, idx), scale.float())
    store.ae4_bank_pin_root_delta_scale_by_frame = scale_by_frame
    store.ae4_bank_pin_yaw_cutoff_rad = float(yaw_cutoff)


@dataclass(frozen=True)
class InitPoseNoiseBatch:
    noisy_rows: torch.Tensor
    position_deltas: tuple[torch.Tensor, ...]
    scalar_deltas: tuple[torch.Tensor, ...]
    rotation_deltas: tuple[torch.Tensor, ...]
    global_yaw_delta: torch.Tensor


def init_noise_clean_count(batch_size: int, clean_fraction: float) -> int:
    batch_size = max(0, int(batch_size))
    if batch_size <= 0:
        return 0
    clean_fraction = max(0.0, min(1.0, float(clean_fraction)))
    return max(0, min(batch_size, int(round(batch_size * clean_fraction))))


def init_noise_enabled(clean_fraction: float) -> bool:
    return float(clean_fraction) < (1.0 - 1.0e-8)


def sample_init_noise_row_masks(
    batch_size: int,
    clean_fraction: float,
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor]:
    batch_size = max(0, int(batch_size))
    clean_count = init_noise_clean_count(batch_size, clean_fraction)
    clean_rows = torch.zeros((batch_size,), dtype=torch.bool, device=device)
    if clean_count > 0:
        perm = torch.randperm(batch_size, device=device)
        clean_rows[perm[:clean_count]] = True
    noisy_rows = ~clean_rows
    return clean_rows, noisy_rows


def sample_init_noise_row_mask_in_range(
    batch_size: int,
    start_row: int,
    row_count: int,
    noisy_fraction: float,
    device: torch.device,
) -> torch.Tensor:
    batch_size = max(0, int(batch_size))
    mask = torch.zeros((batch_size,), dtype=torch.bool, device=device)
    start_row = max(0, min(batch_size, int(start_row)))
    row_count = max(0, min(batch_size - start_row, int(row_count)))
    noisy_fraction = max(0.0, min(1.0, float(noisy_fraction)))
    if row_count <= 0 or noisy_fraction <= 0.0:
        return mask
    noisy_count = int(round(row_count * noisy_fraction))
    noisy_count = max(1, min(row_count, noisy_count))
    picked = torch.randperm(row_count, device=device)[:noisy_count] + start_row
    mask[picked] = True
    return mask


def forced_idle_batch_row_count(batch_size: int, fraction: float | None) -> int:
    batch_size = max(0, int(batch_size))
    if batch_size <= 0:
        return 0
    if fraction is None:
        count = 1
    else:
        count = int(math.ceil(batch_size * max(0.0, min(1.0, float(fraction)))))
    return max(0, min(batch_size, count))


def forced_turn45_batch_row_count(batch_size: int, fraction: float | None) -> int:
    batch_size = max(0, int(batch_size))
    if batch_size <= 0 or fraction is None or float(fraction) <= 0.0:
        return 0
    count = int(math.ceil(batch_size * max(0.0, min(1.0, float(fraction)))))
    return max(0, min(batch_size, count))


def sample_init_pose_noise_batch(
    store: SimpleClipStore,
    batch_size: int,
    amount: float,
    clean_fraction: float,
    *,
    device: torch.device | None = None,
    dtype: torch.dtype | None = None,
    noisy_rows: torch.Tensor | None = None,
    position_amount: float | None = None,
    rotation_amount: float | None = None,
    global_yaw_degrees: float = 0.0,
) -> InitPoseNoiseBatch:
    batch_size = max(0, int(batch_size))
    device = store.device if device is None else device
    dtype = torch.float32 if dtype is None else dtype
    if noisy_rows is None:
        _clean_rows, noisy_rows = sample_init_noise_row_masks(batch_size, clean_fraction, device)
    noisy_rows = noisy_rows.to(device=device, dtype=torch.bool).reshape(batch_size)
    noisy_f = noisy_rows.to(dtype=dtype)
    position_amount = float(amount) if position_amount is None else float(position_amount)
    rotation_amount = float(amount) if rotation_amount is None else float(rotation_amount)
    pos_sigma = max(0.0, position_amount) * float(POSE_NOISE_POS_SIGMA_M_AT_1)
    rot_sigma = max(0.0, rotation_amount) * float(POSE_NOISE_ROT_SIGMA_DEG_AT_1) * math.pi / 180.0
    scalar_sigma = max(0.0, position_amount) * float(POSE_NOISE_SCALAR_SIGMA_AT_1)
    yaw_sigma = max(0.0, float(global_yaw_degrees)) * math.pi / 180.0
    if pos_sigma <= 0.0 and scalar_sigma <= 0.0 and rot_sigma <= 0.0 and yaw_sigma <= 0.0:
        noisy_rows = torch.zeros_like(noisy_rows)
        noisy_f = noisy_rows.to(dtype=dtype)
    position_deltas = tuple(
        (
            torch.randn((batch_size, int(sl.stop - sl.start)), dtype=dtype, device=device) * pos_sigma * noisy_f[:, None]
            if pos_sigma > 0.0
            else torch.zeros((batch_size, int(sl.stop - sl.start)), dtype=dtype, device=device)
        )
        for sl in vector_position_slices(store)
    )
    scalar_deltas = tuple(
        (
            torch.randn((batch_size, int(sl.stop - sl.start)), dtype=dtype, device=device)
            * scalar_sigma
            * noisy_f[:, None]
            if scalar_sigma > 0.0
            else torch.zeros((batch_size, int(sl.stop - sl.start)), dtype=dtype, device=device)
        )
        for sl in vector_scalar_slices(store)
    )
    rotation_deltas: list[torch.Tensor] = []
    for _sl in vector_rot6_slices(store):
        if rot_sigma > 0.0:
            axis = torch.randn((batch_size, 3), dtype=dtype, device=device)
            angle = torch.randn((batch_size,), dtype=dtype, device=device) * rot_sigma * noisy_f
            rotation_deltas.append(tl.axis_angle_to_row_matrix(axis, angle))
        else:
            rotation_deltas.append(torch.eye(3, dtype=dtype, device=device).reshape(1, 3, 3).expand(batch_size, -1, -1).clone())
    if yaw_sigma > 0.0:
        global_yaw_delta = ik_motion_ae2_up_axis_row_matrix(
            torch.randn((batch_size,), dtype=dtype, device=device) * yaw_sigma * noisy_f
        )
    else:
        global_yaw_delta = torch.eye(3, dtype=dtype, device=device).reshape(1, 3, 3).expand(batch_size, -1, -1).clone()
    return InitPoseNoiseBatch(
        noisy_rows=noisy_rows,
        position_deltas=position_deltas,
        scalar_deltas=scalar_deltas,
        rotation_deltas=tuple(rotation_deltas),
        global_yaw_delta=global_yaw_delta,
    )


def sample_fixed_init_pose_noise_batch(
    store: SimpleClipStore,
    batch_size: int,
    clean_fraction: float,
    *,
    device: torch.device | None = None,
    dtype: torch.dtype | None = None,
    noisy_rows: torch.Tensor | None = None,
    strength_scale: float = 1.0,
) -> InitPoseNoiseBatch:
    strength_scale = max(0.0, float(strength_scale))
    return sample_init_pose_noise_batch(
        store,
        batch_size,
        amount=0.0,
        clean_fraction=clean_fraction,
        device=device,
        dtype=dtype,
        noisy_rows=noisy_rows,
        position_amount=INIT_NOISE_FIXED_POSITION_AMOUNT * strength_scale,
        rotation_amount=INIT_NOISE_FIXED_ROTATION_AMOUNT * strength_scale,
        global_yaw_degrees=INIT_NOISE_FIXED_GLOBAL_YAW_DEG * strength_scale,
    )


def empty_init_pose_noise_batch(
    store: SimpleClipStore,
    batch_size: int,
    *,
    device: torch.device | None = None,
    dtype: torch.dtype | None = None,
) -> InitPoseNoiseBatch:
    batch_size = max(0, int(batch_size))
    device = store.device if device is None else device
    dtype = torch.float32 if dtype is None else dtype
    eye = torch.eye(3, dtype=dtype, device=device).reshape(1, 3, 3).expand(batch_size, -1, -1).clone()
    return InitPoseNoiseBatch(
        noisy_rows=torch.zeros((batch_size,), dtype=torch.bool, device=device),
        position_deltas=tuple(
            torch.zeros((batch_size, int(sl.stop - sl.start)), dtype=dtype, device=device)
            for sl in vector_position_slices(store)
        ),
        scalar_deltas=tuple(
            torch.zeros((batch_size, int(sl.stop - sl.start)), dtype=dtype, device=device)
            for sl in vector_scalar_slices(store)
        ),
        rotation_deltas=tuple(eye.clone() for _sl in vector_rot6_slices(store)),
        global_yaw_delta=eye.clone(),
    )


def copy_init_pose_noise_batch_(dst: InitPoseNoiseBatch, src: InitPoseNoiseBatch) -> None:
    dst.noisy_rows.copy_(src.noisy_rows)
    for dst_delta, src_delta in zip(dst.position_deltas, src.position_deltas):
        dst_delta.copy_(src_delta)
    for dst_delta, src_delta in zip(dst.scalar_deltas, src.scalar_deltas):
        dst_delta.copy_(src_delta)
    for dst_delta, src_delta in zip(dst.rotation_deltas, src.rotation_deltas):
        dst_delta.copy_(src_delta)
    dst.global_yaw_delta.copy_(src.global_yaw_delta)


def fill_init_pose_noise_batch_(
    dst: InitPoseNoiseBatch,
    store: SimpleClipStore,
    amount: float,
    clean_fraction: float,
    force_last_noisy_count: int = 0,
    force_noisy_rows: torch.Tensor | None = None,
    exact_noisy_rows: torch.Tensor | None = None,
    fixed_strength_scale: float = 1.0,
) -> InitPoseNoiseBatch:
    if not init_noise_enabled(clean_fraction) and exact_noisy_rows is None:
        dst.noisy_rows.zero_()
        for delta in dst.position_deltas:
            delta.zero_()
        for delta in dst.scalar_deltas:
            delta.zero_()
        for delta in dst.rotation_deltas:
            delta.zero_()
            diag = torch.arange(3, device=delta.device)
            delta[:, diag, diag] = 1.0
        dst.global_yaw_delta.zero_()
        diag = torch.arange(3, device=dst.global_yaw_delta.device)
        dst.global_yaw_delta[:, diag, diag] = 1.0
        return dst
    batch_size = int(dst.noisy_rows.shape[0])
    forced_noisy_rows = max(0, min(batch_size, int(force_last_noisy_count)))
    noisy_rows: torch.Tensor | None = None
    if exact_noisy_rows is not None:
        noisy_rows = exact_noisy_rows.to(device=dst.noisy_rows.device, dtype=torch.bool).reshape(batch_size).clone()
    if forced_noisy_rows > 0 or force_noisy_rows is not None:
        if noisy_rows is None:
            _clean_rows, noisy_rows = sample_init_noise_row_masks(batch_size, clean_fraction, dst.noisy_rows.device)
        if forced_noisy_rows > 0:
            rows = torch.arange(batch_size - forced_noisy_rows, batch_size, device=dst.noisy_rows.device)
            noisy_rows.index_fill_(0, rows, True)
        if force_noisy_rows is not None and int(force_noisy_rows.numel()) > 0:
            rows = force_noisy_rows.to(device=dst.noisy_rows.device, dtype=torch.long).clamp(0, batch_size - 1)
            noisy_rows.index_fill_(0, rows, True)
    sampled = sample_fixed_init_pose_noise_batch(
        store,
        batch_size,
        clean_fraction,
        device=dst.noisy_rows.device,
        dtype=dst.position_deltas[0].dtype if dst.position_deltas else torch.float32,
        noisy_rows=noisy_rows,
        strength_scale=fixed_strength_scale,
    )
    copy_init_pose_noise_batch_(dst, sampled)
    return dst


def index_init_pose_noise_batch(noise_batch: InitPoseNoiseBatch, rows: torch.Tensor) -> InitPoseNoiseBatch:
    rows = rows.to(device=noise_batch.noisy_rows.device, dtype=torch.long)
    return InitPoseNoiseBatch(
        noisy_rows=noise_batch.noisy_rows.index_select(0, rows),
        position_deltas=tuple(delta.index_select(0, rows) for delta in noise_batch.position_deltas),
        scalar_deltas=tuple(delta.index_select(0, rows) for delta in noise_batch.scalar_deltas),
        rotation_deltas=tuple(delta.index_select(0, rows) for delta in noise_batch.rotation_deltas),
        global_yaw_delta=noise_batch.global_yaw_delta.index_select(0, rows),
    )


def apply_init_pose_noise_batch(
    store: SimpleClipStore,
    vec: torch.Tensor,
    noise_batch: InitPoseNoiseBatch | None,
) -> torch.Tensor:
    if noise_batch is None or int(vec.shape[0]) == 0:
        return vec
    if int(noise_batch.noisy_rows.shape[0]) != int(vec.shape[0]):
        raise ValueError(
            f"Init noise batch row count {int(noise_batch.noisy_rows.shape[0])} does not match vec batch {int(vec.shape[0])}"
        )
    out = vec.clone()
    for sl, delta in zip(vector_position_slices(store), noise_batch.position_deltas):
        out[:, sl] = out[:, sl] + delta.to(dtype=out.dtype)
    for sl, delta in zip(vector_scalar_slices(store), noise_batch.scalar_deltas):
        out[:, sl] = out[:, sl] + delta.to(dtype=out.dtype)
    for sl, delta in zip(vector_rot6_slices(store), noise_batch.rotation_deltas):
        base_rot = tl.rotation_6d_to_matrix(vec[:, sl])
        out[:, sl] = tl.rotmat_to_6d(delta.to(dtype=base_rot.dtype) @ base_rot)
    yaw_delta = noise_batch.global_yaw_delta.to(dtype=out.dtype)
    pelvis_pos = out[:, :3]
    position_slices = vector_position_slices(store)
    for sl in position_slices[1:]:
        rel = out[:, sl] - pelvis_pos
        out[:, sl] = pelvis_pos + torch.matmul(rel.unsqueeze(1), yaw_delta).squeeze(1)
    for sl in vector_rot6_slices(store):
        base_rot = tl.rotation_6d_to_matrix(out[:, sl])
        out[:, sl] = tl.rotmat_to_6d(base_rot @ yaw_delta)
    return out


def add_pose_noise_to_vector(store: SimpleClipStore, vec: torch.Tensor, amount: float) -> torch.Tensor:
    noise_batch = sample_init_pose_noise_batch(
        store,
        int(vec.shape[0]),
        float(amount),
        clean_fraction=0.0,
        device=vec.device,
        dtype=vec.dtype,
    )
    return apply_init_pose_noise_batch(store, vec, noise_batch)


def target_state(store: SimpleClipStore, clip_ids: torch.Tensor, idx: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    vec = store.get_target_output(clip_ids, idx)
    return vec, vec[:, :3], vec[:, payload_slice(store)]


def rollout_init_context_indices(init_starts: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    if bool(DUPLICATE_ROLLOUT_INIT_CONTEXT):
        return init_starts, init_starts
    return torch.clamp(init_starts - 1, min=0), init_starts


def rebase_output_vector_root(
    store: SimpleClipStore,
    vec: torch.Tensor,
    from_root_pos: torch.Tensor,
    from_root_rot: torch.Tensor,
    to_root_pos: torch.Tensor,
    to_root_rot: torch.Tensor,
) -> torch.Tensor:
    rebased = fast_rebase_output_vector_root(store, vec, from_root_pos, from_root_rot, to_root_pos, to_root_rot)
    return clean_output_vector(rebased, store)


def fast_rebase_output_vector_root(
    store: SimpleClipStore,
    vec: torch.Tensor,
    from_root_pos: torch.Tensor,
    from_root_rot: torch.Tensor,
    to_root_pos: torch.Tensor,
    to_root_rot: torch.Tensor,
) -> torch.Tensor:
    b = int(vec.shape[0])
    pelvis_pos = tl._rebase_root_local_position(vec[:, 0:3], from_root_pos, from_root_rot, to_root_pos, to_root_rot)
    pelvis_rot6 = tl._rebase_root_local_rot6(tl.clean_6d(vec[:, 3:9]), from_root_rot, to_root_rot)
    core_dim = store.Jcore * 6
    core = tl.clean_6d(vec[:, 9 : 9 + core_dim].reshape(-1, 6)).reshape(b, store.Jcore * 6)
    payload = tl.clean_ik_payload(
        vec[:, 9 + core_dim : 9 + core_dim + store.ik_payload_dim],
        store.ik_payload_slices,
        store.ik_payload_dim,
    )
    if store.ik_payload_dim == 0:
        return torch.cat((pelvis_pos, pelvis_rot6, core), dim=-1)

    pos_parts: list[torch.Tensor] = []
    rot_parts: list[torch.Tensor] = []
    start_rot_parts: list[torch.Tensor] = []
    toe_parts: list[torch.Tensor | None] = []
    for spec in store.ik_payload_slices:
        pos_slice = spec["pos"]
        rot_slice = spec["rot6"]
        start_rot_slice = spec["start_rot6"]
        toe_slice = spec["toe_float"]
        assert isinstance(pos_slice, slice)
        assert isinstance(rot_slice, slice)
        assert isinstance(start_rot_slice, slice)
        pos_parts.append(payload[:, pos_slice])
        rot_parts.append(payload[:, rot_slice])
        start_rot_parts.append(payload[:, start_rot_slice])
        if toe_slice is not None:
            assert isinstance(toe_slice, slice)
            toe_parts.append(payload[:, toe_slice])
        else:
            toe_parts.append(None)

    local_pos = torch.stack(pos_parts, dim=1)
    world_pos = torch.matmul(local_pos, from_root_rot) + from_root_pos[:, None, :]
    rebased_pos = torch.matmul(world_pos - to_root_pos[:, None, :], to_root_rot.transpose(-1, -2))

    all_rot6 = torch.cat((torch.stack(rot_parts, dim=1), torch.stack(start_rot_parts, dim=1)), dim=1)
    limb_count = len(rot_parts)
    all_rot = tl.rotation_6d_to_matrix(all_rot6.reshape(-1, 6)).reshape(b, limb_count * 2, 3, 3)
    world_rot = all_rot @ from_root_rot[:, None, :, :]
    rebased_rot6 = tl.rotmat_to_6d(
        (world_rot @ to_root_rot[:, None, :, :].transpose(-1, -2)).reshape(-1, 3, 3)
    ).reshape(b, limb_count * 2, 6)

    payload_parts: list[torch.Tensor] = []
    for limb_i, toe in enumerate(toe_parts):
        payload_parts.append(rebased_pos[:, limb_i])
        payload_parts.append(rebased_rot6[:, limb_i])
        payload_parts.append(rebased_rot6[:, limb_count + limb_i])
        if toe is not None:
            payload_parts.append(toe)
    rebased_payload = tl.clean_ik_payload(torch.cat(payload_parts, dim=-1), store.ik_payload_slices, store.ik_payload_dim)
    return torch.cat((pelvis_pos, pelvis_rot6, core, rebased_payload), dim=-1)


def transition_output_root_state(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    output_idx = cur_idx if tl.output_reference_uses_current_root() else cur_idx + 1
    root_pos, root_rot, _yaw, _heading = store.root_state(clip_ids, output_idx)
    return root_pos, root_rot


def current_state_as_transition_output(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
    cur_vec: torch.Tensor,
) -> torch.Tensor:
    if tl.output_reference_uses_current_root():
        return cur_vec
    cur_root_pos, cur_root_rot, _cur_yaw, _cur_heading = store.root_state(clip_ids, cur_idx)
    next_root_pos, next_root_rot, _next_yaw, _next_heading = store.root_state(clip_ids, cur_idx + 1)
    return rebase_output_vector_root(store, cur_vec, cur_root_pos, cur_root_rot, next_root_pos, next_root_rot)


def transition_target_output(store: SimpleClipStore, clip_ids: torch.Tensor, cur_idx: torch.Tensor) -> torch.Tensor:
    target_idx = cur_idx + 1
    target = store.get_target_output(clip_ids, target_idx)
    if tl.output_reference_uses_future_root():
        return target
    cur_root_pos, cur_root_rot, _cur_yaw, _cur_heading = store.root_state(clip_ids, cur_idx)
    target_root_pos, target_root_rot, _target_yaw, _target_heading = store.root_state(clip_ids, target_idx)
    return rebase_output_vector_root(store, target, target_root_pos, target_root_rot, cur_root_pos, cur_root_rot)


def advance_transition_output(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
    transition_vec: torch.Tensor,
) -> torch.Tensor:
    if tl.output_reference_uses_future_root():
        return clean_output_vector(transition_vec, store)
    next_idx = cur_idx + 1
    cur_root_pos, cur_root_rot, _cur_yaw, _cur_heading = store.root_state(clip_ids, cur_idx)
    next_root_pos, next_root_rot, _next_yaw, _next_heading = store.root_state(clip_ids, next_idx)
    return rebase_output_vector_root(store, transition_vec, cur_root_pos, cur_root_rot, next_root_pos, next_root_rot)


def advance_transition_state(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
    transition_vec: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    state_vec = advance_transition_output(store, clip_ids, cur_idx, transition_vec)
    return predicted_state_from_vector(state_vec, store)


def fast_clean_6d(d6: torch.Tensor) -> torch.Tensor:
    a1 = d6[..., 0:3]
    a2 = d6[..., 3:6]
    b1 = torch.nn.functional.normalize(a1, dim=-1, eps=1e-8)
    b2 = torch.nn.functional.normalize(a2 - (b1 * a2).sum(dim=-1, keepdim=True) * b1, dim=-1, eps=1e-8)
    return torch.cat((b1, b2), dim=-1)


def fast_clean_ik_payload(payload: torch.Tensor, store: SimpleClipStore) -> torch.Tensor:
    if int(store.ik_payload_dim) == 0:
        return payload
    pos_parts: list[torch.Tensor] = []
    rot_parts: list[torch.Tensor] = []
    start_rot_parts: list[torch.Tensor] = []
    toe_parts: list[torch.Tensor | None] = []
    for spec in store.ik_payload_slices:
        pos_slice = spec["pos"]
        rot_slice = spec["rot6"]
        start_rot_slice = spec["start_rot6"]
        toe_slice = spec["toe_float"]
        assert isinstance(pos_slice, slice)
        assert isinstance(rot_slice, slice)
        assert isinstance(start_rot_slice, slice)
        pos_parts.append(payload[:, pos_slice])
        rot_parts.append(payload[:, rot_slice])
        start_rot_parts.append(payload[:, start_rot_slice])
        if toe_slice is not None:
            assert isinstance(toe_slice, slice)
            toe_parts.append(payload[:, toe_slice])
        else:
            toe_parts.append(None)
    limb_count = len(rot_parts)
    all_rot6 = torch.cat((torch.stack(rot_parts, dim=1), torch.stack(start_rot_parts, dim=1)), dim=1)
    cleaned_rot6 = fast_clean_6d(all_rot6.reshape(-1, 6)).reshape(payload.shape[0], limb_count * 2, 6)
    parts: list[torch.Tensor] = []
    for limb_i, toe in enumerate(toe_parts):
        parts.append(pos_parts[limb_i])
        parts.append(cleaned_rot6[:, limb_i])
        parts.append(cleaned_rot6[:, limb_count + limb_i])
        if toe is not None:
            parts.append(toe.clamp(-1.0, 1.0))
    return torch.cat(parts, dim=-1)


def _row_matvec(vec: torch.Tensor, rot: torch.Tensor) -> torch.Tensor:
    return torch.matmul(vec.unsqueeze(1), rot).squeeze(1)


def _store_rows_for_batch(
    values: torch.Tensor,
    batch: int,
    field_name: str,
) -> torch.Tensor:
    """Expand ordinary geometry or repeat row-batched geometry for step-major work."""

    if values.ndim == 2:
        return values.unsqueeze(0).expand(batch, -1, -1)
    if values.ndim != 3:
        raise ValueError(f"{field_name} must be [item,value] or [row,item,value], got {tuple(values.shape)}")
    rows = int(values.shape[0])
    if rows == batch:
        return values
    if rows <= 0 or batch % rows != 0:
        raise ValueError(
            f"{field_name} has {rows} geometry rows but tensor batch is {batch}"
        )
    return values.repeat(batch // rows, 1, 1)


def _store_indexed_vector_for_batch(
    values: torch.Tensor,
    index: int,
    batch: int,
    field_name: str,
) -> torch.Tensor:
    return _store_rows_for_batch(values, batch, field_name)[:, int(index)]


def _axis_support_sign(axis_up: torch.Tensor) -> torch.Tensor:
    eps = 1e-5
    zeros = torch.zeros_like(axis_up)
    ones = torch.ones_like(axis_up)
    return torch.where(axis_up > eps, -ones, torch.where(axis_up < -eps, ones, zeros))


def _saturated_asin_ratio(value: torch.Tensor, saturation_radians: float) -> torch.Tensor:
    """Return ``clamp(asin(abs(value)) / radians, 0, 1)`` with finite gradients.

    Once ``abs(value)`` reaches ``sin(radians)``, the mathematical result is
    already the constant one.  Avoid evaluating asin on that saturated branch:
    asin's derivative is singular at one and can otherwise produce ``inf * 0 =
    NaN`` during the backward pass through the following clamp.
    """

    denominator = max(float(saturation_radians), 1e-6)
    if denominator > math.pi * 0.5:
        raise ValueError("asin saturation angle must be at most 90 degrees")
    magnitude = torch.clamp(value.abs(), 0.0, 1.0)
    saturated = magnitude >= math.sin(denominator)
    safe_magnitude = torch.where(saturated, torch.zeros_like(magnitude), magnitude)
    return torch.where(
        saturated,
        torch.ones_like(magnitude),
        torch.asin(safe_magnitude) / denominator,
    )


def _box_contact_from_axes(
    center: torch.Tensor,
    forward: torch.Tensor,
    side: torch.Tensor,
    up: torch.Tensor,
    half_dims: torch.Tensor,
    side_blend_rad: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    dtype = center.dtype
    half_dims = half_dims.to(dtype=dtype).reshape(1, 3)
    forward_sign = _axis_support_sign(forward[:, FOOT_ROLL_UP_AXIS])
    side_sign = _axis_support_sign(side[:, FOOT_ROLL_UP_AXIS])
    side_scale = _saturated_asin_ratio(side[:, FOOT_ROLL_UP_AXIS], side_blend_rad)
    forward_factor = (forward_sign != 0.0).to(dtype=dtype)
    amounts = torch.stack(
        (
            forward_sign * half_dims[:, 0] * forward_factor,
            side_sign * half_dims[:, 1] * side_scale,
            -half_dims[:, 2].expand_as(forward_sign),
        ),
        dim=-1,
    )
    point = center + forward * amounts[:, 0:1] + side * amounts[:, 1:2] + up * amounts[:, 2:3]
    return point, amounts


def _box_point_from_support(
    center: torch.Tensor,
    forward: torch.Tensor,
    side: torch.Tensor,
    up: torch.Tensor,
    support_amounts: torch.Tensor,
) -> torch.Tensor:
    return (
        center
        + forward * support_amounts[:, 0:1]
        + side * support_amounts[:, 1:2]
        + up * support_amounts[:, 2:3]
    )


def _row_rotation_vector_between(from_rot: torch.Tensor, to_rot: torch.Tensor) -> torch.Tensor:
    rel = to_rot @ from_rot.transpose(-1, -2)
    vee = torch.stack(
        (
            rel[:, 1, 2] - rel[:, 2, 1],
            rel[:, 2, 0] - rel[:, 0, 2],
            rel[:, 0, 1] - rel[:, 1, 0],
        ),
        dim=-1,
    )
    vee_norm = torch.linalg.norm(vee, dim=-1)
    cos_angle = torch.clamp((rel[:, 0, 0] + rel[:, 1, 1] + rel[:, 2, 2] - 1.0) * 0.5, -1.0, 1.0)
    angle = torch.atan2(vee_norm * 0.5, cos_angle)
    scale = torch.where(
        vee_norm > 1e-7,
        angle / torch.clamp(vee_norm, min=1e-7),
        torch.full_like(vee_norm, 0.5),
    )
    return vee * scale.unsqueeze(-1)


def _row_rotation_from_vector(rotvec: torch.Tensor) -> torch.Tensor:
    angle = torch.linalg.norm(rotvec, dim=-1)
    axis = tl.normalize(rotvec)
    return tl.axis_angle_to_row_matrix(axis, angle)


def inertia_body_names() -> tuple[str, str, str]:
    return ("pelvis", "foot_l", "foot_r")


def inertia_transition_delta_rows(
    store: SimpleClipStore,
    from_vec: torch.Tensor,
    to_vec: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Return pelvis/foot transition deltas in the controller IK vector space.

    Positions are simple output-space deltas. Rotations are row-vector rotation
    vectors for the requested local rotation change. This mirrors the controller
    input/output convention and avoids scoring raw world speed.
    """

    linear_parts = [to_vec[:, 0:3] - from_vec[:, 0:3]]
    from_rot_parts = [tl.rotation_6d_to_matrix(tl.clean_6d(from_vec[:, 3:9]))]
    to_rot_parts = [tl.rotation_6d_to_matrix(tl.clean_6d(to_vec[:, 3:9]))]
    payload = payload_slice(store)
    from_payload = from_vec[:, payload]
    to_payload = to_vec[:, payload]
    for limb_i in ik_pose_ae4_leg_limb_indices_by_side(store):
        spec = store.ik_payload_slices[int(limb_i)]
        pos_slice = spec["pos"]
        rot_slice = spec["rot6"]
        assert isinstance(pos_slice, slice)
        assert isinstance(rot_slice, slice)
        linear_parts.append(to_payload[:, pos_slice] - from_payload[:, pos_slice])
        from_rot_parts.append(tl.rotation_6d_to_matrix(tl.clean_6d(from_payload[:, rot_slice])))
        to_rot_parts.append(tl.rotation_6d_to_matrix(tl.clean_6d(to_payload[:, rot_slice])))
    from_rot = torch.stack(from_rot_parts, dim=1)
    to_rot = torch.stack(to_rot_parts, dim=1)
    angular = _row_rotation_vector_between(from_rot.reshape(-1, 3, 3), to_rot.reshape(-1, 3, 3)).reshape(
        from_vec.shape[0], len(from_rot_parts), 3
    )
    return torch.stack(linear_parts, dim=1), angular


def gt_mse_tracking_loss_rows(
    store: SimpleClipStore,
    cur_vec: torch.Tensor,
    pred_vec: torch.Tensor,
    target_vec: torch.Tensor,
    target_cur_vec: torch.Tensor | None = None,
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    """AE1 replacement: GT pose MSE plus one-frame linear/angular rate MSE."""

    pred_pos = torch.stack([pred_vec[:, sl] for sl in vector_position_slices(store)], dim=1)
    target_pos = torch.stack([target_vec[:, sl] for sl in vector_position_slices(store)], dim=1)
    cur_pos = torch.stack([cur_vec[:, sl] for sl in vector_position_slices(store)], dim=1)
    target_cur_source = cur_vec if target_cur_vec is None else target_cur_vec
    target_cur_pos = torch.stack([target_cur_source[:, sl] for sl in vector_position_slices(store)], dim=1)
    pos_rows = (pred_pos - target_pos).square().mean(dim=(1, 2))

    pred_rot_parts = [tl.rotation_6d_to_matrix(tl.clean_6d(pred_vec[:, sl])) for sl in vector_rot6_slices(store)]
    target_rot_parts = [tl.rotation_6d_to_matrix(tl.clean_6d(target_vec[:, sl])) for sl in vector_rot6_slices(store)]
    cur_rot_parts = [tl.rotation_6d_to_matrix(tl.clean_6d(cur_vec[:, sl])) for sl in vector_rot6_slices(store)]
    target_cur_rot_parts = [
        tl.rotation_6d_to_matrix(tl.clean_6d(target_cur_source[:, sl])) for sl in vector_rot6_slices(store)
    ]
    pred_rot = torch.stack(pred_rot_parts, dim=1)
    target_rot = torch.stack(target_rot_parts, dim=1)
    cur_rot = torch.stack(cur_rot_parts, dim=1)
    target_cur_rot = torch.stack(target_cur_rot_parts, dim=1)
    rot_delta = _row_rotation_vector_between(
        pred_rot.reshape(-1, 3, 3),
        target_rot.reshape(-1, 3, 3),
    ).reshape(pred_vec.shape[0], len(pred_rot_parts), 3)
    rot_rows = rot_delta.square().mean(dim=(1, 2))

    pred_linear_delta = pred_pos - cur_pos
    target_linear_delta = target_pos - target_cur_pos
    pred_angular_delta = _row_rotation_vector_between(
        cur_rot.reshape(-1, 3, 3),
        pred_rot.reshape(-1, 3, 3),
    ).reshape(pred_vec.shape[0], len(pred_rot_parts), 3)
    target_angular_delta = _row_rotation_vector_between(
        target_cur_rot.reshape(-1, 3, 3),
        target_rot.reshape(-1, 3, 3),
    ).reshape(pred_vec.shape[0], len(pred_rot_parts), 3)
    linvel_rows = (pred_linear_delta - target_linear_delta).square().mean(dim=(1, 2))
    angvel_rows = (pred_angular_delta - target_angular_delta).square().mean(dim=(1, 2))
    raw_rows = (pos_rows + rot_rows + linvel_rows + angvel_rows) * 0.25
    scaled_rows = raw_rows * float(GT_MSE_LOSS_SCALE)
    return scaled_rows, {
        GT_MSE_RAW_TERM_NAME: raw_rows,
        GT_MSE_POS_TERM_NAME: pos_rows,
        GT_MSE_ROT_TERM_NAME: rot_rows,
        GT_MSE_LINVEL_TERM_NAME: linvel_rows,
        GT_MSE_ANGVEL_TERM_NAME: angvel_rows,
    }


def inertia_acceleration_excess_rows(
    store: SimpleClipStore,
    prev_linear_delta: torch.Tensor,
    prev_angular_delta: torch.Tensor,
    cur_linear_delta: torch.Tensor,
    cur_angular_delta: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    linear_limits = getattr(store, "inertia_linear_accel_limits", None)
    angular_limits = getattr(store, "inertia_angular_accel_limits", None)
    if not isinstance(linear_limits, torch.Tensor) or not isinstance(angular_limits, torch.Tensor):
        raise RuntimeError("inertia acceleration loss is enabled but GT inertia limits were not prepared")
    linear_limits = linear_limits.to(device=cur_linear_delta.device, dtype=cur_linear_delta.dtype).reshape(1, -1)
    angular_limits = angular_limits.to(device=cur_angular_delta.device, dtype=cur_angular_delta.dtype).reshape(1, -1)
    linear_accel = torch.linalg.vector_norm(cur_linear_delta - prev_linear_delta, dim=-1)
    angular_accel = torch.linalg.vector_norm(cur_angular_delta - prev_angular_delta, dim=-1)
    linear_excess = torch.relu(linear_accel - linear_limits)
    angular_excess = torch.relu(angular_accel - angular_limits)
    linear_ratio = linear_excess / linear_limits.clamp_min(1.0e-8)
    angular_ratio = angular_excess / angular_limits.clamp_min(1.0e-8)
    rows = torch.cat((linear_ratio, angular_ratio), dim=-1).mean(dim=-1)
    bad_rows = ((linear_excess > 0.0).any(dim=-1) | (angular_excess > 0.0).any(dim=-1)).to(dtype=rows.dtype)
    return rows, linear_excess.mean(dim=-1), angular_excess.mean(dim=-1), bad_rows


@torch.no_grad()
def compute_real_dataset_inertia_acceleration_limits(
    store: SimpleClipStore,
    clip_ids: tuple[int, ...],
    batch_rows: int = 8192,
) -> dict[str, object]:
    linear_limit = torch.zeros((len(inertia_body_names()),), dtype=torch.float32, device=store.device)
    angular_limit = torch.zeros_like(linear_limit)
    sample_count = 0
    transition_sample_count = 0
    init_linear_max = torch.zeros_like(linear_limit)
    init_angular_max = torch.zeros_like(linear_limit)
    transition_linear_max = torch.zeros_like(linear_limit)
    transition_angular_max = torch.zeros_like(linear_limit)
    for clip_id in clip_ids:
        clip = store.clips[int(clip_id)]
        max_start = max_training_start_for_clip(clip, store.cfg)
        if max_start < 1:
            continue
        for start in range(1, max_start + 1, max(1, int(batch_rows))):
            end = min(max_start + 1, start + max(1, int(batch_rows)))
            idx = torch.arange(start, end, dtype=torch.long, device=store.device)
            ids = torch.full_like(idx, int(clip_id))
            prev_vec, _prev_pelvis, _prev_payload = target_state(store, ids, idx - 1)
            cur_vec, _cur_pelvis, _cur_payload = target_state(store, ids, idx)
            next_vec = transition_target_output(store, ids, idx)

            prev_linear_delta, prev_angular_delta = inertia_transition_delta_rows(store, prev_vec, cur_vec)
            cur_linear_delta, cur_angular_delta = inertia_transition_delta_rows(store, cur_vec, next_vec)
            init_linear = torch.linalg.vector_norm(cur_linear_delta - prev_linear_delta, dim=-1)
            init_angular = torch.linalg.vector_norm(cur_angular_delta - prev_angular_delta, dim=-1)
            init_linear_max = torch.maximum(init_linear_max, init_linear.amax(dim=0))
            init_angular_max = torch.maximum(init_angular_max, init_angular.amax(dim=0))
            linear_limit = torch.maximum(linear_limit, init_linear.amax(dim=0))
            angular_limit = torch.maximum(angular_limit, init_angular.amax(dim=0))
            sample_count += int(idx.numel())

            next_pair = idx < int(max_start)
            if bool(next_pair.any().item()):
                next_ids = ids[next_pair]
                next_idx = idx[next_pair]
                next_state_vec, _next_state_pelvis, _next_state_payload = target_state(store, next_ids, next_idx + 1)
                next_next_vec = transition_target_output(store, next_ids, next_idx + 1)
                next_linear_delta, next_angular_delta = inertia_transition_delta_rows(
                    store,
                    next_state_vec,
                    next_next_vec,
                )
                transition_linear = torch.linalg.vector_norm(
                    next_linear_delta - cur_linear_delta[next_pair],
                    dim=-1,
                )
                transition_angular = torch.linalg.vector_norm(
                    next_angular_delta - cur_angular_delta[next_pair],
                    dim=-1,
                )
                transition_linear_max = torch.maximum(transition_linear_max, transition_linear.amax(dim=0))
                transition_angular_max = torch.maximum(transition_angular_max, transition_angular.amax(dim=0))
                linear_limit = torch.maximum(linear_limit, transition_linear.amax(dim=0))
                angular_limit = torch.maximum(angular_limit, transition_angular.amax(dim=0))
                transition_sample_count += int(next_idx.numel())
    eps = torch.full_like(linear_limit, 1.0e-7)
    return {
        "body_names": list(inertia_body_names()),
        "linear_limits": (linear_limit + eps).detach(),
        "angular_limits": (angular_limit + eps).detach(),
        "sample_count": int(sample_count),
        "transition_sample_count": int(transition_sample_count),
        "init_linear_max": init_linear_max.detach(),
        "init_angular_max": init_angular_max.detach(),
        "transition_linear_max": transition_linear_max.detach(),
        "transition_angular_max": transition_angular_max.detach(),
    }


def prepare_inertia_acceleration_limits(store: SimpleClipStore, real_clip_ids: tuple[int, ...]) -> dict[str, object]:
    limits = compute_real_dataset_inertia_acceleration_limits(store, real_clip_ids)
    store.inertia_linear_accel_limits = limits["linear_limits"]
    store.inertia_angular_accel_limits = limits["angular_limits"]
    return limits


def inertia_limits_metadata(limits: dict[str, object]) -> dict[str, object]:
    def tensor_list(key: str) -> list[float]:
        value = limits.get(key)
        if isinstance(value, torch.Tensor):
            return [float(x) for x in value.detach().cpu().tolist()]
        return []

    return {
        "body_names": list(limits.get("body_names", inertia_body_names())),
        "sample_count": int(limits.get("sample_count", 0)),
        "transition_sample_count": int(limits.get("transition_sample_count", 0)),
        "linear_limits": tensor_list("linear_limits"),
        "angular_limits": tensor_list("angular_limits"),
        "init_linear_max": tensor_list("init_linear_max"),
        "init_angular_max": tensor_list("init_angular_max"),
        "transition_linear_max": tensor_list("transition_linear_max"),
        "transition_angular_max": tensor_list("transition_angular_max"),
    }


def _foot_roll_step_t_like(ref: torch.Tensor, steps: int) -> torch.Tensor:
    device = ref.device
    key = (device.type, -1 if device.index is None else int(device.index), str(ref.dtype), int(steps))
    cached = _FOOT_ROLL_STEP_T_CACHE.get(key)
    if cached is not None and cached.device == device and cached.dtype == ref.dtype:
        return cached
    t = torch.linspace(
        1.0 / float(steps),
        1.0,
        int(steps),
        dtype=ref.dtype,
        device=device,
    ).reshape(int(steps), 1, 1)
    _FOOT_ROLL_STEP_T_CACHE[key] = t
    return t


def _row_rotation_slerp_steps(
    from_rot: torch.Tensor,
    to_rot: torch.Tensor,
    steps: int,
    step_t: torch.Tensor | None = None,
) -> torch.Tensor:
    b = int(from_rot.shape[0])
    rotvec = _row_rotation_vector_between(from_rot, to_rot)
    t = step_t if step_t is not None else _foot_roll_step_t_like(from_rot, steps)
    delta = _row_rotation_from_vector((rotvec.unsqueeze(0) * t).reshape(-1, 3))
    base = from_rot.unsqueeze(0).expand(steps, b, 3, 3).reshape(-1, 3, 3)
    return (delta @ base).reshape(steps, b, 3, 3)


def _foot_toe_box_axes(
    store: SimpleClipStore,
    limb_i: int,
    foot_pos: torch.Tensor,
    foot_rot: torch.Tensor,
    toe_float: torch.Tensor,
    up_axis: int | None = None,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    b = int(foot_pos.shape[0])
    dtype = foot_pos.dtype
    toe_offset = _store_indexed_vector_for_batch(
        store.ik_toe_offsets.to(device=foot_pos.device, dtype=dtype),
        limb_i,
        b,
        "ik_toe_offsets",
    )
    toe_pos = foot_pos + _row_matvec(toe_offset, foot_rot)

    foot_up = foot_rot[:, 0]
    foot_forward = foot_rot[:, 1]
    foot_side = foot_rot[:, 2]
    toe_vec = toe_pos - foot_pos
    foot_forward = torch.where(
        (foot_forward * toe_vec).sum(dim=-1, keepdim=True) < 0.0,
        -foot_forward,
        foot_forward,
    )
    vertical_axis = int(FOOT_ROLL_UP_AXIS if up_axis is None else up_axis)
    foot_up = torch.where(foot_up[:, vertical_axis : vertical_axis + 1] < 0.0, -foot_up, foot_up)
    foot_center = toe_pos - foot_forward * (FOOT_ROLL_FOOT_DIMS_M[0] * 0.5) + foot_up * FOOT_ROLL_SOLE_VERTICAL_OFFSET_M

    toe_axis = _store_indexed_vector_for_batch(
        store.ik_toe_axis.to(device=foot_pos.device, dtype=dtype),
        limb_i,
        b,
        "ik_toe_axis",
    )
    toe_hinge = tl.axis_angle_to_row_matrix(toe_axis, toe_float.squeeze(-1).clamp(-1.0, 1.0) * tl.IK_TOE_ALPHA)
    toe_rot = toe_hinge @ foot_rot
    toe_forward = toe_rot[:, 0]
    toe_up = toe_rot[:, 1]
    toe_side = toe_rot[:, 2]
    toe_forward = torch.where(
        (toe_forward * toe_vec).sum(dim=-1, keepdim=True) < 0.0,
        -toe_forward,
        toe_forward,
    )
    toe_up = torch.where(toe_up[:, vertical_axis : vertical_axis + 1] < 0.0, -toe_up, toe_up)
    toe_center = toe_pos + toe_forward * (FOOT_ROLL_TOE_DIMS_M[0] * 0.5) + toe_up * FOOT_ROLL_SOLE_VERTICAL_OFFSET_M
    return foot_center, foot_forward, foot_side, foot_up, toe_center, toe_forward, toe_side, toe_up


def _foot_contact_fields_full(
    store: SimpleClipStore,
    limb_i: int,
    foot_rot: torch.Tensor,
    toe_float: torch.Tensor,
) -> tuple[torch.Tensor, ...]:
    side_blend_rad = math.radians(float(getattr(store.cfg, "foot_roll_side_blend_deg", 8.0)))
    zero_pos = foot_rot.new_zeros((foot_rot.shape[0], 3))
    foot_center, foot_forward, foot_side, foot_up, toe_center, toe_forward, toe_side, toe_up = _foot_toe_box_axes(
        store,
        limb_i,
        zero_pos,
        foot_rot,
        toe_float,
    )
    foot_point, foot_support = _box_contact_from_axes(
        foot_center,
        foot_forward,
        foot_side,
        foot_up,
        store.foot_roll_foot_half_dims,
        side_blend_rad,
    )
    toe_point, toe_support = _box_contact_from_axes(
        toe_center,
        toe_forward,
        toe_side,
        toe_up,
        store.foot_roll_toe_half_dims,
        side_blend_rad,
    )
    return (
        foot_point,
        foot_support,
        foot_center,
        foot_forward,
        foot_side,
        foot_up,
        toe_point,
        toe_support,
        toe_center,
        toe_forward,
        toe_side,
        toe_up,
    )


def _foot_roll_integrated_delta(
    store: SimpleClipStore,
    limb_i: int,
    cur_rot: torch.Tensor,
    cur_toe: torch.Tensor,
    pred_rot: torch.Tensor,
    pred_toe: torch.Tensor,
    integration_steps: int | None = None,
) -> torch.Tensor:
    steps = int(FOOT_ROLL_INTEGRATION_STEPS if integration_steps is None else integration_steps)
    t = _foot_roll_step_t_like(cur_rot, steps)
    step_rot = _row_rotation_slerp_steps(cur_rot, pred_rot, steps, t)
    step_toe = cur_toe.unsqueeze(0) + (pred_toe - cur_toe).unsqueeze(0) * t
    all_rot = torch.cat((cur_rot.unsqueeze(0), step_rot), dim=0)
    all_toe = torch.cat((cur_toe.unsqueeze(0), step_toe), dim=0)

    s, b = steps, int(cur_rot.shape[0])
    prev_rot = all_rot[:-1].reshape(s * b, 3, 3)
    next_rot = all_rot[1:].reshape(s * b, 3, 3)
    prev_toe = all_toe[:-1].reshape(s * b, 1)
    next_toe = all_toe[1:].reshape(s * b, 1)

    (
        next_foot_point,
        next_foot_support,
        _next_foot_center,
        _next_foot_forward,
        _next_foot_side,
        _next_foot_up,
        next_toe_point,
        next_toe_support,
        _next_toe_center,
        _next_toe_forward,
        _next_toe_side,
        _next_toe_up,
    ) = _foot_contact_fields_full(store, limb_i, next_rot, next_toe)
    (
        _prev_foot_point,
        _prev_foot_support,
        prev_foot_center,
        prev_foot_forward,
        prev_foot_side,
        prev_foot_up,
        _prev_toe_point,
        _prev_toe_support,
        prev_toe_center,
        prev_toe_forward,
        prev_toe_side,
        prev_toe_up,
    ) = _foot_contact_fields_full(store, limb_i, prev_rot, prev_toe)

    prev_foot_point = _box_point_from_support(
        prev_foot_center,
        prev_foot_forward,
        prev_foot_side,
        prev_foot_up,
        next_foot_support,
    )
    prev_toe_point = _box_point_from_support(
        prev_toe_center,
        prev_toe_forward,
        prev_toe_side,
        prev_toe_up,
        next_toe_support,
    )
    use_toe = next_toe_point[:, FOOT_ROLL_UP_AXIS] < next_foot_point[:, FOOT_ROLL_UP_AXIS]
    delta = torch.where(
        use_toe[:, None],
        prev_toe_point - next_toe_point,
        prev_foot_point - next_foot_point,
    )
    return delta.reshape(s, b, 3).sum(dim=0)


def _foot_contact_points(
    store: SimpleClipStore,
    limb_i: int,
    foot_pos: torch.Tensor,
    foot_rot: torch.Tensor,
    toe_float: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    side_blend_rad = math.radians(float(getattr(store.cfg, "foot_roll_side_blend_deg", 8.0)))
    foot_center, foot_forward, foot_side, foot_up, toe_center, toe_forward, toe_side, toe_up = _foot_toe_box_axes(
        store,
        limb_i,
        foot_pos,
        foot_rot,
        toe_float,
    )
    foot_point, foot_support = _box_contact_from_axes(
        foot_center,
        foot_forward,
        foot_side,
        foot_up,
        store.foot_roll_foot_half_dims,
        side_blend_rad,
    )
    toe_point, toe_support = _box_contact_from_axes(
        toe_center,
        toe_forward,
        toe_side,
        toe_up,
        store.foot_roll_toe_half_dims,
        side_blend_rad,
    )
    use_toe = toe_point[:, FOOT_ROLL_UP_AXIS] < foot_point[:, FOOT_ROLL_UP_AXIS]
    contact = torch.where(use_toe[:, None], toe_point, foot_point)
    return contact, use_toe, foot_support, toe_support, foot_point


def _foot_point_with_prior_support(
    store: SimpleClipStore,
    limb_i: int,
    foot_pos: torch.Tensor,
    foot_rot: torch.Tensor,
    toe_float: torch.Tensor,
    use_toe: torch.Tensor,
    foot_support: torch.Tensor,
    toe_support: torch.Tensor,
) -> torch.Tensor:
    foot_center, foot_forward, foot_side, foot_up, toe_center, toe_forward, toe_side, toe_up = _foot_toe_box_axes(
        store,
        limb_i,
        foot_pos,
        foot_rot,
        toe_float,
    )
    foot_point = _box_point_from_support(foot_center, foot_forward, foot_side, foot_up, foot_support)
    toe_point = _box_point_from_support(toe_center, toe_forward, toe_side, toe_up, toe_support)
    return torch.where(use_toe[:, None], toe_point, foot_point)


def _foot_lowest_y(
    store: SimpleClipStore,
    limb_i: int,
    foot_pos: torch.Tensor,
    foot_rot: torch.Tensor,
    toe_float: torch.Tensor,
) -> torch.Tensor:
    contact, _use_toe, _foot_support, _toe_support, _foot_point = _foot_contact_points(
        store,
        limb_i,
        foot_pos,
        foot_rot,
        toe_float,
    )
    return contact[:, FOOT_ROLL_UP_AXIS]


def _vertical_lift_like(ref: torch.Tensor, lift: torch.Tensor) -> torch.Tensor:
    components = []
    for axis in range(3):
        components.append(lift if axis == FOOT_ROLL_UP_AXIS else torch.zeros_like(lift))
    return torch.stack(components, dim=-1).to(dtype=ref.dtype)


def _foot_height_pin_gate(height_m: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    high = max(float(FOOT_CONTACT_MIN_HEIGHT_LOSS_FULL_M), float(FOOT_HEIGHT_PIN_THRESHOLD_M) + 1e-12)
    gate = torch.clamp((high - height_m) / (high - float(FOOT_HEIGHT_PIN_THRESHOLD_M)), 0.0, 1.0)
    pinned = height_m <= float(FOOT_HEIGHT_PIN_THRESHOLD_M)
    return gate, pinned


def foot_pin_mask_from_cleaned_heights(heights_m: torch.Tensor) -> torch.Tensor:
    if int(heights_m.shape[-1]) < int(tl.FOOT_ROLL_PIN_OUTPUT_DIM):
        return torch.zeros(
            (*heights_m.shape[:-1], int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)),
            dtype=torch.bool,
            device=heights_m.device,
        )
    return heights_m[..., : int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)] <= float(FOOT_HEIGHT_PIN_THRESHOLD_M)


def foot_pin_mask_from_heights_and_logits(heights_m: torch.Tensor, pin_logits: torch.Tensor) -> torch.Tensor:
    logit_contact = foot_pin_mask_from_logits(pin_logits)
    if not bool(FOOT_ROLL_HEIGHT_PIN_GATE):
        return logit_contact
    height_contact = foot_pin_mask_from_cleaned_heights(heights_m)
    return height_contact & logit_contact


def soft_any_foot_unpin_rows(pin_logits: torch.Tensor) -> torch.Tensor:
    if int(pin_logits.shape[-1]) < int(tl.FOOT_ROLL_PIN_OUTPUT_DIM):
        return torch.zeros((*pin_logits.shape[:-1],), dtype=pin_logits.dtype, device=pin_logits.device)
    logits = pin_logits[..., : int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)]
    soft_both_pinned = torch.sigmoid(-logits[..., 0] * float(FOOT_ROLL_PIN_STE_SCALE)) * torch.sigmoid(
        -logits[..., 1] * float(FOOT_ROLL_PIN_STE_SCALE)
    )
    return 1.0 - soft_both_pinned


def soft_foot_pin_weights(pin_logits: torch.Tensor) -> torch.Tensor:
    if int(pin_logits.shape[-1]) < int(tl.FOOT_ROLL_PIN_OUTPUT_DIM):
        return torch.zeros(
            (*pin_logits.shape[:-1], int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)),
            dtype=pin_logits.dtype,
            device=pin_logits.device,
        )
    logits = pin_logits[..., : int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)]
    left_pin = logits[..., 0]
    right_pin = logits[..., 1]
    soft_both = torch.sigmoid(-left_pin * float(FOOT_ROLL_PIN_STE_SCALE)) * torch.sigmoid(
        -right_pin * float(FOOT_ROLL_PIN_STE_SCALE)
    )
    single_soft = torch.softmax(-logits * float(FOOT_ROLL_PIN_STE_SCALE), dim=-1)
    left_soft = soft_both + (1.0 - soft_both) * single_soft[..., 0]
    right_soft = soft_both + (1.0 - soft_both) * single_soft[..., 1]
    return torch.stack((left_soft, right_soft), dim=-1)


def legacy_logit_selected_foot_pin_probabilities(pin_logits: torch.Tensor) -> torch.Tensor:
    pin_dim = int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)
    if int(pin_logits.shape[-1]) < pin_dim:
        return torch.zeros(
            (*pin_logits.shape[:-1], pin_dim),
            dtype=pin_logits.dtype,
            device=pin_logits.device,
        )
    logits = pin_logits[..., :pin_dim]
    left_pin = logits[..., 0]
    right_pin = logits[..., 1]
    both_pinned = (left_pin < 0.0) & (right_pin < 0.0)
    left_pinned = both_pinned | ((left_pin <= right_pin) & (~both_pinned))
    right_pinned = both_pinned | ((right_pin < left_pin) & (~both_pinned))

    # Preserve the historical hard forward result while retaining the smooth
    # surrogate gradient that the walk controller was trained with.
    soft_pins = soft_foot_pin_weights(pin_logits)
    left_gate = left_pinned.to(dtype=pin_logits.dtype) + soft_pins[..., 0] - soft_pins[..., 0].detach()
    right_gate = right_pinned.to(dtype=pin_logits.dtype) + soft_pins[..., 1] - soft_pins[..., 1].detach()
    return torch.stack((left_gate, right_gate), dim=-1)


def soft_foot_pin_probabilities(pin_logits: torch.Tensor) -> torch.Tensor:
    if int(pin_logits.shape[-1]) < int(tl.FOOT_ROLL_PIN_OUTPUT_DIM):
        return torch.zeros(
            (*pin_logits.shape[:-1], int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)),
            dtype=pin_logits.dtype,
            device=pin_logits.device,
        )
    logits = pin_logits[..., : int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)]
    return torch.sigmoid(-logits * float(FOOT_ROLL_PIN_STE_SCALE))


def near_floor_forced_pin_probabilities(
    store: SimpleClipStore,
    pred_vec: torch.Tensor,
    pin_logits: torch.Tensor,
) -> torch.Tensor:
    pin_dim = int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)
    pin_prob = soft_foot_pin_probabilities(pin_logits).to(dtype=pred_vec.dtype)
    if int(pin_logits.shape[-1]) < pin_dim:
        return pin_prob
    heights = foot_roll_lowest_heights_from_vec(store, pred_vec)[..., :pin_dim].to(dtype=pin_prob.dtype)
    logits = pin_logits[..., :pin_dim]
    lowest_logit_idx = torch.argmin(logits, dim=-1)
    lowest_height_idx = torch.argmin(heights, dim=-1)
    below_fade_height = heights < float(FOOT_ROLL_NEAR_FLOOR_PIN_FADE_HEIGHT_M)
    any_below_fade_height = below_fade_height.any(dim=-1)
    both_below_fade_height = below_fade_height.all(dim=-1)
    selected_idx = torch.where(both_below_fade_height, lowest_logit_idx, lowest_height_idx)
    selected = F.one_hot(selected_idx, num_classes=pin_dim).to(dtype=pin_prob.dtype, device=pin_prob.device)
    selected_height = (heights * selected).sum(dim=-1, keepdim=True)
    fade_span = max(
        1.0e-6,
        float(FOOT_ROLL_NEAR_FLOOR_PIN_FADE_HEIGHT_M) - float(FOOT_ROLL_NEAR_FLOOR_PIN_FULL_HEIGHT_M),
    )
    force_alpha = torch.clamp(
        (float(FOOT_ROLL_NEAR_FLOOR_PIN_FADE_HEIGHT_M) - selected_height) / fade_span,
        0.0,
        1.0,
    )
    pin_floor = float(FOOT_ROLL_NEAR_FLOOR_PIN_MIN_PROB) * force_alpha
    pin_floor = pin_floor * any_below_fade_height.to(dtype=pin_prob.dtype).unsqueeze(-1)
    forced_selected = torch.maximum(pin_prob, pin_floor.to(dtype=pin_prob.dtype))
    return torch.where(selected.bool(), forced_selected, pin_prob).clamp(0.0, 1.0)


def fake_gravity_pin_probabilities(
    store: SimpleClipStore,
    pred_vec: torch.Tensor,
    pin_logits: torch.Tensor,
) -> torch.Tensor:
    pin_prob = near_floor_forced_pin_probabilities(store, pred_vec, pin_logits).to(dtype=pred_vec.dtype)
    if bool(FAKE_GRAVITY_USES_HEIGHT_GATE):
        heights = foot_roll_lowest_heights_from_vec(store, pred_vec)
        height_gate = _foot_height_pin_gate(heights)[0].to(dtype=pin_prob.dtype)
        pin_prob = pin_prob * height_gate[..., : int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)]
    return pin_prob.clamp(0.0, 1.0)


def post_gate_foot_pin_probabilities(
    store: SimpleClipStore,
    pred_vec: torch.Tensor,
    pin_logits: torch.Tensor,
    heights_m: torch.Tensor | None = None,
) -> torch.Tensor:
    pin_dim = int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)
    if int(pin_logits.shape[-1]) < pin_dim:
        return torch.zeros((*pin_logits.shape[:-1], pin_dim), dtype=pin_logits.dtype, device=pin_logits.device)
    pin_prob = soft_foot_pin_probabilities(pin_logits).to(dtype=pred_vec.dtype)
    if bool(FOOT_ROLL_HEIGHT_PIN_GATE):
        heights = heights_m if heights_m is not None else foot_roll_lowest_heights_from_vec(store, pred_vec)
        height_gate = _foot_height_pin_gate(heights)[0].to(dtype=pin_prob.dtype)
        pin_prob = pin_prob * height_gate[..., :pin_dim]
    return pin_prob.clamp(0.0, 1.0)


def ae3_foot_only_height_gradient_vector(store: SimpleClipStore, pred_vec: torch.Tensor) -> torch.Tensor:
    """Detach non-foot channels for AE3's height gate gradient path."""
    if int(store.ik_payload_dim) == 0:
        return pred_vec.detach()
    scoped = pred_vec.detach().clone()
    payload_start = int(payload_slice(store).start)
    for limb_i in getattr(store, "ik_payload_leg_limb_indices", ()):
        spec = store.ik_payload_slices[int(limb_i)]
        pos_slice = spec["pos"]
        rot_slice = spec["rot6"]
        toe_slice = spec["toe_float"]
        assert isinstance(pos_slice, slice)
        assert isinstance(rot_slice, slice)
        vertical_idx = payload_start + int(pos_slice.start) + int(FOOT_ROLL_UP_AXIS)
        scoped[:, vertical_idx : vertical_idx + 1] = pred_vec[:, vertical_idx : vertical_idx + 1]
        rot_start = payload_start + int(rot_slice.start)
        rot_stop = payload_start + int(rot_slice.stop)
        scoped[:, rot_start:rot_stop] = pred_vec[:, rot_start:rot_stop]
        if toe_slice is not None:
            assert isinstance(toe_slice, slice)
            toe_start = payload_start + int(toe_slice.start)
            toe_stop = payload_start + int(toe_slice.stop)
            scoped[:, toe_start:toe_stop] = pred_vec[:, toe_start:toe_stop]
    return scoped


def ae3_expected_pin_height_push_rows(expected_prob: torch.Tensor, heights_m: torch.Tensor) -> torch.Tensor:
    pin_dim = int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)
    high = max(float(FOOT_CONTACT_MIN_HEIGHT_LOSS_FULL_M), float(FOOT_HEIGHT_PIN_THRESHOLD_M) + 1.0e-12)
    denom = high - float(FOOT_HEIGHT_PIN_THRESHOLD_M)
    linear = torch.relu((heights_m[..., :pin_dim] - float(FOOT_HEIGHT_PIN_THRESHOLD_M)) / denom)
    capped_forward = linear.clamp(max=1.0)
    excess = capped_forward.detach() + linear - linear.detach()
    return (expected_prob[..., :pin_dim] * excess).mean(dim=-1)


def ae3_post_gate_pin_probabilities(
    pin_logits: torch.Tensor,
    heights_m: torch.Tensor | None,
) -> torch.Tensor:
    pin_dim = int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)
    pin_prob = soft_foot_pin_probabilities(pin_logits)
    if not bool(FOOT_ROLL_HEIGHT_PIN_GATE) or heights_m is None:
        return pin_prob.clamp(0.0, 1.0)
    height_gate = _foot_height_pin_gate(heights_m)[0].to(dtype=pin_prob.dtype)[..., :pin_dim]
    return (pin_prob * height_gate).clamp(0.0, 1.0)


def ae3_bce_input(pin_meter: torch.Tensor) -> torch.Tensor:
    clamped = pin_meter.clamp(1.0e-4, 1.0 - 1.0e-4)
    return clamped.detach() + pin_meter - pin_meter.detach()


def ae3_logit_alignment_rows(expected_prob: torch.Tensor, pin_logits: torch.Tensor) -> torch.Tensor:
    pin_prob = soft_foot_pin_probabilities(pin_logits).to(dtype=expected_prob.dtype)
    loss = F.binary_cross_entropy(ae3_bce_input(pin_prob), expected_prob, reduction="none")
    return loss.mean(dim=-1)


def fake_gravity_delta_m(store: SimpleClipStore, prev_vec: torch.Tensor, cur_vec: torch.Tensor) -> torch.Tensor:
    dt = 1.0 / max(1.0, float(getattr(store.prototype, "fps", 30.0)))
    delta = cur_vec[:, :3] - prev_vec[:, :3]
    gravity = delta.new_zeros(delta.shape)
    gravity[:, int(FOOT_ROLL_UP_AXIS)] = -float(FAKE_GRAVITY_MPS2) * dt * dt
    return delta + gravity


def fake_gravity_only_delta_m(store: SimpleClipStore, ref_vec: torch.Tensor) -> torch.Tensor:
    delta = ref_vec[:, :3].new_zeros((ref_vec.shape[0], 3))
    dt = 1.0 / max(1.0, float(getattr(store.prototype, "fps", 30.0)))
    delta[:, int(FOOT_ROLL_UP_AXIS)] = -float(FAKE_GRAVITY_MPS2) * dt * dt
    return delta


def apply_fake_gravity_output(
    store: SimpleClipStore,
    pred_vec: torch.Tensor,
    prev_vec: torch.Tensor | None,
    cur_vec: torch.Tensor | None,
    pin_logits: torch.Tensor,
) -> torch.Tensor:
    if (
        float(FAKE_GRAVITY_ENABLED) <= 0.0
        or prev_vec is None
        or cur_vec is None
        or int(pin_logits.shape[-1]) < int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)
        or int(store.ik_payload_dim) == 0
    ):
        return pred_vec
    prev_clean = _clean_output_vector_base(prev_vec[:, : base_output_dim_for_store(store)], store)
    cur_clean = _clean_output_vector_base(cur_vec[:, : base_output_dim_for_store(store)], store)
    pin_prob = fake_gravity_pin_probabilities(store, pred_vec, pin_logits)
    pelvis_pin_meter = pin_prob.amax(dim=-1, keepdim=True).clamp(0.0, 1.0)
    fake_amount = 1.0 - pelvis_pin_meter
    fg_delta = fake_gravity_delta_m(store, prev_clean, cur_clean)
    foot_gravity_delta = fake_gravity_only_delta_m(store, cur_clean)
    fake_weight = float(FAKE_GRAVITY_ENABLED)
    model_delta = pred_vec[:, :3] - cur_clean[:, :3]
    out = pred_vec.clone()
    fake_pelvis = cur_clean[:, :3] + model_delta * pelvis_pin_meter + fg_delta * fake_amount
    out[:, :3] = (1.0 - fake_weight) * pred_vec[:, :3] + fake_weight * fake_pelvis

    if len(getattr(store, "ik_payload_leg_limb_indices", ())) < 2:
        return out
    payload = out[:, payload_slice(store)]
    cur_payload = cur_clean[:, payload_slice(store)]
    pos_parts, rot_parts, start_rot_parts, toe_parts = _parse_payload_parts(payload, store)
    cur_pos_parts, _cur_rot_parts, _cur_start_rot_parts, _cur_toe_parts = _parse_payload_parts(cur_payload, store)
    side_to_prob = {"l": pin_prob[:, 0:1], "r": pin_prob[:, 1:2]}
    adjusted_pos = list(pos_parts)
    for limb_i in store.ik_payload_leg_limb_indices:
        limb_i = int(limb_i)
        side = str(store.ik_payload_slices[limb_i].get("side", "")).lower().strip()
        if side not in side_to_prob:
            continue
        foot_unpin = 1.0 - side_to_prob[side].to(dtype=pred_vec.dtype)
        foot_model_delta = pos_parts[limb_i] - cur_pos_parts[limb_i]
        adjusted_pos[limb_i] = (
            cur_pos_parts[limb_i]
            + foot_model_delta
            + foot_unpin * foot_gravity_delta * fake_weight
        )
    adjusted_payload = _assemble_payload_parts(store, adjusted_pos, rot_parts, start_rot_parts, toe_parts)
    return torch.cat((out[:, : payload_slice(store).start], adjusted_payload), dim=-1)


def foot_contact_min_height_loss_rows(heights_m: torch.Tensor) -> torch.Tensor:
    min_height = heights_m[..., : int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)].amin(dim=-1)
    high = max(float(FOOT_CONTACT_MIN_HEIGHT_LOSS_FULL_M), float(FOOT_HEIGHT_PIN_THRESHOLD_M) + 1e-12)
    ramp = torch.clamp((min_height - float(FOOT_HEIGHT_PIN_THRESHOLD_M)) / (high - float(FOOT_HEIGHT_PIN_THRESHOLD_M)), 0.0, 1.0)
    return ramp * float(FOOT_CONTACT_MIN_HEIGHT_LOSS_MAX)


def calibrated_capped_excess_loss_rows(
    excess_rows: torch.Tensor,
    reference_excess_m: float,
    zero_fraction: float,
    reference_loss: float,
    cap: float,
) -> torch.Tensor:
    reference = max(float(reference_excess_m), 1.0e-9)
    deadzone = reference * max(0.0, float(zero_fraction))
    active = torch.relu(excess_rows - deadzone)
    active_at_reference = max(reference - deadzone, 1.0e-9)
    cap_f = max(float(cap), 1.0e-9)
    slope = max(0.0, float(reference_loss)) / active_at_reference
    linear = active * slope
    target_fraction = max(0.0, min(0.999999, float(reference_loss) / cap_f))
    tanh_arg_at_reference = math.atanh(target_fraction)
    capped_forward = cap_f * torch.tanh(active * (tanh_arg_at_reference / active_at_reference))
    return capped_forward.detach() + linear - linear.detach()


def forced_idle_clip_id(store: SimpleClipStore) -> int:
    cached = getattr(store, "_forced_idle_clip_id", None)
    if cached is not None:
        return int(cached)
    wanted_idle = str(getattr(store, "forced_idle_clip_stem", FORCED_IDLE_CLIP_STEM)).lower().strip()
    fallback = -1
    for idx, clip in enumerate(store.clips):
        stem = str(clip.path.stem).lower()
        if wanted_idle and stem == wanted_idle:
            setattr(store, "_forced_idle_clip_id", int(idx))
            return int(idx)
        if wanted_idle == FORCED_IDLE_CLIP_STEM and "stand_idle" in stem and fallback < 0:
            fallback = int(idx)
    setattr(store, "_forced_idle_clip_id", int(fallback))
    return int(fallback)


def forced_turn45_clip_ids(store: SimpleClipStore) -> tuple[int, ...]:
    cached = getattr(store, "_forced_turn45_clip_ids", None)
    if cached is not None:
        return tuple(int(v) for v in cached)
    wanted_stems = tuple(
        str(stem).lower().strip()
        for stem in getattr(store, "forced_turn45_clip_stems", FORCED_TURN45_CLIP_STEMS)
        if str(stem).strip()
    )
    if wanted_stems != tuple(FORCED_TURN45_CLIP_STEMS):
        wanted_set = set(wanted_stems)
        out = tuple(
            int(idx)
            for idx, clip in enumerate(store.clips)
            if str(clip.path.stem).lower() in wanted_set
        )
        setattr(store, "_forced_turn45_clip_ids", out)
        return out
    found: dict[str, int] = {}
    fallback: dict[str, int] = {}
    for idx, clip in enumerate(store.clips):
        stem = str(clip.path.stem).lower()
        for wanted in wanted_stems:
            side = "l" if wanted.endswith("_l") else "r"
            if stem == wanted:
                found[side] = int(idx)
            elif side not in fallback and "stand_turn_045" in stem and stem.endswith(f"_{side}"):
                fallback[side] = int(idx)
    left = found.get("l", fallback.get("l", -1))
    right = found.get("r", fallback.get("r", -1))
    out = (int(left), int(right))
    setattr(store, "_forced_turn45_clip_ids", out)
    return out


def forced_idle_row_enabled(idle_foot_flatness_weight: float) -> bool:
    return float(idle_foot_flatness_weight) != 0.0


def forced_idle_rows_enabled(idle_foot_flatness_weight: float, fraction: float | None) -> bool:
    return forced_idle_row_enabled(idle_foot_flatness_weight) or (
        fraction is not None and float(fraction) > 0.0
    )


def forced_turn45_rows_enabled(fraction: float | None) -> bool:
    return fraction is not None and float(fraction) > 0.0


def forced_tail_noisy_row_count(
    batch_size: int,
    force_idle_row: bool,
    forced_idle_batch_fraction: float | None,
    force_turn45_row: bool,
    forced_turn45_batch_fraction: float | None,
) -> int:
    count = 0
    if force_idle_row:
        count += forced_idle_batch_row_count(batch_size, forced_idle_batch_fraction)
    if force_turn45_row:
        count += forced_turn45_batch_row_count(batch_size, forced_turn45_batch_fraction)
    return max(0, min(max(0, int(batch_size)), int(count)))


def apply_forced_turn45_training_row_(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    starts: torch.Tensor,
    ae_frames: int,
    fraction: float | None,
    reserved_tail_rows: int = 0,
    row_limit: int | None = None,
) -> None:
    if int(clip_ids.numel()) <= 0:
        return
    valid = [int(v) for v in forced_turn45_clip_ids(store) if int(v) >= 0]
    if not valid:
        return
    batch_size = int(clip_ids.numel()) if row_limit is None else max(0, min(int(clip_ids.numel()), int(row_limit)))
    count = forced_turn45_batch_row_count(batch_size, fraction)
    reserved_tail_rows = max(0, min(batch_size, int(reserved_tail_rows)))
    count = max(0, min(count, batch_size - reserved_tail_rows))
    if count <= 0:
        return
    row_start = batch_size - reserved_tail_rows - count
    rows = torch.arange(row_start, row_start + count, device=clip_ids.device)
    choices = torch.tensor(valid, dtype=clip_ids.dtype, device=clip_ids.device)
    picked = choices.index_select(0, torch.randint(0, int(choices.numel()), (count,), device=clip_ids.device))
    base_start = torch.full((count,), max(1, int(ae_frames)), dtype=starts.dtype, device=starts.device)
    max_starts = store.max_training_starts.index_select(0, picked.to(device=store.device, dtype=torch.long))
    max_starts = max_starts.to(device=starts.device, dtype=starts.dtype).clamp_min(1)
    clip_ids.index_copy_(0, rows, picked)
    starts.index_copy_(0, rows, torch.minimum(base_start, max_starts))


def apply_forced_idle_training_row_(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    starts: torch.Tensor,
    ae_frames: int,
    fraction: float | None = None,
    row_limit: int | None = None,
) -> None:
    if int(clip_ids.numel()) <= 0:
        return
    idle_id = forced_idle_clip_id(store)
    if idle_id < 0:
        return
    batch_size = int(clip_ids.numel()) if row_limit is None else max(0, min(int(clip_ids.numel()), int(row_limit)))
    count = forced_idle_batch_row_count(batch_size, fraction)
    if count <= 0:
        return
    start = torch.full((), max(1, int(ae_frames)), dtype=starts.dtype, device=starts.device)
    max_start = store.max_training_starts[int(idle_id)].to(device=starts.device, dtype=starts.dtype).clamp_min(1)
    rows = torch.arange(batch_size - count, batch_size, device=clip_ids.device)
    clip_ids.index_fill_(0, rows, int(idle_id))
    starts.index_copy_(0, rows, torch.minimum(start, max_start).expand(count))


def idle_clip_mask_for_rows(store: SimpleClipStore, clip_ids: torch.Tensor) -> torch.Tensor:
    idle_id = forced_idle_clip_id(store)
    if idle_id < 0:
        return torch.zeros_like(clip_ids, dtype=torch.bool)
    return clip_ids == int(idle_id)


def foot_roll_box_flatness_from_vec(
    store: SimpleClipStore,
    vec: torch.Tensor,
) -> torch.Tensor:
    b = int(vec.shape[0])
    pin_dim = int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)
    if int(store.ik_payload_dim) == 0 or len(getattr(store, "ik_payload_leg_limb_indices", ())) < 2:
        return vec.new_zeros((b, pin_dim))
    payload = vec[:, payload_slice(store)]
    pos_parts, rot_parts, _start_rot_parts, toe_parts = _parse_payload_parts(payload, store)
    by_side: dict[str, int] = {}
    for limb_i in store.ik_payload_leg_limb_indices:
        side = str(store.ik_payload_slices[int(limb_i)].get("side", "")).lower().strip()
        if side:
            by_side[side] = int(limb_i)
    foot_half = store.foot_roll_foot_half_dims.to(dtype=vec.dtype)
    toe_half = store.foot_roll_toe_half_dims.to(dtype=vec.dtype)
    flatness: list[torch.Tensor] = []
    for side in ("l", "r"):
        limb_i = by_side.get(side)
        if limb_i is None or toe_parts[limb_i] is None:
            flatness.append(vec.new_zeros((b,)))
            continue
        rot = tl.rotation_6d_to_matrix(rot_parts[limb_i])
        up_axis = int(FOOT_ROLL_UP_AXIS)
        (
            foot_center,
            foot_forward,
            foot_side,
            foot_up,
            toe_center,
            toe_forward,
            toe_side,
            toe_up,
        ) = _foot_toe_box_axes(store, limb_i, pos_parts[limb_i], rot, toe_parts[limb_i], up_axis=up_axis)
        foot_spread = (
            foot_forward[:, up_axis].abs() * foot_half[0] + foot_side[:, up_axis].abs() * foot_half[1]
        ) * 2.0
        toe_spread = (
            toe_forward[:, up_axis].abs() * toe_half[0] + toe_side[:, up_axis].abs() * toe_half[1]
        ) * 2.0
        flatness.append(torch.maximum(foot_spread, toe_spread))
    return torch.stack(flatness, dim=-1)


def pinned_foot_height_loss_rows(
    heights: torch.Tensor,
    pin_logits: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    pin_weights = soft_foot_pin_weights(pin_logits).to(dtype=heights.dtype)
    denom = pin_weights.sum(dim=-1).clamp_min(1.0e-6)
    excess_rows = (heights * pin_weights).sum(dim=-1) / denom
    loss_rows = calibrated_capped_excess_loss_rows(
        excess_rows,
        PINNED_FOOT_HEIGHT_REFERENCE_EXCESS_M,
        PINNED_FOOT_HEIGHT_ZERO_FRACTION,
        PINNED_FOOT_HEIGHT_REFERENCE_LOSS,
        PINNED_FOOT_HEIGHT_LOSS_CAP,
    )
    return loss_rows, excess_rows


def pinned_foot_height_max_m_rows(
    heights: torch.Tensor,
    pin_logits: torch.Tensor,
) -> torch.Tensor:
    pin_dim = int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)
    if int(heights.shape[-1]) < pin_dim or int(pin_logits.shape[-1]) < pin_dim:
        return torch.zeros((*heights.shape[:-1],), dtype=heights.dtype, device=heights.device)
    pin_mask = foot_pin_mask_from_logits(pin_logits).to(dtype=heights.dtype)
    return (heights[..., :pin_dim] * pin_mask).amax(dim=-1)


def idle_foot_flatness_loss_rows(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    vec: torch.Tensor,
    pin_logits: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    flatness = foot_roll_box_flatness_from_vec(store, vec)
    pin_mask = foot_pin_mask_from_logits(pin_logits).to(dtype=flatness.dtype)
    idle_rows = idle_clip_mask_for_rows(store, clip_ids).to(dtype=flatness.dtype)
    excess_rows = (flatness * pin_mask).amax(dim=-1) * idle_rows
    loss_rows = calibrated_capped_excess_loss_rows(
        excess_rows,
        IDLE_FOOT_FLATNESS_REFERENCE_EXCESS_M,
        IDLE_FOOT_FLATNESS_ZERO_FRACTION,
        IDLE_FOOT_FLATNESS_REFERENCE_LOSS,
        IDLE_FOOT_FLATNESS_LOSS_CAP,
    ) * idle_rows
    return loss_rows, excess_rows


def idle_foot_flatness_batch_scale(batch_size: int) -> float:
    return 0.5 * float(max(1, int(batch_size)))


def pinned_foot_intent_motion_rows(
    store: SimpleClipStore,
    cur_root_pos: torch.Tensor,
    cur_root_rot: torch.Tensor,
    output_root_pos: torch.Tensor,
    output_root_rot: torch.Tensor,
    cur_vec: torch.Tensor,
    raw_clean_vec: torch.Tensor,
    pin_logits: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    if (
        int(store.ik_payload_dim) == 0
        or int(pin_logits.shape[-1]) < int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)
        or len(getattr(store, "ik_payload_leg_limb_indices", ())) < 2
    ):
        zeros = torch.zeros((int(cur_vec.shape[0]),), dtype=cur_vec.dtype, device=cur_vec.device)
        return zeros, zeros
    cur_foot_pos, _cur_foot_rot = env.ik_foot_toe_state_from_vec(store, cur_root_pos, cur_root_rot, cur_vec)
    raw_foot_pos, _raw_foot_rot = env.ik_foot_toe_state_from_vec(
        store, output_root_pos, output_root_rot, raw_clean_vec
    )
    foot_speeds = env.compact_foot_slide_speeds(cur_foot_pos, raw_foot_pos, store.prototype.fps)
    pin_weights = soft_foot_pin_weights(pin_logits).to(dtype=foot_speeds.dtype)
    denom = pin_weights.sum(dim=-1).clamp_min(1e-6)
    mps2_rows = (foot_speeds.square() * pin_weights).sum(dim=-1) / denom
    mps_rows = (foot_speeds.detach() * pin_weights.detach()).sum(dim=-1) / denom.detach()
    return mps2_rows, mps_rows


def slide_tentative_projection_correction_rows(
    store: SimpleClipStore,
    raw_clean_vec: torch.Tensor,
    projected_vec: torch.Tensor,
    final_pin_mask: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    if (
        int(store.ik_payload_dim) == 0
        or int(final_pin_mask.shape[-1]) < int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)
        or len(getattr(store, "ik_payload_leg_limb_indices", ())) < 2
    ):
        zeros = torch.zeros((int(raw_clean_vec.shape[0]),), dtype=raw_clean_vec.dtype, device=raw_clean_vec.device)
        return zeros, zeros
    raw_payload = raw_clean_vec[:, payload_slice(store)]
    projected_payload = projected_vec[:, payload_slice(store)].detach()
    left_pos_slice: slice | None = None
    right_pos_slice: slice | None = None
    for limb_i in store.ik_payload_leg_limb_indices:
        spec = store.ik_payload_slices[int(limb_i)]
        side = str(spec.get("side", "")).lower().strip()
        pos_slice = spec["pos"]
        if side not in ("l", "r") or not isinstance(pos_slice, slice):
            continue
        if side == "l":
            left_pos_slice = pos_slice
        else:
            right_pos_slice = pos_slice
    if left_pos_slice is None or right_pos_slice is None:
        zeros = torch.zeros((int(raw_clean_vec.shape[0]),), dtype=raw_clean_vec.dtype, device=raw_clean_vec.device)
        return zeros, zeros

    def horizontal_l1(pos_slice: slice) -> torch.Tensor:
        delta = raw_payload[:, pos_slice] - projected_payload[:, pos_slice]
        up_axis = int(FOOT_ROLL_UP_AXIS)
        if up_axis == 0:
            horizontal = delta[:, 1:3]
        elif up_axis == 1:
            horizontal = delta[:, (0, 2)]
        else:
            horizontal = delta[:, 0:2]
        return horizontal.abs().sum(dim=-1)

    left = horizontal_l1(left_pos_slice)
    right = horizontal_l1(right_pos_slice)
    pin = final_pin_mask[..., : int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)].to(dtype=left.dtype).detach()
    left_pin = pin[:, 0]
    right_pin = pin[:, 1]
    denom = (left_pin + right_pin).clamp_min(1.0)
    rows = (left * left_pin + right * right_pin) / denom
    pin_rate_rows = ((left_pin + right_pin) > 0.0).to(dtype=left.dtype)
    return rows, pin_rate_rows


def ae_output_mse_mask(
    store: SimpleClipStore | None,
    output_dim: int,
    dtype: torch.dtype,
    device: torch.device,
) -> torch.Tensor:
    cache_key = (
        int(output_dim),
        str(dtype),
        str(device),
        float(AE_FOOT_LOCATION_MULTIPLIER),
        float(AE_FOOT_ROTATION_MULTIPLIER),
    )
    cached = getattr(store, "_ae_output_mse_mask", None) if store is not None else None
    cached_key = getattr(store, "_ae_output_mse_mask_key", None) if store is not None else None
    if (
        torch.is_tensor(cached)
        and cached_key == cache_key
        and int(cached.numel()) == int(output_dim)
        and cached.device == device
        and cached.dtype == dtype
    ):
        return cached
    mask = torch.ones((int(output_dim),), dtype=dtype, device=device)
    if store is not None and (
        float(AE_FOOT_LOCATION_MULTIPLIER) != 1.0
        or float(AE_FOOT_ROTATION_MULTIPLIER) != 1.0
    ):
        payload_start = payload_slice(store).start
        for spec in store.ik_payload_slices:
            if str(spec.get("kind", "")).lower().strip() != "leg":
                continue
            pos_slice = spec["pos"]
            rot_slice = spec["rot6"]
            assert isinstance(pos_slice, slice)
            assert isinstance(rot_slice, slice)
            pos_start = int(payload_start) + int(pos_slice.start)
            pos_stop = int(payload_start) + int(pos_slice.stop)
            if 0 <= pos_start < pos_stop <= int(output_dim):
                mask[pos_start:pos_stop] = float(AE_FOOT_LOCATION_MULTIPLIER)
            rot_start = int(payload_start) + int(rot_slice.start)
            rot_stop = int(payload_start) + int(rot_slice.stop)
            if 0 <= rot_start < rot_stop <= int(output_dim):
                mask[rot_start:rot_stop] = float(AE_FOOT_ROTATION_MULTIPLIER)
    if store is not None:
        store._ae_output_mse_mask = mask
        store._ae_output_mse_mask_key = cache_key
    return mask


def prepare_ae_output_mse_mask(store: SimpleClipStore, output_dim: int, dtype: torch.dtype = torch.float32) -> None:
    mask = ae_output_mse_mask(store, output_dim, dtype, store.device)
    store._ae_output_mse_mask = mask


def _parse_payload_parts(
    payload: torch.Tensor,
    store: SimpleClipStore,
) -> tuple[list[torch.Tensor], list[torch.Tensor], list[torch.Tensor], list[torch.Tensor | None]]:
    pos_parts: list[torch.Tensor] = []
    rot_parts: list[torch.Tensor] = []
    start_rot_parts: list[torch.Tensor] = []
    toe_parts: list[torch.Tensor | None] = []
    for spec in store.ik_payload_slices:
        pos_slice = spec["pos"]
        rot_slice = spec["rot6"]
        start_rot_slice = spec["start_rot6"]
        toe_slice = spec["toe_float"]
        assert isinstance(pos_slice, slice)
        assert isinstance(rot_slice, slice)
        assert isinstance(start_rot_slice, slice)
        pos_parts.append(payload[:, pos_slice])
        rot_parts.append(payload[:, rot_slice])
        start_rot_parts.append(payload[:, start_rot_slice])
        if toe_slice is not None:
            assert isinstance(toe_slice, slice)
            toe_parts.append(payload[:, toe_slice])
        else:
            toe_parts.append(None)
    return pos_parts, rot_parts, start_rot_parts, toe_parts


def _assemble_payload_parts(
    store: SimpleClipStore,
    pos_parts: list[torch.Tensor],
    rot_parts: list[torch.Tensor],
    start_rot_parts: list[torch.Tensor],
    toe_parts: list[torch.Tensor | None],
) -> torch.Tensor:
    parts: list[torch.Tensor] = []
    for limb_i, toe in enumerate(toe_parts):
        parts.append(pos_parts[limb_i])
        parts.append(rot_parts[limb_i])
        parts.append(start_rot_parts[limb_i])
        if toe is not None:
            parts.append(toe)
    return torch.cat(parts, dim=-1) if parts else pos_parts[0].new_empty((pos_parts[0].shape[0], 0))


def lift_feet_above_ground(store: SimpleClipStore, vec: torch.Tensor) -> torch.Tensor:
    if int(store.ik_payload_dim) == 0 or len(getattr(store, "ik_payload_leg_limb_indices", ())) < 2:
        return vec
    base_dim = base_output_dim_for_store(store)
    if int(vec.shape[-1]) < int(base_dim):
        return vec
    payload_vec_slice = payload_slice(store)
    payload = vec[:, payload_vec_slice]
    pos_parts, rot_parts, start_rot_parts, toe_parts = _parse_payload_parts(payload, store)
    lifted_pos = list(pos_parts)
    ground = store.foot_roll_ground_y_tensor.to(dtype=vec.dtype, device=vec.device)
    for limb_i in store.ik_payload_leg_limb_indices:
        limb_i = int(limb_i)
        toe = toe_parts[limb_i]
        if toe is None:
            continue
        rot = tl.rotation_6d_to_matrix(rot_parts[limb_i])
        lowest_y = _foot_lowest_y(store, limb_i, lifted_pos[limb_i], rot, toe)
        lift = torch.relu(ground - lowest_y)
        lifted_pos[limb_i] = lifted_pos[limb_i] + _vertical_lift_like(lifted_pos[limb_i], lift)
    lifted_payload = _assemble_payload_parts(store, lifted_pos, rot_parts, start_rot_parts, toe_parts)
    if int(vec.shape[-1]) == int(base_dim):
        return torch.cat((vec[:, : payload_vec_slice.start], lifted_payload), dim=-1)
    return torch.cat((vec[:, : payload_vec_slice.start], lifted_payload, vec[:, payload_vec_slice.stop :]), dim=-1)


def _project_one_foot_location(
    store: SimpleClipStore,
    limb_i: int,
    cur_pos: torch.Tensor,
    cur_rot6: torch.Tensor,
    cur_toe: torch.Tensor,
    pred_pos: torch.Tensor,
    pred_rot6: torch.Tensor,
    pred_toe: torch.Tensor,
    logit_pin_gate: torch.Tensor,
    integration_steps: int | None = None,
    height_pin_gate_enabled: bool | None = None,
) -> torch.Tensor:
    cur_rot = tl.rotation_6d_to_matrix(cur_rot6)
    pred_rot = tl.rotation_6d_to_matrix(pred_rot6)
    ground = store.foot_roll_ground_y_tensor.to(dtype=pred_pos.dtype)
    desired_lowest_y = _foot_lowest_y(store, limb_i, pred_pos, pred_rot, pred_toe)
    desired_height_after_lift = torch.relu(desired_lowest_y - ground)
    use_height_gate = bool(
        FOOT_ROLL_HEIGHT_PIN_GATE
        if height_pin_gate_enabled is None
        else height_pin_gate_enabled
    )
    height_gate = (
        _foot_height_pin_gate(desired_height_after_lift)[0]
        if use_height_gate
        else torch.ones_like(desired_height_after_lift)
    )
    roll_delta = _foot_roll_integrated_delta(
        store,
        limb_i,
        cur_rot,
        cur_toe,
        pred_rot,
        pred_toe,
        integration_steps=integration_steps,
    )
    pinned_components = []
    for axis in range(3):
        if axis == FOOT_ROLL_UP_AXIS:
            pinned_components.append(pred_pos[:, axis])
        else:
            pinned_components.append(cur_pos[:, axis] + roll_delta[:, axis])
    pinned_pos = torch.stack(pinned_components, dim=-1)
    pinned_weight = (height_gate.to(dtype=pred_pos.dtype) * logit_pin_gate.to(dtype=pred_pos.dtype)).reshape(-1, 1)
    out_pos = pred_pos + pinned_weight * (pinned_pos - pred_pos)
    lowest_y = _foot_lowest_y(store, limb_i, out_pos, pred_rot, pred_toe)
    lift = torch.relu(ground.to(dtype=out_pos.dtype) - lowest_y)
    return out_pos + _vertical_lift_like(out_pos, lift)


def _empty_foot_roll_pin_prob_like(pred_vec: torch.Tensor) -> torch.Tensor:
    return pred_vec.new_zeros((int(pred_vec.shape[0]), int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)))


def apply_foot_roll_output_projection_with_pin_prob(
    pred_vec: torch.Tensor,
    cur_vec: torch.Tensor,
    pin_logits: torch.Tensor,
    store: SimpleClipStore,
) -> tuple[torch.Tensor, torch.Tensor]:
    if (
        int(store.ik_payload_dim) == 0
        or int(pin_logits.shape[-1]) < int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)
        or len(getattr(store, "ik_payload_leg_limb_indices", ())) < 2
    ):
        return pred_vec, _empty_foot_roll_pin_prob_like(pred_vec)

    base_dim = base_output_dim_for_store(store)
    cur_base = cur_vec[:, :base_dim]
    pred_payload = pred_vec[:, payload_slice(store)]
    cur_payload = cur_base[:, payload_slice(store)]
    pred_pos, pred_rot6, pred_start_rot6, pred_toe = _parse_payload_parts(pred_payload, store)
    cur_pos, cur_rot6, _cur_start_rot6, cur_toe = _parse_payload_parts(cur_payload, store)

    legs_by_side: dict[str, int] = {}
    for limb_i in store.ik_payload_leg_limb_indices:
        side = str(store.ik_payload_slices[int(limb_i)].get("side", "")).lower().strip()
        if side:
            legs_by_side[side] = int(limb_i)
    if "l" not in legs_by_side or "r" not in legs_by_side:
        return pred_vec, _empty_foot_roll_pin_prob_like(pred_vec)

    pin_prob = foot_roll_pin_probabilities(pred_vec, pin_logits, store)

    projected_vec = apply_foot_roll_output_projection_with_pin_probabilities(
        pred_vec,
        cur_vec,
        pin_prob,
        store,
    )
    return projected_vec, pin_prob[..., : int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)].clamp(0.0, 1.0)


def foot_roll_pin_probabilities(
    pred_vec: torch.Tensor,
    pin_logits: torch.Tensor,
    store: SimpleClipStore,
) -> torch.Tensor:
    """Resolve the established frozen-controller pin probabilities without projection."""

    if (
        int(store.ik_payload_dim) == 0
        or int(pin_logits.shape[-1]) < int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)
        or len(getattr(store, "ik_payload_leg_limb_indices", ())) < 2
    ):
        return _empty_foot_roll_pin_prob_like(pred_vec)
    if str(FOOT_ROLL_PIN_MODE) == FOOT_ROLL_PIN_MODE_LEGACY_LOGIT_SELECTED:
        result = legacy_logit_selected_foot_pin_probabilities(pin_logits).to(
            dtype=pred_vec.dtype
        )
    else:
        result = near_floor_forced_pin_probabilities(store, pred_vec, pin_logits)
    return result[..., : int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)].clamp(0.0, 1.0)


def apply_foot_roll_output_projection_with_pin_probabilities(
    pred_vec: torch.Tensor,
    cur_vec: torch.Tensor,
    pin_probabilities: torch.Tensor,
    store: SimpleClipStore,
    integration_steps: int | None = None,
    height_pin_gate_enabled: bool | None = None,
) -> torch.Tensor:
    """Apply the established continuous foot projection from explicit probabilities.

    Controller checkpoints normally reach this kernel through raw pin logits.  A
    later residual controller can instead supply an already-defined continuous
    probability contract without inheriting the currently loaded controller's
    global pin mode or its near-floor forcing rule.
    """

    if (
        int(store.ik_payload_dim) == 0
        or int(pin_probabilities.shape[-1]) < int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)
        or len(getattr(store, "ik_payload_leg_limb_indices", ())) < 2
    ):
        return pred_vec

    base_dim = base_output_dim_for_store(store)
    cur_base = cur_vec[:, :base_dim]
    pred_payload = pred_vec[:, payload_slice(store)]
    cur_payload = cur_base[:, payload_slice(store)]
    pred_pos, pred_rot6, pred_start_rot6, pred_toe = _parse_payload_parts(pred_payload, store)
    cur_pos, cur_rot6, _cur_start_rot6, cur_toe = _parse_payload_parts(cur_payload, store)

    legs_by_side: dict[str, int] = {}
    for limb_i in store.ik_payload_leg_limb_indices:
        side = str(store.ik_payload_slices[int(limb_i)].get("side", "")).lower().strip()
        if side:
            legs_by_side[side] = int(limb_i)
    if "l" not in legs_by_side or "r" not in legs_by_side:
        return pred_vec

    pin_prob = pin_probabilities[..., : int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)].to(
        dtype=pred_vec.dtype
    ).clamp(0.0, 1.0)
    pinned_by_side = {"l": pin_prob[:, 0], "r": pin_prob[:, 1]}

    projected_pos = list(pred_pos)
    for side, limb_i in legs_by_side.items():
        toe_cur = cur_toe[limb_i]
        toe_pred = pred_toe[limb_i]
        if toe_cur is None or toe_pred is None:
            continue
        projected_pos[limb_i] = _project_one_foot_location(
            store,
            limb_i,
            cur_pos[limb_i],
            cur_rot6[limb_i],
            toe_cur,
            pred_pos[limb_i],
            pred_rot6[limb_i],
            toe_pred,
            pinned_by_side[side],
            integration_steps=integration_steps,
            height_pin_gate_enabled=height_pin_gate_enabled,
        )

    projected_payload = _assemble_payload_parts(store, projected_pos, pred_rot6, pred_start_rot6, pred_toe)
    projected_vec = torch.cat((pred_vec[:, : payload_slice(store).start], projected_payload), dim=-1)
    return projected_vec


def apply_foot_roll_output_projection(
    pred_vec: torch.Tensor,
    cur_vec: torch.Tensor,
    pin_logits: torch.Tensor,
    store: SimpleClipStore,
) -> torch.Tensor:
    projected_vec, _pin_prob = apply_foot_roll_output_projection_with_pin_prob(
        pred_vec,
        cur_vec,
        pin_logits,
        store,
    )
    return projected_vec


def _ik_base_positions_root(
    store: SimpleClipStore,
    pelvis_pos: torch.Tensor,
    pelvis_rot: torch.Tensor,
    core_rot6: torch.Tensor,
) -> torch.Tensor:
    clip = store.prototype
    b = int(pelvis_pos.shape[0])
    dtype = pelvis_pos.dtype
    offsets = store.local_offsets.to(dtype=dtype)
    if all(int(clip.parents_body_list[int(start)]) == int(clip.pelvis) for start in store.ik_base_start_indices):
        start_offsets = _store_rows_for_batch(offsets, b, "local_offsets").index_select(
            1, store.ik_base_start_indices_tensor
        )
        return pelvis_pos[:, None, :] + torch.matmul(start_offsets, pelvis_rot)
    fast_indices = store.ik_fast_base_indices
    if fast_indices is not None:
        def core_rot_for_name(bone_name: str) -> torch.Tensor:
            bone = int(fast_indices[bone_name])
            slot = int(clip.core_nonpelvis_map[bone])
            return tl.rotation_6d_to_matrix(core_rot6[:, slot])

        def child_pos(parent_pos: torch.Tensor, parent_rot: torch.Tensor, bone_name: str) -> torch.Tensor:
            offset = _store_indexed_vector_for_batch(
                offsets,
                int(fast_indices[bone_name]),
                b,
                "local_offsets",
            )
            return torch.matmul(offset.unsqueeze(1), parent_rot).squeeze(1) + parent_pos

        def child_rot(parent_rot: torch.Tensor, bone_name: str) -> torch.Tensor:
            return core_rot_for_name(bone_name) @ parent_rot

        pos = pelvis_pos
        rot = pelvis_rot
        for spine_name in ("spine_01", "spine_02", "spine_03", "spine_04", "spine_05"):
            pos = child_pos(pos, rot, spine_name)
            rot = child_rot(rot, spine_name)
        spine_pos = pos
        spine_rot = rot
        clav_l_pos = child_pos(spine_pos, spine_rot, "clavicle_l")
        clav_l_rot = child_rot(spine_rot, "clavicle_l")
        clav_r_pos = child_pos(spine_pos, spine_rot, "clavicle_r")
        clav_r_rot = child_rot(spine_rot, "clavicle_r")
        base_by_bone = {
            int(fast_indices["upperarm_l"]): child_pos(clav_l_pos, clav_l_rot, "upperarm_l"),
            int(fast_indices["upperarm_r"]): child_pos(clav_r_pos, clav_r_rot, "upperarm_r"),
            int(fast_indices["thigh_l"]): child_pos(pelvis_pos, pelvis_rot, "thigh_l"),
            int(fast_indices["thigh_r"]): child_pos(pelvis_pos, pelvis_rot, "thigh_r"),
        }
        return torch.stack([base_by_bone[int(start)] for start in store.ik_base_start_indices], dim=1)

    core_rot = tl.rotation_6d_to_matrix(core_rot6.reshape(-1, 6)).reshape(b, store.Jcore, 3, 3)
    identity = torch.eye(3, dtype=dtype, device=store.device).expand(b, 3, 3)
    pos_root: list[torch.Tensor | None] = [None] * int(clip.J)
    rot_root: list[torch.Tensor | None] = [None] * int(clip.J)
    for j in store.ik_base_eval_order:
        if j == int(clip.pelvis):
            local_pos = pelvis_pos
            local_rot = pelvis_rot
        else:
            local_pos = _store_indexed_vector_for_batch(offsets, j, b, "local_offsets")
            local_rot = core_rot[:, int(clip.core_nonpelvis_map[j])] if j in clip.core_nonpelvis_map else identity
        parent = int(clip.parents_body_list[j])
        if parent < 0:
            pos_j = local_pos
            rot_j = local_rot
        else:
            parent_pos = pos_root[parent]
            parent_rot = rot_root[parent]
            assert parent_pos is not None and parent_rot is not None
            pos_j = torch.matmul(local_pos.unsqueeze(1), parent_rot).squeeze(1) + parent_pos
            rot_j = local_rot @ parent_rot
        pos_root[j] = pos_j
        rot_root[j] = rot_j
    starts = store.ik_base_start_indices
    return torch.stack([pos_root[start] for start in starts], dim=1)  # type: ignore[index]


def clamp_clean_ik_payload(
    payload: torch.Tensor,
    store: SimpleClipStore,
    pelvis_pos: torch.Tensor,
    pelvis_rot: torch.Tensor,
    core_rot6: torch.Tensor,
) -> torch.Tensor:
    cleaned = fast_clean_ik_payload(payload, store)
    if not store.prototype.ik_limb_specs or not tl.IK_CLAMP_END_EFFECTORS_TO_REACH:
        return cleaned
    base_root = _ik_base_positions_root(store, pelvis_pos, pelvis_rot, core_rot6)
    lengths = _store_rows_for_batch(
        store.ik_limb_lengths.to(dtype=cleaned.dtype), b, "ik_limb_lengths"
    )
    end_parts: list[torch.Tensor] = []
    rot_parts: list[torch.Tensor] = []
    start_rot_parts: list[torch.Tensor] = []
    toe_parts: list[torch.Tensor | None] = []
    for spec in store.ik_payload_slices:
        pos_slice = spec["pos"]
        rot_slice = spec["rot6"]
        start_rot_slice = spec["start_rot6"]
        toe_slice = spec["toe_float"]
        assert isinstance(pos_slice, slice)
        assert isinstance(rot_slice, slice)
        assert isinstance(start_rot_slice, slice)
        end_parts.append(cleaned[:, pos_slice])
        rot_parts.append(cleaned[:, rot_slice])
        start_rot_parts.append(cleaned[:, start_rot_slice])
        if toe_slice is not None:
            assert isinstance(toe_slice, slice)
            toe_parts.append(cleaned[:, toe_slice])
        else:
            toe_parts.append(None)
    end_root = torch.stack(end_parts, dim=1)
    start_rot = tl.rotation_6d_to_matrix(torch.stack(start_rot_parts, dim=1).reshape(-1, 6)).reshape(
        end_root.shape[0], -1, 3, 3
    )
    upper_offsets = _store_rows_for_batch(
        store.ik_mid_offsets.to(dtype=cleaned.dtype), b, "ik_mid_offsets"
    )
    mid_root = base_root + torch.matmul(upper_offsets.unsqueeze(2), start_rot).squeeze(2)
    delta = end_root - mid_root
    d = torch.linalg.norm(delta, dim=-1, keepdim=True)
    lower_offsets = _store_rows_for_batch(
        store.ik_end_offsets.to(dtype=cleaned.dtype), b, "ik_end_offsets"
    )
    fallback_axis = torch.matmul(lower_offsets.unsqueeze(2), start_rot).squeeze(2)
    axis = torch.where(d > 1e-8, tl.normalize(delta), tl.normalize(fallback_axis))
    l2 = lengths[:, :, 1:2]
    clamped_pos = mid_root + axis * d.clamp_min(1e-8).clamp(max=l2 - 1e-5)
    parts: list[torch.Tensor] = []
    for limb_i, toe in enumerate(toe_parts):
        parts.append(clamped_pos[:, limb_i])
        parts.append(rot_parts[limb_i])
        parts.append(start_rot_parts[limb_i])
        if toe is not None:
            parts.append(toe)
    return torch.cat(parts, dim=-1)


def _clean_output_vector_base(raw: torch.Tensor, store: SimpleClipStore) -> torch.Tensor:
    b = raw.shape[0]
    cursor = 0
    pelvis_pos = raw[:, cursor : cursor + 3]
    cursor += 3
    core_dim = store.Jcore * 6
    cleaned_body_rot6 = fast_clean_6d(raw[:, cursor : cursor + 6 + core_dim].reshape(-1, 6)).reshape(
        b, store.Jcore + 1, 6
    )
    pelvis_rot6 = cleaned_body_rot6[:, 0]
    core_rot6 = cleaned_body_rot6[:, 1:]
    cursor += 6 + core_dim
    pelvis_rot = tl.rotation_6d_to_matrix(pelvis_rot6)
    payload = clamp_clean_ik_payload(raw[:, cursor : cursor + store.ik_payload_dim], store, pelvis_pos, pelvis_rot, core_rot6)
    return torch.cat((pelvis_pos, pelvis_rot6, core_rot6.reshape(b, -1), payload), dim=-1)


def clean_output_vector(
    raw: torch.Tensor,
    store: SimpleClipStore,
    cur_vec: torch.Tensor | None = None,
    prev_vec: torch.Tensor | None = None,
) -> torch.Tensor:
    projected, _unprojected = clean_output_vector_pair(raw, store, cur_vec, prev_vec)
    return projected


def clean_output_vector_pair(
    raw: torch.Tensor,
    store: SimpleClipStore,
    cur_vec: torch.Tensor | None = None,
    prev_vec: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    projected, unprojected, _pin_prob = clean_output_vector_pair_with_pin_prob(raw, store, cur_vec, prev_vec)
    return projected, unprojected


def clean_output_vector_pair_with_pin_prob(
    raw: torch.Tensor,
    store: SimpleClipStore,
    cur_vec: torch.Tensor | None = None,
    prev_vec: torch.Tensor | None = None,
    *,
    apply_foot_projection: bool = True,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    base_dim = base_output_dim_for_store(store)
    raw_base = raw[:, :base_dim]
    vec = _clean_output_vector_base(raw_base, store)
    unprojected_vec = vec
    pin_prob = _empty_foot_roll_pin_prob_like(vec)
    if (
        cur_vec is not None
        and raw.shape[-1] >= base_dim + int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)
    ):
        pin_logits = raw[:, base_dim : base_dim + int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)]
        vec = apply_fake_gravity_output(store, vec, prev_vec, cur_vec, pin_logits)
        unprojected_vec = vec
        pin_prob = foot_roll_pin_probabilities(vec, pin_logits, store)
        if apply_foot_projection:
            vec = apply_foot_roll_output_projection_with_pin_probabilities(
                vec,
                _clean_output_vector_base(cur_vec[:, :base_dim], store),
                pin_prob,
                store,
            )
    return vec, unprojected_vec, pin_prob


def foot_roll_lowest_heights_from_vec(store: SimpleClipStore, vec: torch.Tensor) -> torch.Tensor:
    if int(store.ik_payload_dim) == 0 or len(getattr(store, "ik_payload_leg_limb_indices", ())) < 2:
        return vec.new_zeros((int(vec.shape[0]), int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)))
    payload = vec[:, payload_slice(store)]
    pos_parts, rot_parts, _start_rot_parts, toe_parts = _parse_payload_parts(payload, store)
    by_side: dict[str, int] = {}
    for limb_i in store.ik_payload_leg_limb_indices:
        side = str(store.ik_payload_slices[int(limb_i)].get("side", "")).lower().strip()
        if side:
            by_side[side] = int(limb_i)
    heights: list[torch.Tensor] = []
    ground = store.foot_roll_ground_y_tensor.to(dtype=vec.dtype)
    for side in ("l", "r"):
        limb_i = by_side.get(side)
        if limb_i is None or toe_parts[limb_i] is None:
            heights.append(vec.new_full((int(vec.shape[0]),), float("inf")))
            continue
        rot = tl.rotation_6d_to_matrix(rot_parts[limb_i])
        lowest_y = _foot_lowest_y(store, limb_i, pos_parts[limb_i], rot, toe_parts[limb_i])
        heights.append(torch.relu(lowest_y - ground))
    return torch.stack(heights, dim=-1)


def foot_roll_smooth_lowest_heights_from_vec(store: SimpleClipStore, vec: torch.Tensor) -> torch.Tensor:
    if int(store.ik_payload_dim) == 0 or len(getattr(store, "ik_payload_leg_limb_indices", ())) < 2:
        return vec.new_zeros((int(vec.shape[0]), int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)))
    payload = vec[:, payload_slice(store)]
    pos_parts, rot_parts, _start_rot_parts, toe_parts = _parse_payload_parts(payload, store)
    by_side: dict[str, int] = {}
    for limb_i in store.ik_payload_leg_limb_indices:
        side = str(store.ik_payload_slices[int(limb_i)].get("side", "")).lower().strip()
        if side:
            by_side[side] = int(limb_i)
    ground = store.foot_roll_ground_y_tensor.to(dtype=vec.dtype)
    foot_half = store.foot_roll_foot_half_dims.to(dtype=vec.dtype)
    toe_half = store.foot_roll_toe_half_dims.to(dtype=vec.dtype)
    up_axis = int(FOOT_ROLL_HEIGHT_AXIS)
    heights: list[torch.Tensor] = []
    for side in ("l", "r"):
        limb_i = by_side.get(side)
        if limb_i is None or toe_parts[limb_i] is None:
            heights.append(vec.new_zeros((int(vec.shape[0]),)))
            continue
        rot = tl.rotation_6d_to_matrix(rot_parts[limb_i])
        (
            foot_center,
            foot_forward,
            foot_side,
            foot_up,
            toe_center,
            toe_forward,
            toe_side,
            toe_up,
        ) = _foot_toe_box_axes(store, limb_i, pos_parts[limb_i], rot, toe_parts[limb_i], up_axis=up_axis)
        foot_low = foot_center[:, up_axis] - (
            foot_forward[:, up_axis].abs() * foot_half[0]
            + foot_side[:, up_axis].abs() * foot_half[1]
            + foot_up[:, up_axis].abs() * foot_half[2]
        )
        toe_low = toe_center[:, up_axis] - (
            toe_forward[:, up_axis].abs() * toe_half[0]
            + toe_side[:, up_axis].abs() * toe_half[1]
            + toe_up[:, up_axis].abs() * toe_half[2]
        )
        heights.append(torch.relu(torch.minimum(foot_low, toe_low) - ground))
    return torch.stack(heights, dim=-1)


def predicted_state_from_raw(
    raw: torch.Tensor,
    store: SimpleClipStore,
    cur_vec: torch.Tensor | None = None,
    prev_vec: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    vec = clean_output_vector(raw, store, cur_vec, prev_vec)
    return vec, vec[:, :3], vec[:, payload_slice(store)]


def predicted_state_from_vector(vec: torch.Tensor, store: SimpleClipStore) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    return vec, vec[:, :3], vec[:, payload_slice(store)]


def model_forward(
    model: torch.nn.Module,
    inp: torch.Tensor,
    cur_vec: torch.Tensor,
    cfg_or_store: tl.TrainConfig | SimpleClipStore,
    prev_vec: torch.Tensor | None = None,
) -> torch.Tensor:
    raw = model_raw_output(model, inp, cur_vec, cfg_or_store)
    if isinstance(cfg_or_store, SimpleClipStore):
        return clean_output_vector(raw, cfg_or_store, cur_vec, prev_vec)
    return raw


def model_raw_output(
    model: torch.nn.Module,
    inp: torch.Tensor,
    cur_vec: torch.Tensor,
    cfg_or_store: tl.TrainConfig | SimpleClipStore,
) -> torch.Tensor:
    store = cfg_or_store if isinstance(cfg_or_store, SimpleClipStore) else None
    cfg = store.cfg if store is not None else cfg_or_store
    raw = model(inp)
    if cfg.predict_residual or tl.output_prediction_uses_residual():
        base_dim = int(cur_vec.shape[-1])
        if int(raw.shape[-1]) > base_dim:
            raw = torch.cat((cur_vec + raw[:, :base_dim], raw[:, base_dim:]), dim=-1)
        else:
            raw = cur_vec + raw
    return raw


def foot_pin_mask_from_logits(pin_logits: torch.Tensor) -> torch.Tensor:
    if int(pin_logits.shape[-1]) < int(tl.FOOT_ROLL_PIN_OUTPUT_DIM):
        return torch.zeros((*pin_logits.shape[:-1], int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)), dtype=torch.bool, device=pin_logits.device)
    if str(FOOT_ROLL_PIN_MODE) == FOOT_ROLL_PIN_MODE_LEGACY_LOGIT_SELECTED:
        return legacy_logit_selected_foot_pin_probabilities(pin_logits) >= 0.5
    return soft_foot_pin_probabilities(pin_logits) >= 0.5


def foot_pin_logits_from_raw(raw: torch.Tensor, store: SimpleClipStore) -> torch.Tensor:
    base_dim = base_output_dim_for_store(store)
    pin_dim = int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)
    if int(raw.shape[-1]) < base_dim + pin_dim:
        return raw.new_empty((*raw.shape[:-1], 0))
    return raw[..., base_dim : base_dim + pin_dim]


def real_dataset_row_scope_rows(store: SimpleClipStore, clip_ids: torch.Tensor, dtype: torch.dtype) -> torch.Tensor:
    synthetic_flags = getattr(store, "synthetic", None)
    if not isinstance(synthetic_flags, torch.Tensor) or int(synthetic_flags.numel()) == 0:
        return torch.ones_like(clip_ids, dtype=dtype)
    generated = synthetic_flags.index_select(0, clip_ids.to(store.device).long())
    return (~generated).to(dtype=dtype)


def periodic_dataset_row_scope_rows(store: SimpleClipStore, clip_ids: torch.Tensor, dtype: torch.dtype) -> torch.Tensor:
    cyclic = store.cyclic.index_select(0, clip_ids.to(store.device).long()).to(dtype=dtype)
    return cyclic * real_dataset_row_scope_rows(store, clip_ids, dtype)


def scoped_row_metric_weight(
    row_weight: torch.Tensor,
    active_f: torch.Tensor,
    scope: torch.Tensor,
    batch_count_override: int | None = None,
) -> torch.Tensor:
    scoped_active = active_f * scope
    scoped_count = scoped_active.detach().sum().clamp_min(1.0)
    batch_count = float(max(1, int(batch_count_override if batch_count_override is not None else scoped_active.shape[0])))
    return row_weight * scoped_active * (batch_count / scoped_count)


def real_dataset_row_metric_weight(
    row_weight: torch.Tensor,
    active_f: torch.Tensor,
    real_scope: torch.Tensor,
) -> torch.Tensor:
    real_count = real_scope.detach().sum().clamp_min(1.0)
    batch_count = float(max(1, int(real_scope.shape[0])))
    return row_weight * active_f * real_scope * (batch_count / real_count)


def apply_dedicated_real_loss_multiplier(
    row_weight: torch.Tensor,
    dedicated_real_rows: int,
    multiplier: float,
) -> torch.Tensor:
    row_count = max(0, min(int(row_weight.numel()), int(dedicated_real_rows)))
    multiplier_f = max(0.0, float(multiplier))
    if row_count <= 0 or multiplier_f == 1.0:
        return row_weight
    scaled = row_weight.clone()
    scaled[:row_count] = scaled[:row_count] * multiplier_f
    return scaled


def allocated_row_scope_mask(
    scope: str,
    row_weight: torch.Tensor,
    dedicated_real_rows: int,
    periodic_reserved_rows: int,
) -> torch.Tensor:
    if scope == GT_MSE_ROW_SCOPE_ALL:
        return torch.ones_like(row_weight)
    if scope != GT_MSE_ROW_SCOPE_DEDICATED_PERIODIC:
        raise ValueError(f"Unknown allocated row scope {scope!r}")
    row_count = max(
        0,
        min(
            int(row_weight.numel()),
            int(max(0, dedicated_real_rows)) + int(max(0, periodic_reserved_rows)),
        ),
    )
    scoped = torch.zeros_like(row_weight)
    if row_count > 0:
        scoped[:row_count] = 1.0
    return scoped


def gt_mse_row_scope_mask(
    row_weight: torch.Tensor,
    dedicated_real_rows: int,
    periodic_reserved_rows: int,
) -> torch.Tensor:
    return allocated_row_scope_mask(GT_MSE_ROW_SCOPE, row_weight, dedicated_real_rows, periodic_reserved_rows)


def gt_mse_row_metric_weight(
    row_weight: torch.Tensor,
    dedicated_real_rows: int,
    periodic_reserved_rows: int,
) -> torch.Tensor:
    return row_weight * gt_mse_row_scope_mask(row_weight, dedicated_real_rows, periodic_reserved_rows)


def ae6_row_scope_mask(
    row_weight: torch.Tensor,
    dedicated_real_rows: int,
    periodic_reserved_rows: int,
) -> torch.Tensor:
    return allocated_row_scope_mask(AE6_ROW_SCOPE, row_weight, dedicated_real_rows, periodic_reserved_rows)


def pin_logit_gap_hinge_rows(pin_logits: torch.Tensor) -> torch.Tensor:
    pin_dim = int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)
    if int(pin_logits.shape[-1]) < pin_dim:
        return torch.zeros((*pin_logits.shape[:-1],), dtype=pin_logits.dtype, device=pin_logits.device)
    gap = (pin_logits[..., 0] - pin_logits[..., 1]).abs()
    return gap.neg().add(float(PIN_LOGIT_GAP_MARGIN)).clamp_min(0.0)


def root_horizontal_acceleration_rows(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
) -> torch.Tensor:
    prev_pos, _prev_rot, _prev_yaw, _prev_heading = store.root_state(clip_ids, cur_idx - 1)
    cur_pos, _cur_rot, _cur_yaw, _cur_heading = store.root_state(clip_ids, cur_idx)
    next_pos, _next_rot, _next_yaw, _next_heading = store.root_state(clip_ids, cur_idx + 1)
    fps = float(getattr(store.prototype, "fps", 30.0))
    prev_xz = torch.stack((prev_pos[:, 0], prev_pos[:, 2]), dim=-1)
    cur_xz = torch.stack((cur_pos[:, 0], cur_pos[:, 2]), dim=-1)
    next_xz = torch.stack((next_pos[:, 0], next_pos[:, 2]), dim=-1)
    prev_vel = (cur_xz - prev_xz) * fps
    next_vel = (next_xz - cur_xz) * fps
    return torch.linalg.vector_norm(next_vel - prev_vel, dim=-1) * fps


def _smoothstep01(x: torch.Tensor) -> torch.Tensor:
    t = x.clamp(0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def root_accel_pin_loss_rows(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
    pin_logits: torch.Tensor,
    cleaned_heights_m: torch.Tensor,
    smooth_heights_m: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    pin_dim = int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)
    if int(pin_logits.shape[-1]) < pin_dim or int(cleaned_heights_m.shape[-1]) < pin_dim:
        zeros = torch.zeros((*pin_logits.shape[:-1],), dtype=pin_logits.dtype, device=pin_logits.device)
        return zeros, zeros, zeros, zeros, zeros, zeros, zeros

    root_acc = root_horizontal_acceleration_rows(store, clip_ids, cur_idx).to(dtype=pin_logits.dtype)
    gate_width = max(float(ROOT_ACCEL_PIN_ACCEL_GATE_WIDTH_MPS2), 1.0e-6)
    accel_gate = _smoothstep01((root_acc - float(ROOT_ACCEL_PIN_ACCEL_THRESHOLD_MPS2)) / gate_width)
    accel_active = (root_acc > float(ROOT_ACCEL_PIN_ACCEL_THRESHOLD_MPS2)).to(dtype=pin_logits.dtype)

    pin_prob = soft_foot_pin_probabilities(pin_logits)[..., :pin_dim].to(dtype=pin_logits.dtype)
    soft_select = torch.softmax(pin_prob * float(ROOT_ACCEL_PIN_SOFTMAX_SCALE), dim=-1)
    hard_idx = pin_prob.detach().argmax(dim=-1, keepdim=True)

    hard_max_pin = pin_prob.detach().gather(-1, hard_idx).squeeze(-1)
    soft_max_pin = (soft_select * pin_prob).sum(dim=-1)
    selected_pin = hard_max_pin + soft_max_pin - soft_max_pin.detach()

    forward_heights = cleaned_heights_m[..., :pin_dim].to(dtype=pin_logits.dtype)
    gradient_heights = smooth_heights_m[..., :pin_dim].to(dtype=pin_logits.dtype)
    height_for_loss = forward_heights.detach() + gradient_heights - gradient_heights.detach()
    hard_selected_height = forward_heights.detach().gather(-1, hard_idx).squeeze(-1)
    soft_selected_height = (soft_select * height_for_loss).sum(dim=-1)
    selected_height = hard_selected_height + soft_selected_height - soft_selected_height.detach()

    pin_deficit = torch.relu(float(ROOT_ACCEL_PIN_TARGET_PROB) - selected_pin) / max(
        float(ROOT_ACCEL_PIN_TARGET_PROB),
        1.0e-6,
    )
    height_excess = torch.relu(selected_height - float(ROOT_ACCEL_PIN_HEIGHT_THRESHOLD_M)) / max(
        float(ROOT_ACCEL_PIN_HEIGHT_THRESHOLD_M),
        1.0e-6,
    )
    rows = accel_gate * (pin_deficit.square() + height_excess.square())
    bad_rows = (
        (
            (hard_max_pin < float(ROOT_ACCEL_PIN_TARGET_PROB))
            | (hard_selected_height > float(ROOT_ACCEL_PIN_HEIGHT_THRESHOLD_M))
        ).to(dtype=pin_logits.dtype)
        * accel_active
    )
    return rows, root_acc.detach(), accel_active.detach(), bad_rows.detach(), hard_max_pin.detach(), hard_selected_height.detach(), accel_gate.detach()


def root_motion_activity_rows(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
    reference_store: SimpleClipStore | None = None,
) -> torch.Tensor:
    ref = reference_store or store
    prev_idx = cur_idx - 1
    prev_pos, _prev_rot, prev_yaw, _prev_heading = store.root_state(clip_ids, prev_idx)
    cur_pos, _cur_rot, cur_yaw, _cur_heading = store.root_state(clip_ids, cur_idx)
    root_delta_xz = torch.stack((cur_pos[:, 0] - prev_pos[:, 0], cur_pos[:, 2] - prev_pos[:, 2]), dim=-1)
    root_speed = torch.linalg.vector_norm(root_delta_xz, dim=-1) * float(store.prototype.fps)
    yaw_delta = tl.wrap_angle(cur_yaw - prev_yaw).abs()
    speed_cutoff = max(float(getattr(ref, "stationary_double_pin_speed_cutoff_mps", 0.0)), 1e-6)
    yaw_cutoff = max(float(getattr(ref, "stationary_double_pin_yaw_cutoff_rad", 0.0)), 1e-6)
    speed_activity = root_speed / speed_cutoff
    yaw_activity = yaw_delta / yaw_cutoff
    return torch.maximum(speed_activity, yaw_activity).clamp(min=0.0, max=1.0)


def model_forward_with_pin_mask(
    model: torch.nn.Module,
    inp: torch.Tensor,
    cur_vec: torch.Tensor,
    store: SimpleClipStore,
    prev_vec: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    raw = model_raw_output(model, inp, cur_vec, store)
    pred_vec = clean_output_vector(raw, store, cur_vec, prev_vec)
    heights = foot_roll_lowest_heights_from_vec(store, pred_vec)
    pin_logits = foot_pin_logits_from_raw(raw, store)
    return pred_vec, foot_pin_mask_from_heights_and_logits(heights, pin_logits)


def build_controller_input(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
    prev_vec: torch.Tensor,
    cur_vec: torch.Tensor,
    prev_pelvis: torch.Tensor,
    cur_pelvis: torch.Tensor,
    prev_payload: torch.Tensor,
    cur_payload: torch.Tensor,
) -> torch.Tensor:
    pelvis_vel = (cur_pelvis - prev_pelvis) / store.cfg.pose_delta_scale_final
    payload_vel = (cur_payload - prev_payload).reshape(cur_idx.shape[0], -1) / store.cfg.pose_delta_scale_final
    root_features = store.get_input_root_features(clip_ids, cur_idx)
    return torch.cat((cur_vec, prev_vec, pelvis_vel, payload_vel, root_features), dim=-1)


def ae_window_frames_from_dims(mean: torch.Tensor, controller_input_dim: int, output_dim: int) -> int:
    base_dim = int(controller_input_dim) + int(output_dim)
    if base_dim <= 0:
        return 1
    total_dim = int(mean.shape[-1])
    if total_dim == base_dim:
        return 1
    if total_dim % base_dim != 0:
        raise ValueError(f"AE feature dim {total_dim} is not a multiple of controller row dim {base_dim}")
    return max(1, total_dim // base_dim)


def ae_window_frames_for_checkpoint(ae_ckpt: dict, controller_feature_dim: int) -> int:
    schema = ae_ckpt.get("schema", {}) if isinstance(ae_ckpt, dict) else {}
    if isinstance(schema, dict):
        window_frames = schema.get("window_frames")
        if window_frames is not None:
            return max(1, int(window_frames))
        total_dim = schema.get("total_dim")
        base_total_dim = schema.get("base_total_dim", controller_feature_dim)
        if total_dim is not None:
            base = max(1, int(base_total_dim or controller_feature_dim))
            if int(total_dim) % base != 0:
                raise ValueError(f"AE checkpoint total_dim={total_dim} is not divisible by base_total_dim={base}")
            return max(1, int(total_dim) // base)
    return 2


def ae5_window_frames_for_checkpoint(ae_ckpt: dict, controller_feature_dim: int) -> int:
    schema = ae_ckpt.get("schema", {}) if isinstance(ae_ckpt, dict) else {}
    if isinstance(schema, dict) and schema.get("feature") == IK_MOTION_AE_FEATURE_ROOT_POSE_WINDOW:
        return max(1, int(schema.get("window_frames", 1)))
    return ae_window_frames_for_checkpoint(ae_ckpt, controller_feature_dim)


def transition_target_feature(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
) -> torch.Tensor:
    cyclic = store.cyclic.index_select(0, clip_ids.to(store.device).long())
    cur_idx = torch.where(cyclic, cur_idx, cur_idx.clamp_min(0))
    prev_idx = torch.where(cyclic, cur_idx - 1, (cur_idx - 1).clamp_min(0))
    prev_vec, prev_pelvis, prev_payload = target_state(store, clip_ids, prev_idx)
    cur_vec, cur_pelvis, cur_payload = target_state(store, clip_ids, cur_idx)
    inp = build_controller_input(store, clip_ids, cur_idx, prev_vec, cur_vec, prev_pelvis, cur_pelvis, prev_payload, cur_payload)
    target_vec = transition_target_output(store, clip_ids, cur_idx)
    return torch.cat((inp, target_vec), dim=-1)


def initial_ae_context(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
    frames: int,
) -> torch.Tensor | None:
    frames = max(1, int(frames))
    if frames <= 1:
        return None
    rows = [transition_target_feature(store, clip_ids, cur_idx + offset) for offset in range(-(frames - 1), 0)]
    return torch.stack(rows, dim=1)


def duplicated_init_ae_context(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
    init_vec: torch.Tensor,
    init_pelvis: torch.Tensor,
    init_payload: torch.Tensor,
    frames: int,
) -> torch.Tensor | None:
    frames = max(1, int(frames))
    if frames <= 1:
        return None
    inp = build_controller_input(
        store,
        clip_ids,
        cur_idx,
        init_vec,
        init_vec,
        init_pelvis,
        init_pelvis,
        init_payload,
        init_payload,
    )
    row = torch.cat((inp, init_vec), dim=-1)
    return row[:, None, :].expand(-1, frames - 1, -1)


def ae_feature_rows(
    mean: torch.Tensor,
    controller_input: torch.Tensor,
    predicted_output: torch.Tensor,
    context: torch.Tensor | None = None,
) -> tuple[torch.Tensor, int, int, int]:
    input_dim = int(controller_input.shape[-1])
    output_dim = int(predicted_output.shape[-1])
    base_dim = input_dim + output_dim
    frames = ae_window_frames_from_dims(mean, input_dim, output_dim)
    current = torch.cat((controller_input, predicted_output), dim=-1)
    if frames <= 1:
        return current, frames, input_dim, output_dim
    if context is None:
        raise ValueError(f"AE expects {frames} transition rows but no temporal context was provided")
    if int(context.shape[1]) != frames - 1 or int(context.shape[2]) != base_dim:
        raise ValueError(
            f"AE context shape {tuple(context.shape)} does not match frames={frames} and base_dim={base_dim}"
        )
    return torch.cat((context, current[:, None, :]), dim=1).reshape(current.shape[0], frames * base_dim), frames, input_dim, output_dim


def ae_model_feature(ae: SimpleAutoencoder, feature: torch.Tensor) -> torch.Tensor:
    schema = getattr(ae, "_simple_ae_schema", None)
    if not isinstance(schema, dict):
        return feature
    return transform_ae_feature_space(feature, schema)


def ae_score_rows(
    ae: SimpleAutoencoder,
    mean: torch.Tensor,
    std: torch.Tensor,
    controller_input: torch.Tensor,
    predicted_output: torch.Tensor,
    context: torch.Tensor | None = None,
    store: SimpleClipStore | None = None,
) -> torch.Tensor:
    feature, frames, input_dim, output_dim = ae_feature_rows(mean, controller_input, predicted_output, context)
    feature = ae_model_feature(ae, feature)
    x = (feature - mean) / std
    recon = ae(x)
    schema = getattr(ae, "_simple_ae_schema", None)
    score_scope = (
        normalized_ae_score_scope(schema.get("ae_score_scope", AE_SCORE_SCOPE_OUTPUT))
        if isinstance(schema, dict)
        else AE_SCORE_SCOPE_OUTPUT
    )
    if score_scope == AE_SCORE_SCOPE_FULL_WINDOW:
        return (recon - x).square().mean(dim=-1)
    if AE_SCORE_OUTPUT_ONLY:
        base_dim = input_dim + output_dim
        output_start = (frames - 1) * base_dim + input_dim
        output_end = output_start + output_dim
        diff = recon[:, output_start:output_end] - x[:, output_start:output_end]
        mask = ae_output_mse_mask(store, output_dim, diff.dtype, diff.device)
        denom = mask.sum().clamp_min(1.0)
        return diff.square().mul(mask.reshape(1, -1)).sum(dim=-1) / denom
    return (recon - x).square().mean(dim=-1)


def ae6_contact_target_rows(
    ae6: torch.nn.Module,
    mean: torch.Tensor,
    std: torch.Tensor,
    controller_input: torch.Tensor,
    predicted_output: torch.Tensor,
    context: torch.Tensor | None = None,
) -> torch.Tensor:
    feature, _frames, _input_dim, _output_dim = ae_feature_rows(mean, controller_input, predicted_output, context)
    schema = getattr(ae6, "_ae6_schema", None)
    if isinstance(schema, dict):
        feature = transform_ae_feature_space(feature, schema)
    x = (feature - mean) / std
    return ae6(x).clamp(0.0, 1.0)


def ae6_contact_loss_rows(
    ae6: torch.nn.Module,
    mean: torch.Tensor,
    std: torch.Tensor,
    controller_input: torch.Tensor,
    predicted_output: torch.Tensor,
    pin_logits: torch.Tensor,
    context: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    if int(pin_logits.shape[-1]) < int(tl.FOOT_ROLL_PIN_OUTPUT_DIM):
        zeros = torch.zeros((int(controller_input.shape[0]),), dtype=controller_input.dtype, device=controller_input.device)
        return zeros, zeros, zeros, zeros
    target = ae6_contact_target_rows(ae6, mean, std, controller_input, predicted_output, context).detach()
    pin_meter = soft_foot_pin_probabilities(pin_logits).to(dtype=target.dtype)
    pin_meter = pin_meter[..., : int(target.shape[-1])]
    target = target[..., : int(pin_meter.shape[-1])]
    pin_error = pin_meter - target
    mse = pin_error.square().mean(dim=-1)
    mae = pin_error.abs().mean(dim=-1)
    acc = ((pin_meter >= 0.5) == (target >= 0.5)).to(dtype=pin_meter.dtype).mean(dim=-1)
    return mse, mse.detach(), mae.detach(), acc.detach()


@torch.no_grad()
def simple_ae_gt_score_mean(
    ae: SimpleAutoencoder,
    mean: torch.Tensor,
    std: torch.Tensor,
    store: SimpleClipStore,
    clip_ids: tuple[int, ...],
    min_start: int,
    max_rows: int = 4096,
    batch_rows: int = 512,
) -> float:
    if not clip_ids:
        return float("nan")
    frames = ae_window_frames_from_dims(mean, *tl.make_batch_dims(store.prototype, store.cfg))
    pool = build_training_start_pool(store, 1, max(int(min_start), int(frames)), clip_ids)
    row_clip_ids, row_starts = validation_rows(pool, max(1, int(max_rows)))
    total = 0.0
    count = 0
    for start in range(0, int(row_clip_ids.numel()), max(1, int(batch_rows))):
        end = min(int(row_clip_ids.numel()), start + max(1, int(batch_rows)))
        batch_clip_ids = row_clip_ids[start:end]
        batch_starts = row_starts[start:end]
        prev_vec, prev_pelvis, prev_payload = target_state(store, batch_clip_ids, batch_starts - 1)
        cur_vec, cur_pelvis, cur_payload = target_state(store, batch_clip_ids, batch_starts)
        inp = build_controller_input(
            store,
            batch_clip_ids,
            batch_starts,
            prev_vec,
            cur_vec,
            prev_pelvis,
            cur_pelvis,
            prev_payload,
            cur_payload,
        )
        target_vec = transition_target_output(store, batch_clip_ids, batch_starts)
        context = initial_ae_context(store, batch_clip_ids, batch_starts, frames)
        rows = ae_score_rows(ae, mean, std, inp, target_vec, context, store)
        total += float(rows.sum().detach().cpu())
        count += int(rows.numel())
    return total / float(max(1, count))


def calibrate_ae5_effective_loss_weight(
    ae: SimpleAutoencoder | None,
    mean: torch.Tensor,
    std: torch.Tensor,
    ae_loss_weight: float,
    ae5: SimpleAutoencoder | None,
    ae5_mean: torch.Tensor | None,
    ae5_std: torch.Tensor | None,
    ae5_loss_weight: float,
    store: SimpleClipStore,
    periodic_clip_ids: tuple[int, ...],
    min_start: int,
    max_rows: int = 4096,
) -> tuple[float, dict[str, float]]:
    if ae5 is None or ae5_mean is None or ae5_std is None or float(ae5_loss_weight) == 0.0:
        return 0.0, {}
    if ae is None:
        return float(ae5_loss_weight), {
            "ae1_omni_gt_mean": float("nan"),
            "ae5_omni_gt_mean": float("nan"),
            "ae1_loss_weight": float(ae_loss_weight),
            "ae5_user_loss_weight": float(ae5_loss_weight),
            "ae5_effective_loss_weight": float(ae5_loss_weight),
            "calibration_rows": 0.0,
            "calibration_fallback": "ae1_disabled_use_user_weight",
        }
    ae1_mean = simple_ae_gt_score_mean(ae, mean, std, store, periodic_clip_ids, min_start, max_rows)
    ae5_gt_mean = (
        ik_motion_ae_gt_score_mean(ae5, ae5_mean, ae5_std, store, periodic_clip_ids, min_start, max_rows)
        if is_ik_motion_window_ae(ae5)
        else simple_ae_gt_score_mean(ae5, ae5_mean, ae5_std, store, periodic_clip_ids, min_start, max_rows)
    )
    if not (math.isfinite(ae1_mean) and math.isfinite(ae5_gt_mean)) or ae5_gt_mean <= 0.0:
        raise RuntimeError(f"AE5 calibration failed: ae1_omni_mean={ae1_mean} ae5_omni_mean={ae5_gt_mean}")
    effective = float(ae5_loss_weight) * float(ae_loss_weight) * float(ae1_mean) / float(ae5_gt_mean)
    return effective, {
        "ae1_omni_gt_mean": float(ae1_mean),
        "ae5_omni_gt_mean": float(ae5_gt_mean),
        "ae1_loss_weight": float(ae_loss_weight),
        "ae5_user_loss_weight": float(ae5_loss_weight),
        "ae5_effective_loss_weight": float(effective),
        "calibration_rows": float(max_rows),
    }


def pin_aware_ae3_score_rows(
    ae3: torch.nn.Module,
    mean: torch.Tensor,
    std: torch.Tensor,
    pos_weight: torch.Tensor | None,
    controller_input: torch.Tensor,
    store: SimpleClipStore,
    predicted_output: torch.Tensor,
    pin_logits: torch.Tensor,
    heights_m: torch.Tensor | None = None,
) -> torch.Tensor:
    if int(pin_logits.shape[-1]) < int(tl.FOOT_ROLL_PIN_OUTPUT_DIM):
        return torch.zeros((int(controller_input.shape[0]),), dtype=controller_input.dtype, device=controller_input.device)
    _ = pos_weight
    x = (controller_input.detach() - mean) / std
    expected_prob = torch.sigmoid(ae3(x).detach())
    if bool(FOOT_ROLL_HEIGHT_PIN_GATE):
        height_vec = ae3_foot_only_height_gradient_vector(store, predicted_output)
        heights_m = foot_roll_lowest_heights_from_vec(store, height_vec)
    pin_meter = ae3_post_gate_pin_probabilities(pin_logits, heights_m).to(dtype=expected_prob.dtype)
    loss = F.binary_cross_entropy(ae3_bce_input(pin_meter), expected_prob, reduction="none")
    rows = loss.mean(dim=-1)
    if bool(FOOT_ROLL_HEIGHT_PIN_GATE) and heights_m is not None:
        rows = rows + float(AE3_EXPECTED_PIN_HEIGHT_PUSH_SCALE) * ae3_expected_pin_height_push_rows(
            expected_prob, heights_m
        ).to(dtype=rows.dtype)
    if float(AE3_LOGIT_ALIGNMENT_SCALE) != 0.0:
        rows = rows + float(AE3_LOGIT_ALIGNMENT_SCALE) * ae3_logit_alignment_rows(expected_prob, pin_logits).to(
            dtype=rows.dtype
        )
    return rows


def ae_rollout_step_weight(
    effective_k: torch.Tensor,
    active_f: torch.Tensor,
    step: int,
) -> torch.Tensor:
    if not AE_TERMINAL_ONLY:
        return active_f
    terminal_f = (effective_k == int(step + 1)).to(dtype=active_f.dtype) * active_f
    return terminal_f * effective_k.to(dtype=active_f.dtype).clamp_min(1.0)


def ae_rollout_step_may_score(step: int, max_k: int) -> bool:
    if not AE_TERMINAL_ONLY:
        return True
    if mixed_rollout_enabled(int(max_k)):
        return int(step + 1) in set(rollout_values_for(int(max_k)))
    return int(step + 1) >= int(max_k)


def identity_world_position_rows(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
    pred_vec: torch.Tensor,
    cur_vec: torch.Tensor,
) -> torch.Tensor:
    cur_root_pos, cur_root_rot, _cur_yaw, _cur_heading = store.root_state(clip_ids, cur_idx)
    pred_root_pos, pred_root_rot = transition_output_root_state(store, clip_ids, cur_idx)
    pred_pose, _pred_raw_pose = tl.output_to_pose(pred_vec, store.prototype)
    cur_pose, _cur_raw_pose = tl.output_to_pose(cur_vec, store.prototype)
    pred_pos, _pred_rot, _pred_canon = tl.fk_from_pose(
        store.prototype, pred_root_pos, pred_root_rot, pred_pose, store.device
    )
    cur_pos, _cur_rot, _cur_canon = tl.fk_from_pose(store.prototype, cur_root_pos, cur_root_rot, cur_pose, store.device)
    return (pred_pos - cur_pos).square().sum(dim=-1).mean(dim=-1)


def root_still_gate_rows(
    store: SimpleClipStore,
    cur_root_pos: torch.Tensor,
    gate_next_root_pos: torch.Tensor,
    root_still_cutoff_mps: float,
) -> torch.Tensor:
    root_delta_xz = torch.stack(
        (gate_next_root_pos[:, 0] - cur_root_pos[:, 0], gate_next_root_pos[:, 2] - cur_root_pos[:, 2]),
        dim=-1,
    )
    root_speed = torch.linalg.vector_norm(root_delta_xz, dim=-1) * float(store.prototype.fps)
    cutoff = max(float(root_still_cutoff_mps), 1e-6)
    return torch.clamp(1.0 - root_speed / cutoff, min=0.0, max=1.0)


def alternating_feet_loss_terms(
    store: SimpleClipStore,
    cur_root_pos: torch.Tensor,
    gate_next_root_pos: torch.Tensor,
    cur_foot_pos: torch.Tensor,
    next_foot_pos: torch.Tensor,
    row_weight: torch.Tensor,
    active_f: torch.Tensor,
    loss_weight: float,
    root_still_cutoff_mps: float,
    include_diagnostics: bool = True,
    precomputed_root_still_gate: torch.Tensor | None = None,
    loss_weight_tensor: torch.Tensor | None = None,
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    zero = torch.zeros((), dtype=torch.float32, device=store.device)
    if float(loss_weight) == 0.0:
        names = ALTERNATING_FEET_TERM_NAMES if include_diagnostics else ALTERNATING_FEET_LOSS_TERM_NAMES
        return zero, {name: zero for name in names}

    foot_speeds = env.compact_foot_slide_speeds(cur_foot_pos, next_foot_pos, store.prototype.fps)
    overlap_speed = foot_speeds.amin(dim=-1)
    still_gate = (
        precomputed_root_still_gate
        if precomputed_root_still_gate is not None
        else root_still_gate_rows(store, cur_root_pos, gate_next_root_pos, root_still_cutoff_mps)
    )
    loss_rows = overlap_speed.square() * still_gate
    weights = row_weight * active_f
    scale = loss_weight_tensor if loss_weight_tensor is not None else float(loss_weight)
    weighted_loss = (loss_rows * weights).sum() * scale
    if not include_diagnostics:
        return weighted_loss, {"alternating_feet_weighted": weighted_loss}

    threshold = float(BOTH_FEET_MOVING_THRESHOLD_MPS)
    both_moving = ((foot_speeds[:, 0] > threshold) & (foot_speeds[:, 1] > threshold)).float()
    terms = {
        "alternating_feet_weighted": weighted_loss,
        "both_feet_moving_rate": (both_moving * still_gate * weights).sum(),
        "both_feet_overlap_mps": (overlap_speed * still_gate * weights).sum(),
        "root_still_gate": (still_gate * weights).sum(),
    }
    return weighted_loss, terms


def foot_lift_slide_loss_terms(
    store: SimpleClipStore,
    envelope: dict[str, torch.Tensor | dict[str, float | int | str]] | None,
    cur_root_pos: torch.Tensor,
    gate_next_root_pos: torch.Tensor,
    cur_foot_pos: torch.Tensor,
    next_foot_pos: torch.Tensor,
    next_foot_rot: torch.Tensor,
    clip_ids: torch.Tensor,
    cur_idx: torch.Tensor,
    row_weight: torch.Tensor,
    active_f: torch.Tensor,
    loss_weight: float,
    root_still_cutoff_mps: float,
    terminal_gate: torch.Tensor | None = None,
    include_diagnostics: bool = True,
    precomputed_foot_speeds: torch.Tensor | None = None,
    precomputed_heights: torch.Tensor | None = None,
    precomputed_height_lower_bound: torch.Tensor | None = None,
    precomputed_root_still_gate: torch.Tensor | None = None,
    loss_weight_tensor: torch.Tensor | None = None,
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    zero = torch.zeros((), dtype=torch.float32, device=store.device)
    if float(loss_weight) == 0.0 or envelope is None:
        names = FOOT_LIFT_SLIDE_TERM_NAMES if include_diagnostics else FOOT_LIFT_SLIDE_LOSS_TERM_NAMES
        return zero, {name: zero for name in names}

    if (
        precomputed_foot_speeds is not None
        and precomputed_heights is not None
        and precomputed_height_lower_bound is not None
    ):
        foot_speeds = precomputed_foot_speeds
        heights = precomputed_heights
        height_lower_bound = precomputed_height_lower_bound
    else:
        foot_speeds = env.compact_foot_slide_speeds(cur_foot_pos, next_foot_pos, store.prototype.fps)
        heights, height_lower_bound, _height_upper_bound = env.envelope_height_values_ik_state_rows(
            store,
            envelope,
            cur_foot_pos,
            next_foot_pos,
            next_foot_rot,
            clip_ids,
            cur_idx,
        )
    clearance = heights - height_lower_bound
    lift_fraction = torch.clamp(clearance / float(FOOT_LIFT_FULL_HEIGHT_M), min=0.0, max=1.0)
    allowed_speed = lift_fraction * float(FOOT_LIFT_FULL_SPEED_MPS)
    still_gate = (
        precomputed_root_still_gate
        if precomputed_root_still_gate is not None
        else root_still_gate_rows(store, cur_root_pos, gate_next_root_pos, root_still_cutoff_mps)
    )
    # Treat speed as the intent signal here; the lift term should raise a moving
    # foot, not win by braking the horizontal motion that the AE is asking for.
    excess = torch.relu(foot_speeds.detach() - allowed_speed)
    side_weights = row_weight[:, None] * active_f[:, None] * still_gate[:, None] * 0.5
    scale = loss_weight_tensor if loss_weight_tensor is not None else float(loss_weight)
    weighted_loss = (excess.square() * side_weights).sum() * scale

    threshold = float(BOTH_FEET_MOVING_THRESHOLD_MPS)
    grounded_gate = torch.clamp(1.0 - clearance / float(GROUNDED_FOOT_SLIDE_RELEASE_M), min=0.0, max=1.0)
    grounded_loss = (
        (foot_speeds.square() * grounded_gate * side_weights).sum()
        * scale
        * float(GROUNDED_FOOT_SLIDE_LOSS_SCALE)
    )

    deadzone_low = float(FOOT_SPEED_DEADZONE_LOW_MPS)
    deadzone_fast = max(float(FOOT_SPEED_DEADZONE_FAST_MPS), deadzone_low + 1e-6)
    deadzone = (
        torch.relu(foot_speeds - deadzone_low)
        * torch.relu(deadzone_fast - foot_speeds)
        / (deadzone_fast - deadzone_low)
    )
    deadzone_loss = (
        deadzone.square().mul(side_weights).sum()
        * scale
        * float(FOOT_SPEED_DEADZONE_LOSS_SCALE)
    )
    overspeed_cap = float(FOOT_SPEED_OVERSPEED_MAX_MPS)
    overspeed_excess = torch.relu(foot_speeds - overspeed_cap)
    overspeed_loss = (
        overspeed_excess.square().mul(side_weights).sum()
        * scale
        * float(FOOT_SPEED_OVERSPEED_LOSS_SCALE)
    )

    if terminal_gate is None:
        terminal_gate = torch.zeros_like(row_weight)
    terminal_weights = side_weights * terminal_gate[:, None]
    foot_points = next_foot_pos.reshape(next_foot_pos.shape[0], 2, 2, 3)
    cur_points = cur_foot_pos.reshape(cur_foot_pos.shape[0], 2, 2, 3)
    marker_dx = foot_points[..., 0] - cur_points[..., 0]
    marker_dz = foot_points[..., 2] - cur_points[..., 2]
    marker_dxz = torch.sqrt(marker_dx.square() + marker_dz.square() + 1e-12)
    terminal_horizontal = marker_dxz.amax(dim=-1) * float(store.prototype.fps)
    terminal_vertical = (foot_points[..., 1] - cur_points[..., 1]).abs().amax(dim=-1) * float(store.prototype.fps)
    terminal_loss = (
        (terminal_horizontal.square() + terminal_vertical.square()).mul(terminal_weights).sum()
        * scale
        * float(TERMINAL_FOOT_STILLNESS_LOSS_SCALE)
    )
    total = weighted_loss + grounded_loss + deadzone_loss + overspeed_loss + terminal_loss
    if not include_diagnostics:
        return total, {
            "foot_lift_slide_weighted": weighted_loss,
            "grounded_foot_slide_weighted": grounded_loss,
            "foot_speed_deadzone_weighted": deadzone_loss,
            "foot_speed_overspeed_weighted": overspeed_loss,
            "terminal_foot_stillness_weighted": terminal_loss,
        }

    violation = (excess > threshold).float()
    moving = (foot_speeds > threshold).float()
    moving_weights = moving * side_weights
    grounded_slide = (foot_speeds > threshold).float() * (grounded_gate > 0.5).float()
    grounded_weights = grounded_gate * side_weights
    deadzone_mask = ((foot_speeds > deadzone_low) & (foot_speeds < deadzone_fast)).float()
    overspeed_mask = (foot_speeds > overspeed_cap).float()
    terminal_moving = ((terminal_horizontal > deadzone_low) | (terminal_vertical > deadzone_low)).float()

    terms = {
        "foot_lift_slide_weighted": weighted_loss,
        "foot_lift_slide_violation_rate": (violation * side_weights).sum(),
        "foot_lift_slide_excess_mps": (excess * side_weights).sum(),
        "foot_lift_moving_rate": moving_weights.sum(),
        "foot_lift_moving_clearance_m": (clearance * moving_weights).sum(),
        "foot_lift_allowed_speed_mps": (allowed_speed * moving_weights).sum(),
        "foot_lift_root_still_gate": (still_gate * row_weight * active_f).sum(),
        "grounded_foot_slide_weighted": grounded_loss,
        "grounded_foot_slide_rate": (grounded_slide * side_weights).sum(),
        "grounded_foot_slide_mps": (foot_speeds * grounded_weights).sum(),
        "grounded_foot_clearance_m": (clearance * grounded_weights).sum(),
        "foot_speed_deadzone_weighted": deadzone_loss,
        "foot_speed_deadzone_rate": (deadzone_mask * side_weights).sum(),
        "foot_speed_deadzone_mps": (foot_speeds * deadzone_mask * side_weights).sum(),
        "foot_speed_overspeed_weighted": overspeed_loss,
        "foot_speed_overspeed_rate": (overspeed_mask * side_weights).sum(),
        "foot_speed_overspeed_mps": (foot_speeds * overspeed_mask * side_weights).sum(),
        "terminal_foot_stillness_weighted": terminal_loss,
        "terminal_foot_horizontal_mps": (terminal_horizontal * terminal_weights).sum(),
        "terminal_foot_vertical_mps": (terminal_vertical * terminal_weights).sum(),
        "terminal_foot_stillness_rate": (terminal_moving * terminal_weights).sum(),
    }
    return total, terms


def ik_lower_lengths_from_vec(store: SimpleClipStore, vec: torch.Tensor) -> torch.Tensor:
    if not store.prototype.ik_limb_specs:
        return torch.empty((vec.shape[0], 0), dtype=vec.dtype, device=store.device)
    b = int(vec.shape[0])
    cursor = 0
    pelvis_pos = vec[:, cursor : cursor + 3]
    cursor += 3
    pelvis_rot = tl.rotation_6d_to_matrix(vec[:, cursor : cursor + 6])
    cursor += 6
    core_dim = store.Jcore * 6
    core_rot6 = vec[:, cursor : cursor + core_dim].reshape(b, store.Jcore, 6)
    cursor += core_dim
    payload = vec[:, cursor : cursor + store.ik_payload_dim]
    base_root = _ik_base_positions_root(store, pelvis_pos, pelvis_rot, core_rot6)

    end_parts: list[torch.Tensor] = []
    start_rot_parts: list[torch.Tensor] = []
    for spec in store.ik_payload_slices:
        pos_slice = spec["pos"]
        start_rot_slice = spec["start_rot6"]
        assert isinstance(pos_slice, slice)
        assert isinstance(start_rot_slice, slice)
        end_parts.append(payload[:, pos_slice])
        start_rot_parts.append(payload[:, start_rot_slice])
    end_root = torch.stack(end_parts, dim=1)
    start_rot = tl.rotation_6d_to_matrix(torch.stack(start_rot_parts, dim=1).reshape(-1, 6)).reshape(b, -1, 3, 3)
    upper_offsets = store.ik_mid_offsets.to(dtype=vec.dtype)
    mid_root = base_root + torch.matmul(upper_offsets.reshape(1, -1, 1, 3), start_rot).squeeze(-2)
    return torch.linalg.vector_norm(end_root - mid_root, dim=-1)


def ik_lower_length_loss_terms(
    store: SimpleClipStore,
    pred_vec: torch.Tensor,
    row_weight: torch.Tensor,
    active_f: torch.Tensor,
    include_diagnostics: bool = True,
    loss_weight: float | None = None,
    loss_weight_tensor: torch.Tensor | None = None,
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    zero = torch.zeros((), dtype=torch.float32, device=store.device)
    effective_weight = float(IK_LOWER_LENGTH_LOSS_WEIGHT if loss_weight is None else loss_weight)
    if effective_weight == 0.0 or not store.prototype.ik_limb_specs:
        names = IK_LOWER_LENGTH_TERM_NAMES if include_diagnostics else IK_LOWER_LENGTH_LOSS_TERM_NAMES
        return zero, {name: zero for name in names}

    lower_len = ik_lower_lengths_from_vec(store, pred_vec)
    rest = store.ik_limb_lengths[:, 1].to(dtype=pred_vec.dtype).reshape(1, -1)
    tolerance = store.ik_lower_length_tolerance_m.to(dtype=pred_vec.dtype).reshape(1, -1)
    excess = torch.relu((lower_len - rest).abs() - tolerance)
    limb_weights = row_weight[:, None] * active_f[:, None] / float(max(1, lower_len.shape[1]))
    scale = loss_weight_tensor if loss_weight_tensor is not None else effective_weight
    weighted_loss = (excess.square() * limb_weights).sum() * scale
    if not include_diagnostics:
        return weighted_loss, {"ik_lower_length_weighted": weighted_loss}

    leg_excess = excess.index_select(1, store.ik_leg_indices_tensor) if store.ik_leg_count else excess[:, :0]
    arm_excess = excess.index_select(1, store.ik_arm_indices_tensor) if store.ik_arm_count else excess[:, :0]
    leg_weights = row_weight[:, None] * active_f[:, None] / float(max(1, int(store.ik_leg_count)))
    arm_weights = row_weight[:, None] * active_f[:, None] / float(max(1, int(store.ik_arm_count)))
    terms = {
        "ik_lower_length_weighted": weighted_loss,
        "leg_lower_length_excess_m": (leg_excess * leg_weights).sum() if leg_excess.numel() else zero,
        "leg_lower_length_bad_rate": ((leg_excess > 0.0).float() * leg_weights).sum() if leg_excess.numel() else zero,
        "leg_lower_length_max_excess_m": (
            leg_excess.amax(dim=-1).mul(row_weight * active_f).sum() if leg_excess.numel() else zero
        ),
        "arm_lower_length_excess_m": (arm_excess * arm_weights).sum() if arm_excess.numel() else zero,
        "arm_lower_length_bad_rate": ((arm_excess > 0.0).float() * arm_weights).sum() if arm_excess.numel() else zero,
    }
    return weighted_loss, terms


def pure_ae_rollout_loss(
    model: torch.nn.Module,
    ae: SimpleAutoencoder,
    mean: torch.Tensor,
    std: torch.Tensor,
    store: SimpleClipStore,
    rollout_k: int,
    batch_size: int,
    start_pools: dict[int, StartPool],
    full_window_start_pools: dict[int, StartPool] | None,
    rl_cfg: RLLossConfig,
    ae_loss_weight: float,
    envelope: dict[str, torch.Tensor | dict[str, float | int | str]] | None = None,
    linear_slide_weight: float = 0.0,
    angular_slide_weight: float = 0.0,
    foot_height_weight: float = 0.0,
    alternating_feet_weight: float = 0.0,
    foot_lift_slide_weight: float = 0.0,
    pinned_foot_height_weight: float = 0.0,
    idle_foot_flatness_weight: float = 0.0,
    slide_tentative_loss_weight: float = 0.0,
    forced_idle_batch_fraction: float | None = None,
    alternating_root_cutoff_mps: float = 1.0,
    identity_loss_weight: float = 0.0,
    identity_maxabs_weight: float = 0.0,
    identity_world_pos_weight: float = 0.0,
    identity_pelvis_pos_weight: float = 0.0,
    init_store: SimpleClipStore | None = None,
    init_start_pool: StartPool | None = None,
    init_noise_amount: float = DEFAULT_INIT_NOISE_AMOUNT,
    init_noise_clean_fraction: float = DEFAULT_INIT_NOISE_CLEAN_FRACTION,
    init_pose_noise_batch: InitPoseNoiseBatch | None = None,
    extra_ae: SimpleAutoencoder | None = None,
    extra_mean: torch.Tensor | None = None,
    extra_std: torch.Tensor | None = None,
    extra_ae_loss_weight: float = 0.0,
    ae5: SimpleAutoencoder | None = None,
    ae5_mean: torch.Tensor | None = None,
    ae5_std: torch.Tensor | None = None,
    ae5_loss_weight: float = 0.0,
    ae5_reserved_row_start: int = 0,
    ae5_reserved_rows: int | None = None,
    ae6: torch.nn.Module | None = None,
    ae6_mean: torch.Tensor | None = None,
    ae6_std: torch.Tensor | None = None,
    ae6_loss_weight: float = 0.0,
    ae2: torch.nn.Module | None = None,
    ae2_mean: torch.Tensor | None = None,
    ae2_std: torch.Tensor | None = None,
    ae2_loss_weight: float = 0.0,
    ae2_window_weights: torch.Tensor | None = None,
    ae3: torch.nn.Module | None = None,
    ae3_mean: torch.Tensor | None = None,
    ae3_std: torch.Tensor | None = None,
    ae3_pos_weight: torch.Tensor | None = None,
    ae3_loss_weight: float = 0.0,
    pin_logit_gap_loss_weight: float = 0.0,
    inertia_acceleration_loss_weight: float = 0.0,
    root_accel_pin_loss_ratio: float = 0.0,
    leg_crossing_capsule_loss_weight: float = 0.0,
    ae4: object | None = None,
    ae4_input_mean: torch.Tensor | None = None,
    ae4_input_std: torch.Tensor | None = None,
    ae4_target_mean: torch.Tensor | None = None,
    ae4_target_std: torch.Tensor | None = None,
    ae4_loss_weight: float = 0.0,
    ae4_bank_pin_loss_weight: float = 0.0,
    dedicated_real_start_pools: dict[int, StartPool] | None = None,
    dedicated_real_rows: int = 0,
    dedicated_real_loss_multiplier: float = DEFAULT_DEDICATED_REAL_LOSS_MULTIPLIER,
    periodic_reserved_rows: int = 0,
    debug_capture: dict[str, torch.Tensor] | None = None,
) -> ControllerLossResult:
    max_k = max(1, int(rollout_k))
    original_batch_size = max(1, int(batch_size))
    effective_k = sample_effective_rollout_k(original_batch_size, max_k, store.device)
    clip_ids, starts = sample_rollout_rows(
        start_pools,
        effective_k,
        full_window_start_pools=full_window_start_pools,
        full_window_rows=None,
        dedicated_real_start_pools=dedicated_real_start_pools,
        dedicated_real_rows=dedicated_real_rows,
    )
    if init_pose_noise_batch is None and init_noise_enabled(init_noise_clean_fraction):
        rng_snapshot = clone_rng_state(store.device)
        try:
            init_pose_noise_batch = sample_fixed_init_pose_noise_batch(
                store,
                original_batch_size,
                init_noise_clean_fraction,
                device=store.device,
                dtype=torch.float32,
            )
        finally:
            restore_rng_state(rng_snapshot, store.device)
    cur_idx = starts
    if init_store is not None and init_start_pool is not None:
        init_clip_ids, init_starts = sample_from_pool(init_start_pool, original_batch_size)
        init_prev_starts, init_cur_starts = rollout_init_context_indices(init_starts)
        prev_vec, prev_pelvis, prev_payload = target_state(init_store, init_clip_ids, init_prev_starts)
        cur_vec, cur_pelvis, cur_payload = target_state(init_store, init_clip_ids, init_cur_starts)
        if isinstance(getattr(store, "synthetic", None), torch.Tensor):
            synth_rows = store.synthetic.index_select(0, clip_ids).reshape(-1, 1)
            synth_prev_vec, synth_prev_pelvis, synth_prev_payload = target_state(store, clip_ids, cur_idx - 1)
            synth_cur_vec, synth_cur_pelvis, synth_cur_payload = target_state(store, clip_ids, cur_idx)
            prev_vec = torch.where(synth_rows, synth_prev_vec, prev_vec)
            prev_pelvis = torch.where(synth_rows, synth_prev_pelvis, prev_pelvis)
            prev_payload = torch.where(synth_rows, synth_prev_payload, prev_payload)
            cur_vec = torch.where(synth_rows, synth_cur_vec, cur_vec)
            cur_pelvis = torch.where(synth_rows, synth_cur_pelvis, cur_pelvis)
            cur_payload = torch.where(synth_rows, synth_cur_payload, cur_payload)
    else:
        prev_vec, prev_pelvis, prev_payload = target_state(store, clip_ids, cur_idx - 1)
        cur_vec, cur_pelvis, cur_payload = target_state(store, clip_ids, cur_idx)
    if init_pose_noise_batch is not None:
        prev_vec = apply_init_pose_noise_batch(store, prev_vec, init_pose_noise_batch)
        cur_vec = apply_init_pose_noise_batch(store, cur_vec, init_pose_noise_batch)
        prev_pelvis = prev_vec[:, :3]
        cur_pelvis = cur_vec[:, :3]
        vec_payload_slice = payload_slice(store)
        prev_payload = prev_vec[:, vec_payload_slice]
        cur_payload = cur_vec[:, vec_payload_slice]
    input_dim, output_dim = tl.make_batch_dims(store.prototype, store.cfg)
    ae_frames = ae_window_frames_from_dims(mean, input_dim, output_dim)
    if extra_ae is not None and extra_mean is not None:
        extra_frames = ae_window_frames_from_dims(extra_mean, input_dim, output_dim)
        if extra_frames != ae_frames:
            raise ValueError(f"Extra AE window_frames={extra_frames} does not match primary AE window_frames={ae_frames}")
    ae5_enabled = ae5 is not None and ae5_mean is not None and ae5_std is not None and float(ae5_loss_weight) != 0.0
    ae5_motion_enabled = ae5_enabled and is_ik_motion_window_ae(ae5)
    ae5_frames = (
        ik_motion_ae2_window_shape(ae5)[0]
        if ae5_motion_enabled and ae5 is not None
        else (ae_window_frames_from_dims(ae5_mean, input_dim, output_dim) if ae5_mean is not None else 1)
    )
    ae5_context = None
    ae_context = (
        duplicated_init_ae_context(store, clip_ids, cur_idx, cur_vec, cur_pelvis, cur_payload, ae_frames)
        if init_store is not None
        else initial_ae_context(store, clip_ids, cur_idx, ae_frames)
    )
    if ae5_enabled and not ae5_motion_enabled:
        ae5_context = (
            duplicated_init_ae_context(store, clip_ids, cur_idx, cur_vec, cur_pelvis, cur_payload, ae5_frames)
            if init_store is not None
            else initial_ae_context(store, clip_ids, cur_idx, ae5_frames)
        )
    ae6_enabled = ae6 is not None and ae6_mean is not None and ae6_std is not None and float(ae6_loss_weight) != 0.0
    ae6_frames = ae_window_frames_from_dims(ae6_mean, input_dim, output_dim) if ae6_mean is not None else 1
    ae_required_context_frames = max(
        int(ae_frames),
        int(ae5_frames) if ae5_enabled else 1,
        int(ae6_frames) if ae6_enabled else 1,
    )
    ae2_enabled = ae2 is not None and ae2_mean is not None and ae2_std is not None and float(ae2_loss_weight) != 0.0
    ae3_enabled = ae3 is not None and ae3_mean is not None and ae3_std is not None and float(ae3_loss_weight) != 0.0
    pin_logit_gap_enabled = float(pin_logit_gap_loss_weight) != 0.0
    inertia_acceleration_enabled = float(inertia_acceleration_loss_weight) != 0.0
    root_accel_pin_enabled = float(root_accel_pin_loss_ratio) != 0.0 and float(ae_loss_weight) != 0.0
    leg_crossing_capsule_enabled = float(leg_crossing_capsule_loss_weight) != 0.0
    ae4_enabled = (
        ae4 is not None
        and ae4_input_mean is not None
        and ae4_input_std is not None
        and ae4_target_mean is not None
        and ae4_target_std is not None
        and (float(ae4_loss_weight) != 0.0 or float(ae4_bank_pin_loss_weight) != 0.0)
    )
    ae4_bank_pin_enabled = (
        ae4_enabled and ae4_uses_pose_bank_projector(ae4) and float(ae4_bank_pin_loss_weight) != 0.0
    )
    ae2_window_frames = 1
    ae2_context: torch.Tensor | None = None
    if ae2_enabled:
        ae2_window_frames, ae2_frame_dim = ik_motion_ae2_window_shape(ae2)
        ae2_context = torch.zeros(
            (cur_vec.shape[0], max(0, ae2_window_frames - 1), ae2_frame_dim),
            dtype=cur_vec.dtype,
            device=store.device,
        )
        if ae2_window_weights is None:
            ae2_frame_weights = ik_motion_ae2_frame_feature_weights(
                store,
                ae2_frame_dim,
                ae2_loss_weight,
                dtype=cur_vec.dtype,
                device=store.device,
            )
            ae2_window_weights = ae2_frame_weights.repeat(ae2_window_frames)
    ae5_motion_row_count = (
        int(original_batch_size)
        if ae5_reserved_rows is None
        else max(0, min(int(original_batch_size), int(ae5_reserved_rows)))
    )
    ae5_motion_row_start = max(0, min(int(original_batch_size), int(ae5_reserved_row_start)))
    ae5_motion_row_count = max(0, min(int(original_batch_size) - ae5_motion_row_start, int(ae5_motion_row_count)))
    ae5_motion_context: torch.Tensor | None = None
    ae5_motion_context_next: torch.Tensor | None = None
    if ae5_motion_enabled and ae5 is not None:
        ae5_frames, ae5_frame_dim = ik_motion_ae2_window_shape(ae5)
        ae5_motion_context = torch.zeros(
            (ae5_motion_row_count, max(0, ae5_frames - 1), ae5_frame_dim),
            dtype=cur_vec.dtype,
            device=store.device,
        )
    row_weight = (1.0 / effective_k.float()) / float(original_batch_size)
    row_weight = apply_dedicated_real_loss_multiplier(
        row_weight,
        dedicated_real_rows,
        dedicated_real_loss_multiplier,
    )
    total_loss = torch.zeros((), dtype=torch.float32, device=store.device)
    ae_raw_total = torch.zeros_like(total_loss)
    ae_total = torch.zeros_like(total_loss)
    ae_pose_total = torch.zeros_like(total_loss)
    ae_velocity_total = torch.zeros_like(total_loss)
    gt_mse_raw_total = torch.zeros_like(total_loss)
    gt_mse_weighted_total = torch.zeros_like(total_loss)
    gt_mse_pos_total = torch.zeros_like(total_loss)
    gt_mse_rot_total = torch.zeros_like(total_loss)
    gt_mse_linvel_total = torch.zeros_like(total_loss)
    gt_mse_angvel_total = torch.zeros_like(total_loss)
    ae5_score_total = torch.zeros_like(total_loss)
    ae5_weighted_total = torch.zeros_like(total_loss)
    ae5_active_rate_total = torch.zeros_like(total_loss)
    ae6_score_total = torch.zeros_like(total_loss)
    ae6_weighted_total = torch.zeros_like(total_loss)
    ae6_mae_total = torch.zeros_like(total_loss)
    ae6_acc_total = torch.zeros_like(total_loss)
    ae2_weighted_total = torch.zeros_like(total_loss)
    ae3_weighted_total = torch.zeros_like(total_loss)
    pin_logit_gap_total = torch.zeros_like(total_loss)
    pin_logit_gap_raw_total = torch.zeros_like(total_loss)
    pin_logit_gap_bad_rate_total = torch.zeros_like(total_loss)
    inertia_acceleration_total = torch.zeros_like(total_loss)
    inertia_acceleration_raw_total = torch.zeros_like(total_loss)
    inertia_linear_acceleration_raw_total = torch.zeros_like(total_loss)
    inertia_angular_acceleration_raw_total = torch.zeros_like(total_loss)
    inertia_acceleration_bad_rate_total = torch.zeros_like(total_loss)
    root_accel_pin_total = torch.zeros_like(total_loss)
    root_accel_pin_raw_total = torch.zeros_like(total_loss)
    root_accel_pin_scale_total = torch.zeros_like(total_loss)
    root_accel_pin_accel_total = torch.zeros_like(total_loss)
    root_accel_pin_active_rate_total = torch.zeros_like(total_loss)
    root_accel_pin_bad_rate_total = torch.zeros_like(total_loss)
    root_accel_pin_max_prob_total = torch.zeros_like(total_loss)
    root_accel_pin_height_total = torch.zeros_like(total_loss)
    ae4_score_total = torch.zeros_like(total_loss)
    ae4_hinge_total = torch.zeros_like(total_loss)
    ae4_weighted_total = torch.zeros_like(total_loss)
    ae4_bank_pin_total = torch.zeros_like(total_loss)
    ae4_bank_pin_raw_total = torch.zeros_like(total_loss)
    ae4_bank_pin_root_scale_total = torch.zeros_like(total_loss)
    pinned_foot_height_total = torch.zeros_like(total_loss)
    pinned_foot_height_raw_total = torch.zeros_like(total_loss)
    pinned_foot_height_max_total = torch.zeros_like(total_loss)
    idle_foot_flatness_total = torch.zeros_like(total_loss)
    idle_foot_flatness_raw_total = torch.zeros_like(total_loss)
    idle_foot_flatness_max_total = torch.zeros_like(total_loss)
    leg_crossing_capsule_total = torch.zeros_like(total_loss)
    leg_crossing_capsule_raw_total = torch.zeros_like(total_loss)
    leg_crossing_capsule_rate_total = torch.zeros_like(total_loss)
    identity_total = torch.zeros_like(total_loss)
    identity_maxabs_total = torch.zeros_like(total_loss)
    identity_world_pos_total = torch.zeros_like(total_loss)
    identity_pelvis_pos_total = torch.zeros_like(total_loss)
    foot_unpin_penalty_total = torch.zeros_like(total_loss)
    foot_unpin_soft_rate_total = torch.zeros_like(total_loss)
    pinned_foot_intent_total = torch.zeros_like(total_loss)
    pinned_foot_intent_raw_total = torch.zeros_like(total_loss)
    pinned_foot_intent_mps_total = torch.zeros_like(total_loss)
    slide_tentative_total = torch.zeros_like(total_loss)
    slide_tentative_raw_total = torch.zeros_like(total_loss)
    slide_tentative_pin_rate_total = torch.zeros_like(total_loss)
    pin_behavior_terms = {name: torch.zeros_like(total_loss) for name in PIN_BEHAVIOR_TERM_NAMES}
    foot_contact_terms = {name: torch.zeros_like(total_loss) for name in (FOOT_CONTACT_HEIGHT_LOSS_TERM_NAME, *FOOT_CONTACT_HEIGHT_METRIC_NAMES)}
    rl_terms = {name: torch.zeros_like(total_loss) for name in RL_TERM_NAMES}
    envelope_terms = {name: torch.zeros_like(total_loss) for name in ENVELOPE_TERM_NAMES}
    alternating_terms = {name: torch.zeros_like(total_loss) for name in ALTERNATING_FEET_TERM_NAMES}
    foot_lift_terms = {name: torch.zeros_like(total_loss) for name in FOOT_LIFT_SLIDE_TERM_NAMES}
    anatomy_terms = {name: torch.zeros_like(total_loss) for name in IK_LOWER_LENGTH_TERM_NAMES}
    has_envelope = envelope is not None and envelope_loss_enabled(linear_slide_weight, angular_slide_weight, foot_height_weight)
    has_alternating = alternating_feet_loss_enabled(alternating_feet_weight)
    has_foot_lift = envelope is not None and foot_lift_slide_loss_enabled(foot_lift_slide_weight)
    has_anatomy = ik_lower_length_loss_enabled()
    prev_pin_mask: torch.Tensor | None = None
    prev_inertia_linear_delta: torch.Tensor | None = None
    prev_inertia_angular_delta: torch.Tensor | None = None
    if inertia_acceleration_enabled:
        prev_inertia_linear_delta, prev_inertia_angular_delta = inertia_transition_delta_rows(store, prev_vec, cur_vec)

    for step in range(max_k):
        inp = build_controller_input(
            store, clip_ids, cur_idx, prev_vec, cur_vec, prev_pelvis, cur_pelvis, prev_payload, cur_payload
        )
        raw_pred = model_raw_output(model, inp, cur_vec, store)
        raw_clean_vec = None
        if float(slide_tentative_loss_weight) != 0.0:
            pred_vec, raw_clean_vec = clean_output_vector_pair(raw_pred, store, cur_vec, prev_vec)
        else:
            pred_vec = clean_output_vector(raw_pred, store, cur_vec, prev_vec)
        cleaned_foot_heights = foot_roll_lowest_heights_from_vec(store, pred_vec)
        pin_logits = foot_pin_logits_from_raw(raw_pred, store)
        stationary_both_pin_amount = 1.0 - root_motion_activity_rows(store, clip_ids, cur_idx, init_store)
        foot_unpin_rows = soft_any_foot_unpin_rows(pin_logits)
        foot_unpin_penalty = (foot_unpin_rows * row_weight).sum() * float(FOOT_UNPIN_PENALTY_WEIGHT)
        foot_unpin_penalty_total = foot_unpin_penalty_total + foot_unpin_penalty
        foot_unpin_soft_rate_total = foot_unpin_soft_rate_total + (foot_unpin_rows.detach() * row_weight).sum()
        pinned_foot_intent_loss = torch.zeros_like(total_loss)
        if float(PINNED_FOOT_INTENT_PENALTY_WEIGHT) != 0.0:
            raw_clean_vec = clean_output_vector(raw_pred, store, cur_vec, prev_vec)
            cur_root_pos, cur_root_rot, _cur_yaw, _cur_heading = store.root_state(clip_ids, cur_idx)
            output_root_pos, output_root_rot = transition_output_root_state(store, clip_ids, cur_idx)
            intent_rows, intent_mps_rows = pinned_foot_intent_motion_rows(
                store,
                cur_root_pos,
                cur_root_rot,
                output_root_pos,
                output_root_rot,
                cur_vec,
                raw_clean_vec,
                pin_logits,
            )
            intent_raw = (intent_rows * row_weight).sum()
            pinned_foot_intent_loss = intent_raw * float(PINNED_FOOT_INTENT_PENALTY_WEIGHT)
            pinned_foot_intent_total = pinned_foot_intent_total + pinned_foot_intent_loss
            pinned_foot_intent_raw_total = pinned_foot_intent_raw_total + intent_raw.detach()
            pinned_foot_intent_mps_total = pinned_foot_intent_mps_total + (intent_mps_rows * row_weight).sum().detach()
        pinned_foot_height_loss = torch.zeros_like(total_loss)
        if float(pinned_foot_height_weight) != 0.0:
            smooth_heights = foot_roll_smooth_lowest_heights_from_vec(store, pred_vec)
            height_loss_heights = cleaned_foot_heights.detach() + smooth_heights - smooth_heights.detach()
            height_rows, height_raw_rows = pinned_foot_height_loss_rows(height_loss_heights, pin_logits)
            height_scale = float(pinned_foot_height_weight)
            pinned_foot_height_loss = (height_rows * row_weight).sum() * height_scale
            pinned_foot_height_total = pinned_foot_height_total + pinned_foot_height_loss
            pinned_foot_height_raw_total = pinned_foot_height_raw_total + (
                height_raw_rows.detach() * row_weight
            ).sum()
            pinned_foot_height_max_total = torch.maximum(
                pinned_foot_height_max_total,
                pinned_foot_height_max_m_rows(cleaned_foot_heights, pin_logits).detach().amax(),
            )
        idle_foot_flatness_loss = torch.zeros_like(total_loss)
        if float(idle_foot_flatness_weight) != 0.0:
            flatness_rows, flatness_raw_rows = idle_foot_flatness_loss_rows(store, clip_ids, pred_vec, pin_logits)
            flatness_batch_scale = idle_foot_flatness_batch_scale(original_batch_size)
            flatness_scale = float(idle_foot_flatness_weight) * flatness_batch_scale
            idle_foot_flatness_loss = (flatness_rows * row_weight).sum() * flatness_scale
            idle_foot_flatness_total = idle_foot_flatness_total + idle_foot_flatness_loss
            idle_foot_flatness_raw_total = idle_foot_flatness_raw_total + (
                flatness_raw_rows.detach() * row_weight * flatness_batch_scale
            ).sum()
            idle_foot_flatness_max_total = torch.maximum(
                idle_foot_flatness_max_total,
                flatness_raw_rows.detach().amax(),
            )
        pin_dim = int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)
        previous_pin_mask_for_step = prev_pin_mask
        pin_mask = None
        if int(cleaned_foot_heights.shape[-1]) >= pin_dim:
            pin_mask = foot_pin_mask_from_heights_and_logits(cleaned_foot_heights, pin_logits)
            pin_count = pin_mask.to(dtype=row_weight.dtype).sum(dim=-1)
            double_rows = (pin_count >= 2.0).to(dtype=row_weight.dtype)
            single_rows = (pin_count == 1.0).to(dtype=row_weight.dtype)
            min_height_rows = cleaned_foot_heights[..., :pin_dim].amin(dim=-1)
            any_pinned_rows = (pin_count >= 1.0).to(dtype=row_weight.dtype)
            if previous_pin_mask_for_step is None:
                switch_rows = torch.zeros_like(row_weight)
                unpin_after_double_rows = torch.zeros_like(row_weight)
            else:
                prev_pin_count = previous_pin_mask_for_step.to(dtype=row_weight.dtype).sum(dim=-1)
                switch_rows = (pin_mask != previous_pin_mask_for_step).any(dim=-1).to(dtype=row_weight.dtype)
                unpin_after_double_rows = (
                    (prev_pin_count >= 2.0) & (pin_count < 2.0)
                ).to(dtype=row_weight.dtype)
            pin_behavior_terms["pin_double_rate"] = pin_behavior_terms["pin_double_rate"] + (
                double_rows * row_weight
            ).sum()
            pin_behavior_terms["pin_single_rate"] = pin_behavior_terms["pin_single_rate"] + (
                single_rows * row_weight
            ).sum()
            pin_behavior_terms["pin_switch_rate"] = pin_behavior_terms["pin_switch_rate"] + (
                switch_rows * row_weight
            ).sum()
            pin_behavior_terms["pin_unpin_after_double_rate"] = (
                pin_behavior_terms["pin_unpin_after_double_rate"] + (unpin_after_double_rows * row_weight).sum()
            )
            pin_behavior_terms["pin_stationary_amount"] = pin_behavior_terms["pin_stationary_amount"] + (
                stationary_both_pin_amount.detach() * row_weight
            ).sum()
            foot_contact_terms["foot_contact_min_height_m"] = foot_contact_terms["foot_contact_min_height_m"] + (
                min_height_rows.detach() * row_weight
            ).sum()
            foot_contact_terms["foot_contact_any_pinned_rate"] = foot_contact_terms["foot_contact_any_pinned_rate"] + (
                any_pinned_rows * row_weight
            ).sum()
            foot_contact_terms["foot_contact_left_pinned_rate"] = foot_contact_terms["foot_contact_left_pinned_rate"] + (
                pin_mask[:, 0].to(dtype=row_weight.dtype) * row_weight
            ).sum()
            foot_contact_terms["foot_contact_right_pinned_rate"] = foot_contact_terms["foot_contact_right_pinned_rate"] + (
                pin_mask[:, 1].to(dtype=row_weight.dtype) * row_weight
            ).sum()
            prev_pin_mask = pin_mask
        slide_tentative_loss = torch.zeros_like(total_loss)
        if float(slide_tentative_loss_weight) != 0.0:
            assert raw_clean_vec is not None
            if pin_mask is None:
                pin_mask = foot_pin_mask_from_logits(pin_logits)
            slide_rows, slide_pin_rate_rows = slide_tentative_projection_correction_rows(
                store,
                raw_clean_vec,
                pred_vec,
                pin_mask,
            )
            slide_scale = float(slide_tentative_loss_weight)
            slide_tentative_loss = (slide_rows * row_weight).sum() * slide_scale
            slide_tentative_total = slide_tentative_total + slide_tentative_loss
            slide_tentative_raw_total = slide_tentative_raw_total + (slide_rows.detach() * row_weight).sum()
            slide_tentative_pin_rate_total = slide_tentative_pin_rate_total + (
                slide_pin_rate_rows.detach() * row_weight
            ).sum()
        contact_height_rows = foot_contact_min_height_loss_rows(cleaned_foot_heights)
        contact_height_loss = (contact_height_rows * row_weight).sum()
        foot_contact_terms[FOOT_CONTACT_HEIGHT_LOSS_TERM_NAME] = foot_contact_terms[FOOT_CONTACT_HEIGHT_LOSS_TERM_NAME] + contact_height_loss
        raw_feature = torch.cat((inp, pred_vec), dim=-1)
        cur_output_vec = current_state_as_transition_output(store, clip_ids, cur_idx, cur_vec)
        active = torch.ones_like(row_weight, dtype=torch.bool)
        active_f = torch.ones_like(row_weight)
        ae_step_weight = ae_rollout_step_weight(effective_k, active_f, step)
        ae_metric_weight = row_weight * ae_step_weight
        ae_step_scores = ae_rollout_step_may_score(step, max_k)
        ae_loss = torch.zeros_like(total_loss)
        ae_pose_loss = torch.zeros_like(total_loss)
        ae_velocity_loss = torch.zeros_like(total_loss)
        ae_rows_for_root_accel_scale: torch.Tensor | None = None
        if ae_step_scores and float(ae_loss_weight) != 0.0:
            ae_scale = float(ae_loss_weight)
            gt_mse_rows: torch.Tensor | None = None
            if primary_loss_uses_gt_mse():
                target_vec = transition_target_output(store, clip_ids, cur_idx)
                gt_cur_vec, _gt_cur_pelvis, _gt_cur_payload = target_state(store, clip_ids, cur_idx)
                gt_cur_output_vec = current_state_as_transition_output(store, clip_ids, cur_idx, gt_cur_vec)
                gt_mse_rows, gt_mse_terms = gt_mse_tracking_loss_rows(
                    store,
                    cur_output_vec,
                    pred_vec,
                    target_vec,
                    gt_cur_output_vec,
                )
                gt_mse_scope = gt_mse_row_scope_mask(row_weight, dedicated_real_rows, periodic_reserved_rows)
                gt_mse_metric_weight = ae_metric_weight * gt_mse_scope
                gt_mse_loss = (gt_mse_rows * gt_mse_metric_weight).sum() * ae_scale
                gt_mse_weighted_total = gt_mse_weighted_total + gt_mse_loss
                gt_mse_raw_total = gt_mse_raw_total + (gt_mse_terms[GT_MSE_RAW_TERM_NAME].detach() * gt_mse_metric_weight).sum()
                gt_mse_pos_total = gt_mse_pos_total + (gt_mse_terms[GT_MSE_POS_TERM_NAME].detach() * gt_mse_metric_weight).sum()
                gt_mse_rot_total = gt_mse_rot_total + (gt_mse_terms[GT_MSE_ROT_TERM_NAME].detach() * gt_mse_metric_weight).sum()
                gt_mse_linvel_total = gt_mse_linvel_total + (gt_mse_terms[GT_MSE_LINVEL_TERM_NAME].detach() * gt_mse_metric_weight).sum()
                gt_mse_angvel_total = gt_mse_angvel_total + (gt_mse_terms[GT_MSE_ANGVEL_TERM_NAME].detach() * gt_mse_metric_weight).sum()
                if PRIMARY_LOSS_MODE == PRIMARY_LOSS_MODE_GT_MSE:
                    ae_rows_for_root_accel_scale = gt_mse_rows
                    ae_raw_total = ae_raw_total + (gt_mse_rows * gt_mse_metric_weight).sum()
                    ae_pose_loss = gt_mse_loss
                    ae_loss = ae_loss + ae_pose_loss
                else:
                    ae_loss = ae_loss + gt_mse_loss
            if primary_loss_uses_ae1():
                ae_rows = ae_score_rows(ae, mean, std, inp, pred_vec, ae_context, store)
                ae_rows_for_root_accel_scale = ae_rows
                ae_raw_total = ae_raw_total + (ae_rows * ae_metric_weight).sum()
                ae_pose_loss = (ae_rows * ae_metric_weight).sum() * ae_scale
                ae_loss = ae_loss + ae_pose_loss
        if (
            ae_step_scores
            and extra_ae is not None
            and extra_mean is not None
            and extra_std is not None
            and float(extra_ae_loss_weight) != 0.0
        ):
            extra_rows = ae_score_rows(extra_ae, extra_mean, extra_std, inp, pred_vec, ae_context, store)
            ae_velocity_loss = (
                extra_rows * ae_metric_weight
            ).sum() * float(extra_ae_loss_weight)
            ae_loss = ae_loss + ae_velocity_loss
        ae6_loss = torch.zeros_like(total_loss)
        if (
            ae_step_scores
            and ae6 is not None
            and ae6_mean is not None
            and ae6_std is not None
            and float(ae6_loss_weight) != 0.0
        ):
            ae6_rows, _ae6_bce_rows, ae6_mae_rows, ae6_acc_rows = ae6_contact_loss_rows(
                ae6,
                ae6_mean,
                ae6_std,
                inp,
                pred_vec,
                pin_logits,
                ae_context,
            )
            ae6_scale = float(ae6_loss_weight)
            ae6_scope = ae6_row_scope_mask(row_weight, dedicated_real_rows, periodic_reserved_rows)
            ae6_metric_weight = ae_metric_weight * ae6_scope
            ae6_loss = (ae6_rows * ae6_metric_weight).sum() * ae6_scale
            ae6_score_total = ae6_score_total + (ae6_rows.detach() * ae6_metric_weight).sum()
            ae6_weighted_total = ae6_weighted_total + ae6_loss
            ae6_mae_total = ae6_mae_total + (ae6_mae_rows.detach() * ae6_metric_weight).sum()
            ae6_acc_total = ae6_acc_total + (ae6_acc_rows.detach() * ae6_metric_weight).sum()
            ae_loss = ae_loss + ae6_loss
        ae2_loss = torch.zeros_like(total_loss)
        ae2_context_next = ae2_context
        if ae2_enabled and ae2_context is not None and ae2 is not None and ae2_mean is not None and ae2_std is not None:
            ae2_row = ik_motion_ae2_feature_rows(store, cur_vec, pred_vec)
            ae2_window = ik_motion_ae2_window_rows(ae2_context, ae2_row)
            ae2_context_next = torch.cat((ae2_context[:, 1:, :], ae2_row[:, None, :]), dim=1)
            if step + 1 >= ae2_window_frames:
                ae2_valid = (effective_k > int(step + 1)).to(dtype=row_weight.dtype)
                ae2_rows = ik_motion_ae2_score_window_rows(ae2, ae2_mean, ae2_std, ae2_window, ae2_window_weights)
                ae2_loss = (ae2_rows * row_weight * ae2_valid).sum() * float(ae2_loss_weight)
                ae2_weighted_total = ae2_weighted_total + ae2_loss
        ae3_loss = torch.zeros_like(total_loss)
        if ae3_enabled and ae3 is not None and ae3_mean is not None and ae3_std is not None:
            ae3_valid = (effective_k > int(step + 1)).to(dtype=row_weight.dtype)
            ae3_rows = pin_aware_ae3_score_rows(
                ae3, ae3_mean, ae3_std, ae3_pos_weight, inp, store, pred_vec, pin_logits, cleaned_foot_heights
            )
            ae3_loss = (ae3_rows * row_weight * ae3_valid).sum() * float(ae3_loss_weight)
            ae3_weighted_total = ae3_weighted_total + ae3_loss
        leg_crossing_capsule_loss = torch.zeros_like(total_loss)
        if leg_crossing_capsule_enabled:
            capsule_rows, capsule_raw_rows, capsule_rate_rows = leg_crossing_capsule_loss_rows(
                store,
                pred_vec,
            )
            leg_crossing_capsule_loss = (
                capsule_rows * row_weight
            ).sum() * float(leg_crossing_capsule_loss_weight)
            leg_crossing_capsule_total = leg_crossing_capsule_total + leg_crossing_capsule_loss
            leg_crossing_capsule_raw_total = leg_crossing_capsule_raw_total + (
                capsule_raw_rows.detach() * row_weight
            ).sum()
            leg_crossing_capsule_rate_total = leg_crossing_capsule_rate_total + (
                capsule_rate_rows.detach() * row_weight
            ).sum()
        pin_logit_gap_loss = torch.zeros_like(total_loss)
        if pin_logit_gap_enabled:
            gap_rows = pin_logit_gap_hinge_rows(pin_logits)
            real_scope = real_dataset_row_scope_rows(store, clip_ids, row_weight.dtype)
            gap_metric_weight = real_dataset_row_metric_weight(row_weight, torch.ones_like(row_weight), real_scope)
            gap_scale = float(pin_logit_gap_loss_weight)
            pin_logit_gap_loss = (gap_rows * gap_metric_weight).sum() * gap_scale
            pin_logit_gap_total = pin_logit_gap_total + pin_logit_gap_loss
            pin_logit_gap_raw_total = pin_logit_gap_raw_total + (gap_rows.detach() * gap_metric_weight).sum()
            pin_logit_gap_bad_rate_total = pin_logit_gap_bad_rate_total + (
                (gap_rows.detach() > 0.0).to(dtype=row_weight.dtype) * gap_metric_weight
            ).sum()
        inertia_acceleration_loss = torch.zeros_like(total_loss)
        cur_inertia_linear_delta = None
        cur_inertia_angular_delta = None
        if inertia_acceleration_enabled:
            assert prev_inertia_linear_delta is not None and prev_inertia_angular_delta is not None
            cur_inertia_linear_delta, cur_inertia_angular_delta = inertia_transition_delta_rows(store, cur_vec, pred_vec)
            (
                inertia_rows,
                inertia_linear_raw_rows,
                inertia_angular_raw_rows,
                inertia_bad_rows,
            ) = inertia_acceleration_excess_rows(
                store,
                prev_inertia_linear_delta,
                prev_inertia_angular_delta,
                cur_inertia_linear_delta,
                cur_inertia_angular_delta,
            )
            real_scope = real_dataset_row_scope_rows(store, clip_ids, row_weight.dtype)
            inertia_metric_weight = real_dataset_row_metric_weight(row_weight, torch.ones_like(row_weight), real_scope)
            inertia_scale = float(inertia_acceleration_loss_weight) * float(INERTIA_ACCELERATION_LOSS_SCALE)
            inertia_acceleration_loss = (inertia_rows * inertia_metric_weight).sum() * inertia_scale
            inertia_acceleration_total = inertia_acceleration_total + inertia_acceleration_loss
            inertia_acceleration_raw_total = inertia_acceleration_raw_total + (
                inertia_rows.detach() * inertia_metric_weight
            ).sum()
            inertia_linear_acceleration_raw_total = inertia_linear_acceleration_raw_total + (
                inertia_linear_raw_rows.detach() * inertia_metric_weight
            ).sum()
            inertia_angular_acceleration_raw_total = inertia_angular_acceleration_raw_total + (
                inertia_angular_raw_rows.detach() * inertia_metric_weight
            ).sum()
            inertia_acceleration_bad_rate_total = inertia_acceleration_bad_rate_total + (
                inertia_bad_rows.detach() * inertia_metric_weight
            ).sum()
        root_accel_pin_loss = torch.zeros_like(total_loss)
        if root_accel_pin_enabled and ae_rows_for_root_accel_scale is not None:
            smooth_heights = foot_roll_smooth_lowest_heights_from_vec(store, pred_vec)
            (
                root_accel_pin_rows,
                root_accel_rows,
                root_accel_active_rows,
                root_accel_bad_rows,
                root_accel_max_pin_rows,
                root_accel_height_rows,
                _root_accel_gate_rows,
            ) = root_accel_pin_loss_rows(
                store,
                clip_ids,
                cur_idx,
                pin_logits,
                cleaned_foot_heights,
                smooth_heights,
            )
            root_accel_metric_weight = row_weight
            root_accel_raw = (root_accel_pin_rows * root_accel_metric_weight).sum()
            root_accel_scale = torch.full_like(
                root_accel_raw,
                float(ROOT_ACCEL_PIN_FIXED_LOSS_WEIGHT) * float(root_accel_pin_loss_ratio),
            )
            root_accel_pin_loss = root_accel_raw * root_accel_scale
            root_accel_pin_total = root_accel_pin_total + root_accel_pin_loss
            root_accel_pin_raw_total = root_accel_pin_raw_total + root_accel_raw.detach()
            root_accel_pin_scale_total = root_accel_pin_scale_total + root_accel_scale.detach()
            root_accel_pin_accel_total = root_accel_pin_accel_total + (
                root_accel_rows * root_accel_metric_weight
            ).sum()
            root_accel_pin_active_rate_total = root_accel_pin_active_rate_total + (
                root_accel_active_rows * root_accel_metric_weight
            ).sum()
            root_accel_pin_bad_rate_total = root_accel_pin_bad_rate_total + (
                root_accel_bad_rows * root_accel_metric_weight
            ).sum()
            root_accel_pin_max_prob_total = root_accel_pin_max_prob_total + (
                root_accel_max_pin_rows * root_accel_metric_weight
            ).sum()
            root_accel_pin_height_total = root_accel_pin_height_total + (
                root_accel_height_rows * root_accel_metric_weight
            ).sum()
        if float(identity_loss_weight) != 0.0:
            identity_loss = (
                (pred_vec - cur_output_vec).square().mean(dim=-1) * row_weight
            ).sum() * float(identity_loss_weight)
        else:
            identity_loss = torch.zeros_like(total_loss)
        if float(identity_maxabs_weight) != 0.0:
            identity_maxabs_loss = (
                (pred_vec - cur_output_vec).abs().amax(dim=-1) * row_weight
            ).sum() * float(identity_maxabs_weight)
        else:
            identity_maxabs_loss = torch.zeros_like(total_loss)
        if float(identity_world_pos_weight) != 0.0:
            identity_world_pos_loss = (
                identity_world_position_rows(store, clip_ids, cur_idx, pred_vec, cur_vec) * row_weight
            ).sum() * float(identity_world_pos_weight)
        else:
            identity_world_pos_loss = torch.zeros_like(total_loss)
        if float(identity_pelvis_pos_weight) != 0.0:
            identity_pelvis_pos_loss = (
                (pred_vec[:, :3] - cur_output_vec[:, :3]).square().sum(dim=-1) * row_weight
            ).sum() * float(identity_pelvis_pos_weight)
        else:
            identity_pelvis_pos_loss = torch.zeros_like(total_loss)
        rl_loss = compute_rl_loss(
            pred_vec,
            cur_output_vec,
            row_weight,
            active,
            rl_cfg,
            payload_slices=store.ik_payload_slices,
            payload_start=payload_slice(store).start,
        )
        ae_total = ae_total + ae_loss
        ae_pose_total = ae_pose_total + ae_pose_loss
        ae_velocity_total = ae_velocity_total + ae_velocity_loss
        identity_total = identity_total + identity_loss
        identity_maxabs_total = identity_maxabs_total + identity_maxabs_loss
        identity_world_pos_total = identity_world_pos_total + identity_world_pos_loss
        identity_pelvis_pos_total = identity_pelvis_pos_total + identity_pelvis_pos_loss
        for key, value in rl_loss.terms.items():
            rl_terms[key] = rl_terms.get(key, torch.zeros_like(total_loss)) + value
        envelope_loss = torch.zeros_like(total_loss)
        alternating_loss = torch.zeros_like(total_loss)
        foot_lift_loss = torch.zeros_like(total_loss)
        anatomy_loss = torch.zeros_like(total_loss)
        if has_anatomy:
            active_f = torch.ones_like(row_weight)
            anatomy_loss, step_anatomy_terms = ik_lower_length_loss_terms(store, pred_vec, row_weight, active_f)
            for key, value in step_anatomy_terms.items():
                anatomy_terms[key] = anatomy_terms.get(key, torch.zeros_like(total_loss)) + value
        if has_envelope or has_alternating or has_foot_lift:
            cur_root_pos, cur_root_rot, _cur_yaw, _cur_heading = store.root_state(clip_ids, cur_idx)
            next_root_pos, next_root_rot = transition_output_root_state(store, clip_ids, cur_idx)
            gate_next_root_pos, _gate_next_root_rot, _gate_next_yaw, _gate_next_heading = store.root_state(
                clip_ids, cur_idx + 1
            )
            cur_foot_pos, cur_foot_rot = env.ik_foot_toe_state_from_vec(store, cur_root_pos, cur_root_rot, cur_vec)
            next_foot_pos, next_foot_rot = env.ik_foot_toe_state_from_vec(store, next_root_pos, next_root_rot, pred_vec)
            envelope_row_weight = row_weight
            envelope_clip_ids = clip_ids
            envelope_cur_idx = cur_idx
            synthetic_flags = getattr(store, "synthetic", None)
            if envelope is not None and isinstance(synthetic_flags, torch.Tensor) and int(synthetic_flags.numel()) > 0:
                generated_rows = synthetic_flags.index_select(0, clip_ids.to(store.device).long())
                envelope_row_weight = row_weight * (~generated_rows).to(dtype=row_weight.dtype)
                envelope_clip_ids = torch.where(generated_rows, torch.zeros_like(clip_ids), clip_ids)
                envelope_cur_idx = torch.where(generated_rows, torch.ones_like(cur_idx), cur_idx)
            if has_envelope:
                linear_loss = torch.zeros_like(total_loss)
                angular_loss = torch.zeros_like(total_loss)
                height_loss = torch.zeros_like(total_loss)
                if float(linear_slide_weight) != 0.0 or float(angular_slide_weight) != 0.0:
                    linear_rows, angular_rows = env.envelope_excess_ik_state_rows(
                        store,
                        envelope,  # type: ignore[arg-type]
                        cur_foot_pos,
                        cur_foot_rot,
                        next_foot_pos,
                        next_foot_rot,
                        envelope_clip_ids,
                        envelope_cur_idx,
                    )
                    linear_loss = (linear_rows * envelope_row_weight).sum() * float(linear_slide_weight)
                    angular_loss = (angular_rows * envelope_row_weight).sum() * float(angular_slide_weight)
                if float(foot_height_weight) != 0.0:
                    height_rows = env.envelope_height_excess_ik_state_rows(
                        store,
                        envelope,  # type: ignore[arg-type]
                        cur_foot_pos,
                        next_foot_pos,
                        next_foot_rot,
                        envelope_clip_ids,
                        envelope_cur_idx,
                    ).mean(dim=-1)
                    height_loss = (height_rows * envelope_row_weight).sum() * float(foot_height_weight) * FOOT_HEIGHT_LOSS_SCALE
                envelope_terms["linear_slide_weighted"] = envelope_terms["linear_slide_weighted"] + linear_loss
                envelope_terms["angular_slide_weighted"] = envelope_terms["angular_slide_weighted"] + angular_loss
                envelope_terms["foot_height_weighted"] = envelope_terms["foot_height_weighted"] + height_loss
                envelope_loss = linear_loss + angular_loss + height_loss
            if has_alternating:
                active_f = torch.ones_like(row_weight)
                alternating_loss, step_alternating_terms = alternating_feet_loss_terms(
                    store,
                    cur_root_pos,
                    gate_next_root_pos,
                    cur_foot_pos,
                    next_foot_pos,
                    row_weight,
                    active_f,
                    alternating_feet_weight,
                    alternating_root_cutoff_mps,
                )
                for key, value in step_alternating_terms.items():
                    alternating_terms[key] = alternating_terms.get(key, torch.zeros_like(total_loss)) + value
            if has_foot_lift:
                active_f = torch.ones_like(row_weight)
                terminal_gate = (effective_k.float() - float(step) <= float(TERMINAL_FOOT_STILLNESS_FRAMES)).float()
                foot_lift_loss, step_foot_lift_terms = foot_lift_slide_loss_terms(
                    store,
                    envelope,
                    cur_root_pos,
                    gate_next_root_pos,
                    cur_foot_pos,
                    next_foot_pos,
                    next_foot_rot,
                    clip_ids,
                    cur_idx,
                    row_weight,
                    active_f,
                    foot_lift_slide_weight,
                    alternating_root_cutoff_mps,
                    terminal_gate,
                )
                for key, value in step_foot_lift_terms.items():
                    foot_lift_terms[key] = foot_lift_terms.get(key, torch.zeros_like(total_loss)) + value
        total_loss = (
            total_loss
            + ae_loss
            + identity_loss
            + identity_maxabs_loss
            + identity_world_pos_loss
            + identity_pelvis_pos_loss
            + rl_loss.total
            + ae2_loss
            + ae3_loss
            + leg_crossing_capsule_loss
            + pin_logit_gap_loss
            + inertia_acceleration_loss
            + root_accel_pin_loss
            + envelope_loss
            + alternating_loss
            + foot_lift_loss
            + anatomy_loss
            + contact_height_loss
            + foot_unpin_penalty
            + pinned_foot_intent_loss
            + slide_tentative_loss
            + pinned_foot_height_loss
            + idle_foot_flatness_loss
        )
        if step + 1 >= max_k:
            break

        continuing = effective_k > (step + 1)
        rows = continuing.nonzero(as_tuple=False).flatten()
        if rows.numel() == 0:
            break
        if init_pose_noise_batch is not None:
            init_pose_noise_batch = index_init_pose_noise_batch(init_pose_noise_batch, rows)
        clip_ids = clip_ids.index_select(0, rows)
        reset = training_reset_rows(store, clip_ids, cur_idx.index_select(0, rows), torch.ones_like(rows, dtype=torch.bool))
        selected_cur_idx = cur_idx.index_select(0, rows)
        next_vec, next_pelvis, next_payload = advance_transition_state(
            store,
            clip_ids,
            selected_cur_idx,
            pred_vec.index_select(0, rows),
        )
        next_idx = cur_idx.index_select(0, rows) + 1
        remaining_steps = max(1, int(max_k) - int(step + 1))
        reset_starts = sample_same_clip_training_starts(
            store,
            clip_ids,
            ae_required_context_frames,
            remaining_steps,
        )
        reset_prev_vec, reset_prev_pelvis, reset_prev_payload = target_state(store, clip_ids, reset_starts - 1)
        reset_cur_vec, reset_cur_pelvis, reset_cur_payload = target_state(store, clip_ids, reset_starts)
        if ae_context is not None:
            context_rows = ae_context.index_select(0, rows)
            raw_rows = raw_feature.index_select(0, rows)
            shifted_context = torch.cat((context_rows[:, 1:, :], raw_rows[:, None, :]), dim=1)
            reset_context = initial_ae_context(store, clip_ids, reset_starts, ae_frames)
            assert reset_context is not None
            ae_context = torch.where(reset[:, None, None], reset_context, shifted_context)
        if ae2_context_next is not None:
            selected_ae2_context = ae2_context_next.index_select(0, rows)
            zero_ae2_context = torch.zeros_like(selected_ae2_context)
            ae2_context = torch.where(reset[:, None, None], zero_ae2_context, selected_ae2_context)
        if inertia_acceleration_enabled:
            assert cur_inertia_linear_delta is not None and cur_inertia_angular_delta is not None
            assert prev_inertia_linear_delta is not None and prev_inertia_angular_delta is not None
            selected_linear_delta = cur_inertia_linear_delta.index_select(0, rows)
            selected_angular_delta = cur_inertia_angular_delta.index_select(0, rows)
            reset_linear_delta, reset_angular_delta = inertia_transition_delta_rows(store, reset_prev_vec, reset_cur_vec)
            prev_inertia_linear_delta = torch.where(reset[:, None, None], reset_linear_delta, selected_linear_delta)
            prev_inertia_angular_delta = torch.where(reset[:, None, None], reset_angular_delta, selected_angular_delta)
        reset_mask = reset[:, None]
        prev_vec = torch.where(reset_mask, reset_prev_vec, cur_vec.index_select(0, rows))
        prev_pelvis = torch.where(reset_mask, reset_prev_pelvis, cur_pelvis.index_select(0, rows))
        prev_payload = torch.where(reset_mask, reset_prev_payload, cur_payload.index_select(0, rows))
        cur_vec = torch.where(reset_mask, reset_cur_vec, next_vec)
        cur_pelvis = torch.where(reset_mask, reset_cur_pelvis, next_pelvis)
        cur_payload = torch.where(reset_mask, reset_cur_payload, next_payload)
        cur_idx = torch.where(reset, reset_starts, next_idx)
        effective_k = effective_k.index_select(0, rows)
        row_weight = row_weight.index_select(0, rows)
    if not total_loss.requires_grad:
        total_loss = total_loss + pred_vec.sum() * 0.0
    return ControllerLossResult(
        total=total_loss,
        terms={
            "ae_score": ae_raw_total,
            AE_POSE_TERM_NAME: ae_pose_total,
            AE_VELOCITY_TERM_NAME: ae_velocity_total,
            GT_MSE_WEIGHTED_TERM_NAME: gt_mse_weighted_total,
            GT_MSE_RAW_TERM_NAME: gt_mse_raw_total,
            GT_MSE_POS_TERM_NAME: gt_mse_pos_total,
            GT_MSE_ROT_TERM_NAME: gt_mse_rot_total,
            GT_MSE_LINVEL_TERM_NAME: gt_mse_linvel_total,
            GT_MSE_ANGVEL_TERM_NAME: gt_mse_angvel_total,
            AE5_SCORE_TERM_NAME: ae5_score_total,
            AE5_WEIGHTED_TERM_NAME: ae5_weighted_total,
            AE5_ACTIVE_RATE_TERM_NAME: ae5_active_rate_total,
            AE6_CONTACT_SCORE_TERM_NAME: ae6_score_total,
            AE6_CONTACT_WEIGHTED_TERM_NAME: ae6_weighted_total,
            AE6_CONTACT_MAE_TERM_NAME: ae6_mae_total,
            AE6_CONTACT_ACC_TERM_NAME: ae6_acc_total,
            AE2_WEIGHTED_TERM_NAME: ae2_weighted_total,
            AE3_PIN_WEIGHTED_TERM_NAME: ae3_weighted_total,
            LEG_CROSSING_CAPSULE_TERM_NAME: leg_crossing_capsule_total,
            LEG_CROSSING_CAPSULE_RAW_TERM_NAME: leg_crossing_capsule_raw_total,
            LEG_CROSSING_CAPSULE_RATE_TERM_NAME: leg_crossing_capsule_rate_total,
            PIN_LOGIT_GAP_WEIGHTED_TERM_NAME: pin_logit_gap_total,
            PIN_LOGIT_GAP_RAW_TERM_NAME: pin_logit_gap_raw_total,
            PIN_LOGIT_GAP_BAD_RATE_TERM_NAME: pin_logit_gap_bad_rate_total,
            INERTIA_ACCELERATION_WEIGHTED_TERM_NAME: inertia_acceleration_total,
            INERTIA_ACCELERATION_RAW_TERM_NAME: inertia_acceleration_raw_total,
            INERTIA_LINEAR_ACCELERATION_RAW_TERM_NAME: inertia_linear_acceleration_raw_total,
            INERTIA_ANGULAR_ACCELERATION_RAW_TERM_NAME: inertia_angular_acceleration_raw_total,
            INERTIA_ACCELERATION_BAD_RATE_TERM_NAME: inertia_acceleration_bad_rate_total,
            ROOT_ACCEL_PIN_WEIGHTED_TERM_NAME: root_accel_pin_total,
            ROOT_ACCEL_PIN_RAW_TERM_NAME: root_accel_pin_raw_total,
            ROOT_ACCEL_PIN_SCALE_TERM_NAME: root_accel_pin_scale_total,
            ROOT_ACCEL_PIN_ACCEL_TERM_NAME: root_accel_pin_accel_total,
            ROOT_ACCEL_PIN_ACTIVE_RATE_TERM_NAME: root_accel_pin_active_rate_total,
            ROOT_ACCEL_PIN_BAD_RATE_TERM_NAME: root_accel_pin_bad_rate_total,
            ROOT_ACCEL_PIN_MAX_PROB_TERM_NAME: root_accel_pin_max_prob_total,
            ROOT_ACCEL_PIN_HEIGHT_TERM_NAME: root_accel_pin_height_total,
            AE4_BANK_PIN_WEIGHTED_TERM_NAME: ae4_bank_pin_total,
            AE4_BANK_PIN_RAW_TERM_NAME: ae4_bank_pin_raw_total,
            AE4_BANK_PIN_ROOT_SCALE_TERM_NAME: ae4_bank_pin_root_scale_total,
            IDENTITY_TERM_NAME: identity_total,
            IDENTITY_MAXABS_TERM_NAME: identity_maxabs_total,
            IDENTITY_WORLD_POS_TERM_NAME: identity_world_pos_total,
            IDENTITY_PELVIS_POS_TERM_NAME: identity_pelvis_pos_total,
            FOOT_UNPIN_PENALTY_TERM_NAME: foot_unpin_penalty_total,
            FOOT_UNPIN_SOFT_RATE_TERM_NAME: foot_unpin_soft_rate_total,
            PINNED_FOOT_INTENT_TERM_NAME: pinned_foot_intent_total,
            PINNED_FOOT_INTENT_RAW_TERM_NAME: pinned_foot_intent_raw_total,
            PINNED_FOOT_INTENT_MPS_TERM_NAME: pinned_foot_intent_mps_total,
            SLIDE_TENTATIVE_TERM_NAME: slide_tentative_total,
            SLIDE_TENTATIVE_RAW_TERM_NAME: slide_tentative_raw_total,
            SLIDE_TENTATIVE_PIN_RATE_TERM_NAME: slide_tentative_pin_rate_total,
            PINNED_FOOT_HEIGHT_TERM_NAME: pinned_foot_height_total,
            PINNED_FOOT_HEIGHT_RAW_TERM_NAME: pinned_foot_height_raw_total,
            PINNED_FOOT_HEIGHT_MAX_TERM_NAME: pinned_foot_height_max_total,
            IDLE_FOOT_FLATNESS_TERM_NAME: idle_foot_flatness_total,
            IDLE_FOOT_FLATNESS_RAW_TERM_NAME: idle_foot_flatness_raw_total,
            IDLE_FOOT_FLATNESS_MAX_TERM_NAME: idle_foot_flatness_max_total,
            **pin_behavior_terms,
            **foot_contact_terms,
            **rl_terms,
            **envelope_terms,
            **alternating_terms,
            **foot_lift_terms,
            **anatomy_terms,
        },
    )


def pure_ae_rollout_loss_static(
    model: torch.nn.Module,
    ae: SimpleAutoencoder,
    mean: torch.Tensor,
    std: torch.Tensor,
    store: SimpleClipStore,
    rollout_k: int,
    batch_size: int,
    effective_k: torch.Tensor,
    clip_ids: torch.Tensor,
    starts: torch.Tensor,
    init_clip_ids: torch.Tensor | None = None,
    init_starts: torch.Tensor | None = None,
    reset_starts_by_step: torch.Tensor | None = None,
    rl_cfg: RLLossConfig | None = None,
    ae_loss_weight: float = 1.0,
    envelope: dict[str, torch.Tensor | dict[str, float | int | str]] | None = None,
    linear_slide_weight: float = 0.0,
    angular_slide_weight: float = 0.0,
    foot_height_weight: float = 0.0,
    alternating_feet_weight: float = 0.0,
    foot_lift_slide_weight: float = 0.0,
    pinned_foot_height_weight: float = 0.0,
    idle_foot_flatness_weight: float = 0.0,
    slide_tentative_loss_weight: float = 0.0,
    forced_idle_batch_fraction: float | None = None,
    alternating_root_cutoff_mps: float = 1.0,
    identity_loss_weight: float = 0.0,
    identity_maxabs_weight: float = 0.0,
    identity_world_pos_weight: float = 0.0,
    identity_pelvis_pos_weight: float = 0.0,
    init_store: SimpleClipStore | None = None,
    init_adjacent_context: bool = False,
    random_init_rows: torch.Tensor | None = None,
    random_reset_clip_ids_by_step: torch.Tensor | None = None,
    random_reset_starts_by_step: torch.Tensor | None = None,
    include_diagnostics: bool = True,
    loss_weight_tensors: dict[str, torch.Tensor] | None = None,
    init_noise_amount: float = DEFAULT_INIT_NOISE_AMOUNT,
    init_noise_clean_fraction: float = DEFAULT_INIT_NOISE_CLEAN_FRACTION,
    init_pose_noise_batch: InitPoseNoiseBatch | None = None,
    extra_ae: SimpleAutoencoder | None = None,
    extra_mean: torch.Tensor | None = None,
    extra_std: torch.Tensor | None = None,
    extra_ae_loss_weight: float = 0.0,
    ae5: SimpleAutoencoder | None = None,
    ae5_mean: torch.Tensor | None = None,
    ae5_std: torch.Tensor | None = None,
    ae5_loss_weight: float = 0.0,
    ae5_reserved_row_start: int = 0,
    ae5_reserved_rows: int | None = None,
    ae6: torch.nn.Module | None = None,
    ae6_mean: torch.Tensor | None = None,
    ae6_std: torch.Tensor | None = None,
    ae6_loss_weight: float = 0.0,
    ae2: torch.nn.Module | None = None,
    ae2_mean: torch.Tensor | None = None,
    ae2_std: torch.Tensor | None = None,
    ae2_loss_weight: float = 0.0,
    ae2_window_weights: torch.Tensor | None = None,
    ae3: torch.nn.Module | None = None,
    ae3_mean: torch.Tensor | None = None,
    ae3_std: torch.Tensor | None = None,
    ae3_pos_weight: torch.Tensor | None = None,
    ae3_loss_weight: float = 0.0,
    pin_logit_gap_loss_weight: float = 0.0,
    inertia_acceleration_loss_weight: float = 0.0,
    root_accel_pin_loss_ratio: float = 0.0,
    leg_crossing_capsule_loss_weight: float = 0.0,
    ae4: object | None = None,
    ae4_input_mean: torch.Tensor | None = None,
    ae4_input_std: torch.Tensor | None = None,
    ae4_target_mean: torch.Tensor | None = None,
    ae4_target_std: torch.Tensor | None = None,
    ae4_loss_weight: float = 0.0,
    ae4_bank_pin_loss_weight: float = 0.0,
    dedicated_real_rows: int = 0,
    dedicated_real_loss_multiplier: float = DEFAULT_DEDICATED_REAL_LOSS_MULTIPLIER,
    periodic_reserved_rows: int = 0,
    debug_capture: dict[str, torch.Tensor] | None = None,
) -> ControllerLossResult:
    global PRETRAIN_LOSS_PROFILE_EMITTED

    profile_loss = (
        bool(PRETRAIN_DETAILED_LOSS_PROFILE)
        and PRETRAIN_RELEASE_EVENT is not None
        and PRETRAIN_ARM_STARTED_AT is not None
        and not PRETRAIN_LOSS_PROFILE_EMITTED
    )
    profile_times: dict[str, float] = {}
    profile_started = time.perf_counter()

    def mark_profile(name: str, started: float) -> float:
        if profile_loss:
            profile_times[name] = profile_times.get(name, 0.0) + time.perf_counter() - started
        return time.perf_counter()

    rl_cfg = rl_cfg or RLLossConfig()
    max_k = max(1, int(rollout_k))
    part_started = time.perf_counter()
    cur_idx = starts
    if init_store is not None and init_clip_ids is not None and init_starts is not None:
        if bool(init_adjacent_context):
            init_prev_starts, init_cur_starts = torch.clamp(init_starts - 1, min=0), init_starts
        else:
            init_prev_starts, init_cur_starts = rollout_init_context_indices(init_starts)
        prev_vec, prev_pelvis, prev_payload = target_state(init_store, init_clip_ids, init_prev_starts)
        cur_vec, cur_pelvis, cur_payload = target_state(init_store, init_clip_ids, init_cur_starts)
        ae4_source_store = store
        ae4_source_clip_ids = clip_ids
        ae4_source_idx = cur_idx
        if isinstance(getattr(store, "synthetic", None), torch.Tensor):
            synth_rows = store.synthetic.index_select(0, clip_ids).reshape(-1, 1)
            synth_prev_vec, synth_prev_pelvis, synth_prev_payload = target_state(store, clip_ids, cur_idx - 1)
            synth_cur_vec, synth_cur_pelvis, synth_cur_payload = target_state(store, clip_ids, cur_idx)
            prev_vec = torch.where(synth_rows, synth_prev_vec, prev_vec)
            prev_pelvis = torch.where(synth_rows, synth_prev_pelvis, prev_pelvis)
            prev_payload = torch.where(synth_rows, synth_prev_payload, prev_payload)
            cur_vec = torch.where(synth_rows, synth_cur_vec, cur_vec)
            cur_pelvis = torch.where(synth_rows, synth_cur_pelvis, cur_pelvis)
            cur_payload = torch.where(synth_rows, synth_cur_payload, cur_payload)
    else:
        prev_vec, prev_pelvis, prev_payload = target_state(store, clip_ids, cur_idx - 1)
        cur_vec, cur_pelvis, cur_payload = target_state(store, clip_ids, cur_idx)
        ae4_source_store = store
        ae4_source_clip_ids = clip_ids
        ae4_source_idx = cur_idx
    if init_pose_noise_batch is None and init_noise_enabled(init_noise_clean_fraction):
        rng_snapshot = clone_rng_state(store.device)
        try:
            init_pose_noise_batch = sample_fixed_init_pose_noise_batch(
                store,
                int(cur_vec.shape[0]),
                init_noise_clean_fraction,
                device=cur_vec.device,
                dtype=cur_vec.dtype,
            )
        finally:
            restore_rng_state(rng_snapshot, store.device)
    if init_pose_noise_batch is not None:
        prev_vec = apply_init_pose_noise_batch(store, prev_vec, init_pose_noise_batch)
        cur_vec = apply_init_pose_noise_batch(store, cur_vec, init_pose_noise_batch)
        prev_pelvis = prev_vec[:, :3]
        cur_pelvis = cur_vec[:, :3]
        vec_payload_slice = payload_slice(store)
        prev_payload = prev_vec[:, vec_payload_slice]
        cur_payload = cur_vec[:, vec_payload_slice]
    input_dim, output_dim = tl.make_batch_dims(store.prototype, store.cfg)
    ae_frames = ae_window_frames_from_dims(mean, input_dim, output_dim)
    if extra_ae is not None and extra_mean is not None:
        extra_frames = ae_window_frames_from_dims(extra_mean, input_dim, output_dim)
        if extra_frames != ae_frames:
            raise ValueError(f"Extra AE window_frames={extra_frames} does not match primary AE window_frames={ae_frames}")
    ae5_enabled = ae5 is not None and ae5_mean is not None and ae5_std is not None and float(ae5_loss_weight) != 0.0
    ae5_motion_enabled = ae5_enabled and is_ik_motion_window_ae(ae5)
    ae5_frames = (
        ik_motion_ae2_window_shape(ae5)[0]
        if ae5_motion_enabled and ae5 is not None
        else (ae_window_frames_from_dims(ae5_mean, input_dim, output_dim) if ae5_mean is not None else 1)
    )
    ae5_context = None
    if init_store is not None and bool(init_adjacent_context) and init_clip_ids is not None and init_starts is not None:
        ae_context = initial_ae_context(init_store, init_clip_ids, init_starts, ae_frames)
    elif init_store is not None:
        ae_context = duplicated_init_ae_context(store, clip_ids, cur_idx, cur_vec, cur_pelvis, cur_payload, ae_frames)
    else:
        ae_context = initial_ae_context(store, clip_ids, cur_idx, ae_frames)
    if ae5_enabled and not ae5_motion_enabled:
        if init_store is not None and bool(init_adjacent_context) and init_clip_ids is not None and init_starts is not None:
            ae5_context = initial_ae_context(init_store, init_clip_ids, init_starts, ae5_frames)
        elif init_store is not None:
            ae5_context = duplicated_init_ae_context(
                store, clip_ids, cur_idx, cur_vec, cur_pelvis, cur_payload, ae5_frames
            )
        else:
            ae5_context = initial_ae_context(store, clip_ids, cur_idx, ae5_frames)
    ae6_enabled = ae6 is not None and ae6_mean is not None and ae6_std is not None and float(ae6_loss_weight) != 0.0
    ae6_frames = ae_window_frames_from_dims(ae6_mean, input_dim, output_dim) if ae6_mean is not None else 1
    ae_required_context_frames = max(
        int(ae_frames),
        int(ae5_frames) if ae5_enabled else 1,
        int(ae6_frames) if ae6_enabled else 1,
    )
    ae2_enabled = ae2 is not None and ae2_mean is not None and ae2_std is not None and float(ae2_loss_weight) != 0.0
    ae3_enabled = ae3 is not None and ae3_mean is not None and ae3_std is not None and float(ae3_loss_weight) != 0.0
    pin_logit_gap_enabled = float(pin_logit_gap_loss_weight) != 0.0
    inertia_acceleration_enabled = float(inertia_acceleration_loss_weight) != 0.0
    root_accel_pin_enabled = float(root_accel_pin_loss_ratio) != 0.0 and float(ae_loss_weight) != 0.0
    ae4_enabled = (
        ae4 is not None
        and ae4_input_mean is not None
        and ae4_input_std is not None
        and ae4_target_mean is not None
        and ae4_target_std is not None
        and (float(ae4_loss_weight) != 0.0 or float(ae4_bank_pin_loss_weight) != 0.0)
    )
    ae4_bank_pin_enabled = (
        ae4_enabled and ae4_uses_pose_bank_projector(ae4) and float(ae4_bank_pin_loss_weight) != 0.0
    )
    ae2_window_frames = 1
    ae2_context: torch.Tensor | None = None
    if ae2_enabled:
        ae2_window_frames, ae2_frame_dim = ik_motion_ae2_window_shape(ae2)
        ae2_context = torch.zeros(
            (cur_vec.shape[0], max(0, ae2_window_frames - 1), ae2_frame_dim),
            dtype=cur_vec.dtype,
            device=store.device,
        )
        if ae2_window_weights is None:
            ae2_frame_weights = ik_motion_ae2_frame_feature_weights(
                store,
                ae2_frame_dim,
                ae2_loss_weight,
                dtype=cur_vec.dtype,
                device=store.device,
            )
            ae2_window_weights = ae2_frame_weights.repeat(ae2_window_frames)
    ae5_motion_row_count = (
        int(batch_size)
        if ae5_reserved_rows is None
        else max(0, min(int(batch_size), int(ae5_reserved_rows)))
    )
    ae5_motion_row_start = max(0, min(int(batch_size), int(ae5_reserved_row_start)))
    ae5_motion_row_count = max(0, min(int(batch_size) - ae5_motion_row_start, int(ae5_motion_row_count)))
    ae5_motion_context: torch.Tensor | None = None
    ae5_motion_context_next: torch.Tensor | None = None
    if ae5_motion_enabled and ae5 is not None:
        ae5_frames, ae5_frame_dim = ik_motion_ae2_window_shape(ae5)
        ae5_motion_context = torch.zeros(
            (ae5_motion_row_count, max(0, ae5_frames - 1), ae5_frame_dim),
            dtype=cur_vec.dtype,
            device=store.device,
        )
    effective_k_f = effective_k.float()
    max_k_f = float(max(1, int(max_k)))
    row_weight = torch.full_like(effective_k_f, 1.0 / (float(max(1, int(batch_size))) * max_k_f))
    row_weight = apply_dedicated_real_loss_multiplier(
        row_weight,
        dedicated_real_rows,
        dedicated_real_loss_multiplier,
    )
    total_loss = torch.zeros((), dtype=torch.float32, device=store.device)
    ae_raw_total = torch.zeros_like(total_loss)
    ae_total = torch.zeros_like(total_loss)
    ae_pose_total = torch.zeros_like(total_loss)
    ae_velocity_total = torch.zeros_like(total_loss)
    gt_mse_raw_total = torch.zeros_like(total_loss)
    gt_mse_weighted_total = torch.zeros_like(total_loss)
    gt_mse_pos_total = torch.zeros_like(total_loss)
    gt_mse_rot_total = torch.zeros_like(total_loss)
    gt_mse_linvel_total = torch.zeros_like(total_loss)
    gt_mse_angvel_total = torch.zeros_like(total_loss)
    ae5_score_total = torch.zeros_like(total_loss)
    ae5_weighted_total = torch.zeros_like(total_loss)
    ae5_active_rate_total = torch.zeros_like(total_loss)
    ae6_score_total = torch.zeros_like(total_loss)
    ae6_weighted_total = torch.zeros_like(total_loss)
    ae6_mae_total = torch.zeros_like(total_loss)
    ae6_acc_total = torch.zeros_like(total_loss)
    ae2_weighted_total = torch.zeros_like(total_loss)
    ae3_weighted_total = torch.zeros_like(total_loss)
    pin_logit_gap_total = torch.zeros_like(total_loss)
    pin_logit_gap_raw_total = torch.zeros_like(total_loss)
    pin_logit_gap_bad_rate_total = torch.zeros_like(total_loss)
    inertia_acceleration_total = torch.zeros_like(total_loss)
    inertia_acceleration_raw_total = torch.zeros_like(total_loss)
    inertia_linear_acceleration_raw_total = torch.zeros_like(total_loss)
    inertia_angular_acceleration_raw_total = torch.zeros_like(total_loss)
    inertia_acceleration_bad_rate_total = torch.zeros_like(total_loss)
    root_accel_pin_total = torch.zeros_like(total_loss)
    root_accel_pin_raw_total = torch.zeros_like(total_loss)
    root_accel_pin_scale_total = torch.zeros_like(total_loss)
    root_accel_pin_accel_total = torch.zeros_like(total_loss)
    root_accel_pin_active_rate_total = torch.zeros_like(total_loss)
    root_accel_pin_bad_rate_total = torch.zeros_like(total_loss)
    root_accel_pin_max_prob_total = torch.zeros_like(total_loss)
    root_accel_pin_height_total = torch.zeros_like(total_loss)
    ae4_score_total = torch.zeros_like(total_loss)
    ae4_hinge_total = torch.zeros_like(total_loss)
    ae4_weighted_total = torch.zeros_like(total_loss)
    ae4_bank_pin_total = torch.zeros_like(total_loss)
    ae4_bank_pin_raw_total = torch.zeros_like(total_loss)
    ae4_bank_pin_root_scale_total = torch.zeros_like(total_loss)
    pinned_foot_height_total = torch.zeros_like(total_loss)
    pinned_foot_height_raw_total = torch.zeros_like(total_loss)
    pinned_foot_height_max_total = torch.zeros_like(total_loss)
    idle_foot_flatness_total = torch.zeros_like(total_loss)
    idle_foot_flatness_raw_total = torch.zeros_like(total_loss)
    idle_foot_flatness_max_total = torch.zeros_like(total_loss)
    leg_crossing_capsule_total = torch.zeros_like(total_loss)
    leg_crossing_capsule_raw_total = torch.zeros_like(total_loss)
    leg_crossing_capsule_rate_total = torch.zeros_like(total_loss)
    identity_total = torch.zeros_like(total_loss)
    identity_maxabs_total = torch.zeros_like(total_loss)
    identity_world_pos_total = torch.zeros_like(total_loss)
    identity_pelvis_pos_total = torch.zeros_like(total_loss)
    foot_unpin_penalty_total = torch.zeros_like(total_loss)
    foot_unpin_soft_rate_total = torch.zeros_like(total_loss)
    pinned_foot_intent_total = torch.zeros_like(total_loss)
    pinned_foot_intent_raw_total = torch.zeros_like(total_loss)
    pinned_foot_intent_mps_total = torch.zeros_like(total_loss)
    slide_tentative_total = torch.zeros_like(total_loss)
    slide_tentative_raw_total = torch.zeros_like(total_loss)
    slide_tentative_pin_rate_total = torch.zeros_like(total_loss)
    pin_behavior_terms = {name: torch.zeros_like(total_loss) for name in PIN_BEHAVIOR_TERM_NAMES}
    foot_contact_terms = {name: torch.zeros_like(total_loss) for name in (FOOT_CONTACT_HEIGHT_LOSS_TERM_NAME, *FOOT_CONTACT_HEIGHT_METRIC_NAMES)}
    rl_terms = {name: torch.zeros_like(total_loss) for name in RL_TERM_NAMES}
    envelope_terms = {name: torch.zeros_like(total_loss) for name in ENVELOPE_TERM_NAMES}
    alternating_names = ALTERNATING_FEET_TERM_NAMES if include_diagnostics else ALTERNATING_FEET_LOSS_TERM_NAMES
    foot_lift_names = FOOT_LIFT_SLIDE_TERM_NAMES if include_diagnostics else FOOT_LIFT_SLIDE_LOSS_TERM_NAMES
    anatomy_names = IK_LOWER_LENGTH_TERM_NAMES if include_diagnostics else IK_LOWER_LENGTH_LOSS_TERM_NAMES
    alternating_terms = {name: torch.zeros_like(total_loss) for name in alternating_names}
    foot_lift_terms = {name: torch.zeros_like(total_loss) for name in foot_lift_names}
    anatomy_terms = {name: torch.zeros_like(total_loss) for name in anatomy_names}
    has_envelope = envelope is not None and envelope_loss_enabled(linear_slide_weight, angular_slide_weight, foot_height_weight)
    has_alternating = alternating_feet_loss_enabled(alternating_feet_weight)
    has_foot_lift = envelope is not None and foot_lift_slide_loss_enabled(foot_lift_slide_weight)
    has_anatomy = ik_lower_length_loss_enabled()
    has_identity = (
        float(identity_loss_weight) != 0.0
        or float(identity_maxabs_weight) != 0.0
        or float(identity_world_pos_weight) != 0.0
        or float(identity_pelvis_pos_weight) != 0.0
    )
    has_rl = bool(rl_cfg.enabled)
    track_pin_contact_diagnostics = bool(include_diagnostics)
    foot_unpin_enabled = float(FOOT_UNPIN_PENALTY_WEIGHT) != 0.0
    pinned_foot_intent_enabled = float(PINNED_FOOT_INTENT_PENALTY_WEIGHT) != 0.0
    slide_tentative_enabled = float(slide_tentative_loss_weight) != 0.0
    pinned_foot_height_enabled = float(pinned_foot_height_weight) != 0.0
    idle_foot_flatness_enabled = float(idle_foot_flatness_weight) != 0.0
    leg_crossing_capsule_enabled = float(leg_crossing_capsule_loss_weight) != 0.0
    contact_height_loss_enabled = float(FOOT_CONTACT_MIN_HEIGHT_LOSS_MAX) != 0.0
    need_foot_heights = (
        bool(FOOT_ROLL_HEIGHT_PIN_GATE)
        or contact_height_loss_enabled
        or pinned_foot_height_enabled
        or root_accel_pin_enabled
        or track_pin_contact_diagnostics
        or debug_capture is not None
    )
    need_pin_mask = (
        bool(FOOT_ROLL_HEIGHT_PIN_GATE)
        or slide_tentative_enabled
        or track_pin_contact_diagnostics
        or debug_capture is not None
    )
    need_foot_unpin_rows = foot_unpin_enabled or track_pin_contact_diagnostics
    output_uses_current_root = tl.output_reference_uses_current_root()
    output_uses_future_root = tl.output_reference_uses_future_root()
    row_loss_accum = torch.zeros((int(batch_size),), dtype=torch.float32, device=store.device)
    segment_step = torch.zeros_like(effective_k)
    prev_pin_mask: torch.Tensor | None = None
    prev_inertia_linear_delta: torch.Tensor | None = None
    prev_inertia_angular_delta: torch.Tensor | None = None
    if inertia_acceleration_enabled:
        prev_inertia_linear_delta, prev_inertia_angular_delta = inertia_transition_delta_rows(store, prev_vec, cur_vec)
    if debug_capture is not None:
        debug_capture["vectors"][:, 0, :].copy_(cur_vec.detach())
        debug_capture["frame_idx"][:, 0].copy_(cur_idx.detach())
        debug_capture["pin_logits"][:, 0, :].zero_()
        debug_capture["pin_mask"][:, 0, :].zero_()
        debug_capture["reset_flags"][:, 0].zero_()
    part_started = mark_profile("loss_init_state", part_started)

    for step in range(max_k):
        step_started = time.perf_counter()
        inp = build_controller_input(
            store, clip_ids, cur_idx, prev_vec, cur_vec, prev_pelvis, cur_pelvis, prev_payload, cur_payload
        )
        part_started = mark_profile("loss_build_input", step_started)
        raw_pred = model_raw_output(model, inp, cur_vec, store)
        stationary_both_pin_amount = (
            1.0 - root_motion_activity_rows(store, clip_ids, cur_idx, init_store)
            if track_pin_contact_diagnostics
            else None
        )
        raw_clean_vec = None
        if slide_tentative_enabled:
            pred_vec, raw_clean_vec = clean_output_vector_pair(raw_pred, store, cur_vec, prev_vec)
        else:
            pred_vec = clean_output_vector(raw_pred, store, cur_vec, prev_vec)
        pin_logits = foot_pin_logits_from_raw(raw_pred, store)
        cleaned_foot_heights = foot_roll_lowest_heights_from_vec(store, pred_vec) if need_foot_heights else None
        pin_mask = None
        if need_pin_mask:
            pin_mask = (
                foot_pin_mask_from_heights_and_logits(cleaned_foot_heights, pin_logits)
                if cleaned_foot_heights is not None
                else foot_pin_mask_from_logits(pin_logits)
            )
        foot_unpin_rows = soft_any_foot_unpin_rows(pin_logits) if need_foot_unpin_rows else None
        if debug_capture is not None:
            debug_capture["vectors"][:, step + 1, :].copy_(pred_vec.detach())
            debug_frame_idx = cur_idx + 1 if output_uses_future_root else cur_idx
            debug_capture["frame_idx"][:, step + 1].copy_(debug_frame_idx.detach())
            debug_capture["pin_logits"][:, step + 1, :].copy_(pin_logits.detach())
            assert pin_mask is not None
            debug_capture["pin_mask"][:, step + 1, :].copy_(pin_mask.detach())
            debug_capture["reset_flags"][:, step + 1].zero_()
        part_started = mark_profile("loss_model_forward", part_started)
        raw_feature = torch.cat((inp, pred_vec), dim=-1)
        part_started = mark_profile("loss_clean_output", part_started)
        cur_output_vec = (
            current_state_as_transition_output(store, clip_ids, cur_idx, cur_vec)
            if has_identity or has_rl or PRIMARY_LOSS_MODE == PRIMARY_LOSS_MODE_GT_MSE
            else cur_vec
        )
        segment_next = segment_step + 1
        segment_terminal = segment_next >= effective_k
        active = torch.ones_like(effective_k, dtype=torch.bool)
        active_f = active.float()
        part_started = mark_profile("loss_current_output_active", part_started)
        if AE_TERMINAL_ONLY:
            ae_step_weight = segment_terminal.to(dtype=active_f.dtype) * effective_k_f.clamp_min(1.0)
        else:
            ae_step_weight = active_f
        ae_metric_weight = row_weight * ae_step_weight
        ae_step_scores = True if mixed_rollout_enabled(int(max_k)) else ae_rollout_step_may_score(step, max_k)
        ae3_phase_scale, ae4_bank_pin_phase_scale = ae3_bank_pin_phase_scale_for_segment_rows(
            effective_k,
            segment_step,
        )
        if not (ae3_enabled and ae4_bank_pin_enabled):
            ae3_phase_scale = torch.ones_like(ae3_phase_scale)
            ae4_bank_pin_phase_scale = torch.ones_like(ae4_bank_pin_phase_scale)
        row_step_loss = torch.zeros((int(batch_size),), dtype=torch.float32, device=store.device)
        foot_unpin_penalty = torch.zeros_like(total_loss)
        if foot_unpin_rows is not None:
            foot_unpin_scale = float(FOOT_UNPIN_PENALTY_WEIGHT)
            foot_unpin_penalty = (foot_unpin_rows * row_weight * active_f).sum() * foot_unpin_scale
            foot_unpin_penalty_total = foot_unpin_penalty_total + foot_unpin_penalty
            foot_unpin_soft_rate_total = foot_unpin_soft_rate_total + (
                foot_unpin_rows.detach() * row_weight * active_f
            ).sum()
            if foot_unpin_enabled:
                row_step_loss = row_step_loss + foot_unpin_rows.float() * foot_unpin_scale
        cur_root_pos = cur_root_rot = next_frame_root_pos = next_frame_root_rot = None
        pinned_foot_intent_loss = torch.zeros_like(total_loss)
        if pinned_foot_intent_enabled:
            raw_clean_vec = clean_output_vector(raw_pred, store, cur_vec, prev_vec)
            cur_root_pos, cur_root_rot, _cur_yaw, _cur_heading = store.root_state(clip_ids, cur_idx)
            next_frame_root_pos, next_frame_root_rot, _next_yaw, _next_heading = store.root_state(
                clip_ids, cur_idx + 1
            )
            if output_uses_current_root:
                output_root_pos, output_root_rot = cur_root_pos, cur_root_rot
            else:
                output_root_pos, output_root_rot = next_frame_root_pos, next_frame_root_rot
            intent_rows, intent_mps_rows = pinned_foot_intent_motion_rows(
                store,
                cur_root_pos,
                cur_root_rot,
                output_root_pos,
                output_root_rot,
                cur_vec,
                raw_clean_vec,
                pin_logits,
            )
            intent_raw = (intent_rows * row_weight * active_f).sum()
            intent_scale = float(PINNED_FOOT_INTENT_PENALTY_WEIGHT)
            pinned_foot_intent_loss = intent_raw * intent_scale
            pinned_foot_intent_total = pinned_foot_intent_total + pinned_foot_intent_loss
            pinned_foot_intent_raw_total = pinned_foot_intent_raw_total + intent_raw.detach()
            pinned_foot_intent_mps_total = pinned_foot_intent_mps_total + (
                intent_mps_rows * row_weight * active_f
            ).sum().detach()
            row_step_loss = row_step_loss + intent_rows.float() * intent_scale
        slide_tentative_loss = torch.zeros_like(total_loss)
        if slide_tentative_enabled:
            assert raw_clean_vec is not None
            assert pin_mask is not None
            slide_rows, slide_pin_rate_rows = slide_tentative_projection_correction_rows(
                store,
                raw_clean_vec,
                pred_vec,
                pin_mask,
            )
            slide_metric_weight = row_weight * active_f
            slide_scale = weight_scale(
                loss_weight_tensors,
                "slide_tentative_loss_weight",
                slide_tentative_loss_weight,
                pred_vec.dtype,
            )
            slide_tentative_loss = (slide_rows * slide_metric_weight).sum() * slide_scale
            slide_tentative_total = slide_tentative_total + slide_tentative_loss
            slide_tentative_raw_total = slide_tentative_raw_total + (
                slide_rows.detach() * slide_metric_weight
            ).sum()
            slide_tentative_pin_rate_total = slide_tentative_pin_rate_total + (
                slide_pin_rate_rows.detach() * slide_metric_weight
            ).sum()
            row_step_loss = row_step_loss + slide_rows.float() * slide_scale
        pinned_foot_height_loss = torch.zeros_like(total_loss)
        if pinned_foot_height_enabled:
            assert cleaned_foot_heights is not None
            smooth_heights = foot_roll_smooth_lowest_heights_from_vec(store, pred_vec)
            height_loss_heights = cleaned_foot_heights.detach() + smooth_heights - smooth_heights.detach()
            height_rows, height_raw_rows = pinned_foot_height_loss_rows(height_loss_heights, pin_logits)
            height_scale = weight_scale(
                loss_weight_tensors,
                "pinned_foot_height_weight",
                pinned_foot_height_weight,
                pred_vec.dtype,
            )
            height_metric_weight = row_weight * active_f
            pinned_foot_height_loss = (height_rows * height_metric_weight).sum() * height_scale
            pinned_foot_height_total = pinned_foot_height_total + pinned_foot_height_loss
            pinned_foot_height_raw_total = pinned_foot_height_raw_total + (
                height_raw_rows.detach() * height_metric_weight
            ).sum()
            pinned_foot_height_max_total = torch.maximum(
                pinned_foot_height_max_total,
                (pinned_foot_height_max_m_rows(cleaned_foot_heights, pin_logits).detach() * active_f).amax(),
            )
            row_step_loss = row_step_loss + height_rows.float() * height_scale
        idle_foot_flatness_loss = torch.zeros_like(total_loss)
        if idle_foot_flatness_enabled:
            flatness_rows, flatness_raw_rows = idle_foot_flatness_loss_rows(store, clip_ids, pred_vec, pin_logits)
            flatness_batch_scale = idle_foot_flatness_batch_scale(batch_size)
            flatness_scale = (
                weight_scale(
                    loss_weight_tensors,
                    "idle_foot_flatness_weight",
                    idle_foot_flatness_weight,
                    pred_vec.dtype,
                )
                * flatness_batch_scale
            )
            flatness_metric_weight = row_weight * active_f
            idle_foot_flatness_loss = (flatness_rows * flatness_metric_weight).sum() * flatness_scale
            idle_foot_flatness_total = idle_foot_flatness_total + idle_foot_flatness_loss
            idle_foot_flatness_raw_total = idle_foot_flatness_raw_total + (
                flatness_raw_rows.detach() * flatness_metric_weight * flatness_batch_scale
            ).sum()
            idle_foot_flatness_max_total = torch.maximum(
                idle_foot_flatness_max_total,
                (flatness_raw_rows.detach() * active_f).amax(),
            )
            row_step_loss = row_step_loss + flatness_rows.float() * flatness_scale
        pin_dim = int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)
        previous_pin_mask_for_step = prev_pin_mask
        if (
            track_pin_contact_diagnostics
            and cleaned_foot_heights is not None
            and pin_mask is not None
            and int(cleaned_foot_heights.shape[-1]) >= pin_dim
        ):
            pin_count = pin_mask.to(dtype=active_f.dtype).sum(dim=-1)
            double_rows = (pin_count >= 2.0).to(dtype=active_f.dtype)
            single_rows = (pin_count == 1.0).to(dtype=active_f.dtype)
            min_height_rows = cleaned_foot_heights[..., :pin_dim].amin(dim=-1)
            any_pinned_rows = (pin_count >= 1.0).to(dtype=active_f.dtype)
            if previous_pin_mask_for_step is None:
                switch_rows = torch.zeros_like(active_f)
                unpin_after_double_rows = torch.zeros_like(active_f)
            else:
                prev_pin_count = previous_pin_mask_for_step.to(dtype=active_f.dtype).sum(dim=-1)
                switch_rows = (pin_mask != previous_pin_mask_for_step).any(dim=-1).to(dtype=active_f.dtype)
                unpin_after_double_rows = (
                    (prev_pin_count >= 2.0) & (pin_count < 2.0)
                ).to(dtype=active_f.dtype)
            metric_weight = row_weight * active_f
            pin_behavior_terms["pin_double_rate"] = pin_behavior_terms["pin_double_rate"] + (
                double_rows * metric_weight
            ).sum()
            pin_behavior_terms["pin_single_rate"] = pin_behavior_terms["pin_single_rate"] + (
                single_rows * metric_weight
            ).sum()
            pin_behavior_terms["pin_switch_rate"] = pin_behavior_terms["pin_switch_rate"] + (
                switch_rows * metric_weight
            ).sum()
            pin_behavior_terms["pin_unpin_after_double_rate"] = (
                pin_behavior_terms["pin_unpin_after_double_rate"] + (unpin_after_double_rows * metric_weight).sum()
            )
            assert stationary_both_pin_amount is not None
            pin_behavior_terms["pin_stationary_amount"] = pin_behavior_terms["pin_stationary_amount"] + (
                stationary_both_pin_amount.detach() * metric_weight
            ).sum()
            foot_contact_terms["foot_contact_min_height_m"] = foot_contact_terms["foot_contact_min_height_m"] + (
                min_height_rows.detach() * metric_weight
            ).sum()
            foot_contact_terms["foot_contact_any_pinned_rate"] = foot_contact_terms["foot_contact_any_pinned_rate"] + (
                any_pinned_rows * metric_weight
            ).sum()
            foot_contact_terms["foot_contact_left_pinned_rate"] = foot_contact_terms["foot_contact_left_pinned_rate"] + (
                pin_mask[:, 0].to(dtype=active_f.dtype) * metric_weight
            ).sum()
            foot_contact_terms["foot_contact_right_pinned_rate"] = foot_contact_terms["foot_contact_right_pinned_rate"] + (
                pin_mask[:, 1].to(dtype=active_f.dtype) * metric_weight
            ).sum()
            prev_pin_mask = pin_mask
        contact_height_loss = torch.zeros_like(total_loss)
        if contact_height_loss_enabled and cleaned_foot_heights is not None:
            contact_height_rows = foot_contact_min_height_loss_rows(cleaned_foot_heights)
            contact_height_loss = (contact_height_rows * row_weight * active_f).sum()
            foot_contact_terms[FOOT_CONTACT_HEIGHT_LOSS_TERM_NAME] = (
                foot_contact_terms[FOOT_CONTACT_HEIGHT_LOSS_TERM_NAME] + contact_height_loss
            )
            row_step_loss = row_step_loss + contact_height_rows.float()
        ae_loss = torch.zeros_like(total_loss)
        ae_pose_loss = torch.zeros_like(total_loss)
        ae_velocity_loss = torch.zeros_like(total_loss)
        ae_rows_for_root_accel_scale: torch.Tensor | None = None
        if ae_step_scores and float(ae_loss_weight) != 0.0:
            ae_scale = weight_scale(loss_weight_tensors, "ae_loss_weight", ae_loss_weight, pred_vec.dtype)
            gt_mse_rows: torch.Tensor | None = None
            if primary_loss_uses_gt_mse():
                target_vec = transition_target_output(store, clip_ids, cur_idx)
                gt_cur_vec, _gt_cur_pelvis, _gt_cur_payload = target_state(store, clip_ids, cur_idx)
                gt_cur_output_vec = current_state_as_transition_output(store, clip_ids, cur_idx, gt_cur_vec)
                gt_mse_rows, gt_mse_terms = gt_mse_tracking_loss_rows(
                    store,
                    cur_output_vec,
                    pred_vec,
                    target_vec,
                    gt_cur_output_vec,
                )
                gt_mse_scope = gt_mse_row_scope_mask(row_weight, dedicated_real_rows, periodic_reserved_rows)
                gt_mse_metric_weight = ae_metric_weight * gt_mse_scope
                gt_mse_loss = (gt_mse_rows * gt_mse_metric_weight).sum() * ae_scale
                gt_mse_weighted_total = gt_mse_weighted_total + gt_mse_loss
                gt_mse_raw_total = gt_mse_raw_total + (gt_mse_terms[GT_MSE_RAW_TERM_NAME].detach() * gt_mse_metric_weight).sum()
                gt_mse_pos_total = gt_mse_pos_total + (gt_mse_terms[GT_MSE_POS_TERM_NAME].detach() * gt_mse_metric_weight).sum()
                gt_mse_rot_total = gt_mse_rot_total + (gt_mse_terms[GT_MSE_ROT_TERM_NAME].detach() * gt_mse_metric_weight).sum()
                gt_mse_linvel_total = gt_mse_linvel_total + (gt_mse_terms[GT_MSE_LINVEL_TERM_NAME].detach() * gt_mse_metric_weight).sum()
                gt_mse_angvel_total = gt_mse_angvel_total + (gt_mse_terms[GT_MSE_ANGVEL_TERM_NAME].detach() * gt_mse_metric_weight).sum()
                row_step_loss = row_step_loss + gt_mse_rows.float() * ae_scale * ae_step_weight * gt_mse_scope
                if PRIMARY_LOSS_MODE == PRIMARY_LOSS_MODE_GT_MSE:
                    ae_rows_for_root_accel_scale = gt_mse_rows
                    ae_raw_total = ae_raw_total + (gt_mse_rows * gt_mse_metric_weight).sum()
                    ae_pose_loss = gt_mse_loss
                    ae_loss = ae_loss + ae_pose_loss
                else:
                    ae_loss = ae_loss + gt_mse_loss
            if primary_loss_uses_ae1():
                ae_rows = ae_score_rows(ae, mean, std, inp, pred_vec, ae_context, store)
                ae_rows_for_root_accel_scale = ae_rows
                ae_raw_total = ae_raw_total + (ae_rows * ae_metric_weight).sum()
                ae_pose_loss = (ae_rows * ae_metric_weight).sum() * ae_scale
                row_step_loss = row_step_loss + ae_rows.float() * ae_scale * ae_step_weight
                ae_loss = ae_loss + ae_pose_loss
        if (
            ae_step_scores
            and extra_ae is not None
            and extra_mean is not None
            and extra_std is not None
            and float(extra_ae_loss_weight) != 0.0
        ):
            extra_rows = ae_score_rows(extra_ae, extra_mean, extra_std, inp, pred_vec, ae_context, store)
            ae_velocity_loss = (
                extra_rows * ae_metric_weight
            ).sum() * float(extra_ae_loss_weight)
            row_step_loss = row_step_loss + extra_rows.float() * float(extra_ae_loss_weight) * ae_step_weight
            ae_loss = ae_loss + ae_velocity_loss
        ae6_loss = torch.zeros_like(total_loss)
        if (
            ae_step_scores
            and ae6 is not None
            and ae6_mean is not None
            and ae6_std is not None
            and float(ae6_loss_weight) != 0.0
        ):
            ae6_rows, _ae6_bce_rows, ae6_mae_rows, ae6_acc_rows = ae6_contact_loss_rows(
                ae6,
                ae6_mean,
                ae6_std,
                inp,
                pred_vec,
                pin_logits,
                ae_context,
            )
            ae6_scale = float(ae6_loss_weight)
            ae6_scope = ae6_row_scope_mask(row_weight, dedicated_real_rows, periodic_reserved_rows)
            ae6_metric_weight = ae_metric_weight * ae6_scope
            ae6_step_weight = ae_step_weight
            ae6_loss = (ae6_rows * ae6_metric_weight).sum() * ae6_scale
            ae6_score_total = ae6_score_total + (ae6_rows.detach() * ae6_metric_weight).sum()
            ae6_weighted_total = ae6_weighted_total + ae6_loss
            ae6_mae_total = ae6_mae_total + (ae6_mae_rows.detach() * ae6_metric_weight).sum()
            ae6_acc_total = ae6_acc_total + (ae6_acc_rows.detach() * ae6_metric_weight).sum()
            row_step_loss = row_step_loss + ae6_rows.float() * ae6_scale * ae6_step_weight * ae6_scope
            ae_loss = ae_loss + ae6_loss
        ae5_loss = torch.zeros_like(total_loss)
        ae5_motion_context_next = ae5_motion_context
        if (
            ae5_motion_enabled
            and ae5 is not None
            and ae5_mean is not None
            and ae5_std is not None
            and ae5_motion_context is not None
        ):
            ae5_row_count = int(ae5_motion_row_count)
            if ae5_row_count > 0:
                ae5_slice = slice(ae5_motion_row_start, ae5_motion_row_start + ae5_row_count)
                ae5_row = ik_motion_ae_window_feature_rows(
                    ae5,
                    store,
                    cur_vec[ae5_slice],
                    pred_vec[ae5_slice],
                    clip_ids[ae5_slice],
                    cur_idx[ae5_slice],
                )
                ae5_motion_context_next = torch.cat((ae5_motion_context[:, 1:, :], ae5_row[:, None, :]), dim=1)
                if step + 1 >= int(ae5_frames):
                    ae5_window = ik_motion_ae2_window_rows(ae5_motion_context, ae5_row)
                    ae5_segment_valid = (
                        (segment_next[ae5_slice] >= int(ae5_frames))
                        & (effective_k[ae5_slice] >= int(ae5_frames))
                    ).to(dtype=row_weight.dtype)
                    ae5_scope = periodic_dataset_row_scope_rows(store, clip_ids[ae5_slice], row_weight.dtype)
                    ae5_valid = ae5_segment_valid * ae5_scope * active_f[ae5_slice]
                    ae5_rows = ik_motion_ae2_score_window_rows(
                        ae5,
                        ae5_mean,
                        ae5_std,
                        ae5_window,
                        None,
                    )
                    ae5_metric_weight = scoped_row_metric_weight(
                        row_weight[ae5_slice],
                        ae5_segment_valid * active_f[ae5_slice],
                        ae5_scope,
                        batch_count_override=batch_size,
                    )
                    ae5_loss = (ae5_rows * ae5_metric_weight).sum() * float(ae5_loss_weight)
                    ae5_score_total = ae5_score_total + (ae5_rows.detach() * ae5_metric_weight).sum()
                    ae5_weighted_total = ae5_weighted_total + ae5_loss
                    ae5_active_rate_total = ae5_active_rate_total + (
                        ae5_valid.detach() * row_weight[ae5_slice]
                    ).sum()
                    ae_loss = ae_loss + ae5_loss
        elif (
            ae5_enabled
            and step + 1 >= int(ae5_frames)
            and ae5 is not None
            and ae5_mean is not None
            and ae5_std is not None
            and ae5_context is not None
        ):
            ae5_row_count = (
                int(batch_size)
                if ae5_reserved_rows is None
                else max(0, min(int(batch_size), int(ae5_reserved_rows)))
            )
            ae5_row_start = max(0, min(int(batch_size), int(ae5_reserved_row_start)))
            ae5_row_count = max(0, min(int(batch_size) - ae5_row_start, int(ae5_row_count)))
            if ae5_row_count > 0:
                ae5_slice = slice(ae5_row_start, ae5_row_start + ae5_row_count)
                ae5_segment_valid = (
                    (segment_next[ae5_slice] >= int(ae5_frames))
                    & (effective_k[ae5_slice] >= int(ae5_frames))
                ).to(dtype=row_weight.dtype)
                ae5_scope = periodic_dataset_row_scope_rows(store, clip_ids[ae5_slice], row_weight.dtype)
                ae5_valid = ae5_segment_valid * ae5_scope * active_f[ae5_slice]
                ae5_rows = ae_score_rows(
                    ae5,
                    ae5_mean,
                    ae5_std,
                    inp[ae5_slice],
                    pred_vec[ae5_slice],
                    ae5_context[ae5_slice],
                    store,
                )
                ae5_metric_weight = scoped_row_metric_weight(
                    row_weight[ae5_slice],
                    ae5_segment_valid * active_f[ae5_slice],
                    ae5_scope,
                    batch_count_override=batch_size,
                )
                ae5_loss = (ae5_rows * ae5_metric_weight).sum() * float(ae5_loss_weight)
                ae5_score_total = ae5_score_total + (ae5_rows.detach() * ae5_metric_weight).sum()
                ae5_weighted_total = ae5_weighted_total + ae5_loss
                ae5_active_rate_total = ae5_active_rate_total + (
                    ae5_valid.detach() * row_weight[ae5_slice]
                ).sum()
                ae_loss = ae_loss + ae5_loss
        ae2_loss = torch.zeros_like(total_loss)
        ae2_context_next = ae2_context
        if ae2_enabled and ae2_context is not None and ae2 is not None and ae2_mean is not None and ae2_std is not None:
            ae2_row = ik_motion_ae2_feature_rows(store, cur_vec, pred_vec)
            ae2_window = ik_motion_ae2_window_rows(ae2_context, ae2_row)
            ae2_context_next = torch.cat((ae2_context[:, 1:, :], ae2_row[:, None, :]), dim=1)
            if step + 1 >= ae2_window_frames:
                ae2_valid = (
                    (segment_next >= int(ae2_window_frames)).float()
                    * (effective_k > segment_next).float()
                    * active_f
                ).to(dtype=row_weight.dtype)
                ae2_rows = ik_motion_ae2_score_window_rows(ae2, ae2_mean, ae2_std, ae2_window, ae2_window_weights)
                ae2_scale = float(ae2_loss_weight)
                ae2_loss = (ae2_rows * row_weight * ae2_valid).sum() * ae2_scale
                ae2_weighted_total = ae2_weighted_total + ae2_loss
                row_step_loss = row_step_loss + ae2_rows.float() * ae2_scale * ae2_valid
        ae3_loss = torch.zeros_like(total_loss)
        if ae3_enabled and ae3 is not None and ae3_mean is not None and ae3_std is not None:
            ae3_valid = ((effective_k > segment_next).float() * active_f * ae3_phase_scale).to(
                dtype=row_weight.dtype
            )
            ae3_rows = pin_aware_ae3_score_rows(
                ae3, ae3_mean, ae3_std, ae3_pos_weight, inp, store, pred_vec, pin_logits, cleaned_foot_heights
            )
            ae3_scale = float(ae3_loss_weight)
            ae3_loss = (ae3_rows * row_weight * ae3_valid).sum() * ae3_scale
            ae3_weighted_total = ae3_weighted_total + ae3_loss
            row_step_loss = row_step_loss + ae3_rows.float() * ae3_scale * ae3_valid
        leg_crossing_capsule_loss = torch.zeros_like(total_loss)
        if leg_crossing_capsule_enabled:
            capsule_rows, capsule_raw_rows, capsule_rate_rows = leg_crossing_capsule_loss_rows(
                store,
                pred_vec,
            )
            capsule_metric_weight = row_weight * active_f
            capsule_scale = weight_scale(
                loss_weight_tensors,
                "leg_crossing_capsule_loss_weight",
                leg_crossing_capsule_loss_weight,
                pred_vec.dtype,
            )
            leg_crossing_capsule_loss = (capsule_rows * capsule_metric_weight).sum() * capsule_scale
            leg_crossing_capsule_total = leg_crossing_capsule_total + leg_crossing_capsule_loss
            leg_crossing_capsule_raw_total = leg_crossing_capsule_raw_total + (
                capsule_raw_rows.detach() * capsule_metric_weight
            ).sum()
            leg_crossing_capsule_rate_total = leg_crossing_capsule_rate_total + (
                capsule_rate_rows.detach() * capsule_metric_weight
            ).sum()
            row_step_loss = row_step_loss + capsule_rows.float() * capsule_scale
        pin_logit_gap_loss = torch.zeros_like(total_loss)
        if pin_logit_gap_enabled:
            gap_rows = pin_logit_gap_hinge_rows(pin_logits)
            real_scope = real_dataset_row_scope_rows(store, clip_ids, row_weight.dtype)
            gap_metric_weight = real_dataset_row_metric_weight(row_weight, active_f, real_scope)
            gap_scale = weight_scale(
                loss_weight_tensors,
                "pin_logit_gap_loss_weight",
                pin_logit_gap_loss_weight,
                pred_vec.dtype,
            )
            pin_logit_gap_loss = (gap_rows * gap_metric_weight).sum() * gap_scale
            pin_logit_gap_total = pin_logit_gap_total + pin_logit_gap_loss
            pin_logit_gap_raw_total = pin_logit_gap_raw_total + (gap_rows.detach() * gap_metric_weight).sum()
            pin_logit_gap_bad_rate_total = pin_logit_gap_bad_rate_total + (
                (gap_rows.detach() > 0.0).to(dtype=row_weight.dtype) * gap_metric_weight
            ).sum()
            row_step_loss = row_step_loss + gap_rows.float() * gap_scale * real_scope.float()
        inertia_acceleration_loss = torch.zeros_like(total_loss)
        cur_inertia_linear_delta = None
        cur_inertia_angular_delta = None
        if inertia_acceleration_enabled:
            assert prev_inertia_linear_delta is not None and prev_inertia_angular_delta is not None
            cur_inertia_linear_delta, cur_inertia_angular_delta = inertia_transition_delta_rows(
                store,
                cur_vec,
                pred_vec,
            )
            (
                inertia_rows,
                inertia_linear_raw_rows,
                inertia_angular_raw_rows,
                inertia_bad_rows,
            ) = inertia_acceleration_excess_rows(
                store,
                prev_inertia_linear_delta,
                prev_inertia_angular_delta,
                cur_inertia_linear_delta,
                cur_inertia_angular_delta,
            )
            real_scope = real_dataset_row_scope_rows(store, clip_ids, row_weight.dtype)
            inertia_metric_weight = real_dataset_row_metric_weight(row_weight, active_f, real_scope)
            inertia_scale = (
                weight_scale(
                    loss_weight_tensors,
                    "inertia_acceleration_loss_weight",
                    inertia_acceleration_loss_weight,
                    pred_vec.dtype,
                )
                * float(INERTIA_ACCELERATION_LOSS_SCALE)
            )
            inertia_acceleration_loss = (inertia_rows * inertia_metric_weight).sum() * inertia_scale
            inertia_acceleration_total = inertia_acceleration_total + inertia_acceleration_loss
            inertia_acceleration_raw_total = inertia_acceleration_raw_total + (
                inertia_rows.detach() * inertia_metric_weight
            ).sum()
            inertia_linear_acceleration_raw_total = inertia_linear_acceleration_raw_total + (
                inertia_linear_raw_rows.detach() * inertia_metric_weight
            ).sum()
            inertia_angular_acceleration_raw_total = inertia_angular_acceleration_raw_total + (
                inertia_angular_raw_rows.detach() * inertia_metric_weight
            ).sum()
            inertia_acceleration_bad_rate_total = inertia_acceleration_bad_rate_total + (
                inertia_bad_rows.detach() * inertia_metric_weight
            ).sum()
            row_step_loss = row_step_loss + inertia_rows.float() * inertia_scale * real_scope.float()
        root_accel_pin_loss = torch.zeros_like(total_loss)
        if root_accel_pin_enabled and ae_rows_for_root_accel_scale is not None:
            assert cleaned_foot_heights is not None
            smooth_heights = foot_roll_smooth_lowest_heights_from_vec(store, pred_vec)
            (
                root_accel_pin_rows,
                root_accel_rows,
                root_accel_active_rows,
                root_accel_bad_rows,
                root_accel_max_pin_rows,
                root_accel_height_rows,
                _root_accel_gate_rows,
            ) = root_accel_pin_loss_rows(
                store,
                clip_ids,
                cur_idx,
                pin_logits,
                cleaned_foot_heights,
                smooth_heights,
            )
            root_accel_metric_weight = row_weight * active_f
            root_accel_raw = (root_accel_pin_rows * root_accel_metric_weight).sum()
            root_accel_scale = torch.full_like(
                root_accel_raw,
                float(ROOT_ACCEL_PIN_FIXED_LOSS_WEIGHT) * float(root_accel_pin_loss_ratio),
            )
            root_accel_pin_loss = root_accel_raw * root_accel_scale
            root_accel_pin_total = root_accel_pin_total + root_accel_pin_loss
            root_accel_pin_raw_total = root_accel_pin_raw_total + root_accel_raw.detach()
            root_accel_pin_scale_total = root_accel_pin_scale_total + root_accel_scale.detach()
            root_accel_pin_accel_total = root_accel_pin_accel_total + (
                root_accel_rows * root_accel_metric_weight
            ).sum()
            root_accel_pin_active_rate_total = root_accel_pin_active_rate_total + (
                root_accel_active_rows * root_accel_metric_weight
            ).sum()
            root_accel_pin_bad_rate_total = root_accel_pin_bad_rate_total + (
                root_accel_bad_rows * root_accel_metric_weight
            ).sum()
            root_accel_pin_max_prob_total = root_accel_pin_max_prob_total + (
                root_accel_max_pin_rows * root_accel_metric_weight
            ).sum()
            root_accel_pin_height_total = root_accel_pin_height_total + (
                root_accel_height_rows * root_accel_metric_weight
            ).sum()
            row_step_loss = row_step_loss + root_accel_pin_rows.float() * root_accel_scale.float()
        ae4_loss = torch.zeros_like(total_loss)
        ae4_bank_pin_loss = torch.zeros_like(total_loss)
        if (
            ae4_enabled
            and ae4 is not None
            and ae4_input_mean is not None
            and ae4_input_std is not None
            and ae4_target_mean is not None
            and ae4_target_std is not None
        ):
            idle_ae4_rows = idle_clip_mask_for_rows(store, clip_ids).to(dtype=pred_vec.dtype)
            ae4_deadzone_rows = (
                (1.0 - idle_ae4_rows) * float(AE4_POSE_DISTANCE_DEADZONE_M)
            )
            if ae4_uses_pose_bank_projector(ae4):
                ae4_rows, ae4_hinge_rows, ae4_bank_pin_labels = ik_pose_ae4_posebank_projection_rows(
                    ae4,
                    store,
                    clip_ids,
                    cur_idx,
                    pred_vec,
                    ae4_source_store=ae4_source_store,
                    ae4_source_clip_ids=ae4_source_clip_ids,
                    ae4_source_idx=ae4_source_idx,
                    deadzone_rows=ae4_deadzone_rows,
                )
            else:
                ae4_rows, ae4_hinge_rows = ik_pose_ae4_distance_and_hinge_rows(
                    ae4,
                    ae4_input_mean,
                    ae4_input_std,
                    ae4_target_mean,
                    ae4_target_std,
                    store,
                    clip_ids,
                    cur_idx,
                    cur_vec,
                    pred_vec,
                    ae4_source_store=ae4_source_store,
                    ae4_source_clip_ids=ae4_source_clip_ids,
                    ae4_source_idx=ae4_source_idx,
                    deadzone_rows=ae4_deadzone_rows,
                )
                ae4_bank_pin_labels = None
            ae4_scale = weight_scale(loss_weight_tensors, "ae4_loss_weight", ae4_loss_weight, pred_vec.dtype)
            ae4_metric_weight = row_weight * active_f
            ae4_score_total = ae4_score_total + (ae4_rows.detach() * ae4_metric_weight).sum()
            ae4_hinge_total = ae4_hinge_total + (ae4_hinge_rows.detach() * ae4_metric_weight).sum()
            ae4_loss = (ae4_hinge_rows * ae4_metric_weight).sum() * ae4_scale
            ae4_weighted_total = ae4_weighted_total + ae4_loss
            row_step_loss = row_step_loss + ae4_hinge_rows.float() * ae4_scale
            if ae4_bank_pin_enabled and ae4_bank_pin_labels is not None:
                ae4_bank_pin_rows = ae4_bank_pin_score_rows(pin_logits, ae4_bank_pin_labels)
                ae4_bank_pin_root_scale = ae4_bank_pin_root_delta_scale_rows(store, clip_ids, cur_idx).to(
                    dtype=ae4_bank_pin_rows.dtype
                )
                ae4_bank_pin_scale = weight_scale(
                    loss_weight_tensors,
                    "ae4_bank_pin_loss_weight",
                    ae4_bank_pin_loss_weight,
                    pred_vec.dtype,
                )
                ae4_bank_pin_scope = forced_idle_tail_row_scope_rows(
                    int(ae4_bank_pin_rows.shape[0]),
                    int(batch_size),
                    forced_idle_batch_fraction,
                    ae4_bank_pin_rows.device,
                    ae4_bank_pin_rows.dtype,
                ).detach()
                ae4_bank_pin_weighted_rows = (
                    ae4_bank_pin_rows
                    * ae4_bank_pin_root_scale.detach()
                    * ae4_bank_pin_phase_scale.detach()
                    * ae4_bank_pin_scope
                )
                ae4_bank_pin_loss = (ae4_bank_pin_weighted_rows * ae4_metric_weight).sum() * ae4_bank_pin_scale
                ae4_bank_pin_total = ae4_bank_pin_total + ae4_bank_pin_loss
                ae4_bank_pin_raw_total = ae4_bank_pin_raw_total + (
                    ae4_bank_pin_weighted_rows.detach() * ae4_metric_weight
                ).sum()
                ae4_bank_pin_root_scale_total = ae4_bank_pin_root_scale_total + (
                    ae4_bank_pin_root_scale.detach() * ae4_bank_pin_scope.detach() * ae4_metric_weight
                ).sum()
                row_step_loss = row_step_loss + ae4_bank_pin_weighted_rows.float() * ae4_bank_pin_scale
        part_started = mark_profile("loss_ae_score", part_started)
        if float(identity_loss_weight) != 0.0:
            identity_rows = (pred_vec - cur_output_vec).square().mean(dim=-1)
            identity_scale = weight_scale(loss_weight_tensors, "identity_loss_weight", identity_loss_weight, pred_vec.dtype)
            identity_loss = (
                identity_rows * row_weight * active.float()
            ).sum() * identity_scale
            row_step_loss = row_step_loss + identity_rows.float() * identity_scale
        else:
            identity_loss = None
        if float(identity_maxabs_weight) != 0.0:
            identity_maxabs_rows = (pred_vec - cur_output_vec).abs().amax(dim=-1)
            identity_maxabs_scale = weight_scale(
                loss_weight_tensors,
                "identity_maxabs_weight",
                identity_maxabs_weight,
                pred_vec.dtype,
            )
            identity_maxabs_loss = (
                identity_maxabs_rows * row_weight * active.float()
            ).sum() * identity_maxabs_scale
            row_step_loss = row_step_loss + identity_maxabs_rows.float() * identity_maxabs_scale
        else:
            identity_maxabs_loss = None
        if float(identity_world_pos_weight) != 0.0:
            identity_world_rows = identity_world_position_rows(store, clip_ids, cur_idx, pred_vec, cur_vec)
            identity_world_scale = weight_scale(
                loss_weight_tensors,
                "identity_world_pos_weight",
                identity_world_pos_weight,
                pred_vec.dtype,
            )
            identity_world_pos_loss = (
                identity_world_rows * row_weight * active_f
            ).sum() * identity_world_scale
            row_step_loss = row_step_loss + identity_world_rows.float() * identity_world_scale
        else:
            identity_world_pos_loss = None
        if float(identity_pelvis_pos_weight) != 0.0:
            identity_pelvis_rows = (pred_vec[:, :3] - cur_output_vec[:, :3]).square().sum(dim=-1)
            identity_pelvis_scale = weight_scale(
                loss_weight_tensors,
                "identity_pelvis_pos_weight",
                identity_pelvis_pos_weight,
                pred_vec.dtype,
            )
            identity_pelvis_pos_loss = (
                identity_pelvis_rows * row_weight * active_f
            ).sum() * identity_pelvis_scale
            row_step_loss = row_step_loss + identity_pelvis_rows.float() * identity_pelvis_scale
        else:
            identity_pelvis_pos_loss = None
        part_started = mark_profile("loss_identity_terms", part_started)
        if has_rl:
            rl_loss = compute_rl_loss(
                pred_vec,
                cur_output_vec,
                row_weight,
                active,
                rl_cfg,
                loss_weight_tensors,
                payload_slices=store.ik_payload_slices,
                payload_start=payload_slice(store).start,
            )
            rl_loss_total = rl_loss.total
            for key, value in rl_loss.terms.items():
                rl_terms[key] = rl_terms.get(key, torch.zeros_like(total_loss)) + value
        else:
            rl_loss_total = None
        part_started = mark_profile("loss_rl_terms", part_started)
        ae_total = ae_total + ae_loss
        ae_pose_total = ae_pose_total + ae_pose_loss
        ae_velocity_total = ae_velocity_total + ae_velocity_loss
        if identity_loss is not None:
            identity_total = identity_total + identity_loss
        if identity_maxabs_loss is not None:
            identity_maxabs_total = identity_maxabs_total + identity_maxabs_loss
        if identity_world_pos_loss is not None:
            identity_world_pos_total = identity_world_pos_total + identity_world_pos_loss
        if identity_pelvis_pos_loss is not None:
            identity_pelvis_pos_total = identity_pelvis_pos_total + identity_pelvis_pos_loss
        envelope_loss = torch.zeros_like(total_loss)
        alternating_loss = torch.zeros_like(total_loss)
        foot_lift_loss = torch.zeros_like(total_loss)
        anatomy_loss = torch.zeros_like(total_loss)
        if has_anatomy:
            anatomy_loss, step_anatomy_terms = ik_lower_length_loss_terms(
                store,
                pred_vec,
                row_weight,
                active_f,
                include_diagnostics=include_diagnostics,
                loss_weight=IK_LOWER_LENGTH_LOSS_WEIGHT,
                loss_weight_tensor=(
                    loss_weight_tensors.get("ik_lower_length_loss_weight")
                    if loss_weight_tensors is not None
                    else None
                ),
            )
            for key, value in step_anatomy_terms.items():
                anatomy_terms[key] = anatomy_terms.get(key, torch.zeros_like(total_loss)) + value
        part_started = mark_profile("loss_anatomy_terms", part_started)
        if has_envelope or has_alternating or has_foot_lift:
            if cur_root_pos is None or cur_root_rot is None:
                cur_root_pos, cur_root_rot, _cur_yaw, _cur_heading = store.root_state(clip_ids, cur_idx)
            if next_frame_root_pos is None or next_frame_root_rot is None:
                next_frame_root_pos, next_frame_root_rot, _gate_next_yaw, _gate_next_heading = store.root_state(
                    clip_ids, cur_idx + 1
                )
            if output_uses_current_root:
                output_root_pos, output_root_rot = cur_root_pos, cur_root_rot
            else:
                output_root_pos, output_root_rot = next_frame_root_pos, next_frame_root_rot
            cur_foot_pos, cur_foot_rot = env.ik_foot_toe_state_from_vec(store, cur_root_pos, cur_root_rot, cur_vec)
            next_foot_pos, next_foot_rot = env.ik_foot_toe_state_from_vec(
                store, output_root_pos, output_root_rot, pred_vec
            )
            part_started = mark_profile("loss_foot_state", part_started)
            envelope_diag = None
            envelope_active_f = active_f
            envelope_clip_ids = clip_ids
            envelope_cur_idx = cur_idx
            synthetic_flags = getattr(store, "synthetic", None)
            if envelope is not None and isinstance(synthetic_flags, torch.Tensor) and int(synthetic_flags.numel()) > 0:
                generated_rows = synthetic_flags.index_select(0, clip_ids.to(store.device).long())
                envelope_active_f = active_f * (~generated_rows).to(dtype=active_f.dtype)
                envelope_clip_ids = torch.where(generated_rows, torch.zeros_like(clip_ids), clip_ids)
                envelope_cur_idx = torch.where(generated_rows, torch.ones_like(cur_idx), cur_idx)
            if envelope is not None and (has_envelope or has_foot_lift):
                envelope_diag = env.envelope_diagnostics_ik_state_rows(
                    store,
                    envelope,  # type: ignore[arg-type]
                    cur_foot_pos,
                    cur_foot_rot,
                    next_foot_pos,
                    next_foot_rot,
                    envelope_clip_ids,
                    envelope_cur_idx,
                )
            root_still_gate = (
                root_still_gate_rows(store, cur_root_pos, next_frame_root_pos, alternating_root_cutoff_mps)
                if has_alternating or has_foot_lift
                else None
            )
            if has_envelope:
                linear_loss = torch.zeros_like(total_loss)
                angular_loss = torch.zeros_like(total_loss)
                height_loss = torch.zeros_like(total_loss)
                if float(linear_slide_weight) != 0.0 or float(angular_slide_weight) != 0.0:
                    assert envelope_diag is not None
                    linear_rows = envelope_diag["linear_excess_per_side_mps"].mean(dim=-1)
                    angular_rows = envelope_diag["angular_excess_per_side_radps"].mean(dim=-1)
                    linear_scale = weight_scale(loss_weight_tensors, "linear_slide_weight", linear_slide_weight, pred_vec.dtype)
                    angular_scale = weight_scale(
                        loss_weight_tensors,
                        "angular_slide_weight",
                        angular_slide_weight,
                        pred_vec.dtype,
                    )
                    linear_loss = (
                        (linear_rows * row_weight * envelope_active_f).sum()
                        * linear_scale
                    )
                    angular_loss = (angular_rows * row_weight * envelope_active_f).sum() * angular_scale
                    row_step_loss = row_step_loss + linear_rows.float() * linear_scale * envelope_active_f.float()
                    row_step_loss = row_step_loss + angular_rows.float() * angular_scale * envelope_active_f.float()
                if float(foot_height_weight) != 0.0:
                    assert envelope_diag is not None
                    height_rows = envelope_diag["height_excess_m"].mean(dim=-1)
                    height_scale = (
                        weight_scale(loss_weight_tensors, "foot_height_weight", foot_height_weight, pred_vec.dtype)
                        * FOOT_HEIGHT_LOSS_SCALE
                    )
                    height_loss = (
                        (height_rows * row_weight * envelope_active_f).sum()
                        * height_scale
                    )
                    row_step_loss = row_step_loss + height_rows.float() * height_scale * envelope_active_f.float()
                envelope_terms["linear_slide_weighted"] = envelope_terms["linear_slide_weighted"] + linear_loss
                envelope_terms["angular_slide_weighted"] = envelope_terms["angular_slide_weighted"] + angular_loss
                envelope_terms["foot_height_weighted"] = envelope_terms["foot_height_weighted"] + height_loss
                envelope_loss = linear_loss + angular_loss + height_loss
            part_started = mark_profile("loss_envelope_terms", part_started)
            if has_alternating:
                alternating_loss, step_alternating_terms = alternating_feet_loss_terms(
                    store,
                    cur_root_pos,
                    next_frame_root_pos,
                    cur_foot_pos,
                    next_foot_pos,
                    row_weight,
                    active_f,
                    alternating_feet_weight,
                    alternating_root_cutoff_mps,
                    include_diagnostics=include_diagnostics,
                    precomputed_root_still_gate=root_still_gate,
                    loss_weight_tensor=(
                        loss_weight_tensors.get("alternating_feet_weight")
                        if loss_weight_tensors is not None
                        else None
                    ),
                )
                for key, value in step_alternating_terms.items():
                    alternating_terms[key] = alternating_terms.get(key, torch.zeros_like(total_loss)) + value
            part_started = mark_profile("loss_alternating_terms", part_started)
            if has_foot_lift:
                terminal_gate = (
                    ((effective_k.to(dtype=segment_step.dtype) - segment_step).to(dtype=torch.float32)
                     <= float(TERMINAL_FOOT_STILLNESS_FRAMES)).float() * active_f
                )
                foot_lift_loss, step_foot_lift_terms = foot_lift_slide_loss_terms(
                    store,
                    envelope,
                    cur_root_pos,
                    next_frame_root_pos,
                    cur_foot_pos,
                    next_foot_pos,
                    next_foot_rot,
                    clip_ids,
                    cur_idx,
                    row_weight,
                    active_f,
                    foot_lift_slide_weight,
                    alternating_root_cutoff_mps,
                    terminal_gate,
                    include_diagnostics=include_diagnostics,
                    precomputed_foot_speeds=(
                        envelope_diag["height_speed_mps"] if envelope_diag is not None else None
                    ),
                    precomputed_heights=(envelope_diag["height_m"] if envelope_diag is not None else None),
                    precomputed_height_lower_bound=(
                        envelope_diag["height_lower_bound_m"] if envelope_diag is not None else None
                    ),
                    precomputed_root_still_gate=root_still_gate,
                    loss_weight_tensor=(
                        loss_weight_tensors.get("foot_lift_slide_weight")
                        if loss_weight_tensors is not None
                        else None
                    ),
                )
                for key, value in step_foot_lift_terms.items():
                    foot_lift_terms[key] = foot_lift_terms.get(key, torch.zeros_like(total_loss)) + value
            part_started = mark_profile("loss_foot_lift_terms", part_started)
        else:
            part_started = mark_profile("loss_foot_losses_skipped", part_started)
        total_loss = total_loss + ae_loss
        if identity_loss is not None:
            total_loss = total_loss + identity_loss
        if identity_maxabs_loss is not None:
            total_loss = total_loss + identity_maxabs_loss
        if identity_world_pos_loss is not None:
            total_loss = total_loss + identity_world_pos_loss
        if identity_pelvis_pos_loss is not None:
            total_loss = total_loss + identity_pelvis_pos_loss
        if rl_loss_total is not None:
            total_loss = total_loss + rl_loss_total
        total_loss = (
            total_loss
            + ae2_loss
            + ae3_loss
            + leg_crossing_capsule_loss
            + pin_logit_gap_loss
            + inertia_acceleration_loss
            + root_accel_pin_loss
            + ae4_loss
            + ae4_bank_pin_loss
            + envelope_loss
            + alternating_loss
            + foot_lift_loss
            + anatomy_loss
            + contact_height_loss
            + foot_unpin_penalty
            + pinned_foot_intent_loss
            + slide_tentative_loss
            + pinned_foot_height_loss
            + idle_foot_flatness_loss
        )
        row_loss_accum = row_loss_accum + row_step_loss * active_f
        part_started = mark_profile("loss_accumulate_total", part_started)
        if step + 1 >= max_k:
            break

        continuing = torch.ones_like(effective_k, dtype=torch.bool)
        if output_uses_future_root:
            next_vec = clean_output_vector(pred_vec, store)
        else:
            if cur_root_pos is None or cur_root_rot is None:
                cur_root_pos, cur_root_rot, _cur_yaw, _cur_heading = store.root_state(clip_ids, cur_idx)
            if next_frame_root_pos is None or next_frame_root_rot is None:
                next_frame_root_pos, next_frame_root_rot, _next_yaw, _next_heading = store.root_state(
                    clip_ids, cur_idx + 1
                )
            next_vec = rebase_output_vector_root(
                store,
                pred_vec,
                cur_root_pos,
                cur_root_rot,
                next_frame_root_pos,
                next_frame_root_rot,
        )
        next_pelvis, next_payload = next_vec[:, :3], next_vec[:, payload_slice(store)]
        reset = training_reset_rows(store, clip_ids, cur_idx, continuing) | segment_terminal
        if debug_capture is not None:
            debug_capture["reset_flags"][:, step + 1].copy_(reset.detach())
        advance = continuing & (~reset)
        reset_starts = (
            reset_starts_by_step[step]
            if reset_starts_by_step is not None
            else sample_same_clip_training_starts(
                store,
                clip_ids,
                ae_required_context_frames,
                (effective_k - segment_next).clamp_min(1),
            )
        )
        reset_prev_vec, reset_prev_pelvis, reset_prev_payload = target_state(store, clip_ids, reset_starts - 1)
        reset_cur_vec, reset_cur_pelvis, reset_cur_payload = target_state(store, clip_ids, reset_starts)
        random_reset_mask = None
        random_reset_starts = None
        random_reset_clip_ids = None
        if (
            random_init_rows is not None
            and random_reset_clip_ids_by_step is not None
            and random_reset_starts_by_step is not None
        ):
            random_reset_mask = random_init_rows.to(device=store.device, dtype=torch.bool).reshape(-1)
            random_reset_clip_ids = random_reset_clip_ids_by_step[step].to(device=store.device, dtype=torch.long)
            random_reset_starts = random_reset_starts_by_step[step].to(device=store.device, dtype=torch.long)
            random_prev_vec, random_prev_pelvis, random_prev_payload = target_state(
                store, random_reset_clip_ids, random_reset_starts - 1
            )
            random_cur_vec, random_cur_pelvis, random_cur_payload = target_state(
                store, random_reset_clip_ids, random_reset_starts
            )
            random_reset_mask_vec = random_reset_mask[:, None]
            reset_prev_vec = torch.where(random_reset_mask_vec, random_prev_vec, reset_prev_vec)
            reset_prev_pelvis = torch.where(random_reset_mask_vec, random_prev_pelvis, reset_prev_pelvis)
            reset_prev_payload = torch.where(random_reset_mask_vec, random_prev_payload, reset_prev_payload)
            reset_cur_vec = torch.where(random_reset_mask_vec, random_cur_vec, reset_cur_vec)
            reset_cur_pelvis = torch.where(random_reset_mask_vec, random_cur_pelvis, reset_cur_pelvis)
            reset_cur_payload = torch.where(random_reset_mask_vec, random_cur_payload, reset_cur_payload)
        if init_pose_noise_batch is not None:
            reset_prev_vec = apply_init_pose_noise_batch(store, reset_prev_vec, init_pose_noise_batch)
            reset_cur_vec = apply_init_pose_noise_batch(store, reset_cur_vec, init_pose_noise_batch)
            reset_prev_pelvis = reset_prev_vec[:, :3]
            reset_cur_pelvis = reset_cur_vec[:, :3]
            vec_payload_slice = payload_slice(store)
            reset_prev_payload = reset_prev_vec[:, vec_payload_slice]
            reset_cur_payload = reset_cur_vec[:, vec_payload_slice]
        if ae_context is not None:
            shifted_context = torch.cat((ae_context[:, 1:, :], raw_feature[:, None, :]), dim=1)
            reset_context = initial_ae_context(store, clip_ids, reset_starts, ae_frames)
            assert reset_context is not None
            if random_reset_mask is not None and random_reset_clip_ids is not None and random_reset_starts is not None:
                random_reset_context = initial_ae_context(store, random_reset_clip_ids, random_reset_starts, ae_frames)
                assert random_reset_context is not None
                reset_context = torch.where(random_reset_mask[:, None, None], random_reset_context, reset_context)
            reset_mask_ctx = reset[:, None, None]
            advance_mask_ctx = advance[:, None, None]
            ae_context = torch.where(reset_mask_ctx, reset_context, torch.where(advance_mask_ctx, shifted_context, ae_context))
        if ae5_context is not None and not ae5_motion_enabled:
            shifted_ae5_context = torch.cat((ae5_context[:, 1:, :], raw_feature[:, None, :]), dim=1)
            reset_ae5_context = initial_ae_context(store, clip_ids, reset_starts, ae5_frames)
            assert reset_ae5_context is not None
            if random_reset_mask is not None and random_reset_clip_ids is not None and random_reset_starts is not None:
                random_reset_ae5_context = initial_ae_context(
                    store, random_reset_clip_ids, random_reset_starts, ae5_frames
                )
                assert random_reset_ae5_context is not None
                reset_ae5_context = torch.where(
                    random_reset_mask[:, None, None],
                    random_reset_ae5_context,
                    reset_ae5_context,
                )
            reset_mask_ctx = reset[:, None, None]
            advance_mask_ctx = advance[:, None, None]
            ae5_context = torch.where(
                reset_mask_ctx,
                reset_ae5_context,
                torch.where(advance_mask_ctx, shifted_ae5_context, ae5_context),
            )
        if ae5_motion_context_next is not None:
            reset_ae5_motion_context = torch.zeros_like(ae5_motion_context_next)
            reset_mask_ctx = reset[:ae5_motion_row_count, None, None]
            advance_mask_ctx = advance[:ae5_motion_row_count, None, None]
            ae5_motion_context = torch.where(
                reset_mask_ctx,
                reset_ae5_motion_context,
                torch.where(advance_mask_ctx, ae5_motion_context_next, ae5_motion_context),
            )
        if ae2_context_next is not None:
            reset_ae2_context = torch.zeros_like(ae2_context_next)
            reset_mask_ctx = reset[:, None, None]
            advance_mask_ctx = advance[:, None, None]
            ae2_context = torch.where(
                reset_mask_ctx,
                reset_ae2_context,
                torch.where(advance_mask_ctx, ae2_context_next, ae2_context),
            )
        if inertia_acceleration_enabled:
            assert cur_inertia_linear_delta is not None and cur_inertia_angular_delta is not None
            assert prev_inertia_linear_delta is not None and prev_inertia_angular_delta is not None
            reset_linear_delta, reset_angular_delta = inertia_transition_delta_rows(store, reset_prev_vec, reset_cur_vec)
            reset_mask_inertia = reset[:, None, None]
            advance_mask_inertia = advance[:, None, None]
            prev_inertia_linear_delta = torch.where(
                reset_mask_inertia,
                reset_linear_delta,
                torch.where(advance_mask_inertia, cur_inertia_linear_delta, prev_inertia_linear_delta),
            )
            prev_inertia_angular_delta = torch.where(
                reset_mask_inertia,
                reset_angular_delta,
                torch.where(advance_mask_inertia, cur_inertia_angular_delta, prev_inertia_angular_delta),
            )
        reset_mask = reset[:, None]
        advance_mask = advance[:, None]
        prev_vec = torch.where(reset_mask, reset_prev_vec, torch.where(advance_mask, cur_vec, prev_vec))
        prev_pelvis = torch.where(reset_mask, reset_prev_pelvis, torch.where(advance_mask, cur_pelvis, prev_pelvis))
        prev_payload = torch.where(reset_mask, reset_prev_payload, torch.where(advance_mask, cur_payload, prev_payload))
        cur_vec = torch.where(reset_mask, reset_cur_vec, torch.where(advance_mask, next_vec, cur_vec))
        cur_pelvis = torch.where(reset_mask, reset_cur_pelvis, torch.where(advance_mask, next_pelvis, cur_pelvis))
        cur_payload = torch.where(reset_mask, reset_cur_payload, torch.where(advance_mask, next_payload, cur_payload))
        cur_idx = torch.where(reset, reset_starts, cur_idx + 1)
        ae4_source_idx = torch.where(
            reset,
            reset_starts,
            ae4_source_idx + 1,
        )
        segment_step = torch.where(reset, torch.zeros_like(segment_step), segment_next)
        part_started = mark_profile("loss_advance_state", part_started)
    if profile_loss:
        PRETRAIN_LOSS_PROFILE_EMITTED = True
        profile_times["loss_total_profiled"] = time.perf_counter() - profile_started
        for name, delta_s in sorted(profile_times.items(), key=lambda item: item[1], reverse=True):
            emit_pretrain_arm_delta(f"profile_{name}", delta_s)
    if not total_loss.requires_grad:
        total_loss = total_loss + pred_vec.sum() * 0.0
    return ControllerLossResult(
        total=total_loss,
        terms={
            "ae_score": ae_raw_total,
            AE_POSE_TERM_NAME: ae_pose_total,
            AE_VELOCITY_TERM_NAME: ae_velocity_total,
            GT_MSE_WEIGHTED_TERM_NAME: gt_mse_weighted_total,
            GT_MSE_RAW_TERM_NAME: gt_mse_raw_total,
            GT_MSE_POS_TERM_NAME: gt_mse_pos_total,
            GT_MSE_ROT_TERM_NAME: gt_mse_rot_total,
            GT_MSE_LINVEL_TERM_NAME: gt_mse_linvel_total,
            GT_MSE_ANGVEL_TERM_NAME: gt_mse_angvel_total,
            AE5_SCORE_TERM_NAME: ae5_score_total,
            AE5_WEIGHTED_TERM_NAME: ae5_weighted_total,
            AE5_ACTIVE_RATE_TERM_NAME: ae5_active_rate_total,
            AE6_CONTACT_SCORE_TERM_NAME: ae6_score_total,
            AE6_CONTACT_WEIGHTED_TERM_NAME: ae6_weighted_total,
            AE6_CONTACT_MAE_TERM_NAME: ae6_mae_total,
            AE6_CONTACT_ACC_TERM_NAME: ae6_acc_total,
            AE2_WEIGHTED_TERM_NAME: ae2_weighted_total,
            AE3_PIN_WEIGHTED_TERM_NAME: ae3_weighted_total,
            LEG_CROSSING_CAPSULE_TERM_NAME: leg_crossing_capsule_total,
            LEG_CROSSING_CAPSULE_RAW_TERM_NAME: leg_crossing_capsule_raw_total,
            LEG_CROSSING_CAPSULE_RATE_TERM_NAME: leg_crossing_capsule_rate_total,
            PIN_LOGIT_GAP_WEIGHTED_TERM_NAME: pin_logit_gap_total,
            PIN_LOGIT_GAP_RAW_TERM_NAME: pin_logit_gap_raw_total,
            PIN_LOGIT_GAP_BAD_RATE_TERM_NAME: pin_logit_gap_bad_rate_total,
            INERTIA_ACCELERATION_WEIGHTED_TERM_NAME: inertia_acceleration_total,
            INERTIA_ACCELERATION_RAW_TERM_NAME: inertia_acceleration_raw_total,
            INERTIA_LINEAR_ACCELERATION_RAW_TERM_NAME: inertia_linear_acceleration_raw_total,
            INERTIA_ANGULAR_ACCELERATION_RAW_TERM_NAME: inertia_angular_acceleration_raw_total,
            INERTIA_ACCELERATION_BAD_RATE_TERM_NAME: inertia_acceleration_bad_rate_total,
            ROOT_ACCEL_PIN_WEIGHTED_TERM_NAME: root_accel_pin_total,
            ROOT_ACCEL_PIN_RAW_TERM_NAME: root_accel_pin_raw_total,
            ROOT_ACCEL_PIN_SCALE_TERM_NAME: root_accel_pin_scale_total,
            ROOT_ACCEL_PIN_ACCEL_TERM_NAME: root_accel_pin_accel_total,
            ROOT_ACCEL_PIN_ACTIVE_RATE_TERM_NAME: root_accel_pin_active_rate_total,
            ROOT_ACCEL_PIN_BAD_RATE_TERM_NAME: root_accel_pin_bad_rate_total,
            ROOT_ACCEL_PIN_MAX_PROB_TERM_NAME: root_accel_pin_max_prob_total,
            ROOT_ACCEL_PIN_HEIGHT_TERM_NAME: root_accel_pin_height_total,
            AE4_POSE_SCORE_TERM_NAME: ae4_score_total,
            AE4_POSE_HINGE_TERM_NAME: ae4_hinge_total,
            AE4_POSE_WEIGHTED_TERM_NAME: ae4_weighted_total,
            AE4_BANK_PIN_WEIGHTED_TERM_NAME: ae4_bank_pin_total,
            AE4_BANK_PIN_RAW_TERM_NAME: ae4_bank_pin_raw_total,
            AE4_BANK_PIN_ROOT_SCALE_TERM_NAME: ae4_bank_pin_root_scale_total,
            IDENTITY_TERM_NAME: identity_total,
            IDENTITY_MAXABS_TERM_NAME: identity_maxabs_total,
            IDENTITY_WORLD_POS_TERM_NAME: identity_world_pos_total,
            IDENTITY_PELVIS_POS_TERM_NAME: identity_pelvis_pos_total,
            FOOT_UNPIN_PENALTY_TERM_NAME: foot_unpin_penalty_total,
            FOOT_UNPIN_SOFT_RATE_TERM_NAME: foot_unpin_soft_rate_total,
            PINNED_FOOT_INTENT_TERM_NAME: pinned_foot_intent_total,
            PINNED_FOOT_INTENT_RAW_TERM_NAME: pinned_foot_intent_raw_total,
            PINNED_FOOT_INTENT_MPS_TERM_NAME: pinned_foot_intent_mps_total,
            SLIDE_TENTATIVE_TERM_NAME: slide_tentative_total,
            SLIDE_TENTATIVE_RAW_TERM_NAME: slide_tentative_raw_total,
            SLIDE_TENTATIVE_PIN_RATE_TERM_NAME: slide_tentative_pin_rate_total,
            PINNED_FOOT_HEIGHT_TERM_NAME: pinned_foot_height_total,
            PINNED_FOOT_HEIGHT_RAW_TERM_NAME: pinned_foot_height_raw_total,
            PINNED_FOOT_HEIGHT_MAX_TERM_NAME: pinned_foot_height_max_total,
            IDLE_FOOT_FLATNESS_TERM_NAME: idle_foot_flatness_total,
            IDLE_FOOT_FLATNESS_RAW_TERM_NAME: idle_foot_flatness_raw_total,
            IDLE_FOOT_FLATNESS_MAX_TERM_NAME: idle_foot_flatness_max_total,
            **pin_behavior_terms,
            **foot_contact_terms,
            **rl_terms,
            **envelope_terms,
            **alternating_terms,
            **foot_lift_terms,
            **anatomy_terms,
        },
        row_losses=row_loss_accum / max_k_f,
    )


def cuda_graph_loss_term_names(
    rl_cfg: RLLossConfig,
    ae_loss_weight: float,
    extra_ae_loss_weight: float,
    envelope: dict[str, torch.Tensor | dict[str, float | int | str]] | None,
    linear_slide_weight: float,
    angular_slide_weight: float,
    foot_height_weight: float,
    alternating_feet_weight: float,
    foot_lift_slide_weight: float,
    identity_loss_weight: float,
    identity_maxabs_weight: float,
    identity_world_pos_weight: float,
    identity_pelvis_pos_weight: float,
    ae2_loss_weight: float = 0.0,
    ae3_loss_weight: float = 0.0,
    pin_logit_gap_loss_weight: float = 0.0,
    inertia_acceleration_loss_weight: float = 0.0,
    root_accel_pin_loss_ratio: float = 0.0,
    leg_crossing_capsule_loss_weight: float = 0.0,
    ae4_loss_weight: float = 0.0,
    ae4_bank_pin_loss_weight: float = 0.0,
    slide_tentative_loss_weight: float = 0.0,
    pinned_foot_height_weight: float = 0.0,
    idle_foot_flatness_weight: float = 0.0,
    ae5_loss_weight: float = 0.0,
    ae6_loss_weight: float = 0.0,
) -> tuple[str, ...]:
    # CUDA graph capture is the expensive path, so keep only values that are
    # weighted losses shown in the launcher. Extra diagnostic rates can still be
    # computed by eager/debug paths without becoming part of every graph replay.
    names: list[str] = []
    if float(ae_loss_weight) != 0.0 or float(extra_ae_loss_weight) != 0.0:
        names.append("ae_score")
        names.append(AE_POSE_TERM_NAME)
        if primary_loss_uses_gt_mse():
            names.extend(
                (
                    GT_MSE_WEIGHTED_TERM_NAME,
                    GT_MSE_RAW_TERM_NAME,
                    GT_MSE_POS_TERM_NAME,
                    GT_MSE_ROT_TERM_NAME,
                    GT_MSE_LINVEL_TERM_NAME,
                    GT_MSE_ANGVEL_TERM_NAME,
                )
            )
    if float(extra_ae_loss_weight) != 0.0:
        names.append(AE_VELOCITY_TERM_NAME)
    if float(ae5_loss_weight) != 0.0:
        names.extend((AE5_SCORE_TERM_NAME, AE5_WEIGHTED_TERM_NAME, AE5_ACTIVE_RATE_TERM_NAME))
    if float(ae6_loss_weight) != 0.0:
        names.extend(
            (
                AE6_CONTACT_SCORE_TERM_NAME,
                AE6_CONTACT_WEIGHTED_TERM_NAME,
                AE6_CONTACT_MAE_TERM_NAME,
                AE6_CONTACT_ACC_TERM_NAME,
            )
        )
    if float(ae2_loss_weight) != 0.0:
        names.append(AE2_WEIGHTED_TERM_NAME)
    if float(ae3_loss_weight) != 0.0:
        names.append(AE3_PIN_WEIGHTED_TERM_NAME)
    if float(leg_crossing_capsule_loss_weight) != 0.0:
        names.append(LEG_CROSSING_CAPSULE_TERM_NAME)
        names.append(LEG_CROSSING_CAPSULE_RAW_TERM_NAME)
        names.append(LEG_CROSSING_CAPSULE_RATE_TERM_NAME)
    if float(pin_logit_gap_loss_weight) != 0.0:
        names.append(PIN_LOGIT_GAP_WEIGHTED_TERM_NAME)
        names.append(PIN_LOGIT_GAP_RAW_TERM_NAME)
        names.append(PIN_LOGIT_GAP_BAD_RATE_TERM_NAME)
    if float(inertia_acceleration_loss_weight) != 0.0:
        names.append(INERTIA_ACCELERATION_WEIGHTED_TERM_NAME)
        names.append(INERTIA_ACCELERATION_RAW_TERM_NAME)
        names.append(INERTIA_LINEAR_ACCELERATION_RAW_TERM_NAME)
        names.append(INERTIA_ANGULAR_ACCELERATION_RAW_TERM_NAME)
        names.append(INERTIA_ACCELERATION_BAD_RATE_TERM_NAME)
    if float(root_accel_pin_loss_ratio) != 0.0:
        names.append(ROOT_ACCEL_PIN_WEIGHTED_TERM_NAME)
        names.append(ROOT_ACCEL_PIN_RAW_TERM_NAME)
        names.append(ROOT_ACCEL_PIN_SCALE_TERM_NAME)
        names.append(ROOT_ACCEL_PIN_ACCEL_TERM_NAME)
        names.append(ROOT_ACCEL_PIN_ACTIVE_RATE_TERM_NAME)
        names.append(ROOT_ACCEL_PIN_BAD_RATE_TERM_NAME)
        names.append(ROOT_ACCEL_PIN_MAX_PROB_TERM_NAME)
        names.append(ROOT_ACCEL_PIN_HEIGHT_TERM_NAME)
    if float(ae4_loss_weight) != 0.0:
        names.extend((AE4_POSE_SCORE_TERM_NAME, AE4_POSE_HINGE_TERM_NAME, AE4_POSE_WEIGHTED_TERM_NAME))
    if float(ae4_bank_pin_loss_weight) != 0.0:
        names.append(AE4_BANK_PIN_WEIGHTED_TERM_NAME)
        names.append(AE4_BANK_PIN_RAW_TERM_NAME)
        names.append(AE4_BANK_PIN_ROOT_SCALE_TERM_NAME)
    if float(FOOT_UNPIN_PENALTY_WEIGHT) != 0.0:
        names.append(FOOT_UNPIN_PENALTY_TERM_NAME)
        names.append(FOOT_UNPIN_SOFT_RATE_TERM_NAME)
    if float(PINNED_FOOT_INTENT_PENALTY_WEIGHT) != 0.0:
        names.append(PINNED_FOOT_INTENT_TERM_NAME)
        names.append(PINNED_FOOT_INTENT_RAW_TERM_NAME)
        names.append(PINNED_FOOT_INTENT_MPS_TERM_NAME)
    if float(slide_tentative_loss_weight) != 0.0:
        names.append(SLIDE_TENTATIVE_TERM_NAME)
        names.append(SLIDE_TENTATIVE_RAW_TERM_NAME)
        names.append(SLIDE_TENTATIVE_PIN_RATE_TERM_NAME)
    if float(pinned_foot_height_weight) != 0.0:
        names.append(PINNED_FOOT_HEIGHT_TERM_NAME)
        names.append(PINNED_FOOT_HEIGHT_RAW_TERM_NAME)
        names.append(PINNED_FOOT_HEIGHT_MAX_TERM_NAME)
    if float(idle_foot_flatness_weight) != 0.0:
        names.append(IDLE_FOOT_FLATNESS_TERM_NAME)
        names.append(IDLE_FOOT_FLATNESS_RAW_TERM_NAME)
        names.append(IDLE_FOOT_FLATNESS_MAX_TERM_NAME)
    if float(FOOT_CONTACT_MIN_HEIGHT_LOSS_MAX) != 0.0:
        names.append(FOOT_CONTACT_HEIGHT_LOSS_TERM_NAME)
    if float(identity_loss_weight) != 0.0:
        names.append(IDENTITY_TERM_NAME)
    if float(identity_maxabs_weight) != 0.0:
        names.append(IDENTITY_MAXABS_TERM_NAME)
    if float(identity_world_pos_weight) != 0.0:
        names.append(IDENTITY_WORLD_POS_TERM_NAME)
    if float(identity_pelvis_pos_weight) != 0.0:
        names.append(IDENTITY_PELVIS_POS_TERM_NAME)
    names.extend(rl_cfg.enabled_terms())
    if envelope is not None:
        if float(linear_slide_weight) != 0.0:
            names.append("linear_slide_weighted")
        if float(angular_slide_weight) != 0.0:
            names.append("angular_slide_weighted")
        if float(foot_height_weight) != 0.0:
            names.append("foot_height_weighted")
    if alternating_feet_loss_enabled(alternating_feet_weight):
        names.extend(ALTERNATING_FEET_LOSS_TERM_NAMES)
    if foot_lift_slide_loss_enabled(foot_lift_slide_weight):
        names.extend(FOOT_LIFT_SLIDE_LOSS_TERM_NAMES)
    if ik_lower_length_loss_enabled():
        names.extend(IK_LOWER_LENGTH_LOSS_TERM_NAMES)
    return tuple(dict.fromkeys(names))


class CudaGraphPureAEStep:
    kind = "cuda_graph_static_rolling_mixed"

    def __init__(
        self,
        model: torch.nn.Module,
        optimizer: torch.optim.Optimizer,
        ae: SimpleAutoencoder,
        mean: torch.Tensor,
        std: torch.Tensor,
        store: SimpleClipStore,
        rollout_k: int,
        batch_size: int,
        start_pools: dict[int, StartPool],
        full_window_start_pools: dict[int, StartPool] | None,
        rl_cfg: RLLossConfig,
        ae_loss_weight: float,
        envelope: dict[str, torch.Tensor | dict[str, float | int | str]] | None,
        linear_slide_weight: float,
        angular_slide_weight: float,
        foot_height_weight: float,
        alternating_feet_weight: float,
        foot_lift_slide_weight: float,
        pinned_foot_height_weight: float,
        idle_foot_flatness_weight: float,
        forced_idle_batch_fraction: float | None,
        forced_turn45_batch_fraction: float | None,
        alternating_root_cutoff_mps: float,
        identity_loss_weight: float,
        identity_maxabs_weight: float,
        identity_world_pos_weight: float,
        identity_pelvis_pos_weight: float,
        init_store: SimpleClipStore | None = None,
        init_start_pool: StartPool | None = None,
        init_noise_amount: float = DEFAULT_INIT_NOISE_AMOUNT,
        init_noise_clean_fraction: float = DEFAULT_INIT_NOISE_CLEAN_FRACTION,
        init_noise_regular_row_fraction: float = 0.0,
        init_noise_fixed_strength_scale: float = 1.0,
        random_init_noise_rows: bool = False,
        adaptive_sampler: AdaptiveAnimationSampler | None = None,
        synthetic_start_pools: dict[int, StartPool] | None = None,
        synthetic_batch_fraction: float = 0.0,
        synthetic_reserved_start_pools: dict[int, StartPool] | None = None,
        synthetic_reserved_rows: int = 0,
        virtual_reserved_start_pools: dict[int, StartPool] | None = None,
        virtual_reserved_rows: int = 0,
        dedicated_real_start_pools: dict[int, StartPool] | None = None,
        dedicated_real_rows: int = 0,
        dedicated_real_loss_multiplier: float = DEFAULT_DEDICATED_REAL_LOSS_MULTIPLIER,
        periodic_reserved_start_pools: dict[int, StartPool] | None = None,
        periodic_reserved_rows: int = 0,
        extra_ae: SimpleAutoencoder | None = None,
        extra_mean: torch.Tensor | None = None,
        extra_std: torch.Tensor | None = None,
        extra_ae_loss_weight: float = 0.0,
        ae5: SimpleAutoencoder | None = None,
        ae5_mean: torch.Tensor | None = None,
        ae5_std: torch.Tensor | None = None,
        ae5_loss_weight: float = 0.0,
        ae6: torch.nn.Module | None = None,
        ae6_mean: torch.Tensor | None = None,
        ae6_std: torch.Tensor | None = None,
        ae6_loss_weight: float = 0.0,
        ae2: torch.nn.Module | None = None,
        ae2_mean: torch.Tensor | None = None,
        ae2_std: torch.Tensor | None = None,
        ae2_loss_weight: float = 0.0,
        ae3: torch.nn.Module | None = None,
        ae3_mean: torch.Tensor | None = None,
        ae3_std: torch.Tensor | None = None,
        ae3_pos_weight: torch.Tensor | None = None,
        ae3_loss_weight: float = 0.0,
        pin_logit_gap_loss_weight: float = 0.0,
        inertia_acceleration_loss_weight: float = 0.0,
        root_accel_pin_loss_ratio: float = 0.0,
        leg_crossing_capsule_loss_weight: float = 0.0,
        ae4: object | None = None,
        ae4_input_mean: torch.Tensor | None = None,
        ae4_input_std: torch.Tensor | None = None,
        ae4_target_mean: torch.Tensor | None = None,
        ae4_target_std: torch.Tensor | None = None,
        ae4_loss_weight: float = 0.0,
        ae4_bank_pin_loss_weight: float = 0.0,
        slide_tentative_loss_weight: float = 0.0,
    ):
        if store.device.type != "cuda":
            raise RuntimeError("CudaGraphPureAEStep requires CUDA")
        self.model = model
        self.optimizer = optimizer
        self.ae = ae
        self.mean = mean
        self.std = std
        self.store = store
        self.rollout_k = int(rollout_k)
        self.batch_size = int(batch_size)
        self.start_pools = start_pools
        self.full_window_start_pools = full_window_start_pools
        self.rl_cfg = rl_cfg
        self.ae_loss_weight = float(ae_loss_weight)
        self.envelope = envelope
        self.linear_slide_weight = float(linear_slide_weight)
        self.angular_slide_weight = float(angular_slide_weight)
        self.foot_height_weight = float(foot_height_weight)
        self.alternating_feet_weight = float(alternating_feet_weight)
        self.foot_lift_slide_weight = float(foot_lift_slide_weight)
        self.pinned_foot_height_weight = float(pinned_foot_height_weight)
        self.idle_foot_flatness_weight = float(idle_foot_flatness_weight)
        self.forced_idle_batch_fraction = (
            None if forced_idle_batch_fraction is None else max(0.0, min(1.0, float(forced_idle_batch_fraction)))
        )
        self.forced_turn45_batch_fraction = (
            None if forced_turn45_batch_fraction is None else max(0.0, min(1.0, float(forced_turn45_batch_fraction)))
        )
        self.force_idle_row = forced_idle_rows_enabled(
            self.idle_foot_flatness_weight,
            self.forced_idle_batch_fraction,
        )
        self.force_turn45_row = forced_turn45_rows_enabled(self.forced_turn45_batch_fraction)
        self.alternating_root_cutoff_mps = float(alternating_root_cutoff_mps)
        self.identity_loss_weight = float(identity_loss_weight)
        self.identity_maxabs_weight = float(identity_maxabs_weight)
        self.identity_world_pos_weight = float(identity_world_pos_weight)
        self.identity_pelvis_pos_weight = float(identity_pelvis_pos_weight)
        self.init_store = init_store
        self.init_start_pool = init_start_pool
        self.init_noise_amount = max(0.0, float(init_noise_amount))
        self.init_noise_clean_fraction = max(0.0, min(1.0, float(init_noise_clean_fraction)))
        self.init_noise_regular_row_fraction = max(0.0, min(1.0, float(init_noise_regular_row_fraction)))
        self.init_noise_fixed_strength_scale = max(0.0, float(init_noise_fixed_strength_scale))
        self.random_init_noise_rows = bool(random_init_noise_rows)
        if self.random_init_noise_rows and init_store is not None:
            raise ValueError("--random-init-noise-rows cannot be combined with the global --init-* dataset path")
        self.init_noise_active = (
            self.init_noise_fixed_strength_scale > 0.0
            and (init_noise_enabled(self.init_noise_clean_fraction) or self.init_noise_regular_row_fraction > 0.0)
        )
        self.random_init_active = self.random_init_noise_rows and self.init_noise_regular_row_fraction > 0.0
        self.adaptive_sampler = adaptive_sampler
        self.synthetic_start_pools = synthetic_start_pools
        self.synthetic_batch_fraction = max(0.0, min(1.0, float(synthetic_batch_fraction)))
        self.synthetic_reserved_start_pools = synthetic_reserved_start_pools
        self.synthetic_reserved_rows = max(0, min(self.batch_size, int(synthetic_reserved_rows)))
        self.virtual_reserved_start_pools = virtual_reserved_start_pools
        self.virtual_reserved_rows = max(0, min(self.batch_size - self.synthetic_reserved_rows, int(virtual_reserved_rows)))
        self.real_batch_size = generated_reserved_real_batch_size(
            self.batch_size,
            self.synthetic_reserved_rows,
            self.virtual_reserved_rows,
        )
        self.dedicated_real_start_pools = dedicated_real_start_pools
        self.dedicated_real_rows = (
            max(0, min(self.real_batch_size, int(dedicated_real_rows)))
            if dedicated_real_start_pools is not None
            else 0
        )
        self.dedicated_real_loss_multiplier = max(0.0, float(dedicated_real_loss_multiplier))
        self.periodic_reserved_start_pools = periodic_reserved_start_pools
        self.periodic_reserved_rows = (
            max(0, min(self.real_batch_size - self.dedicated_real_rows, int(periodic_reserved_rows)))
            if periodic_reserved_start_pools is not None
            else 0
        )
        self.extra_ae = extra_ae
        self.extra_mean = extra_mean
        self.extra_std = extra_std
        self.extra_ae_loss_weight = float(extra_ae_loss_weight)
        self.ae5 = ae5
        self.ae5_mean = ae5_mean
        self.ae5_std = ae5_std
        self.ae5_loss_weight = float(ae5_loss_weight)
        self.ae6 = ae6
        self.ae6_mean = ae6_mean
        self.ae6_std = ae6_std
        self.ae6_loss_weight = float(ae6_loss_weight)
        self.ae2 = ae2
        self.ae2_mean = ae2_mean
        self.ae2_std = ae2_std
        self.ae2_loss_weight = float(ae2_loss_weight)
        self.ae2_window_weights: torch.Tensor | None = None
        if self.ae2 is not None and self.ae2_mean is not None and self.ae2_std is not None and self.ae2_loss_weight != 0.0:
            ae2_window_frames, ae2_frame_dim = ik_motion_ae2_window_shape(self.ae2)
            self.ae2_window_weights = ik_motion_ae2_frame_feature_weights(
                store,
                ae2_frame_dim,
                self.ae2_loss_weight,
                dtype=torch.float32,
                device=store.device,
            ).repeat(ae2_window_frames)
        self.ae3 = ae3
        self.ae3_mean = ae3_mean
        self.ae3_std = ae3_std
        self.ae3_pos_weight = ae3_pos_weight
        self.ae3_loss_weight = float(ae3_loss_weight)
        self.pin_logit_gap_loss_weight = float(pin_logit_gap_loss_weight)
        self.inertia_acceleration_loss_weight = float(inertia_acceleration_loss_weight)
        self.root_accel_pin_loss_ratio = float(root_accel_pin_loss_ratio)
        self.leg_crossing_capsule_loss_weight = float(leg_crossing_capsule_loss_weight)
        self.ae4 = ae4
        self.ae4_input_mean = ae4_input_mean
        self.ae4_input_std = ae4_input_std
        self.ae4_target_mean = ae4_target_mean
        self.ae4_target_std = ae4_target_std
        self.ae4_loss_weight = float(ae4_loss_weight)
        self.ae4_bank_pin_loss_weight = float(ae4_bank_pin_loss_weight)
        self.slide_tentative_loss_weight = float(slide_tentative_loss_weight)
        input_dim, output_dim = tl.make_batch_dims(store.prototype, store.cfg)
        prepare_ae_output_mse_mask(store, output_dim, mean.dtype)
        self.ae_frames = ae_window_frames_from_dims(mean, input_dim, output_dim)
        if self.extra_ae is not None and self.extra_mean is not None:
            extra_frames = ae_window_frames_from_dims(self.extra_mean, input_dim, output_dim)
            if extra_frames != self.ae_frames:
                raise ValueError(
                    f"Extra AE window_frames={extra_frames} does not match primary AE window_frames={self.ae_frames}"
                )
        self.ae5_frames = (
            ik_motion_ae2_window_shape(self.ae5)[0]
            if is_ik_motion_window_ae(self.ae5)
            else ae_window_frames_from_dims(self.ae5_mean, input_dim, output_dim)
            if self.ae5 is not None and self.ae5_mean is not None and self.ae5_loss_weight != 0.0
            else 1
        )
        self.ae6_frames = (
            ae_window_frames_from_dims(self.ae6_mean, input_dim, output_dim)
            if self.ae6 is not None and self.ae6_mean is not None and self.ae6_loss_weight != 0.0
            else 1
        )
        self.required_context_frames = max(int(self.ae_frames), int(self.ae5_frames), int(self.ae6_frames))
        self.loss_weight_values = self.current_loss_weight_values()
        self.reset_snapshot = {
            "model": clone_module_tensors(self.model),
            "optimizer": clone_optimizer_tensors(self.optimizer),
            "rng": clone_rng_state(self.store.device),
        }
        self.loss_weight_tensors = make_loss_weight_tensors(self.loss_weight_values, store.device)
        self.effective_k = torch.empty((self.batch_size,), dtype=torch.long, device=store.device)
        self.clip_ids = torch.empty_like(self.effective_k)
        self.starts = torch.empty_like(self.effective_k)
        self.init_clip_ids = torch.empty_like(self.effective_k)
        self.init_starts = torch.empty_like(self.effective_k)
        self.random_init_rows = torch.zeros((self.batch_size,), dtype=torch.bool, device=store.device)
        self.reset_starts_by_step = torch.empty(
            (max(1, int(self.rollout_k)), self.batch_size), dtype=torch.long, device=store.device
        )
        self.random_reset_clip_ids_by_step = torch.empty_like(self.reset_starts_by_step)
        self.random_reset_starts_by_step = torch.empty_like(self.reset_starts_by_step)
        self.init_pose_noise_batch = (
            empty_init_pose_noise_batch(
                store,
                self.batch_size,
                device=store.device,
                dtype=torch.float32,
            )
            if self.init_noise_active
            else None
        )
        self.debug_capture = {
            "vectors": torch.empty(
                (self.batch_size, max(1, int(self.rollout_k)) + 1, output_dim),
                dtype=torch.float32,
                device=store.device,
            ),
            "frame_idx": torch.empty(
                (self.batch_size, max(1, int(self.rollout_k)) + 1),
                dtype=torch.long,
                device=store.device,
            ),
            "pin_logits": torch.empty(
                (self.batch_size, max(1, int(self.rollout_k)) + 1, int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)),
                dtype=torch.float32,
                device=store.device,
            ),
            "pin_mask": torch.empty(
                (self.batch_size, max(1, int(self.rollout_k)) + 1, int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)),
                dtype=torch.bool,
                device=store.device,
            ),
            "reset_flags": torch.empty(
                (self.batch_size, max(1, int(self.rollout_k)) + 1),
                dtype=torch.bool,
                device=store.device,
            ),
            "init_noisy_rows": (
                self.init_pose_noise_batch.noisy_rows
                if self.init_pose_noise_batch is not None
                else torch.zeros((self.batch_size,), dtype=torch.bool, device=store.device)
            ),
        }
        self.debug_export_requested = False
        self.debug_export_ready = False
        self.debug_export_effective_k = torch.empty_like(self.effective_k)
        self.debug_export_clip_ids = torch.empty_like(self.clip_ids)
        self.debug_export_starts = torch.empty_like(self.starts)
        self.debug_export_capture = {
            key: torch.empty_like(value)
            for key, value in self.debug_capture.items()
        }
        self.loss = torch.zeros((), dtype=torch.float32, device=store.device)
        self.row_losses = torch.zeros((self.batch_size,), dtype=torch.float32, device=store.device)
        self.debug_capture["row_losses"] = self.row_losses
        self.debug_export_capture["row_losses"] = torch.empty_like(self.row_losses)
        self.term_names = cuda_graph_loss_term_names(
            self.rl_cfg,
            self.ae_loss_weight,
            self.extra_ae_loss_weight,
            self.envelope,
            self.linear_slide_weight,
            self.angular_slide_weight,
            self.foot_height_weight,
            self.alternating_feet_weight,
            self.foot_lift_slide_weight,
            self.identity_loss_weight,
            self.identity_maxabs_weight,
            self.identity_world_pos_weight,
            self.identity_pelvis_pos_weight,
            self.ae2_loss_weight,
            self.ae3_loss_weight,
            self.pin_logit_gap_loss_weight,
            self.inertia_acceleration_loss_weight,
            self.root_accel_pin_loss_ratio,
            self.leg_crossing_capsule_loss_weight,
            self.ae4_loss_weight,
            self.ae4_bank_pin_loss_weight,
            self.slide_tentative_loss_weight,
            self.pinned_foot_height_weight,
            self.idle_foot_flatness_weight,
            self.ae5_loss_weight,
            self.ae6_loss_weight,
        )
        self.term_tensors = {name: torch.zeros_like(self.loss) for name in self.term_names}
        self._boundary_log_enabled = bool(int(os.environ.get("IK_CUDA_GRAPH_BOUNDARY_LOG", "0") or "0"))
        self._ae5_full_batch_diag = bool(int(os.environ.get("IK_AE5_FULL_BATCH_DIAG", "0") or "0"))
        self._boundary_step = 0
        self.graph = torch.cuda.CUDAGraph()
        self._capture()

    def current_loss_weight_values(self) -> dict[str, float]:
        values = {
            "ae_loss_weight": float(self.ae_loss_weight),
            "identity_loss_weight": float(self.identity_loss_weight),
            "identity_maxabs_weight": float(self.identity_maxabs_weight),
            "identity_world_pos_weight": float(self.identity_world_pos_weight),
            "identity_pelvis_pos_weight": float(self.identity_pelvis_pos_weight),
            "linear_slide_weight": float(self.linear_slide_weight),
            "angular_slide_weight": float(self.angular_slide_weight),
            "foot_height_weight": float(self.foot_height_weight),
            "alternating_feet_weight": float(self.alternating_feet_weight),
            "foot_lift_slide_weight": float(self.foot_lift_slide_weight),
            "ik_lower_length_loss_weight": float(IK_LOWER_LENGTH_LOSS_WEIGHT),
            "ae4_loss_weight": float(self.ae4_loss_weight),
            "ae4_bank_pin_loss_weight": float(self.ae4_bank_pin_loss_weight),
            "pin_logit_gap_loss_weight": float(self.pin_logit_gap_loss_weight),
            "inertia_acceleration_loss_weight": float(self.inertia_acceleration_loss_weight),
            "leg_crossing_capsule_loss_weight": float(self.leg_crossing_capsule_loss_weight),
            "slide_tentative_loss_weight": float(self.slide_tentative_loss_weight),
            "pinned_foot_height_weight": float(self.pinned_foot_height_weight),
            "idle_foot_flatness_weight": float(self.idle_foot_flatness_weight),
        }
        for field in RLLossConfig._weight_fields():
            values[field] = float(getattr(self.rl_cfg, field))
        return values

    def apply_loss_weight_values(self, values: dict[str, float]) -> None:
        global IK_LOWER_LENGTH_LOSS_WEIGHT

        self.ae_loss_weight = float(values["ae_loss_weight"])
        self.identity_loss_weight = float(values["identity_loss_weight"])
        self.identity_maxabs_weight = float(values["identity_maxabs_weight"])
        self.identity_world_pos_weight = float(values["identity_world_pos_weight"])
        self.identity_pelvis_pos_weight = float(values["identity_pelvis_pos_weight"])
        self.linear_slide_weight = float(values["linear_slide_weight"])
        self.angular_slide_weight = float(values["angular_slide_weight"])
        self.foot_height_weight = float(values["foot_height_weight"])
        self.alternating_feet_weight = float(values["alternating_feet_weight"])
        self.foot_lift_slide_weight = float(values["foot_lift_slide_weight"])
        self.ae4_loss_weight = float(values["ae4_loss_weight"])
        self.ae4_bank_pin_loss_weight = float(values["ae4_bank_pin_loss_weight"])
        self.pin_logit_gap_loss_weight = float(values["pin_logit_gap_loss_weight"])
        self.inertia_acceleration_loss_weight = float(values["inertia_acceleration_loss_weight"])
        self.leg_crossing_capsule_loss_weight = float(values["leg_crossing_capsule_loss_weight"])
        self.slide_tentative_loss_weight = float(values["slide_tentative_loss_weight"])
        self.pinned_foot_height_weight = float(values["pinned_foot_height_weight"])
        self.idle_foot_flatness_weight = float(values["idle_foot_flatness_weight"])
        self.force_idle_row = forced_idle_rows_enabled(
            self.idle_foot_flatness_weight,
            self.forced_idle_batch_fraction,
        )
        IK_LOWER_LENGTH_LOSS_WEIGHT = float(values["ik_lower_length_loss_weight"])
        rl_updates = {field: float(values[field]) for field in RLLossConfig._weight_fields()}
        self.rl_cfg = replace(self.rl_cfg, **rl_updates)
        self.loss_weight_values = dict(values)

    def update_loss_weights(self, updates: dict[str, float]) -> dict[str, object]:
        current = self.loss_weight_values
        next_values = dict(current)
        for key, value in updates.items():
            if key in MUTABLE_LOSS_WEIGHT_FIELDS:
                next_values[key] = float(value)
        ok, reason = loss_weight_shape_compatible(current, next_values)
        if not ok:
            return {"ok": False, "requires_rearm": True, "reason": reason}
        torch.cuda.synchronize(self.store.device)
        with torch.no_grad():
            for key, value in next_values.items():
                tensor = self.loss_weight_tensors.get(key)
                if tensor is not None:
                    tensor.fill_(float(value))
        torch.cuda.synchronize(self.store.device)
        self.apply_loss_weight_values(next_values)
        return {"ok": True, "requires_rearm": False, "updated": len(next_values)}

    def _sample_into_static_buffers(self) -> None:
        effective_k = sample_effective_rollout_k_with_reserved_rows(
            self.batch_size,
            self.rollout_k,
            self.store.device,
            self.synthetic_reserved_rows,
            self.virtual_reserved_rows,
        )
        if self.ae5 is not None and self.ae5_loss_weight != 0.0 and self.periodic_reserved_rows > 0:
            force_row_range_to_rollout_k_(
                effective_k,
                self.dedicated_real_rows,
                self.periodic_reserved_rows,
                self.rollout_k,
            )
        clip_ids, starts = sample_rollout_rows(
            self.start_pools,
            effective_k,
            self.adaptive_sampler,
            self.required_context_frames,
            self.synthetic_start_pools,
            self.synthetic_batch_fraction,
            self.full_window_start_pools,
            None,
            self.synthetic_reserved_start_pools,
            self.synthetic_reserved_rows,
            self.virtual_reserved_start_pools,
            self.virtual_reserved_rows,
            self.dedicated_real_start_pools,
            self.dedicated_real_rows,
            self.periodic_reserved_start_pools,
            self.periodic_reserved_rows,
        )
        idle_tail_count = (
            forced_idle_batch_row_count(self.real_batch_size, self.forced_idle_batch_fraction)
            if self.force_idle_row
            else 0
        )
        if self.force_turn45_row:
            apply_forced_turn45_training_row_(
                self.store,
                clip_ids,
                starts,
                self.required_context_frames,
                self.forced_turn45_batch_fraction,
                reserved_tail_rows=idle_tail_count,
                row_limit=self.real_batch_size,
            )
        if self.force_idle_row:
            apply_forced_idle_training_row_(
                self.store,
                clip_ids,
                starts,
                self.required_context_frames,
                self.forced_idle_batch_fraction,
                row_limit=self.real_batch_size,
            )
        self.effective_k.copy_(effective_k)
        self.clip_ids.copy_(clip_ids)
        self.starts.copy_(starts)
        if self.init_store is not None and self.init_start_pool is not None:
            init_clip_ids, init_starts = sample_from_pool(self.init_start_pool, self.batch_size)
            self.init_clip_ids.copy_(init_clip_ids)
            self.init_starts.copy_(init_starts)
        else:
            self.init_clip_ids.copy_(clip_ids)
            self.init_starts.copy_(starts)
        self.reset_starts_by_step.copy_(
            sample_same_clip_training_starts_by_step(
                self.store,
                clip_ids,
                self.reset_starts_by_step.shape[0],
                self.required_context_frames,
                effective_k,
            )
        )
        if self.random_init_active:
            reserved_real_rows = self.dedicated_real_rows + self.periodic_reserved_rows
            random_rows = sample_init_noise_row_mask_in_range(
                self.batch_size,
                reserved_real_rows,
                self.real_batch_size - reserved_real_rows,
                self.init_noise_regular_row_fraction,
                self.store.device,
            )
            self.random_init_rows.copy_(random_rows)
            random_clip_ids, random_starts = sample_adjacent_init_rows_from_start_pools(
                self.start_pools,
                self.batch_size,
            )
            self.init_clip_ids.copy_(torch.where(random_rows, random_clip_ids, self.init_clip_ids))
            self.init_starts.copy_(torch.where(random_rows, random_starts, self.init_starts))
            for reset_step in range(int(self.reset_starts_by_step.shape[0])):
                reset_clip_ids, reset_starts = sample_adjacent_init_rows_from_start_pools(
                    self.start_pools,
                    self.batch_size,
                )
                self.random_reset_clip_ids_by_step[reset_step].copy_(reset_clip_ids)
                self.random_reset_starts_by_step[reset_step].copy_(reset_starts)
        else:
            self.random_init_rows.zero_()
        if self.init_pose_noise_batch is not None:
            rng_snapshot = clone_rng_state(self.store.device)
            try:
                forced_rows = forced_tail_row_indices(
                    self.batch_size,
                    self.real_batch_size,
                    self.force_idle_row,
                    self.forced_idle_batch_fraction,
                    self.force_turn45_row,
                    self.forced_turn45_batch_fraction,
                    self.store.device,
                )
                exact_noisy_rows = None
                if self.init_noise_regular_row_fraction > 0.0 and self.init_noise_fixed_strength_scale > 0.0:
                    reserved_real_rows = self.dedicated_real_rows + self.periodic_reserved_rows
                    exact_noisy_rows = sample_init_noise_row_mask_in_range(
                        self.batch_size,
                        reserved_real_rows,
                        self.real_batch_size - reserved_real_rows,
                        self.init_noise_regular_row_fraction,
                        self.store.device,
                    )
                fill_init_pose_noise_batch_(
                    self.init_pose_noise_batch,
                    self.store,
                    self.init_noise_amount,
                    self.init_noise_clean_fraction,
                    force_noisy_rows=forced_rows,
                    exact_noisy_rows=exact_noisy_rows,
                    fixed_strength_scale=self.init_noise_fixed_strength_scale,
                )
            finally:
                restore_rng_state(rng_snapshot, self.store.device)

    def _loss(self) -> ControllerLossResult:
        return pure_ae_rollout_loss_static(
            self.model,
            self.ae,
            self.mean,
            self.std,
            self.store,
            self.rollout_k,
            self.batch_size,
            self.effective_k,
            self.clip_ids,
            self.starts,
            self.init_clip_ids,
            self.init_starts,
            self.reset_starts_by_step,
            self.rl_cfg,
            self.ae_loss_weight,
            self.envelope,
            self.linear_slide_weight,
            self.angular_slide_weight,
            self.foot_height_weight,
            self.alternating_feet_weight,
            self.foot_lift_slide_weight,
            self.pinned_foot_height_weight,
            self.idle_foot_flatness_weight,
            self.slide_tentative_loss_weight,
            self.forced_idle_batch_fraction,
            self.alternating_root_cutoff_mps,
            self.identity_loss_weight,
            self.identity_maxabs_weight,
            self.identity_world_pos_weight,
            self.identity_pelvis_pos_weight,
            self.store if self.random_init_active else self.init_store,
            init_adjacent_context=self.random_init_active,
            random_init_rows=self.random_init_rows if self.random_init_active else None,
            random_reset_clip_ids_by_step=(
                self.random_reset_clip_ids_by_step if self.random_init_active else None
            ),
            random_reset_starts_by_step=(
                self.random_reset_starts_by_step if self.random_init_active else None
            ),
            include_diagnostics=False,
            loss_weight_tensors=self.loss_weight_tensors,
            init_noise_amount=self.init_noise_amount,
            init_noise_clean_fraction=self.init_noise_clean_fraction,
            init_pose_noise_batch=self.init_pose_noise_batch,
            extra_ae=self.extra_ae,
            extra_mean=self.extra_mean,
            extra_std=self.extra_std,
            extra_ae_loss_weight=self.extra_ae_loss_weight,
            ae5=self.ae5,
            ae5_mean=self.ae5_mean,
            ae5_std=self.ae5_std,
            ae5_loss_weight=self.ae5_loss_weight,
            ae5_reserved_row_start=0 if self._ae5_full_batch_diag else self.dedicated_real_rows,
            ae5_reserved_rows=None if self._ae5_full_batch_diag else self.periodic_reserved_rows,
            ae6=self.ae6,
            ae6_mean=self.ae6_mean,
            ae6_std=self.ae6_std,
            ae6_loss_weight=self.ae6_loss_weight,
            ae2=self.ae2,
            ae2_mean=self.ae2_mean,
            ae2_std=self.ae2_std,
            ae2_loss_weight=self.ae2_loss_weight,
            ae2_window_weights=self.ae2_window_weights,
            ae3=self.ae3,
            ae3_mean=self.ae3_mean,
            ae3_std=self.ae3_std,
            ae3_pos_weight=self.ae3_pos_weight,
            ae3_loss_weight=self.ae3_loss_weight,
            pin_logit_gap_loss_weight=self.pin_logit_gap_loss_weight,
            inertia_acceleration_loss_weight=self.inertia_acceleration_loss_weight,
            root_accel_pin_loss_ratio=self.root_accel_pin_loss_ratio,
            leg_crossing_capsule_loss_weight=self.leg_crossing_capsule_loss_weight,
            ae4=self.ae4,
            ae4_input_mean=self.ae4_input_mean,
            ae4_input_std=self.ae4_input_std,
            ae4_target_mean=self.ae4_target_mean,
            ae4_target_std=self.ae4_target_std,
            ae4_loss_weight=self.ae4_loss_weight,
            ae4_bank_pin_loss_weight=self.ae4_bank_pin_loss_weight,
            dedicated_real_rows=self.dedicated_real_rows,
            dedicated_real_loss_multiplier=self.dedicated_real_loss_multiplier,
            periodic_reserved_rows=self.periodic_reserved_rows,
            debug_capture=self.debug_capture,
        )

    def _capture(self) -> None:
        phase_started = time.perf_counter()
        self._sample_into_static_buffers()
        phase_started = emit_pretrain_arm_timing("cuda_graph_initial_sample", phase_started)
        warmup_started = time.perf_counter()
        side_stream = torch.cuda.Stream()
        side_stream.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(side_stream):
            for warmup_idx in range(int(CUDA_GRAPH_WARMUP_STEPS)):
                part_started = time.perf_counter()
                self._sample_into_static_buffers()
                emit_pretrain_arm_timing(
                    f"cuda_graph_warmup{warmup_idx + 1}_sample",
                    part_started,
                    step=warmup_idx + 1,
                )
                part_started = time.perf_counter()
                self.optimizer.zero_grad(set_to_none=False)
                emit_pretrain_arm_timing(
                    f"cuda_graph_warmup{warmup_idx + 1}_zero_grad",
                    part_started,
                    step=warmup_idx + 1,
                )
                part_started = time.perf_counter()
                loss_result = self._loss()
                emit_pretrain_arm_timing(
                    f"cuda_graph_warmup{warmup_idx + 1}_loss_forward",
                    part_started,
                    step=warmup_idx + 1,
                )
                part_started = time.perf_counter()
                loss_result.total.backward()
                emit_pretrain_arm_timing(
                    f"cuda_graph_warmup{warmup_idx + 1}_backward",
                    part_started,
                    step=warmup_idx + 1,
                )
                part_started = time.perf_counter()
                maybe_clip_rl_gradients(self.model, self.rl_cfg)
                emit_pretrain_arm_timing(
                    f"cuda_graph_warmup{warmup_idx + 1}_grad_clip",
                    part_started,
                    step=warmup_idx + 1,
                )
                part_started = time.perf_counter()
                self.optimizer.step()
                emit_pretrain_arm_timing(
                    f"cuda_graph_warmup{warmup_idx + 1}_optimizer",
                    part_started,
                    step=warmup_idx + 1,
                )
                del loss_result
        torch.cuda.current_stream().wait_stream(side_stream)
        phase_started = emit_pretrain_arm_timing(
            "cuda_graph_warmup_steps",
            warmup_started,
            steps=int(CUDA_GRAPH_WARMUP_STEPS),
        )
        torch.cuda.synchronize()
        phase_started = emit_pretrain_arm_timing("cuda_graph_synchronize", phase_started)
        self.optimizer.zero_grad(set_to_none=False)
        capture_started = time.perf_counter()
        capture_parts: list[tuple[str, float]] = []
        with torch.cuda.graph(self.graph):
            part_started = time.perf_counter()
            self.optimizer.zero_grad(set_to_none=False)
            capture_parts.append(("cuda_graph_capture_zero_grad", time.perf_counter() - part_started))
            part_started = time.perf_counter()
            loss_result = self._loss()
            capture_parts.append(("cuda_graph_capture_loss_forward", time.perf_counter() - part_started))
            part_started = time.perf_counter()
            graph_loss = loss_result.total
            self.loss.copy_(graph_loss.detach())
            if loss_result.row_losses is not None:
                self.row_losses.copy_(loss_result.row_losses.detach())
            for name in self.term_names:
                self.term_tensors[name].copy_(loss_result.terms[name].detach())
            capture_parts.append(("cuda_graph_capture_terms", time.perf_counter() - part_started))
            part_started = time.perf_counter()
            graph_loss.backward()
            capture_parts.append(("cuda_graph_capture_backward", time.perf_counter() - part_started))
            part_started = time.perf_counter()
            maybe_clip_rl_gradients(self.model, self.rl_cfg)
            capture_parts.append(("cuda_graph_capture_grad_clip", time.perf_counter() - part_started))
            part_started = time.perf_counter()
            self.optimizer.step()
            capture_parts.append(("cuda_graph_capture_optimizer", time.perf_counter() - part_started))
        for phase, delta_s in capture_parts:
            emit_pretrain_arm_delta(phase, delta_s)
        emit_pretrain_arm_timing("cuda_graph_record", capture_started)
        torch.cuda.synchronize(self.store.device)
        # Warmup/capture execute real optimizer steps. Keep the initialized graph
        # storage, but restore the model and any pre-existing optimizer state so
        # step 1 starts from the requested checkpoint/state.
        self.reset_to_capture_state()
        self.reset_snapshot = {
            "model": clone_module_tensors(self.model),
            "optimizer": clone_optimizer_tensors(self.optimizer),
            "rng": clone_rng_state(self.store.device),
        }

    def reset_to_capture_state(self) -> None:
        torch.cuda.synchronize(self.store.device)
        restore_module_tensors(self.model, self.reset_snapshot["model"])  # type: ignore[arg-type]
        restore_optimizer_tensors(self.optimizer, self.reset_snapshot["optimizer"])  # type: ignore[arg-type]
        restore_rng_state(self.reset_snapshot["rng"], self.store.device)  # type: ignore[arg-type]
        torch.cuda.synchronize(self.store.device)

    def arm_debug_export_snapshot(self) -> None:
        self.debug_export_requested = True

    @torch.no_grad()
    def _snapshot_debug_export_if_requested(self) -> None:
        if not self.debug_export_requested:
            return
        self.debug_export_effective_k.copy_(self.effective_k)
        self.debug_export_clip_ids.copy_(self.clip_ids)
        self.debug_export_starts.copy_(self.starts)
        for key, value in self.debug_capture.items():
            self.debug_export_capture[key].copy_(value)
        self.debug_export_ready = True
        self.debug_export_requested = False

    def consume_debug_export_snapshot(
        self,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, dict[str, torch.Tensor]] | None:
        if not self.debug_export_ready:
            return None
        self.debug_export_ready = False
        return (
            self.debug_export_effective_k,
            self.debug_export_clip_ids,
            self.debug_export_starts,
            self.debug_export_capture,
        )

    def step(self) -> ControllerLossResult:
        if self._boundary_log_enabled:
            self._boundary_step += 1
            print(f"CUDA_GRAPH_BOUNDARY step={self._boundary_step} enter", flush=True)
        self._sample_into_static_buffers()
        if self._boundary_log_enabled:
            print(f"CUDA_GRAPH_BOUNDARY step={self._boundary_step} sample_done", flush=True)
        self.graph.replay()
        if self._boundary_log_enabled:
            print(f"CUDA_GRAPH_BOUNDARY step={self._boundary_step} replay_done", flush=True)
        self._snapshot_debug_export_if_requested()
        if self._boundary_log_enabled:
            print(f"CUDA_GRAPH_BOUNDARY step={self._boundary_step} snapshot_done", flush=True)
        return ControllerLossResult(
            total=self.loss.detach(),
            terms={name: self.term_tensors[name].detach() for name in self.term_names},
            row_losses=self.row_losses.detach(),
        )

class EagerPureAEStep:
    kind = "eager"

    def __init__(
        self,
        model: torch.nn.Module,
        optimizer: torch.optim.Optimizer,
        ae: SimpleAutoencoder,
        mean: torch.Tensor,
        std: torch.Tensor,
        store: SimpleClipStore,
        rollout_k: int,
        batch_size: int,
        start_pools: dict[int, StartPool],
        full_window_start_pools: dict[int, StartPool] | None,
        rl_cfg: RLLossConfig,
        ae_loss_weight: float,
        envelope: dict[str, torch.Tensor | dict[str, float | int | str]] | None,
        linear_slide_weight: float,
        angular_slide_weight: float,
        foot_height_weight: float,
        alternating_feet_weight: float,
        foot_lift_slide_weight: float,
        pinned_foot_height_weight: float,
        idle_foot_flatness_weight: float,
        forced_idle_batch_fraction: float | None,
        forced_turn45_batch_fraction: float | None,
        alternating_root_cutoff_mps: float,
        identity_loss_weight: float,
        identity_maxabs_weight: float,
        identity_world_pos_weight: float,
        identity_pelvis_pos_weight: float,
        init_store: SimpleClipStore | None = None,
        init_start_pool: StartPool | None = None,
        init_noise_amount: float = DEFAULT_INIT_NOISE_AMOUNT,
        init_noise_clean_fraction: float = DEFAULT_INIT_NOISE_CLEAN_FRACTION,
        init_noise_regular_row_fraction: float = 0.0,
        init_noise_fixed_strength_scale: float = 1.0,
        adaptive_sampler: AdaptiveAnimationSampler | None = None,
        synthetic_start_pools: dict[int, StartPool] | None = None,
        synthetic_batch_fraction: float = 0.0,
        synthetic_reserved_start_pools: dict[int, StartPool] | None = None,
        synthetic_reserved_rows: int = 0,
        virtual_reserved_start_pools: dict[int, StartPool] | None = None,
        virtual_reserved_rows: int = 0,
        dedicated_real_start_pools: dict[int, StartPool] | None = None,
        dedicated_real_rows: int = 0,
        dedicated_real_loss_multiplier: float = DEFAULT_DEDICATED_REAL_LOSS_MULTIPLIER,
        periodic_reserved_start_pools: dict[int, StartPool] | None = None,
        periodic_reserved_rows: int = 0,
        extra_ae: SimpleAutoencoder | None = None,
        extra_mean: torch.Tensor | None = None,
        extra_std: torch.Tensor | None = None,
        extra_ae_loss_weight: float = 0.0,
        ae5: SimpleAutoencoder | None = None,
        ae5_mean: torch.Tensor | None = None,
        ae5_std: torch.Tensor | None = None,
        ae5_loss_weight: float = 0.0,
        ae2: torch.nn.Module | None = None,
        ae2_mean: torch.Tensor | None = None,
        ae2_std: torch.Tensor | None = None,
        ae2_loss_weight: float = 0.0,
        ae3: torch.nn.Module | None = None,
        ae3_mean: torch.Tensor | None = None,
        ae3_std: torch.Tensor | None = None,
        ae3_pos_weight: torch.Tensor | None = None,
        ae3_loss_weight: float = 0.0,
        pin_logit_gap_loss_weight: float = 0.0,
        inertia_acceleration_loss_weight: float = 0.0,
        ae4: object | None = None,
        ae4_input_mean: torch.Tensor | None = None,
        ae4_input_std: torch.Tensor | None = None,
        ae4_target_mean: torch.Tensor | None = None,
        ae4_target_std: torch.Tensor | None = None,
        ae4_loss_weight: float = 0.0,
        ae4_bank_pin_loss_weight: float = 0.0,
        slide_tentative_loss_weight: float = 0.0,
    ):
        self.model = model
        self.optimizer = optimizer
        self.ae = ae
        self.mean = mean
        self.std = std
        self.store = store
        self.rollout_k = int(rollout_k)
        self.batch_size = int(batch_size)
        self.start_pools = start_pools
        self.full_window_start_pools = full_window_start_pools
        self.rl_cfg = rl_cfg
        self.ae_loss_weight = float(ae_loss_weight)
        self.envelope = envelope
        self.linear_slide_weight = float(linear_slide_weight)
        self.angular_slide_weight = float(angular_slide_weight)
        self.foot_height_weight = float(foot_height_weight)
        self.alternating_feet_weight = float(alternating_feet_weight)
        self.foot_lift_slide_weight = float(foot_lift_slide_weight)
        self.pinned_foot_height_weight = float(pinned_foot_height_weight)
        self.idle_foot_flatness_weight = float(idle_foot_flatness_weight)
        self.forced_idle_batch_fraction = (
            None if forced_idle_batch_fraction is None else max(0.0, min(1.0, float(forced_idle_batch_fraction)))
        )
        self.forced_turn45_batch_fraction = (
            None if forced_turn45_batch_fraction is None else max(0.0, min(1.0, float(forced_turn45_batch_fraction)))
        )
        self.force_idle_row = forced_idle_rows_enabled(
            self.idle_foot_flatness_weight,
            self.forced_idle_batch_fraction,
        )
        self.force_turn45_row = forced_turn45_rows_enabled(self.forced_turn45_batch_fraction)
        self.alternating_root_cutoff_mps = float(alternating_root_cutoff_mps)
        self.identity_loss_weight = float(identity_loss_weight)
        self.identity_maxabs_weight = float(identity_maxabs_weight)
        self.identity_world_pos_weight = float(identity_world_pos_weight)
        self.identity_pelvis_pos_weight = float(identity_pelvis_pos_weight)
        self.init_store = init_store
        self.init_start_pool = init_start_pool
        self.init_noise_amount = max(0.0, float(init_noise_amount))
        self.init_noise_clean_fraction = max(0.0, min(1.0, float(init_noise_clean_fraction)))
        self.init_noise_regular_row_fraction = max(0.0, min(1.0, float(init_noise_regular_row_fraction)))
        self.init_noise_fixed_strength_scale = max(0.0, float(init_noise_fixed_strength_scale))
        self.adaptive_sampler = adaptive_sampler
        self.synthetic_start_pools = synthetic_start_pools
        self.synthetic_batch_fraction = max(0.0, min(1.0, float(synthetic_batch_fraction)))
        self.synthetic_reserved_start_pools = synthetic_reserved_start_pools
        self.synthetic_reserved_rows = max(0, min(self.batch_size, int(synthetic_reserved_rows)))
        self.virtual_reserved_start_pools = virtual_reserved_start_pools
        self.virtual_reserved_rows = max(0, min(self.batch_size - self.synthetic_reserved_rows, int(virtual_reserved_rows)))
        self.real_batch_size = generated_reserved_real_batch_size(
            self.batch_size,
            self.synthetic_reserved_rows,
            self.virtual_reserved_rows,
        )
        self.dedicated_real_start_pools = dedicated_real_start_pools
        self.dedicated_real_rows = (
            max(0, min(self.real_batch_size, int(dedicated_real_rows)))
            if dedicated_real_start_pools is not None
            else 0
        )
        self.dedicated_real_loss_multiplier = max(0.0, float(dedicated_real_loss_multiplier))
        self.periodic_reserved_start_pools = periodic_reserved_start_pools
        self.periodic_reserved_rows = (
            max(0, min(self.real_batch_size - self.dedicated_real_rows, int(periodic_reserved_rows)))
            if periodic_reserved_start_pools is not None
            else 0
        )
        self.extra_ae = extra_ae
        self.extra_mean = extra_mean
        self.extra_std = extra_std
        self.extra_ae_loss_weight = float(extra_ae_loss_weight)
        self.ae5 = ae5
        self.ae5_mean = ae5_mean
        self.ae5_std = ae5_std
        self.ae5_loss_weight = float(ae5_loss_weight)
        self.ae2 = ae2
        self.ae2_mean = ae2_mean
        self.ae2_std = ae2_std
        self.ae2_loss_weight = float(ae2_loss_weight)
        self.ae2_window_weights: torch.Tensor | None = None
        if self.ae2 is not None and self.ae2_mean is not None and self.ae2_std is not None and self.ae2_loss_weight != 0.0:
            ae2_window_frames, ae2_frame_dim = ik_motion_ae2_window_shape(self.ae2)
            self.ae2_window_weights = ik_motion_ae2_frame_feature_weights(
                store,
                ae2_frame_dim,
                self.ae2_loss_weight,
                dtype=torch.float32,
                device=store.device,
            ).repeat(ae2_window_frames)
        self.ae3 = ae3
        self.ae3_mean = ae3_mean
        self.ae3_std = ae3_std
        self.ae3_pos_weight = ae3_pos_weight
        self.ae3_loss_weight = float(ae3_loss_weight)
        self.pin_logit_gap_loss_weight = float(pin_logit_gap_loss_weight)
        self.inertia_acceleration_loss_weight = float(inertia_acceleration_loss_weight)
        self.ae4 = ae4
        self.ae4_input_mean = ae4_input_mean
        self.ae4_input_std = ae4_input_std
        self.ae4_target_mean = ae4_target_mean
        self.ae4_target_std = ae4_target_std
        self.ae4_loss_weight = float(ae4_loss_weight)
        self.ae4_bank_pin_loss_weight = float(ae4_bank_pin_loss_weight)
        self.slide_tentative_loss_weight = float(slide_tentative_loss_weight)
        self.loss_weight_values = self.current_loss_weight_values()
        input_dim, output_dim = tl.make_batch_dims(store.prototype, store.cfg)
        self.ae_frames = ae_window_frames_from_dims(mean, input_dim, output_dim)
        self.ae5_frames = (
            ik_motion_ae2_window_shape(self.ae5)[0]
            if is_ik_motion_window_ae(self.ae5)
            else ae_window_frames_from_dims(self.ae5_mean, input_dim, output_dim)
            if self.ae5 is not None and self.ae5_mean is not None and self.ae5_loss_weight != 0.0
            else 1
        )
        self.required_context_frames = max(int(self.ae_frames), int(self.ae5_frames))
        self.clip_ids = torch.empty((self.batch_size,), dtype=torch.long, device=store.device)
        self.debug_capture = {
            "vectors": torch.empty(
                (self.batch_size, max(1, int(self.rollout_k)) + 1, output_dim),
                dtype=torch.float32,
                device=store.device,
            ),
            "frame_idx": torch.empty(
                (self.batch_size, max(1, int(self.rollout_k)) + 1),
                dtype=torch.long,
                device=store.device,
            ),
            "pin_logits": torch.empty(
                (self.batch_size, max(1, int(self.rollout_k)) + 1, int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)),
                dtype=torch.float32,
                device=store.device,
            ),
            "pin_mask": torch.empty(
                (self.batch_size, max(1, int(self.rollout_k)) + 1, int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)),
                dtype=torch.bool,
                device=store.device,
            ),
            "reset_flags": torch.empty(
                (self.batch_size, max(1, int(self.rollout_k)) + 1),
                dtype=torch.bool,
                device=store.device,
            ),
        }

    def current_loss_weight_values(self) -> dict[str, float]:
        values = {
            "ae_loss_weight": float(self.ae_loss_weight),
            "identity_loss_weight": float(self.identity_loss_weight),
            "identity_maxabs_weight": float(self.identity_maxabs_weight),
            "identity_world_pos_weight": float(self.identity_world_pos_weight),
            "identity_pelvis_pos_weight": float(self.identity_pelvis_pos_weight),
            "linear_slide_weight": float(self.linear_slide_weight),
            "angular_slide_weight": float(self.angular_slide_weight),
            "foot_height_weight": float(self.foot_height_weight),
            "alternating_feet_weight": float(self.alternating_feet_weight),
            "foot_lift_slide_weight": float(self.foot_lift_slide_weight),
            "ik_lower_length_loss_weight": float(IK_LOWER_LENGTH_LOSS_WEIGHT),
            "ae4_loss_weight": float(self.ae4_loss_weight),
            "ae4_bank_pin_loss_weight": float(self.ae4_bank_pin_loss_weight),
            "pin_logit_gap_loss_weight": float(self.pin_logit_gap_loss_weight),
            "inertia_acceleration_loss_weight": float(self.inertia_acceleration_loss_weight),
            "slide_tentative_loss_weight": float(self.slide_tentative_loss_weight),
            "pinned_foot_height_weight": float(self.pinned_foot_height_weight),
            "idle_foot_flatness_weight": float(self.idle_foot_flatness_weight),
        }
        for field in RLLossConfig._weight_fields():
            values[field] = float(getattr(self.rl_cfg, field))
        return values

    def apply_loss_weight_values(self, values: dict[str, float]) -> None:
        global IK_LOWER_LENGTH_LOSS_WEIGHT

        self.ae_loss_weight = float(values["ae_loss_weight"])
        self.identity_loss_weight = float(values["identity_loss_weight"])
        self.identity_maxabs_weight = float(values["identity_maxabs_weight"])
        self.identity_world_pos_weight = float(values["identity_world_pos_weight"])
        self.identity_pelvis_pos_weight = float(values["identity_pelvis_pos_weight"])
        self.linear_slide_weight = float(values["linear_slide_weight"])
        self.angular_slide_weight = float(values["angular_slide_weight"])
        self.foot_height_weight = float(values["foot_height_weight"])
        self.alternating_feet_weight = float(values["alternating_feet_weight"])
        self.foot_lift_slide_weight = float(values["foot_lift_slide_weight"])
        self.ae4_loss_weight = float(values["ae4_loss_weight"])
        self.ae4_bank_pin_loss_weight = float(values["ae4_bank_pin_loss_weight"])
        self.pin_logit_gap_loss_weight = float(values["pin_logit_gap_loss_weight"])
        self.inertia_acceleration_loss_weight = float(values["inertia_acceleration_loss_weight"])
        self.slide_tentative_loss_weight = float(values["slide_tentative_loss_weight"])
        self.pinned_foot_height_weight = float(values["pinned_foot_height_weight"])
        self.idle_foot_flatness_weight = float(values["idle_foot_flatness_weight"])
        self.force_idle_row = forced_idle_rows_enabled(
            self.idle_foot_flatness_weight,
            self.forced_idle_batch_fraction,
        )
        IK_LOWER_LENGTH_LOSS_WEIGHT = float(values["ik_lower_length_loss_weight"])
        rl_updates = {field: float(values[field]) for field in RLLossConfig._weight_fields()}
        self.rl_cfg = replace(self.rl_cfg, **rl_updates)
        self.loss_weight_values = dict(values)

    def update_loss_weights(self, updates: dict[str, float]) -> dict[str, object]:
        current = self.loss_weight_values
        next_values = dict(current)
        for key, value in updates.items():
            if key in MUTABLE_LOSS_WEIGHT_FIELDS:
                next_values[key] = float(value)
        ok, reason = loss_weight_shape_compatible(current, next_values)
        if not ok:
            return {"ok": False, "requires_rearm": True, "reason": reason}
        self.apply_loss_weight_values(next_values)
        return {"ok": True, "requires_rearm": False, "updated": len(next_values)}

    def reset_to_capture_state(self) -> None:
        restore_module_tensors(self.model, self.reset_snapshot["model"])  # type: ignore[arg-type]
        restore_optimizer_tensors(self.optimizer, self.reset_snapshot["optimizer"])  # type: ignore[arg-type]
        restore_rng_state(self.reset_snapshot["rng"], self.store.device)  # type: ignore[arg-type]

    def step(self) -> ControllerLossResult:
        effective_k = sample_effective_rollout_k_with_reserved_rows(
            self.batch_size,
            self.rollout_k,
            self.store.device,
            self.synthetic_reserved_rows,
            self.virtual_reserved_rows,
        )
        init_pose_noise_batch: InitPoseNoiseBatch | None = None
        init_noise_active = (
            self.init_noise_fixed_strength_scale > 0.0
            and (init_noise_enabled(self.init_noise_clean_fraction) or self.init_noise_regular_row_fraction > 0.0)
        )
        if self.ae5 is not None and self.ae5_loss_weight != 0.0 and self.periodic_reserved_rows > 0:
            force_row_range_to_rollout_k_(
                effective_k,
                self.dedicated_real_rows,
                self.periodic_reserved_rows,
                self.rollout_k,
            )
        clip_ids, starts = sample_rollout_rows(
            self.start_pools,
            effective_k,
            self.adaptive_sampler,
            self.required_context_frames,
            self.synthetic_start_pools,
            self.synthetic_batch_fraction,
            self.full_window_start_pools,
            None,
            self.synthetic_reserved_start_pools,
            self.synthetic_reserved_rows,
            self.virtual_reserved_start_pools,
            self.virtual_reserved_rows,
            self.dedicated_real_start_pools,
            self.dedicated_real_rows,
            self.periodic_reserved_start_pools,
            self.periodic_reserved_rows,
        )
        idle_tail_count = (
            forced_idle_batch_row_count(self.real_batch_size, self.forced_idle_batch_fraction)
            if self.force_idle_row
            else 0
        )
        if self.force_turn45_row:
            apply_forced_turn45_training_row_(
                self.store,
                clip_ids,
                starts,
                self.required_context_frames,
                self.forced_turn45_batch_fraction,
                reserved_tail_rows=idle_tail_count,
                row_limit=self.real_batch_size,
            )
        if self.force_idle_row:
            apply_forced_idle_training_row_(
                self.store,
                clip_ids,
                starts,
                self.required_context_frames,
                self.forced_idle_batch_fraction,
                row_limit=self.real_batch_size,
            )
        self.clip_ids = clip_ids
        self.effective_k = effective_k
        self.starts = starts
        if self.init_store is not None and self.init_start_pool is not None:
            init_clip_ids, init_starts = sample_from_pool(self.init_start_pool, self.batch_size)
        else:
            init_clip_ids, init_starts = clip_ids, starts
        self.init_clip_ids = init_clip_ids
        self.init_starts = init_starts
        reset_starts_by_step = sample_same_clip_training_starts_by_step(
            self.store,
            clip_ids,
            max(1, int(self.rollout_k)),
            self.required_context_frames,
            effective_k,
        )
        self.reset_starts_by_step = reset_starts_by_step
        if init_noise_active:
            rng_snapshot = clone_rng_state(self.store.device)
            try:
                forced_rows = forced_tail_row_indices(
                    self.batch_size,
                    self.real_batch_size,
                    self.force_idle_row,
                    self.forced_idle_batch_fraction,
                    self.force_turn45_row,
                    self.forced_turn45_batch_fraction,
                    self.store.device,
                )
                exact_noisy_rows: torch.Tensor | None = None
                if self.init_noise_regular_row_fraction > 0.0 and self.init_noise_fixed_strength_scale > 0.0:
                    reserved_real_rows = self.dedicated_real_rows + self.periodic_reserved_rows
                    exact_noisy_rows = sample_init_noise_row_mask_in_range(
                        self.batch_size,
                        reserved_real_rows,
                        self.real_batch_size - reserved_real_rows,
                        self.init_noise_regular_row_fraction,
                        self.store.device,
                    )
                if forced_rows.numel() > 0 and exact_noisy_rows is None:
                    _clean_rows, noisy_rows = sample_init_noise_row_masks(
                        self.batch_size,
                        self.init_noise_clean_fraction,
                        self.store.device,
                    )
                    noisy_rows.index_fill_(0, forced_rows, True)
                elif forced_rows.numel() > 0 and exact_noisy_rows is not None:
                    exact_noisy_rows.index_fill_(0, forced_rows, True)
                    noisy_rows = exact_noisy_rows
                else:
                    noisy_rows = exact_noisy_rows
                init_pose_noise_batch = sample_fixed_init_pose_noise_batch(
                    self.store,
                    self.batch_size,
                    self.init_noise_clean_fraction,
                    device=self.store.device,
                    dtype=torch.float32,
                    noisy_rows=noisy_rows,
                    strength_scale=self.init_noise_fixed_strength_scale,
                )
            finally:
                restore_rng_state(rng_snapshot, self.store.device)
        loss_result = pure_ae_rollout_loss_static(
            self.model,
            self.ae,
            self.mean,
            self.std,
            self.store,
            self.rollout_k,
            self.batch_size,
            effective_k,
            clip_ids,
            starts,
            init_clip_ids,
            init_starts,
            reset_starts_by_step,
            self.rl_cfg,
            self.ae_loss_weight,
            self.envelope,
            self.linear_slide_weight,
            self.angular_slide_weight,
            self.foot_height_weight,
            self.alternating_feet_weight,
            self.foot_lift_slide_weight,
            self.pinned_foot_height_weight,
            self.idle_foot_flatness_weight,
            self.slide_tentative_loss_weight,
            self.forced_idle_batch_fraction,
            self.alternating_root_cutoff_mps,
            self.identity_loss_weight,
            self.identity_maxabs_weight,
            self.identity_world_pos_weight,
            self.identity_pelvis_pos_weight,
            self.init_store,
            include_diagnostics=True,
            init_noise_amount=self.init_noise_amount,
            init_noise_clean_fraction=self.init_noise_clean_fraction,
            init_pose_noise_batch=init_pose_noise_batch,
            extra_ae=self.extra_ae,
            extra_mean=self.extra_mean,
            extra_std=self.extra_std,
            extra_ae_loss_weight=self.extra_ae_loss_weight,
            ae5=self.ae5,
            ae5_mean=self.ae5_mean,
            ae5_std=self.ae5_std,
            ae5_loss_weight=self.ae5_loss_weight,
            ae5_reserved_row_start=self.dedicated_real_rows,
            ae5_reserved_rows=self.periodic_reserved_rows,
            ae2=self.ae2,
            ae2_mean=self.ae2_mean,
            ae2_std=self.ae2_std,
            ae2_loss_weight=self.ae2_loss_weight,
            ae2_window_weights=self.ae2_window_weights,
            ae3=self.ae3,
            ae3_mean=self.ae3_mean,
            ae3_std=self.ae3_std,
            ae3_pos_weight=self.ae3_pos_weight,
            ae3_loss_weight=self.ae3_loss_weight,
            pin_logit_gap_loss_weight=self.pin_logit_gap_loss_weight,
            inertia_acceleration_loss_weight=self.inertia_acceleration_loss_weight,
            ae4=self.ae4,
            ae4_input_mean=self.ae4_input_mean,
            ae4_input_std=self.ae4_input_std,
            ae4_target_mean=self.ae4_target_mean,
            ae4_target_std=self.ae4_target_std,
            ae4_loss_weight=self.ae4_loss_weight,
            ae4_bank_pin_loss_weight=self.ae4_bank_pin_loss_weight,
            dedicated_real_rows=self.dedicated_real_rows,
            dedicated_real_loss_multiplier=self.dedicated_real_loss_multiplier,
            periodic_reserved_rows=self.periodic_reserved_rows,
            debug_capture=self.debug_capture,
        )
        self.optimizer.zero_grad(set_to_none=True)
        loss_result.total.backward()
        maybe_clip_rl_gradients(self.model, self.rl_cfg)
        self.optimizer.step()
        return detach_loss_result(loss_result)


def make_pure_ae_stepper(
    model: torch.nn.Module,
    optimizer: torch.optim.Optimizer,
    ae: SimpleAutoencoder,
    mean: torch.Tensor,
    std: torch.Tensor,
    store: SimpleClipStore,
    rollout_k: int,
    batch_size: int,
    start_pools: dict[int, StartPool],
    full_window_start_pools: dict[int, StartPool] | None,
    rl_cfg: RLLossConfig,
    ae_loss_weight: float,
    envelope: dict[str, torch.Tensor | dict[str, float | int | str]] | None = None,
    linear_slide_weight: float = 0.0,
    angular_slide_weight: float = 0.0,
    foot_height_weight: float = 0.0,
    alternating_feet_weight: float = 0.0,
    foot_lift_slide_weight: float = 0.0,
    pinned_foot_height_weight: float = 0.0,
    idle_foot_flatness_weight: float = 0.0,
    forced_idle_batch_fraction: float | None = None,
    forced_turn45_batch_fraction: float | None = None,
    alternating_root_cutoff_mps: float = 1.0,
    identity_loss_weight: float = 0.0,
    identity_maxabs_weight: float = 0.0,
    identity_world_pos_weight: float = 0.0,
    identity_pelvis_pos_weight: float = 0.0,
    init_store: SimpleClipStore | None = None,
    init_start_pool: StartPool | None = None,
    init_noise_amount: float = DEFAULT_INIT_NOISE_AMOUNT,
    init_noise_clean_fraction: float = DEFAULT_INIT_NOISE_CLEAN_FRACTION,
    init_noise_regular_row_fraction: float = 0.0,
    init_noise_fixed_strength_scale: float = 1.0,
    random_init_noise_rows: bool = False,
    adaptive_sampler: AdaptiveAnimationSampler | None = None,
    synthetic_start_pools: dict[int, StartPool] | None = None,
    synthetic_batch_fraction: float = 0.0,
    synthetic_reserved_start_pools: dict[int, StartPool] | None = None,
    synthetic_reserved_rows: int = 0,
    virtual_reserved_start_pools: dict[int, StartPool] | None = None,
    virtual_reserved_rows: int = 0,
    dedicated_real_start_pools: dict[int, StartPool] | None = None,
    dedicated_real_rows: int = 0,
    dedicated_real_loss_multiplier: float = DEFAULT_DEDICATED_REAL_LOSS_MULTIPLIER,
    periodic_reserved_start_pools: dict[int, StartPool] | None = None,
    periodic_reserved_rows: int = 0,
    extra_ae: SimpleAutoencoder | None = None,
    extra_mean: torch.Tensor | None = None,
    extra_std: torch.Tensor | None = None,
    extra_ae_loss_weight: float = 0.0,
    ae5: SimpleAutoencoder | None = None,
    ae5_mean: torch.Tensor | None = None,
    ae5_std: torch.Tensor | None = None,
    ae5_loss_weight: float = 0.0,
    ae6: torch.nn.Module | None = None,
    ae6_mean: torch.Tensor | None = None,
    ae6_std: torch.Tensor | None = None,
    ae6_loss_weight: float = 0.0,
    ae2: torch.nn.Module | None = None,
    ae2_mean: torch.Tensor | None = None,
    ae2_std: torch.Tensor | None = None,
    ae2_loss_weight: float = 0.0,
    ae3: torch.nn.Module | None = None,
    ae3_mean: torch.Tensor | None = None,
    ae3_std: torch.Tensor | None = None,
    ae3_pos_weight: torch.Tensor | None = None,
    ae3_loss_weight: float = 0.0,
    pin_logit_gap_loss_weight: float = 0.0,
    inertia_acceleration_loss_weight: float = 0.0,
    root_accel_pin_loss_ratio: float = 0.0,
    leg_crossing_capsule_loss_weight: float = 0.0,
    ae4: object | None = None,
    ae4_input_mean: torch.Tensor | None = None,
    ae4_input_std: torch.Tensor | None = None,
    ae4_target_mean: torch.Tensor | None = None,
    ae4_target_std: torch.Tensor | None = None,
    ae4_loss_weight: float = 0.0,
    ae4_bank_pin_loss_weight: float = 0.0,
    slide_tentative_loss_weight: float = 0.0,
) -> CudaGraphPureAEStep | EagerPureAEStep:
    # The FK-based identity terms currently allocate small constants inside FK;
    # CUDA graph capture forbids that, so keep this diagnostic loss on eager.
    input_dim, output_dim = tl.make_batch_dims(store.prototype, store.cfg)
    prepare_ae_output_mse_mask(store, output_dim, mean.dtype)
    ae_frames = ae_window_frames_from_dims(mean, input_dim, output_dim)
    if extra_ae is not None and extra_mean is not None:
        extra_frames = ae_window_frames_from_dims(extra_mean, input_dim, output_dim)
        if extra_frames != ae_frames:
            raise ValueError(f"Extra AE window_frames={extra_frames} does not match primary AE window_frames={ae_frames}")
    ae5_enabled = ae5 is not None and ae5_mean is not None and ae5_std is not None and float(ae5_loss_weight) != 0.0
    if ae5_enabled:
        ae5_frames = (
            ik_motion_ae2_window_shape(ae5)[0]
            if is_ik_motion_window_ae(ae5)
            else ae_window_frames_from_dims(ae5_mean, input_dim, output_dim)
        )
        if int(ae5_frames) < int(ae_frames):
            raise ValueError(f"AE5 window_frames={ae5_frames} must be >= primary AE window_frames={ae_frames}")
    if ae6 is not None and ae6_mean is not None and ae6_std is not None and float(ae6_loss_weight) != 0.0:
        ae6_frames = ae_window_frames_from_dims(ae6_mean, input_dim, output_dim)
        if int(ae6_frames) != int(ae_frames):
            raise ValueError(f"AE6 window_frames={ae6_frames} must match primary AE window_frames={ae_frames}")
    eager_reasons: list[str] = []
    if not USE_CUDA_GRAPH:
        eager_reasons.append("USE_CUDA_GRAPH is disabled")
    if store.device.type != "cuda":
        eager_reasons.append(f"device={store.device.type}")
    if float(identity_world_pos_weight) != 0.0:
        eager_reasons.append("identity_world_pos_weight requires eager")
    if eager_reasons:
        raise RuntimeError("Eager mode is disabled; cannot build slow stepper: " + ", ".join(eager_reasons))
    return CudaGraphPureAEStep(
        model,
        optimizer,
        ae,
        mean,
        std,
        store,
        rollout_k,
        batch_size,
        start_pools,
        full_window_start_pools,
        rl_cfg,
        ae_loss_weight,
        envelope,
        linear_slide_weight,
        angular_slide_weight,
        foot_height_weight,
        alternating_feet_weight,
        foot_lift_slide_weight,
        pinned_foot_height_weight,
        idle_foot_flatness_weight,
        forced_idle_batch_fraction,
        forced_turn45_batch_fraction,
        alternating_root_cutoff_mps,
        identity_loss_weight,
        identity_maxabs_weight,
        identity_world_pos_weight,
        identity_pelvis_pos_weight,
        init_store,
        init_start_pool,
        init_noise_amount,
        init_noise_clean_fraction,
        init_noise_regular_row_fraction,
        init_noise_fixed_strength_scale,
        random_init_noise_rows,
        adaptive_sampler,
        synthetic_start_pools,
        synthetic_batch_fraction,
        synthetic_reserved_start_pools,
        synthetic_reserved_rows,
        virtual_reserved_start_pools,
        virtual_reserved_rows,
        dedicated_real_start_pools,
        dedicated_real_rows,
        dedicated_real_loss_multiplier,
        periodic_reserved_start_pools,
        periodic_reserved_rows,
        extra_ae,
        extra_mean,
        extra_std,
        extra_ae_loss_weight,
        ae5,
        ae5_mean,
        ae5_std,
        ae5_loss_weight,
        ae6,
        ae6_mean,
        ae6_std,
        ae6_loss_weight,
        ae2,
        ae2_mean,
        ae2_std,
        ae2_loss_weight,
        ae3,
        ae3_mean,
        ae3_std,
        ae3_pos_weight,
        ae3_loss_weight,
        pin_logit_gap_loss_weight,
        inertia_acceleration_loss_weight,
        root_accel_pin_loss_ratio,
        leg_crossing_capsule_loss_weight,
        ae4,
        ae4_input_mean,
        ae4_input_std,
        ae4_target_mean,
        ae4_target_std,
        ae4_loss_weight,
        ae4_bank_pin_loss_weight,
        slide_tentative_loss_weight,
    )


def validation_rows(pool: StartPool, max_rows: int) -> tuple[torch.Tensor, torch.Tensor]:
    if pool.row_count <= max_rows:
        return pool.clip_ids, pool.starts
    rows = torch.linspace(0, pool.row_count - 1, steps=max_rows, device=pool.starts.device).round().long().unique()
    return pool.clip_ids.index_select(0, rows), pool.starts.index_select(0, rows)


@torch.no_grad()
def validation_ae_score(
    model: torch.nn.Module,
    ae: SimpleAutoencoder,
    mean: torch.Tensor,
    std: torch.Tensor,
    store: SimpleClipStore,
    rollout_k: int,
    pool: StartPool,
) -> float:
    clip_ids, starts = validation_rows(pool, VALIDATION_ROWS)
    cur_idx = starts
    prev_vec, prev_pelvis, prev_payload = target_state(store, clip_ids, cur_idx - 1)
    cur_vec, cur_pelvis, cur_payload = target_state(store, clip_ids, cur_idx)
    input_dim, output_dim = tl.make_batch_dims(store.prototype, store.cfg)
    ae_frames = ae_window_frames_from_dims(mean, input_dim, output_dim)
    ae_context = initial_ae_context(store, clip_ids, cur_idx, ae_frames)
    total = 0.0
    count = 0
    for step in range(max(1, int(rollout_k))):
        inp = build_controller_input(
            store, clip_ids, cur_idx, prev_vec, cur_vec, prev_pelvis, cur_pelvis, prev_payload, cur_payload
        )
        pred_vec = model_forward(model, inp, cur_vec, store, prev_vec)
        raw_feature = torch.cat((inp, pred_vec), dim=-1)
        score = ae_score_rows(ae, mean, std, inp, pred_vec, ae_context, store)
        total += float(score.sum().detach().cpu())
        count += int(score.numel())
        if step + 1 >= int(rollout_k):
            break
        if ae_context is not None:
            ae_context = torch.cat((ae_context[:, 1:, :], raw_feature[:, None, :]), dim=1)
        prev_vec = cur_vec
        prev_pelvis = cur_pelvis
        prev_payload = cur_payload
        cur_vec, cur_pelvis, cur_payload = advance_transition_state(store, clip_ids, cur_idx, pred_vec)
        cur_idx = cur_idx + 1
    return total / float(max(1, count))


def pose_rows(pose: dict[str, torch.Tensor], rows: torch.Tensor) -> dict[str, torch.Tensor]:
    return {key: value.index_select(0, rows) for key, value in pose.items()}


@torch.no_grad()
def fk_positions_by_clip(
    store: SimpleClipStore,
    clip_ids: torch.Tensor,
    root_pos: torch.Tensor,
    root_rot: torch.Tensor,
    pose: dict[str, torch.Tensor],
) -> torch.Tensor:
    ensure_full_store_clips(store)
    out = torch.empty((clip_ids.shape[0], store.J, 3), dtype=root_pos.dtype, device=store.device)
    for clip_id in clip_ids.unique().tolist():
        rows = (clip_ids == int(clip_id)).nonzero(as_tuple=False).flatten()
        pos, _rot, _canon = tl.fk_from_pose(
            store.clips[int(clip_id)],
            root_pos.index_select(0, rows),
            root_rot.index_select(0, rows),
            pose_rows(pose, rows),
            store.device,
        )
        out[rows] = pos
    return out


def _capsule_pair_overlap_rows(
    a0: torch.Tensor,
    a1: torch.Tensor,
    radius_a: float,
    b0: torch.Tensor,
    b1: torch.Tensor,
    radius_b: float,
) -> torch.Tensor:
    d1 = a1 - a0
    d2 = b1 - b0
    r = a0 - b0
    a = d1.square().sum(dim=-1).clamp_min(1.0e-8)
    e = d2.square().sum(dim=-1).clamp_min(1.0e-8)
    b = (d1 * d2).sum(dim=-1)
    c = (d1 * r).sum(dim=-1)
    f = (d2 * r).sum(dim=-1)
    denom = (a * e - b.square()).clamp_min(1.0e-8)
    s = ((b * f - c * e) / denom).clamp(0.0, 1.0)
    t = (b * s + f) / e
    s_if_t_low = (-c / a).clamp(0.0, 1.0)
    s_if_t_high = ((b - c) / a).clamp(0.0, 1.0)
    s = torch.where(t < 0.0, s_if_t_low, torch.where(t > 1.0, s_if_t_high, s))
    t = t.clamp(0.0, 1.0)
    closest_a = a0 + d1 * s.unsqueeze(-1)
    closest_b = b0 + d2 * t.unsqueeze(-1)
    dist = (closest_a - closest_b).square().sum(dim=-1).clamp_min(1.0e-12).sqrt()
    return F.relu(float(radius_a + radius_b) - dist)


def leg_crossing_capsule_loss_rows(
    store: SimpleClipStore,
    pred_vec: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    leg_entries = tuple(
        (int(limb_i), spec)
        for limb_i, spec in enumerate(store.ik_payload_slices)
        if str(spec.get("kind", "")).lower().strip() == "leg"
    )
    if int(store.ik_payload_dim) == 0 or len(leg_entries) != 2:
        zero = torch.zeros((pred_vec.shape[0],), dtype=pred_vec.dtype, device=pred_vec.device)
        return zero, zero, zero
    payload = tl.clean_ik_payload(
        pred_vec[:, payload_slice(store)],
        store.ik_payload_slices,
        store.ik_payload_dim,
    )
    pos_parts, _rot_parts, start_rot_parts, _toe_parts = _parse_payload_parts(payload, store)
    pelvis_pos = pred_vec[:, 0:3]
    pelvis_rot = tl.rotation_6d_to_matrix(tl.clean_6d(pred_vec[:, 3:9]))
    leg_points: dict[str, tuple[torch.Tensor, torch.Tensor, torch.Tensor]] = {}
    for limb_i, spec in leg_entries:
        side = str(spec.get("side", "")).lower().strip()
        if side not in {"l", "r"}:
            continue
        start_idx = int(spec["start"])
        mid_idx = int(spec["mid"])
        end_idx = int(spec["end"])
        thigh_offset = store.local_offsets[start_idx].to(dtype=pred_vec.dtype).reshape(1, 3)
        thigh_root = torch.matmul(thigh_offset.unsqueeze(1), pelvis_rot).squeeze(1) + pelvis_pos
        start_rot = tl.rotation_6d_to_matrix(start_rot_parts[limb_i])
        calf_offset = store.local_offsets[mid_idx].to(dtype=pred_vec.dtype).reshape(1, 3)
        calf_root = torch.matmul(calf_offset.unsqueeze(1), start_rot).squeeze(1) + thigh_root
        foot_root = pos_parts[limb_i]
        if tl.IK_CLAMP_END_EFFECTORS_TO_REACH:
            lower_len = store.ik_limb_lengths[limb_i, 1].to(dtype=pred_vec.dtype)
            delta = foot_root - calf_root
            dist = torch.linalg.norm(delta, dim=-1, keepdim=True)
            fallback = torch.matmul(
                store.local_offsets[end_idx].to(dtype=pred_vec.dtype).reshape(1, 3).unsqueeze(1),
                start_rot,
            ).squeeze(1)
            axis = torch.where(dist > 1.0e-8, tl.normalize(delta), tl.normalize(fallback))
            foot_root = calf_root + axis * dist.clamp_min(1.0e-8).clamp(max=lower_len.reshape(1, 1) - 1.0e-5)
        leg_points[side] = (thigh_root, calf_root, foot_root)
    if "l" not in leg_points or "r" not in leg_points:
        zero = torch.zeros((pred_vec.shape[0],), dtype=pred_vec.dtype, device=pred_vec.device)
        return zero, zero, zero
    thigh_l, calf_l, foot_l = leg_points["l"]
    thigh_r, calf_r, foot_r = leg_points["r"]
    overlaps = torch.stack(
        (
            _capsule_pair_overlap_rows(thigh_l, calf_l, 0.064, thigh_r, calf_r, 0.064),
            _capsule_pair_overlap_rows(thigh_l, calf_l, 0.064, calf_r, foot_r, 0.052),
            _capsule_pair_overlap_rows(calf_l, foot_l, 0.052, thigh_r, calf_r, 0.064),
            _capsule_pair_overlap_rows(calf_l, foot_l, 0.052, calf_r, foot_r, 0.052),
        ),
        dim=-1,
    )
    raw_rows = overlaps.amax(dim=-1)
    loss_rows = overlaps.square().mean(dim=-1)
    rate_rows = (raw_rows > 0.0).to(dtype=pred_vec.dtype)
    return loss_rows, raw_rows, rate_rows


@torch.no_grad()
def rollout_joint_error(
    model: torch.nn.Module,
    store: SimpleClipStore,
    rollout_k: int,
    pool: StartPool,
) -> tuple[float, float]:
    clip_ids, starts = validation_rows(pool, VALIDATION_ROWS)
    cur_idx = starts
    prev_vec, prev_pelvis, prev_payload = target_state(store, clip_ids, cur_idx - 1)
    cur_vec, cur_pelvis, cur_payload = target_state(store, clip_ids, cur_idx)
    total_error = 0.0
    total_frames = 0
    max_error = 0.0
    for step in range(max(1, int(rollout_k))):
        inp = build_controller_input(
            store, clip_ids, cur_idx, prev_vec, cur_vec, prev_pelvis, cur_pelvis, prev_payload, cur_payload
        )
        pred_vec = model_forward(model, inp, cur_vec, store, prev_vec)
        pred_pose, _raw_pose = tl.output_to_pose(pred_vec, store.prototype)
        target_idx = cur_idx + 1
        target_root_pos, target_root_rot, _target_yaw, _target_heading = store.root_state(clip_ids, target_idx)
        pred_root_pos, pred_root_rot = transition_output_root_state(store, clip_ids, cur_idx)
        pred_global = fk_positions_by_clip(store, clip_ids, pred_root_pos, pred_root_rot, pred_pose)
        target_global = fk_positions_by_clip(
            store, clip_ids, target_root_pos, target_root_rot, store.get_pose(clip_ids, target_idx)
        )
        per_frame = (pred_global - target_global).norm(dim=-1).mean(dim=-1)
        total_error += float(per_frame.sum().detach().cpu())
        total_frames += int(per_frame.numel())
        max_error = max(max_error, float(per_frame.max().detach().cpu()))
        if step + 1 >= int(rollout_k):
            break
        prev_vec = cur_vec
        prev_pelvis = cur_pelvis
        prev_payload = cur_payload
        cur_vec, cur_pelvis, cur_payload = advance_transition_state(store, clip_ids, cur_idx, pred_vec)
        cur_idx = target_idx
    return total_error / float(max(1, total_frames)), max_error


_DEBUG_ROLLOUT_NEXT_CHECK_AT = 0.0
_DEBUG_ROLLOUT_ARM_NEXT_CHECK_AT = 0.0


def debug_rollout_request_path(run_dir: Path) -> Path:
    return run_dir / "debug" / DEBUG_ROLLOUT_REQUEST_NAME


def debug_rollout_artifact_path(run_dir: Path) -> Path:
    return run_dir / "debug" / DEBUG_ROLLOUT_ARTIFACT_NAME


def maybe_arm_debug_rollout_snapshot(run_dir: Path, stepper: object) -> None:
    global _DEBUG_ROLLOUT_ARM_NEXT_CHECK_AT
    now = time.perf_counter()
    if now < _DEBUG_ROLLOUT_ARM_NEXT_CHECK_AT:
        return
    _DEBUG_ROLLOUT_ARM_NEXT_CHECK_AT = now + float(DEBUG_ROLLOUT_CHECK_INTERVAL_S)
    if not debug_rollout_request_path(run_dir).exists():
        return
    arm = getattr(stepper, "arm_debug_export_snapshot", None)
    if callable(arm):
        arm()


def pause_request_path(run_dir: Path) -> Path:
    return run_dir / "debug" / TRAIN_PAUSE_REQUEST_NAME


def paused_state_path(run_dir: Path) -> Path:
    return run_dir / "debug" / TRAIN_PAUSED_STATE_NAME


def wait_for_training_pause_release(run_dir: Path, run_id: str, step: int) -> float:
    request_path = pause_request_path(run_dir)
    if not request_path.exists():
        paused_state_path(run_dir).unlink(missing_ok=True)
        return 0.0
    debug_dir = run_dir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    state_path = paused_state_path(run_dir)
    paused_at = time.perf_counter()
    state_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "step": int(step),
                "paused_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"TRAINING_PAUSED_BY_VIEWER step={step} path={request_path}", flush=True)
    try:
        while request_path.exists():
            time.sleep(float(TRAIN_PAUSE_CHECK_INTERVAL_S))
    finally:
        state_path.unlink(missing_ok=True)
    paused_s = time.perf_counter() - paused_at
    print(f"TRAINING_RESUMED_BY_VIEWER step={step} paused_s={paused_s:.2f}", flush=True)
    return paused_s


def debug_rollout_bones(store: SimpleClipStore) -> list[list[int]]:
    return [
        [int(parent), int(child)]
        for child, parent in enumerate(store.prototype.parents_body_list)
        if int(parent) >= 0
    ]


@torch.no_grad()
def build_debug_rollout_payload(
    model: torch.nn.Module,
    store: SimpleClipStore,
    run_id: str,
    step: int,
    rollout_k: int,
    effective_k: torch.Tensor,
    clip_ids: torch.Tensor,
    starts: torch.Tensor,
    init_clip_ids: torch.Tensor | None,
    init_starts: torch.Tensor | None,
    reset_starts_by_step: torch.Tensor | None,
    init_store: SimpleClipStore | None,
    ae_frames: int,
    request_payload: dict[str, object] | None,
) -> dict[str, object]:
    device = store.device
    clip_ids = clip_ids.to(device=device, dtype=torch.long)
    starts = starts.to(device=device, dtype=torch.long)
    effective_k = effective_k.to(device=device, dtype=torch.long)
    max_k = max(1, int(rollout_k))
    if init_store is not None and init_clip_ids is not None and init_starts is not None:
        init_clip_ids = init_clip_ids.to(device=init_store.device, dtype=torch.long)
        init_starts = init_starts.to(device=init_store.device, dtype=torch.long)
        init_prev_starts, init_cur_starts = rollout_init_context_indices(init_starts)
        prev_vec, prev_pelvis, prev_payload = target_state(init_store, init_clip_ids, init_prev_starts)
        cur_vec, cur_pelvis, cur_payload = target_state(init_store, init_clip_ids, init_cur_starts)
        if isinstance(getattr(store, "synthetic", None), torch.Tensor):
            synth_rows = store.synthetic.index_select(0, clip_ids).reshape(-1, 1)
            synth_prev_vec, synth_prev_pelvis, synth_prev_payload = target_state(store, clip_ids, starts - 1)
            synth_cur_vec, synth_cur_pelvis, synth_cur_payload = target_state(store, clip_ids, starts)
            prev_vec = torch.where(synth_rows, synth_prev_vec, prev_vec.to(device))
            prev_pelvis = torch.where(synth_rows, synth_prev_pelvis, prev_pelvis.to(device))
            prev_payload = torch.where(synth_rows, synth_prev_payload, prev_payload.to(device))
            cur_vec = torch.where(synth_rows, synth_cur_vec, cur_vec.to(device))
            cur_pelvis = torch.where(synth_rows, synth_cur_pelvis, cur_pelvis.to(device))
            cur_payload = torch.where(synth_rows, synth_cur_payload, cur_payload.to(device))
    else:
        prev_vec, prev_pelvis, prev_payload = target_state(store, clip_ids, starts - 1)
        cur_vec, cur_pelvis, cur_payload = target_state(store, clip_ids, starts)
    cur_idx = starts.clone()
    ae_context = initial_ae_context(store, clip_ids, cur_idx, int(ae_frames))
    positions_frames: list[torch.Tensor] = []
    pin_logits_frames: list[torch.Tensor] = []
    pin_mask_frames: list[torch.Tensor] = []
    foot_height_frames: list[torch.Tensor] = []
    reset_frames: list[torch.Tensor] = []

    root_pos, root_rot, _yaw, _heading = store.root_state(clip_ids, cur_idx)
    cur_pose, _cur_raw_pose = tl.output_to_pose(cur_vec, store.prototype)
    positions_frames.append(fk_positions_by_clip(store, clip_ids, root_pos, root_rot, cur_pose))
    empty_pin_logits = torch.zeros(
        (int(clip_ids.numel()), int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)),
        dtype=cur_vec.dtype,
        device=device,
    )
    zero_pin_mask = torch.zeros((int(clip_ids.numel()), int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)), dtype=torch.bool, device=device)
    current_reset = torch.zeros((int(clip_ids.numel()),), dtype=torch.bool, device=device)
    pin_logits_frames.append(empty_pin_logits)
    pin_mask_frames.append(zero_pin_mask)
    foot_height_frames.append(foot_roll_lowest_heights_from_vec(store, cur_vec))
    reset_frames.append(current_reset)

    output_uses_future_root = tl.output_reference_uses_future_root()
    for rollout_step in range(max_k):
        inp = build_controller_input(
            store, clip_ids, cur_idx, prev_vec, cur_vec, prev_pelvis, cur_pelvis, prev_payload, cur_payload
        )
        raw_pred = model_raw_output(model, inp, cur_vec, store)
        pred_vec = clean_output_vector(raw_pred, store, cur_vec, prev_vec)
        cleaned_heights = foot_roll_lowest_heights_from_vec(store, pred_vec)
        pin_logits = foot_pin_logits_from_raw(raw_pred, store)
        pred_pose, _pred_raw_pose = tl.output_to_pose(pred_vec, store.prototype)
        out_root_pos, out_root_rot = transition_output_root_state(store, clip_ids, cur_idx)
        positions_frames.append(fk_positions_by_clip(store, clip_ids, out_root_pos, out_root_rot, pred_pose))
        pin_logits_frames.append(pin_logits if pin_logits.numel() else empty_pin_logits)
        pin_mask_frames.append(
            foot_pin_mask_from_heights_and_logits(cleaned_heights, pin_logits)
            if cleaned_heights.numel() and pin_logits.numel()
            else zero_pin_mask
        )
        foot_height_frames.append(cleaned_heights)
        reset_frames.append(current_reset)

        if rollout_step + 1 >= max_k:
            break
        raw_feature = torch.cat((inp, pred_vec), dim=-1)
        continuing = effective_k > (rollout_step + 1)
        if output_uses_future_root:
            next_vec = clean_output_vector(pred_vec, store)
        else:
            next_frame_root_pos, next_frame_root_rot, _next_yaw, _next_heading = store.root_state(clip_ids, cur_idx + 1)
            next_vec = rebase_output_vector_root(
                store,
                pred_vec,
                out_root_pos,
                out_root_rot,
                next_frame_root_pos,
                next_frame_root_rot,
        )
        next_pelvis, next_payload = next_vec[:, :3], next_vec[:, payload_slice(store)]
        reset = training_reset_rows(store, clip_ids, cur_idx, continuing)
        advance = continuing & (~reset)
        reset_starts = (
            reset_starts_by_step[rollout_step].to(device=device, dtype=torch.long)
            if reset_starts_by_step is not None
            else sample_same_clip_training_starts(
                store,
                clip_ids,
                int(ae_frames),
                (effective_k - int(rollout_step + 1)).clamp_min(1),
            )
        )
        reset_prev_vec, reset_prev_pelvis, reset_prev_payload = target_state(store, clip_ids, reset_starts - 1)
        reset_cur_vec, reset_cur_pelvis, reset_cur_payload = target_state(store, clip_ids, reset_starts)
        if ae_context is not None:
            shifted_context = torch.cat((ae_context[:, 1:, :], raw_feature[:, None, :]), dim=1)
            reset_context = initial_ae_context(store, clip_ids, reset_starts, int(ae_frames))
            assert reset_context is not None
            ae_context = torch.where(
                reset[:, None, None],
                reset_context,
                torch.where(advance[:, None, None], shifted_context, ae_context),
            )
        prev_vec = torch.where(reset[:, None], reset_prev_vec, torch.where(advance[:, None], cur_vec, prev_vec))
        prev_pelvis = torch.where(reset[:, None], reset_prev_pelvis, torch.where(advance[:, None], cur_pelvis, prev_pelvis))
        prev_payload = torch.where(reset[:, None], reset_prev_payload, torch.where(advance[:, None], cur_payload, prev_payload))
        cur_vec = torch.where(reset[:, None], reset_cur_vec, torch.where(advance[:, None], next_vec, cur_vec))
        cur_pelvis = torch.where(reset[:, None], reset_cur_pelvis, torch.where(advance[:, None], next_pelvis, cur_pelvis))
        cur_payload = torch.where(reset[:, None], reset_cur_payload, torch.where(advance[:, None], next_payload, cur_payload))
        cur_idx = torch.where(reset, reset_starts, torch.where(continuing, cur_idx + 1, cur_idx))
        current_reset = reset

    clip_ids_cpu = clip_ids.detach().cpu()
    starts_cpu = starts.detach().cpu()
    effective_k_cpu = effective_k.detach().cpu()
    row_losses_tensor = debug_capture.get("row_losses")
    row_losses_cpu = (
        row_losses_tensor.detach().cpu()
        if isinstance(row_losses_tensor, torch.Tensor)
        else None
    )
    init_noisy_tensor = debug_capture.get("init_noisy_rows")
    init_noisy_cpu = (
        init_noisy_tensor.detach().cpu()
        if isinstance(init_noisy_tensor, torch.Tensor)
        else None
    )
    synthetic_cpu = (
        store.synthetic.index_select(0, clip_ids).detach().cpu()
        if isinstance(getattr(store, "synthetic", None), torch.Tensor)
        else torch.zeros_like(clip_ids_cpu, dtype=torch.bool)
    )
    rows = []
    for row_i, clip_id_value in enumerate(clip_ids_cpu.tolist()):
        clip = store.clips[int(clip_id_value)]
        rows.append(
            {
                "row": int(row_i),
                "clip_id": int(clip_id_value),
                "clip_name": Path(str(clip.path)).stem,
                "clip_path": str(clip.path),
                "start": int(starts_cpu[row_i]),
                "effective_k": int(effective_k_cpu[row_i]),
                **(
                    {"row_loss": float(row_losses_cpu[row_i])}
                    if row_losses_cpu is not None and int(row_losses_cpu.numel()) > row_i
                    else {}
                ),
                **(
                    {"init_noisy": bool(init_noisy_cpu[row_i])}
                    if init_noisy_cpu is not None and int(init_noisy_cpu.numel()) > row_i
                    else {}
                ),
                "virtual": bool(synthetic_cpu[row_i]),
            }
        )
    return {
        "schema_version": 1,
        "computed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "run_id": str(run_id),
        "step": int(step),
        "fps": float(store.prototype.fps),
        "joint_names": list(store.prototype.body_names),
        "bones": debug_rollout_bones(store),
        "rows": rows,
        "positions": torch.stack(positions_frames, dim=1).detach().cpu().tolist(),
        "pin_logits": torch.stack(pin_logits_frames, dim=1).detach().cpu().tolist(),
        "pin_mask": torch.stack(pin_mask_frames, dim=1).detach().cpu().tolist(),
        "foot_heights": torch.stack(foot_height_frames, dim=1).detach().cpu().tolist(),
        "reset_flags": torch.stack(reset_frames, dim=1).detach().cpu().tolist(),
        "request": request_payload,
        "source": "on_demand_recompute_from_latest_sample",
    }


@torch.no_grad()
def build_debug_rollout_payload_from_buffers(
    store: SimpleClipStore,
    run_id: str,
    step: int,
    effective_k: torch.Tensor,
    clip_ids: torch.Tensor,
    starts: torch.Tensor,
    debug_capture: dict[str, torch.Tensor],
    request_payload: dict[str, object] | None,
) -> dict[str, object]:
    clip_ids = clip_ids.to(device=store.device, dtype=torch.long)
    starts = starts.to(device=store.device, dtype=torch.long)
    effective_k = effective_k.to(device=store.device, dtype=torch.long)
    vectors = debug_capture["vectors"]
    frame_idx = debug_capture["frame_idx"].to(device=store.device, dtype=torch.long)
    positions_frames: list[torch.Tensor] = []
    foot_height_frames: list[torch.Tensor] = []
    frame_count = int(vectors.shape[1])
    for frame_i in range(frame_count):
        vec = vectors[:, frame_i, :]
        root_pos, root_rot, _yaw, _heading = store.root_state(clip_ids, frame_idx[:, frame_i])
        pose, _raw_pose = tl.output_to_pose(vec, store.prototype)
        positions_frames.append(fk_positions_by_clip(store, clip_ids, root_pos, root_rot, pose))
        foot_height_frames.append(foot_roll_lowest_heights_from_vec(store, vec))

    clip_ids_cpu = clip_ids.detach().cpu()
    starts_cpu = starts.detach().cpu()
    effective_k_cpu = effective_k.detach().cpu()
    row_losses_tensor = debug_capture.get("row_losses")
    row_losses_cpu = (
        row_losses_tensor.detach().cpu()
        if isinstance(row_losses_tensor, torch.Tensor)
        else None
    )
    init_noisy_tensor = debug_capture.get("init_noisy_rows")
    init_noisy_cpu = (
        init_noisy_tensor.detach().cpu()
        if isinstance(init_noisy_tensor, torch.Tensor)
        else None
    )
    synthetic_cpu = (
        store.synthetic.index_select(0, clip_ids).detach().cpu()
        if isinstance(getattr(store, "synthetic", None), torch.Tensor)
        else torch.zeros_like(clip_ids_cpu, dtype=torch.bool)
    )
    rows = []
    for row_i, clip_id_value in enumerate(clip_ids_cpu.tolist()):
        clip = store.clips[int(clip_id_value)]
        rows.append(
            {
                "row": int(row_i),
                "clip_id": int(clip_id_value),
                "clip_name": Path(str(clip.path)).stem,
                "clip_path": str(clip.path),
                "start": int(starts_cpu[row_i]),
                "effective_k": int(effective_k_cpu[row_i]),
                **(
                    {"row_loss": float(row_losses_cpu[row_i])}
                    if row_losses_cpu is not None and int(row_losses_cpu.numel()) > row_i
                    else {}
                ),
                **(
                    {"init_noisy": bool(init_noisy_cpu[row_i])}
                    if init_noisy_cpu is not None and int(init_noisy_cpu.numel()) > row_i
                    else {}
                ),
                "virtual": bool(synthetic_cpu[row_i]),
            }
        )
    return {
        "schema_version": 1,
        "computed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "run_id": str(run_id),
        "step": int(step),
        "fps": float(store.prototype.fps),
        "joint_names": list(store.prototype.body_names),
        "bones": debug_rollout_bones(store),
        "rows": rows,
        "positions": torch.stack(positions_frames, dim=1).detach().cpu().tolist(),
        "pin_logits": debug_capture["pin_logits"].detach().cpu().tolist(),
        "pin_mask": debug_capture["pin_mask"].detach().cpu().tolist(),
        "foot_heights": torch.stack(foot_height_frames, dim=1).detach().cpu().tolist(),
        "reset_flags": debug_capture["reset_flags"].detach().cpu().tolist(),
        "request": request_payload,
        "source": "latest_gpu_rollout_buffer",
    }


def clone_debug_rollout_tensors(
    effective_k: torch.Tensor,
    clip_ids: torch.Tensor,
    starts: torch.Tensor,
    debug_capture: dict[str, torch.Tensor],
    device: torch.device | None = None,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, dict[str, torch.Tensor]]:
    """Move a rollout snapshot to the export device before JSON export."""

    target_device = device
    effective_k_snapshot = effective_k.detach().to(device=target_device, copy=True) if target_device is not None else effective_k.detach().clone()
    clip_ids_snapshot = clip_ids.detach().to(device=target_device, copy=True) if target_device is not None else clip_ids.detach().clone()
    starts_snapshot = starts.detach().to(device=target_device, copy=True) if target_device is not None else starts.detach().clone()
    capture_snapshot: dict[str, torch.Tensor] = {}
    for key, value in debug_capture.items():
        if isinstance(value, torch.Tensor):
            capture_snapshot[key] = (
                value.detach().to(device=target_device, copy=True)
                if target_device is not None
                else value.detach().clone()
            )
    return effective_k_snapshot, clip_ids_snapshot, starts_snapshot, capture_snapshot


def debug_rollout_export_store(store: SimpleClipStore) -> SimpleClipStore:
    if store.device.type != "cuda":
        return store
    cached = getattr(store, "_debug_rollout_cpu_store", None)
    if isinstance(cached, SimpleClipStore):
        return cached
    if all(isinstance(clip, tl.MotionClip) for clip in store.clips):
        export_clips = list(store.clips)
    else:
        specs = [(Path(clip.path), bool(clip.cyclic_animation)) for clip in store.clips]
        export_clips = load_clips(specs, store.cfg)
    cpu_store = cached_simple_clip_store(export_clips, store.cfg, torch.device("cpu"))
    setattr(store, "_debug_rollout_cpu_store", cpu_store)
    return cpu_store


def maybe_export_debug_rollout(
    run_dir: Path,
    run_id: str,
    step: int,
    stepper: object,
) -> bool:
    global _DEBUG_ROLLOUT_NEXT_CHECK_AT
    now = time.perf_counter()
    if now < _DEBUG_ROLLOUT_NEXT_CHECK_AT:
        return False
    _DEBUG_ROLLOUT_NEXT_CHECK_AT = now + float(DEBUG_ROLLOUT_CHECK_INTERVAL_S)
    request_path = debug_rollout_request_path(run_dir)
    if not request_path.exists():
        return False
    try:
        request_payload = json.loads(request_path.read_text(encoding="utf-8"))
    except Exception:
        request_payload = {"unreadable_request": True}
    model = getattr(stepper, "model", None)
    store = getattr(stepper, "store", None)
    if model is None or store is None:
        return False
    request = request_payload if isinstance(request_payload, dict) else None
    debug_capture = getattr(stepper, "debug_capture", None)
    effective_k = getattr(stepper, "effective_k", None)
    clip_ids = getattr(stepper, "clip_ids", None)
    starts = getattr(stepper, "starts", None)
    stepper_kind = str(getattr(stepper, "kind", ""))
    was_training: bool | None = None
    cpu_rng: torch.Tensor | None = None
    cuda_rng: torch.Tensor | None = None
    try:
        if (
            isinstance(debug_capture, dict)
            and effective_k is not None
            and clip_ids is not None
            and starts is not None
        ):
            if stepper_kind.startswith("cuda_graph"):
                consume = getattr(stepper, "consume_debug_export_snapshot", None)
                snapshot = consume() if callable(consume) else None
                if snapshot is None:
                    return False
                effective_k, clip_ids, starts, debug_capture = snapshot
                payload_store = debug_rollout_export_store(store)
                effective_k, clip_ids, starts, debug_capture = clone_debug_rollout_tensors(
                    effective_k,
                    clip_ids,
                    starts,
                    debug_capture,
                    device=payload_store.device,
                )
                payload = build_debug_rollout_payload_from_buffers(
                    payload_store,
                    run_id,
                    step,
                    effective_k,
                    clip_ids,
                    starts,
                    debug_capture,
                    request,
                )
                payload["source"] = "latest_cuda_graph_rollout_mirror"
            else:
                payload_store = debug_rollout_export_store(store)
                effective_k, clip_ids, starts, debug_capture = clone_debug_rollout_tensors(
                    effective_k,
                    clip_ids,
                    starts,
                    debug_capture,
                    device=payload_store.device,
                )
                payload = build_debug_rollout_payload_from_buffers(
                    payload_store,
                    run_id,
                    step,
                    effective_k,
                    clip_ids,
                    starts,
                    debug_capture,
                    request,
                )
                payload["source"] = (
                    "latest_cuda_rollout_snapshot"
                    if getattr(store, "device", torch.device("cpu")).type == "cuda"
                    else payload.get("source", "latest_gpu_rollout_buffer")
                )
        else:
            was_training = bool(model.training)
            cpu_rng = torch.get_rng_state()
            cuda_rng = torch.cuda.get_rng_state(store.device) if store.device.type == "cuda" else None
            model.eval()
            payload = build_debug_rollout_payload(
                model,
                store,
                run_id,
                step,
                int(getattr(stepper, "rollout_k")),
                effective_k,
                clip_ids,
                starts,
                getattr(stepper, "init_clip_ids", None),
                getattr(stepper, "init_starts", None),
                getattr(stepper, "reset_starts_by_step", None),
                getattr(stepper, "init_store", None),
                int(getattr(stepper, "ae_frames", 1)),
                request,
            )
        artifact_path = debug_rollout_artifact_path(run_dir)
        if request is not None:
            requested_artifact = request.get("artifact_name")
            if isinstance(requested_artifact, str) and requested_artifact.strip():
                safe_name = Path(requested_artifact).name
                if safe_name.endswith(".json"):
                    artifact_path = run_dir / "debug" / "rollouts" / safe_name
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = artifact_path.with_suffix(artifact_path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload), encoding="utf-8")
        tmp_path.replace(artifact_path)
        try:
            request_path.unlink()
        except FileNotFoundError:
            pass
        payload_source = str(payload.get("source", "unknown"))
        row_count = len(payload.get("rows", [])) if isinstance(payload.get("rows"), list) else -1
        print(f"debug_rollout_exported step={step} path={artifact_path}", flush=True)
        print(
            f"WARNING_DEBUG_ROLLOUT_LIVE_EXPORT step={step} source={payload_source} rows={row_count} "
            f"artifact={artifact_path}",
            flush=True,
        )
        return True
    except Exception as exc:
        print(f"debug_rollout_export_failed step={step} error={exc}", flush=True)
        try:
            request_path.unlink()
        except FileNotFoundError:
            pass
        return False
    finally:
        if cpu_rng is not None:
            torch.set_rng_state(cpu_rng)
        if cuda_rng is not None:
            torch.cuda.set_rng_state(cuda_rng, store.device)
        if was_training is not None:
            model.train(was_training)


def save_controller_checkpoint(
    run_dir: Path,
    run_id: str,
    tag: str,
    model: torch.nn.Module,
    optimizer: torch.optim.Optimizer,
    step: int,
    best: float,
    rollout_k: int,
    cfg: tl.TrainConfig,
    metadata: dict,
    adaptive_sampler: AdaptiveAnimationSampler | None = None,
) -> Path:
    path = checkpoint_path(run_dir, run_id, tag)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = tl.checkpoint_payload(model, optimizer, step, best, rollout_k, cfg, metadata)
    payload["rng_state"] = checkpoint_rng_state()
    if adaptive_sampler is not None:
        payload["adaptive_sampler_state"] = adaptive_sampler.checkpoint_state_dict()
    tmp_key = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:12]
    last_error: Exception | None = None
    for attempt in range(3):
        tmp = path.parent / f".tmp_ckpt_{tmp_key}_{attempt}.pt"
        try:
            if tmp.exists():
                tmp.unlink()
            torch.save(payload, tmp)
            tmp.replace(path)
            return path
        except Exception as exc:
            last_error = exc
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            time.sleep(0.25 * float(attempt + 1))
    assert last_error is not None
    raise last_error
    return path


def load_controller_init_checkpoint(
    model: torch.nn.Module,
    path: Path,
    expected_body_mode: str | None = None,
) -> dict:
    ckpt = load_controller_checkpoint(path)
    ckpt_runtime.require_current_ik_controller_checkpoint(ckpt, path)
    policy = ckpt_runtime.checkpoint_policy(ckpt)
    checkpoint_root = str(policy.get("output_reference_root", "")).strip().lower()
    if checkpoint_root != tl.OUTPUT_REFERENCE_ROOT:
        raise ValueError(
            f"Controller init checkpoint uses output_reference_root={checkpoint_root!r}; "
            f"expected {tl.OUTPUT_REFERENCE_ROOT!r}: {path}"
        )
    checkpoint_prediction = str(policy.get("output_prediction_mode", tl.OUTPUT_PREDICTION_MODE_ABSOLUTE)).strip().lower()
    if checkpoint_prediction != tl.normalized_output_prediction_mode():
        raise ValueError(
            f"Controller init checkpoint uses output_prediction_mode={checkpoint_prediction!r}; "
            f"expected {tl.normalized_output_prediction_mode()!r}: {path}"
        )
    if expected_body_mode is not None:
        metadata = ckpt.get("metadata", {})
        config = ckpt.get("config", {})
        raw_mode = None
        if isinstance(metadata, dict):
            raw_mode = metadata.get("body_mode") or policy.get("body_mode")
        if raw_mode is None and isinstance(config, dict):
            raw_mode = config.get("body_mode")
        if raw_mode is None:
            raise ValueError(f"Controller init checkpoint is missing body_mode; expected {expected_body_mode!r}: {path}")
        checkpoint_body_mode = tl.normalized_body_mode(raw_mode)
        expected = tl.normalized_body_mode(expected_body_mode)
        if checkpoint_body_mode != expected:
            raise ValueError(
                f"Controller init checkpoint uses body_mode={checkpoint_body_mode!r}; "
                f"expected {expected!r}: {path}"
            )
    state_dict = dict(ckpt["model"])
    model_state = model.state_dict()
    weight_keys = [key for key in model_state if key.endswith(".weight")]
    bias_keys = [key for key in model_state if key.endswith(".bias")]
    final_weight_key = weight_keys[-1] if weight_keys else ""
    final_bias_key = bias_keys[-1] if bias_keys else ""
    extended_output_head = False
    if (
        final_weight_key in state_dict
        and final_bias_key in state_dict
        and state_dict[final_weight_key].ndim == 2
        and model_state[final_weight_key].ndim == 2
        and int(state_dict[final_weight_key].shape[1]) == int(model_state[final_weight_key].shape[1])
        and int(model_state[final_weight_key].shape[0]) == int(state_dict[final_weight_key].shape[0]) + int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)
        and int(model_state[final_bias_key].shape[0]) == int(state_dict[final_bias_key].shape[0]) + int(tl.FOOT_ROLL_PIN_OUTPUT_DIM)
    ):
        expanded_weight = model_state[final_weight_key].clone()
        expanded_bias = model_state[final_bias_key].clone()
        old_rows = int(state_dict[final_weight_key].shape[0])
        expanded_weight.zero_()
        expanded_bias.zero_()
        expanded_weight[:old_rows].copy_(state_dict[final_weight_key])
        expanded_bias[:old_rows].copy_(state_dict[final_bias_key])
        expanded_bias[old_rows:].fill_(-1.0)
        state_dict[final_weight_key] = expanded_weight
        state_dict[final_bias_key] = expanded_bias
        extended_output_head = True
    model.load_state_dict(state_dict, strict=True)
    ckpt["_output_head_extended_for_foot_roll"] = extended_output_head
    apply_foot_roll_runtime_policy_from_checkpoint(ckpt)
    return ckpt


def load_controller_optimizer_state(
    optimizer: torch.optim.Optimizer,
    ckpt: dict,
    path: Path,
    device: torch.device,
) -> None:
    if "optimizer" not in ckpt:
        raise ValueError(f"Controller checkpoint has no optimizer state: {path}")
    optimizer.load_state_dict(ckpt["optimizer"])
    move_optimizer_state_to_device(optimizer, device)


def warm_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--npz", default=None)
    parser.add_argument("--periodic-folder", default=None)
    parser.add_argument("--nonperiodic-folder", default=None)
    parser.add_argument("--synthetic-npz", default=None)
    parser.add_argument("--synthetic-folder", default=None)
    parser.add_argument("--virtual-npz", default=None)
    parser.add_argument("--virtual-folder", default=None)
    parser.add_argument(
        "--virtual-batch-fraction",
        "--synthetic-batch-fraction",
        dest="synthetic_batch_fraction",
        type=float,
        default=DEFAULT_SYNTHETIC_BATCH_FRACTION,
    )
    parser.add_argument("--synthetic-reserved-rows", type=int, default=DEFAULT_SYNTHETIC_RESERVED_ROWS)
    parser.add_argument("--virtual-reserved-rows", type=int, default=DEFAULT_VIRTUAL_RESERVED_ROWS)
    parser.add_argument(
        "--periodic-reserved-batch-fraction",
        "--omni-reserved-batch-fraction",
        dest="periodic_reserved_batch_fraction",
        type=float,
        default=0.0,
        help="Reserve this fraction of real batch rows for cyclic/periodic clips, i.e. the omni folder.",
    )
    parser.add_argument("--dedicated-real-clip-stems", nargs="*", default=[])
    parser.add_argument("--dedicated-real-rows", type=int, default=0)
    parser.add_argument("--dedicated-real-loss-multiplier", type=float, default=DEFAULT_DEDICATED_REAL_LOSS_MULTIPLIER)
    parser.add_argument("--init-npz", default=None)
    parser.add_argument("--init-periodic-folder", default=None)
    parser.add_argument("--init-nonperiodic-folder", default=None)
    parser.add_argument("--init-fixed-frame", type=int, default=None)
    parser.add_argument("--ae-checkpoint", default=None)
    parser.add_argument("--extra-ae-checkpoint", default=None)
    parser.add_argument("--init-checkpoint", default=None)
    parser.add_argument("--load-optimizer", action="store_true")
    parser.add_argument("--resume-step-from-checkpoint", action="store_true")
    parser.add_argument("--body-mode", default=tl.BODY_MODE_LOWER, choices=tl.BODY_MODE_VALUES)
    parser.add_argument(
        "--ae-foot-location-multiplier",
        type=float,
        default=DEFAULT_AE_FOOT_LOCATION_MULTIPLIER,
    )
    parser.add_argument(
        "--ae-foot-rotation-multiplier",
        type=float,
        default=DEFAULT_AE_FOOT_ROTATION_MULTIPLIER,
    )
    parser.add_argument(
        "--ae-terminal-only",
        dest="ae_terminal_only",
        action="store_true",
        default=DEFAULT_AE_TERMINAL_ONLY,
    )
    parser.add_argument(
        "--ae-all-rollout-steps",
        dest="ae_terminal_only",
        action="store_false",
    )
    parser.add_argument(
        "--foot-roll-height-pin-gate",
        dest="foot_roll_height_pin_gate",
        action="store_true",
        default=DEFAULT_FOOT_ROLL_HEIGHT_PIN_GATE,
    )
    parser.add_argument(
        "--no-foot-roll-height-pin-gate",
        dest="foot_roll_height_pin_gate",
        action="store_false",
    )
    parser.add_argument("--foot-roll-integration-steps", type=int, default=DEFAULT_FOOT_ROLL_INTEGRATION_STEPS)
    parser.add_argument(
        "--fake-gravity",
        dest="fake_gravity",
        nargs="?",
        const=1.0,
        type=float,
        default=DEFAULT_FAKE_GRAVITY_ENABLED,
        help="Enable fake gravity with strength in [0, 1]. Default: disabled when omitted (0).",
    )
    parser.add_argument("--no-fake-gravity", dest="fake_gravity", action="store_const", const=0.0)
    parser.add_argument("--fake-gravity-mps2", type=float, default=DEFAULT_FAKE_GRAVITY_MPS2)
    parser.add_argument(
        "--fake-gravity-uses-height-gate",
        dest="fake_gravity_uses_height_gate",
        action="store_true",
        default=DEFAULT_FAKE_GRAVITY_USES_HEIGHT_GATE,
    )
    parser.add_argument("--fake-gravity-no-height-gate", dest="fake_gravity_uses_height_gate", action="store_false")
    parser.add_argument("--foot-unpin-penalty-weight", type=float, default=DEFAULT_FOOT_UNPIN_PENALTY_WEIGHT)
    parser.add_argument(
        "--pinned-foot-intent-penalty-weight",
        type=float,
        default=DEFAULT_PINNED_FOOT_INTENT_PENALTY_WEIGHT,
    )
    parser.add_argument("--slide-tentative-loss-weight", type=float, default=DEFAULT_SLIDE_TENTATIVE_LOSS_WEIGHT)
    parser.add_argument("--ae-loss-weight", type=float, default=1.0)
    parser.add_argument(
        "--primary-loss-mode",
        choices=PRIMARY_LOSS_MODE_VALUES,
        default=DEFAULT_PRIMARY_LOSS_MODE,
        help="Primary rollout loss: ae1, gt_mse, or ae1_gt_mse. Weighted terms are logged separately.",
    )
    parser.add_argument(
        "--gt-mse-loss-scale",
        type=float,
        default=DEFAULT_GT_MSE_LOSS_SCALE,
        help="Fixed scale applied before GT MSE is added to the objective and logged as loss/gt_mse_weighted.",
    )
    parser.add_argument(
        "--gt-mse-row-scope",
        choices=GT_MSE_ROW_SCOPE_VALUES,
        default=GT_MSE_ROW_SCOPE_ALL,
        help=(
            "Rows that receive GT-MSE. all preserves legacy behavior; dedicated_periodic limits it to "
            "dedicated real rows followed by periodic/omni reserved rows, regardless of what regular rows sample."
        ),
    )
    parser.add_argument(
        "--ae6-row-scope",
        choices=GT_MSE_ROW_SCOPE_VALUES,
        default=GT_MSE_ROW_SCOPE_ALL,
        help=(
            "Rows that receive AE6 contact loss. all preserves legacy behavior; dedicated_periodic limits it to "
            "dedicated real rows followed by periodic/omni reserved rows, regardless of what regular rows sample."
        ),
    )
    parser.add_argument("--extra-ae-loss-weight", type=float, default=0.0)
    parser.add_argument("--ae2-checkpoint", default=None)
    parser.add_argument("--ae2-loss-weight", type=float, default=None)
    parser.add_argument("--ae3-checkpoint", default=None)
    parser.add_argument("--ae3-loss-weight", type=float, default=None)
    parser.add_argument(
        "--leg-crossing-capsule-loss-weight",
        type=float,
        default=DEFAULT_LEG_CROSSING_CAPSULE_LOSS_WEIGHT,
    )
    parser.add_argument("--pin-logit-gap-loss-weight", type=float, default=DEFAULT_PIN_LOGIT_GAP_LOSS_WEIGHT)
    parser.add_argument(
        "--inertia-acceleration-loss-weight",
        type=float,
        default=DEFAULT_INERTIA_ACCELERATION_LOSS_WEIGHT,
    )
    parser.add_argument("--root-accel-pin-loss-ratio", type=float, default=DEFAULT_ROOT_ACCEL_PIN_LOSS_RATIO)
    parser.add_argument("--ae4-checkpoint", default=None)
    parser.add_argument("--ae4-loss-weight", type=float, default=None)
    parser.add_argument("--ae4-bank-pin-loss-weight", type=float, default=DEFAULT_AE4_BANK_PIN_LOSS_WEIGHT)
    parser.add_argument("--ae5-checkpoint", default=None)
    parser.add_argument("--ae5-loss-weight", type=float, default=0.0)
    parser.add_argument("--ae6-checkpoint", default=None)
    parser.add_argument("--ae6-loss-weight", type=float, default=0.0)
    parser.add_argument(
        "--ae5-calibrate-to-ae1-omni",
        dest="ae5_calibrate_to_ae1_omni",
        action="store_true",
        default=True,
    )
    parser.add_argument("--ae5-no-calibrate-to-ae1-omni", dest="ae5_calibrate_to_ae1_omni", action="store_false")
    parser.add_argument("--ae5-calibration-rows", type=int, default=4096)
    parser.add_argument("--forced-idle-batch-fraction", type=float, default=DEFAULT_FORCED_IDLE_BATCH_FRACTION)
    parser.add_argument("--forced-idle-clip-stem", default=FORCED_IDLE_CLIP_STEM)
    parser.add_argument("--forced-turn45-batch-fraction", type=float, default=DEFAULT_FORCED_TURN45_BATCH_FRACTION)
    parser.add_argument("--forced-turn45-clip-stems", nargs="+", default=list(FORCED_TURN45_CLIP_STEMS))
    parser.add_argument("--init-noise-amount", type=float, default=DEFAULT_INIT_NOISE_AMOUNT, help=argparse.SUPPRESS)
    parser.add_argument("--init-noise-clean-fraction", type=float, default=DEFAULT_INIT_NOISE_CLEAN_FRACTION)
    parser.add_argument(
        "--init-noise-regular-row-fraction",
        type=float,
        default=0.0,
        help="Fraction of non-dedicated/non-periodic real rows that receive the fixed init-noise recipe.",
    )
    parser.add_argument("--init-noise-fixed-strength-scale", type=float, default=1.0)
    parser.add_argument(
        "--random-init-noise-rows",
        action="store_true",
        help="Initialize and reset the regular rows selected by --init-noise-regular-row-fraction from random adjacent dataset frames; does not add vector noise or change loss masks.",
    )
    parser.add_argument(
        "--adaptive-sampler-fraction",
        type=float,
        default=0.0,
        help="Fraction of eligible non-reserved real rows sampled by per-animation loss EMA. Default: 0, disabled.",
    )
    parser.add_argument("--rollout-schedule", type=int, nargs="+", default=None)
    parser.add_argument("--rollout-stage-steps", type=int, nargs="+", default=None)
    parser.add_argument("--rollout-k", type=int, default=None)
    parser.add_argument("--mixed-rollout-at-max", dest="mixed_rollout_at_max", action="store_true", default=None)
    parser.add_argument("--no-mixed-rollout-at-max", dest="mixed_rollout_at_max", action="store_false")
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--hidden-dim", type=int, default=None)
    parser.add_argument("--num-hidden-layers", type=int, default=None)
    parser.add_argument("--timed-checkpoint-interval-minutes", type=float, default=None)
    parser.add_argument("--max-train-seconds", type=float, default=None)
    parser.add_argument("--max-train-seconds-file", default=None)
    parser.add_argument("--stage-learning-rate", type=float, default=None)
    parser.add_argument("--stage-learning-rate-map", nargs="+", default=None)
    parser.add_argument("--log-every", type=int, default=None)
    parser.add_argument("--loss-refresh-rate", type=int, default=None)
    parser.add_argument("--debug-rollout-auto-export-count", type=int, default=0)
    parser.add_argument("--debug-rollout-auto-export-every", type=int, default=1)
    parser.add_argument("--identity-output-loss-weight", type=float, default=0.0)
    parser.add_argument("--identity-output-maxabs-loss-weight", type=float, default=0.0)
    parser.add_argument("--identity-world-pos-loss-weight", type=float, default=0.0)
    parser.add_argument("--identity-pelvis-pos-loss-weight", type=float, default=0.0)
    parser.add_argument("--linear-slide-loss-weight", type=float, default=0.0)
    parser.add_argument("--angular-slide-loss-weight", type=float, default=0.0)
    parser.add_argument("--foot-height-loss-weight", type=float, default=0.0)
    parser.add_argument("--alternating-feet-loss-weight", type=float, default=0.0)
    parser.add_argument("--foot-lift-slide-loss-weight", type=float, default=0.0)
    parser.add_argument("--pinned-foot-height-loss-weight", type=float, default=DEFAULT_PINNED_FOOT_HEIGHT_LOSS_WEIGHT)
    parser.add_argument("--idle-foot-flatness-loss-weight", type=float, default=DEFAULT_IDLE_FOOT_FLATNESS_LOSS_WEIGHT)
    parser.add_argument("--ik-lower-length-loss-weight", type=float, default=IK_LOWER_LENGTH_LOSS_WEIGHT)
    parser.add_argument("--envelope-margin", type=float, default=env.ExcessEnvelopeConfig().margin)
    parser.add_argument("--envelope-knn", type=int, default=env.ExcessEnvelopeConfig().knn)
    parser.add_argument("--pelvis-root-horizontal-loss-weight", type=float, default=0.0)
    parser.add_argument("--pelvis-root-horizontal-limit-m", type=float, default=RLLossConfig().pelvis_root_horizontal_limit_m)
    parser.add_argument("--pelvis-root-rotation-loss-weight", type=float, default=0.0)
    parser.add_argument("--pelvis-root-rotation-limit-deg", type=float, default=RLLossConfig().pelvis_root_rotation_limit_deg)
    parser.add_argument("--end-effector-location-loss-weight", type=float, default=0.0)
    parser.add_argument("--end-effector-location-limit-m", type=float, nargs=4, default=RLLossConfig().end_effector_location_limit_m)
    parser.add_argument("--end-effector-rotation-loss-weight", type=float, default=0.0)
    parser.add_argument("--end-effector-rotation-limit-deg", type=float, nargs=4, default=RLLossConfig().end_effector_rotation_limit_deg)
    parser.add_argument("--end-effector-velocity-loss-weight", type=float, default=0.0)
    parser.add_argument("--end-effector-velocity-limit-mps", type=float, default=RLLossConfig().end_effector_velocity_limit_mps)
    parser.add_argument("--end-effector-angular-velocity-loss-weight", type=float, default=0.0)
    parser.add_argument(
        "--end-effector-angular-velocity-limit-deg-s",
        type=float,
        default=RLLossConfig().end_effector_angular_velocity_limit_deg_s,
    )
    parser.add_argument("--pelvis-velocity-loss-weight", type=float, default=0.0)
    parser.add_argument("--pelvis-velocity-limit-mps", type=float, default=RLLossConfig().pelvis_velocity_limit_mps)
    parser.add_argument("--pelvis-angular-velocity-loss-weight", type=float, default=0.0)
    parser.add_argument("--pelvis-angular-velocity-limit-deg-s", type=float, default=RLLossConfig().pelvis_angular_velocity_limit_deg_s)
    parser.add_argument("--core-angular-velocity-loss-weight", type=float, default=0.0)
    parser.add_argument("--core-angular-velocity-limit-deg-s", type=float, default=RLLossConfig().core_angular_velocity_limit_deg_s)
    return parser


def warm_training_caches(argv: list[str]) -> dict[str, int | float]:
    started = time.perf_counter()
    args, _unknown = warm_arg_parser().parse_known_args(argv)
    require_slide_tentative_disabled(args)
    apply_training_args(args)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        torch.set_float32_matmul_precision("high")

    ae_loss_weight = float(args.ae_loss_weight)
    ae6_loss_weight = float(getattr(args, "ae6_loss_weight", 0.0))
    root_accel_pin_loss_ratio = float(getattr(args, "root_accel_pin_loss_ratio", DEFAULT_ROOT_ACCEL_PIN_LOSS_RATIO))
    ae_ckpt: dict = {}
    if ae_loss_weight != 0.0:
        ae_path = resolve_path(args.ae_checkpoint) if args.ae_checkpoint else latest_simple_ae_checkpoint()
        ae, mean, std, ae_ckpt = load_simple_ae(ae_path, device, args.body_mode)
    else:
        ae = None
        mean = torch.empty(0, dtype=torch.float32, device=device)
        std = torch.empty(0, dtype=torch.float32, device=device)
    ae5_loss_weight = float(getattr(args, "ae5_loss_weight", 0.0))
    ae5_ckpt: dict = {}
    ae5_mean: torch.Tensor | None = None
    if ae5_loss_weight != 0.0:
        if not getattr(args, "ae5_checkpoint", None):
            raise ValueError("--ae5-loss-weight requires --ae5-checkpoint")
        _ae5, ae5_mean, _ae5_std, ae5_ckpt = load_ae5_checkpoint(resolve_path(args.ae5_checkpoint), device, args.body_mode)
    cfg = make_cfg(device, ae_ckpt, args.body_mode, args.hidden_dim, args.num_hidden_layers)
    cfg.timed_checkpoint_interval_minutes = controller_timed_checkpoint_interval_minutes(args)
    cfg.ae_loss_weight = ae_loss_weight
    rl_cfg = RLLossConfig(
        pelvis_root_horizontal_weight=float(args.pelvis_root_horizontal_loss_weight),
        pelvis_root_horizontal_limit_m=float(args.pelvis_root_horizontal_limit_m),
        pelvis_root_rotation_weight=float(args.pelvis_root_rotation_loss_weight),
        pelvis_root_rotation_limit_deg=float(args.pelvis_root_rotation_limit_deg),
        end_effector_location_weight=float(args.end_effector_location_loss_weight),
        end_effector_location_limit_m=tuple(float(v) for v in args.end_effector_location_limit_m),
        end_effector_rotation_weight=float(args.end_effector_rotation_loss_weight),
        end_effector_rotation_limit_deg=tuple(float(v) for v in args.end_effector_rotation_limit_deg),
        end_effector_velocity_weight=float(args.end_effector_velocity_loss_weight),
        end_effector_velocity_limit_mps=float(args.end_effector_velocity_limit_mps),
        end_effector_angular_velocity_weight=float(args.end_effector_angular_velocity_loss_weight),
        end_effector_angular_velocity_limit_deg_s=float(args.end_effector_angular_velocity_limit_deg_s),
        pelvis_velocity_weight=float(args.pelvis_velocity_loss_weight),
        pelvis_velocity_limit_mps=float(args.pelvis_velocity_limit_mps),
        pelvis_angular_velocity_weight=float(args.pelvis_angular_velocity_loss_weight),
        pelvis_angular_velocity_limit_deg_s=float(args.pelvis_angular_velocity_limit_deg_s),
        core_angular_velocity_weight=float(args.core_angular_velocity_loss_weight),
        core_angular_velocity_limit_deg_s=float(args.core_angular_velocity_limit_deg_s),
        fps=float(cfg.fps),
    )

    base_specs = resolve_clip_specs(args.npz, args.periodic_folder, args.nonperiodic_folder)
    synthetic_specs = resolve_synthetic_clip_specs(args.synthetic_npz, args.synthetic_folder)
    virtual_specs = resolve_synthetic_clip_specs(args.virtual_npz, args.virtual_folder)
    specs = base_specs + synthetic_specs + virtual_specs
    synthetic_reserved_clip_ids = tuple(range(len(base_specs), len(base_specs) + len(synthetic_specs)))
    virtual_reserved_clip_ids = tuple(range(len(base_specs) + len(synthetic_specs), len(specs)))
    synthetic_clip_ids = tuple(sorted(set(synthetic_reserved_clip_ids + virtual_reserved_clip_ids)))
    synthetic_id_set = set(synthetic_clip_ids)
    real_clip_ids = tuple(i for i in range(len(specs)) if i not in synthetic_id_set)
    periodic_real_clip_ids = tuple(
        i for i, (_path, cyclic) in enumerate(specs) if i in set(real_clip_ids) and bool(cyclic)
    )
    if ae5_loss_weight != 0.0 and not periodic_real_clip_ids:
        raise ValueError("AE5 is scoped to omni/periodic rows, but no periodic real clips are available")
    clips = load_clips(specs, cfg)
    input_dim, output_dim = tl.make_batch_dims(clips[0], cfg)
    controller_feature_dim = int(input_dim) + int(output_dim)
    ae_window_frames = (
        ae_window_frames_for_checkpoint(ae_ckpt, controller_feature_dim)
        if ae_ckpt
        else int(SIMPLE_AE_WINDOW_FRAMES)
    )
    ae5_window_frames = (
        ae5_window_frames_for_checkpoint(ae5_ckpt, controller_feature_dim)
        if ae5_ckpt and ae5_mean is not None
        else 1
    )
    ae_required_window_frames = max(
        int(ae_window_frames),
        int(ae5_window_frames) if ae5_loss_weight != 0.0 else 1,
        int(SIMPLE_AE_WINDOW_FRAMES) if ae6_loss_weight != 0.0 else 1,
    )
    store = cached_simple_clip_store(clips, cfg, device)
    if synthetic_clip_ids:
        store.synthetic[torch.tensor(synthetic_clip_ids, dtype=torch.long, device=device)] = True
    init_store: SimpleClipStore | None = None
    init_start_pool: StartPool | None = None
    if args.init_npz or args.init_periodic_folder or args.init_nonperiodic_folder:
        init_specs = resolve_clip_specs(args.init_npz, args.init_periodic_folder, args.init_nonperiodic_folder)
        init_store = cached_simple_clip_store_from_specs(init_specs, cfg, device)
        if args.init_fixed_frame is not None:
            init_start_pool = cached_fixed_start_pool(init_store, int(args.init_fixed_frame))
        else:
            init_start_pool = cached_training_start_pools(init_store, (1,), ae_required_window_frames)[1]

    linear_slide_weight = float(args.linear_slide_loss_weight)
    angular_slide_weight = float(args.angular_slide_loss_weight)
    foot_height_weight = float(args.foot_height_loss_weight)
    alternating_feet_weight = float(args.alternating_feet_loss_weight)
    foot_lift_slide_weight = float(args.foot_lift_slide_loss_weight)
    pinned_foot_height_weight = float(args.pinned_foot_height_loss_weight)
    idle_foot_flatness_weight = float(args.idle_foot_flatness_loss_weight)
    slide_tentative_loss_weight = 0.0
    forced_idle_batch_fraction = (
        None
        if args.forced_idle_batch_fraction is None
        else max(0.0, min(1.0, float(args.forced_idle_batch_fraction)))
    )
    forced_turn45_batch_fraction = (
        None
        if args.forced_turn45_batch_fraction is None
        else max(0.0, min(1.0, float(args.forced_turn45_batch_fraction)))
    )
    root_gated_loss = (
        alternating_feet_loss_enabled(alternating_feet_weight)
        or foot_lift_slide_loss_enabled(foot_lift_slide_weight)
        or float(args.ae4_bank_pin_loss_weight) != 0.0
    )
    walk_f_root_speed_mps = default_walk_f_root_speed_mps(cfg) if root_gated_loss else 0.0
    alternating_root_cutoff_mps = walk_f_root_speed_mps / 3.0 if walk_f_root_speed_mps > 0.0 else 1.0

    envelope = None
    needs_envelope = envelope_loss_enabled(
        linear_slide_weight,
        angular_slide_weight,
        foot_height_weight,
    ) or foot_lift_slide_loss_enabled(foot_lift_slide_weight)
    if needs_envelope:
        envelope_store = store
        envelope_specs = specs
        ae_envelope_specs = resolve_clip_specs_from_checkpoint_metadata(ae_ckpt) if ae_ckpt else []
        if ae_envelope_specs:
            envelope_specs = ae_envelope_specs
            envelope_paths = [path for path, _cyclic in envelope_specs]
            target_paths = [path.resolve() for path, _cyclic in specs]
            if envelope_paths != target_paths:
                envelope_store = cached_simple_clip_store_from_specs(envelope_specs, cfg, device)
        envelope = env.load_or_build_excess_envelope(
            envelope_store,
            env.ExcessEnvelopeConfig(margin=float(args.envelope_margin), knn=int(args.envelope_knn)),
        )
        env.groundtruth_sanity(envelope_store, envelope)

    init_checkpoint_path = resolve_path(args.init_checkpoint) if args.init_checkpoint else None
    if init_checkpoint_path is not None:
        load_controller_checkpoint(init_checkpoint_path)
    for stage_k in ROLLOUT_SCHEDULE:
        rollout_values = rollout_values_for(stage_k) if mixed_rollout_enabled(stage_k) else (int(stage_k),)
        start_pools = cached_training_start_pools(
            store,
            rollout_values,
            ae_required_window_frames,
            clip_ids=real_clip_ids,
        )
        if synthetic_clip_ids:
            cached_fixed_start_pools(store, rollout_values, SYNTHETIC_ROLLOUT_START_FRAME, synthetic_clip_ids)
        max_pool = start_pools[int(stage_k)]
        batch_size_for_stage(store, int(stage_k), max_pool.row_count)

    return {
        "elapsed_s": time.perf_counter() - started,
        "clip_caches": len(_CLIP_CACHE),
        "store_caches": len(_STORE_CACHE),
        "ae_caches": len(_AE_CACHE) + len(_AE2_CACHE) + len(_AE3_CACHE) + len(_AE4_CACHE) + len(_AE6_CACHE),
        "pool_caches": len(_TRAINING_START_POOLS_CACHE) + len(_FULL_WINDOW_START_POOLS_CACHE) + len(_FIXED_START_POOL_CACHE),
    }


def main(argv: list[str] | None = None) -> None:
    global IK_LOWER_LENGTH_LOSS_WEIGHT, LOG_EVERY, MIXED_ROLLOUT_AT_MAX, PRETRAIN_ARM_STARTED_AT, PRETRAIN_LOSS_PROFILE_EMITTED, ROLLOUT_K, ROLLOUT_SCHEDULE, ROLLOUT_STAGE_STEPS, STAGE_LEARNING_RATES

    arm_phase_started = time.perf_counter()
    TRAIN_STOP_REQUEST_EVENT.clear()
    TRAIN_RESUME_EVENT.clear()
    TRAIN_HOT_STOP_REQUEST_EVENT.clear()
    TRAIN_HOT_STOPPED_EVENT.clear()
    if PRETRAIN_RELEASE_EVENT is not None:
        PRETRAIN_ARM_STARTED_AT = arm_phase_started
        PRETRAIN_LOSS_PROFILE_EMITTED = False
    parser = argparse.ArgumentParser(description="Train IK controller with simple AE and optional separated RL losses.")
    parser.add_argument("--npz", default=None)
    parser.add_argument("--periodic-folder", default=None)
    parser.add_argument("--nonperiodic-folder", default=None)
    parser.add_argument("--synthetic-npz", default=None)
    parser.add_argument("--synthetic-folder", default=None)
    parser.add_argument("--virtual-npz", default=None)
    parser.add_argument("--virtual-folder", default=None)
    parser.add_argument(
        "--virtual-batch-fraction",
        "--synthetic-batch-fraction",
        dest="synthetic_batch_fraction",
        type=float,
        default=DEFAULT_SYNTHETIC_BATCH_FRACTION,
    )
    parser.add_argument("--synthetic-reserved-rows", type=int, default=DEFAULT_SYNTHETIC_RESERVED_ROWS)
    parser.add_argument("--virtual-reserved-rows", type=int, default=DEFAULT_VIRTUAL_RESERVED_ROWS)
    parser.add_argument(
        "--periodic-reserved-batch-fraction",
        "--omni-reserved-batch-fraction",
        dest="periodic_reserved_batch_fraction",
        type=float,
        default=0.0,
        help="Reserve this fraction of real batch rows for cyclic/periodic clips, i.e. the omni folder.",
    )
    parser.add_argument("--dedicated-real-clip-stems", nargs="*", default=[])
    parser.add_argument("--dedicated-real-rows", type=int, default=0)
    parser.add_argument("--dedicated-real-loss-multiplier", type=float, default=DEFAULT_DEDICATED_REAL_LOSS_MULTIPLIER)
    parser.add_argument("--init-npz", default=None)
    parser.add_argument("--init-periodic-folder", default=None)
    parser.add_argument("--init-nonperiodic-folder", default=None)
    parser.add_argument("--init-fixed-frame", type=int, default=None)
    parser.add_argument("--ae-checkpoint", default=None)
    parser.add_argument("--extra-ae-checkpoint", default=None)
    parser.add_argument("--init-checkpoint", default=None)
    parser.add_argument("--load-optimizer", action="store_true")
    parser.add_argument("--resume-step-from-checkpoint", action="store_true")
    parser.add_argument("--body-mode", default=tl.BODY_MODE_LOWER, choices=tl.BODY_MODE_VALUES)
    parser.add_argument("--run-label", default="walkF_simple_ae_controller")
    parser.add_argument("--foot-roll-integration-steps", type=int, default=DEFAULT_FOOT_ROLL_INTEGRATION_STEPS)
    parser.add_argument("--ae6-checkpoint", default=None)
    parser.add_argument("--ae6-loss-weight", type=float, default=0.0)
    parser.add_argument(
        "--ae-foot-location-multiplier",
        type=float,
        default=DEFAULT_AE_FOOT_LOCATION_MULTIPLIER,
    )
    parser.add_argument(
        "--ae-foot-rotation-multiplier",
        type=float,
        default=DEFAULT_AE_FOOT_ROTATION_MULTIPLIER,
    )
    parser.add_argument(
        "--ae-terminal-only",
        dest="ae_terminal_only",
        action="store_true",
        default=DEFAULT_AE_TERMINAL_ONLY,
    )
    parser.add_argument(
        "--ae-all-rollout-steps",
        dest="ae_terminal_only",
        action="store_false",
    )
    parser.add_argument(
        "--foot-roll-height-pin-gate",
        dest="foot_roll_height_pin_gate",
        action="store_true",
        default=DEFAULT_FOOT_ROLL_HEIGHT_PIN_GATE,
    )
    parser.add_argument(
        "--no-foot-roll-height-pin-gate",
        dest="foot_roll_height_pin_gate",
        action="store_false",
    )
    parser.add_argument(
        "--fake-gravity",
        dest="fake_gravity",
        nargs="?",
        const=1.0,
        type=float,
        default=DEFAULT_FAKE_GRAVITY_ENABLED,
        help="Enable fake gravity with strength in [0, 1]. Default: disabled when omitted (0).",
    )
    parser.add_argument("--no-fake-gravity", dest="fake_gravity", action="store_const", const=0.0)
    parser.add_argument("--fake-gravity-mps2", type=float, default=DEFAULT_FAKE_GRAVITY_MPS2)
    parser.add_argument(
        "--fake-gravity-uses-height-gate",
        dest="fake_gravity_uses_height_gate",
        action="store_true",
        default=DEFAULT_FAKE_GRAVITY_USES_HEIGHT_GATE,
    )
    parser.add_argument("--fake-gravity-no-height-gate", dest="fake_gravity_uses_height_gate", action="store_false")
    parser.add_argument("--foot-unpin-penalty-weight", type=float, default=DEFAULT_FOOT_UNPIN_PENALTY_WEIGHT)
    parser.add_argument(
        "--pinned-foot-intent-penalty-weight",
        type=float,
        default=DEFAULT_PINNED_FOOT_INTENT_PENALTY_WEIGHT,
    )
    parser.add_argument("--slide-tentative-loss-weight", type=float, default=DEFAULT_SLIDE_TENTATIVE_LOSS_WEIGHT)
    parser.add_argument("--ae-loss-weight", type=float, default=1.0)
    parser.add_argument(
        "--primary-loss-mode",
        choices=PRIMARY_LOSS_MODE_VALUES,
        default=DEFAULT_PRIMARY_LOSS_MODE,
        help="Primary rollout loss logged in the AE1 slots: ae1 or gt_mse.",
    )
    parser.add_argument(
        "--gt-mse-loss-scale",
        type=float,
        default=DEFAULT_GT_MSE_LOSS_SCALE,
        help="Fixed scale applied before GT MSE is logged/trained through the AE1 loss slot.",
    )
    parser.add_argument(
        "--gt-mse-row-scope",
        choices=GT_MSE_ROW_SCOPE_VALUES,
        default=GT_MSE_ROW_SCOPE_ALL,
        help=(
            "Rows that receive GT-MSE. all preserves legacy behavior; dedicated_periodic limits it to "
            "dedicated real rows followed by periodic/omni reserved rows, regardless of what regular rows sample."
        ),
    )
    parser.add_argument(
        "--ae6-row-scope",
        choices=GT_MSE_ROW_SCOPE_VALUES,
        default=GT_MSE_ROW_SCOPE_ALL,
        help=(
            "Rows that receive AE6 contact loss. all preserves legacy behavior; dedicated_periodic limits it to "
            "dedicated real rows followed by periodic/omni reserved rows, regardless of what regular rows sample."
        ),
    )
    parser.add_argument("--extra-ae-loss-weight", type=float, default=0.0)
    parser.add_argument("--ae2-checkpoint", default=None)
    parser.add_argument("--ae2-loss-weight", type=float, default=None)
    parser.add_argument("--ae3-checkpoint", default=None)
    parser.add_argument("--ae3-loss-weight", type=float, default=None)
    parser.add_argument(
        "--leg-crossing-capsule-loss-weight",
        type=float,
        default=DEFAULT_LEG_CROSSING_CAPSULE_LOSS_WEIGHT,
    )
    parser.add_argument("--pin-logit-gap-loss-weight", type=float, default=DEFAULT_PIN_LOGIT_GAP_LOSS_WEIGHT)
    parser.add_argument(
        "--inertia-acceleration-loss-weight",
        type=float,
        default=DEFAULT_INERTIA_ACCELERATION_LOSS_WEIGHT,
    )
    parser.add_argument("--root-accel-pin-loss-ratio", type=float, default=DEFAULT_ROOT_ACCEL_PIN_LOSS_RATIO)
    parser.add_argument("--ae4-checkpoint", default=None)
    parser.add_argument("--ae4-loss-weight", type=float, default=None)
    parser.add_argument("--ae4-bank-pin-loss-weight", type=float, default=DEFAULT_AE4_BANK_PIN_LOSS_WEIGHT)
    parser.add_argument("--ae5-checkpoint", default=None)
    parser.add_argument("--ae5-loss-weight", type=float, default=0.0)
    parser.add_argument(
        "--ae5-calibrate-to-ae1-omni",
        dest="ae5_calibrate_to_ae1_omni",
        action="store_true",
        default=True,
    )
    parser.add_argument("--ae5-no-calibrate-to-ae1-omni", dest="ae5_calibrate_to_ae1_omni", action="store_false")
    parser.add_argument("--ae5-calibration-rows", type=int, default=4096)
    parser.add_argument("--forced-idle-batch-fraction", type=float, default=DEFAULT_FORCED_IDLE_BATCH_FRACTION)
    parser.add_argument("--forced-idle-clip-stem", default=FORCED_IDLE_CLIP_STEM)
    parser.add_argument("--forced-turn45-batch-fraction", type=float, default=DEFAULT_FORCED_TURN45_BATCH_FRACTION)
    parser.add_argument("--forced-turn45-clip-stems", nargs="+", default=list(FORCED_TURN45_CLIP_STEMS))
    parser.add_argument("--init-noise-amount", type=float, default=DEFAULT_INIT_NOISE_AMOUNT, help=argparse.SUPPRESS)
    parser.add_argument("--init-noise-clean-fraction", type=float, default=DEFAULT_INIT_NOISE_CLEAN_FRACTION)
    parser.add_argument(
        "--init-noise-regular-row-fraction",
        type=float,
        default=0.0,
        help="Fraction of non-dedicated/non-periodic real rows that receive the fixed init-noise recipe.",
    )
    parser.add_argument("--init-noise-fixed-strength-scale", type=float, default=1.0)
    parser.add_argument(
        "--random-init-noise-rows",
        action="store_true",
        help="Initialize and reset the regular rows selected by --init-noise-regular-row-fraction from random adjacent dataset frames; does not add vector noise or change loss masks.",
    )
    parser.add_argument(
        "--adaptive-sampler-fraction",
        type=float,
        default=0.0,
        help="Fraction of eligible non-reserved real rows sampled by per-animation loss EMA. Default: 0, disabled.",
    )
    parser.add_argument("--rollout-schedule", type=int, nargs="+", default=None)
    parser.add_argument("--rollout-stage-steps", type=int, nargs="+", default=None)
    parser.add_argument("--rollout-k", type=int, default=None)
    parser.add_argument("--mixed-rollout-at-max", dest="mixed_rollout_at_max", action="store_true", default=None)
    parser.add_argument("--no-mixed-rollout-at-max", dest="mixed_rollout_at_max", action="store_false")
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--hidden-dim", type=int, default=None)
    parser.add_argument("--num-hidden-layers", type=int, default=None)
    parser.add_argument("--timed-checkpoint-interval-minutes", type=float, default=None)
    parser.add_argument("--max-train-seconds", type=float, default=None)
    parser.add_argument("--max-train-seconds-file", default=None)
    parser.add_argument("--stage-learning-rate", type=float, default=None)
    parser.add_argument("--stage-learning-rate-map", nargs="+", default=None)
    parser.add_argument("--log-every", type=int, default=None)
    parser.add_argument("--loss-refresh-rate", type=int, default=None)
    parser.add_argument("--debug-rollout-auto-export-count", type=int, default=0)
    parser.add_argument("--debug-rollout-auto-export-every", type=int, default=1)
    parser.add_argument("--identity-output-loss-weight", type=float, default=0.0)
    parser.add_argument("--identity-output-maxabs-loss-weight", type=float, default=0.0)
    parser.add_argument("--identity-world-pos-loss-weight", type=float, default=0.0)
    parser.add_argument("--identity-pelvis-pos-loss-weight", type=float, default=0.0)
    parser.add_argument("--linear-slide-loss-weight", type=float, default=0.0)
    parser.add_argument("--angular-slide-loss-weight", type=float, default=0.0)
    parser.add_argument("--foot-height-loss-weight", type=float, default=0.0)
    parser.add_argument("--alternating-feet-loss-weight", type=float, default=0.0)
    parser.add_argument("--foot-lift-slide-loss-weight", type=float, default=0.0)
    parser.add_argument("--pinned-foot-height-loss-weight", type=float, default=DEFAULT_PINNED_FOOT_HEIGHT_LOSS_WEIGHT)
    parser.add_argument("--idle-foot-flatness-loss-weight", type=float, default=DEFAULT_IDLE_FOOT_FLATNESS_LOSS_WEIGHT)
    parser.add_argument("--ik-lower-length-loss-weight", type=float, default=IK_LOWER_LENGTH_LOSS_WEIGHT)
    parser.add_argument("--envelope-margin", type=float, default=env.ExcessEnvelopeConfig().margin)
    parser.add_argument("--envelope-knn", type=int, default=env.ExcessEnvelopeConfig().knn)
    parser.add_argument("--pelvis-root-horizontal-loss-weight", type=float, default=0.0)
    parser.add_argument("--pelvis-root-horizontal-limit-m", type=float, default=RLLossConfig().pelvis_root_horizontal_limit_m)
    parser.add_argument("--pelvis-root-rotation-loss-weight", type=float, default=0.0)
    parser.add_argument("--pelvis-root-rotation-limit-deg", type=float, default=RLLossConfig().pelvis_root_rotation_limit_deg)
    parser.add_argument("--end-effector-location-loss-weight", type=float, default=0.0)
    parser.add_argument(
        "--end-effector-location-limit-m",
        type=float,
        nargs=4,
        default=RLLossConfig().end_effector_location_limit_m,
        metavar=("HAND_L", "HAND_R", "FOOT_L", "FOOT_R"),
    )
    parser.add_argument("--end-effector-rotation-loss-weight", type=float, default=0.0)
    parser.add_argument(
        "--end-effector-rotation-limit-deg",
        type=float,
        nargs=4,
        default=RLLossConfig().end_effector_rotation_limit_deg,
        metavar=("HAND_L", "HAND_R", "FOOT_L", "FOOT_R"),
    )
    parser.add_argument("--end-effector-velocity-loss-weight", type=float, default=0.0)
    parser.add_argument("--end-effector-velocity-limit-mps", type=float, default=RLLossConfig().end_effector_velocity_limit_mps)
    parser.add_argument("--end-effector-angular-velocity-loss-weight", type=float, default=0.0)
    parser.add_argument(
        "--end-effector-angular-velocity-limit-deg-s",
        type=float,
        default=RLLossConfig().end_effector_angular_velocity_limit_deg_s,
    )
    parser.add_argument("--pelvis-velocity-loss-weight", type=float, default=0.0)
    parser.add_argument("--pelvis-velocity-limit-mps", type=float, default=RLLossConfig().pelvis_velocity_limit_mps)
    parser.add_argument("--pelvis-angular-velocity-loss-weight", type=float, default=0.0)
    parser.add_argument("--pelvis-angular-velocity-limit-deg-s", type=float, default=RLLossConfig().pelvis_angular_velocity_limit_deg_s)
    parser.add_argument("--core-angular-velocity-loss-weight", type=float, default=0.0)
    parser.add_argument("--core-angular-velocity-limit-deg-s", type=float, default=RLLossConfig().core_angular_velocity_limit_deg_s)
    args = parser.parse_args(argv)
    require_slide_tentative_disabled(args)
    apply_training_args(args)
    arm_phase_started = emit_pretrain_arm_timing("parse_args", arm_phase_started)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        torch.set_float32_matmul_precision("high")
    arm_phase_started = emit_pretrain_arm_timing("device_setup", arm_phase_started, device=device)

    ae_loss_weight = float(args.ae_loss_weight)
    extra_ae_loss_weight = float(args.extra_ae_loss_weight)
    identity_loss_weight = float(args.identity_output_loss_weight)
    identity_maxabs_weight = float(args.identity_output_maxabs_loss_weight)
    identity_world_pos_weight = float(args.identity_world_pos_loss_weight)
    identity_pelvis_pos_weight = float(args.identity_pelvis_pos_loss_weight)
    init_noise_clean_fraction = max(0.0, min(1.0, float(args.init_noise_clean_fraction)))
    init_noise_amount = 0.0
    init_noise_regular_row_fraction = max(0.0, min(1.0, float(args.init_noise_regular_row_fraction)))
    init_noise_fixed_strength_scale = max(0.0, float(args.init_noise_fixed_strength_scale))
    random_init_noise_rows = bool(getattr(args, "random_init_noise_rows", False))
    ae_path: Path | None = None
    ae_ckpt: dict = {}
    if ae_loss_weight != 0.0 or extra_ae_loss_weight != 0.0:
        ae_path = resolve_path(args.ae_checkpoint) if args.ae_checkpoint else latest_simple_ae_checkpoint()
        ae, mean, std, ae_ckpt = load_simple_ae(ae_path, device, args.body_mode)
    else:
        ae = None
        mean = torch.empty(0, dtype=torch.float32, device=device)
        std = torch.empty(0, dtype=torch.float32, device=device)
        if args.ae_checkpoint:
            ae_path = resolve_path(args.ae_checkpoint)
            ae_ckpt = torch.load(ae_path, map_location="cpu", weights_only=False)
    extra_ae_path: Path | None = None
    extra_ae = None
    extra_mean: torch.Tensor | None = None
    extra_std: torch.Tensor | None = None
    extra_ae_ckpt: dict = {}
    if extra_ae_loss_weight != 0.0:
        if not args.extra_ae_checkpoint:
            raise ValueError("--extra-ae-loss-weight requires --extra-ae-checkpoint")
        extra_ae_path = resolve_path(args.extra_ae_checkpoint)
        extra_ae, extra_mean, extra_std, extra_ae_ckpt = load_simple_ae(extra_ae_path, device, args.body_mode)
    arm_phase_started = emit_pretrain_arm_timing(
        "load_ae_checkpoint",
        arm_phase_started,
        enabled=bool(ae_loss_weight != 0.0 or extra_ae_loss_weight != 0.0),
    )
    ae2_loss_weight = (
        float(args.ae2_loss_weight)
        if args.ae2_loss_weight is not None
        else (DEFAULT_AE2_LOSS_WEIGHT if args.ae2_checkpoint else 0.0)
    )
    ae2_path: Path | None = None
    ae2 = None
    ae2_mean: torch.Tensor | None = None
    ae2_std: torch.Tensor | None = None
    ae2_ckpt: dict = {}
    if args.ae2_checkpoint:
        ae2_path = resolve_path(args.ae2_checkpoint)
    if ae2_loss_weight != 0.0:
        if not args.ae2_checkpoint:
            raise ValueError("--ae2-loss-weight requires --ae2-checkpoint")
        assert ae2_path is not None
        ae2, ae2_mean, ae2_std, ae2_ckpt = load_ik_motion_ae2(ae2_path, device, args.body_mode)
    elif ae2_path is not None:
        ae2_ckpt = torch.load(ae2_path, map_location="cpu", weights_only=False)
    arm_phase_started = emit_pretrain_arm_timing(
        "load_ae2_checkpoint",
        arm_phase_started,
        enabled=bool(ae2_loss_weight != 0.0),
    )
    ae3_loss_weight = (
        float(args.ae3_loss_weight)
        if args.ae3_loss_weight is not None
        else (DEFAULT_AE3_LOSS_WEIGHT if args.ae3_checkpoint else 0.0)
    )
    ae3_path: Path | None = None
    ae3 = None
    ae3_mean: torch.Tensor | None = None
    ae3_std: torch.Tensor | None = None
    ae3_pos_weight: torch.Tensor | None = None
    ae3_ckpt: dict = {}
    if args.ae3_checkpoint:
        ae3_path = resolve_path(args.ae3_checkpoint)
    if ae3_loss_weight != 0.0:
        if not args.ae3_checkpoint:
            raise ValueError("--ae3-loss-weight requires --ae3-checkpoint")
        assert ae3_path is not None
        ae3, ae3_mean, ae3_std, ae3_pos_weight, ae3_ckpt = load_pin_aware_ae3(
            ae3_path,
            device,
            args.body_mode,
        )
    elif ae3_path is not None:
        ae3_ckpt = torch.load(ae3_path, map_location="cpu", weights_only=False)
    arm_phase_started = emit_pretrain_arm_timing(
        "load_ae3_checkpoint",
        arm_phase_started,
        enabled=bool(ae3_loss_weight != 0.0),
    )
    pin_logit_gap_loss_weight = float(args.pin_logit_gap_loss_weight)
    inertia_acceleration_loss_weight = float(args.inertia_acceleration_loss_weight)
    root_accel_pin_loss_ratio = float(args.root_accel_pin_loss_ratio)
    leg_crossing_capsule_loss_weight = float(args.leg_crossing_capsule_loss_weight)
    ae4_loss_weight = (
        float(args.ae4_loss_weight)
        if args.ae4_loss_weight is not None
        else (DEFAULT_AE4_LOSS_WEIGHT if resolve_ae4_checkpoint_arg(args) is not None else 0.0)
    )
    ae4_bank_pin_loss_weight = float(args.ae4_bank_pin_loss_weight)
    ae4_path: Path | None = None
    ae4 = None
    ae4_input_mean: torch.Tensor | None = None
    ae4_input_std: torch.Tensor | None = None
    ae4_target_mean: torch.Tensor | None = None
    ae4_target_std: torch.Tensor | None = None
    ae4_ckpt: dict = {}
    if ae4_loss_weight != 0.0 or ae4_bank_pin_loss_weight != 0.0:
        ae4_path = resolve_ae4_checkpoint_arg(args)
        if ae4_path is None:
            raise ValueError(
                "--ae4-loss-weight/--ae4-bank-pin-loss-weight requires --ae4-checkpoint or a valid canonical AE4 projector at "
                f"{DEFAULT_AE4_PROJECTOR_DIR}"
            )
        ae4, ae4_input_mean, ae4_input_std, ae4_target_mean, ae4_target_std, ae4_ckpt = load_ik_pose_ae4(
            ae4_path,
            device,
            args.body_mode,
        )
        if ae4_bank_pin_loss_weight != 0.0 and not ae4_uses_pose_bank_projector(ae4):
            raise ValueError("--ae4-bank-pin-loss-weight requires the AE4 pose-bank projector.")
    arm_phase_started = emit_pretrain_arm_timing(
        "load_ae4_checkpoint",
        arm_phase_started,
        enabled=bool(ae4_loss_weight != 0.0 or ae4_bank_pin_loss_weight != 0.0),
    )
    ae5_loss_weight = float(args.ae5_loss_weight)
    ae5_path: Path | None = None
    ae5 = None
    ae5_mean: torch.Tensor | None = None
    ae5_std: torch.Tensor | None = None
    ae5_ckpt: dict = {}
    if args.ae5_checkpoint:
        ae5_path = resolve_path(args.ae5_checkpoint)
    if ae5_loss_weight != 0.0:
        if ae5_path is None:
            raise ValueError("--ae5-loss-weight requires --ae5-checkpoint")
        ae5, ae5_mean, ae5_std, ae5_ckpt = load_ae5_checkpoint(ae5_path, device, args.body_mode)
    elif ae5_path is not None:
        ae5_ckpt = torch.load(ae5_path, map_location="cpu", weights_only=False)
    arm_phase_started = emit_pretrain_arm_timing(
        "load_ae5_checkpoint",
        arm_phase_started,
        enabled=bool(ae5_loss_weight != 0.0),
    )
    ae6_loss_weight = float(args.ae6_loss_weight)
    ae6_path: Path | None = None
    ae6 = None
    ae6_mean: torch.Tensor | None = None
    ae6_std: torch.Tensor | None = None
    ae6_ckpt: dict = {}
    if args.ae6_checkpoint:
        ae6_path = resolve_path(args.ae6_checkpoint)
    if ae6_loss_weight != 0.0:
        if ae6_path is None:
            raise ValueError("--ae6-loss-weight requires --ae6-checkpoint")
        ae6, ae6_mean, ae6_std, ae6_ckpt = load_contact_ae6(ae6_path, device, args.body_mode)
    elif ae6_path is not None:
        ae6_ckpt = torch.load(ae6_path, map_location="cpu", weights_only=False)
    arm_phase_started = emit_pretrain_arm_timing(
        "load_ae6_checkpoint",
        arm_phase_started,
        enabled=bool(ae6_loss_weight != 0.0),
    )
    cfg = make_cfg(device, ae_ckpt, args.body_mode, args.hidden_dim, args.num_hidden_layers)
    cfg.timed_checkpoint_interval_minutes = controller_timed_checkpoint_interval_minutes(args)
    cfg.ae_loss_weight = ae_loss_weight
    tl.set_seed(int(cfg.seed))
    rl_cfg = RLLossConfig(
        pelvis_root_horizontal_weight=float(args.pelvis_root_horizontal_loss_weight),
        pelvis_root_horizontal_limit_m=float(args.pelvis_root_horizontal_limit_m),
        pelvis_root_rotation_weight=float(args.pelvis_root_rotation_loss_weight),
        pelvis_root_rotation_limit_deg=float(args.pelvis_root_rotation_limit_deg),
        end_effector_location_weight=float(args.end_effector_location_loss_weight),
        end_effector_location_limit_m=tuple(float(v) for v in args.end_effector_location_limit_m),
        end_effector_rotation_weight=float(args.end_effector_rotation_loss_weight),
        end_effector_rotation_limit_deg=tuple(float(v) for v in args.end_effector_rotation_limit_deg),
        end_effector_velocity_weight=float(args.end_effector_velocity_loss_weight),
        end_effector_velocity_limit_mps=float(args.end_effector_velocity_limit_mps),
        end_effector_angular_velocity_weight=float(args.end_effector_angular_velocity_loss_weight),
        end_effector_angular_velocity_limit_deg_s=float(args.end_effector_angular_velocity_limit_deg_s),
        pelvis_velocity_weight=float(args.pelvis_velocity_loss_weight),
        pelvis_velocity_limit_mps=float(args.pelvis_velocity_limit_mps),
        pelvis_angular_velocity_weight=float(args.pelvis_angular_velocity_loss_weight),
        pelvis_angular_velocity_limit_deg_s=float(args.pelvis_angular_velocity_limit_deg_s),
        core_angular_velocity_weight=float(args.core_angular_velocity_loss_weight),
        core_angular_velocity_limit_deg_s=float(args.core_angular_velocity_limit_deg_s),
        fps=float(cfg.fps),
    )
    arm_phase_started = emit_pretrain_arm_timing("build_config_and_loss_flags", arm_phase_started)
    identity_enabled = (
        identity_loss_weight != 0.0
        or identity_maxabs_weight != 0.0
        or identity_world_pos_weight != 0.0
        or identity_pelvis_pos_weight != 0.0
    )
    base_specs = resolve_clip_specs(args.npz, args.periodic_folder, args.nonperiodic_folder)
    synthetic_specs = resolve_synthetic_clip_specs(args.synthetic_npz, args.synthetic_folder)
    virtual_specs = resolve_synthetic_clip_specs(args.virtual_npz, args.virtual_folder)
    specs = base_specs + synthetic_specs + virtual_specs
    synthetic_reserved_clip_ids = tuple(range(len(base_specs), len(base_specs) + len(synthetic_specs)))
    virtual_reserved_clip_ids = tuple(range(len(base_specs) + len(synthetic_specs), len(specs)))
    synthetic_clip_ids = tuple(sorted(set(synthetic_reserved_clip_ids + virtual_reserved_clip_ids)))
    synthetic_id_set = set(synthetic_clip_ids)
    real_clip_ids = tuple(i for i in range(len(specs)) if i not in synthetic_id_set)
    periodic_real_clip_ids = tuple(
        i for i, (_path, cyclic) in enumerate(specs) if i in set(real_clip_ids) and bool(cyclic)
    )
    dedicated_real_clip_stems = tuple(
        str(stem).lower().strip()
        for stem in (args.dedicated_real_clip_stems or [])
        if str(stem).strip()
    )
    dedicated_real_rows = max(0, int(args.dedicated_real_rows))
    dedicated_real_loss_multiplier = max(0.0, float(args.dedicated_real_loss_multiplier))
    dedicated_real_clip_ids = clip_ids_matching_path_stems(specs, dedicated_real_clip_stems, real_clip_ids)
    synthetic_reserved_rows = max(0, int(args.synthetic_reserved_rows))
    virtual_reserved_rows = max(0, int(args.virtual_reserved_rows))
    periodic_reserved_batch_fraction = max(0.0, min(1.0, float(args.periodic_reserved_batch_fraction)))
    synthetic_batch_fraction = (
        max(0.0, min(1.0, float(args.synthetic_batch_fraction)))
        if synthetic_clip_ids
        else 0.0
    )
    if synthetic_reserved_rows > 0 and not synthetic_reserved_clip_ids:
        raise ValueError("--synthetic-reserved-rows requires --synthetic-folder or --synthetic-npz")
    if virtual_reserved_rows > 0 and not virtual_reserved_clip_ids:
        raise ValueError("--virtual-reserved-rows requires --virtual-folder or --virtual-npz")
    if periodic_reserved_batch_fraction > 0.0 and not periodic_real_clip_ids:
        raise ValueError("--periodic-reserved-batch-fraction requires at least one cyclic/periodic real clip")
    if dedicated_real_rows > 0 and not dedicated_real_clip_ids:
        raise ValueError(
            "--dedicated-real-rows requires --dedicated-real-clip-stems matching at least one real training clip"
        )
    clips = load_clips(specs, cfg)
    input_dim, output_dim = tl.make_batch_dims(clips[0], cfg)
    if ae3 is not None and ae3_mean is not None and int(ae3_mean.shape[-1]) != int(input_dim):
        raise ValueError(f"AE3 input_dim={int(ae3_mean.shape[-1])} does not match controller input_dim={int(input_dim)}")
    if ae4 is not None and not ae4_uses_pose_bank_projector(ae4):
        ae4_schema = getattr(ae4, "_ik_pose_ae4_schema", {})
        if isinstance(ae4_schema, dict) and int(ae4_schema.get("output_dim", 0)) != int(output_dim):
            raise ValueError(f"AE4 output_dim={int(ae4_schema.get('output_dim', 0))} does not match controller output_dim={int(output_dim)}")
    model_output_dim = tl.controller_output_dim(clips[0], cfg)
    controller_feature_dim = input_dim + output_dim
    ae_window_frames = int(SIMPLE_AE_WINDOW_FRAMES)
    if ae_ckpt:
        expected_dim = int(ae_ckpt["schema"]["total_dim"])
        checkpoint_ae_window_frames = ae_window_frames_for_checkpoint(ae_ckpt, controller_feature_dim)
        if int(checkpoint_ae_window_frames) != int(SIMPLE_AE_WINDOW_FRAMES):
            raise ValueError(
                f"Simple AE checkpoint window_frames={checkpoint_ae_window_frames} does not match the hardcoded "
                f"controller AE window={SIMPLE_AE_WINDOW_FRAMES}"
            )
        if controller_feature_dim * ae_window_frames != expected_dim:
            raise ValueError(
                f"AE dim {expected_dim} does not match controller feature dim {controller_feature_dim} "
                f"and hardcoded window_frames={ae_window_frames}"
            )
    if extra_ae is not None:
        extra_expected_dim = int(extra_ae_ckpt["schema"]["total_dim"])
        extra_ae_window_frames = ae_window_frames_for_checkpoint(extra_ae_ckpt, controller_feature_dim)
        if int(extra_ae_window_frames) != int(SIMPLE_AE_WINDOW_FRAMES):
            raise ValueError(
                f"Extra AE checkpoint window_frames={extra_ae_window_frames} does not match the hardcoded "
                f"controller AE window={SIMPLE_AE_WINDOW_FRAMES}"
            )
        if controller_feature_dim * ae_window_frames != extra_expected_dim:
            raise ValueError(
                f"Extra AE dim {extra_expected_dim} does not match controller feature dim {controller_feature_dim} "
                f"and hardcoded window_frames={ae_window_frames}"
            )
    if ae6 is not None and ae6_mean is not None:
        ae6_expected_dim = int(ae6_mean.numel())
        ae6_window_frames = ae_window_frames_for_checkpoint(ae6_ckpt, controller_feature_dim)
        if int(ae6_window_frames) != int(SIMPLE_AE_WINDOW_FRAMES):
            raise ValueError(
                f"AE6 checkpoint window_frames={ae6_window_frames} does not match the hardcoded "
                f"controller AE window={SIMPLE_AE_WINDOW_FRAMES}"
            )
        if controller_feature_dim * ae_window_frames != ae6_expected_dim:
            raise ValueError(
                f"AE6 dim {ae6_expected_dim} does not match controller feature dim {controller_feature_dim} "
                f"and hardcoded window_frames={ae_window_frames}"
            )
    ae5_window_frames = 1
    if ae5_ckpt:
        ae5_schema = ae5_ckpt.get("schema", {})
        ae5_expected_dim = int(ae5_schema["total_dim"])
        ae5_window_frames = ae5_window_frames_for_checkpoint(ae5_ckpt, controller_feature_dim)
        if not isinstance(ae5_schema, dict):
            raise ValueError("AE5 checkpoint is missing a schema")
        if ae5_schema.get("feature") == IK_MOTION_AE_FEATURE_ROOT_POSE_WINDOW:
            frame_dim = int(ae5_schema["frame_feature_dim"])
            if frame_dim * int(ae5_window_frames) != ae5_expected_dim:
                raise ValueError(
                    f"AE5 root-conditioned pose-window dim {ae5_expected_dim} does not match frame_dim={frame_dim} "
                    f"and window_frames={ae5_window_frames}"
                )
        elif ae5_schema.get("ae_feature_mode") in AE5_SIMPLE_DELTA_FEATURE_MODES:
            if normalized_ae_score_scope(ae5_schema.get("ae_score_scope", AE_SCORE_SCOPE_OUTPUT)) != AE_SCORE_SCOPE_FULL_WINDOW:
                raise ValueError(
                    "AE5 temporal SimpleAE must use ae_score_scope='full_window'; "
                    f"got {ae5_schema.get('ae_score_scope')!r}"
                )
            base_total_dim = int(ae5_schema.get("base_total_dim", controller_feature_dim))
            if int(base_total_dim) != int(controller_feature_dim):
                raise ValueError(
                    f"AE5 SimpleAE base_total_dim={base_total_dim} does not match controller feature dim "
                    f"{controller_feature_dim}"
                )
            if int(ae5_expected_dim) != int(controller_feature_dim) * int(ae5_window_frames):
                raise ValueError(
                    f"AE5 SimpleAE dim {ae5_expected_dim} does not match controller feature dim "
                    f"{controller_feature_dim} and window_frames={ae5_window_frames}"
                )
            if int(ae5_window_frames) <= 1:
                raise ValueError(f"AE5 SimpleAE should be temporal; got window_frames={ae5_window_frames}")
            if ae5_schema.get("output_reference_root") != tl.OUTPUT_REFERENCE_ROOT:
                raise ValueError(
                    f"AE5 SimpleAE output_reference_root={ae5_schema.get('output_reference_root')!r}; "
                    f"expected {tl.OUTPUT_REFERENCE_ROOT!r}"
                )
        else:
            raise ValueError(
                "AE5 checkpoint must use either "
                f"root-conditioned pose-window feature={IK_MOTION_AE_FEATURE_ROOT_POSE_WINDOW!r} or a temporal "
                f"SimpleAE delta feature mode in {sorted(AE5_SIMPLE_DELTA_FEATURE_MODES)!r} "
                "with ae_score_scope='full_window'; "
                f"got feature={ae5_schema.get('feature')!r} mode={ae5_schema.get('ae_feature_mode')!r} "
                f"scope={ae5_schema.get('ae_score_scope')!r}"
            )
    ae_required_window_frames = max(
        int(ae_window_frames),
        int(ae5_window_frames) if ae5_loss_weight != 0.0 else 1,
    )
    arm_phase_started = emit_pretrain_arm_timing("load_target_clips", arm_phase_started, clips=len(clips))

    store = cached_simple_clip_store(clips, cfg, device)
    if synthetic_clip_ids:
        store.synthetic[torch.tensor(synthetic_clip_ids, dtype=torch.long, device=device)] = True
    if isinstance(ae4, IKPoseBankProjectorPrior):
        ae4.prepare_store(store)
    ae5_effective_loss_weight = float(ae5_loss_weight)
    ae5_calibration: dict[str, float] = {}
    if ae5_loss_weight != 0.0:
        if not periodic_real_clip_ids:
            raise ValueError("AE5 is scoped to omni/periodic rows, but no periodic real clips are available")
        if bool(args.ae5_calibrate_to_ae1_omni):
            ae5_effective_loss_weight, ae5_calibration = calibrate_ae5_effective_loss_weight(
                ae,
                mean,
                std,
                ae_loss_weight,
                ae5,
                ae5_mean,
                ae5_std,
                ae5_loss_weight,
                store,
                periodic_real_clip_ids,
                ae_required_window_frames,
                max_rows=max(1, int(args.ae5_calibration_rows)),
            )
        print(
            "AE5_CALIBRATION "
            f"user_weight={ae5_loss_weight:.6g} effective_weight={ae5_effective_loss_weight:.6g} "
            f"window_frames={ae5_window_frames} scope=periodic_real_rows "
            f"ae1_omni_mean={ae5_calibration.get('ae1_omni_gt_mean', float('nan')):.6g} "
            f"ae5_omni_mean={ae5_calibration.get('ae5_omni_gt_mean', float('nan')):.6g}",
            flush=True,
        )
    inertia_limits: dict[str, object] = {}
    if inertia_acceleration_loss_weight != 0.0:
        inertia_phase_started = time.perf_counter()
        inertia_limits = prepare_inertia_acceleration_limits(store, real_clip_ids)
        emit_pretrain_arm_timing(
            "build_inertia_acceleration_limits",
            inertia_phase_started,
            clips=len(real_clip_ids),
            samples=int(inertia_limits.get("sample_count", 0)),
        )
    arm_phase_started = emit_pretrain_arm_timing("build_target_store", arm_phase_started)
    init_specs: list[tuple[Path, bool]] = []
    init_store: SimpleClipStore | None = None
    init_start_pool: StartPool | None = None
    if args.init_npz or args.init_periodic_folder or args.init_nonperiodic_folder:
        init_phase_started = time.perf_counter()
        init_specs = resolve_clip_specs(args.init_npz, args.init_periodic_folder, args.init_nonperiodic_folder)
        init_phase_started = emit_pretrain_arm_timing(
            "resolve_init_specs",
            init_phase_started,
            clips=len(init_specs),
        )
        init_store = cached_simple_clip_store_from_specs(init_specs, cfg, device)
        init_phase_started = emit_pretrain_arm_timing("load_init_store", init_phase_started)
        init_input_dim, init_output_dim = tl.make_batch_dims(init_store.prototype, cfg)
        if init_input_dim != input_dim or init_output_dim != output_dim:
            raise ValueError(
                f"init dataset dims {init_input_dim}->{init_output_dim} do not match target dims {input_dim}->{output_dim}"
            )
        if args.init_fixed_frame is not None:
            init_start_pool = cached_fixed_start_pool(init_store, int(args.init_fixed_frame))
        else:
            init_start_pool = cached_training_start_pools(init_store, (1,), ae_required_window_frames)[1]
        emit_pretrain_arm_timing(
            "build_init_start_pool",
            init_phase_started,
            fixed=bool(args.init_fixed_frame is not None),
        )
    arm_phase_started = emit_pretrain_arm_timing(
        "load_init_clips",
        arm_phase_started,
        enabled=bool(init_store is not None),
        clips=len(init_specs),
    )
    envelope = None
    linear_slide_weight = float(args.linear_slide_loss_weight)
    angular_slide_weight = float(args.angular_slide_loss_weight)
    foot_height_weight = float(args.foot_height_loss_weight)
    alternating_feet_weight = float(args.alternating_feet_loss_weight)
    foot_lift_slide_weight = float(args.foot_lift_slide_loss_weight)
    pinned_foot_height_weight = float(args.pinned_foot_height_loss_weight)
    idle_foot_flatness_weight = float(args.idle_foot_flatness_loss_weight)
    slide_tentative_loss_weight = 0.0
    forced_idle_batch_fraction = (
        None
        if args.forced_idle_batch_fraction is None
        else max(0.0, min(1.0, float(args.forced_idle_batch_fraction)))
    )
    forced_turn45_batch_fraction = (
        None
        if args.forced_turn45_batch_fraction is None
        else max(0.0, min(1.0, float(args.forced_turn45_batch_fraction)))
    )
    forced_idle_clip_stem = str(args.forced_idle_clip_stem or FORCED_IDLE_CLIP_STEM).lower().strip()
    forced_turn45_clip_stems = tuple(
        str(stem).lower().strip()
        for stem in (args.forced_turn45_clip_stems or [])
        if str(stem).strip()
    )
    if not forced_turn45_clip_stems:
        forced_turn45_clip_stems = tuple(FORCED_TURN45_CLIP_STEMS)
    store.forced_idle_clip_stem = forced_idle_clip_stem
    store.forced_turn45_clip_stems = forced_turn45_clip_stems
    root_gated_loss = (
        alternating_feet_loss_enabled(alternating_feet_weight)
        or foot_lift_slide_loss_enabled(foot_lift_slide_weight)
        or ae4_bank_pin_loss_weight != 0.0
    )
    walk_f_root_speed_mps = default_walk_f_root_speed_mps(cfg) if root_gated_loss else 0.0
    alternating_root_cutoff_mps = walk_f_root_speed_mps / 3.0 if walk_f_root_speed_mps > 0.0 else 1.0
    ae4_bank_pin_speed_cutoff_mps = (
        walk_f_root_speed_mps * float(AE4_BANK_PIN_WALKF_SPEED_FRACTION)
        if ae4_bank_pin_loss_weight != 0.0 and walk_f_root_speed_mps > 0.0
        else 1.0
    )
    store.ae4_bank_pin_speed_cutoff_mps = float(ae4_bank_pin_speed_cutoff_mps)
    ae4_bank_pin_turn45l_max_yaw_delta_rad = (
        max_turn45l_root_yaw_delta_rad(store)
        if ae4_bank_pin_loss_weight != 0.0
        else 0.0
    )
    ae4_bank_pin_yaw_cutoff_rad = (
        ae4_bank_pin_turn45l_max_yaw_delta_rad * float(AE4_BANK_PIN_TURN45L_YAW_FRACTION)
        if ae4_bank_pin_loss_weight != 0.0 and ae4_bank_pin_turn45l_max_yaw_delta_rad > 0.0
        else 1.0
    )
    store.ae4_bank_pin_yaw_cutoff_rad = float(ae4_bank_pin_yaw_cutoff_rad)
    envelope_specs: list[tuple[Path, bool]] = []
    envelope_source = "disabled"
    envelope_sanity: dict[str, float] = {}
    needs_envelope = envelope_loss_enabled(
        linear_slide_weight,
        angular_slide_weight,
        foot_height_weight,
    ) or foot_lift_slide_loss_enabled(foot_lift_slide_weight)
    if needs_envelope:
        envelope_phase_started = time.perf_counter()
        envelope_source = "target_dataset"
        envelope_store = store
        envelope_specs = specs
        ae_envelope_specs = resolve_clip_specs_from_checkpoint_metadata(ae_ckpt) if ae_ckpt else []
        envelope_phase_started = emit_pretrain_arm_timing(
            "resolve_envelope_specs",
            envelope_phase_started,
            clips=len(ae_envelope_specs) if ae_envelope_specs else len(envelope_specs),
        )
        if ae_envelope_specs:
            envelope_source = "simple_ae_metadata_dataset"
            envelope_specs = ae_envelope_specs
            envelope_paths = [path for path, _cyclic in envelope_specs]
            target_paths = [path.resolve() for path, _cyclic in specs]
            if envelope_paths == target_paths:
                envelope_store = store
            else:
                envelope_store = cached_simple_clip_store_from_specs(envelope_specs, cfg, device)
        envelope_phase_started = emit_pretrain_arm_timing(
            "load_envelope_store",
            envelope_phase_started,
            source=envelope_source,
        )
        envelope = env.load_or_build_excess_envelope(
            envelope_store,
            env.ExcessEnvelopeConfig(margin=float(args.envelope_margin), knn=int(args.envelope_knn)),
        )
        envelope_phase_started = emit_pretrain_arm_timing("load_or_build_envelope", envelope_phase_started)
        envelope_sanity = env.groundtruth_sanity(envelope_store, envelope)
        emit_pretrain_arm_timing("groundtruth_envelope_sanity", envelope_phase_started)
        if not all(math.isfinite(float(value)) for value in envelope_sanity.values()):
            raise RuntimeError(f"GT foot envelope sanity produced non-finite values: {envelope_sanity}")
    arm_phase_started = emit_pretrain_arm_timing(
        "build_foot_envelope",
        arm_phase_started,
        enabled=bool(envelope is not None),
    )
    init_checkpoint_path = resolve_path(args.init_checkpoint) if args.init_checkpoint else None
    model_phase_started = time.perf_counter()
    model = tl.MLPController(input_dim, model_output_dim, cfg).to(device)
    model_phase_started = emit_pretrain_arm_timing("construct_controller_model", model_phase_started)
    output_initialization = "default"
    init_ckpt: dict | None = None
    init_checkpoint_epoch = 0
    if init_checkpoint_path is not None:
        init_ckpt = load_controller_init_checkpoint(model, init_checkpoint_path, cfg.body_mode)
        init_checkpoint_epoch = int(init_ckpt.get("epoch", 0))
        output_initialization = f"loaded_controller_checkpoint:{init_checkpoint_path}"
        if bool(init_ckpt.get("_output_head_extended_for_foot_roll", False)):
            output_initialization += ":extended_pin_logits"
    elif ae is not None and ae_loss_weight != 0.0 and not tl.output_prediction_uses_residual():
        output_initialization = initialize_controller_output_from_ae_mean(model, mean, input_dim, output_dim)
    elif tl.output_prediction_uses_residual():
        output_initialization = "residual_zero_weight_zero_bias"
        initialize_foot_roll_pin_logits(model)
        output_initialization += "_pin_logits_negative"
    model_phase_started = emit_pretrain_arm_timing(
        "initialize_controller_weights",
        model_phase_started,
        init_checkpoint=bool(init_checkpoint_path is not None),
    )
    optimizer = make_adamw(model.parameters(), LEARNING_RATE, device, capturable=bool(device.type == "cuda"))
    optimizer_state_loaded = False
    if init_ckpt is not None and bool(args.load_optimizer):
        if bool(init_ckpt.get("_output_head_extended_for_foot_roll", False)):
            print(
                "optimizer state skipped: init checkpoint output head was extended for foot-roll pin logits",
                flush=True,
            )
        else:
            load_controller_optimizer_state(optimizer, init_ckpt, init_checkpoint_path, device)
            optimizer_state_loaded = True
    emit_pretrain_arm_timing("construct_optimizer", model_phase_started)
    arm_phase_started = emit_pretrain_arm_timing(
        "build_model_optimizer",
        arm_phase_started,
        init_checkpoint=bool(init_checkpoint_path is not None),
    )

    stage_cache: dict[int, dict[str, object]] = {}
    for stage_k in ROLLOUT_SCHEDULE:
        rollout_values = rollout_values_for(stage_k) if mixed_rollout_enabled(stage_k) else (int(stage_k),)
        start_pools = cached_training_start_pools(store, rollout_values, ae_required_window_frames, real_clip_ids)
        dedicated_real_start_pools = (
            cached_training_start_pools(store, rollout_values, ae_required_window_frames, dedicated_real_clip_ids)
            if dedicated_real_rows > 0
            else None
        )
        periodic_reserved_start_pools = (
            cached_training_start_pools(store, rollout_values, ae_required_window_frames, periodic_real_clip_ids)
            if periodic_reserved_batch_fraction > 0.0
            else None
        )
        synthetic_start_pools = (
            cached_training_start_pools(store, rollout_values, ae_required_window_frames, synthetic_clip_ids)
            if synthetic_clip_ids
            else None
        )
        synthetic_reserved_start_pools = (
            cached_training_start_pools(store, rollout_values, ae_required_window_frames, synthetic_reserved_clip_ids)
            if synthetic_reserved_clip_ids
            else None
        )
        virtual_reserved_start_pools = (
            cached_training_start_pools(store, rollout_values, ae_required_window_frames, virtual_reserved_clip_ids)
            if virtual_reserved_clip_ids
            else None
        )
        max_pool = start_pools[int(stage_k)]
        real_batch_size = batch_size_for_stage(store, int(stage_k), max_pool.row_count)
        batch_size = real_batch_size + synthetic_reserved_rows + virtual_reserved_rows
        dedicated_rows_for_stage = (
            max(0, min(real_batch_size, int(dedicated_real_rows)))
            if dedicated_real_start_pools is not None
            else 0
        )
        periodic_reserved_capacity = max(0, real_batch_size - dedicated_rows_for_stage)
        periodic_reserved_rows = (
            max(
                1,
                min(
                    periodic_reserved_capacity,
                    int(round(real_batch_size * periodic_reserved_batch_fraction)),
                ),
            )
            if (
                periodic_reserved_start_pools is not None
                and periodic_reserved_batch_fraction > 0.0
                and periodic_reserved_capacity > 0
            )
            else 0
        )
        stage_cache[int(stage_k)] = {
            "rollout_values": rollout_values,
            "start_pools": start_pools,
            "full_window_start_pools": None,
            "dedicated_real_start_pools": dedicated_real_start_pools,
            "periodic_reserved_start_pools": periodic_reserved_start_pools,
            "synthetic_start_pools": synthetic_start_pools,
            "synthetic_reserved_start_pools": synthetic_reserved_start_pools,
            "virtual_reserved_start_pools": virtual_reserved_start_pools,
            "max_pool": max_pool,
            "row_count": max_pool.row_count,
            "real_batch_size": real_batch_size,
            "batch_size": batch_size,
            "dedicated_real_rows": dedicated_rows_for_stage,
            "periodic_reserved_rows": periodic_reserved_rows,
            "rollout_stats": rollout_stat_summary(batch_size, int(stage_k)),
            "pool_rows": {str(int(k)): int(pool.row_count) for k, pool in start_pools.items()},
            "dedicated_real_pool_rows": (
                {str(int(k)): int(pool.row_count) for k, pool in dedicated_real_start_pools.items()}
                if dedicated_real_start_pools is not None
                else {}
            ),
            "periodic_reserved_pool_rows": (
                {str(int(k)): int(pool.row_count) for k, pool in periodic_reserved_start_pools.items()}
                if periodic_reserved_start_pools is not None
                else {}
            ),
            "synthetic_pool_rows": (
                {str(int(k)): int(pool.row_count) for k, pool in synthetic_start_pools.items()}
                if synthetic_start_pools is not None
                else {}
            ),
            "synthetic_reserved_pool_rows": (
                {str(int(k)): int(pool.row_count) for k, pool in synthetic_reserved_start_pools.items()}
                if synthetic_reserved_start_pools is not None
                else {}
            ),
            "virtual_reserved_pool_rows": (
                {str(int(k)): int(pool.row_count) for k, pool in virtual_reserved_start_pools.items()}
                if virtual_reserved_start_pools is not None
                else {}
            ),
        }
    arm_phase_started = emit_pretrain_arm_timing(
        "build_stage_start_pools",
        arm_phase_started,
        stages=len(stage_cache),
    )
    adaptive_eligible_clip_mask = ~store.synthetic
    if forced_idle_batch_fraction is not None and float(forced_idle_batch_fraction) >= 1.0:
        adaptive_eligible_clip_mask = torch.zeros_like(adaptive_eligible_clip_mask)
        adaptive_eligible_clip_mask[int(forced_idle_clip_id(store))] = True
    adaptive_sampler_fraction = max(0.0, min(1.0, float(args.adaptive_sampler_fraction)))
    adaptive_sampler = (
        AdaptiveAnimationSampler(
            store,
            adaptive_fraction=adaptive_sampler_fraction,
            update_interval_s=120.0,
            eligible_clip_mask=adaptive_eligible_clip_mask,
        )
        if adaptive_sampler_fraction > 0.0
        else None
    )
    restore_continuation_state = (
        init_ckpt is not None
        and optimizer_state_loaded
        and bool(args.resume_step_from_checkpoint)
    )
    if restore_continuation_state:
        restored_rng = restore_checkpoint_rng_state(init_ckpt.get("rng_state"), device)
        print(
            "checkpoint_rng_state_restored=1" if restored_rng else "checkpoint_rng_state_restored=0 reason=missing_old_checkpoint",
            flush=True,
        )
        if adaptive_sampler is not None:
            restored_sampler = adaptive_sampler.load_checkpoint_state_dict(init_ckpt.get("adaptive_sampler_state"))
            print(
                "adaptive_sampler_state_restored=1"
                if restored_sampler
                else "adaptive_sampler_state_restored=0 reason=missing_or_incompatible",
                flush=True,
            )

    final_cache = stage_cache[int(ROLLOUT_K)]
    metadata = {
        "npz_paths": [str(path) for path, _cyclic in specs],
        "npz_folders": [{"path": str(path.parent), "cyclic": bool(cyclic)} for path, cyclic in specs],
        "real_training_clip_count": int(len(real_clip_ids)),
        "synthetic_npz_paths": [str(path) for path, _cyclic in synthetic_specs],
        "synthetic_npz_folders": [{"path": str(path.parent), "cyclic": False} for path, _cyclic in synthetic_specs],
        "synthetic_clip_count": int(len(synthetic_reserved_clip_ids)),
        "virtual_npz_paths": [str(path) for path, _cyclic in virtual_specs],
        "virtual_npz_folders": [{"path": str(path.parent), "cyclic": False} for path, _cyclic in virtual_specs],
        "virtual_clip_count": int(len(virtual_reserved_clip_ids)),
        "virtual_batch_fraction": float(synthetic_batch_fraction),
        "dedicated_real_clip_stems": list(dedicated_real_clip_stems),
        "dedicated_real_clip_ids": [int(i) for i in dedicated_real_clip_ids],
        "dedicated_real_clip_paths": [str(specs[int(i)][0]) for i in dedicated_real_clip_ids],
        "dedicated_real_rows": int(final_cache["dedicated_real_rows"]),
        "dedicated_real_loss_multiplier": float(dedicated_real_loss_multiplier),
        "periodic_reserved_batch_fraction": float(periodic_reserved_batch_fraction),
        "periodic_reserved_clip_count": int(len(periodic_real_clip_ids)),
        "periodic_reserved_rows": int(final_cache["periodic_reserved_rows"]),
        "synthetic_reserved_rows": int(synthetic_reserved_rows),
        "virtual_reserved_rows": int(virtual_reserved_rows),
        "generated_reserved_rows": int(synthetic_reserved_rows + virtual_reserved_rows),
        "real_batch_size": int(final_cache["real_batch_size"]),
        "physical_batch_size": int(final_cache["batch_size"]),
        "virtual_rollout_start_frame": int(SYNTHETIC_ROLLOUT_START_FRAME),
        "init_npz_paths": [str(path) for path, _cyclic in init_specs],
        "init_npz_folders": [{"path": str(path.parent), "cyclic": bool(cyclic)} for path, cyclic in init_specs],
        "init_fixed_frame": int(args.init_fixed_frame) if args.init_fixed_frame is not None else None,
        "envelope_npz_paths": [str(path) for path, _cyclic in envelope_specs],
        "envelope_npz_folders": [{"path": str(path.parent), "cyclic": bool(cyclic)} for path, cyclic in envelope_specs],
        "envelope_source": envelope_source,
        "envelope_gt_sanity": envelope_sanity,
        "simple_ae_checkpoint": str(ae_path) if ae_path is not None else None,
        "extra_simple_ae_checkpoint": str(extra_ae_path) if extra_ae_path is not None else None,
        "ae2_checkpoint": str(ae2_path) if ae2_path is not None else None,
        "ae3_checkpoint": str(ae3_path) if ae3_path is not None else None,
        "ae4_checkpoint": str(ae4_path) if ae4_path is not None else None,
        "ae5_checkpoint": str(ae5_path) if ae5_path is not None else None,
        "ae6_checkpoint": str(ae6_path) if ae6_path is not None else None,
        "simple_ae_window_frames": int(ae_window_frames),
        "ae_required_window_frames": int(ae_required_window_frames),
        "simple_ae_metadata": ae_ckpt.get("metadata", {}) if ae_ckpt else {},
        "extra_simple_ae_metadata": extra_ae_ckpt.get("metadata", {}) if extra_ae_ckpt else {},
        "ae2_schema": ae2_ckpt.get("schema", {}) if ae2_ckpt else {},
        "ae2_metadata": ae2_ckpt.get("metadata", {}) if ae2_ckpt else {},
        "ae3_schema": ae3_ckpt.get("schema", {}) if ae3_ckpt else {},
        "ae3_metadata": ae3_ckpt.get("metadata", {}) if ae3_ckpt else {},
        "ae4_schema": ae4_ckpt.get("schema", {}) if ae4_ckpt else {},
        "ae4_metadata": ae4_ckpt.get("metadata", {}) if ae4_ckpt else {},
        "ae5_schema": ae5_ckpt.get("schema", {}) if ae5_ckpt else {},
        "ae5_metadata": ae5_ckpt.get("metadata", {}) if ae5_ckpt else {},
        "ae6_schema": ae6_ckpt.get("schema", {}) if ae6_ckpt else {},
        "ae6_metadata": ae6_ckpt.get("metadata", {}) if ae6_ckpt else {},
        "ae5_calibration": ae5_calibration,
        "init_checkpoint": str(init_checkpoint_path) if init_checkpoint_path is not None else None,
        "tensorboard_logdir": "",
        "body_mode": tl.normalized_body_mode(cfg.body_mode),
        "foot_roll_output_projection": True,
        "policy": {
            "loss": (
                "identity_statue"
                if ae_loss_weight == 0.0 and extra_ae_loss_weight == 0.0 and identity_enabled and not rl_cfg.enabled
                else (
                    "rl_only"
                    if (ae_loss_weight == 0.0 and extra_ae_loss_weight == 0.0 and rl_cfg.enabled)
                    else (
                        "simple_ae_output_reconstruction_with_optional_envelope"
                        if envelope is not None
                        else "simple_ae_output_reconstruction"
                    )
                )
            ),
            "primary_loss_mode": str(PRIMARY_LOSS_MODE),
            "primary_loss_terms": {
                "ae1_active": bool(primary_loss_uses_ae1() and ae_loss_weight != 0.0),
                "gt_mse_active": bool(primary_loss_uses_gt_mse() and ae_loss_weight != 0.0),
                "ae1_weighted_tb": "loss/ae1_weighted",
                "gt_mse_weighted_tb": f"loss/{GT_MSE_WEIGHTED_TERM_NAME}",
                "raw_diagnostics_prefix": "metrics/",
                "gt_mse_row_scope": str(GT_MSE_ROW_SCOPE),
            },
            "gt_mse_loss_scale": float(GT_MSE_LOSS_SCALE),
            "gt_mse_row_scope": {
                "mode": str(GT_MSE_ROW_SCOPE),
                "all": "GT-MSE applies to every training row",
                "dedicated_periodic": (
                    "GT-MSE applies only to the dedicated real rows followed by periodic/omni reserved rows; "
                    "regular rows receive no GT-MSE even when they sample an omni clip"
                ),
                "dedicated_real_rows": int(final_cache["dedicated_real_rows"]),
                "periodic_reserved_rows": int(final_cache["periodic_reserved_rows"]),
            },
            "gt_mse_components": {
                "position": GT_MSE_POS_TERM_NAME,
                "rotation": GT_MSE_ROT_TERM_NAME,
                "linear_velocity": GT_MSE_LINVEL_TERM_NAME,
                "angular_velocity": GT_MSE_ANGVEL_TERM_NAME,
                "note": "linear/angular velocity are one-frame rates from current to predicted/GT next state",
            },
            "ae_loss_weight": float(ae_loss_weight),
            "extra_ae_loss_weight": float(extra_ae_loss_weight),
            "ae2_loss_weight": float(ae2_loss_weight),
            "ae2_weighted_term": AE2_WEIGHTED_TERM_NAME,
            "ae2_policy": "scores only non-terminal rollout windows; final frame is left to terminal AE1",
            "ae2_feature_weighting": {
                "baked_normal_loss_weight": float(AE2_BAKED_NORMAL_LOSS_WEIGHT),
                "boost_rule": "when the scalar AE2 weight exceeds baked normal, only foot end-effector flat position, foot rotation, and toe scalar channels keep the boosted scalar",
                "nonfoot_rule": "pelvis and thigh/start-rotation channels are compensated back to baked-normal effective strength",
                "foot_vertical_delta_rule": "foot position vertical-delta channels are zero-weighted; AE2 scores flat foot motion only",
                "vertical_axis": int(FOOT_ROLL_UP_AXIS),
            },
            "ae6_contact_predictor": {
                "enabled": bool(ae6_loss_weight != 0.0),
                "checkpoint": str(ae6_path) if ae6_path is not None else None,
                "loss_weight": float(ae6_loss_weight),
                "row_scope": {
                    "mode": str(AE6_ROW_SCOPE),
                    "all": "AE6 applies to every training row",
                    "dedicated_periodic": (
                        "AE6 applies only to the dedicated real rows followed by periodic/omni reserved rows; "
                        "regular rows receive no AE6 even when they sample an omni clip"
                    ),
                    "dedicated_real_rows": int(final_cache["dedicated_real_rows"]),
                    "periodic_reserved_rows": int(final_cache["periodic_reserved_rows"]),
                },
                "terms": {
                    "raw": AE6_CONTACT_SCORE_TERM_NAME,
                    "weighted": AE6_CONTACT_WEIGHTED_TERM_NAME,
                    "mae": AE6_CONTACT_MAE_TERM_NAME,
                    "binary_acc": AE6_CONTACT_ACC_TERM_NAME,
                },
                "target": "frozen AE6 predicts Unreal contact channels from controller input+output; controller pre-rule sigmoid pin meters are trained symmetrically against that detached target",
                "pin_meter": "sigmoid(-pin_logit * FOOT_ROLL_PIN_STE_SCALE), independent per foot",
                "loss_rule": "two-sided MSE on controller_pin_meter - AE6_contact_target; punishes both wrong unpinning and wrong pinning before height/forced-pin post logic",
                "init_noise_rule": "AE6 remains active on init-noise rows; init noise must perturb inputs only, not toggle losses",
            },
            "ae3_loss_weight": float(ae3_loss_weight),
            "ae3_weighted_term": AE3_PIN_WEIGHTED_TERM_NAME,
            "ae3_policy": (
                "scores non-terminal rollout pin choices with two-sided BCE between frozen pin-aware AE probabilities "
                "and the controller's post-height-gate pin meters; AE3 output gradients are scoped to pin logits "
                "plus foot vertical position, foot rotation, and toe hinge for the height-gate path; uses a soft "
                "expected-pin height push and full-strength raw-logit alignment; "
                "when bank pin is also enabled, AE3 is full-strength for the configured start hold of each rollout, then crossfades to zero by the configured end hold"
            ),
            "leg_crossing_capsule_loss": {
                "enabled": bool(leg_crossing_capsule_loss_weight != 0.0),
                "weight": float(leg_crossing_capsule_loss_weight),
                "term": LEG_CROSSING_CAPSULE_TERM_NAME,
                "raw_term": LEG_CROSSING_CAPSULE_RAW_TERM_NAME,
                "bad_rate_term": LEG_CROSSING_CAPSULE_RATE_TERM_NAME,
                "pairs": [
                    "left thigh vs right thigh",
                    "left thigh vs right calf",
                    "left calf vs right thigh",
                    "left calf vs right calf",
                ],
                "definition": (
                    "viewer-radius lower-body capsule overlap on the controller output pose using root-local IK leg endpoints; "
                    "raw metric is exact max segment-capsule overlap in meters, optimized loss is mean squared overlap across the four cross-leg pairs"
                ),
            },
            "pin_logit_gap_loss": {
                "enabled": bool(pin_logit_gap_loss_weight != 0.0),
                "weight": float(pin_logit_gap_loss_weight),
                "term": PIN_LOGIT_GAP_WEIGHTED_TERM_NAME,
                "raw_term": PIN_LOGIT_GAP_RAW_TERM_NAME,
                "bad_rate_term": PIN_LOGIT_GAP_BAD_RATE_TERM_NAME,
                "margin": float(PIN_LOGIT_GAP_MARGIN),
                "definition": (
                    "real-dataset rows only; differentiable hinge relu(margin - abs(left_pin_logit - right_pin_logit)) "
                    "so the controller is penalized unless the two foot pin logits are at least margin apart"
                ),
            },
            "inertia_acceleration_loss": {
                "enabled": bool(inertia_acceleration_loss_weight != 0.0),
                "weight": float(inertia_acceleration_loss_weight),
                "effective_scale": float(INERTIA_ACCELERATION_LOSS_SCALE),
                "reference_loss": float(INERTIA_ACCELERATION_REFERENCE_LOSS),
                "reference_raw": float(INERTIA_ACCELERATION_REFERENCE_RAW),
                "term": INERTIA_ACCELERATION_WEIGHTED_TERM_NAME,
                "raw_term": INERTIA_ACCELERATION_RAW_TERM_NAME,
                "linear_raw_term": INERTIA_LINEAR_ACCELERATION_RAW_TERM_NAME,
                "angular_raw_term": INERTIA_ANGULAR_ACCELERATION_RAW_TERM_NAME,
                "bad_rate_term": INERTIA_ACCELERATION_BAD_RATE_TERM_NAME,
                "limits": inertia_limits_metadata(inertia_limits) if inertia_limits else {},
                "definition": (
                    "real-dataset rows only; compares consecutive controller transition deltas for pelvis, foot_l, and foot_r. "
                    "Position deltas are output-space vector differences, rotation deltas are row-vector rotation vectors, "
                    "and the differentiable hinge is zero up to the maximum GT delta-differential found in the omni+transition real dataset."
                ),
            },
            "root_accel_pin_loss": {
                "enabled": bool(root_accel_pin_loss_ratio != 0.0),
                "fixed_loss_weight_multiplier": float(root_accel_pin_loss_ratio),
                "fixed_loss_weight": float(ROOT_ACCEL_PIN_FIXED_LOSS_WEIGHT),
                "effective_loss_weight": float(ROOT_ACCEL_PIN_FIXED_LOSS_WEIGHT) * float(root_accel_pin_loss_ratio),
                "term": ROOT_ACCEL_PIN_WEIGHTED_TERM_NAME,
                "raw_term": ROOT_ACCEL_PIN_RAW_TERM_NAME,
                "scale_term": ROOT_ACCEL_PIN_SCALE_TERM_NAME,
                "root_accel_term": ROOT_ACCEL_PIN_ACCEL_TERM_NAME,
                "active_rate_term": ROOT_ACCEL_PIN_ACTIVE_RATE_TERM_NAME,
                "bad_rate_term": ROOT_ACCEL_PIN_BAD_RATE_TERM_NAME,
                "max_pin_term": ROOT_ACCEL_PIN_MAX_PROB_TERM_NAME,
                "height_term": ROOT_ACCEL_PIN_HEIGHT_TERM_NAME,
                "acceleration_threshold_mps2": float(ROOT_ACCEL_PIN_ACCEL_THRESHOLD_MPS2),
                "acceleration_gate_width_mps2": float(ROOT_ACCEL_PIN_ACCEL_GATE_WIDTH_MPS2),
                "target_pin_probability": float(ROOT_ACCEL_PIN_TARGET_PROB),
                "height_threshold_m": float(ROOT_ACCEL_PIN_HEIGHT_THRESHOLD_M),
                "definition": (
                    "when horizontal root acceleration exceeds 10 m/s2, the loss softly selects the most pinned foot "
                    "and penalizes pin probability below 0.9 or collider-computed foot height above 0.5 cm; "
                    "the forward metric uses the hard max-pin foot, while gradients use a softmax foot selection "
                    "and the existing smooth collider-height surrogate"
                ),
                "scale_rule": "weighted loss is root_accel_pin_raw multiplied by fixed_loss_weight * fixed_loss_weight_multiplier; TensorBoard loss/root_accel_pin_weighted is the actual training contribution",
            },
            "ae4_loss_weight": float(ae4_loss_weight),
            "ae4_weighted_term": AE4_POSE_WEIGHTED_TERM_NAME,
            "ae4_score_deadzone": float(AE4_POSE_SCORE_DEADZONE),
            "ae4_idle_clip_deadzone": 0.0,
            "ae4_score_units": "mean joint distance plus rotation angle converted to AE4-equivalent meters",
            "ae4_hinge_units": (
                "mean per-joint position excess over row deadzone plus rotation excess converted to AE4-equivalent meters; "
                "position uses the row distance deadzone, rotation has a fixed 20 degree deadzone"
            ),
            "ae4_reference_score": float(AE4_POSE_REFERENCE_SCORE),
            "ae4_reference_loss": float(AE4_POSE_REFERENCE_LOSS),
            "ae4_rotation_deadzone_deg": float(AE4_POSE_ROTATION_DEADZONE_DEG),
            "ae4_rotation_reference_deg": float(AE4_POSE_ROTATION_REFERENCE_DEG),
            "ae4_rotation_reference_loss": float(AE4_POSE_ROTATION_REFERENCE_LOSS),
            "ae4_policy": (
                "scores every rollout output against the frozen root-conditioned AE4 pose-bank projection shown in the viz; "
                "the bank target is detached, non-idle rows use the configured position dead-zone, idle clip rows have zero position dead-zone, "
                "rotations have a 20 degree dead-zone, and a 45 degree rotation miss contributes 0.01 at the base AE4 weight before rollout averaging"
                if ae4_uses_pose_bank_projector(ae4)
                else "scores every rollout output with frozen output-pose AE4 in pose space; non-idle rows use the configured position dead-zone, idle clip rows have zero position dead-zone, rotations have a 20 degree dead-zone, and a 45 degree rotation miss contributes 0.01 at the base AE4 weight before rollout averaging"
            ),
            "ae4_bank_pin_loss_weight": float(ae4_bank_pin_loss_weight),
            "ae4_bank_pin_weighted_term": AE4_BANK_PIN_WEIGHTED_TERM_NAME,
            "ae4_bank_pin_raw_term": AE4_BANK_PIN_RAW_TERM_NAME,
            "ae4_bank_pin_root_scale_term": AE4_BANK_PIN_ROOT_SCALE_TERM_NAME,
            "ae4_bank_pin_per_logit_mistake_loss": float(AE4_BANK_PIN_LOGIT_MISTAKE_LOSS),
            "ae4_bank_pin_walkf_speed_fraction": float(AE4_BANK_PIN_WALKF_SPEED_FRACTION),
            "ae4_bank_pin_speed_cutoff_mps": float(ae4_bank_pin_speed_cutoff_mps),
            "ae4_bank_pin_turn45l_yaw_fraction": float(AE4_BANK_PIN_TURN45L_YAW_FRACTION),
            "ae4_bank_pin_turn45l_max_yaw_delta_rad": float(ae4_bank_pin_turn45l_max_yaw_delta_rad),
            "ae4_bank_pin_yaw_cutoff_rad": float(ae4_bank_pin_yaw_cutoff_rad),
            "ae3_bank_pin_phase_start_hold_fraction": float(AE3_BANK_PIN_PHASE_START_HOLD_FRACTION),
            "ae3_bank_pin_phase_end_hold_fraction": float(AE3_BANK_PIN_PHASE_END_HOLD_FRACTION),
            "ae4_bank_pin_policy": (
                "pose-bank AE4 precomputes precise GT pin labels per bank frame using the old sole-rectangle detector; "
                "each rollout output gathers labels from the same nearest bank pose used by AE4, scores differentiable wrong-sign pin probability, "
                "linearly gates it by root translation from 1 at idle speed to 0 at 20% of walkF root speed, "
                "also gates it by root yaw from 1 at zero yaw to 0 at 20% of max Turn45L root yaw delta, and when AE3 is also enabled, "
                "keeps bank pin at zero for the configured start hold of each rollout before crossfading to full strength for the configured end hold; "
                "the term is scoped only to the forced idle tail row(s), so random full-dataset rows and the forced turn45 row do not receive bank-pin loss"
            ),
            "ae_score_terminal_only": bool(AE_TERMINAL_ONLY),
            "ae_score_terminal_scale": (
                "effective rollout length, so terminal-only AE keeps dense rollout-average scale"
                if bool(AE_TERMINAL_ONLY)
                else "none"
            ),
            "simple_ae_window_frames": int(ae_window_frames),
            "simple_ae_window_policy": "hardcoded_to_2_frames",
            "ae5_big_window": {
                "enabled": bool(ae5_effective_loss_weight != 0.0),
                "checkpoint": str(ae5_path) if ae5_path is not None else None,
                "window_frames": int(ae5_window_frames),
                "required_start_context_frames": int(ae_required_window_frames),
                "user_loss_weight": float(ae5_loss_weight),
                "effective_loss_weight": float(ae5_effective_loss_weight),
                "calibrate_to_ae1_omni": bool(args.ae5_calibrate_to_ae1_omni),
                "calibration": ae5_calibration,
                "scope": "real cyclic/periodic omni rows only; CUDA training evaluates AE5 only on fixed periodic-reserved head rows",
                "validity": "scores only rollout segments with at least ae5 window_frames since the last reset; rows with K < window_frames get zero AE5 weight",
                "terms": {
                    "raw": AE5_SCORE_TERM_NAME,
                    "weighted": AE5_WEIGHTED_TERM_NAME,
                    "active_rate": AE5_ACTIVE_RATE_TERM_NAME,
                },
            },
            "init_noise": {
                "enabled": bool(init_noise_enabled(init_noise_clean_fraction) or init_noise_regular_row_fraction > 0.0),
                "clean_fraction": float(init_noise_clean_fraction),
                "noisy_fraction": float(1.0 - init_noise_clean_fraction),
                "regular_row_noisy_fraction": float(init_noise_regular_row_fraction),
                "regular_row_start": int(final_cache["dedicated_real_rows"]) + int(final_cache["periodic_reserved_rows"]),
                "regular_row_count": max(
                    0,
                    int(final_cache["real_batch_size"])
                    - int(final_cache["dedicated_real_rows"])
                    - int(final_cache["periodic_reserved_rows"]),
                ),
                "fixed_strength_scale": float(init_noise_fixed_strength_scale),
                "fixed_position_amount": float(INIT_NOISE_FIXED_POSITION_AMOUNT * init_noise_fixed_strength_scale),
                "fixed_rotation_amount": float(INIT_NOISE_FIXED_ROTATION_AMOUNT * init_noise_fixed_strength_scale),
                "fixed_global_yaw_deg": float(INIT_NOISE_FIXED_GLOBAL_YAW_DEG * init_noise_fixed_strength_scale),
                "fixed_base_position_amount": float(INIT_NOISE_FIXED_POSITION_AMOUNT),
                "fixed_base_rotation_amount": float(INIT_NOISE_FIXED_ROTATION_AMOUNT),
                "fixed_base_global_yaw_deg": float(INIT_NOISE_FIXED_GLOBAL_YAW_DEG),
                "batch_rule": "sample one noisy mask per batch; clean rows stay unperturbed, noisy rows receive shared init noise; optional regular-row fraction excludes dedicated RunB and periodic omni reserved rows",
                "pair_rule": "the exact same sampled noise is applied to both sampled init frames for each noisy row",
                "cleanup_rule": "init noise applies vector perturbations only; it does not run a separate cleanup/lift path",
                "rollout_k_rule": "init noise does not alter rollout K or full-window sampling",
                "loss_rule": "init noise does not change AE1 row weights, AE context construction, or AE6 activity",
            },
            "random_initialization": {
                "enabled": bool(random_init_noise_rows),
                "row_source": "same regular real row range selected by init_noise_regular_row_fraction",
                "regular_row_fraction": float(init_noise_regular_row_fraction),
                "regular_row_start": int(final_cache["dedicated_real_rows"]) + int(final_cache["periodic_reserved_rows"]),
                "regular_row_count": max(
                    0,
                    int(final_cache["real_batch_size"])
                    - int(final_cache["dedicated_real_rows"])
                    - int(final_cache["periodic_reserved_rows"]),
                ),
                "adjacent_frame_rule": "selected rows initialize and internal mixed-K resets use random adjacent dataset frames (t-1, t)",
                "target_rule": "target clip/start, row weighting, rollout K sampling, AE6 activity, and loss masks remain unchanged",
                "noise_strength_scale": float(init_noise_fixed_strength_scale),
            },
            "forced_rows": {
                "idle_clip_stem": forced_idle_clip_stem,
                "idle_batch_row": "last rows",
                "idle_batch_fraction": forced_idle_batch_fraction,
                "turn45_clip_stems": list(forced_turn45_clip_stems),
                "turn45_batch_row": "immediately before forced idle rows",
                "turn45_batch_fraction": forced_turn45_batch_fraction,
                "turn45_sampling": "each forced turn45 row independently samples one of the configured turn45 clips",
                "noise_rule": "forced tail rows are marked noisy whenever init noise is enabled",
            },
            "dedicated_real_rows": {
                "clip_stems": list(dedicated_real_clip_stems),
                "rows": int(final_cache["dedicated_real_rows"]),
                "loss_multiplier": float(dedicated_real_loss_multiplier),
                "layout": "dedicated real rows are sampled first in the real batch, before omni-reserved rows",
                "weight_rule": "the base per-row rollout loss weight is multiplied by loss_multiplier for these rows",
            },
            "foot_unpin_penalty": {
                "enabled": bool(float(FOOT_UNPIN_PENALTY_WEIGHT) != 0.0),
                "weight": float(FOOT_UNPIN_PENALTY_WEIGHT),
                "term": FOOT_UNPIN_PENALTY_TERM_NAME,
                "soft_rate_metric": FOOT_UNPIN_SOFT_RATE_TERM_NAME,
                "definition": "differentiable penalty on 1 - soft_both_feet_pinned from pin logits",
            },
            "pinned_foot_intent_penalty": {
                "enabled": bool(float(PINNED_FOOT_INTENT_PENALTY_WEIGHT) != 0.0),
                "weight": float(PINNED_FOOT_INTENT_PENALTY_WEIGHT),
                "term": PINNED_FOOT_INTENT_TERM_NAME,
                "raw_term": PINNED_FOOT_INTENT_RAW_TERM_NAME,
                "speed_metric": PINNED_FOOT_INTENT_MPS_TERM_NAME,
                "definition": "soft pin-logit weighted pre-projection foot motion mps^2",
            },
            "slide_tentative_loss": {
                "enabled": bool(slide_tentative_loss_weight != 0.0),
                "weight": float(slide_tentative_loss_weight),
                "term": SLIDE_TENTATIVE_TERM_NAME,
                "raw_term": SLIDE_TENTATIVE_RAW_TERM_NAME,
                "pin_rate_metric": SLIDE_TENTATIVE_PIN_RATE_TERM_NAME,
                "definition": (
                    "final-pin-mask averaged horizontal L1 IK foot-position correction between clean raw controller output "
                    "and the foot-roll projected output; vertical axis is excluded with FOOT_ROLL_UP_AXIS"
                ),
            },
            "pinned_foot_height_loss": {
                "enabled": bool(pinned_foot_height_weight != 0.0),
                "weight": float(pinned_foot_height_weight),
                "term": PINNED_FOOT_HEIGHT_TERM_NAME,
                "raw_term": PINNED_FOOT_HEIGHT_RAW_TERM_NAME,
                "reference_excess_m": float(PINNED_FOOT_HEIGHT_REFERENCE_EXCESS_M),
                "zero_excess_m": float(PINNED_FOOT_HEIGHT_REFERENCE_EXCESS_M * PINNED_FOOT_HEIGHT_ZERO_FRACTION),
                "reference_loss": float(PINNED_FOOT_HEIGHT_REFERENCE_LOSS),
                "cap": float(PINNED_FOOT_HEIGHT_LOSS_CAP),
                "definition": "soft pin-logit weighted existing cleaned foot/toe height; exact forward value uses pin-gate height, gradient uses a smooth lowest-OBB surrogate",
            },
            "idle_foot_flatness_loss": {
                "enabled": bool(idle_foot_flatness_weight != 0.0),
                "weight": float(idle_foot_flatness_weight),
                "term": IDLE_FOOT_FLATNESS_TERM_NAME,
                "raw_term": IDLE_FOOT_FLATNESS_RAW_TERM_NAME,
                "forced_idle_clip_stem": forced_idle_clip_stem,
                "forced_idle_batch_row": "last",
                "forced_idle_batch_fraction": forced_idle_batch_fraction,
                "batch_scale": "batch_size * 0.5",
                "reference_excess_m": float(IDLE_FOOT_FLATNESS_REFERENCE_EXCESS_M),
                "zero_excess_m": float(IDLE_FOOT_FLATNESS_REFERENCE_EXCESS_M * IDLE_FOOT_FLATNESS_ZERO_FRACTION),
                "reference_loss": float(IDLE_FOOT_FLATNESS_REFERENCE_LOSS),
                "cap": float(IDLE_FOOT_FLATNESS_LOSS_CAP),
                "definition": "idle-only foot/toe sole vertical spread; the forced idle row is kept in the noisy side of the init-noise split",
            },
            "identity_output_loss_weight": float(identity_loss_weight),
            "identity_output_maxabs_loss_weight": float(identity_maxabs_weight),
            "identity_world_pos_loss_weight": float(identity_world_pos_weight),
            "identity_pelvis_pos_loss_weight": float(identity_pelvis_pos_weight),
            "ae_score_output_only": bool(AE_SCORE_OUTPUT_ONLY),
            "ae_scores_raw_output": False,
            "ae_scores_clean_projected_output": True,
            "ae_scores_include_pin_logits": False,
            "ae_foot_location_multiplier": float(AE_FOOT_LOCATION_MULTIPLIER),
            "ae_foot_rotation_multiplier": float(AE_FOOT_ROTATION_MULTIPLIER),
            "ae_foot_location_switches": {
                "location_multiplier": "--ae-foot-location-multiplier",
                "rotation_multiplier": "--ae-foot-rotation-multiplier",
            },
            "rl_loss_enabled": bool(rl_cfg.enabled),
            "rl_loss": rl_cfg.to_dict(),
            "envelope_loss_enabled": bool(envelope is not None),
            "envelope_loss": {
                "linear_slide_loss_weight": float(linear_slide_weight),
                "angular_slide_loss_weight": float(angular_slide_weight),
                "foot_height_loss_weight": float(foot_height_weight),
                "foot_height_loss_scale": float(FOOT_HEIGHT_LOSS_SCALE),
                "foot_height_loss_effective_weight": float(foot_height_weight) * float(FOOT_HEIGHT_LOSS_SCALE),
                "margin": float(args.envelope_margin),
                "knn": int(args.envelope_knn),
                "source": envelope_source,
                "source_clip_count": int(len(envelope_specs)),
                "gt_sanity": envelope_sanity,
                "metadata": envelope["metadata"] if envelope is not None else None,
            },
            "alternating_feet_loss": {
                "enabled": bool(alternating_feet_loss_enabled(alternating_feet_weight)),
                "weight": float(alternating_feet_weight),
                "both_feet_moving_threshold_mps": float(BOTH_FEET_MOVING_THRESHOLD_MPS),
                "walkF_root_speed_mps": float(walk_f_root_speed_mps),
                "root_still_cutoff_mps": float(alternating_root_cutoff_mps),
                "root_gate": "clamp(1 - root_1frame_speed / (walkF_root_speed / 3), 0, 1)",
                "overlap_definition": "min(left_compact_slide_speed, right_compact_slide_speed)",
            },
            "foot_lift_slide_loss": {
                "enabled": bool(foot_lift_slide_loss_enabled(foot_lift_slide_weight)),
                "weight": float(foot_lift_slide_weight),
                "full_lift_height_m": float(FOOT_LIFT_FULL_HEIGHT_M),
                "full_lift_speed_mps": float(FOOT_LIFT_FULL_SPEED_MPS),
                "grounded_slide_loss_scale": float(GROUNDED_FOOT_SLIDE_LOSS_SCALE),
                "grounded_slide_release_m": float(GROUNDED_FOOT_SLIDE_RELEASE_M),
                "deadzone_low_mps": float(FOOT_SPEED_DEADZONE_LOW_MPS),
                "deadzone_fast_mps": float(FOOT_SPEED_DEADZONE_FAST_MPS),
                "deadzone_loss_scale": float(FOOT_SPEED_DEADZONE_LOSS_SCALE),
                "overspeed_max_mps": float(FOOT_SPEED_OVERSPEED_MAX_MPS),
                "overspeed_loss_scale": float(FOOT_SPEED_OVERSPEED_LOSS_SCALE),
                "terminal_stillness_frames": int(TERMINAL_FOOT_STILLNESS_FRAMES),
                "terminal_stillness_loss_scale": float(TERMINAL_FOOT_STILLNESS_LOSS_SCALE),
                "moving_threshold_mps": float(BOTH_FEET_MOVING_THRESHOLD_MPS),
                "walkF_root_speed_mps": float(walk_f_root_speed_mps),
                "root_still_cutoff_mps": float(alternating_root_cutoff_mps),
                "root_gate": "clamp(1 - root_1frame_speed / (walkF_root_speed / 3), 0, 1)",
                "bound": (
                    f"allowed linear foot speed = clamp((height - height_lower_bound) / "
                    f"{FOOT_LIFT_FULL_HEIGHT_M:.2f}, 0, 1) * {FOOT_LIFT_FULL_SPEED_MPS:.2f}"
                ),
            },
            "ik_lower_length_loss": {
                "enabled": bool(ik_lower_length_loss_enabled()),
                "weight": float(IK_LOWER_LENGTH_LOSS_WEIGHT),
                "leg_tolerance_m": float(IK_LOWER_LENGTH_LEG_TOLERANCE_M),
                "arm_tolerance_m": float(IK_LOWER_LENGTH_ARM_TOLERANCE_M),
                "definition": "penalize IK lower segment length outside authored rest length tolerance",
            },
            "rl_grad_clip_norm": float(RL_GRAD_CLIP_NORM) if rl_cfg.enabled else 0.0,
            "zero_loss_stop_threshold": float(ZERO_LOSS_STOP_THRESHOLD),
            "predict_residual": bool(cfg.predict_residual),
            "zero_init_output": bool(cfg.zero_init_output),
            "max_train_seconds": float(args.max_train_seconds) if args.max_train_seconds is not None else None,
            "output_initialization": output_initialization,
            "output_reference_root": tl.OUTPUT_REFERENCE_ROOT,
            "output_prediction_mode": tl.normalized_output_prediction_mode(),
            "state_reference_root": tl.STATE_REFERENCE_ROOT,
            "ik_schema_version": tl.IK_SCHEMA_VERSION,
            "ik_pole_reference": tl.IK_POLE_REFERENCE,
            "ik_leg_pole_alpha_deg": math.degrees(tl.IK_LEG_POLE_ALPHA),
            "ik_arm_pole_alpha_deg": math.degrees(tl.IK_ARM_POLE_ALPHA),
            "mixed_rollout_at_max": bool(MIXED_ROLLOUT_AT_MAX),
            "adaptive_sampling": {
                "enabled": bool(adaptive_sampler is not None),
                "adaptive_fraction": float(adaptive_sampler.adaptive_fraction) if adaptive_sampler is not None else 0.0,
                "uniform_fraction": float(1.0 - adaptive_sampler.adaptive_fraction) if adaptive_sampler is not None else 1.0,
                "eligible_clip_count": int(adaptive_sampler.eligible_count) if adaptive_sampler is not None else 0,
                "virtual_excluded": True,
                "update_interval_s": float(adaptive_sampler.update_interval_s) if adaptive_sampler is not None else 0.0,
                "loss_buffer": "per-animation EMA of sampled per-row training loss",
                "probability_rule": "p(animation) proportional to its loss EMA; 2x loss gives 2x adaptive probability",
                "tensorboard": "sampler/{omni,transition}_{prob,picked}_hist_frame image summaries",
            },
            "virtual_training": {
                "enabled": bool(
                    synthetic_clip_ids
                    and (synthetic_batch_fraction > 0.0 or synthetic_reserved_rows > 0 or virtual_reserved_rows > 0)
                ),
                "generated_clip_count": int(len(synthetic_clip_ids)),
                "synthetic_clip_count": int(len(synthetic_reserved_clip_ids)),
                "virtual_clip_count": int(len(virtual_reserved_clip_ids)),
                "batch_fraction": float(synthetic_batch_fraction),
                "synthetic_reserved_rows": int(synthetic_reserved_rows),
                "virtual_reserved_rows": int(virtual_reserved_rows),
                "real_rows": int(final_cache["real_batch_size"]),
                "physical_batch_size": int(final_cache["batch_size"]),
                "row_layout": "real rows first, then synthetic reserved rows, then virtual reserved rows",
                "start_rule": "reserved generated rows sample random starts from their own datasets using the same K pool as their row",
                "reset_rule": "generated rows use normal same-clip random reset starts; they are not forced back to frame 1",
                "adaptive_sampling": "virtual rows do not update adaptive loss buffers or probabilities",
            },
            "pose_representation": tl.IK_POSE_REPRESENTATION,
            "body_mode": tl.normalized_body_mode(cfg.body_mode),
            "body_mode_role": "lower_body_controller" if tl.body_mode_is_lower(cfg.body_mode) else "upper_body_placeholder",
            "foot_roll_output_projection": {
                "enabled": True,
                "pin_outputs": int(tl.FOOT_ROLL_PIN_OUTPUT_DIM),
                "pin_mode": str(FOOT_ROLL_PIN_MODE),
                "integration_steps": int(FOOT_ROLL_INTEGRATION_STEPS),
                "side_blend_deg": float(cfg.foot_roll_side_blend_deg),
                "ground_y": float(cfg.foot_roll_ground_y),
                "height_pin_gate_enabled": bool(FOOT_ROLL_HEIGHT_PIN_GATE),
                "height_pin_gate_flag": "--foot-roll-height-pin-gate",
                "near_floor_forced_pin": {
                    "enabled": bool(str(FOOT_ROLL_PIN_MODE) == FOOT_ROLL_PIN_MODE_CONTINUOUS_SIGMOID),
                    "selected_foot": "lowest raw pin logit when both feet are below fade height; otherwise lowest collider height when only one foot is below fade height",
                    "full_height_m": float(FOOT_ROLL_NEAR_FLOOR_PIN_FULL_HEIGHT_M),
                    "fade_height_m": float(FOOT_ROLL_NEAR_FLOOR_PIN_FADE_HEIGHT_M),
                    "minimum_pin_probability": float(FOOT_ROLL_NEAR_FLOOR_PIN_MIN_PROB),
                    "rule": (
                        "continuous-sigmoid inference starts from the model pin meter for each foot and never caps a foot because "
                        "it is high. If both feet are below the fade height, the foot with the lowest raw pin logit receives "
                        "the near-floor minimum-pin floor and the other foot keeps the model value. If only one foot is below "
                        "the fade height, the lower-height foot receives that floor. The selected foot is clamped to at least "
                        f"{FOOT_ROLL_NEAR_FLOOR_PIN_MIN_PROB:.2f} "
                        f"when its collider height is below {FOOT_ROLL_NEAR_FLOOR_PIN_FULL_HEIGHT_M * 100.0:.1f} cm, "
                        f"then linearly fades to no forced floor by {FOOT_ROLL_NEAR_FLOOR_PIN_FADE_HEIGHT_M * 100.0:.1f} cm. "
                        "Non-selected feet are free to pin themselves as the model asks."
                    ),
                },
                "rule": (
                    "logit-selected feet pin/project regardless of current height"
                    if str(FOOT_ROLL_PIN_MODE) == FOOT_ROLL_PIN_MODE_LEGACY_LOGIT_SELECTED
                    else "each foot independently blends foot-roll projection by its final pin meter; height only adds a selected-foot minimum floor, never a ceiling"
                ),
                "pin_threshold_m": float(FOOT_HEIGHT_PIN_THRESHOLD_M),
                "release_height_m": float(FOOT_CONTACT_MIN_HEIGHT_LOSS_FULL_M),
                "contact_min_height_loss": {
                    "term": FOOT_CONTACT_HEIGHT_LOSS_TERM_NAME,
                    "max_loss": float(FOOT_CONTACT_MIN_HEIGHT_LOSS_MAX),
                    "zero_at_m": float(FOOT_HEIGHT_PIN_THRESHOLD_M),
                    "full_at_m": float(FOOT_CONTACT_MIN_HEIGHT_LOSS_FULL_M),
                    "definition": "linear ramp on min(left_height, right_height) after foot-roll/penetration cleaning",
                },
                "gradient": (
                    "height gate disabled; pin-logit gradient directly controls horizontal foot-roll projection"
                    if str(FOOT_ROLL_PIN_MODE) == FOOT_ROLL_PIN_MODE_LEGACY_LOGIT_SELECTED
                    else "continuous sigmoid pin meters directly scale horizontal foot-roll projection per foot; final vertical lift only prevents penetration"
                ),
            },
            "fake_gravity": {
                "enabled": bool(FAKE_GRAVITY_ENABLED),
                "strength": float(FAKE_GRAVITY_ENABLED),
                "gravity_mps2": float(FAKE_GRAVITY_MPS2),
                "vertical_axis": int(FOOT_ROLL_UP_AXIS),
                "fps": float(store.prototype.fps),
                "per_frame_gravity_delta_m": float(FAKE_GRAVITY_MPS2)
                / max(1.0, float(store.prototype.fps))
                / max(1.0, float(store.prototype.fps)),
                "uses_height_gate": bool(FAKE_GRAVITY_USES_HEIGHT_GATE),
                "toggle_on": "--fake-gravity",
                "toggle_off": "--no-fake-gravity",
                "pelvis_rule": "blend model pelvis delta to previous-frame pelvis delta plus gravity by 1 - max(left_pin_meter, right_pin_meter)",
                "foot_rule": "each unpinned foot keeps its model delta and adds only per-step fake gravity by 1 - that foot pin meter; final foot projection/lift prevents penetration",
            },
            "test_set": False,
            "checkpoint_selection": "latest_stage_last",
            "init_checkpoint_epoch": int(init_ckpt.get("epoch", 0)) if init_ckpt is not None else 0,
            "init_checkpoint_rollout_k": int(init_ckpt.get("rollout_k", 0)) if init_ckpt is not None else 0,
            "init_checkpoint_optimizer_loaded": bool(init_ckpt is not None and args.load_optimizer),
            "resume_step_from_checkpoint": bool(args.resume_step_from_checkpoint),
            "rollout_initialization": "random_inter_animation" if init_store is not None else "target_clip",
            "rollout_init_fixed_frame": int(args.init_fixed_frame) if args.init_fixed_frame is not None else None,
            "rollout_init_context": (
                "duplicated_sampled_frame" if init_store is not None and DUPLICATE_ROLLOUT_INIT_CONTEXT else "previous_current"
            ),
            "rollout_init_source_count": int(len(init_specs)),
            "rollout_init_source_rows": int(init_start_pool.row_count) if init_start_pool is not None else 0,
        },
        "rollout_schedule": [int(k) for k in ROLLOUT_SCHEDULE],
        "rollout_stage_steps": [int(n) for n in ROLLOUT_STAGE_STEPS],
        "rollout_k": int(ROLLOUT_K),
        "rollout_mode": "mixed_geometric_at_max" if MIXED_ROLLOUT_AT_MAX else "fixed_per_stage",
        "log_every": int(LOG_EVERY),
        "loss_refresh_rate": int(LOSS_REFRESH_RATE),
        "row_count": int(final_cache["row_count"]),
        "batch_size": int(final_cache["batch_size"]),
        "input_dim": int(input_dim),
        "output_dim": int(output_dim),
        "controller_output_dim": int(model_output_dim),
        "start_pool_rows": {str(k): v["pool_rows"] for k, v in stage_cache.items()},
        "dedicated_real_start_pool_rows": {
            str(k): v["dedicated_real_pool_rows"] for k, v in stage_cache.items()
        },
        "periodic_reserved_start_pool_rows": {
            str(k): v["periodic_reserved_pool_rows"] for k, v in stage_cache.items()
        },
        "synthetic_start_pool_rows": {str(k): v["synthetic_pool_rows"] for k, v in stage_cache.items()},
        "stage_learning_rates": {str(k): float(stage_learning_rate(k)) for k in ROLLOUT_SCHEDULE},
    }
    start_step = int(init_checkpoint_epoch) if bool(args.resume_step_from_checkpoint) else 0

    def begin_controller_run() -> tuple[str, Path, SummaryWriter, float, float, int, float, float]:
        nonlocal arm_phase_started

        run_id = ik_run_id(args.run_label)
        run_dir = RUNS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        metadata["tensorboard_logdir"] = str(run_dir / "tb")
        config_payload = {"config": asdict(cfg), "metadata": metadata}
        (run_dir / "config.json").write_text(json.dumps(config_payload, indent=2), encoding="utf-8")
        writer = SummaryWriter(log_dir=str(run_dir / "tb"), flush_secs=1)
        writer.add_text("config/json", f"```json\n{json.dumps(config_payload, indent=2)}\n```", 0)
        writer.flush()
        refresh_tensorboard_async()
        arm_phase_started = emit_pretrain_arm_timing("write_config_tensorboard", arm_phase_started)
        print(
            f"simple_ae_controller run={run_id} "
            f"ae={ae_path if ae_path is not None else 'disabled'} tensorboard_logdir={run_dir / 'tb'}",
            flush=True,
        )
        last_loss = float("inf")
        best_loss = float("inf")
        init_path = save_controller_checkpoint(
            run_dir,
            run_id,
            "init",
            model,
            optimizer,
            start_step,
            last_loss,
            int(init_ckpt.get("rollout_k", 0)) if init_ckpt is not None else 0,
            cfg,
            metadata,
            adaptive_sampler=adaptive_sampler,
        )
        print(f"saved initial checkpoint {init_path}", flush=True)
        arm_phase_started = emit_pretrain_arm_timing("save_init_checkpoint", arm_phase_started)
        run_started = time.perf_counter()
        timed_interval_seconds = 60.0 * max(0.0, float(getattr(cfg, "timed_checkpoint_interval_minutes", 0.0)))
        return run_id, run_dir, writer, last_loss, best_loss, start_step, run_started, timed_interval_seconds

    run_id, run_dir, writer, last_loss, best_loss, step, start, timed_interval_seconds = begin_controller_run()
    best_pending_save = False
    total_steps = sum(int(x) for x in ROLLOUT_STAGE_STEPS)
    stop_training = False
    nonfinite_loss_stop = False
    reported_max_train_seconds: float | None = None
    auto_debug_export_count = max(0, int(getattr(args, "debug_rollout_auto_export_count", 0)))
    auto_debug_export_every = max(1, int(getattr(args, "debug_rollout_auto_export_every", 1)))
    auto_debug_next_index = 0
    last_stage_k = int(ROLLOUT_SCHEDULE[0]) if ROLLOUT_SCHEDULE else int(ROLLOUT_K)
    next_timed_checkpoint = (
        start + timed_interval_seconds if timed_interval_seconds > 0.0 else float("inf")
    )

    def current_max_train_seconds() -> float | None:
        nonlocal reported_max_train_seconds
        cap = float(args.max_train_seconds) if args.max_train_seconds is not None else None
        cap_file = getattr(args, "max_train_seconds_file", None)
        if cap_file:
            cap_path = Path(cap_file)
            try:
                if cap_path.exists():
                    text = cap_path.read_text(encoding="utf-8").strip()
                    if text:
                        cap = float(text)
            except Exception as exc:
                print(f"max_train_seconds_file_read_failed path={cap_path} error={exc}", flush=True)
        if cap is not None and (reported_max_train_seconds is None or abs(cap - reported_max_train_seconds) > 1e-6):
            source = cap_file if cap_file else "args"
            print(f"effective_max_train_seconds={cap:.1f} source={source}", flush=True)
            reported_max_train_seconds = cap
        return cap

    set_active_checkpoint_context(
        run_id=run_id,
        run_dir=run_dir,
        model=model,
        optimizer=optimizer,
        step=step,
        last_loss=last_loss,
        last_stage_k=last_stage_k,
        cfg=cfg,
        metadata=metadata,
        adaptive_sampler=adaptive_sampler,
    )
    cumulative_stage_steps = 0
    for stage_idx, stage_k in enumerate(ROLLOUT_SCHEDULE):
        last_stage_k = int(stage_k)
        stage_steps = int(ROLLOUT_STAGE_STEPS[stage_idx])
        stage_global_start = cumulative_stage_steps + 1
        stage_global_end = cumulative_stage_steps + stage_steps
        cumulative_stage_steps = stage_global_end
        if step >= stage_global_end:
            print(
                f"skipping completed stage={stage_idx + 1}/{len(ROLLOUT_SCHEDULE)} "
                f"K={stage_k} steps={stage_global_start}-{stage_global_end} resume_step={step}",
                flush=True,
            )
            continue
        initial_stage_step = max(0, step - stage_global_start + 1)
        lr = stage_learning_rate(int(stage_k))
        entering_resumed_stage = (
            bool(args.load_optimizer)
            and bool(args.resume_step_from_checkpoint)
            and step == start_step
            and stage_global_start <= step + 1 <= stage_global_end
        )
        if stage_idx > 0 and bool(cfg.lr_reset_on_rollout_advance) and not entering_resumed_stage:
            optimizer = make_adamw(model.parameters(), lr, device, capturable=bool(device.type == "cuda"))
        else:
            set_optimizer_lr(optimizer, lr)
        update_active_checkpoint_context(optimizer=optimizer, last_stage_k=last_stage_k)
        cache = stage_cache[int(stage_k)]
        model.train()
        root_cache_started = time.perf_counter()
        store.prepare_root_state_cache(int(stage_k))
        if ae4_bank_pin_loss_weight != 0.0:
            prepare_ae4_bank_pin_root_delta_scale_cache(
                store,
                ae4_bank_pin_speed_cutoff_mps,
                ae4_bank_pin_yaw_cutoff_rad,
            )
        arm_phase_started = emit_pretrain_arm_timing(
            "prepare_root_state_cache",
            root_cache_started,
            K=int(stage_k),
        )
        stepper_started = time.perf_counter()
        stepper = make_pure_ae_stepper(
            model,
            optimizer,
            ae,
            mean,
            std,
            store,
            int(stage_k),
            int(cache["batch_size"]),
            cache["start_pools"],
            cache["full_window_start_pools"],
            rl_cfg,
            ae_loss_weight,
            envelope,
            linear_slide_weight,
            angular_slide_weight,
            foot_height_weight,
            alternating_feet_weight,
            foot_lift_slide_weight,
            pinned_foot_height_weight,
            idle_foot_flatness_weight,
            forced_idle_batch_fraction,
            forced_turn45_batch_fraction,
            alternating_root_cutoff_mps,
            identity_loss_weight,
            identity_maxabs_weight,
            identity_world_pos_weight,
            identity_pelvis_pos_weight,
            init_store,
            init_start_pool,
            init_noise_amount,
            init_noise_clean_fraction,
            init_noise_regular_row_fraction,
            init_noise_fixed_strength_scale,
            random_init_noise_rows,
            adaptive_sampler,
            cache["synthetic_start_pools"],  # type: ignore[arg-type]
            synthetic_batch_fraction,
            cache["synthetic_reserved_start_pools"],  # type: ignore[arg-type]
            synthetic_reserved_rows,
            cache["virtual_reserved_start_pools"],  # type: ignore[arg-type]
            virtual_reserved_rows,
            cache["dedicated_real_start_pools"],  # type: ignore[arg-type]
            int(cache["dedicated_real_rows"]),
            dedicated_real_loss_multiplier,
            cache["periodic_reserved_start_pools"],  # type: ignore[arg-type]
            int(cache["periodic_reserved_rows"]),
            extra_ae,
            extra_mean,
            extra_std,
            extra_ae_loss_weight,
            ae5,
            ae5_mean,
            ae5_std,
            ae5_effective_loss_weight,
            ae6,
            ae6_mean,
            ae6_std,
            ae6_loss_weight,
            ae2,
            ae2_mean,
            ae2_std,
            ae2_loss_weight,
            ae3,
            ae3_mean,
            ae3_std,
            ae3_pos_weight,
            ae3_loss_weight,
            pin_logit_gap_loss_weight,
            inertia_acceleration_loss_weight,
            root_accel_pin_loss_ratio,
            leg_crossing_capsule_loss_weight,
            ae4,
            ae4_input_mean,
            ae4_input_std,
            ae4_target_mean,
            ae4_target_std,
            ae4_loss_weight,
            ae4_bank_pin_loss_weight,
            slide_tentative_loss_weight,
        )
        arm_phase_started = emit_pretrain_arm_timing(
            "build_stepper",
            stepper_started,
            kind=stepper.kind,
            K=int(stage_k),
            batch=int(cache["batch_size"]),
        )
        set_active_stepper(stepper)
        if stage_idx == 0 and step == 0 and wait_for_prearmed_launch():
            start = time.perf_counter()
        print(
            f"stage={stage_idx + 1}/{len(ROLLOUT_SCHEDULE)} K={stage_k} "
            f"steps={stage_global_start}-{stage_global_end} remaining={stage_steps - initial_stage_step} "
            f"batch={int(cache['batch_size'])} real_batch={int(cache['real_batch_size'])} "
            f"dedicated_real_rows={int(cache['dedicated_real_rows'])} "
            f"dedicated_real_loss_x={dedicated_real_loss_multiplier:.3g} "
            f"omni_reserved_rows={int(cache['periodic_reserved_rows'])} "
            f"synthetic_rows={synthetic_reserved_rows} virtual_rows={virtual_reserved_rows} "
            f"virtual_frac={synthetic_batch_fraction:.3g} "
            f"lr={lr:.3g} stepper={stepper.kind}",
            flush=True,
        )
        stage_step = initial_stage_step
        while stage_step < stage_steps:
            if TRAIN_HOT_STOP_REQUEST_EVENT.is_set():
                print("TRAINER_WORKER_TRAINING_STOPPING_HOT", flush=True)
                last = save_controller_checkpoint(
                    run_dir,
                    run_id,
                    "last",
                    model,
                    optimizer,
                    step,
                    last_loss,
                    last_stage_k,
                    cfg,
                    metadata,
                    adaptive_sampler=adaptive_sampler,
                )
                writer.close()
                print(f"saved {last}", flush=True)
                with ACTIVE_STEPPER_LOCK:
                    stepper.reset_to_capture_state()
                model.train()
                TRAIN_HOT_STOP_REQUEST_EVENT.clear()
                TRAIN_STOP_REQUEST_EVENT.clear()
                TRAIN_RESUME_EVENT.clear()
                TRAIN_HOT_STOPPED_EVENT.set()
                clear_active_checkpoint_context()
                print("TRAINER_WORKER_TRAINING_STOPPED_HOT", flush=True)
                while not TRAIN_RESUME_EVENT.wait(0.05):
                    pass
                TRAIN_RESUME_EVENT.clear()
                TRAIN_HOT_STOPPED_EVENT.clear()
                run_id, run_dir, writer, last_loss, best_loss, step, start, timed_interval_seconds = begin_controller_run()
                best_pending_save = False
                next_timed_checkpoint = (
                    start + timed_interval_seconds if timed_interval_seconds > 0.0 else float("inf")
                )
                set_active_checkpoint_context(
                    run_id=run_id,
                    run_dir=run_dir,
                    model=model,
                    optimizer=optimizer,
                    step=step,
                    last_loss=last_loss,
                    last_stage_k=last_stage_k,
                    cfg=cfg,
                    metadata=metadata,
                    adaptive_sampler=adaptive_sampler,
                )
                stage_step = 0
                print("TRAINER_WORKER_TRAINING_RESTARTED", flush=True)
                continue
            if TRAIN_STOP_REQUEST_EVENT.is_set():
                print("TRAINER_WORKER_TRAINING_PAUSED", flush=True)
                while TRAIN_STOP_REQUEST_EVENT.is_set():
                    TRAIN_RESUME_EVENT.wait(0.05)
                TRAIN_RESUME_EVENT.clear()
                print("TRAINER_WORKER_TRAINING_RESUMED", flush=True)
                if TRAIN_HOT_STOP_REQUEST_EVENT.is_set():
                    continue
            stage_step += 1
            step += 1
            if auto_debug_next_index < auto_debug_export_count and step % auto_debug_export_every == 0:
                request_path = debug_rollout_request_path(run_dir)
                if not request_path.exists():
                    request_path.parent.mkdir(parents=True, exist_ok=True)
                    auto_debug_next_index += 1
                    request_payload = {
                        "source": "auto_debug_rollout_export",
                        "index": int(auto_debug_next_index),
                        "count": int(auto_debug_export_count),
                        "step": int(step),
                        "artifact_name": f"noisy_rollout_{auto_debug_next_index:02d}_step{step:06d}.json",
                    }
                    tmp_request_path = request_path.with_suffix(request_path.suffix + ".tmp")
                    tmp_request_path.write_text(json.dumps(request_payload), encoding="utf-8")
                    tmp_request_path.replace(request_path)
            maybe_arm_debug_rollout_snapshot(run_dir, stepper)
            with ACTIVE_STEPPER_LOCK:
                loss_result = stepper.step()
            last_loss = float(loss_result.total.detach().cpu())
            loss_terms = {key: float(value.detach().cpu()) for key, value in loss_result.terms.items()}
            maybe_export_debug_rollout(run_dir, run_id, step, stepper)
            start += wait_for_training_pause_release(run_dir, run_id, step)
            if adaptive_sampler is not None:
                adaptive_sampler.record_batch(
                    getattr(stepper, "clip_ids", torch.empty(0, dtype=torch.long, device=device)),
                    loss_result.row_losses,
                )
                if adaptive_sampler.maybe_update():
                    adaptive_sampler.log_figures(writer, step)
                    writer.flush()
                    coverage_count = int((adaptive_sampler.pick_counts > 0).sum().detach().cpu())
                    prob_max = float(adaptive_sampler.probabilities.max().detach().cpu())
                    print(
                        f"adaptive_sampler_update step={step} ready={int(adaptive_sampler.adaptive_ready)} "
                        f"coverage={coverage_count}/{adaptive_sampler.num_clips} prob_max={prob_max:.6g} "
                        f"pending_rows={float(adaptive_sampler.pending_loss_count.sum().detach().cpu()):.0f} "
                        f"interval_s={adaptive_sampler.update_interval_s:.1f}",
                        flush=True,
                    )
            update_active_checkpoint_context(step=step, last_loss=last_loss, last_stage_k=int(stage_k))
            if not math.isfinite(last_loss):
                print(
                    f"TRAINER_WORKER_NONFINITE_LOSS step={step} train_loss={last_loss} "
                    "stopping_before_checkpoint_save",
                    flush=True,
                )
                stop_training = True
                nonfinite_loss_stop = True
                break
            zero_loss_stop = math.isfinite(last_loss) and last_loss <= float(ZERO_LOSS_STOP_THRESHOLD)
            effective_max_train_seconds = current_max_train_seconds()
            time_budget_stop = (
                effective_max_train_seconds is not None
                and (time.perf_counter() - start) >= float(effective_max_train_seconds)
            )
            if stage_step % LOSS_REFRESH_RATE == 0 or stage_step == 1 or stage_step == stage_steps or zero_loss_stop:
                model.eval()
                mean_err = NAN_METRIC
                max_err = NAN_METRIC
                if RUN_FK_DIAGNOSTIC:
                    mean_err, max_err = rollout_joint_error(model, store, int(stage_k), cache["max_pool"])
                elapsed = time.perf_counter() - start
                stats = cache["rollout_stats"]
                gt_text = (
                    f"gt_mean_m={mean_err:.6f} gt_max_m={max_err:.6f}"
                    if RUN_FK_DIAGNOSTIC
                    else "gt_diag=off"
                )
                ae_text = "disabled"
                if (
                    ae_loss_weight != 0.0
                    or extra_ae_loss_weight != 0.0
                    or ae5_effective_loss_weight != 0.0
                    or ae6_loss_weight != 0.0
                ):
                    ae_parts: list[str] = []
                    if primary_loss_uses_ae1():
                        ae_parts.append(f"ae1w={loss_terms.get(AE_POSE_TERM_NAME, NAN_METRIC):.6g}")
                        ae_parts.append(f"ae1raw={loss_terms.get('ae_score', NAN_METRIC):.6g}")
                    ae_text = " ".join(ae_parts) if ae_parts else "primary=off"
                if primary_loss_uses_gt_mse():
                    ae_text = (
                        f"{ae_text} gtmsew={loss_terms.get(GT_MSE_WEIGHTED_TERM_NAME, NAN_METRIC):.6g} "
                        f"gtmseraw={loss_terms.get(GT_MSE_RAW_TERM_NAME, NAN_METRIC):.6g}"
                    )
                if extra_ae_loss_weight != 0.0:
                    ae_text = f"{ae_text} ae_v={loss_terms.get(AE_VELOCITY_TERM_NAME, NAN_METRIC):.6g}"
                if ae5_effective_loss_weight != 0.0:
                    ae_text = (
                        f"{ae_text} ae5w={loss_terms.get(AE5_WEIGHTED_TERM_NAME, NAN_METRIC):.6g} "
                        f"ae5raw={loss_terms.get(AE5_SCORE_TERM_NAME, NAN_METRIC):.6g} "
                        f"ae5active={loss_terms.get(AE5_ACTIVE_RATE_TERM_NAME, NAN_METRIC):.3f}"
                    )
                if ae6_loss_weight != 0.0:
                    ae_text = (
                        f"{ae_text} ae6w={loss_terms.get(AE6_CONTACT_WEIGHTED_TERM_NAME, NAN_METRIC):.6g} "
                        f"ae6raw={loss_terms.get(AE6_CONTACT_SCORE_TERM_NAME, NAN_METRIC):.6g} "
                        f"ae6mae={loss_terms.get(AE6_CONTACT_MAE_TERM_NAME, NAN_METRIC):.6g} "
                        f"ae6acc={loss_terms.get(AE6_CONTACT_ACC_TERM_NAME, NAN_METRIC):.3f}"
                    )
                if ae2_loss_weight != 0.0:
                    ae_text = f"{ae_text} ae2w={loss_terms.get(AE2_WEIGHTED_TERM_NAME, NAN_METRIC):.6g}"
                if ae3_loss_weight != 0.0:
                    ae_text = f"{ae_text} ae3w={loss_terms.get(AE3_PIN_WEIGHTED_TERM_NAME, NAN_METRIC):.6g}"
                if leg_crossing_capsule_loss_weight != 0.0:
                    ae_text = (
                        f"{ae_text} legcap={loss_terms.get(LEG_CROSSING_CAPSULE_TERM_NAME, NAN_METRIC):.6g} "
                        f"legcap_m={loss_terms.get(LEG_CROSSING_CAPSULE_RAW_TERM_NAME, NAN_METRIC):.6g} "
                        f"legcapbad={loss_terms.get(LEG_CROSSING_CAPSULE_RATE_TERM_NAME, NAN_METRIC):.3f}"
                    )
                if pin_logit_gap_loss_weight != 0.0:
                    ae_text = (
                        f"{ae_text} pingap={loss_terms.get(PIN_LOGIT_GAP_WEIGHTED_TERM_NAME, NAN_METRIC):.6g} "
                        f"pingapraw={loss_terms.get(PIN_LOGIT_GAP_RAW_TERM_NAME, NAN_METRIC):.6g} "
                        f"pingapbad={loss_terms.get(PIN_LOGIT_GAP_BAD_RATE_TERM_NAME, NAN_METRIC):.3f}"
                    )
                if inertia_acceleration_loss_weight != 0.0:
                    ae_text = (
                        f"{ae_text} inertia={loss_terms.get(INERTIA_ACCELERATION_WEIGHTED_TERM_NAME, NAN_METRIC):.6g} "
                        f"inertiaraw={loss_terms.get(INERTIA_ACCELERATION_RAW_TERM_NAME, NAN_METRIC):.6g} "
                        f"inertiabad={loss_terms.get(INERTIA_ACCELERATION_BAD_RATE_TERM_NAME, NAN_METRIC):.3f}"
                    )
                if root_accel_pin_loss_ratio != 0.0:
                    ae_text = (
                        f"{ae_text} rootaccelpin={loss_terms.get(ROOT_ACCEL_PIN_WEIGHTED_TERM_NAME, NAN_METRIC):.6g} "
                        f"rootaccelbad={loss_terms.get(ROOT_ACCEL_PIN_BAD_RATE_TERM_NAME, NAN_METRIC):.3f} "
                        f"rootaccel={loss_terms.get(ROOT_ACCEL_PIN_ACCEL_TERM_NAME, NAN_METRIC):.3f}"
                    )
                if ae4_loss_weight != 0.0:
                    ae_text = (
                        f"{ae_text} ae4w={loss_terms.get(AE4_POSE_WEIGHTED_TERM_NAME, NAN_METRIC):.6g} "
                        f"ae4raw={loss_terms.get(AE4_POSE_SCORE_TERM_NAME, NAN_METRIC):.6g}"
                    )
                if ae4_bank_pin_loss_weight != 0.0:
                    ae_text = (
                        f"{ae_text} ae4pin={loss_terms.get(AE4_BANK_PIN_WEIGHTED_TERM_NAME, NAN_METRIC):.6g} "
                        f"ae4pinraw={loss_terms.get(AE4_BANK_PIN_RAW_TERM_NAME, NAN_METRIC):.6g} "
                        f"ae4pinscale={loss_terms.get(AE4_BANK_PIN_ROOT_SCALE_TERM_NAME, NAN_METRIC):.3f}"
                    )
                identity_text = ""
                if identity_enabled:
                    identity_parts = []
                    if identity_loss_weight != 0.0:
                        identity_parts.append(f"identity_output={loss_terms.get(IDENTITY_TERM_NAME, NAN_METRIC):.6g}")
                    if identity_maxabs_weight != 0.0:
                        identity_parts.append(
                            f"identity_output_maxabs={loss_terms.get(IDENTITY_MAXABS_TERM_NAME, NAN_METRIC):.6g}"
                        )
                    if identity_world_pos_weight != 0.0:
                        identity_parts.append(
                            f"identity_world_pos={loss_terms.get(IDENTITY_WORLD_POS_TERM_NAME, NAN_METRIC):.6g}"
                        )
                    if identity_pelvis_pos_weight != 0.0:
                        identity_parts.append(
                            f"identity_pelvis_pos={loss_terms.get(IDENTITY_PELVIS_POS_TERM_NAME, NAN_METRIC):.6g}"
                        )
                    identity_text = " " + " ".join(identity_parts)
                rl_text = " ".join(f"{name}={loss_terms.get(name, NAN_METRIC):.6g}" for name in rl_cfg.enabled_terms())
                slide_text = ""
                if envelope is not None:
                    slide_text = (
                        f"linear_slide_weighted={loss_terms.get('linear_slide_weighted', NAN_METRIC):.6g} "
                        f"angular_slide_weighted={loss_terms.get('angular_slide_weighted', NAN_METRIC):.6g} "
                        f"foot_height_weighted={loss_terms.get('foot_height_weighted', NAN_METRIC):.6g} "
                    )
                if slide_tentative_loss_weight != 0.0:
                    slide_text = (
                        f"{slide_text}"
                        f"slide_tentative={loss_terms.get(SLIDE_TENTATIVE_TERM_NAME, NAN_METRIC):.6g} "
                        f"slide_tentative_m={loss_terms.get(SLIDE_TENTATIVE_RAW_TERM_NAME, NAN_METRIC):.6g} "
                        f"slide_tentative_pin={loss_terms.get(SLIDE_TENTATIVE_PIN_RATE_TERM_NAME, NAN_METRIC):.3f} "
                    )
                alternating_text = ""
                if alternating_feet_loss_enabled(alternating_feet_weight):
                    alternating_text = (
                        f"alternating_feet_weighted={loss_terms.get('alternating_feet_weighted', NAN_METRIC):.6g} "
                        f"both_feet_rate={loss_terms.get('both_feet_moving_rate', NAN_METRIC):.3f} "
                        f"overlap_mps={loss_terms.get('both_feet_overlap_mps', NAN_METRIC):.3f} "
                    )
                foot_lift_text = ""
                if foot_lift_slide_loss_enabled(foot_lift_slide_weight):
                    lift_move_rate = loss_terms.get("foot_lift_moving_rate", 0.0)
                    lift_clear = loss_terms.get("foot_lift_moving_clearance_m", NAN_METRIC)
                    lift_bound = loss_terms.get("foot_lift_allowed_speed_mps", NAN_METRIC)
                    lift_denom = max(float(lift_move_rate), 1e-8)
                    foot_lift_text = (
                        f"foot_lift_slide_weighted={loss_terms.get('foot_lift_slide_weighted', NAN_METRIC):.6g} "
                        f"lift_violate={loss_terms.get('foot_lift_slide_violation_rate', NAN_METRIC):.3f} "
                        f"lift_move_rate={lift_move_rate:.3f} "
                        f"lift_clear_m={lift_clear / lift_denom:.3f} "
                        f"lift_bound_mps={lift_bound / lift_denom:.3f} "
                    )
                grounded_text = ""
                if foot_lift_slide_loss_enabled(foot_lift_slide_weight):
                    grounded_rate = loss_terms.get("grounded_foot_slide_rate", 0.0)
                    grounded_speed = loss_terms.get("grounded_foot_slide_mps", NAN_METRIC)
                    grounded_clear = loss_terms.get("grounded_foot_clearance_m", NAN_METRIC)
                    grounded_denom = max(float(grounded_rate), 1e-8)
                    grounded_text = (
                        f"grounded_slide_weighted={loss_terms.get('grounded_foot_slide_weighted', NAN_METRIC):.6g} "
                        f"grounded_rate={grounded_rate:.3f} "
                        f"grounded_mps={grounded_speed / grounded_denom:.3f} "
                        f"grounded_clear_m={grounded_clear / grounded_denom:.3f} "
                    )
                foot_style_text = ""
                if foot_lift_slide_loss_enabled(foot_lift_slide_weight):
                    deadzone_rate = loss_terms.get("foot_speed_deadzone_rate", 0.0)
                    deadzone_denom = max(float(deadzone_rate), 1e-8)
                    overspeed_rate = loss_terms.get("foot_speed_overspeed_rate", 0.0)
                    overspeed_denom = max(float(overspeed_rate), 1e-8)
                    terminal_rate = loss_terms.get("terminal_foot_stillness_rate", 0.0)
                    terminal_denom = max(float(terminal_rate), 1e-8)
                    foot_style_text = (
                        f"deadzone_weighted={loss_terms.get('foot_speed_deadzone_weighted', NAN_METRIC):.6g} "
                        f"deadzone_rate={deadzone_rate:.3f} "
                        f"deadzone_mps={loss_terms.get('foot_speed_deadzone_mps', NAN_METRIC) / deadzone_denom:.3f} "
                        f"overspeed_weighted={loss_terms.get('foot_speed_overspeed_weighted', NAN_METRIC):.6g} "
                        f"overspeed_rate={overspeed_rate:.3f} "
                        f"overspeed_mps={loss_terms.get('foot_speed_overspeed_mps', NAN_METRIC) / overspeed_denom:.3f} "
                        f"terminal_still_weighted={loss_terms.get('terminal_foot_stillness_weighted', NAN_METRIC):.6g} "
                        f"terminal_h_mps={loss_terms.get('terminal_foot_horizontal_mps', NAN_METRIC) / terminal_denom:.3f} "
                        f"terminal_v_mps={loss_terms.get('terminal_foot_vertical_mps', NAN_METRIC) / terminal_denom:.3f} "
                    )
                anatomy_text = ""
                if ik_lower_length_loss_enabled():
                    anatomy_text = (
                        f"ik_lower_len_weighted={loss_terms.get('ik_lower_length_weighted', NAN_METRIC):.6g} "
                        f"leg_len_excess_m={loss_terms.get('leg_lower_length_excess_m', NAN_METRIC):.4f} "
                        f"leg_len_bad={loss_terms.get('leg_lower_length_bad_rate', NAN_METRIC):.3f} "
                    )
                foot_contact_text = (
                    f"foot_contact_height_weighted={loss_terms.get(FOOT_CONTACT_HEIGHT_LOSS_TERM_NAME, NAN_METRIC):.6g} "
                    f"foot_unpin_penalty={loss_terms.get(FOOT_UNPIN_PENALTY_TERM_NAME, NAN_METRIC):.6g} "
                    f"soft_unpin={loss_terms.get(FOOT_UNPIN_SOFT_RATE_TERM_NAME, NAN_METRIC):.3f} "
                    f"pin_intent={loss_terms.get(PINNED_FOOT_INTENT_TERM_NAME, NAN_METRIC):.6g} "
                    f"pin_intent_mps={loss_terms.get(PINNED_FOOT_INTENT_MPS_TERM_NAME, NAN_METRIC):.3f} "
                    f"pinned_h={loss_terms.get(PINNED_FOOT_HEIGHT_TERM_NAME, NAN_METRIC):.6g} "
                    f"pinned_h_m={loss_terms.get(PINNED_FOOT_HEIGHT_RAW_TERM_NAME, NAN_METRIC):.6g} "
                    f"pinned_h_max_m={loss_terms.get(PINNED_FOOT_HEIGHT_MAX_TERM_NAME, NAN_METRIC):.6g} "
                    f"idle_flat={loss_terms.get(IDLE_FOOT_FLATNESS_TERM_NAME, NAN_METRIC):.6g} "
                    f"idle_flat_m={loss_terms.get(IDLE_FOOT_FLATNESS_RAW_TERM_NAME, NAN_METRIC):.6g} "
                    f"idle_flat_max_m={loss_terms.get(IDLE_FOOT_FLATNESS_MAX_TERM_NAME, NAN_METRIC):.6g} "
                    f"min_foot_h={loss_terms.get('foot_contact_min_height_m', NAN_METRIC):.6g} "
                    f"any_pin={loss_terms.get('foot_contact_any_pinned_rate', NAN_METRIC):.3f} "
                )
                print(
                    f"step={step:05d} K={stage_k} train_loss={last_loss:.6g} "
                    f"ae={ae_text}{identity_text} "
                    f"{rl_text} "
                    f"{slide_text}"
                    f"{alternating_text}"
                    f"{foot_lift_text}"
                    f"{grounded_text}"
                    f"{foot_style_text}"
                    f"{anatomy_text}"
                    f"{foot_contact_text}"
                    f"{gt_text} effK_mean={stats['effective_k_mean']:.2f} lr={lr:.3g} elapsed_s={elapsed:.1f}",
                    flush=True,
                )
                if stage_step % LOG_EVERY != 0 and stage_step != stage_steps and not zero_loss_stop:
                    model.train()
                    continue
                if last_loss < best_loss:
                    best_loss = last_loss
                    best_pending_save = True
                force_checkpoint_save = bool(stage_step == stage_steps or zero_loss_stop or time_budget_stop)
                save_interval = max(0, int(getattr(cfg, "save_last_every_epochs", 0)))
                should_save_latest = force_checkpoint_save or save_interval <= 0 or stage_step % save_interval == 0
                latest: Path | None = None
                if should_save_latest:
                    latest = save_controller_checkpoint(
                        run_dir,
                        run_id,
                        "latest",
                        model,
                        optimizer,
                        step,
                        last_loss,
                        int(stage_k),
                        cfg,
                        metadata,
                        adaptive_sampler=adaptive_sampler,
                    )
                now = time.perf_counter()
                should_save_temp = timed_interval_seconds > 0.0 and now >= next_timed_checkpoint
                if should_save_temp:
                    timed_tag = time.strftime("t%m%d_%H%M%S", time.localtime())
                    temp = save_controller_checkpoint(
                        run_dir,
                        run_id,
                        f"{timed_tag}_s{step:07d}",
                        model,
                        optimizer,
                        step,
                        last_loss,
                        int(stage_k),
                        cfg,
                        metadata,
                        adaptive_sampler=adaptive_sampler,
                    )
                    print(f"saved timed checkpoint {temp}", flush=True)
                    while next_timed_checkpoint <= now:
                        next_timed_checkpoint += timed_interval_seconds
                if best_pending_save and should_save_latest:
                    save_controller_checkpoint(
                        run_dir,
                        run_id,
                        "best",
                        model,
                        optimizer,
                        step,
                        best_loss,
                        int(stage_k),
                        cfg,
                        metadata,
                        adaptive_sampler=adaptive_sampler,
                    )
                    best_pending_save = False
                writer.add_scalar("loss/train_total", last_loss, step)
                if ae_loss_weight != 0.0 or extra_ae_loss_weight != 0.0:
                    ae1_weighted_value = loss_terms.get(AE_POSE_TERM_NAME, NAN_METRIC)
                    writer.add_scalar("loss/ae_score", ae1_weighted_value, step)
                    if primary_loss_uses_ae1():
                        writer.add_scalar("loss/ae1_weighted", ae1_weighted_value, step)
                        writer.add_scalar("metrics/ae_score_raw", loss_terms.get("ae_score", NAN_METRIC), step)
                    if primary_loss_uses_gt_mse():
                        writer.add_scalar(
                            f"loss/{GT_MSE_WEIGHTED_TERM_NAME}",
                            loss_terms.get(GT_MSE_WEIGHTED_TERM_NAME, NAN_METRIC),
                            step,
                        )
                        writer.add_scalar(f"metrics/{GT_MSE_RAW_TERM_NAME}", loss_terms.get(GT_MSE_RAW_TERM_NAME, NAN_METRIC), step)
                        writer.add_scalar(f"metrics/{GT_MSE_POS_TERM_NAME}", loss_terms.get(GT_MSE_POS_TERM_NAME, NAN_METRIC), step)
                        writer.add_scalar(f"metrics/{GT_MSE_ROT_TERM_NAME}", loss_terms.get(GT_MSE_ROT_TERM_NAME, NAN_METRIC), step)
                        writer.add_scalar(f"metrics/{GT_MSE_LINVEL_TERM_NAME}", loss_terms.get(GT_MSE_LINVEL_TERM_NAME, NAN_METRIC), step)
                        writer.add_scalar(f"metrics/{GT_MSE_ANGVEL_TERM_NAME}", loss_terms.get(GT_MSE_ANGVEL_TERM_NAME, NAN_METRIC), step)
                if extra_ae_loss_weight != 0.0:
                    writer.add_scalar("loss/ae_v_score", loss_terms.get(AE_VELOCITY_TERM_NAME, NAN_METRIC), step)
                if ae5_effective_loss_weight != 0.0:
                    writer.add_scalar(f"loss/{AE5_WEIGHTED_TERM_NAME}", loss_terms.get(AE5_WEIGHTED_TERM_NAME, NAN_METRIC), step)
                    writer.add_scalar(f"metrics/{AE5_SCORE_TERM_NAME}", loss_terms.get(AE5_SCORE_TERM_NAME, NAN_METRIC), step)
                    writer.add_scalar(f"metrics/{AE5_ACTIVE_RATE_TERM_NAME}", loss_terms.get(AE5_ACTIVE_RATE_TERM_NAME, NAN_METRIC), step)
                if ae6_loss_weight != 0.0:
                    writer.add_scalar(
                        f"loss/{AE6_CONTACT_WEIGHTED_TERM_NAME}",
                        loss_terms.get(AE6_CONTACT_WEIGHTED_TERM_NAME, NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        f"metrics/{AE6_CONTACT_SCORE_TERM_NAME}",
                        loss_terms.get(AE6_CONTACT_SCORE_TERM_NAME, NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        f"metrics/{AE6_CONTACT_MAE_TERM_NAME}",
                        loss_terms.get(AE6_CONTACT_MAE_TERM_NAME, NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        f"metrics/{AE6_CONTACT_ACC_TERM_NAME}",
                        loss_terms.get(AE6_CONTACT_ACC_TERM_NAME, NAN_METRIC),
                        step,
                    )
                if ae2_loss_weight != 0.0:
                    writer.add_scalar("loss/ae2_score_weighted", loss_terms.get(AE2_WEIGHTED_TERM_NAME, NAN_METRIC), step)
                if ae3_loss_weight != 0.0:
                    writer.add_scalar("loss/ae3_pin_score_weighted", loss_terms.get(AE3_PIN_WEIGHTED_TERM_NAME, NAN_METRIC), step)
                if leg_crossing_capsule_loss_weight != 0.0:
                    writer.add_scalar(
                        f"loss/{LEG_CROSSING_CAPSULE_TERM_NAME}",
                        loss_terms.get(LEG_CROSSING_CAPSULE_TERM_NAME, NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        f"metrics/{LEG_CROSSING_CAPSULE_RAW_TERM_NAME}",
                        loss_terms.get(LEG_CROSSING_CAPSULE_RAW_TERM_NAME, NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        f"metrics/{LEG_CROSSING_CAPSULE_RATE_TERM_NAME}",
                        loss_terms.get(LEG_CROSSING_CAPSULE_RATE_TERM_NAME, NAN_METRIC),
                        step,
                    )
                if pin_logit_gap_loss_weight != 0.0:
                    writer.add_scalar(
                        f"loss/{PIN_LOGIT_GAP_WEIGHTED_TERM_NAME}",
                        loss_terms.get(PIN_LOGIT_GAP_WEIGHTED_TERM_NAME, NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        f"metrics/{PIN_LOGIT_GAP_RAW_TERM_NAME}",
                        loss_terms.get(PIN_LOGIT_GAP_RAW_TERM_NAME, NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        f"metrics/{PIN_LOGIT_GAP_BAD_RATE_TERM_NAME}",
                        loss_terms.get(PIN_LOGIT_GAP_BAD_RATE_TERM_NAME, NAN_METRIC),
                        step,
                    )
                if inertia_acceleration_loss_weight != 0.0:
                    writer.add_scalar(
                        f"loss/{INERTIA_ACCELERATION_WEIGHTED_TERM_NAME}",
                        loss_terms.get(INERTIA_ACCELERATION_WEIGHTED_TERM_NAME, NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        f"metrics/{INERTIA_ACCELERATION_RAW_TERM_NAME}",
                        loss_terms.get(INERTIA_ACCELERATION_RAW_TERM_NAME, NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        f"metrics/{INERTIA_LINEAR_ACCELERATION_RAW_TERM_NAME}",
                        loss_terms.get(INERTIA_LINEAR_ACCELERATION_RAW_TERM_NAME, NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        f"metrics/{INERTIA_ANGULAR_ACCELERATION_RAW_TERM_NAME}",
                        loss_terms.get(INERTIA_ANGULAR_ACCELERATION_RAW_TERM_NAME, NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        f"metrics/{INERTIA_ACCELERATION_BAD_RATE_TERM_NAME}",
                        loss_terms.get(INERTIA_ACCELERATION_BAD_RATE_TERM_NAME, NAN_METRIC),
                        step,
                    )
                if root_accel_pin_loss_ratio != 0.0:
                    writer.add_scalar(
                        f"loss/{ROOT_ACCEL_PIN_WEIGHTED_TERM_NAME}",
                        loss_terms.get(ROOT_ACCEL_PIN_WEIGHTED_TERM_NAME, NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        f"metrics/{ROOT_ACCEL_PIN_RAW_TERM_NAME}",
                        loss_terms.get(ROOT_ACCEL_PIN_RAW_TERM_NAME, NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        f"metrics/{ROOT_ACCEL_PIN_SCALE_TERM_NAME}",
                        loss_terms.get(ROOT_ACCEL_PIN_SCALE_TERM_NAME, NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        f"metrics/{ROOT_ACCEL_PIN_ACCEL_TERM_NAME}",
                        loss_terms.get(ROOT_ACCEL_PIN_ACCEL_TERM_NAME, NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        f"metrics/{ROOT_ACCEL_PIN_ACTIVE_RATE_TERM_NAME}",
                        loss_terms.get(ROOT_ACCEL_PIN_ACTIVE_RATE_TERM_NAME, NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        f"metrics/{ROOT_ACCEL_PIN_BAD_RATE_TERM_NAME}",
                        loss_terms.get(ROOT_ACCEL_PIN_BAD_RATE_TERM_NAME, NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        f"metrics/{ROOT_ACCEL_PIN_MAX_PROB_TERM_NAME}",
                        loss_terms.get(ROOT_ACCEL_PIN_MAX_PROB_TERM_NAME, NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        f"metrics/{ROOT_ACCEL_PIN_HEIGHT_TERM_NAME}",
                        loss_terms.get(ROOT_ACCEL_PIN_HEIGHT_TERM_NAME, NAN_METRIC),
                        step,
                    )
                if ae4_loss_weight != 0.0:
                    writer.add_scalar("loss/ae4_pose_score_weighted", loss_terms.get(AE4_POSE_WEIGHTED_TERM_NAME, NAN_METRIC), step)
                    writer.add_scalar("metrics/ae4_pose_score", loss_terms.get(AE4_POSE_SCORE_TERM_NAME, NAN_METRIC), step)
                    writer.add_scalar("metrics/ae4_pose_hinge", loss_terms.get(AE4_POSE_HINGE_TERM_NAME, NAN_METRIC), step)
                if ae4_bank_pin_loss_weight != 0.0:
                    writer.add_scalar(
                        "loss/ae4_bank_pin_score_weighted",
                        loss_terms.get(AE4_BANK_PIN_WEIGHTED_TERM_NAME, NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "metrics/ae4_bank_pin_mistake_prob",
                        loss_terms.get(AE4_BANK_PIN_RAW_TERM_NAME, NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "metrics/ae4_bank_pin_root_scale",
                        loss_terms.get(AE4_BANK_PIN_ROOT_SCALE_TERM_NAME, NAN_METRIC),
                        step,
                    )
                if identity_loss_weight != 0.0:
                    writer.add_scalar("loss/identity_output", loss_terms.get(IDENTITY_TERM_NAME, NAN_METRIC), step)
                if identity_maxabs_weight != 0.0:
                    writer.add_scalar(
                        "loss/identity_output_maxabs", loss_terms.get(IDENTITY_MAXABS_TERM_NAME, NAN_METRIC), step
                    )
                if identity_world_pos_weight != 0.0:
                    writer.add_scalar(
                        "loss/identity_world_pos", loss_terms.get(IDENTITY_WORLD_POS_TERM_NAME, NAN_METRIC), step
                    )
                if identity_pelvis_pos_weight != 0.0:
                    writer.add_scalar(
                        "loss/identity_pelvis_pos", loss_terms.get(IDENTITY_PELVIS_POS_TERM_NAME, NAN_METRIC), step
                    )
                for name in PIN_BEHAVIOR_TERM_NAMES:
                    writer.add_scalar(f"metrics/{name}", loss_terms.get(name, NAN_METRIC), step)
                writer.add_scalar(
                    f"loss/{FOOT_CONTACT_HEIGHT_LOSS_TERM_NAME}",
                    loss_terms.get(FOOT_CONTACT_HEIGHT_LOSS_TERM_NAME, NAN_METRIC),
                    step,
                )
                writer.add_scalar(
                    f"loss/{FOOT_UNPIN_PENALTY_TERM_NAME}",
                    loss_terms.get(FOOT_UNPIN_PENALTY_TERM_NAME, NAN_METRIC),
                    step,
                )
                writer.add_scalar(
                    f"metrics/{FOOT_UNPIN_SOFT_RATE_TERM_NAME}",
                    loss_terms.get(FOOT_UNPIN_SOFT_RATE_TERM_NAME, NAN_METRIC),
                    step,
                )
                writer.add_scalar(
                    f"loss/{PINNED_FOOT_INTENT_TERM_NAME}",
                    loss_terms.get(PINNED_FOOT_INTENT_TERM_NAME, NAN_METRIC),
                    step,
                )
                writer.add_scalar(
                    f"metrics/{PINNED_FOOT_INTENT_RAW_TERM_NAME}",
                    loss_terms.get(PINNED_FOOT_INTENT_RAW_TERM_NAME, NAN_METRIC),
                    step,
                )
                writer.add_scalar(
                    f"metrics/{PINNED_FOOT_INTENT_MPS_TERM_NAME}",
                    loss_terms.get(PINNED_FOOT_INTENT_MPS_TERM_NAME, NAN_METRIC),
                    step,
                )
                if slide_tentative_loss_weight != 0.0:
                    writer.add_scalar(
                        f"loss/{SLIDE_TENTATIVE_TERM_NAME}",
                        loss_terms.get(SLIDE_TENTATIVE_TERM_NAME, NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        f"metrics/{SLIDE_TENTATIVE_RAW_TERM_NAME}",
                        loss_terms.get(SLIDE_TENTATIVE_RAW_TERM_NAME, NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        f"metrics/{SLIDE_TENTATIVE_PIN_RATE_TERM_NAME}",
                        loss_terms.get(SLIDE_TENTATIVE_PIN_RATE_TERM_NAME, NAN_METRIC),
                        step,
                    )
                writer.add_scalar(
                    f"loss/{PINNED_FOOT_HEIGHT_TERM_NAME}",
                    loss_terms.get(PINNED_FOOT_HEIGHT_TERM_NAME, NAN_METRIC),
                    step,
                )
                writer.add_scalar(
                    f"metrics/{PINNED_FOOT_HEIGHT_RAW_TERM_NAME}",
                    loss_terms.get(PINNED_FOOT_HEIGHT_RAW_TERM_NAME, NAN_METRIC),
                    step,
                )
                writer.add_scalar(
                    f"metrics/{PINNED_FOOT_HEIGHT_MAX_TERM_NAME}",
                    loss_terms.get(PINNED_FOOT_HEIGHT_MAX_TERM_NAME, NAN_METRIC),
                    step,
                )
                writer.add_scalar(
                    f"loss/{IDLE_FOOT_FLATNESS_TERM_NAME}",
                    loss_terms.get(IDLE_FOOT_FLATNESS_TERM_NAME, NAN_METRIC),
                    step,
                )
                writer.add_scalar(
                    f"metrics/{IDLE_FOOT_FLATNESS_RAW_TERM_NAME}",
                    loss_terms.get(IDLE_FOOT_FLATNESS_RAW_TERM_NAME, NAN_METRIC),
                    step,
                )
                writer.add_scalar(
                    f"metrics/{IDLE_FOOT_FLATNESS_MAX_TERM_NAME}",
                    loss_terms.get(IDLE_FOOT_FLATNESS_MAX_TERM_NAME, NAN_METRIC),
                    step,
                )
                for name in FOOT_CONTACT_HEIGHT_METRIC_NAMES:
                    writer.add_scalar(f"metrics/{name}", loss_terms.get(name, NAN_METRIC), step)
                for name in rl_cfg.enabled_terms():
                    writer.add_scalar(f"loss/{name}", loss_terms.get(name, NAN_METRIC), step)
                if envelope is not None:
                    writer.add_scalar("loss/linear_slide_weighted", loss_terms.get("linear_slide_weighted", NAN_METRIC), step)
                    writer.add_scalar("loss/angular_slide_weighted", loss_terms.get("angular_slide_weighted", NAN_METRIC), step)
                    writer.add_scalar("loss/foot_height_weighted", loss_terms.get("foot_height_weighted", NAN_METRIC), step)
                if alternating_feet_loss_enabled(alternating_feet_weight):
                    writer.add_scalar(
                        "loss/alternating_feet_weighted",
                        loss_terms.get("alternating_feet_weighted", NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "metrics/both_feet_moving_rate",
                        loss_terms.get("both_feet_moving_rate", NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "metrics/both_feet_overlap_mps",
                        loss_terms.get("both_feet_overlap_mps", NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "metrics/root_still_gate",
                        loss_terms.get("root_still_gate", NAN_METRIC),
                        step,
                    )
                if foot_lift_slide_loss_enabled(foot_lift_slide_weight):
                    writer.add_scalar(
                        "loss/foot_lift_slide_weighted",
                        loss_terms.get("foot_lift_slide_weighted", NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "metrics/foot_lift_slide_violation_rate",
                        loss_terms.get("foot_lift_slide_violation_rate", NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "metrics/foot_lift_slide_excess_mps",
                        loss_terms.get("foot_lift_slide_excess_mps", NAN_METRIC),
                        step,
                    )
                    lift_move_rate = loss_terms.get("foot_lift_moving_rate", NAN_METRIC)
                    writer.add_scalar("metrics/foot_lift_moving_rate", lift_move_rate, step)
                    writer.add_scalar(
                        "metrics/foot_lift_moving_clearance_m",
                        loss_terms.get("foot_lift_moving_clearance_m", NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "metrics/foot_lift_allowed_speed_mps",
                        loss_terms.get("foot_lift_allowed_speed_mps", NAN_METRIC),
                        step,
                    )
                    lift_denom = max(float(lift_move_rate), 1e-8) if math.isfinite(float(lift_move_rate)) else 1e-8
                    writer.add_scalar(
                        "metrics/foot_lift_clearance_when_moving_m",
                        loss_terms.get("foot_lift_moving_clearance_m", NAN_METRIC) / lift_denom,
                        step,
                    )
                    writer.add_scalar(
                        "metrics/foot_lift_allowed_speed_when_moving_mps",
                        loss_terms.get("foot_lift_allowed_speed_mps", NAN_METRIC) / lift_denom,
                        step,
                    )
                    writer.add_scalar(
                        "metrics/foot_lift_root_still_gate",
                        loss_terms.get("foot_lift_root_still_gate", NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "loss/grounded_foot_slide_weighted",
                        loss_terms.get("grounded_foot_slide_weighted", NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "metrics/grounded_foot_slide_rate",
                        loss_terms.get("grounded_foot_slide_rate", NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "metrics/grounded_foot_slide_mps",
                        loss_terms.get("grounded_foot_slide_mps", NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "metrics/grounded_foot_clearance_m",
                        loss_terms.get("grounded_foot_clearance_m", NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "loss/foot_speed_deadzone_weighted",
                        loss_terms.get("foot_speed_deadzone_weighted", NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "metrics/foot_speed_deadzone_rate",
                        loss_terms.get("foot_speed_deadzone_rate", NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "metrics/foot_speed_deadzone_mps",
                        loss_terms.get("foot_speed_deadzone_mps", NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "loss/foot_speed_overspeed_weighted",
                        loss_terms.get("foot_speed_overspeed_weighted", NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "metrics/foot_speed_overspeed_rate",
                        loss_terms.get("foot_speed_overspeed_rate", NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "metrics/foot_speed_overspeed_mps",
                        loss_terms.get("foot_speed_overspeed_mps", NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "loss/terminal_foot_stillness_weighted",
                        loss_terms.get("terminal_foot_stillness_weighted", NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "metrics/terminal_foot_horizontal_mps",
                        loss_terms.get("terminal_foot_horizontal_mps", NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "metrics/terminal_foot_vertical_mps",
                        loss_terms.get("terminal_foot_vertical_mps", NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "metrics/terminal_foot_stillness_rate",
                        loss_terms.get("terminal_foot_stillness_rate", NAN_METRIC),
                        step,
                    )
                if ik_lower_length_loss_enabled():
                    writer.add_scalar(
                        "loss/ik_lower_length_weighted",
                        loss_terms.get("ik_lower_length_weighted", NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "metrics/leg_lower_length_excess_m",
                        loss_terms.get("leg_lower_length_excess_m", NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "metrics/leg_lower_length_bad_rate",
                        loss_terms.get("leg_lower_length_bad_rate", NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "metrics/leg_lower_length_max_excess_m",
                        loss_terms.get("leg_lower_length_max_excess_m", NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "metrics/arm_lower_length_excess_m",
                        loss_terms.get("arm_lower_length_excess_m", NAN_METRIC),
                        step,
                    )
                    writer.add_scalar(
                        "metrics/arm_lower_length_bad_rate",
                        loss_terms.get("arm_lower_length_bad_rate", NAN_METRIC),
                        step,
                    )
                debug_loss_term_names = {
                    "ae_score",
                    GT_MSE_RAW_TERM_NAME,
                    GT_MSE_POS_TERM_NAME,
                    GT_MSE_ROT_TERM_NAME,
                    GT_MSE_LINVEL_TERM_NAME,
                    GT_MSE_ANGVEL_TERM_NAME,
                    AE_VELOCITY_TERM_NAME,
                    AE2_WEIGHTED_TERM_NAME,
                    AE3_PIN_WEIGHTED_TERM_NAME,
                    AE4_POSE_SCORE_TERM_NAME,
                    AE4_POSE_HINGE_TERM_NAME,
                    AE4_POSE_WEIGHTED_TERM_NAME,
                    AE4_BANK_PIN_WEIGHTED_TERM_NAME,
                    AE4_BANK_PIN_RAW_TERM_NAME,
                    AE4_BANK_PIN_ROOT_SCALE_TERM_NAME,
                    IDENTITY_TERM_NAME,
                    IDENTITY_MAXABS_TERM_NAME,
                    IDENTITY_WORLD_POS_TERM_NAME,
                    IDENTITY_PELVIS_POS_TERM_NAME,
                    *rl_cfg.enabled_terms(),
                }
                for term_name, term_value in loss_terms.items():
                    if term_name not in debug_loss_term_names and not term_name.endswith("_weighted"):
                        continue
                    if math.isfinite(term_value) and abs(term_value) > 1e-12:
                        writer.add_scalar(f"loss_terms/{term_name}", term_value, step)
                if RUN_FK_DIAGNOSTIC:
                    writer.add_scalar("eval/rollout_mean_m", mean_err, step)
                    writer.add_scalar("eval/rollout_max_m", max_err, step)
                writer.add_scalar("curriculum/rollout_k", int(stage_k), step)
                writer.add_scalar("curriculum/effective_rollout_k_mean", stats["effective_k_mean"], step)
                writer.add_scalar("curriculum/effective_rollout_k_max", stats["effective_k_max"], step)
                writer.add_scalar("time/elapsed_s", elapsed, step)
                flush_interval = max(0, int(getattr(cfg, "writer_flush_every_epochs", 0)))
                should_flush_writer = force_checkpoint_save or flush_interval <= 0 or stage_step % flush_interval == 0
                if should_flush_writer:
                    writer.flush()
                if latest is not None:
                    print(f"checkpoint_latest={latest}", flush=True)
                model.train()
            if zero_loss_stop:
                stop_training = True
                wake_on_zero_loss(run_id, step, last_loss)
                break
            if time_budget_stop:
                stop_training = True
                print(
                    f"TRAINER_WORKER_TIME_BUDGET_REACHED elapsed_s={time.perf_counter() - start:.1f} "
                    f"limit_s={float(effective_max_train_seconds):.1f}",
                    flush=True,
                )
                break
        if nonfinite_loss_stop:
            print("TRAINER_WORKER_NONFINITE_LOSS_SKIPPED_STAGE_CHECKPOINT", flush=True)
        else:
            stage_path = save_controller_checkpoint(
                run_dir,
                run_id,
                f"stage_K{int(stage_k)}",
                model,
                optimizer,
                step,
                last_loss,
                int(stage_k),
                cfg,
                metadata,
                adaptive_sampler=adaptive_sampler,
            )
            print(f"saved stage checkpoint {stage_path}", flush=True)
        clear_active_stepper(stepper)
        del stepper
        if stop_training:
            break

    if nonfinite_loss_stop:
        writer.close()
        print("TRAINER_WORKER_NONFINITE_LOSS_SKIPPED_FINAL_CHECKPOINT", flush=True)
        clear_active_checkpoint_context()
        return
    last = save_controller_checkpoint(
        run_dir,
        run_id,
        "last",
        model,
        optimizer,
        step,
        last_loss,
        last_stage_k,
        cfg,
        metadata,
        adaptive_sampler=adaptive_sampler,
    )
    writer.close()
    print(f"saved {last}", flush=True)
    clear_active_checkpoint_context()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        write_training_failure_marker(traceback.format_exc(), error_type=type(exc).__name__)
        raise
