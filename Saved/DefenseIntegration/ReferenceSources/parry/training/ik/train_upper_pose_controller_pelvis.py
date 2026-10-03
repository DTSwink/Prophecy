from __future__ import annotations

"""Train the upper+pelvis locomotion controller against vanilla running-style AE1.

The agent contract is 281 -> 99: the existing 90 upper-pose values followed
by pelvis position3+rotation6.  Feet come only from the frozen lower agent.
Every proposal is decoded with the direct, unclamped, pole-preserving leg IK,
then AE1 scores the resulting 171D physical transition in a two-row window.
"""

import argparse
import gc
import hashlib
import json
import math
import os
import shutil
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import torch
import numpy as np
from torch.utils.tensorboard import SummaryWriter

try:
    from .bootstrap import PROJECT_ROOT, ensure_paths
    from . import ik_core as tl
    from . import train_simple_ae_controller as lower_ctl
    from .train_simple_autoencoder import SimpleAEConfig, SimpleAutoencoder
    from . import train_upper_pose_autoencoder as upper_data
    from . import train_upper_pose_controller as runtime_data
    from . import train_upper_pose_root_simple_ae1 as ae_data
    from . import train_upper_pelvis_root_ae22 as ae22_data
    from . import train_upper_pose_ae4 as ae4_data
    from . import upper_pose_pelvis_contract as contract
    from . import upper_cached_lower as cached_lower_data
    from . import visualize
except ImportError:
    from bootstrap import PROJECT_ROOT, ensure_paths
    import ik_core as tl
    import train_simple_ae_controller as lower_ctl
    from train_simple_autoencoder import SimpleAEConfig, SimpleAutoencoder
    import train_upper_pose_autoencoder as upper_data
    import train_upper_pose_controller as runtime_data
    import train_upper_pose_root_simple_ae1 as ae_data
    import train_upper_pelvis_root_ae22 as ae22_data
    import train_upper_pose_ae4 as ae4_data
    import upper_pose_pelvis_contract as contract
    import upper_cached_lower as cached_lower_data
    import visualize


ensure_paths()

HERE = PROJECT_ROOT / "training" / "ik"
RUNS_ROOT = PROJECT_ROOT / "training" / "runs"
AE_POINTER = HERE / "official_upper_pose_pelvis_ae1.json"
CONTROLLER_KIND = "upper_pose_pelvis_vanilla_ae1_controller"
CACHED_LOWER_CONTROLLER_KIND = "upper_pose_cached_lower_vanilla_ae1_controller"
INPUT_DIM = upper_data.INPUT_DIM
OUTPUT_DIM = contract.AGENT_OUTPUT_DIM
ROW_DIM = INPUT_DIM + contract.PHYSICAL_DIM
WINDOW_DIM = ROW_DIM * 2
NEWEST_OUTPUT_START = ROW_DIM + INPUT_DIM
NEWEST_OUTPUT_END = NEWEST_OUTPUT_START + contract.PHYSICAL_DIM
AE4_LOSS_WEIGHT = 10.0
AE4_NON_HAND_ROTATION_WEIGHT = 5.0
AE4_NECK_HEAD_ROTATION_WEIGHT = 15.0
AE4_NON_HAND_ROTATION_DEADZONE_DEG = 5.0
AE4_NECK_HEAD_BONES = ("neck_01", "neck_02", "head")
AE4_NON_HAND_BONES = tuple(
    bone for bone in ae4_data.UPPER_TARGET_BONES if bone not in {"hand_l", "hand_r"}
)
AE4_NECK_HEAD_NON_HAND_START = AE4_NON_HAND_BONES.index(AE4_NECK_HEAD_BONES[0])
AE4_NECK_HEAD_NON_HAND_END = AE4_NECK_HEAD_NON_HAND_START + len(AE4_NECK_HEAD_BONES)
if (
    AE4_NON_HAND_BONES[
        AE4_NECK_HEAD_NON_HAND_START:AE4_NECK_HEAD_NON_HAND_END
    ]
    != AE4_NECK_HEAD_BONES
):
    raise RuntimeError("AE4 neck/head bones must remain contiguous in the loss layout")
RANDOM_INITIAL_GAZE_FRACTION_PER_NOISE_CLASS = 0.5
AE_TEMPORAL_BLEND_END_FRAME = 32
AE_TEMPORAL_BLEND_AE1_START = 0.2
AE_TEMPORAL_BLEND_AE1_END = 0.5
_EXTERNAL_VIEWER_LOWER_CACHE: dict[
    tuple[str, int, int, str, str], dict[str, Any]
] = {}


def ae4_rotation_loss_contract() -> dict[str, Any]:
    return {
        "hands": "unchanged_normalized_6d_rotation_mse",
        "non_hand_bones": "true_root_local_geodesic_angle",
        "deadzone_degrees": AE4_NON_HAND_ROTATION_DEADZONE_DEG,
        "ordinary_non_hand_weight_after_deadzone": AE4_NON_HAND_ROTATION_WEIGHT,
        "neck_head_bones": list(AE4_NECK_HEAD_BONES),
        "neck_head_weight_after_deadzone": AE4_NECK_HEAD_ROTATION_WEIGHT,
        "formula": (
            "ordinary non-hand: 5 * max(angle_radians - radians(5), 0); "
            "neck_01/neck_02/head: 15 * max(angle_radians - radians(5), 0)"
        ),
        "positions": "unchanged_normalized_mse",
    }


def ae1_ae4_temporal_blend_contract(enabled: bool) -> dict[str, Any]:
    return {
        "enabled": bool(enabled),
        "frame_zero": {
            "ae1": AE_TEMPORAL_BLEND_AE1_START,
            "ae4": 1.0 - AE_TEMPORAL_BLEND_AE1_START,
        },
        "frame_32": {
            "ae1": AE_TEMPORAL_BLEND_AE1_END,
            "ae4": 1.0 - AE_TEMPORAL_BLEND_AE1_END,
        },
        "interpolation": "linear_by_predicted_frame_index",
        "scored_frames": "1_through_32; frame_0_is_the_unscored_seed_pose",
        "formula": (
            "ae1(frame)=0.2+0.3*frame/32; ae4(frame)=1-ae1(frame); "
            "blend applies after each objective's existing internal scale"
        ),
    }


def ae1_ae4_temporal_weights(
    predicted_frame: int,
    maximum_k: int,
) -> tuple[float, float]:
    if int(maximum_k) != AE_TEMPORAL_BLEND_END_FRAME:
        raise ValueError(
            "The accepted AE1/AE4 temporal blend is defined only for K=32, "
            f"got K={maximum_k}"
        )
    if not 0 <= int(predicted_frame) <= AE_TEMPORAL_BLEND_END_FRAME:
        raise ValueError(
            f"Temporal blend frame must be in [0,32], got {predicted_frame}"
        )
    ae1_weight = (
        AE_TEMPORAL_BLEND_AE1_START
        + (AE_TEMPORAL_BLEND_AE1_END - AE_TEMPORAL_BLEND_AE1_START)
        * (float(predicted_frame) / float(AE_TEMPORAL_BLEND_END_FRAME))
    )
    return ae1_weight, 1.0 - ae1_weight


def initialization_gaze_contract(enabled: bool) -> dict[str, Any]:
    return {
        "enabled": bool(enabled),
        "random_fraction_within_clean_rows": (
            RANDOM_INITIAL_GAZE_FRACTION_PER_NOISE_CLASS if enabled else 0.0
        ),
        "random_fraction_within_noisy_rows": (
            RANDOM_INITIAL_GAZE_FRACTION_PER_NOISE_CLASS if enabled else 0.0
        ),
        "random_distribution": "independent_uniform_normalized_yaw_pitch_-1_to_1",
        "actual_gaze_input": (
            "unchanged_uniform_-1_to_1_with_5pct_exact_zero_constant_per_rollout"
        ),
        "application_order": (
            "author_initial_pose_from_initialization_gaze_then_apply_episode_start_pose_noise"
        ),
    }


def sample_initialization_gaze(
    gaze: torch.Tensor,
    noisy_mask: torch.Tensor,
    generator: torch.Generator,
    enabled: bool,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Select exact half-random initialization gaze inside each noise class."""

    if gaze.ndim != 2 or gaze.shape[-1] != 2:
        raise ValueError(f"Expected gaze [B,2], got {tuple(gaze.shape)}")
    if tuple(noisy_mask.shape) != (int(gaze.shape[0]),):
        raise ValueError(
            f"Expected noisy mask [{int(gaze.shape[0])}], got {tuple(noisy_mask.shape)}"
        )
    random_mask = torch.zeros(int(gaze.shape[0]), dtype=torch.bool)
    if not enabled:
        return gaze, random_mask
    for noisy_class in (False, True):
        class_rows = torch.nonzero(
            noisy_mask == noisy_class, as_tuple=False
        ).flatten()
        if int(class_rows.numel()) % 2:
            raise ValueError(
                "Half-random initialization gaze requires even rows in each "
                f"noise class; class={noisy_class} rows={int(class_rows.numel())}"
            )
        class_order = torch.randperm(
            int(class_rows.numel()), generator=generator
        )
        random_mask[
            class_rows.index_select(0, class_order[: int(class_rows.numel()) // 2])
        ] = True
    random_gaze = torch.rand(
        (int(gaze.shape[0]), 2), generator=generator
    ) * 2.0 - 1.0
    return torch.where(random_mask[:, None], random_gaze, gaze), random_mask
LOWERARM_LENGTH_WEIGHT = 16.061762145375866
ROLLOUT_SCHEDULE = (2, 4, 8, 16, 32)
ROLLOUT_STAGE_SECONDS = 3.0 * 60.0

EPISODE_NOISE_FK_BONES = (
    *upper_data.CORE_BONES,
    "upperarm_l",
    "upperarm_r",
)
EPISODE_NOISE_HAND_BONES = ("hand_l", "hand_r")


def episode_noise_profile(args: argparse.Namespace) -> dict[str, float]:
    """Return the exact reset-only pose-noise contract requested by the run."""

    profile = {
        "probability": float(args.episode_noise_probability),
        "pelvis_rotation_deg_max": float(args.episode_noise_pelvis_rotation_deg),
        "pelvis_location_cm_max": float(args.episode_noise_pelvis_location_cm),
        "fk_rotation_deg_max": float(args.episode_noise_fk_rotation_deg),
        "hand_location_cm_max": float(args.episode_noise_hand_location_cm),
        "hand_rotation_deg_max": float(args.episode_noise_hand_rotation_deg),
    }
    if not 0.0 <= profile["probability"] <= 1.0:
        raise ValueError(
            "--episode-noise-probability must be between zero and one"
        )
    for name, value in profile.items():
        if name != "probability" and (value < 0.0 or not math.isfinite(value)):
            raise ValueError(f"Invalid episode noise maximum {name}={value}")
    return profile


def _episode_noise_subtree_indices(
    clip: tl.MotionClip, bone_name: str
) -> torch.Tensor:
    by_name = {name: index for index, name in enumerate(clip.body_names)}
    root = by_name[bone_name]
    descendants: list[int] = []
    for joint in range(len(clip.body_names)):
        cursor = joint
        while cursor >= 0:
            if cursor == root:
                descendants.append(joint)
                break
            cursor = int(clip.parents_body_list[cursor])
    return torch.tensor(descendants, dtype=torch.long)


def apply_episode_start_pose_noise(
    clip: tl.MotionClip,
    positions: torch.Tensor,
    rotations: torch.Tensor,
    noisy_mask: torch.Tensor,
    pelvis_rotation_vector: torch.Tensor,
    pelvis_translation: torch.Tensor,
    fk_rotation_vectors: torch.Tensor,
    hand_translations: torch.Tensor,
    hand_rotation_vectors: torch.Tensor,
    subtree_indices: dict[str, torch.Tensor] | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Apply one coherent reset perturbation to a decoded global skeleton.

    Rotation vectors use radians and translations use metres.  Their lengths
    are the independently sampled magnitudes; their directions are uniform on
    the sphere.  Clean rows are selected back from the original tensors at the
    end, giving literal untouched-row semantics.
    """

    batch, joints = int(positions.shape[0]), int(positions.shape[1])
    expected = {
        "rotations": (batch, joints, 3, 3),
        "noisy_mask": (batch,),
        "pelvis_rotation_vector": (batch, 3),
        "pelvis_translation": (batch, 3),
        "fk_rotation_vectors": (batch, len(EPISODE_NOISE_FK_BONES), 3),
        "hand_translations": (batch, len(EPISODE_NOISE_HAND_BONES), 3),
        "hand_rotation_vectors": (batch, len(EPISODE_NOISE_HAND_BONES), 3),
    }
    actual = {
        "rotations": tuple(rotations.shape),
        "noisy_mask": tuple(noisy_mask.shape),
        "pelvis_rotation_vector": tuple(pelvis_rotation_vector.shape),
        "pelvis_translation": tuple(pelvis_translation.shape),
        "fk_rotation_vectors": tuple(fk_rotation_vectors.shape),
        "hand_translations": tuple(hand_translations.shape),
        "hand_rotation_vectors": tuple(hand_rotation_vectors.shape),
    }
    mismatches = {
        key: {"actual": actual[key], "expected": value}
        for key, value in expected.items()
        if actual[key] != value
    }
    if mismatches:
        raise ValueError(f"Episode pose-noise shape mismatch: {mismatches}")

    original_positions = positions
    original_rotations = rotations
    work_positions = positions
    work_rotations = rotations
    device = positions.device
    by_name = {name: index for index, name in enumerate(clip.body_names)}
    if subtree_indices is None:
        subtree_indices = {
            name: _episode_noise_subtree_indices(clip, name).to(device)
            for name in (
                "pelvis",
                *EPISODE_NOISE_FK_BONES,
                *EPISODE_NOISE_HAND_BONES,
            )
        }

    def translate_subtree(bone_name: str, delta: torch.Tensor) -> None:
        nonlocal work_positions
        indices = subtree_indices[bone_name]
        selected = work_positions.index_select(1, indices) + delta[:, None, :]
        work_positions = work_positions.index_copy(1, indices, selected)

    def rotate_subtree(bone_name: str, rotation_vector: torch.Tensor) -> None:
        nonlocal work_positions, work_rotations
        bone = by_name[bone_name]
        indices = subtree_indices[bone_name]
        pivot = work_positions[:, bone]
        local_axis = tl.normalize(rotation_vector)
        world_axis = torch.matmul(
            local_axis.unsqueeze(1), work_rotations[:, bone]
        ).squeeze(1)
        angle = torch.linalg.norm(rotation_vector, dim=-1)
        delta = tl.axis_angle_to_row_matrix(world_axis, angle)
        selected_positions = work_positions.index_select(1, indices)
        selected_positions = pivot[:, None, :] + torch.matmul(
            selected_positions - pivot[:, None, :], delta
        )
        selected_rotations = torch.matmul(
            work_rotations.index_select(1, indices), delta[:, None]
        )
        work_positions = work_positions.index_copy(
            1, indices, selected_positions
        )
        work_rotations = work_rotations.index_copy(
            1, indices, selected_rotations
        )

    # Cached-lower training owns the pelvis.  Its translation and rotation are
    # deliberately never touched, even by a numerically zero transform, so the
    # frozen pelvis/leg tensors stay bit-identical.
    for slot, bone_name in enumerate(EPISODE_NOISE_FK_BONES):
        rotate_subtree(bone_name, fk_rotation_vectors[:, slot])
    for slot, bone_name in enumerate(EPISODE_NOISE_HAND_BONES):
        translate_subtree(bone_name, hand_translations[:, slot])
        rotate_subtree(bone_name, hand_rotation_vectors[:, slot])

    mask_position = noisy_mask[:, None, None]
    mask_rotation = noisy_mask[:, None, None, None]
    return (
        torch.where(mask_position, work_positions, original_positions),
        torch.where(mask_rotation, work_rotations, original_rotations),
    )


class UpperPelvisAgent(torch.nn.Module):
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


class UpperCachedLowerAgent(torch.nn.Module):
    """Unchanged controller trunk with the removed pelvis head absent."""

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
        self.delta_head = torch.nn.Linear(width, upper_data.OUTPUT_DIM)
        torch.nn.init.zeros_(self.delta_head.weight)
        torch.nn.init.zeros_(self.delta_head.bias)

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        return self.delta_head(self.trunk(values))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


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


def atomic_copy(source: Path, destination: Path) -> None:
    """Publish an already-serialized artifact without parsing it again.

    Full BS64 rollout JSON files are large.  Loading one back into nested
    Python lists and serializing it a second time creates a large, pointless
    memory/allocator spike exactly at the checkpoint boundary.  A byte copy to
    a sibling temporary file preserves the same atomic publication contract.
    """

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    shutil.copyfile(source, temporary)
    os.replace(temporary, destination)


def stop_requested(args: argparse.Namespace) -> bool:
    return bool(args.stop_file and Path(args.stop_file).is_file())


def load_ae(
    path: Path, device: torch.device
) -> tuple[
    SimpleAutoencoder,
    torch.Tensor,
    torch.Tensor,
    torch.Tensor,
    dict[str, Any],
]:
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    if checkpoint.get("kind") != "upper_pose_pelvis_physical_simple_autoencoder":
        raise RuntimeError(f"Not the accepted upper pelvis vanilla AE1: {path}")
    schema = dict(checkpoint.get("schema", {}))
    expected = {
        "total_dim": WINDOW_DIM,
        "input_dim": INPUT_DIM,
        "output_dim": contract.PHYSICAL_DIM,
        "newest_output_start": NEWEST_OUTPUT_START,
        "newest_output_end": NEWEST_OUTPUT_END,
    }
    for key, value in expected.items():
        if schema.get(key) != value:
            raise RuntimeError(
                f"AE1 schema {key}={schema.get(key)!r}, expected {value!r}"
            )
    cfg = SimpleAEConfig(**dict(checkpoint["config"]))
    model = SimpleAutoencoder(WINDOW_DIM, cfg).to(device)
    model.load_state_dict(checkpoint["model"], strict=True)
    model.eval().requires_grad_(False)
    mean = checkpoint["mean"].to(device=device, dtype=torch.float32)
    std = checkpoint["std"].to(device=device, dtype=torch.float32).clamp_min(1.0e-8)
    if tuple(mean.shape) != (WINDOW_DIM,) or tuple(std.shape) != (WINDOW_DIM,):
        raise RuntimeError(
            f"AE1 normalization mismatch: mean={tuple(mean.shape)} std={tuple(std.shape)}"
        )
    scoring = dict(schema.get("scoring_weights", {}))
    output_weights = torch.ones(
        contract.PHYSICAL_DIM, dtype=torch.float32, device=device
    )
    hand_weight_l = float(scoring.get("hand_l_transform_weight", 1.0))
    hand_weight_r = float(scoring.get("hand_r_transform_weight", 1.0))
    for hand, weight in (("hand_l", hand_weight_l), ("hand_r", hand_weight_r)):
        if not math.isfinite(weight) or weight < 1.0:
            raise RuntimeError(f"Invalid AE1 {hand} scoring weight {weight!r}: {path}")
        bone = contract.PHYSICAL_BONES.index(hand)
        start = bone * contract.TRANSFORM_DIM
        output_weights[start : start + contract.TRANSFORM_DIM] = weight
    return model, mean, std, output_weights, checkpoint


def weighted_physical_mse(
    error: torch.Tensor,
    weights: torch.Tensor,
) -> torch.Tensor:
    return (error.square() * weights).sum(dim=-1) / weights.sum()


def ae4_absolute_pose_loss(
    candidate: torch.Tensor,
    proposal: torch.Tensor,
    target_std: torch.Tensor,
) -> torch.Tensor:
    """AE4 objective with a linear 5-degree dead zone on non-hand rotations.

    Positions and both complete hand transforms retain the original normalized
    component MSE.  Every other bone's 6D rotation component is replaced by a
    weighted true root-local geodesic angle beyond five degrees: x5 normally,
    and x15 for neck_01, neck_02 and head.  The angular term is repeated
    conceptually across the six rotation slots so the final denominator remains
    the original 144 AE4 output components.
    """

    batch = int(candidate.shape[0])
    expected = (batch, ae4_data.OUTPUT_DIM)
    if tuple(candidate.shape) != expected or tuple(proposal.shape) != expected:
        raise RuntimeError(
            "AE4 candidate/proposal shape changed: "
            f"candidate={tuple(candidate.shape)} proposal={tuple(proposal.shape)}"
        )
    shaped_candidate = candidate.reshape(
        batch, len(ae4_data.UPPER_TARGET_BONES), ae4_data.TRANSFORM_DIM
    )
    shaped_proposal = proposal.reshape_as(shaped_candidate)
    shaped_std = target_std.reshape(
        1, len(ae4_data.UPPER_TARGET_BONES), ae4_data.TRANSFORM_DIM
    )
    normalized_square = (
        (shaped_candidate - shaped_proposal) / shaped_std
    ).square()

    # All positions keep their prior normalized MSE.  Hands additionally keep
    # their prior normalized 6D rotation MSE without a dead zone or x5 scale.
    retained_sum = normalized_square[..., :3].sum(dim=(-1, -2))
    hand_l_index = ae4_data.UPPER_TARGET_BONES.index("hand_l")
    hand_r_index = ae4_data.UPPER_TARGET_BONES.index("hand_r")
    retained_sum = retained_sum + normalized_square[
        :, hand_l_index, 3:9
    ].sum(dim=-1) + normalized_square[:, hand_r_index, 3:9].sum(dim=-1)

    # Basic slices stay entirely on the capture device.  Tuple/list indexing
    # would allocate a CPU index tensor while a CUDA Graph is being captured.
    candidate_non_hand = torch.cat(
        (
            shaped_candidate[:, :hand_l_index, 3:9],
            shaped_candidate[:, hand_l_index + 1 : hand_r_index, 3:9],
            shaped_candidate[:, hand_r_index + 1 :, 3:9],
        ),
        dim=1,
    )
    proposal_non_hand = torch.cat(
        (
            shaped_proposal[:, :hand_l_index, 3:9],
            shaped_proposal[:, hand_l_index + 1 : hand_r_index, 3:9],
            shaped_proposal[:, hand_r_index + 1 :, 3:9],
        ),
        dim=1,
    )
    non_hand_count = len(ae4_data.UPPER_TARGET_BONES) - 2
    candidate_rotation = tl.rotation_6d_to_matrix(
        candidate_non_hand.reshape(-1, 6)
    ).reshape(batch, non_hand_count, 3, 3)
    proposal_rotation = tl.rotation_6d_to_matrix(
        proposal_non_hand.reshape(-1, 6)
    ).reshape(batch, non_hand_count, 3, 3)
    relative = candidate_rotation @ proposal_rotation.transpose(-1, -2)
    cosine = ((relative.diagonal(dim1=-2, dim2=-1).sum(dim=-1) - 1.0) * 0.5).clamp(
        -1.0, 1.0
    )
    skew = torch.stack(
        (
            relative[..., 2, 1] - relative[..., 1, 2],
            relative[..., 0, 2] - relative[..., 2, 0],
            relative[..., 1, 0] - relative[..., 0, 1],
        ),
        dim=-1,
    )
    sine = 0.5 * torch.linalg.vector_norm(skew, dim=-1)
    angle = torch.atan2(sine, cosine)
    excess = (
        angle - math.radians(AE4_NON_HAND_ROTATION_DEADZONE_DEG)
    ).clamp_min(0.0)
    angular_sum = (
        AE4_NON_HAND_ROTATION_WEIGHT
        * float(6)
        * excess.sum(dim=-1)
    )
    neck_head_excess = excess[
        :, AE4_NECK_HEAD_NON_HAND_START:AE4_NECK_HEAD_NON_HAND_END
    ]
    angular_sum = angular_sum + (
        AE4_NECK_HEAD_ROTATION_WEIGHT - AE4_NON_HAND_ROTATION_WEIGHT
    ) * float(6) * neck_head_excess.sum(dim=-1)
    return (retained_sum + angular_sum) / float(ae4_data.OUTPUT_DIM)


def load_ae22(
    path: Path, device: torch.device
) -> tuple[torch.nn.Module, torch.Tensor, torch.Tensor, dict[str, Any]]:
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    if checkpoint.get("kind") != "upper_pelvis_root_ae22_condition_only":
        raise RuntimeError(f"Not an upper pelvis root-relative AE22: {path}")
    projector = dict(checkpoint.get("projector", {}))
    expected = {
        "input_dim": ae22_data.FEATURE_DIM,
        "motion_dim": contract.PHYSICAL_DIM,
        "hidden_dim": 1024,
        "num_hidden_layers": 3,
    }
    for key, value in expected.items():
        if int(projector.get(key, -1)) != int(value):
            raise RuntimeError(
                f"AE22 projector {key}={projector.get(key)!r}, expected {value}"
            )
    if str(projector.get("architecture")) != "condition_only":
        raise RuntimeError(f"AE22 is not condition-only: {path}")
    model = ae22_data.ConditionalDeltaProjector(
        ae22_data.FEATURE_DIM, contract.PHYSICAL_DIM, 1024, 3
    ).to(device)
    model.load_state_dict(checkpoint["model"], strict=True)
    model.eval().requires_grad_(False)
    mean = checkpoint["mean"].to(device=device, dtype=torch.float32)
    std = checkpoint["std"].to(device=device, dtype=torch.float32).clamp_min(1.0e-8)
    if tuple(mean.shape) != (ae22_data.FEATURE_DIM,) or tuple(std.shape) != (
        ae22_data.FEATURE_DIM,
    ):
        raise RuntimeError(
            f"AE22 normalization mismatch: mean={tuple(mean.shape)} std={tuple(std.shape)}"
        )
    return model, mean, std, checkpoint


def resolve_ae4_path(requested: str | None = None) -> Path:
    if requested:
        path = Path(requested).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        return path
    pointer = json.loads(ae4_data.POINTER_PATH.read_text(encoding="utf-8"))
    path = Path(str(pointer["checkpoint"]))
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    expected_hash = str(pointer.get("checkpoint_sha256", "")).upper()
    if expected_hash:
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"Accepted AE4 hash mismatch: expected={expected_hash} actual={actual_hash}"
            )
    return path


def cached_lower_ae4_frame_rows(
    runtime: runtime_data.CategoryRuntime,
    cache: cached_lower_data.CachedLowerCategory,
    clip_ids: torch.Tensor,
    indices: torch.Tensor,
) -> torch.Tensor:
    """Return frozen lower+pelvis transforms in each row's actual root frame."""

    lower_vector = cache.gather("lower_vector", clip_ids, indices)
    root_position = cache.gather("root_position", clip_ids, indices)
    root_rotation = cache.gather("root_rotation", clip_ids, indices)
    inverse = root_rotation.transpose(-1, -2)
    cached_positions = cache.gather("cached_lower_position", clip_ids, indices)
    cached_rotations = cache.gather("cached_lower_rotation", clip_ids, indices)
    transforms: dict[str, torch.Tensor] = {}
    for slot, name in enumerate(contract.CACHED_LOWER_PHYSICAL_BONES):
        position = torch.matmul(
            (cached_positions[:, slot] - root_position).unsqueeze(1), inverse
        ).squeeze(1)
        rotation = cached_rotations[:, slot] @ inverse
        transforms[name] = torch.cat((position, tl.rotmat_to_6d(rotation)), dim=-1)

    payload = lower_vector[:, lower_ctl.payload_slice(runtime.store)]
    toe_offsets = runtime.lower_geometry["ik_toe_offsets"].index_select(0, clip_ids)
    toe_axes = runtime.lower_geometry["ik_toe_axis"].index_select(0, clip_ids)
    for limb, spec in enumerate(runtime.lower_clip.ik_payload_slices):
        if str(spec.get("kind", "")) != "leg":
            continue
        side = str(spec["side"])
        position_slice = spec["pos"]
        rotation_slice = spec["rot6"]
        toe_slice = spec.get("toe_float")
        if not isinstance(position_slice, slice) or not isinstance(rotation_slice, slice):
            raise TypeError(f"Invalid cached lower leg payload slices: {spec}")
        foot_position = payload[:, position_slice]
        foot_rotation = tl.rotation_6d_to_matrix(payload[:, rotation_slice])
        transforms[f"foot_{side}"] = torch.cat(
            (foot_position, tl.rotmat_to_6d(foot_rotation)), dim=-1
        )
        if not isinstance(toe_slice, slice):
            raise RuntimeError(f"Cached lower leg has no toe payload: {spec}")
        toe_float = payload[:, toe_slice].reshape(-1).clamp(-1.0, 1.0)
        toe_position = foot_position + torch.matmul(
            toe_offsets[:, limb].unsqueeze(1), foot_rotation
        ).squeeze(1)
        toe_hinge = tl.axis_angle_to_row_matrix(
            toe_axes[:, limb], toe_float * float(tl.IK_TOE_ALPHA)
        )
        toe_rotation = toe_hinge @ foot_rotation
        transforms[f"ball_{side}"] = torch.cat(
            (toe_position, tl.rotmat_to_6d(toe_rotation)), dim=-1
        )

    # The standalone full-pose decoder resolves the frozen leg chains with the
    # same direct pole-preserving solve used by the old pelvis path.  Reproduce
    # those thigh/calf transforms once here so AE4 sees exactly what the viewer
    # shows, while retaining the cached foot/ball end effectors.
    full_clip = runtime.full_by_mode[runtime_data.MODE_SHEATHED]
    geometry = runtime.full_geometry_by_mode[runtime_data.MODE_SHEATHED]
    local_offsets = geometry["local_offsets"].index_select(0, clip_ids)
    limb_lengths = geometry["ik_limb_lengths"].index_select(0, clip_ids)
    local_poles = geometry["ik_local_pole_axis"].index_select(0, clip_ids)
    cached_slot = {
        name: slot for slot, name in enumerate(contract.CACHED_LOWER_PHYSICAL_BONES)
    }
    for limb, spec in enumerate(full_clip.ik_limb_specs):
        if str(spec.get("kind", "")) != "leg":
            continue
        side = str(spec["side"])
        thigh_name = f"thigh_{side}"
        calf_name = f"calf_{side}"
        thigh_joint = int(spec["start"])
        calf_joint = int(spec["mid"])
        foot_joint = int(spec["end"])
        original_hip = cached_positions[:, cached_slot[thigh_name]]
        original_knee = cached_positions[:, cached_slot[calf_name]]
        foot_root = transforms[f"foot_{side}"][:, :3]
        original_ankle = root_position + torch.matmul(
            foot_root.unsqueeze(1), root_rotation
        ).squeeze(1)
        knee, pole = contract._direct_knee(
            original_hip,
            original_ankle,
            original_hip,
            original_knee,
            original_ankle,
            limb_lengths[:, limb, 0],
            limb_lengths[:, limb, 1],
        )
        thigh_world_rotation = tl.rotation_from_axis_and_pole(
            local_offsets[:, calf_joint],
            knee - original_hip,
            local_poles[:, limb, 0],
            pole,
        )
        world_pole = torch.matmul(
            local_poles[:, limb, 0].unsqueeze(1), thigh_world_rotation
        ).squeeze(1)
        calf_world_rotation = tl.rotation_from_axis_and_pole(
            local_offsets[:, foot_joint],
            original_ankle - knee,
            local_poles[:, limb, 1],
            world_pole,
        )
        thigh_root_rotation = thigh_world_rotation @ inverse
        calf_root_rotation = calf_world_rotation @ inverse
        calf_root_position = torch.matmul(
            (knee - root_position).unsqueeze(1), inverse
        ).squeeze(1)
        transforms[thigh_name] = torch.cat(
            (
                transforms[thigh_name][:, :3],
                tl.rotmat_to_6d(thigh_root_rotation),
            ),
            dim=-1,
        )
        transforms[calf_name] = torch.cat(
            (calf_root_position, tl.rotmat_to_6d(calf_root_rotation)), dim=-1
        )

    result = torch.cat(
        [transforms[name] for name in ae4_data.LOWER_CONDITION_BONES], dim=-1
    )
    expected = (int(clip_ids.numel()), ae4_data.LOWER_FRAME_DIM)
    if tuple(result.shape) != expected:
        raise RuntimeError(
            f"Cached AE4 lower frame shape changed: {tuple(result.shape)} != {expected}"
        )
    return result


@torch.no_grad()
def prepare_cached_lower_ae4_tables(
    runtimes: dict[str, runtime_data.CategoryRuntime],
    caches: dict[str, cached_lower_data.CachedLowerCategory],
) -> None:
    """Precompute immutable AE4 lower conditioning once, outside the hot graph."""

    for category, runtime in runtimes.items():
        cache = caches[category]
        if "ae4_lower_root" in cache.tensors:
            continue
        total = int(cache.tensors["lower_vector"].shape[0])
        table = cache.tensors["lower_vector"].new_empty(
            (total, ae4_data.LOWER_FRAME_DIM)
        )
        for clip_id in range(len(runtime.lower_clips)):
            offset = int(cache.clip_offsets[clip_id].item())
            length = int(cache.cache_lengths[clip_id].item())
            clip_ids = torch.full(
                (length,), clip_id, dtype=torch.long, device=table.device
            )
            indices = torch.arange(length, dtype=torch.long, device=table.device)
            table[offset : offset + length].copy_(
                cached_lower_ae4_frame_rows(runtime, cache, clip_ids, indices)
            )
        if not bool(torch.isfinite(table).all()):
            raise RuntimeError(f"Non-finite cached AE4 lower table for {category}")
        cache.tensors["ae4_lower_root"] = table.contiguous()


def pelvis_heading(
    lower_vector: torch.Tensor,
    root_rotation: torch.Tensor,
    heading: torch.Tensor,
) -> torch.Tensor:
    return contract.root_transform_to_heading(
        lower_vector[:, :9], root_rotation, heading
    )


def lower_next_live(
    runtime: runtime_data.CategoryRuntime,
    state: dict[str, torch.Tensor],
) -> torch.Tensor:
    """Run frozen lower weights while preserving gradients to feedback state."""

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
    next_vector, _next_pelvis, _next_payload = (
        lower_ctl.advance_transition_state(
            runtime.store,
            state["clip_ids"],
            state["cur_idx"],
            transition,
        )
    )
    return next_vector


def decode_rows(
    runtime: runtime_data.CategoryRuntime,
    mode: float,
    lower_vector: torch.Tensor,
    upper: torch.Tensor,
    pelvis: torch.Tensor,
    root_position: torch.Tensor,
    root_rotation: torch.Tensor,
    heading: torch.Tensor,
    clip_ids: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    positions: torch.Tensor | None = None
    rotations: torch.Tensor | None = None
    for clip_id in torch.unique(clip_ids, sorted=True).tolist():
        selection = torch.nonzero(
            clip_ids == int(clip_id), as_tuple=False
        ).flatten()
        selected_positions, selected_rotations = contract.decode_full_pose(
            runtime.full_clips_by_mode[mode][int(clip_id)],
            runtime.lower_clips[int(clip_id)],
            lower_vector.index_select(0, selection),
            upper.index_select(0, selection),
            pelvis.index_select(0, selection),
            root_position.index_select(0, selection),
            root_rotation.index_select(0, selection),
            heading.index_select(0, selection),
        )
        if positions is None:
            positions = selected_positions.new_zeros(
                (int(lower_vector.shape[0]),) + tuple(selected_positions.shape[1:])
            )
            rotations = selected_rotations.new_zeros(
                (int(lower_vector.shape[0]),) + tuple(selected_rotations.shape[1:])
            )
        positions = positions.index_copy(0, selection, selected_positions)
        rotations = rotations.index_copy(0, selection, selected_rotations)
    assert positions is not None and rotations is not None
    return positions, rotations


def physical_delta(
    runtime: runtime_data.CategoryRuntime,
    mode: float,
    current_lower: torch.Tensor,
    next_lower: torch.Tensor,
    current_upper: torch.Tensor,
    next_upper: torch.Tensor,
    current_pelvis: torch.Tensor,
    next_pelvis: torch.Tensor,
    current_root: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    next_root: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    clip_ids: torch.Tensor,
) -> tuple[torch.Tensor, tuple[torch.Tensor, torch.Tensor], tuple[torch.Tensor, torch.Tensor]]:
    current_positions, current_rotations = decode_rows(
        runtime,
        mode,
        current_lower,
        current_upper,
        current_pelvis,
        *current_root,
        clip_ids,
    )
    next_positions, next_rotations = decode_rows(
        runtime,
        mode,
        next_lower,
        next_upper,
        next_pelvis,
        *next_root,
        clip_ids,
    )
    chunks: list[torch.Tensor] = []
    for clip_id in torch.unique(clip_ids, sorted=True).tolist():
        selection = torch.nonzero(
            clip_ids == int(clip_id), as_tuple=False
        ).flatten()
        clip = runtime.full_clips_by_mode[mode][int(clip_id)]
        chunks.append(
            (
                selection,
                contract.physical_transition_from_decoded(
                    clip,
                    current_positions.index_select(0, selection),
                    current_rotations.index_select(0, selection),
                    next_positions.index_select(0, selection),
                    next_rotations.index_select(0, selection),
                    current_root[0].index_select(0, selection),
                    current_root[1].index_select(0, selection),
                ),
            )
        )
    delta = current_lower.new_zeros((int(current_lower.shape[0]), contract.PHYSICAL_DIM))
    for selection, values in chunks:
        delta = delta.index_copy(0, selection, values)
    return delta, (current_positions, current_rotations), (next_positions, next_rotations)


def decode_rows_vectorized(
    runtime: runtime_data.CategoryRuntime,
    mode: float,
    lower_vector: torch.Tensor,
    upper: torch.Tensor,
    pelvis: torch.Tensor,
    root_position: torch.Tensor,
    root_rotation: torch.Tensor,
    heading: torch.Tensor,
    clip_ids: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Capture-safe heterogeneous decode using per-row corpus geometry."""

    geometry = {
        name: values.index_select(0, clip_ids)
        for name, values in runtime.full_geometry_by_mode[mode].items()
    }
    return contract.decode_full_pose(
        runtime.full_by_mode[mode],
        runtime.lower_clip,
        lower_vector,
        upper,
        pelvis,
        root_position,
        root_rotation,
        heading,
        geometry_tensors=geometry,
    )


def physical_delta_vectorized(
    runtime: runtime_data.CategoryRuntime,
    mode: float,
    current_lower: torch.Tensor,
    next_lower: torch.Tensor,
    current_upper: torch.Tensor,
    next_upper: torch.Tensor,
    current_pelvis: torch.Tensor,
    next_pelvis: torch.Tensor,
    current_root: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    next_root: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    clip_ids: torch.Tensor,
) -> tuple[
    torch.Tensor,
    tuple[torch.Tensor, torch.Tensor],
    tuple[torch.Tensor, torch.Tensor],
]:
    current_positions, current_rotations = decode_rows_vectorized(
        runtime,
        mode,
        current_lower,
        current_upper,
        current_pelvis,
        *current_root,
        clip_ids,
    )
    next_positions, next_rotations = decode_rows_vectorized(
        runtime,
        mode,
        next_lower,
        next_upper,
        next_pelvis,
        *next_root,
        clip_ids,
    )
    delta = contract.physical_transition_from_decoded(
        runtime.full_by_mode[mode],
        current_positions,
        current_rotations,
        next_positions,
        next_rotations,
        current_root[0],
        current_root[1],
    )
    return delta, (current_positions, current_rotations), (next_positions, next_rotations)


def ae4_condition_and_candidate(
    runtime: runtime_data.CategoryRuntime,
    mode: float,
    clip_ids: torch.Tensor,
    previous_lower: torch.Tensor,
    previous_upper: torch.Tensor,
    previous_pelvis: torch.Tensor,
    previous_root: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    current_globals: tuple[torch.Tensor, torch.Tensor],
    current_root: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    next_globals: tuple[torch.Tensor, torch.Tensor],
    next_root: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    root_features: torch.Tensor,
    gaze: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Build condition-only AE4 input and the agent's absolute upper pose."""

    previous_positions, previous_rotations = decode_rows(
        runtime,
        mode,
        previous_lower,
        previous_upper,
        previous_pelvis,
        *previous_root,
        clip_ids,
    )
    condition = previous_lower.new_zeros(
        (int(clip_ids.numel()), ae4_data.INPUT_DIM)
    )
    candidate = previous_lower.new_zeros(
        (int(clip_ids.numel()), ae4_data.OUTPUT_DIM)
    )
    for clip_id in torch.unique(clip_ids, sorted=True).tolist():
        selection = torch.nonzero(
            clip_ids == int(clip_id), as_tuple=False
        ).flatten()
        clip = runtime.full_clips_by_mode[mode][int(clip_id)]
        selected_condition = ae4_data.condition_from_decoded_frames(
            clip,
            (
                previous_positions.index_select(0, selection),
                previous_rotations.index_select(0, selection),
            ),
            (
                current_globals[0].index_select(0, selection),
                current_globals[1].index_select(0, selection),
            ),
            (
                next_globals[0].index_select(0, selection),
                next_globals[1].index_select(0, selection),
            ),
            (
                previous_root[0].index_select(0, selection),
                previous_root[1].index_select(0, selection),
            ),
            (
                current_root[0].index_select(0, selection),
                current_root[1].index_select(0, selection),
            ),
            (
                next_root[0].index_select(0, selection),
                next_root[1].index_select(0, selection),
            ),
            root_features.index_select(0, selection),
            mode,
            gaze.index_select(0, selection),
        )
        selected_candidate = ae4_data.absolute_upper_from_decoded(
            clip,
            next_globals[0].index_select(0, selection),
            next_globals[1].index_select(0, selection),
            next_root[0].index_select(0, selection),
            next_root[1].index_select(0, selection),
        )
        condition = condition.index_copy(0, selection, selected_condition)
        candidate = candidate.index_copy(0, selection, selected_candidate)
    return condition, candidate


@torch.no_grad()
def authored_transition_delta_rows(
    runtime: runtime_data.CategoryRuntime,
    mode: float,
    clip_ids: torch.Tensor,
    indices: torch.Tensor,
    gaze: torch.Tensor,
    device: torch.device,
) -> torch.Tensor:
    """Return authored root-relative physical deltas for reporting only."""

    cpu_clip_ids = clip_ids.detach().cpu().long()
    cpu_indices = indices.detach().cpu().long()
    cpu_gaze = gaze.detach().cpu().to(dtype=torch.float32)
    result = torch.empty(
        (int(indices.shape[0]), contract.PHYSICAL_DIM),
        dtype=torch.float32,
        device="cpu",
    )
    for clip_id in torch.unique(cpu_clip_ids, sorted=True).tolist():
        selection = torch.nonzero(
            cpu_clip_ids == int(clip_id), as_tuple=False
        ).flatten()
        values = contract.authored_transition_delta(
            runtime.full_clips_by_mode[mode][int(clip_id)],
            runtime.cfg,
            cpu_indices.index_select(0, selection),
            cpu_gaze.index_select(0, selection),
        )
        result.index_copy_(0, selection, values.to(dtype=torch.float32))
    return result.to(device=device, dtype=torch.float32)


def context_state(
    runtime: runtime_data.CategoryRuntime,
    mode: float,
    lower_state: dict[str, torch.Tensor],
    gaze: torch.Tensor,
    device: torch.device,
) -> dict[str, torch.Tensor]:
    starts = lower_state["cur_idx"]
    clip_ids = lower_state["clip_ids"]
    count = int(starts.numel())
    indices = torch.cat((starts - 2, starts - 1, starts), dim=0)
    upper = runtime_data.upper_overlay_runtime_rows(
        runtime, mode, clip_ids.repeat(3), indices, gaze.repeat(3, 1), device
    )
    older_upper, previous_upper, current_upper = upper.split(count, dim=0)
    old_root = runtime_data.root_state(runtime, starts - 2, clip_ids)
    previous_root = runtime_data.root_state(runtime, starts - 1, clip_ids)
    current_root = runtime_data.root_state(runtime, starts, clip_ids)
    older_pelvis = pelvis_heading(lower_state["older"], old_root[1], old_root[2])
    previous_pelvis = pelvis_heading(lower_state["prev"], previous_root[1], previous_root[2])
    current_pelvis = pelvis_heading(lower_state["cur"], current_root[1], current_root[2])
    rest = runtime.rest_offsets_by_mode[mode].index_select(0, clip_ids)
    full = runtime.full_by_mode[mode]
    previous_base = runtime_data.base_upper_from_lower(
        lower_state["prev"], *previous_root, full, rest
    )
    current_base = runtime_data.base_upper_from_lower(
        lower_state["cur"], *current_root, full, rest
    )
    current_prior = upper_data.clean_upper_state(
        current_base + previous_upper - previous_base
    )
    roots = runtime.store.get_input_root_features(clip_ids, starts - 1)
    feet_previous = runtime_data.foot_heading_features(
        runtime.store, lower_state["prev"], previous_root[1], previous_root[2]
    )
    feet_current = runtime_data.foot_heading_features(
        runtime.store, lower_state["cur"], current_root[1], current_root[2]
    )
    controller_input = torch.cat(
        (
            older_upper,
            current_prior,
            older_pelvis,
            previous_pelvis,
            current_pelvis,
            roots,
            torch.full((count, 1), float(mode), dtype=torch.float32, device=device),
            feet_previous,
            feet_current,
            gaze,
        ),
        dim=-1,
    )
    if tuple(controller_input.shape) != (count, INPUT_DIM):
        raise RuntimeError(f"Context input mismatch: {tuple(controller_input.shape)}")
    transition, _current_globals, _next_globals = physical_delta(
        runtime,
        mode,
        lower_state["prev"],
        lower_state["cur"],
        previous_upper,
        current_upper,
        previous_pelvis,
        current_pelvis,
        previous_root,
        current_root,
        clip_ids,
    )
    return {
        "context_row": torch.cat((controller_input, transition), dim=-1),
        "previous_upper": previous_upper,
        "current_upper": current_upper,
        "current_base": current_base,
        "previous_pelvis": previous_pelvis,
        "current_pelvis": current_pelvis,
        "frozen_current_pelvis": current_pelvis,
    }


def advance_lower(
    runtime: runtime_data.CategoryRuntime,
    state: dict[str, torch.Tensor],
    next_lower: torch.Tensor,
    next_index: torch.Tensor,
) -> None:
    state["older"] = state["prev"]
    state["prev"] = state["cur"]
    state["cur"] = next_lower
    state["cur_idx"] = next_index
    payload_slice = lower_ctl.payload_slice(runtime.store)
    state["prev_pelvis"] = state["prev"][:, :3]
    state["cur_pelvis"] = state["cur"][:, :3]
    state["prev_payload"] = state["prev"][:, payload_slice]
    state["cur_payload"] = state["cur"][:, payload_slice]


@torch.inference_mode()
def rollout_upper_pelvis_checkpoint(
    checkpoint_path: Path,
    source_path: Path,
    *,
    gaze: tuple[float, float] = (0.0, 0.0),
    device: torch.device | str = "cpu",
    max_frames: int | None = None,
    start_frame: int = 2,
) -> runtime_data.UpperPoseRollout:
    """Replay the 99-output upper+pelvis controller in exact training order."""

    device = torch.device(device)
    checkpoint_path = Path(checkpoint_path).resolve()
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if checkpoint.get("kind") != CONTROLLER_KIND:
        raise RuntimeError(
            f"Not an upper+pelvis controller checkpoint: {checkpoint_path}"
        )
    source = Path(source_path).resolve()
    if upper_data.SWORD_ROOT.resolve() in source.parents:
        dataset_root = upper_data.SWORD_ROOT
        mode = runtime_data.MODE_DRAWN
    elif upper_data.ORIGINAL_ROOT.resolve() in source.parents:
        dataset_root = upper_data.ORIGINAL_ROOT
        mode = runtime_data.MODE_SHEATHED
    else:
        raise ValueError(f"Replay source is outside the matched upper datasets: {source}")
    relative = source.relative_to(dataset_root.resolve()).as_posix()
    category = (
        runtime_data.CATEGORY_RUN
        if relative.startswith("run_")
        else runtime_data.CATEGORY_WALK
    )
    gaze_values = (float(gaze[0]), float(gaze[1]))
    if any(not math.isfinite(value) or abs(value) > 1.0 for value in gaze_values):
        raise ValueError(f"Normalized gaze must be finite in [-1,1], got {gaze_values}")

    lower_selection = dict(checkpoint.get("metadata", {})).get(
        "lower_selection", {}
    )
    selected_pointer = (
        lower_selection.get(category)
        if isinstance(lower_selection, dict)
        else None
    )
    if isinstance(selected_pointer, dict) and selected_pointer.get("checkpoint"):
        selected_path = Path(str(selected_pointer["checkpoint"]))
        if not selected_path.is_absolute():
            selected_path = (PROJECT_ROOT / selected_path).resolve()
        selected_sha = str(selected_pointer.get("checkpoint_sha256", "")).upper()
        if not selected_sha:
            raise RuntimeError(
                f"Controller checkpoint lower selection has no SHA for {category}"
            )
        actual_sha = sha256_file(selected_path)
        if actual_sha != selected_sha:
            raise RuntimeError(
                f"Controller checkpoint lower selection SHA mismatch for {category}: "
                f"{actual_sha} != {selected_sha}"
            )
        lower_path = selected_path
    else:
        lower_path, _pointer = runtime_data.resolve_pointer(
            runtime_data.WALK_POINTER
            if category == runtime_data.CATEGORY_WALK
            else runtime_data.RUN_POINTER,
            runtime_data.EXPECTED_WALK_SHA256
            if category == runtime_data.CATEGORY_WALK
            else runtime_data.EXPECTED_RUN_SHA256,
        )
    lower_checkpoint = torch.load(lower_path, map_location="cpu", weights_only=False)
    cfg = runtime_data.apply_checkpoint_config(lower_checkpoint, device)
    probe = tl.MotionClip(
        upper_data.ORIGINAL_ROOT / relative,
        cfg,
        cyclic_animation=runtime_data.is_cyclic(relative),
    )
    lower_model = visualize.load_model(lower_checkpoint, probe, cfg, device)
    lower_model.eval().requires_grad_(False)
    runtime = runtime_data.build_category_runtime(
        category, [relative], lower_checkpoint, cfg, lower_model, device
    )
    agent = UpperPelvisAgent().to(device)
    agent.load_state_dict(checkpoint["model"], strict=True)
    agent.eval().requires_grad_(False)

    start_frame = int(start_frame)
    if start_frame < 2:
        raise ValueError(f"Upper rollout start frame must be at least 2, got {start_frame}")
    starts = torch.tensor([start_frame], dtype=torch.long, device=device)
    lower_state = runtime_data.lower_initial_state(runtime, starts)
    gaze_tensor = torch.tensor([gaze_values], dtype=torch.float32, device=device)
    upper_state = context_state(runtime, mode, lower_state, gaze_tensor, device)
    full_clip = runtime.full_by_mode[mode]
    clip_ids = lower_state["clip_ids"]

    positions_rows: list[torch.Tensor] = []
    rotations_rows: list[torch.Tensor] = []
    target_positions_rows: list[torch.Tensor] = []
    target_rotations_rows: list[torch.Tensor] = []
    frame_indices: list[int] = []
    root_positions: list[torch.Tensor] = []
    root_rotations: list[torch.Tensor] = []
    ae_windows: list[torch.Tensor | None] = []
    ae4_conditions: list[torch.Tensor | None] = []

    def append_pose(
        frame_index: int,
        lower: torch.Tensor,
        upper: torch.Tensor,
        pelvis: torch.Tensor,
        ae_window: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        index = torch.tensor([frame_index], dtype=torch.long, device=device)
        root = runtime_data.root_state(runtime, index, clip_ids)
        position, rotation = decode_rows(
            runtime, mode, lower, upper, pelvis, *root, clip_ids
        )
        logical = (
            frame_index % int(full_clip.cyclic_period)
            if full_clip.cyclic_animation
            else frame_index
        )
        target_position, target_rotation = upper_data.gaze_overlay_global_pose(
            full_clip,
            torch.tensor([logical], dtype=torch.long),
            torch.tensor([gaze_values], dtype=torch.float32),
        )
        positions_rows.append(position[0].detach().cpu())
        rotations_rows.append(rotation[0].detach().cpu())
        target_positions_rows.append(target_position[0].detach().cpu())
        target_rotations_rows.append(target_rotation[0].detach().cpu())
        frame_indices.append(frame_index)
        root_positions.append(root[0][0].detach().cpu())
        root_rotations.append(root[1][0].detach().cpu())
        ae_windows.append(
            None if ae_window is None else ae_window[0].detach().cpu()
        )
        ae4_conditions.append(None)
        return position, rotation

    seed_lower = (lower_state["older"], lower_state["prev"], lower_state["cur"])
    seed_indices = torch.tensor(
        [start_frame - 2, start_frame - 1, start_frame],
        dtype=torch.long,
        device=device,
    )
    seed_upper = runtime_data.upper_overlay_runtime_rows(
        runtime,
        mode,
        clip_ids.repeat(3),
        seed_indices,
        gaze_tensor.repeat(3, 1),
        device,
    )
    previous_positions: torch.Tensor | None = None
    previous_rotations: torch.Tensor | None = None
    current_positions: torch.Tensor | None = None
    current_rotations: torch.Tensor | None = None
    for frame_index, lower, upper in zip(
        range(start_frame - 2, start_frame + 1), seed_lower, seed_upper
    ):
        root = runtime_data.root_state(
            runtime,
            torch.tensor([frame_index], dtype=torch.long, device=device),
            clip_ids,
        )
        previous_positions, previous_rotations = current_positions, current_rotations
        current_positions, current_rotations = append_pose(
            frame_index,
            lower,
            upper.unsqueeze(0),
            pelvis_heading(lower, root[1], root[2]),
        )
    assert previous_positions is not None and previous_rotations is not None
    assert current_positions is not None and current_rotations is not None

    final_index = (
        min(int(runtime.lower_clip.T) - 1, int(runtime.lower_clip.cyclic_period) - 1)
        if runtime.lower_clip.cyclic_animation
        else int(runtime.lower_clip.T) - int(runtime.cfg.future_window) - 1
    )
    if max_frames is not None:
        final_index = min(final_index, max(0, int(max_frames) - 1))
    while int(lower_state["cur_idx"].item()) < final_index:
        next_lower = lower_next_live(runtime, lower_state)
        next_indices = lower_state["cur_idx"] + 1
        current_root = runtime_data.root_state(
            runtime, lower_state["cur_idx"], clip_ids
        )
        next_root = runtime_data.root_state(runtime, next_indices, clip_ids)
        frozen_next_pelvis = pelvis_heading(next_lower, next_root[1], next_root[2])
        pelvis_prior = contract.pelvis_proposal(frozen_next_pelvis)
        rest = runtime.rest_offsets_by_mode[mode].index_select(0, clip_ids)
        frozen_next_base = runtime_data.base_upper_from_lower(
            next_lower, *next_root, full_clip, rest
        )
        upper_prior = upper_data.clean_upper_state(
            frozen_next_base
            + upper_state["current_upper"]
            - upper_state["current_base"]
        )
        roots = runtime.store.get_input_root_features(
            clip_ids, lower_state["cur_idx"]
        )
        feet_current = runtime_data.foot_heading_features(
            runtime.store, lower_state["cur"], current_root[1], current_root[2]
        )
        feet_next = runtime_data.foot_heading_features(
            runtime.store, next_lower, next_root[1], next_root[2]
        )
        controller_input = torch.cat(
            (
                upper_state["previous_upper"],
                upper_prior,
                upper_state["previous_pelvis"],
                upper_state["current_pelvis"],
                pelvis_prior,
                roots,
                torch.full((1, 1), float(mode), dtype=torch.float32, device=device),
                feet_current,
                feet_next,
                gaze_tensor,
            ),
            dim=-1,
        )
        next_upper, next_pelvis, _applied = contract.apply_agent_output(
            upper_prior, pelvis_prior, agent(controller_input)
        )
        next_positions, next_rotations = append_pose(
            int(next_indices.item()),
            next_lower,
            next_upper,
            next_pelvis,
        )
        transition = contract.physical_transition_from_decoded(
            full_clip,
            current_positions,
            current_rotations,
            next_positions,
            next_rotations,
            current_root[0],
            current_root[1],
        )
        current_row = torch.cat((controller_input, transition), dim=-1)
        ae_window = torch.cat((upper_state["context_row"], current_row), dim=-1)
        ae_windows[-1] = ae_window[0].detach().cpu()
        previous_root = runtime_data.root_state(
            runtime, lower_state["cur_idx"] - 1, clip_ids
        )
        ae4_condition = ae4_data.condition_from_decoded_frames(
            full_clip,
            (previous_positions, previous_rotations),
            (current_positions, current_rotations),
            (next_positions, next_rotations),
            (previous_root[0], previous_root[1]),
            (current_root[0], current_root[1]),
            (next_root[0], next_root[1]),
            roots,
            mode,
            gaze_tensor,
        )
        ae4_conditions[-1] = ae4_condition[0].detach().cpu()
        next_lower_feedback = contract.feedback_lower_state(
            runtime.lower_clips[0], next_lower, next_pelvis, *next_root
        )
        controlled_next_base = runtime_data.base_upper_from_lower(
            next_lower_feedback, *next_root, full_clip, rest
        )
        upper_state["previous_upper"] = upper_state["current_upper"]
        upper_state["current_upper"] = next_upper
        upper_state["current_base"] = controlled_next_base
        upper_state["previous_pelvis"] = upper_state["current_pelvis"]
        upper_state["current_pelvis"] = next_pelvis
        upper_state["context_row"] = current_row
        previous_positions, previous_rotations = current_positions, current_rotations
        current_positions, current_rotations = next_positions, next_rotations
        advance_lower(runtime, lower_state, next_lower_feedback, next_indices)

    positions = torch.stack(positions_rows).numpy().astype(np.float32, copy=False)
    rotations = torch.stack(rotations_rows).numpy().astype(np.float32, copy=False)
    target_positions = torch.stack(target_positions_rows).numpy().astype(
        np.float32, copy=False
    )
    target_rotations = torch.stack(target_rotations_rows).numpy().astype(
        np.float32, copy=False
    )
    if not all(
        np.isfinite(value).all()
        for value in (positions, rotations, target_positions, target_rotations)
    ):
        raise RuntimeError("Upper+pelvis checkpoint rollout produced non-finite transforms")
    ae_window_values = np.full(
        (len(ae_windows), WINDOW_DIM), np.nan, dtype=np.float32
    )
    for row_index, values in enumerate(ae_windows):
        if values is not None:
            ae_window_values[row_index] = values.numpy().astype(
                np.float32, copy=False
            )
    ae4_condition_values = np.full(
        (len(ae4_conditions), ae4_data.INPUT_DIM), np.nan, dtype=np.float32
    )
    for row_index, values in enumerate(ae4_conditions):
        if values is not None:
            ae4_condition_values[row_index] = values.numpy().astype(
                np.float32, copy=False
            )
    return runtime_data.UpperPoseRollout(
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
        ae_windows=ae_window_values,
        ae4_conditions=ae4_condition_values,
    )


def resolve_cached_lower_path(metadata: dict[str, Any]) -> Path:
    expected_sha = str(metadata.get("lower_cache_sha256", "")).upper()
    candidates: list[Path] = []
    raw = metadata.get("lower_cache")
    if raw:
        raw_path = Path(str(raw))
        candidates.append(
            raw_path if raw_path.is_absolute() else (PROJECT_ROOT / raw_path)
        )
    cache_root = RUNS_ROOT / "cache" / "upper_cached_lower"
    if cache_root.is_dir():
        candidates.extend(cache_root.glob("*.pt"))
    for candidate in candidates:
        if not candidate.is_file():
            continue
        if expected_sha and sha256_file(candidate) != expected_sha:
            continue
        return candidate.resolve()
    raise FileNotFoundError(
        "The checkpoint's continuous lower cache is unavailable locally "
        f"(expected SHA {expected_sha or 'unspecified'})"
    )


@torch.inference_mode()
def rollout_upper_cached_lower_checkpoint(
    checkpoint_path: Path,
    source_path: Path,
    *,
    gaze: tuple[float, float] = (0.0, 0.0),
    initial_gaze: tuple[float, float] | None = None,
    device: torch.device | str = "cpu",
    max_frames: int | None = None,
    start_frame: int = 2,
    episode_start_noise_seed: int | None = None,
    display_reset_as_frame_zero: bool = False,
    allow_external_viewer_source: bool = False,
) -> runtime_data.UpperPoseRollout:
    """Replay the upper-only controller over its immutable cached lower clip.

    When ``episode_start_noise_seed`` is supplied, the authored current seed is
    perturbed with the exact reset-noise profile stored in the controller
    checkpoint before autoregression starts.  ``display_reset_as_frame_zero``
    hides the two clean history rows so the perturbed reset pose is timeline
    frame zero while retaining those rows as controller context.
    """

    device = torch.device(device)
    checkpoint_path = Path(checkpoint_path).resolve()
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if checkpoint.get("kind") != CACHED_LOWER_CONTROLLER_KIND:
        raise RuntimeError(f"Not a cached-lower upper controller: {checkpoint_path}")
    source = Path(source_path).resolve()
    external_viewer_source = False
    if upper_data.SWORD_ROOT.resolve() in source.parents:
        dataset_root = upper_data.SWORD_ROOT
        mode = runtime_data.MODE_DRAWN
    elif upper_data.ORIGINAL_ROOT.resolve() in source.parents:
        dataset_root = upper_data.ORIGINAL_ROOT
        mode = runtime_data.MODE_SHEATHED
    elif allow_external_viewer_source:
        dataset_root = source.parent
        mode = runtime_data.MODE_SHEATHED
        external_viewer_source = True
    else:
        raise ValueError(f"Replay source is outside matched upper datasets: {source}")
    relative = (
        source.name
        if external_viewer_source
        else source.relative_to(dataset_root.resolve()).as_posix()
    )
    category = runtime_data.CATEGORY_WALK if external_viewer_source else (
        runtime_data.CATEGORY_RUN
        if relative.startswith("run_")
        else runtime_data.CATEGORY_WALK
    )
    gaze_values = (float(gaze[0]), float(gaze[1]))
    if any(not math.isfinite(value) or abs(value) > 1.0 for value in gaze_values):
        raise ValueError(f"Normalized gaze must be finite in [-1,1], got {gaze_values}")
    initial_gaze_values = (
        gaze_values
        if initial_gaze is None
        else (float(initial_gaze[0]), float(initial_gaze[1]))
    )
    if any(
        not math.isfinite(value) or abs(value) > 1.0
        for value in initial_gaze_values
    ):
        raise ValueError(
            "Normalized initialization gaze must be finite in [-1,1], got "
            f"{initial_gaze_values}"
        )
    metadata = dict(checkpoint.get("metadata", {}))
    selected = dict(metadata.get("lower_selection", {})).get(category, {})
    lower_path = Path(str(selected.get("checkpoint", "")))
    if not lower_path.is_absolute():
        lower_path = (PROJECT_ROOT / lower_path).resolve()
    expected_lower_sha = str(selected.get("checkpoint_sha256", "")).upper()
    if not lower_path.is_file() or sha256_file(lower_path) != expected_lower_sha:
        raise RuntimeError(
            f"Frozen lower dependency mismatch for {category}: {lower_path}"
        )
    lower_checkpoint = torch.load(lower_path, map_location="cpu", weights_only=False)
    cfg = runtime_data.apply_checkpoint_config(lower_checkpoint, device)
    probe = tl.MotionClip(
        source if external_viewer_source else upper_data.ORIGINAL_ROOT / relative,
        cfg,
        cyclic_animation=(False if external_viewer_source else runtime_data.is_cyclic(relative)),
    )
    lower_model = visualize.load_model(lower_checkpoint, probe, cfg, device)
    lower_model.eval().requires_grad_(False)
    if external_viewer_source:
        runtime = runtime_data.build_external_viewer_category_runtime(
            category, source, lower_checkpoint, cfg, lower_model, device
        )
        source_stat = source.stat()
        external_cache_key = (
            str(source).casefold(),
            int(source_stat.st_mtime_ns),
            int(source_stat.st_size),
            expected_lower_sha,
            str(device),
        )
        external_payload = _EXTERNAL_VIEWER_LOWER_CACHE.get(external_cache_key)
        if external_payload is None:
            external_payload = cached_lower_data.build_category_cache(
                runtime, lower_path, maximum_k=32
            )
            _EXTERNAL_VIEWER_LOWER_CACHE[external_cache_key] = external_payload
        cache = cached_lower_data.CachedLowerCategory(
            external_payload, runtime, lower_path, device
        )
    else:
        # CategoryRuntime needs the skeleton/store envelope, but the lower model
        # is never evaluated by the normal precomputed-cache replay path.
        runtime = runtime_data.build_category_runtime(
            category, [relative], lower_checkpoint, cfg, lower_model, device
        )
        cache_path = resolve_cached_lower_path(metadata)
        cache = cached_lower_data.load_category(
            cache_path, category, runtime, lower_path, device, maximum_k=32
        )
    agent = UpperCachedLowerAgent().to(device)
    agent.load_state_dict(checkpoint["model"], strict=True)
    agent.eval().requires_grad_(False)
    full_clip = runtime.full_by_mode[mode]
    clip_ids = torch.zeros(1, dtype=torch.long, device=device)
    gaze_tensor = torch.tensor([gaze_values], dtype=torch.float32, device=device)
    initial_gaze_tensor = torch.tensor(
        [initial_gaze_values], dtype=torch.float32, device=device
    )
    start_frame = int(start_frame)
    if start_frame < 2:
        raise ValueError("Cached-lower upper rollout must start at frame 2 or later")
    cache_length = int(cache.cache_lengths[0].item())
    final_index = cache_length - 1
    if not bool(full_clip.cyclic_animation):
        final_index = min(final_index, int(full_clip.T) - 1)
    if max_frames is not None:
        final_index = min(final_index, start_frame - 2 + int(max_frames) - 1)

    seed_indices = torch.tensor(
        [start_frame - 2, start_frame - 1, start_frame],
        dtype=torch.long,
        device=device,
    )
    seed_upper = runtime_data.upper_overlay_runtime_rows(
        runtime,
        mode,
        clip_ids.repeat(3),
        seed_indices,
        initial_gaze_tensor.repeat(3, 1),
        device,
    )
    older_upper, previous_upper, current_upper = seed_upper.split(1, dim=0)
    previous_index = seed_indices[1:2]
    current_index = seed_indices[2:3]
    previous_pelvis = cache.gather("pelvis_heading", clip_ids, previous_index)
    current_pelvis = cache.gather("pelvis_heading", clip_ids, current_index)
    older_pelvis = cache.gather("pelvis_heading", clip_ids, seed_indices[0:1])
    previous_feet = cache.gather("feet_heading", clip_ids, previous_index)
    current_feet = cache.gather("feet_heading", clip_ids, current_index)
    previous_lower_positions = cache.gather(
        "cached_lower_position", clip_ids, previous_index
    )
    previous_lower_rotations = cache.gather(
        "cached_lower_rotation", clip_ids, previous_index
    )
    current_lower_positions = cache.gather(
        "cached_lower_position", clip_ids, current_index
    )
    current_lower_rotations = cache.gather(
        "cached_lower_rotation", clip_ids, current_index
    )
    previous_base = cache.base_upper(mode, clip_ids, previous_index)
    current_base = cache.base_upper(mode, clip_ids, current_index)
    current_noise_pose: tuple[torch.Tensor, torch.Tensor] | None = None
    episode_noise_summary: dict[str, Any] | None = None
    if episode_start_noise_seed is not None:
        raw_profile = metadata.get("episode_start_noise")
        if not isinstance(raw_profile, dict):
            raise RuntimeError(
                "This checkpoint has no episode-start noise profile to replay"
            )
        profile = {
            "probability": float(raw_profile.get("probability", 0.0)),
            "pelvis_rotation_deg_max": float(
                raw_profile.get("pelvis_rotation_deg_max", 0.0)
            ),
            "pelvis_location_cm_max": float(
                raw_profile.get("pelvis_location_cm_max", 0.0)
            ),
            "fk_rotation_deg_max": float(
                raw_profile.get("fk_rotation_deg_max", 0.0)
            ),
            "hand_location_cm_max": float(
                raw_profile.get("hand_location_cm_max", 0.0)
            ),
            "hand_rotation_deg_max": float(
                raw_profile.get("hand_rotation_deg_max", 0.0)
            ),
        }
        if any(
            not math.isfinite(value) or value < 0.0
            for key, value in profile.items()
            if key != "probability"
        ):
            raise RuntimeError(f"Invalid checkpoint episode-noise profile: {profile}")
        if (
            profile["pelvis_rotation_deg_max"] != 0.0
            or profile["pelvis_location_cm_max"] != 0.0
        ):
            raise RuntimeError(
                "Refusing the superseded reset-noise contract: cached-lower "
                "pelvis rotation and location maxima must both be zero"
            )
        generator = torch.Generator(device="cpu")
        generator.manual_seed(int(episode_start_noise_seed))

        def sampled_vectors(shape: tuple[int, ...], maximum: float) -> torch.Tensor:
            directions = tl.normalize(
                torch.randn((*shape, 3), generator=generator, dtype=torch.float32)
            )
            magnitudes = torch.rand(
                (*shape, 1), generator=generator, dtype=torch.float32
            ) * float(maximum)
            return (directions * magnitudes).to(device)

        pelvis_rotation = sampled_vectors(
            (1,), math.radians(profile["pelvis_rotation_deg_max"])
        )
        pelvis_translation = sampled_vectors(
            (1,), profile["pelvis_location_cm_max"] * 0.01
        )
        fk_rotation = sampled_vectors(
            (1, len(EPISODE_NOISE_FK_BONES)),
            math.radians(profile["fk_rotation_deg_max"]),
        )
        hand_translation = sampled_vectors(
            (1, len(EPISODE_NOISE_HAND_BONES)),
            profile["hand_location_cm_max"] * 0.01,
        )
        hand_rotation = sampled_vectors(
            (1, len(EPISODE_NOISE_HAND_BONES)),
            math.radians(profile["hand_rotation_deg_max"]),
        )
        (
            current_upper,
            current_pelvis,
            current_feet,
            current_lower_positions,
            current_lower_rotations,
            noisy_positions,
            noisy_rotations,
        ) = episode_noisy_cached_current_state(
            runtime,
            mode,
            clip_ids,
            cache.gather("lower_vector", clip_ids, current_index),
            current_upper,
            current_pelvis,
            current_feet,
            current_lower_positions,
            current_lower_rotations,
            cache.gather("root_position", clip_ids, current_index),
            cache.gather("root_rotation", clip_ids, current_index),
            cache.gather("heading", clip_ids, current_index),
            torch.ones(1, dtype=torch.bool, device=device),
            pelvis_rotation,
            pelvis_translation,
            fk_rotation,
            hand_translation,
            hand_rotation,
            {
                name: _episode_noise_subtree_indices(full_clip, name).to(device)
                for name in (
                    "pelvis",
                    *EPISODE_NOISE_FK_BONES,
                    *EPISODE_NOISE_HAND_BONES,
                )
            },
        )
        current_noise_pose = (noisy_positions, noisy_rotations)
        episode_noise_summary = {
            "seed": int(episode_start_noise_seed),
            "profile": profile,
            "source_frame": int(start_frame),
            "sampled": {
                "pelvis_rotation_deg": float(
                    torch.linalg.norm(pelvis_rotation[0]).cpu()
                    * (180.0 / math.pi)
                ),
                "pelvis_location_cm": float(
                    torch.linalg.norm(pelvis_translation[0]).cpu() * 100.0
                ),
                "fk_rotation_deg_max": float(
                    torch.linalg.norm(fk_rotation[0], dim=-1).max().cpu()
                    * (180.0 / math.pi)
                ),
                "hand_location_cm_max": float(
                    torch.linalg.norm(hand_translation[0], dim=-1).max().cpu()
                    * 100.0
                ),
                "hand_rotation_deg_max": float(
                    torch.linalg.norm(hand_rotation[0], dim=-1).max().cpu()
                    * (180.0 / math.pi)
                ),
            },
        }
    current_prior = upper_data.clean_upper_state(
        current_base + previous_upper - previous_base
    )
    context_input = torch.cat(
        (
            older_upper,
            current_prior,
            older_pelvis,
            previous_pelvis,
            current_pelvis,
            cache.gather("root_features", clip_ids, previous_index),
            torch.full((1, 1), float(mode), dtype=torch.float32, device=device),
            previous_feet,
            current_feet,
            gaze_tensor,
        ),
        dim=-1,
    )
    local_offsets = runtime.full_geometry_by_mode[mode]["local_offsets"][0:1]
    context_transition = contract.upper_only_physical_transition(
        full_clip,
        previous_upper,
        current_upper,
        cache.gather("root_position", clip_ids, previous_index),
        cache.gather("root_rotation", clip_ids, previous_index),
        cache.gather("heading", clip_ids, previous_index),
        cache.gather("root_position", clip_ids, current_index),
        cache.gather("heading", clip_ids, current_index),
        previous_lower_positions,
        previous_lower_rotations,
        current_lower_positions,
        current_lower_rotations,
        local_offsets=local_offsets,
    )
    context_row = torch.cat((context_input, context_transition), dim=-1)

    positions_rows: list[torch.Tensor] = []
    rotations_rows: list[torch.Tensor] = []
    target_positions_rows: list[torch.Tensor] = []
    target_rotations_rows: list[torch.Tensor] = []
    frame_indices: list[int] = []
    root_positions: list[torch.Tensor] = []
    root_rotations: list[torch.Tensor] = []
    ae_windows: list[torch.Tensor | None] = []
    ae4_conditions: list[torch.Tensor | None] = []

    def append_pose(
        index: int,
        upper: torch.Tensor,
        window: torch.Tensor | None,
        decoded_override: tuple[torch.Tensor, torch.Tensor] | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        tensor_index = torch.tensor([index], dtype=torch.long, device=device)
        lower = cache.gather("lower_vector", clip_ids, tensor_index)
        pelvis_value = cache.gather("pelvis_heading", clip_ids, tensor_index)
        root = (
            cache.gather("root_position", clip_ids, tensor_index),
            cache.gather("root_rotation", clip_ids, tensor_index),
            cache.gather("heading", clip_ids, tensor_index),
        )
        if decoded_override is None:
            position, rotation = decode_rows(
                runtime, mode, lower, upper, pelvis_value, *root, clip_ids
            )
        else:
            position, rotation = decoded_override
        logical = index % int(full_clip.cyclic_period) if full_clip.cyclic_animation else index
        target_position, target_rotation = upper_data.gaze_overlay_global_pose(
            full_clip,
            torch.tensor([logical], dtype=torch.long),
            torch.tensor([gaze_values], dtype=torch.float32),
        )
        positions_rows.append(position[0].cpu())
        rotations_rows.append(rotation[0].cpu())
        target_positions_rows.append(target_position[0].cpu())
        target_rotations_rows.append(target_rotation[0].cpu())
        frame_indices.append(index)
        root_positions.append(root[0][0].cpu())
        root_rotations.append(root[1][0].cpu())
        ae_windows.append(None if window is None else window[0].cpu())
        ae4_conditions.append(None)
        return position, rotation

    append_pose(start_frame - 2, older_upper, None)
    previous_positions, previous_rotations = append_pose(
        start_frame - 1, previous_upper, None
    )
    current_positions, current_rotations = append_pose(
        start_frame, current_upper, None, current_noise_pose
    )
    for next_frame in range(start_frame + 1, final_index + 1):
        next_index = torch.tensor([next_frame], dtype=torch.long, device=device)
        next_pelvis = cache.gather("pelvis_heading", clip_ids, next_index)
        next_feet = cache.gather("feet_heading", clip_ids, next_index)
        next_base = cache.base_upper(mode, clip_ids, next_index)
        upper_prior = upper_data.clean_upper_state(next_base + current_upper - current_base)
        controller_input = torch.cat(
            (
                previous_upper,
                upper_prior,
                previous_pelvis,
                current_pelvis,
                next_pelvis,
                cache.gather("root_features", clip_ids, current_index),
                torch.full((1, 1), float(mode), dtype=torch.float32, device=device),
                current_feet,
                next_feet,
                gaze_tensor,
            ),
            dim=-1,
        )
        next_upper = upper_data.clean_upper_state(upper_prior + agent(controller_input))
        physical = contract.upper_only_physical_transition(
            full_clip,
            current_upper,
            next_upper,
            cache.gather("root_position", clip_ids, current_index),
            cache.gather("root_rotation", clip_ids, current_index),
            cache.gather("heading", clip_ids, current_index),
            cache.gather("root_position", clip_ids, next_index),
            cache.gather("heading", clip_ids, next_index),
            current_lower_positions,
            current_lower_rotations,
            cache.gather("cached_lower_position", clip_ids, next_index),
            cache.gather("cached_lower_rotation", clip_ids, next_index),
            local_offsets=local_offsets,
        )
        current_row = torch.cat((controller_input, physical), dim=-1)
        window = torch.cat((context_row, current_row), dim=-1)
        next_positions, next_rotations = append_pose(next_frame, next_upper, window)
        previous_root = (
            cache.gather("root_position", clip_ids, current_index - 1),
            cache.gather("root_rotation", clip_ids, current_index - 1),
        )
        current_root = (
            cache.gather("root_position", clip_ids, current_index),
            cache.gather("root_rotation", clip_ids, current_index),
        )
        next_root = (
            cache.gather("root_position", clip_ids, next_index),
            cache.gather("root_rotation", clip_ids, next_index),
        )
        ae4_condition = ae4_data.condition_from_decoded_frames(
            full_clip,
            (previous_positions, previous_rotations),
            (current_positions, current_rotations),
            (next_positions, next_rotations),
            previous_root,
            current_root,
            next_root,
            cache.gather("root_features", clip_ids, current_index),
            mode,
            gaze_tensor,
        )
        ae4_conditions[-1] = ae4_condition[0].cpu()
        previous_upper = current_upper
        current_upper = next_upper
        previous_pelvis = current_pelvis
        current_pelvis = next_pelvis
        current_base = next_base
        current_feet = next_feet
        current_lower_positions = cache.gather(
            "cached_lower_position", clip_ids, next_index
        )
        current_lower_rotations = cache.gather(
            "cached_lower_rotation", clip_ids, next_index
        )
        current_index = next_index
        context_row = current_row
        previous_positions, previous_rotations = current_positions, current_rotations
        current_positions, current_rotations = next_positions, next_rotations

    positions = torch.stack(positions_rows).numpy().astype(np.float32, copy=False)
    rotations = torch.stack(rotations_rows).numpy().astype(np.float32, copy=False)
    target_positions = torch.stack(target_positions_rows).numpy().astype(np.float32, copy=False)
    target_rotations = torch.stack(target_rotations_rows).numpy().astype(np.float32, copy=False)
    window_values = np.full((len(ae_windows), WINDOW_DIM), np.nan, dtype=np.float32)
    for row, values in enumerate(ae_windows):
        if values is not None:
            window_values[row] = values.numpy().astype(np.float32, copy=False)
    ae4_condition_values = np.full(
        (len(ae4_conditions), ae4_data.INPUT_DIM), np.nan, dtype=np.float32
    )
    for row, values in enumerate(ae4_conditions):
        if values is not None:
            ae4_condition_values[row] = values.numpy().astype(
                np.float32, copy=False
            )
    if display_reset_as_frame_zero:
        if episode_noise_summary is None:
            raise ValueError(
                "display_reset_as_frame_zero requires episode_start_noise_seed"
            )
        history_rows = 2
        positions = positions[history_rows:]
        rotations = rotations[history_rows:]
        target_positions = target_positions[history_rows:]
        target_rotations = target_rotations[history_rows:]
        window_values = window_values[history_rows:]
        ae4_condition_values = ae4_condition_values[history_rows:]
        frame_indices = frame_indices[history_rows:]
        root_positions = root_positions[history_rows:]
        root_rotations = root_rotations[history_rows:]
    return runtime_data.UpperPoseRollout(
        checkpoint_path=checkpoint_path,
        checkpoint_kind=CACHED_LOWER_CONTROLLER_KIND,
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
        root_positions=(
            torch.stack(root_positions).numpy().astype(np.float32, copy=False)
            if root_positions and torch.is_tensor(root_positions[0])
            else np.asarray(root_positions, dtype=np.float32)
        ),
        root_rotations=(
            torch.stack(root_rotations).numpy().astype(np.float32, copy=False)
            if root_rotations and torch.is_tensor(root_rotations[0])
            else np.asarray(root_rotations, dtype=np.float32)
        ),
        cfg=runtime.cfg,
        clip=full_clip,
        ae_windows=window_values,
        ae4_conditions=ae4_condition_values,
        episode_start_noise=episode_noise_summary,
        initial_gaze=initial_gaze_values,
    )


@torch.inference_mode()
def rollout_frozen_lower_for_ae22(
    source_path: Path,
    *,
    gaze: tuple[float, float] = (0.0, 0.0),
    ae22_checkpoint_path: Path | None = None,
    conditioning_source: str = "frozen_lower",
    device: torch.device | str = "cpu",
    max_frames: int | None = None,
    start_frame: int = 2,
) -> runtime_data.UpperPoseRollout:
    """Temporal AE22 preview driven by authored or frozen-policy lower motion.

    The upper physical pose is seeded from authored frames and then consists
    exclusively of chained AE22 suggestions; no upper controller is loaded or
    evaluated. ``conditioning_source`` changes only the lower trajectory.
    """

    device = torch.device(device)
    conditioning_source = str(conditioning_source).strip().lower()
    if conditioning_source not in {"gt_lower", "frozen_lower"}:
        raise ValueError(f"Unknown AE22 lower conditioning: {conditioning_source}")
    source = Path(source_path).resolve()
    if upper_data.SWORD_ROOT.resolve() in source.parents:
        dataset_root = upper_data.SWORD_ROOT
        mode = runtime_data.MODE_DRAWN
    elif upper_data.ORIGINAL_ROOT.resolve() in source.parents:
        dataset_root = upper_data.ORIGINAL_ROOT
        mode = runtime_data.MODE_SHEATHED
    else:
        raise ValueError(f"AE22 source is outside matched upper datasets: {source}")
    relative = source.relative_to(dataset_root.resolve()).as_posix()
    category = (
        runtime_data.CATEGORY_RUN
        if relative.startswith("run_")
        else runtime_data.CATEGORY_WALK
    )
    lower_path, _pointer = runtime_data.resolve_pointer(
        runtime_data.WALK_POINTER
        if category == runtime_data.CATEGORY_WALK
        else runtime_data.RUN_POINTER,
        runtime_data.EXPECTED_WALK_SHA256
        if category == runtime_data.CATEGORY_WALK
        else runtime_data.EXPECTED_RUN_SHA256,
    )
    lower_checkpoint = torch.load(lower_path, map_location="cpu", weights_only=False)
    cfg = runtime_data.apply_checkpoint_config(lower_checkpoint, device)
    probe = tl.MotionClip(
        upper_data.ORIGINAL_ROOT / relative,
        cfg,
        cyclic_animation=runtime_data.is_cyclic(relative),
    )
    lower_model = visualize.load_model(lower_checkpoint, probe, cfg, device)
    lower_model.eval().requires_grad_(False)
    runtime = runtime_data.build_category_runtime(
        category, [relative], lower_checkpoint, cfg, lower_model, device
    )
    if ae22_checkpoint_path is None:
        ae22_checkpoint_path = resolve_ae22_path(None)
    ae22_model, ae22_mean, ae22_std, ae22_checkpoint = load_ae22(
        Path(ae22_checkpoint_path).resolve(), device
    )
    full_clip = runtime.full_by_mode[mode]
    lower_clip = runtime.lower_clips[0]
    clip_ids = torch.zeros(1, dtype=torch.long, device=device)
    starts = torch.tensor([int(start_frame)], dtype=torch.long, device=device)
    lower_state = runtime_data.lower_initial_state(runtime, starts)
    gaze_values = (float(gaze[0]), float(gaze[1]))
    gaze_tensor = torch.tensor([gaze_values], dtype=torch.float32, device=device)

    seed_indices = torch.tensor(
        [int(start_frame) - 2, int(start_frame) - 1, int(start_frame)],
        dtype=torch.long,
        device=device,
    )
    seed_upper = runtime_data.upper_overlay_runtime_rows(
        runtime, mode, clip_ids.repeat(3), seed_indices, gaze_tensor.repeat(3, 1), device
    )
    seed_lower = (lower_state["older"], lower_state["prev"], lower_state["cur"])
    seed_physical: list[torch.Tensor] = []
    positions_rows: list[torch.Tensor] = []
    rotations_rows: list[torch.Tensor] = []
    target_positions_rows: list[torch.Tensor] = []
    target_rotations_rows: list[torch.Tensor] = []
    root_positions: list[torch.Tensor] = []
    root_rotations: list[torch.Tensor] = []
    frame_indices: list[int] = []
    ae_windows: list[torch.Tensor] = []

    def target_pose(frame: int) -> tuple[torch.Tensor, torch.Tensor]:
        logical = frame % int(full_clip.cyclic_period) if full_clip.cyclic_animation else frame
        return upper_data.gaze_overlay_global_pose(
            full_clip,
            torch.tensor([logical], dtype=torch.long),
            gaze_tensor.detach().cpu(),
        )

    def rebuild_lower_arms(
        position: torch.Tensor,
        rotation: torch.Tensor,
        reference_rotation: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Rebuild the two unscored elbow transforms for faithful collider display."""

        by_name = {name: index for index, name in enumerate(full_clip.body_names)}
        result_position = position.clone()
        result_rotation = rotation.clone()
        offsets = full_clip.local_offsets.to(device=device, dtype=torch.float32)
        for side in ("l", "r"):
            upper_index = by_name[f"upperarm_{side}"]
            lower_index = by_name[f"lowerarm_{side}"]
            hand_index = by_name[f"hand_{side}"]
            result_position[:, lower_index] = (
                offsets[lower_index].view(1, 1, 3)
                @ result_rotation[:, upper_index]
            ).squeeze(1) + result_position[:, upper_index]
            local_axis = offsets[hand_index].view(1, 3).expand(len(position), -1)
            world_axis = result_position[:, hand_index] - result_position[:, lower_index]
            result_rotation[:, lower_index] = tl.rotation_from_axis_with_reference(
                local_axis,
                world_axis,
                reference_rotation[:, lower_index],
            )
        return result_position, result_rotation

    for frame, lower, upper in zip(
        range(int(start_frame) - 2, int(start_frame) + 1), seed_lower, seed_upper
    ):
        index = torch.tensor([frame], dtype=torch.long, device=device)
        root = runtime_data.root_state(runtime, index, clip_ids)
        pelvis = pelvis_heading(lower, root[1], root[2])
        position, rotation = decode_rows(
            runtime, mode, lower, upper.unsqueeze(0), pelvis, *root, clip_ids
        )
        physical_pose = contract.physical_pose_from_globals(
            full_clip, position, rotation, root[0], root[1]
        )
        seed_physical.append(physical_pose)
        truth_position, truth_rotation = target_pose(frame)
        positions_rows.append(position[0].cpu())
        rotations_rows.append(rotation[0].cpu())
        target_positions_rows.append(truth_position[0].cpu())
        target_rotations_rows.append(truth_rotation[0].cpu())
        root_positions.append(root[0][0].cpu())
        root_rotations.append(root[1][0].cpu())
        frame_indices.append(frame)
        ae_windows.append(torch.full((WINDOW_DIM,), float("nan")))

    previous_physical = seed_physical[-2]
    current_physical = seed_physical[-1]
    final_index = (
        int(full_clip.cyclic_period) - 1
        if full_clip.cyclic_animation
        else int(full_clip.T) - int(runtime.cfg.future_window) - 1
    )
    if max_frames is not None:
        final_index = min(final_index, int(start_frame) - 2 + int(max_frames) - 1)

    while int(lower_state["cur_idx"].item()) < final_index:
        current_index = lower_state["cur_idx"]
        next_index = current_index + 1
        if conditioning_source == "frozen_lower":
            next_lower = lower_next_live(runtime, lower_state)
        else:
            next_lower, _next_pelvis_raw, _next_payload = lower_ctl.target_state(
                runtime.store, clip_ids, next_index
            )
        previous_root = runtime_data.root_state(runtime, current_index - 1, clip_ids)
        current_root = runtime_data.root_state(runtime, current_index, clip_ids)
        next_root = runtime_data.root_state(runtime, next_index, clip_ids)
        previous_pelvis = pelvis_heading(
            lower_state["prev"], previous_root[1], previous_root[2]
        )
        current_pelvis = pelvis_heading(
            lower_state["cur"], current_root[1], current_root[2]
        )
        next_pelvis = pelvis_heading(next_lower, next_root[1], next_root[2])
        roots = runtime.store.get_input_root_features(clip_ids, current_index)
        feet_current = runtime_data.foot_heading_features(
            runtime.store, lower_state["cur"], current_root[1], current_root[2]
        )
        feet_next = runtime_data.foot_heading_features(
            runtime.store, next_lower, next_root[1], next_root[2]
        )
        controls = torch.cat(
            (
                previous_pelvis,
                current_pelvis,
                next_pelvis,
                roots,
                torch.full((1, 1), float(mode), device=device),
                feet_current,
                feet_next,
                gaze_tensor,
            ),
            dim=-1,
        )
        # AE22's controls are the controller input after its two 90D upper blocks.
        if int(controls.shape[-1]) != int(ae22_data.CONTROL_DIM):
            raise RuntimeError(
                f"Frozen-lower AE22 controls are {controls.shape[-1]}, expected {ae22_data.CONTROL_DIM}"
            )
        row = torch.cat(
            (
                torch.zeros_like(current_physical),
                previous_physical,
                current_physical,
                controls,
            ),
            dim=-1,
        )
        normalized_delta = ae22_model((row - ae22_mean) / ae22_std)[
            :, : contract.PHYSICAL_DIM
        ]
        delta = (
            normalized_delta * ae22_std[: contract.PHYSICAL_DIM]
            + ae22_mean[: contract.PHYSICAL_DIM]
        )
        proposed_current_root = contract.clean_physical_pose(current_physical + delta)
        proposed_next_root = contract.reframe_physical_pose(
            proposed_current_root,
            current_root[0],
            current_root[1],
            next_root[0],
            next_root[1],
        )
        shaped = proposed_next_root.reshape(
            1, len(contract.PHYSICAL_BONES), contract.TRANSFORM_DIM
        )
        physical_positions = (
            torch.matmul(shaped[..., :3].unsqueeze(-2), next_root[1][:, None])
            .squeeze(-2)
            + next_root[0][:, None]
        )
        physical_rotations = (
            tl.rotation_6d_to_matrix(shaped[..., 3:9].reshape(-1, 6)).reshape(
                1, len(contract.PHYSICAL_BONES), 3, 3
            )
            @ next_root[1][:, None]
        )
        # Start from the frozen-lower pose, then overlay all physical AE22 transforms.
        authored_upper = runtime_data.upper_overlay_runtime_rows(
            runtime, mode, clip_ids, next_index, gaze_tensor, device
        )
        base_position, base_rotation = decode_rows(
            runtime,
            mode,
            next_lower,
            authored_upper,
            next_pelvis,
            *next_root,
            clip_ids,
        )
        indices = contract.physical_indices(full_clip).to(device)
        position = base_position.index_copy(1, indices, physical_positions)
        rotation = base_rotation.index_copy(1, indices, physical_rotations)
        # The temporal viewer's reference uses the same selected lower source:
        # authored lower for GT mode, or the frozen lower-policy trajectory.
        # Its upper body remains the authored gaze-overlay target.
        reference_position = base_position
        reference_rotation = base_rotation
        position, rotation = rebuild_lower_arms(
            position, rotation, reference_rotation
        )
        positions_rows.append(position[0].cpu())
        rotations_rows.append(rotation[0].cpu())
        target_positions_rows.append(reference_position[0].cpu())
        target_rotations_rows.append(reference_rotation[0].cpu())
        root_positions.append(next_root[0][0].cpu())
        root_rotations.append(next_root[1][0].cpu())
        frame_indices.append(int(next_index.item()))
        ae_windows.append(torch.full((WINDOW_DIM,), float("nan")))
        next_previous = contract.reframe_physical_pose(
            current_physical,
            current_root[0],
            current_root[1],
            next_root[0],
            next_root[1],
        )
        previous_physical = next_previous
        current_physical = proposed_next_root
        advance_lower(runtime, lower_state, next_lower, next_index)

    return runtime_data.UpperPoseRollout(
        checkpoint_path=Path(ae22_checkpoint_path).resolve(),
        checkpoint_kind=str(ae22_checkpoint.get("kind", "upper_pelvis_root_ae22_condition_only")),
        source_path=source,
        category=category,
        mode=mode,
        gaze=gaze_values,
        step=int(ae22_checkpoint.get("step", -1)),
        fps=float(full_clip.fps),
        positions=torch.stack(positions_rows).numpy().astype(np.float32, copy=False),
        rotations=torch.stack(rotations_rows).numpy().astype(np.float32, copy=False),
        target_positions=torch.stack(target_positions_rows).numpy().astype(np.float32, copy=False),
        target_rotations=torch.stack(target_rotations_rows).numpy().astype(np.float32, copy=False),
        frame_indices=np.asarray(frame_indices, dtype=np.int32),
        root_positions=torch.stack(root_positions).numpy().astype(np.float32, copy=False),
        root_rotations=torch.stack(root_rotations).numpy().astype(np.float32, copy=False),
        cfg=runtime.cfg,
        clip=full_clip,
        ae_windows=np.stack([value.numpy() for value in ae_windows]).astype(np.float32),
        ae4_conditions=None,
    )


def resolve_ae_path(value: str | None) -> Path:
    expected_hash = ""
    if value:
        path = Path(value).resolve()
    else:
        pointer = json.loads(AE_POINTER.read_text(encoding="utf-8"))
        path = Path(str(pointer["checkpoint"]))
        expected_hash = str(pointer.get("checkpoint_sha256", "")).upper()
        if not path.is_absolute():
            path = (PROJECT_ROOT / path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    if expected_hash:
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"Accepted AE1 hash mismatch: expected={expected_hash} actual={actual_hash}"
            )
    return path


@torch.inference_mode()
def authored_ae_window(
    source_path: Path,
    target_frame: int,
    *,
    gaze: tuple[float, float] = (0.0, 0.0),
    has_sword: float = -1.0,
    cyclic_animation: bool = True,
    device: torch.device | str = "cpu",
) -> torch.Tensor:
    """Build the exact AE1 window whose newest output proposes target_frame."""

    target_frame = int(target_frame)
    if target_frame < 2:
        raise ValueError("AE1 proposal needs two preceding authored frames")
    device = torch.device(device)
    cfg = upper_data.motion_config()
    full_clip = tl.MotionClip(
        Path(source_path), cfg, cyclic_animation=bool(cyclic_animation)
    )
    lower_cfg = upper_data.motion_config()
    lower_cfg.body_mode = tl.BODY_MODE_LOWER
    lower_clip = tl.MotionClip(
        Path(source_path), lower_cfg, cyclic_animation=bool(cyclic_animation)
    )
    first_current = torch.tensor([target_frame - 2], dtype=torch.long)
    gaze_tensor = torch.tensor(
        [[float(gaze[0]), float(gaze[1])]], dtype=torch.float32
    )
    if not bool(torch.isfinite(gaze_tensor).all()) or bool(
        torch.any(gaze_tensor.abs() > 1.0)
    ):
        raise ValueError(f"Normalized gaze must be finite in [-1,1], got {gaze}")
    base = upper_data.fk_base_upper_from_clip(full_clip)
    pelvis = upper_data.pelvis_root_features(full_clip)
    feet = upper_data.feet_root_features(full_clip)
    deltas = contract.authored_decoded_two_row_deltas(
        full_clip, lower_clip, cfg, first_current, gaze_tensor
    )
    rows: list[torch.Tensor] = []
    for current, delta in zip(
        (first_current, first_current + 1), deltas
    ):
        controller = upper_data.controller_rows(
            full_clip,
            cfg,
            current,
            gaze_tensor,
            float(has_sword),
            base,
            pelvis,
            feet,
        )[:, :INPUT_DIM]
        rows.append(torch.cat((controller, delta), dim=-1))
    window = torch.cat(rows, dim=-1)
    if tuple(window.shape) != (1, WINDOW_DIM):
        raise RuntimeError(f"Authored AE1 window mismatch: {tuple(window.shape)}")
    return window.to(device=device, dtype=torch.float32)


@torch.inference_mode()
def authored_ae_windows(
    source_path: Path,
    *,
    gaze: tuple[float, float] = (0.0, 0.0),
    has_sword: float = -1.0,
    cyclic_animation: bool = True,
    device: torch.device | str = "cpu",
) -> torch.Tensor:
    """Build all exact fixed-gaze AE1 proposal windows for an authored clip."""

    device = torch.device(device)
    cfg = upper_data.motion_config()
    full_clip = tl.MotionClip(
        Path(source_path), cfg, cyclic_animation=bool(cyclic_animation)
    )
    lower_cfg = upper_data.motion_config()
    lower_cfg.body_mode = tl.BODY_MODE_LOWER
    lower_clip = tl.MotionClip(
        Path(source_path), lower_cfg, cyclic_animation=bool(cyclic_animation)
    )
    target_count = int(full_clip.T) - 2
    result = torch.full(
        (int(full_clip.T), WINDOW_DIM), float("nan"), dtype=torch.float32
    )
    if target_count <= 0:
        return result.to(device)
    first_current = torch.arange(target_count, dtype=torch.long)
    gaze_row = torch.tensor(
        [[float(gaze[0]), float(gaze[1])]], dtype=torch.float32
    )
    if not bool(torch.isfinite(gaze_row).all()) or bool(
        torch.any(gaze_row.abs() > 1.0)
    ):
        raise ValueError(f"Normalized gaze must be finite in [-1,1], got {gaze}")
    gaze_tensor = gaze_row.repeat(target_count, 1)
    base = upper_data.fk_base_upper_from_clip(full_clip)
    pelvis = upper_data.pelvis_root_features(full_clip)
    feet = upper_data.feet_root_features(full_clip)
    deltas = contract.authored_decoded_two_row_deltas(
        full_clip, lower_clip, cfg, first_current, gaze_tensor
    )
    rows: list[torch.Tensor] = []
    for current, delta in zip(
        (first_current, first_current + 1), deltas
    ):
        controller = upper_data.controller_rows(
            full_clip,
            cfg,
            current,
            gaze_tensor,
            float(has_sword),
            base,
            pelvis,
            feet,
        )[:, :INPUT_DIM]
        rows.append(torch.cat((controller, delta), dim=-1))
    windows = torch.cat(rows, dim=-1)
    if tuple(windows.shape) != (target_count, WINDOW_DIM):
        raise RuntimeError(f"Authored AE1 windows mismatch: {tuple(windows.shape)}")
    result[2:] = windows
    return result.to(device=device, dtype=torch.float32)


def checkpoint_schema() -> dict[str, Any]:
    return {
        "name": "upper_pelvis_controller",
        "input_dim": INPUT_DIM,
        "output_dim": OUTPUT_DIM,
        "output_segments": {
            "upper_pose_delta": [0, upper_data.OUTPUT_DIM],
            "pelvis_transform_delta": [upper_data.OUTPUT_DIM, OUTPUT_DIM],
        },
        "physical_ae1_output_dim": contract.PHYSICAL_DIM,
        "physical_bones": list(contract.PHYSICAL_BONES),
        "feet": "frozen_full_transforms_from_lower_agent",
        "leg_ik": "direct_unclamped_two_bone_sampled_pole",
    }


def cached_lower_checkpoint_schema() -> dict[str, Any]:
    return {
        "name": "upper_cached_lower_controller",
        "input_dim": INPUT_DIM,
        "output_dim": upper_data.OUTPUT_DIM,
        "output_segments": {
            "upper_pose_delta": [0, upper_data.OUTPUT_DIM],
        },
        "pelvis_output": "removed",
        "pelvis_source": "continuous_frozen_lower_cache",
        "physical_ae1_output_dim": contract.PHYSICAL_DIM,
        "physical_bones": list(contract.PHYSICAL_BONES),
        "ae1_scored_bones": list(contract.SCORED_UPPER_PHYSICAL_BONES),
        "ae1_conditioning_only_bones": list(contract.CACHED_LOWER_PHYSICAL_BONES),
        "feet": "continuous_frozen_lower_cache_not_ae_output",
        "lower_rollout": "one_continuous_pass_from_frame_zero_per_clip",
        "lower_inference_in_training_hot_loop": False,
        "leg_fk_ik_in_training_hot_loop": False,
    }


def exact_training_rollout_payload(
    run_id: str,
    step: int,
    prototype: tl.MotionClip,
    rows: list[dict[str, Any]],
    positions: torch.Tensor,
    rotations: torch.Tensor,
    root_positions: torch.Tensor,
    root_rotations: torch.Tensor,
    source_frames: torch.Tensor,
) -> dict[str, Any]:
    row_count = len(rows)
    frame_count = int(positions.shape[1])
    if tuple(positions.shape[:2]) != (row_count, frame_count):
        raise RuntimeError("Upper pelvis replay position rows changed")
    if tuple(rotations.shape[:2]) != (row_count, frame_count):
        raise RuntimeError("Upper pelvis replay rotation rows changed")
    if tuple(root_positions.shape[:2]) != (row_count, frame_count):
        raise RuntimeError("Upper pelvis replay root-position rows changed")
    if tuple(root_rotations.shape[:2]) != (row_count, frame_count):
        raise RuntimeError("Upper pelvis replay root-rotation rows changed")
    if tuple(source_frames.shape) != (row_count, frame_count):
        raise RuntimeError("Upper pelvis replay source-frame rows changed")
    if not all(
        bool(torch.isfinite(value).all())
        for value in (positions, rotations, root_positions, root_rotations)
    ):
        raise RuntimeError("Upper pelvis replay contains non-finite transforms")
    group_counts: dict[str, int] = {}
    for row in rows:
        group = (
            f"{row['locomotion_category']}_"
            f"{'drawn' if bool(row['has_sword']) else 'sheathed'}"
        )
        group_counts[group] = group_counts.get(group, 0) + 1
    return {
        "schema_version": 2,
        "computed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
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
        "basis": rotations.tolist(),
        "controller_root_pos": root_positions.tolist(),
        "controller_root_rot": root_rotations.tolist(),
        "frozen_root_pos": root_positions.tolist(),
        "frozen_root_rot": root_rotations.tolist(),
        "source_frame": source_frames.tolist(),
        "source_clip_name": [
            [str(row["clip_name"])] * frame_count for row in rows
        ],
        "metadata": {
            "body_mode": "full",
            "checkpoint_kind": CONTROLLER_KIND,
            "capture_source": "exact_training_microbatch",
            "source_contract": (
                "exact physical microbatch copied from the real upper+pelvis "
                "training pass; no checkpoint rerun or row substitution"
            ),
            "group_counts": group_counts,
            "row_count": row_count,
            "frame_count": frame_count,
        },
        "message": "Loaded the exact latest upper+pelvis training rollout.",
    }


def save_checkpoint(
    path: Path,
    model: UpperPelvisAgent,
    optimizer: torch.optim.Optimizer,
    step: int,
    best: float,
    elapsed_seconds: float,
    maximum_k: int,
    metadata: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(
        {
            "kind": CONTROLLER_KIND,
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "step": int(step),
            "best": float(best),
            "elapsed_seconds": float(elapsed_seconds),
            "rollout_k": int(maximum_k),
            "schema": checkpoint_schema(),
            "metadata": metadata,
        },
        temporary,
    )
    os.replace(temporary, path)


def save_cached_lower_checkpoint(
    path: Path,
    model: UpperCachedLowerAgent,
    optimizer: torch.optim.Optimizer,
    step: int,
    best: float,
    elapsed_seconds: float,
    maximum_k: int,
    metadata: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(
        {
            "kind": CACHED_LOWER_CONTROLLER_KIND,
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "step": int(step),
            "best": float(best),
            "elapsed_seconds": float(elapsed_seconds),
            "rollout_k": int(maximum_k),
            "schema": cached_lower_checkpoint_schema(),
            "metadata": metadata,
        },
        temporary,
    )
    os.replace(temporary, path)


def direct_mse_static_rollout(
    agent: UpperPelvisAgent,
    runtime: runtime_data.CategoryRuntime,
    mode: float,
    starts: torch.Tensor,
    effective_k: torch.Tensor,
    maximum_k: int,
    upper_targets: torch.Tensor,
    pelvis_targets: torch.Tensor,
    debug_lower: torch.Tensor | None = None,
    debug_upper: torch.Tensor | None = None,
    debug_pelvis: torch.Tensor | None = None,
    debug_frames: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """GPU-only fixed-shape rollout used by the direct-MSE CUDA graph.

    The experiment has one clip, one sword mode and neutral gaze.  Authored
    upper targets are therefore a permanent GPU table and every lookup here is
    an ``index_select``.  Physical pose decoding is deliberately absent: it is
    neither an input to nor a term of the requested direct state-space MSE.
    """

    batch = int(starts.numel())
    clip_ids = torch.zeros_like(starts)
    store = runtime.store
    lower_clip = runtime.lower_clips[0]
    full_clip = runtime.full_by_mode[mode]
    rest = runtime.rest_offsets_by_mode[mode][0]
    payload = lower_ctl.payload_slice(store)
    gaze = torch.zeros((batch, 2), dtype=torch.float32, device=starts.device)
    sword = torch.full(
        (batch, 1), float(mode), dtype=torch.float32, device=starts.device
    )

    older = store.get_target_output(clip_ids, starts - 2)
    previous = store.get_target_output(clip_ids, starts - 1)
    current = store.get_target_output(clip_ids, starts)
    previous_upper = upper_targets.index_select(0, starts - 1)
    current_upper = upper_targets.index_select(0, starts)
    previous_root = runtime_data.root_state(runtime, starts - 1, clip_ids)
    current_root = runtime_data.root_state(runtime, starts, clip_ids)
    previous_pelvis = pelvis_heading(previous, previous_root[1], previous_root[2])
    current_pelvis = pelvis_heading(current, current_root[1], current_root[2])
    current_base = runtime_data.base_upper_from_lower(
        current, *current_root, full_clip, rest
    )
    previous_lower_pelvis = previous[:, :3]
    current_lower_pelvis = current[:, :3]
    previous_payload = previous[:, payload]
    current_payload = current[:, payload]

    if debug_lower is not None:
        assert debug_upper is not None and debug_pelvis is not None
        assert debug_frames is not None
        debug_lower[:, 0].copy_(current.detach())
        debug_upper[:, 0].copy_(current_upper.detach())
        debug_pelvis[:, 0].copy_(current_pelvis.detach())
        debug_frames[:, 0].copy_(starts)

    total = agent.delta_head.weight.new_zeros(())
    upper_total = total.clone()
    pelvis_total = total.clone()
    effective_float = effective_k.to(dtype=torch.float32)
    for rollout_step in range(int(maximum_k)):
        values = lower_ctl.build_controller_input(
            store,
            clip_ids,
            starts + rollout_step,
            previous,
            current,
            previous_lower_pelvis,
            current_lower_pelvis,
            previous_payload,
            current_payload,
        )
        raw_lower = lower_ctl.model_raw_output(
            runtime.model, values, current, store
        )
        transition_lower = lower_ctl.clean_output_vector(
            raw_lower, store, current, previous
        )
        next_lower, _unused_pelvis, _unused_payload = (
            lower_ctl.advance_transition_state(
                store, clip_ids, starts + rollout_step, transition_lower
            )
        )
        next_indices = starts + rollout_step + 1
        next_root = runtime_data.root_state(runtime, next_indices, clip_ids)
        frozen_next_pelvis = pelvis_heading(
            next_lower, next_root[1], next_root[2]
        )
        pelvis_prior = contract.pelvis_proposal(frozen_next_pelvis)
        frozen_next_base = runtime_data.base_upper_from_lower(
            next_lower, *next_root, full_clip, rest
        )
        upper_prior = upper_data.clean_upper_state(
            frozen_next_base + current_upper - current_base
        )
        roots = store.get_input_root_features(
            clip_ids, starts + rollout_step
        )
        feet_current = runtime_data.foot_heading_features(
            store, current, current_root[1], current_root[2]
        )
        feet_next = runtime_data.foot_heading_features(
            store, next_lower, next_root[1], next_root[2]
        )
        controller_input = torch.cat(
            (
                previous_upper,
                upper_prior,
                previous_pelvis,
                current_pelvis,
                pelvis_prior,
                roots,
                sword,
                feet_current,
                feet_next,
                gaze,
            ),
            dim=-1,
        )
        next_upper, next_pelvis, _applied = contract.apply_agent_output(
            upper_prior, pelvis_prior, agent(controller_input)
        )
        target_upper = upper_targets.index_select(0, next_indices)
        target_pelvis = pelvis_targets.index_select(0, next_indices)
        upper_row = (next_upper - target_upper).square().mean(dim=-1)
        pelvis_row = (next_pelvis - target_pelvis).square().mean(dim=-1)
        row = torch.cat(
            (next_upper - target_upper, next_pelvis - target_pelvis), dim=-1
        ).square().mean(dim=-1)
        active = (effective_k > rollout_step).to(dtype=row.dtype)
        weight = active / effective_float
        total = total + (row * weight).mean()
        upper_total = upper_total + (upper_row * weight).mean()
        pelvis_total = pelvis_total + (pelvis_row * weight).mean()

        next_feedback = contract.feedback_lower_state(
            lower_clip, next_lower, next_pelvis, *next_root
        )
        controlled_next_base = runtime_data.base_upper_from_lower(
            next_feedback, *next_root, full_clip, rest
        )
        previous = current
        current = next_feedback
        previous_lower_pelvis = current_lower_pelvis
        current_lower_pelvis = current[:, :3]
        previous_payload = current_payload
        current_payload = current[:, payload]
        previous_upper = current_upper
        current_upper = next_upper
        previous_pelvis = current_pelvis
        current_pelvis = next_pelvis
        current_base = controlled_next_base
        current_root = next_root
        if debug_lower is not None:
            debug_lower[:, rollout_step + 1].copy_(current.detach())
            debug_upper[:, rollout_step + 1].copy_(current_upper.detach())
            debug_pelvis[:, rollout_step + 1].copy_(current_pelvis.detach())
            debug_frames[:, rollout_step + 1].copy_(next_indices)
    return total, upper_total, pelvis_total


def prepare_authored_pose_tables(
    runtime: runtime_data.CategoryRuntime,
) -> dict[float, dict[str, torch.Tensor]]:
    """Pack the authored full-body corpus once for capture-safe GPU lookup."""

    device = runtime.store.device
    tables: dict[float, dict[str, torch.Tensor]] = {}
    expected_total = int(runtime.store.target_output.shape[0])
    for mode in runtime_data.MODE_ORDER:
        clips = runtime.full_clips_by_mode[mode]
        if len(clips) != len(runtime.lower_clips):
            raise RuntimeError(
                f"Full/lower clip count mismatch for {runtime.name}/{mode}: "
                f"{len(clips)} != {len(runtime.lower_clips)}"
            )
        for relative, lower_clip, full_clip in zip(
            runtime.relatives, runtime.lower_clips, clips
        ):
            if int(lower_clip.T) != int(full_clip.T):
                raise RuntimeError(
                    f"Matched clip frame mismatch for {relative}: "
                    f"lower={lower_clip.T} full={full_clip.T}"
                )
        packed = {
            "global_pos": torch.cat([clip.global_pos for clip in clips], dim=0),
            "global_rot": torch.cat([clip.global_rot for clip in clips], dim=0),
            "root_pos": torch.cat([clip.root_pos for clip in clips], dim=0),
            "root_heading": torch.cat(
                [clip.root_heading_rot for clip in clips], dim=0
            ),
        }
        if any(int(value.shape[0]) != expected_total for value in packed.values()):
            raise RuntimeError(
                f"Packed authored table length mismatch for {runtime.name}/{mode}: "
                f"expected={expected_total} got="
                f"{ {key: int(value.shape[0]) for key, value in packed.items()} }"
            )
        tables[mode] = {
            key: value.to(device=device, dtype=torch.float32)
            for key, value in packed.items()
        }
    return tables


def authored_upper_gpu_rows(
    runtime: runtime_data.CategoryRuntime,
    mode: float,
    clip_ids: torch.Tensor,
    indices: torch.Tensor,
    gaze: torch.Tensor,
    tables: dict[float, dict[str, torch.Tensor]],
) -> torch.Tensor:
    """Gather authored rows and apply the accepted gaze overlay on GPU."""

    flat = runtime.store.frame_index(clip_ids, indices)
    table = tables[mode]
    positions, rotations = upper_data.apply_gaze_overlay_global_pose(
        runtime.full_by_mode[mode],
        table["global_pos"].index_select(0, flat),
        table["global_rot"].index_select(0, flat),
        gaze,
    )
    return upper_data.upper_state_from_global_pose_and_heading(
        runtime.full_by_mode[mode],
        positions,
        rotations,
        table["root_pos"].index_select(0, flat),
        table["root_heading"].index_select(0, flat),
    )


def episode_noisy_cached_current_state(
    runtime: runtime_data.CategoryRuntime,
    mode: float,
    clip_ids: torch.Tensor,
    current_lower_vector: torch.Tensor,
    current_upper: torch.Tensor,
    current_pelvis: torch.Tensor,
    current_feet: torch.Tensor,
    current_lower_positions: torch.Tensor,
    current_lower_rotations: torch.Tensor,
    current_root_position: torch.Tensor,
    current_root_rotation: torch.Tensor,
    current_heading: torch.Tensor,
    noisy_mask: torch.Tensor,
    pelvis_rotation_vector: torch.Tensor,
    pelvis_translation: torch.Tensor,
    fk_rotation_vectors: torch.Tensor,
    hand_translations: torch.Tensor,
    hand_rotation_vectors: torch.Tensor,
    subtree_indices: dict[str, torch.Tensor],
) -> tuple[
    torch.Tensor,
    torch.Tensor,
    torch.Tensor,
    torch.Tensor,
    torch.Tensor,
    torch.Tensor,
    torch.Tensor,
]:
    """Decode, perturb, then re-encode every affected reset-state input."""

    full_clip = runtime.full_by_mode[mode]
    positions, rotations = decode_rows_vectorized(
        runtime,
        mode,
        current_lower_vector,
        current_upper,
        current_pelvis,
        current_root_position,
        current_root_rotation,
        current_heading,
        clip_ids,
    )
    positions, rotations = apply_episode_start_pose_noise(
        full_clip,
        positions,
        rotations,
        noisy_mask,
        pelvis_rotation_vector,
        pelvis_translation,
        fk_rotation_vectors,
        hand_translations,
        hand_rotation_vectors,
        subtree_indices,
    )
    noisy_upper = upper_data.upper_state_from_global_pose_and_heading(
        full_clip,
        positions,
        rotations,
        current_root_position,
        current_heading,
    )

    # The cached lower policy is immutable.  Noise may change only controller-
    # owned upper pose values; return the exact original cached tensors rather
    # than re-encoding numerically equivalent lower transforms.
    return (
        noisy_upper,
        current_pelvis,
        current_feet,
        current_lower_positions,
        current_lower_rotations,
        positions,
        rotations,
    )


def ae1_full_corpus_static_rollout(
    agent: UpperPelvisAgent,
    ae: SimpleAutoencoder,
    mean: torch.Tensor,
    std: torch.Tensor,
    output_weights: torch.Tensor,
    runtime: runtime_data.CategoryRuntime,
    mode: float,
    clip_ids: torch.Tensor,
    starts: torch.Tensor,
    effective_k: torch.Tensor,
    gaze: torch.Tensor,
    maximum_k: int,
    authored_tables: dict[float, dict[str, torch.Tensor]],
    debug_lower: torch.Tensor | None = None,
    debug_upper: torch.Tensor | None = None,
    debug_pelvis: torch.Tensor | None = None,
    debug_frames: torch.Tensor | None = None,
) -> torch.Tensor:
    """Captured heterogeneous full-corpus AE1 rollout.

    The graph receives only staged clip/start/K/gaze tensors.  All authored
    pose construction, frozen-lower inference, IK feedback, AE scoring and
    optimization math stay on GPU.
    """

    batch = int(starts.numel())
    store = runtime.store
    lower_clip = runtime.lower_clip
    full_clip = runtime.full_by_mode[mode]
    rest = runtime.rest_offsets_by_mode[mode].index_select(0, clip_ids)
    lower_geometry = {
        name: values.index_select(0, clip_ids)
        for name, values in runtime.lower_geometry.items()
    }
    payload = lower_ctl.payload_slice(store)
    sword = torch.full(
        (batch, 1), float(mode), dtype=torch.float32, device=starts.device
    )

    older = store.get_target_output(clip_ids, starts - 2)
    previous = store.get_target_output(clip_ids, starts - 1)
    current = store.get_target_output(clip_ids, starts)
    repeated_ids = clip_ids.repeat(3)
    repeated_gaze = gaze.repeat(3, 1)
    initial_upper = authored_upper_gpu_rows(
        runtime,
        mode,
        repeated_ids,
        torch.cat((starts - 2, starts - 1, starts), dim=0),
        repeated_gaze,
        authored_tables,
    )
    older_upper = initial_upper[:batch]
    previous_upper = initial_upper[batch : 2 * batch]
    current_upper = initial_upper[2 * batch :]
    older_root = runtime_data.root_state(runtime, starts - 2, clip_ids)
    previous_root = runtime_data.root_state(runtime, starts - 1, clip_ids)
    current_root = runtime_data.root_state(runtime, starts, clip_ids)
    older_pelvis = pelvis_heading(older, older_root[1], older_root[2])
    previous_pelvis = pelvis_heading(previous, previous_root[1], previous_root[2])
    current_pelvis = pelvis_heading(current, current_root[1], current_root[2])
    previous_base = runtime_data.base_upper_from_lower(
        previous, *previous_root, full_clip, rest
    )
    current_base = runtime_data.base_upper_from_lower(
        current, *current_root, full_clip, rest
    )
    current_prior = upper_data.clean_upper_state(
        current_base + previous_upper - previous_base
    )
    context_input = torch.cat(
        (
            older_upper,
            current_prior,
            older_pelvis,
            previous_pelvis,
            current_pelvis,
            store.get_input_root_features(clip_ids, starts - 1),
            sword,
            runtime_data.foot_heading_features(
                store, previous, previous_root[1], previous_root[2]
            ),
            runtime_data.foot_heading_features(
                store, current, current_root[1], current_root[2]
            ),
            gaze,
        ),
        dim=-1,
    )
    previous_positions, previous_rotations = decode_rows_vectorized(
        runtime,
        mode,
        previous,
        previous_upper,
        previous_pelvis,
        *previous_root,
        clip_ids,
    )
    current_positions, current_rotations = decode_rows_vectorized(
        runtime,
        mode,
        current,
        current_upper,
        current_pelvis,
        *current_root,
        clip_ids,
    )
    context_transition = contract.physical_transition_from_decoded(
        full_clip,
        previous_positions,
        previous_rotations,
        current_positions,
        current_rotations,
        previous_root[0],
        previous_root[1],
    )
    context_row = torch.cat((context_input, context_transition), dim=-1)
    previous_lower_pelvis = previous[:, :3]
    current_lower_pelvis = current[:, :3]
    previous_payload = previous[:, payload]
    current_payload = current[:, payload]

    if debug_lower is not None:
        assert debug_upper is not None and debug_pelvis is not None
        assert debug_frames is not None
        debug_lower[:, 0].copy_(current.detach())
        debug_upper[:, 0].copy_(current_upper.detach())
        debug_pelvis[:, 0].copy_(current_pelvis.detach())
        debug_frames[:, 0].copy_(starts)

    total = agent.delta_head.weight.new_zeros(())
    effective_float = effective_k.to(dtype=torch.float32)
    for rollout_step in range(int(maximum_k)):
        values = lower_ctl.build_controller_input(
            store,
            clip_ids,
            starts + rollout_step,
            previous,
            current,
            previous_lower_pelvis,
            current_lower_pelvis,
            previous_payload,
            current_payload,
        )
        raw_lower = lower_ctl.model_raw_output(runtime.model, values, current, store)
        transition_lower = lower_ctl.clean_output_vector(
            raw_lower, store, current, previous
        )
        next_lower, _unused_pelvis, _unused_payload = (
            lower_ctl.advance_transition_state(
                store, clip_ids, starts + rollout_step, transition_lower
            )
        )
        next_indices = starts + rollout_step + 1
        next_root = runtime_data.root_state(runtime, next_indices, clip_ids)
        pelvis_prior = contract.pelvis_proposal(
            pelvis_heading(next_lower, next_root[1], next_root[2])
        )
        frozen_next_base = runtime_data.base_upper_from_lower(
            next_lower, *next_root, full_clip, rest
        )
        upper_prior = upper_data.clean_upper_state(
            frozen_next_base + current_upper - current_base
        )
        roots = store.get_input_root_features(clip_ids, starts + rollout_step)
        feet_current = runtime_data.foot_heading_features(
            store, current, current_root[1], current_root[2]
        )
        feet_next = runtime_data.foot_heading_features(
            store, next_lower, next_root[1], next_root[2]
        )
        controller_input = torch.cat(
            (
                previous_upper,
                upper_prior,
                previous_pelvis,
                current_pelvis,
                pelvis_prior,
                roots,
                sword,
                feet_current,
                feet_next,
                gaze,
            ),
            dim=-1,
        )
        next_upper, next_pelvis, _applied = contract.apply_agent_output(
            upper_prior, pelvis_prior, agent(controller_input)
        )
        next_positions, next_rotations = decode_rows_vectorized(
            runtime,
            mode,
            next_lower,
            next_upper,
            next_pelvis,
            *next_root,
            clip_ids,
        )
        physical = contract.physical_transition_from_decoded(
            full_clip,
            current_positions,
            current_rotations,
            next_positions,
            next_rotations,
            current_root[0],
            current_root[1],
        )
        current_row = torch.cat((controller_input, physical), dim=-1)
        normalized = (torch.cat((context_row, current_row), dim=-1) - mean) / std
        reconstructed = ae(normalized)
        row_loss = weighted_physical_mse(
            reconstructed[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END]
            - normalized[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END],
            output_weights,
        )
        active = (effective_k > rollout_step).to(dtype=row_loss.dtype)
        total = total + (row_loss * active / effective_float).mean()

        next_feedback = contract.feedback_lower_state(
            lower_clip,
            next_lower,
            next_pelvis,
            *next_root,
            geometry_tensors=lower_geometry,
        )
        controlled_next_base = runtime_data.base_upper_from_lower(
            next_feedback, *next_root, full_clip, rest
        )
        previous = current
        current = next_feedback
        previous_lower_pelvis = current_lower_pelvis
        current_lower_pelvis = current[:, :3]
        previous_payload = current_payload
        current_payload = current[:, payload]
        previous_upper = current_upper
        current_upper = next_upper
        previous_pelvis = current_pelvis
        current_pelvis = next_pelvis
        current_base = controlled_next_base
        current_root = next_root
        current_positions = next_positions
        current_rotations = next_rotations
        context_row = current_row
        if debug_lower is not None:
            debug_lower[:, rollout_step + 1].copy_(current.detach())
            debug_upper[:, rollout_step + 1].copy_(current_upper.detach())
            debug_pelvis[:, rollout_step + 1].copy_(current_pelvis.detach())
            debug_frames[:, rollout_step + 1].copy_(next_indices)
    return total


def ae1_static_rollout(
    agent: UpperPelvisAgent,
    ae: SimpleAutoencoder,
    mean: torch.Tensor,
    std: torch.Tensor,
    output_weights: torch.Tensor,
    runtime: runtime_data.CategoryRuntime,
    mode: float,
    starts: torch.Tensor,
    effective_k: torch.Tensor,
    maximum_k: int,
    upper_targets: torch.Tensor,
    debug_lower: torch.Tensor | None = None,
    debug_upper: torch.Tensor | None = None,
    debug_pelvis: torch.Tensor | None = None,
    debug_frames: torch.Tensor | None = None,
) -> torch.Tensor:
    """GPU-only fixed-shape rollout scored exclusively by accepted AE1."""

    batch = int(starts.numel())
    clip_ids = torch.zeros_like(starts)
    store = runtime.store
    lower_clip = runtime.lower_clips[0]
    full_clip = runtime.full_by_mode[mode]
    rest = runtime.rest_offsets_by_mode[mode][0]
    payload = lower_ctl.payload_slice(store)
    gaze = torch.zeros((batch, 2), dtype=torch.float32, device=starts.device)
    sword = torch.full(
        (batch, 1), float(mode), dtype=torch.float32, device=starts.device
    )

    older = store.get_target_output(clip_ids, starts - 2)
    previous = store.get_target_output(clip_ids, starts - 1)
    current = store.get_target_output(clip_ids, starts)
    older_upper = upper_targets.index_select(0, starts - 2)
    previous_upper = upper_targets.index_select(0, starts - 1)
    current_upper = upper_targets.index_select(0, starts)
    older_root = runtime_data.root_state(runtime, starts - 2, clip_ids)
    previous_root = runtime_data.root_state(runtime, starts - 1, clip_ids)
    current_root = runtime_data.root_state(runtime, starts, clip_ids)
    older_pelvis = pelvis_heading(older, older_root[1], older_root[2])
    previous_pelvis = pelvis_heading(previous, previous_root[1], previous_root[2])
    current_pelvis = pelvis_heading(current, current_root[1], current_root[2])
    previous_base = runtime_data.base_upper_from_lower(
        previous, *previous_root, full_clip, rest
    )
    current_base = runtime_data.base_upper_from_lower(
        current, *current_root, full_clip, rest
    )
    current_prior = upper_data.clean_upper_state(
        current_base + previous_upper - previous_base
    )
    context_input = torch.cat(
        (
            older_upper,
            current_prior,
            older_pelvis,
            previous_pelvis,
            current_pelvis,
            store.get_input_root_features(clip_ids, starts - 1),
            sword,
            runtime_data.foot_heading_features(
                store, previous, previous_root[1], previous_root[2]
            ),
            runtime_data.foot_heading_features(
                store, current, current_root[1], current_root[2]
            ),
            gaze,
        ),
        dim=-1,
    )
    previous_positions, previous_rotations = contract.decode_full_pose(
        full_clip,
        lower_clip,
        previous,
        previous_upper,
        previous_pelvis,
        *previous_root,
    )
    current_positions, current_rotations = contract.decode_full_pose(
        full_clip,
        lower_clip,
        current,
        current_upper,
        current_pelvis,
        *current_root,
    )
    context_transition = contract.physical_transition_from_decoded(
        full_clip,
        previous_positions,
        previous_rotations,
        current_positions,
        current_rotations,
        previous_root[0],
        previous_root[1],
    )
    context_row = torch.cat((context_input, context_transition), dim=-1)
    previous_lower_pelvis = previous[:, :3]
    current_lower_pelvis = current[:, :3]
    previous_payload = previous[:, payload]
    current_payload = current[:, payload]

    if debug_lower is not None:
        assert debug_upper is not None and debug_pelvis is not None
        assert debug_frames is not None
        debug_lower[:, 0].copy_(current.detach())
        debug_upper[:, 0].copy_(current_upper.detach())
        debug_pelvis[:, 0].copy_(current_pelvis.detach())
        debug_frames[:, 0].copy_(starts)

    total = agent.delta_head.weight.new_zeros(())
    effective_float = effective_k.to(dtype=torch.float32)
    for rollout_step in range(int(maximum_k)):
        values = lower_ctl.build_controller_input(
            store,
            clip_ids,
            starts + rollout_step,
            previous,
            current,
            previous_lower_pelvis,
            current_lower_pelvis,
            previous_payload,
            current_payload,
        )
        raw_lower = lower_ctl.model_raw_output(runtime.model, values, current, store)
        transition_lower = lower_ctl.clean_output_vector(
            raw_lower, store, current, previous
        )
        next_lower, _unused_pelvis, _unused_payload = (
            lower_ctl.advance_transition_state(
                store, clip_ids, starts + rollout_step, transition_lower
            )
        )
        next_indices = starts + rollout_step + 1
        next_root = runtime_data.root_state(runtime, next_indices, clip_ids)
        pelvis_prior = contract.pelvis_proposal(
            pelvis_heading(next_lower, next_root[1], next_root[2])
        )
        frozen_next_base = runtime_data.base_upper_from_lower(
            next_lower, *next_root, full_clip, rest
        )
        upper_prior = upper_data.clean_upper_state(
            frozen_next_base + current_upper - current_base
        )
        roots = store.get_input_root_features(clip_ids, starts + rollout_step)
        feet_current = runtime_data.foot_heading_features(
            store, current, current_root[1], current_root[2]
        )
        feet_next = runtime_data.foot_heading_features(
            store, next_lower, next_root[1], next_root[2]
        )
        controller_input = torch.cat(
            (
                previous_upper,
                upper_prior,
                previous_pelvis,
                current_pelvis,
                pelvis_prior,
                roots,
                sword,
                feet_current,
                feet_next,
                gaze,
            ),
            dim=-1,
        )
        next_upper, next_pelvis, _applied = contract.apply_agent_output(
            upper_prior, pelvis_prior, agent(controller_input)
        )
        next_positions, next_rotations = contract.decode_full_pose(
            full_clip,
            lower_clip,
            next_lower,
            next_upper,
            next_pelvis,
            *next_root,
        )
        physical = contract.physical_transition_from_decoded(
            full_clip,
            current_positions,
            current_rotations,
            next_positions,
            next_rotations,
            current_root[0],
            current_root[1],
        )
        current_row = torch.cat((controller_input, physical), dim=-1)
        normalized = (torch.cat((context_row, current_row), dim=-1) - mean) / std
        reconstructed = ae(normalized)
        row_loss = weighted_physical_mse(
            reconstructed[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END]
            - normalized[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END],
            output_weights,
        )
        active = (effective_k > rollout_step).to(dtype=row_loss.dtype)
        total = total + (row_loss * active / effective_float).mean()

        next_feedback = contract.feedback_lower_state(
            lower_clip, next_lower, next_pelvis, *next_root
        )
        controlled_next_base = runtime_data.base_upper_from_lower(
            next_feedback, *next_root, full_clip, rest
        )
        previous = current
        current = next_feedback
        previous_lower_pelvis = current_lower_pelvis
        current_lower_pelvis = current[:, :3]
        previous_payload = current_payload
        current_payload = current[:, payload]
        previous_upper = current_upper
        current_upper = next_upper
        previous_pelvis = current_pelvis
        current_pelvis = next_pelvis
        current_base = controlled_next_base
        current_root = next_root
        current_positions = next_positions
        current_rotations = next_rotations
        context_row = current_row
        if debug_lower is not None:
            debug_lower[:, rollout_step + 1].copy_(current.detach())
            debug_upper[:, rollout_step + 1].copy_(current_upper.detach())
            debug_pelvis[:, rollout_step + 1].copy_(current_pelvis.detach())
            debug_frames[:, rollout_step + 1].copy_(next_indices)
    return total


def ae22_static_rollout(
    agent: UpperPelvisAgent,
    ae22: torch.nn.Module,
    mean: torch.Tensor,
    std: torch.Tensor,
    runtime: runtime_data.CategoryRuntime,
    mode: float,
    starts: torch.Tensor,
    effective_k: torch.Tensor,
    maximum_k: int,
    upper_targets: torch.Tensor,
    debug_lower: torch.Tensor | None = None,
    debug_upper: torch.Tensor | None = None,
    debug_pelvis: torch.Tensor | None = None,
    debug_frames: torch.Tensor | None = None,
) -> torch.Tensor:
    """GPU-only rollout scored by root-relative condition-only AE22."""

    batch = int(starts.numel())
    clip_ids = torch.zeros_like(starts)
    store = runtime.store
    lower_clip = runtime.lower_clips[0]
    full_clip = runtime.full_by_mode[mode]
    rest = runtime.rest_offsets_by_mode[mode][0]
    payload = lower_ctl.payload_slice(store)
    gaze = torch.zeros((batch, 2), dtype=torch.float32, device=starts.device)
    sword = torch.full((batch, 1), float(mode), dtype=torch.float32, device=starts.device)

    previous = store.get_target_output(clip_ids, starts - 1)
    current = store.get_target_output(clip_ids, starts)
    previous_upper = upper_targets.index_select(0, starts - 1)
    current_upper = upper_targets.index_select(0, starts)
    previous_root = runtime_data.root_state(runtime, starts - 1, clip_ids)
    current_root = runtime_data.root_state(runtime, starts, clip_ids)
    previous_pelvis = pelvis_heading(previous, previous_root[1], previous_root[2])
    current_pelvis = pelvis_heading(current, current_root[1], current_root[2])
    previous_base = runtime_data.base_upper_from_lower(
        previous, *previous_root, full_clip, rest
    )
    current_base = runtime_data.base_upper_from_lower(current, *current_root, full_clip, rest)
    previous_positions, previous_rotations = contract.decode_full_pose(
        full_clip,
        lower_clip,
        previous,
        previous_upper,
        previous_pelvis,
        *previous_root,
    )
    current_positions, current_rotations = contract.decode_full_pose(
        full_clip,
        lower_clip,
        current,
        current_upper,
        current_pelvis,
        *current_root,
    )
    previous_lower_pelvis = previous[:, :3]
    current_lower_pelvis = current[:, :3]
    previous_payload = previous[:, payload]
    current_payload = current[:, payload]

    if debug_lower is not None:
        assert debug_upper is not None and debug_pelvis is not None
        assert debug_frames is not None
        debug_lower[:, 0].copy_(current.detach())
        debug_upper[:, 0].copy_(current_upper.detach())
        debug_pelvis[:, 0].copy_(current_pelvis.detach())
        debug_frames[:, 0].copy_(starts)

    total = agent.delta_head.weight.new_zeros(())
    effective_float = effective_k.to(dtype=torch.float32)
    for rollout_step in range(int(maximum_k)):
        values = lower_ctl.build_controller_input(
            store,
            clip_ids,
            starts + rollout_step,
            previous,
            current,
            previous_lower_pelvis,
            current_lower_pelvis,
            previous_payload,
            current_payload,
        )
        raw_lower = lower_ctl.model_raw_output(runtime.model, values, current, store)
        transition_lower = lower_ctl.clean_output_vector(raw_lower, store, current, previous)
        next_lower, _unused_pelvis, _unused_payload = lower_ctl.advance_transition_state(
            store, clip_ids, starts + rollout_step, transition_lower
        )
        next_indices = starts + rollout_step + 1
        next_root = runtime_data.root_state(runtime, next_indices, clip_ids)
        pelvis_prior = contract.pelvis_proposal(
            pelvis_heading(next_lower, next_root[1], next_root[2])
        )
        frozen_next_base = runtime_data.base_upper_from_lower(
            next_lower, *next_root, full_clip, rest
        )
        upper_prior = upper_data.clean_upper_state(
            frozen_next_base + current_upper - current_base
        )
        roots = store.get_input_root_features(clip_ids, starts + rollout_step)
        feet_current = runtime_data.foot_heading_features(
            store, current, current_root[1], current_root[2]
        )
        feet_next = runtime_data.foot_heading_features(
            store, next_lower, next_root[1], next_root[2]
        )
        controller_input = torch.cat(
            (
                previous_upper,
                upper_prior,
                previous_pelvis,
                current_pelvis,
                pelvis_prior,
                roots,
                sword,
                feet_current,
                feet_next,
                gaze,
            ),
            dim=-1,
        )
        next_upper, next_pelvis, _applied = contract.apply_agent_output(
            upper_prior, pelvis_prior, agent(controller_input)
        )
        next_positions, next_rotations = contract.decode_full_pose(
            full_clip,
            lower_clip,
            next_lower,
            next_upper,
            next_pelvis,
            *next_root,
        )
        candidate = contract.physical_transition_from_decoded(
            full_clip,
            current_positions,
            current_rotations,
            next_positions,
            next_rotations,
            current_root[0],
            current_root[1],
        )
        previous_physical = contract.physical_pose_from_globals(
            full_clip,
            previous_positions,
            previous_rotations,
            current_root[0],
            current_root[1],
        )
        current_physical = contract.physical_pose_from_globals(
            full_clip,
            current_positions,
            current_rotations,
            current_root[0],
            current_root[1],
        )
        ae22_row = torch.cat(
            (
                candidate,
                previous_physical,
                current_physical,
                controller_input[:, ae22_data.CONTROL_SOURCE_START :],
            ),
            dim=-1,
        )
        normalized = (ae22_row - mean) / std
        teacher = ae22(normalized)[:, : contract.PHYSICAL_DIM]
        row_loss = (teacher - normalized[:, : contract.PHYSICAL_DIM]).square().mean(dim=-1)
        active = (effective_k > rollout_step).to(dtype=row_loss.dtype)
        total = total + (row_loss * active / effective_float).mean()

        next_feedback = contract.feedback_lower_state(
            lower_clip, next_lower, next_pelvis, *next_root
        )
        controlled_next_base = runtime_data.base_upper_from_lower(
            next_feedback, *next_root, full_clip, rest
        )
        previous = current
        current = next_feedback
        previous_lower_pelvis = current_lower_pelvis
        current_lower_pelvis = current[:, :3]
        previous_payload = current_payload
        current_payload = current[:, payload]
        previous_upper = current_upper
        current_upper = next_upper
        previous_pelvis = current_pelvis
        current_pelvis = next_pelvis
        current_base = controlled_next_base
        current_root = next_root
        previous_positions = current_positions
        previous_rotations = current_rotations
        current_positions = next_positions
        current_rotations = next_rotations
        if debug_lower is not None:
            debug_lower[:, rollout_step + 1].copy_(current.detach())
            debug_upper[:, rollout_step + 1].copy_(current_upper.detach())
            debug_pelvis[:, rollout_step + 1].copy_(current_pelvis.detach())
            debug_frames[:, rollout_step + 1].copy_(next_indices)
    return total


class DirectMseCudaGraphStep:
    """Captured full K-step upper+pelvis optimizer update."""

    kind = "cuda_graph_direct_mse_full_rollout"

    def __init__(
        self,
        agent: UpperPelvisAgent,
        optimizer: torch.optim.Optimizer,
        runtime: runtime_data.CategoryRuntime,
        mode: float,
        batch_size: int,
        maximum_k: int,
        upper_targets: torch.Tensor,
    ) -> None:
        if runtime.store.device.type != "cuda":
            raise RuntimeError("DirectMseCudaGraphStep requires CUDA")
        self.agent = agent
        self.optimizer = optimizer
        self.runtime = runtime
        self.mode = float(mode)
        self.batch_size = int(batch_size)
        self.maximum_k = int(maximum_k)
        self.upper_targets = upper_targets
        all_frames = torch.arange(
            int(runtime.full_by_mode[mode].T),
            dtype=torch.long,
            device=runtime.store.device,
        )
        all_clip_ids = torch.zeros_like(all_frames)
        all_roots = runtime_data.root_state(runtime, all_frames, all_clip_ids)
        self.pelvis_targets = pelvis_heading(
            runtime.store.get_target_output(all_clip_ids, all_frames),
            all_roots[1],
            all_roots[2],
        )
        self.starts = torch.empty(
            (self.batch_size,), dtype=torch.long, device=runtime.store.device
        )
        self.effective_k = torch.empty_like(self.starts)
        lower_dim = int(runtime.store.target_output.shape[-1])
        frames = self.maximum_k + 1
        self.debug_lower = torch.empty(
            (self.batch_size, frames, lower_dim),
            dtype=torch.float32,
            device=runtime.store.device,
        )
        self.debug_upper = torch.empty(
            (self.batch_size, frames, upper_data.OUTPUT_DIM),
            dtype=torch.float32,
            device=runtime.store.device,
        )
        self.debug_pelvis = torch.empty(
            (self.batch_size, frames, upper_data.PELVIS_DIM),
            dtype=torch.float32,
            device=runtime.store.device,
        )
        self.debug_frames = torch.empty(
            (self.batch_size, frames),
            dtype=torch.long,
            device=runtime.store.device,
        )
        self.loss = torch.zeros((), dtype=torch.float32, device=runtime.store.device)
        self.upper_mse = torch.zeros_like(self.loss)
        self.pelvis_mse = torch.zeros_like(self.loss)
        self.gradient_norm = torch.zeros_like(self.loss)
        self.maximum_start = runtime_data.valid_start_max(
            runtime.lower_clips[0],
            self.maximum_k,
            int(runtime.cfg.future_window),
        )
        runtime.store.prepare_root_state_cache(self.maximum_k)
        self.initial_model = lower_ctl.clone_module_tensors(agent)
        self.graph = torch.cuda.CUDAGraph()
        self.capture_seconds = self._capture()

    def sample_(self) -> None:
        self.starts.random_(2, int(self.maximum_start) + 1)
        self.effective_k.copy_(
            runtime_data.sample_effective_rollout_k(
                self.batch_size, self.maximum_k, self.starts.device
            )
        )

    def _forward(self) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        return direct_mse_static_rollout(
            self.agent,
            self.runtime,
            self.mode,
            self.starts,
            self.effective_k,
            self.maximum_k,
            self.upper_targets,
            self.pelvis_targets,
        )

    def _zero_optimizer_state(self) -> None:
        lower_ctl.restore_module_tensors(self.agent, self.initial_model)
        with torch.no_grad():
            for state in self.optimizer.state.values():
                for value in state.values():
                    if torch.is_tensor(value):
                        value.zero_()
        self.optimizer.zero_grad(set_to_none=False)

    def _capture(self) -> float:
        started = time.perf_counter()
        side_stream = torch.cuda.Stream()
        side_stream.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(side_stream):
            for _ in range(3):
                self.sample_()
                self.optimizer.zero_grad(set_to_none=False)
                loss, _upper, _pelvis = self._forward()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.agent.parameters(), 50.0)
                self.optimizer.step()
                del loss, _upper, _pelvis
        torch.cuda.current_stream().wait_stream(side_stream)
        torch.cuda.synchronize(self.starts.device)
        self._zero_optimizer_state()
        self.sample_()
        with torch.cuda.graph(self.graph):
            self.optimizer.zero_grad(set_to_none=False)
            loss, upper_mse, pelvis_mse = self._forward()
            self.loss.copy_(loss.detach())
            self.upper_mse.copy_(upper_mse.detach())
            self.pelvis_mse.copy_(pelvis_mse.detach())
            loss.backward()
            norm = torch.nn.utils.clip_grad_norm_(self.agent.parameters(), 50.0)
            self.gradient_norm.copy_(norm.detach())
            self.optimizer.step()
        torch.cuda.synchronize(self.starts.device)
        self._zero_optimizer_state()
        torch.cuda.synchronize(self.starts.device)
        return time.perf_counter() - started

    @torch.no_grad()
    def parity_reference(self) -> tuple[float, float, float]:
        values = direct_mse_static_rollout(
            self.agent,
            self.runtime,
            self.mode,
            self.starts,
            self.effective_k,
            self.maximum_k,
            self.upper_targets,
            self.pelvis_targets,
        )
        return tuple(float(value.detach().cpu()) for value in values)  # type: ignore[return-value]

    def replay_current(self) -> None:
        self.graph.replay()

    def step(self) -> None:
        self.sample_()
        self.graph.replay()

    @torch.no_grad()
    def prepare_debug_rollout(self) -> None:
        # This intentionally runs outside the graph and only at the sparse
        # replayer-export cadence.  The hot optimizer graph performs no debug
        # buffer copies and no physical pose decoding.
        direct_mse_static_rollout(
            self.agent,
            self.runtime,
            self.mode,
            self.starts,
            self.effective_k,
            self.maximum_k,
            self.upper_targets,
            self.pelvis_targets,
            self.debug_lower,
            self.debug_upper,
            self.debug_pelvis,
            self.debug_frames,
        )


class Ae1CudaGraphStep:
    """Captured full K-step update whose sole objective is AE1 or AE22."""

    kind = "cuda_graph_ae1_only_full_rollout"

    def __init__(
        self,
        agent: UpperPelvisAgent,
        optimizer: torch.optim.Optimizer,
        ae: torch.nn.Module,
        mean: torch.Tensor,
        std: torch.Tensor,
        output_weights: torch.Tensor,
        runtime: runtime_data.CategoryRuntime,
        mode: float,
        batch_size: int,
        maximum_k: int,
        upper_targets: torch.Tensor,
        objective: str = "ae1",
    ) -> None:
        if runtime.store.device.type != "cuda":
            raise RuntimeError("Ae1CudaGraphStep requires CUDA")
        self.agent = agent
        self.optimizer = optimizer
        self.ae = ae
        self.objective = str(objective)
        if self.objective not in ("ae1", "ae22"):
            raise ValueError(f"Unknown captured objective {self.objective!r}")
        self.kind = f"cuda_graph_{self.objective}_only_full_rollout"
        self.mean = mean
        self.std = std
        self.output_weights = output_weights
        self.runtime = runtime
        self.mode = float(mode)
        self.batch_size = int(batch_size)
        self.maximum_k = int(maximum_k)
        self.upper_targets = upper_targets
        self.starts = torch.empty(
            (self.batch_size,), dtype=torch.long, device=runtime.store.device
        )
        self.effective_k = torch.empty_like(self.starts)
        lower_dim = int(runtime.store.target_output.shape[-1])
        frames = self.maximum_k + 1
        self.debug_lower = torch.empty(
            (self.batch_size, frames, lower_dim),
            dtype=torch.float32,
            device=runtime.store.device,
        )
        self.debug_upper = torch.empty(
            (self.batch_size, frames, upper_data.OUTPUT_DIM),
            dtype=torch.float32,
            device=runtime.store.device,
        )
        self.debug_pelvis = torch.empty(
            (self.batch_size, frames, upper_data.PELVIS_DIM),
            dtype=torch.float32,
            device=runtime.store.device,
        )
        self.debug_frames = torch.empty(
            (self.batch_size, frames), dtype=torch.long, device=runtime.store.device
        )
        self.loss = torch.zeros((), dtype=torch.float32, device=runtime.store.device)
        self.gradient_norm = torch.zeros_like(self.loss)
        self.maximum_start = runtime_data.valid_start_max(
            runtime.lower_clips[0], self.maximum_k, int(runtime.cfg.future_window)
        )
        runtime.store.prepare_root_state_cache(self.maximum_k)
        self.initial_model = lower_ctl.clone_module_tensors(agent)
        self.graph = torch.cuda.CUDAGraph()
        self.capture_seconds = self._capture()

    def sample_(self) -> None:
        self.starts.random_(2, int(self.maximum_start) + 1)
        self.effective_k.copy_(
            runtime_data.sample_effective_rollout_k(
                self.batch_size, self.maximum_k, self.starts.device
            )
        )

    def _forward(self) -> torch.Tensor:
        common = (
            self.agent,
            self.ae,
            self.mean,
            self.std,
        )
        if self.objective == "ae22":
            return ae22_static_rollout(
                *common,
                self.runtime,
                self.mode,
                self.starts,
                self.effective_k,
                self.maximum_k,
                self.upper_targets,
            )
        return ae1_static_rollout(
            *common,
            self.output_weights,
            self.runtime,
            self.mode,
            self.starts,
            self.effective_k,
            self.maximum_k,
            self.upper_targets,
        )

    def _zero_optimizer_state(self) -> None:
        lower_ctl.restore_module_tensors(self.agent, self.initial_model)
        with torch.no_grad():
            for state in self.optimizer.state.values():
                for value in state.values():
                    if torch.is_tensor(value):
                        value.zero_()
        self.optimizer.zero_grad(set_to_none=False)

    def _capture(self) -> float:
        started = time.perf_counter()
        side_stream = torch.cuda.Stream()
        side_stream.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(side_stream):
            for _ in range(3):
                self.sample_()
                self.optimizer.zero_grad(set_to_none=False)
                loss = self._forward()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.agent.parameters(), 50.0)
                self.optimizer.step()
                del loss
        torch.cuda.current_stream().wait_stream(side_stream)
        torch.cuda.synchronize(self.starts.device)
        self._zero_optimizer_state()
        self.sample_()
        with torch.cuda.graph(self.graph):
            self.optimizer.zero_grad(set_to_none=False)
            loss = self._forward()
            self.loss.copy_(loss.detach())
            loss.backward()
            norm = torch.nn.utils.clip_grad_norm_(self.agent.parameters(), 50.0)
            self.gradient_norm.copy_(norm.detach())
            self.optimizer.step()
        torch.cuda.synchronize(self.starts.device)
        self._zero_optimizer_state()
        torch.cuda.synchronize(self.starts.device)
        return time.perf_counter() - started

    @torch.no_grad()
    def parity_reference(self) -> float:
        return float(self._forward().detach().cpu())

    def replay_current(self) -> None:
        self.graph.replay()

    def step(self) -> None:
        self.sample_()
        self.graph.replay()

    @torch.no_grad()
    def prepare_debug_rollout(self) -> None:
        common = (self.agent, self.ae, self.mean, self.std)
        tail = (
            self.runtime,
            self.mode,
            self.starts,
            self.effective_k,
            self.maximum_k,
            self.upper_targets,
            self.debug_lower,
            self.debug_upper,
            self.debug_pelvis,
            self.debug_frames,
        )
        if self.objective == "ae22":
            ae22_static_rollout(*common, *tail)
        else:
            ae1_static_rollout(*common, self.output_weights, *tail)


class Ae1MixedKCudaGraphStep:
    """Exact BS8 geometric K-mix as four single-use CUDA cohort graphs."""

    kind = "cuda_graph_ae1_only_geometric_kmix32_cohorts"
    COHORTS = ((32, 4), (16, 2), (8, 1), (1, 1))

    def __init__(
        self,
        agent: UpperPelvisAgent,
        optimizer: torch.optim.Optimizer,
        ae: torch.nn.Module,
        mean: torch.Tensor,
        std: torch.Tensor,
        output_weights: torch.Tensor,
        runtime: runtime_data.CategoryRuntime,
        mode: float,
        upper_targets: torch.Tensor,
    ) -> None:
        if runtime.store.device.type != "cuda":
            raise RuntimeError("Ae1MixedKCudaGraphStep requires CUDA")
        self.agent = agent
        self.optimizer = optimizer
        self.ae = ae
        self.mean = mean
        self.std = std
        self.output_weights = output_weights
        self.runtime = runtime
        self.mode = float(mode)
        self.upper_targets = upper_targets
        self.batch_size = sum(count for _horizon, count in self.COHORTS)
        self.maximum_k = 32
        self.maximum_start = runtime_data.valid_start_max(
            runtime.lower_clips[0], self.maximum_k, int(runtime.cfg.future_window)
        )
        runtime.store.prepare_root_state_cache(self.maximum_k)
        device = runtime.store.device
        lower_dim = int(runtime.store.target_output.shape[-1])
        frames = self.maximum_k + 1
        self.starts = torch.empty((self.batch_size,), dtype=torch.long, device=device)
        self._effective_template = torch.tensor(
            [horizon for horizon, count in self.COHORTS for _ in range(count)],
            dtype=torch.long,
            device=device,
        )
        self.effective_k = self._effective_template.clone()
        self._sampling_generator = torch.Generator(device="cpu").manual_seed(20260813)
        self.debug_lower = torch.empty(
            (self.batch_size, frames, lower_dim), dtype=torch.float32, device=device
        )
        self.debug_upper = torch.empty(
            (self.batch_size, frames, upper_data.OUTPUT_DIM),
            dtype=torch.float32,
            device=device,
        )
        self.debug_pelvis = torch.empty(
            (self.batch_size, frames, upper_data.PELVIS_DIM),
            dtype=torch.float32,
            device=device,
        )
        self.debug_frames = torch.empty(
            (self.batch_size, frames), dtype=torch.long, device=device
        )
        self.loss = torch.zeros((), dtype=torch.float32, device=device)
        self.gradient_norm = torch.zeros_like(self.loss)
        self._initial_model = lower_ctl.clone_module_tensors(agent)
        self._cohort_starts = {
            horizon: torch.empty((count,), dtype=torch.long, device=device)
            for horizon, count in self.COHORTS
        }
        self._cohort_effective = {
            horizon: torch.full((count,), horizon, dtype=torch.long, device=device)
            for horizon, count in self.COHORTS
        }
        self._cohort_debug = {
            horizon: (
                torch.empty((count, horizon + 1, lower_dim), dtype=torch.float32, device=device),
                torch.empty(
                    (count, horizon + 1, upper_data.OUTPUT_DIM),
                    dtype=torch.float32,
                    device=device,
                ),
                torch.empty(
                    (count, horizon + 1, upper_data.PELVIS_DIM),
                    dtype=torch.float32,
                    device=device,
                ),
                torch.empty((count, horizon + 1), dtype=torch.long, device=device),
            )
            for horizon, count in self.COHORTS
        }
        self._cohort_graphs = {
            horizon: torch.cuda.CUDAGraph() for horizon, _count in self.COHORTS
        }
        self._zero_graph = torch.cuda.CUDAGraph()
        self._update_graph = torch.cuda.CUDAGraph()
        self.capture_seconds = self._capture()

    def _forward(self, horizon: int) -> torch.Tensor:
        debug_lower, debug_upper, debug_pelvis, debug_frames = self._cohort_debug[horizon]
        return ae1_static_rollout(
            self.agent,
            self.ae,
            self.mean,
            self.std,
            self.output_weights,
            self.runtime,
            self.mode,
            self._cohort_starts[horizon],
            self._cohort_effective[horizon],
            horizon,
            self.upper_targets,
            debug_lower,
            debug_upper,
            debug_pelvis,
            debug_frames,
        )

    def _zero_optimizer_state(self) -> None:
        lower_ctl.restore_module_tensors(self.agent, self._initial_model)
        with torch.no_grad():
            for state in self.optimizer.state.values():
                for value in state.values():
                    if torch.is_tensor(value):
                        value.zero_()
        self.optimizer.zero_grad(set_to_none=False)
        self.loss.zero_()
        self.gradient_norm.zero_()

    def _capture(self) -> float:
        started = time.perf_counter()
        device = self.runtime.store.device
        side_stream = torch.cuda.Stream()
        side_stream.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(side_stream):
            for _ in range(3):
                self.optimizer.zero_grad(set_to_none=False)
                for horizon, count in self.COHORTS:
                    self._cohort_starts[horizon].random_(2, self.maximum_start + 1)
                    warmup = self._forward(horizon) * (float(count) / self.batch_size)
                    warmup.backward()
                torch.nn.utils.clip_grad_norm_(self.agent.parameters(), 50.0)
                self.optimizer.step()
                del warmup
        torch.cuda.current_stream().wait_stream(side_stream)
        torch.cuda.synchronize(device)
        self._zero_optimizer_state()
        pool = torch.cuda.graph_pool_handle()
        with torch.cuda.graph(self._zero_graph, pool=pool):
            self.optimizer.zero_grad(set_to_none=False)
            self.loss.zero_()
            self.gradient_norm.zero_()
        for horizon, count in self.COHORTS:
            self._cohort_starts[horizon].random_(2, self.maximum_start + 1)
            with torch.cuda.graph(self._cohort_graphs[horizon], pool=pool):
                cohort_loss = self._forward(horizon) * (float(count) / self.batch_size)
                self.loss.add_(cohort_loss.detach())
                cohort_loss.backward()
        with torch.cuda.graph(self._update_graph, pool=pool):
            norm = torch.nn.utils.clip_grad_norm_(self.agent.parameters(), 50.0)
            self.gradient_norm.copy_(norm.detach())
            self.optimizer.step()
        torch.cuda.synchronize(device)
        self._zero_optimizer_state()
        torch.cuda.synchronize(device)
        self.sample_()
        return time.perf_counter() - started

    def sample_(self) -> None:
        sampled = torch.randint(
            2,
            self.maximum_start + 1,
            (self.batch_size,),
            generator=self._sampling_generator,
            device="cpu",
        )
        self.starts.copy_(sampled.to(device=self.starts.device))
        self.effective_k.copy_(self._effective_template)

    def _stage_cohort(self, horizon: int, offset: int, count: int) -> None:
        self._cohort_starts[horizon].copy_(self.starts[offset : offset + count])

    def _copy_cohort_debug(self, horizon: int, offset: int, count: int) -> None:
        debug_lower, debug_upper, debug_pelvis, debug_frames = self._cohort_debug[horizon]
        end = offset + count
        slots = horizon + 1
        self.debug_lower[offset:end, :slots].copy_(debug_lower)
        self.debug_upper[offset:end, :slots].copy_(debug_upper)
        self.debug_pelvis[offset:end, :slots].copy_(debug_pelvis)
        self.debug_frames[offset:end, :slots].copy_(debug_frames)
        if slots < self.maximum_k + 1:
            remaining = self.maximum_k + 1 - slots
            self.debug_lower[offset:end, slots:].copy_(
                debug_lower[:, -1:].expand(-1, remaining, -1)
            )
            self.debug_upper[offset:end, slots:].copy_(
                debug_upper[:, -1:].expand(-1, remaining, -1)
            )
            self.debug_pelvis[offset:end, slots:].copy_(
                debug_pelvis[:, -1:].expand(-1, remaining, -1)
            )
            self.debug_frames[offset:end, slots:].copy_(
                debug_frames[:, -1:].expand(-1, remaining)
            )

    def _replay_sampled(self) -> None:
        self._zero_graph.replay()
        torch.cuda.synchronize(self.starts.device)
        offset = 0
        for horizon, count in self.COHORTS:
            self._stage_cohort(horizon, offset, count)
            self._cohort_graphs[horizon].replay()
            torch.cuda.synchronize(self.starts.device)
            self._copy_cohort_debug(horizon, offset, count)
            offset += count
        self._update_graph.replay()
        torch.cuda.synchronize(self.starts.device)

    def replay_loss_only_current(self) -> None:
        offset = 0
        for horizon, count in self.COHORTS:
            self._stage_cohort(horizon, offset, count)
            self._cohort_graphs[horizon].replay()
            torch.cuda.synchronize(self.starts.device)
            offset += count

    @torch.no_grad()
    def parity_reference(self) -> float:
        total = self.agent.delta_head.weight.new_zeros(())
        offset = 0
        for horizon, count in self.COHORTS:
            self._stage_cohort(horizon, offset, count)
            total = total + self._forward(horizon) * (float(count) / self.batch_size)
            offset += count
        return float(total.detach().cpu())

    def replay_current(self) -> None:
        self._replay_sampled()

    def step(self) -> None:
        self.sample_()
        self._replay_sampled()

    @torch.no_grad()
    def prepare_debug_rollout(self) -> None:
        return None


def ae1_cached_lower_full_corpus_static_rollout(
    agent: UpperCachedLowerAgent,
    ae: SimpleAutoencoder,
    mean: torch.Tensor,
    std: torch.Tensor,
    output_weights: torch.Tensor,
    runtime: runtime_data.CategoryRuntime,
    cache: cached_lower_data.CachedLowerCategory,
    mode: float,
    clip_ids: torch.Tensor,
    starts: torch.Tensor,
    effective_k: torch.Tensor,
    gaze: torch.Tensor,
    maximum_k: int,
    authored_tables: dict[float, dict[str, torch.Tensor]],
    rollout_gradient_window: int = 0,
    ae4: torch.nn.Module | None = None,
    ae4_input_mean: torch.Tensor | None = None,
    ae4_input_std: torch.Tensor | None = None,
    ae4_target_mean: torch.Tensor | None = None,
    ae4_target_std: torch.Tensor | None = None,
    ae4_loss_weight: float = 0.0,
    ae4_to_ae1_frame_blend: bool = False,
    debug_lower: torch.Tensor | None = None,
    debug_upper: torch.Tensor | None = None,
    debug_pelvis: torch.Tensor | None = None,
    debug_frames: torch.Tensor | None = None,
    return_terms: bool = False,
    episode_noise: tuple[
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
    ]
    | None = None,
    episode_noise_subtrees: dict[str, torch.Tensor] | None = None,
    debug_positions: torch.Tensor | None = None,
    debug_rotations: torch.Tensor | None = None,
    initial_gaze: torch.Tensor | None = None,
) -> torch.Tensor | tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Upper-only rollout over a precomputed continuous lower trajectory."""

    if int(rollout_gradient_window) < 0:
        raise ValueError("rollout_gradient_window must be zero (full) or positive")

    batch = int(starts.numel())
    full_clip = runtime.full_by_mode[mode]
    local_offsets = runtime.full_geometry_by_mode[mode]["local_offsets"].index_select(
        0, clip_ids
    )
    limb_lengths = runtime.full_geometry_by_mode[mode]["ik_limb_lengths"].index_select(
        0, clip_ids
    )
    local_pole_axes = runtime.full_geometry_by_mode[mode]["ik_local_pole_axis"].index_select(
        0, clip_ids
    )
    sword = torch.full(
        (batch, 1), float(mode), dtype=torch.float32, device=starts.device
    )

    older_indices = starts - 2
    previous_indices = starts - 1
    current_indices = starts
    seed_gaze = gaze if initial_gaze is None else initial_gaze
    if tuple(seed_gaze.shape) != (batch, 2):
        raise RuntimeError(
            f"Initialization gaze shape changed: {tuple(seed_gaze.shape)} != {(batch, 2)}"
        )
    initial_upper = authored_upper_gpu_rows(
        runtime,
        mode,
        clip_ids.repeat(3),
        torch.cat((older_indices, previous_indices, current_indices), dim=0),
        seed_gaze.repeat(3, 1),
        authored_tables,
    )
    older_upper = initial_upper[:batch]
    previous_upper = initial_upper[batch : 2 * batch]
    current_upper = initial_upper[2 * batch :]

    def gather(name: str, indices: torch.Tensor) -> torch.Tensor:
        return cache.gather(name, clip_ids, indices)

    previous_root_position = gather("root_position", previous_indices)
    previous_root_rotation = gather("root_rotation", previous_indices)
    previous_heading = gather("heading", previous_indices)
    current_root_position = gather("root_position", current_indices)
    current_root_rotation = gather("root_rotation", current_indices)
    current_heading = gather("heading", current_indices)
    older_pelvis = gather("pelvis_heading", older_indices)
    previous_pelvis = gather("pelvis_heading", previous_indices)
    current_pelvis = gather("pelvis_heading", current_indices)
    previous_feet = gather("feet_heading", previous_indices)
    current_feet = gather("feet_heading", current_indices)
    previous_lower_positions = gather("cached_lower_position", previous_indices)
    previous_lower_rotations = gather("cached_lower_rotation", previous_indices)
    current_lower_positions = gather("cached_lower_position", current_indices)
    current_lower_rotations = gather("cached_lower_rotation", current_indices)
    current_debug_positions: torch.Tensor | None = None
    current_debug_rotations: torch.Tensor | None = None
    if episode_noise is not None:
        if episode_noise_subtrees is None:
            raise RuntimeError("Episode reset noise has no preallocated subtree indices")
        (
            current_upper,
            current_pelvis,
            current_feet,
            current_lower_positions,
            current_lower_rotations,
            current_debug_positions,
            current_debug_rotations,
        ) = episode_noisy_cached_current_state(
            runtime,
            mode,
            clip_ids,
            gather("lower_vector", current_indices),
            current_upper,
            current_pelvis,
            current_feet,
            current_lower_positions,
            current_lower_rotations,
            current_root_position,
            current_root_rotation,
            current_heading,
            *episode_noise,
            episode_noise_subtrees,
        )
    previous_base = cache.base_upper(mode, clip_ids, previous_indices)
    current_base = cache.base_upper(mode, clip_ids, current_indices)
    current_prior = upper_data.clean_upper_state(
        current_base + previous_upper - previous_base
    )
    context_input = torch.cat(
        (
            older_upper,
            current_prior,
            older_pelvis,
            previous_pelvis,
            current_pelvis,
            gather("root_features", previous_indices),
            sword,
            previous_feet,
            current_feet,
            gaze,
        ),
        dim=-1,
    )
    context_transition = contract.upper_only_physical_transition(
        full_clip,
        previous_upper,
        current_upper,
        previous_root_position,
        previous_root_rotation,
        previous_heading,
        current_root_position,
        current_heading,
        previous_lower_positions,
        previous_lower_rotations,
        current_lower_positions,
        current_lower_rotations,
        local_offsets=local_offsets,
    )
    context_row = torch.cat((context_input, context_transition), dim=-1)

    if debug_lower is not None:
        assert debug_upper is not None and debug_pelvis is not None
        assert debug_frames is not None
        assert debug_positions is not None and debug_rotations is not None
        if current_debug_positions is None or current_debug_rotations is None:
            current_debug_positions, current_debug_rotations = decode_rows_vectorized(
                runtime,
                mode,
                gather("lower_vector", current_indices),
                current_upper,
                current_pelvis,
                current_root_position,
                current_root_rotation,
                current_heading,
                clip_ids,
            )
        debug_lower[:, 0].copy_(gather("lower_vector", current_indices).detach())
        debug_upper[:, 0].copy_(current_upper.detach())
        debug_pelvis[:, 0].copy_(current_pelvis.detach())
        debug_frames[:, 0].copy_(current_indices)
        debug_positions[:, 0].copy_(current_debug_positions.detach())
        debug_rotations[:, 0].copy_(current_debug_rotations.detach())

    ae1_total = agent.delta_head.weight.new_zeros(())
    ae4_total = agent.delta_head.weight.new_zeros(())
    lowerarm_length_sum = agent.delta_head.weight.new_zeros(())
    lowerarm_active_count = agent.delta_head.weight.new_zeros(())
    effective_float = effective_k.to(dtype=torch.float32)
    for rollout_step in range(int(maximum_k)):
        next_indices = starts + rollout_step + 1
        next_root_position = gather("root_position", next_indices)
        next_root_rotation = gather("root_rotation", next_indices)
        next_heading = gather("heading", next_indices)
        next_pelvis = gather("pelvis_heading", next_indices)
        next_feet = gather("feet_heading", next_indices)
        next_base = cache.base_upper(mode, clip_ids, next_indices)
        upper_prior = upper_data.clean_upper_state(
            next_base + current_upper - current_base
        )
        controller_input = torch.cat(
            (
                previous_upper,
                upper_prior,
                previous_pelvis,
                current_pelvis,
                next_pelvis,
                gather("root_features", current_indices),
                sword,
                current_feet,
                next_feet,
                gaze,
            ),
            dim=-1,
        )
        next_upper = upper_data.clean_upper_state(
            upper_prior + agent(controller_input)
        )
        next_lower_positions = gather("cached_lower_position", next_indices)
        next_lower_rotations = gather("cached_lower_rotation", next_indices)
        physical, next_physical_pose = (
            contract.upper_only_physical_transition_and_following_pose(
                full_clip,
                current_upper,
                next_upper,
                current_root_position,
                current_root_rotation,
                current_heading,
                next_root_position,
                next_heading,
                current_lower_positions,
                current_lower_rotations,
                next_lower_positions,
                next_lower_rotations,
                local_offsets=local_offsets,
            )
        )
        current_row = torch.cat((controller_input, physical), dim=-1)
        normalized = (torch.cat((context_row, current_row), dim=-1) - mean) / std
        reconstructed = ae(normalized)
        row_loss = weighted_physical_mse(
            reconstructed[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END]
            - normalized[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END],
            output_weights,
        )
        active = (effective_k > rollout_step).to(dtype=row_loss.dtype)
        ae1_frame_weight, ae4_frame_weight = (1.0, 1.0)
        if ae4_to_ae1_frame_blend:
            ae1_frame_weight, ae4_frame_weight = ae1_ae4_temporal_weights(
                rollout_step + 1, maximum_k
            )
        ae1_total = ae1_total + (
            float(ae1_frame_weight) * row_loss * active / effective_float
        ).mean()
        if float(ae4_loss_weight) > 0.0:
            if any(
                value is None
                for value in (
                    ae4,
                    ae4_input_mean,
                    ae4_input_std,
                    ae4_target_mean,
                    ae4_target_std,
                )
            ):
                raise RuntimeError("AE4 loss is enabled without a complete frozen AE4")
            ae4_condition = torch.cat(
                (
                    gather("ae4_lower_root", current_indices - 1),
                    gather("ae4_lower_root", current_indices),
                    gather("ae4_lower_root", next_indices),
                    gather("root_features", current_indices),
                    sword,
                    gaze,
                ),
                dim=-1,
            )
            if int(ae4_condition.shape[-1]) != ae4_data.INPUT_DIM:
                raise RuntimeError(
                    f"Cached AE4 condition width changed: {tuple(ae4_condition.shape)}"
                )
            ae4_proposal = ae4_data.predict_absolute(
                ae4,
                ae4_condition,
                ae4_input_mean,
                ae4_input_std,
                ae4_target_mean,
                ae4_target_std,
            ).detach()
            ae4_candidate = ae4_data.clean_absolute_pose(
                contract.upper_only_absolute_pose(
                    full_clip,
                    next_upper,
                    next_root_position,
                    next_root_rotation,
                    next_heading,
                    next_lower_positions,
                    next_lower_rotations,
                    tuple(ae4_data.UPPER_TARGET_BONES),
                    local_offsets=local_offsets,
                    local_pole_axes=local_pole_axes,
                )
            )
            ae4_row_loss = ae4_absolute_pose_loss(
                ae4_candidate, ae4_proposal, ae4_target_std
            )
            ae4_total = ae4_total + (
                float(ae4_frame_weight) * ae4_row_loss * active / effective_float
            ).mean()
        lowerarm_rows, _lowerarm_max_error = contract.lowerarm_length_error_rows(
            full_clip,
            next_physical_pose,
            local_offsets,
            limb_lengths,
        )
        lowerarm_length_sum = lowerarm_length_sum + (
            lowerarm_rows * active
        ).sum()
        lowerarm_active_count = lowerarm_active_count + active.sum()

        previous_upper = current_upper
        current_upper = next_upper
        previous_pelvis = current_pelvis
        current_pelvis = next_pelvis
        current_base = next_base
        current_feet = next_feet
        current_root_position = next_root_position
        current_root_rotation = next_root_rotation
        current_heading = next_heading
        current_lower_positions = next_lower_positions
        current_lower_rotations = next_lower_rotations
        current_indices = next_indices
        context_row = current_row
        if (
            int(rollout_gradient_window) > 0
            and (rollout_step + 1) % int(rollout_gradient_window) == 0
        ):
            # Preserve the exact autoregressive forward rollout while limiting
            # how far a later frame's loss can credit earlier predictions.
            # Window 2 means each output can receive its own loss plus one
            # additional future frame of credit.
            previous_upper = previous_upper.detach()
            current_upper = current_upper.detach()
            context_row = context_row.detach()
        if debug_lower is not None:
            debug_lower[:, rollout_step + 1].copy_(
                gather("lower_vector", next_indices).detach()
            )
            debug_upper[:, rollout_step + 1].copy_(current_upper.detach())
            debug_pelvis[:, rollout_step + 1].copy_(current_pelvis.detach())
            debug_frames[:, rollout_step + 1].copy_(next_indices)
            assert debug_positions is not None and debug_rotations is not None
            following_positions, following_rotations = decode_rows_vectorized(
                runtime,
                mode,
                gather("lower_vector", next_indices),
                current_upper,
                current_pelvis,
                current_root_position,
                current_root_rotation,
                current_heading,
                clip_ids,
            )
            debug_positions[:, rollout_step + 1].copy_(
                following_positions.detach()
            )
            debug_rotations[:, rollout_step + 1].copy_(
                following_rotations.detach()
            )
    lowerarm_length_raw_mse = (
        lowerarm_length_sum / lowerarm_active_count.clamp_min(1.0)
    )
    total = (
        ae1_total
        + float(ae4_loss_weight) * ae4_total
        + LOWERARM_LENGTH_WEIGHT * lowerarm_length_raw_mse
    )
    if return_terms:
        return ae1_total, ae4_total, lowerarm_length_sum, lowerarm_active_count
    return total


class FullCorpusAe1CudaGraphStep:
    """BS32/BS64 upper-only update over the continuous cached-lower dataset."""

    GROUPS = (
        (runtime_data.CATEGORY_WALK, runtime_data.MODE_SHEATHED),
        (runtime_data.CATEGORY_WALK, runtime_data.MODE_DRAWN),
        (runtime_data.CATEGORY_RUN, runtime_data.MODE_SHEATHED),
        (runtime_data.CATEGORY_RUN, runtime_data.MODE_DRAWN),
    )
    # Legacy geometric K-mix layout. The current all-K32 recipe selects a
    # separate fixed-horizon layout without changing older run reproducibility.
    BASE_GROUP_HORIZONS = (
        (32, 32, 32, 32, 16, 16, 8, 4),
        (32, 32, 32, 32, 16, 16, 8, 4),
        (32, 32, 32, 32, 16, 16, 8, 2),
        (32, 32, 32, 32, 16, 16, 8, 1),
    )

    @classmethod
    def group_horizons_for_batch(
        cls, batch_size: int, all_rows_k32: bool = False
    ) -> tuple[tuple[int, ...], ...]:
        if int(batch_size) not in (32, 64):
            raise ValueError(
                f"Full-corpus CUDA Graph batch must be 32 or 64, got {batch_size}"
            )
        scale = int(batch_size) // 32
        if all_rows_k32:
            rows_per_group = int(batch_size) // len(cls.GROUPS)
            return tuple((32,) * rows_per_group for _key in cls.GROUPS)
        return tuple(
            tuple(value for value in base for _ in range(scale))
            for base in cls.BASE_GROUP_HORIZONS
        )

    def __init__(
        self,
        agent: UpperCachedLowerAgent,
        optimizer: torch.optim.Optimizer,
        ae: torch.nn.Module,
        mean: torch.Tensor,
        std: torch.Tensor,
        output_weights: torch.Tensor,
        runtimes: dict[str, runtime_data.CategoryRuntime],
        caches: dict[str, cached_lower_data.CachedLowerCategory],
        seed: int,
        batch_size: int,
        rollout_gradient_window: int = 0,
        ae4: torch.nn.Module | None = None,
        ae4_input_mean: torch.Tensor | None = None,
        ae4_input_std: torch.Tensor | None = None,
        ae4_target_mean: torch.Tensor | None = None,
        ae4_target_std: torch.Tensor | None = None,
        ae4_loss_weight: float = 0.0,
        all_rows_k32: bool = False,
        ae4_to_ae1_frame_blend: bool = False,
        reset_noise_profile: dict[str, float] | None = None,
        random_initial_gaze_half_per_noise_class: bool = False,
    ) -> None:
        if set(runtimes) != {
            runtime_data.CATEGORY_WALK,
            runtime_data.CATEGORY_RUN,
        }:
            raise RuntimeError(f"Full corpus requires walk+run runtimes: {set(runtimes)}")
        if any(runtime.store.device.type != "cuda" for runtime in runtimes.values()):
            raise RuntimeError("FullCorpusAe1CudaGraphStep requires CUDA")
        self.agent = agent
        self.optimizer = optimizer
        self.ae = ae
        self.mean = mean
        self.std = std
        self.output_weights = output_weights
        self.ae4 = ae4
        self.ae4_input_mean = ae4_input_mean
        self.ae4_input_std = ae4_input_std
        self.ae4_target_mean = ae4_target_mean
        self.ae4_target_std = ae4_target_std
        self.ae4_loss_weight = float(ae4_loss_weight)
        self.all_rows_k32 = bool(all_rows_k32)
        self.ae4_to_ae1_frame_blend = bool(ae4_to_ae1_frame_blend)
        self.reset_noise_profile = dict(reset_noise_profile or {})
        self.reset_noise_probability = float(
            self.reset_noise_profile.get("probability", 0.0)
        )
        self.random_initial_gaze_half_per_noise_class = bool(
            random_initial_gaze_half_per_noise_class
        )
        noisy_rows_float = self.reset_noise_probability * int(batch_size)
        self.noisy_rows_per_batch = int(round(noisy_rows_float))
        self.episode_noise_enabled = self.noisy_rows_per_batch > 0
        if self.episode_noise_enabled:
            frozen_lower_noise = {
                "pelvis_rotation_deg_max": float(
                    self.reset_noise_profile.get("pelvis_rotation_deg_max", 0.0)
                ),
                "pelvis_location_cm_max": float(
                    self.reset_noise_profile.get("pelvis_location_cm_max", 0.0)
                ),
            }
            if any(value != 0.0 for value in frozen_lower_noise.values()):
                raise ValueError(
                    "Cached-lower reset noise must leave the frozen pelvis exact: "
                    f"{frozen_lower_noise}"
                )
        if abs(noisy_rows_float - self.noisy_rows_per_batch) > 1.0e-7:
            raise ValueError(
                "Episode-noise probability must select an exact integer number "
                f"of BS{batch_size} rows, got {noisy_rows_float}"
            )
        clean_rows_per_batch = int(batch_size) - self.noisy_rows_per_batch
        if self.random_initial_gaze_half_per_noise_class and (
            self.noisy_rows_per_batch % 2 != 0 or clean_rows_per_batch % 2 != 0
        ):
            raise ValueError(
                "Half-random initialization gaze requires even clean and noisy "
                f"row counts, got clean={clean_rows_per_batch} "
                f"noisy={self.noisy_rows_per_batch}"
            )
        if self.ae4_loss_weight < 0.0 or not math.isfinite(self.ae4_loss_weight):
            raise ValueError(f"Invalid AE4 loss weight {self.ae4_loss_weight}")
        if self.ae4_loss_weight > 0.0 and any(
            value is None
            for value in (
                self.ae4,
                self.ae4_input_mean,
                self.ae4_input_std,
                self.ae4_target_mean,
                self.ae4_target_std,
            )
        ):
            raise RuntimeError("AE4 loss weight is positive without a complete frozen AE4")
        if self.ae4_to_ae1_frame_blend and self.ae4_loss_weight <= 0.0:
            raise ValueError("AE1/AE4 temporal blending requires a positive AE4 loss weight")
        self.runtimes = runtimes
        self.caches = caches
        self.maximum_k = 32
        self.batch_size = int(batch_size)
        self.rollout_gradient_window = int(rollout_gradient_window)
        if self.rollout_gradient_window < 0:
            raise ValueError(
                "rollout_gradient_window must be zero (full) or positive"
            )
        gradient_suffix = (
            "fullgrad"
            if self.rollout_gradient_window == 0
            else f"tbptt{self.rollout_gradient_window}"
        )
        self.kind = (
            "cuda_graph_ae1_upper_cached_lower_"
            f"bs{self.batch_size}_{'allk32' if self.all_rows_k32 else 'kmix32'}_"
            f"{gradient_suffix}_"
            f"lowerarm_length_{'ae4' if self.ae4_loss_weight > 0.0 else 'noae4'}_"
            f"resetnoise{int(round(self.reset_noise_probability * 100.0)):02d}_"
            f"initgaze{'half_each' if self.random_initial_gaze_half_per_noise_class else 'matched'}_"
            "reusable_cohort_graphs"
        )
        self.rows_per_group = self.batch_size // len(self.GROUPS)
        self.device = runtimes[runtime_data.CATEGORY_WALK].store.device
        self._sampling_generator = torch.Generator(device="cpu").manual_seed(int(seed))
        group_horizons = self.group_horizons_for_batch(
            self.batch_size, self.all_rows_k32
        )
        effective_template = tuple(
            horizon for horizons in group_horizons for horizon in horizons
        )
        self._effective_template_cpu = torch.tensor(
            effective_template, dtype=torch.long
        )
        self._lowerarm_active_count = float(self._effective_template_cpu.sum())
        if int(self._effective_template_cpu.numel()) != self.batch_size:
            raise RuntimeError(
                f"Internal K-mix template is not BS{self.batch_size}"
            )
        self._group_horizons = {
            key: tuple(int(value) for value in horizons)
            for key, horizons in zip(self.GROUPS, group_horizons, strict=True)
        }
        actual_horizons = sorted(
            horizon
            for horizons in self._group_horizons.values()
            for horizon in horizons
        )
        if actual_horizons != sorted(effective_template):
            raise RuntimeError(
                "Reusable graph horizon layout does not preserve exact K-mix: "
                f"{actual_horizons}"
            )
        self._authored_tables = {
            category: prepare_authored_pose_tables(runtime)
            for category, runtime in runtimes.items()
        }
        self._maximum_start_cpu = {
            category: torch.tensor(
                [
                    int(clip.cyclic_period) - 1
                    if bool(clip.cyclic_animation)
                    else runtime_data.valid_start_max(
                        clip, self.maximum_k, int(runtime.cfg.future_window)
                    )
                    for clip in runtime.lower_clips
                ],
                dtype=torch.long,
            )
            for category, runtime in runtimes.items()
        }
        for category, maxima in self._maximum_start_cpu.items():
            if bool((maxima < 2).any()):
                bad = torch.nonzero(maxima < 2, as_tuple=False).flatten().tolist()
                raise RuntimeError(
                    f"Full corpus contains clips too short for K32 in {category}: {bad}"
                )
            cached_lengths = caches[category].cache_lengths.detach().cpu()
            if bool((maxima + self.maximum_k >= cached_lengths).any()):
                raise RuntimeError(
                    f"Cached lower trajectory is too short for {category}/K32"
                )

        self._clip_ids: dict[tuple[str, float], torch.Tensor] = {}
        self._starts: dict[tuple[str, float], torch.Tensor] = {}
        self._effective_k: dict[tuple[str, float], torch.Tensor] = {}
        self._gaze: dict[tuple[str, float], torch.Tensor] = {}
        self._initial_gaze: dict[tuple[str, float], torch.Tensor] = {}
        self._random_initial_gaze_mask: dict[
            tuple[str, float], torch.Tensor
        ] = {}
        self._episode_noise: dict[
            tuple[str, float],
            tuple[
                torch.Tensor,
                torch.Tensor,
                torch.Tensor,
                torch.Tensor,
                torch.Tensor,
                torch.Tensor,
            ],
        ] = {}
        self._episode_noise_subtrees: dict[
            tuple[str, float], dict[str, torch.Tensor]
        ] = {}
        self._debug: dict[
            tuple[str, float],
            tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor],
        ] = {}
        self._debug_pose: dict[
            tuple[str, float], tuple[torch.Tensor, torch.Tensor]
        ] = {}
        self._group_chunks = {
            key: self._coalesce_horizons(self._group_horizons[key])
            for key in self.GROUPS
        }
        self._graphs = {
            (key, horizon): torch.cuda.CUDAGraph()
            for key in self.GROUPS
            for _start, _end, horizon in self._group_chunks[key]
        }
        self._zero_graph = torch.cuda.CUDAGraph()
        self._update_graph = torch.cuda.CUDAGraph()
        for key in self.GROUPS:
            category, _mode = key
            runtime = runtimes[category]
            lower_dim = int(runtime.store.target_output.shape[-1])
            self._clip_ids[key] = torch.empty(
                (self.rows_per_group,), dtype=torch.long, device=self.device
            )
            self._starts[key] = torch.empty_like(self._clip_ids[key])
            self._effective_k[key] = torch.empty_like(self._clip_ids[key])
            self._effective_k[key].copy_(
                torch.tensor(
                    self._group_horizons[key],
                    dtype=torch.long,
                    device=self.device,
                )
            )
            self._gaze[key] = torch.empty(
                (self.rows_per_group, 2), dtype=torch.float32, device=self.device
            )
            self._initial_gaze[key] = torch.empty_like(self._gaze[key])
            self._random_initial_gaze_mask[key] = torch.empty(
                (self.rows_per_group,), dtype=torch.bool, device=self.device
            )
            self._episode_noise[key] = (
                torch.empty(
                    (self.rows_per_group,), dtype=torch.bool, device=self.device
                ),
                torch.empty(
                    (self.rows_per_group, 3), dtype=torch.float32, device=self.device
                ),
                torch.empty(
                    (self.rows_per_group, 3), dtype=torch.float32, device=self.device
                ),
                torch.empty(
                    (self.rows_per_group, len(EPISODE_NOISE_FK_BONES), 3),
                    dtype=torch.float32,
                    device=self.device,
                ),
                torch.empty(
                    (self.rows_per_group, len(EPISODE_NOISE_HAND_BONES), 3),
                    dtype=torch.float32,
                    device=self.device,
                ),
                torch.empty(
                    (self.rows_per_group, len(EPISODE_NOISE_HAND_BONES), 3),
                    dtype=torch.float32,
                    device=self.device,
                ),
            )
            self._episode_noise_subtrees[key] = {
                name: _episode_noise_subtree_indices(
                    runtime.full_by_mode[_mode], name
                ).to(self.device)
                for name in (
                    "pelvis",
                    *EPISODE_NOISE_FK_BONES,
                    *EPISODE_NOISE_HAND_BONES,
                )
            }
            self._debug[key] = (
                torch.empty(
                    (self.rows_per_group, self.maximum_k + 1, lower_dim),
                    dtype=torch.float32,
                    device=self.device,
                ),
                torch.empty(
                    (self.rows_per_group, self.maximum_k + 1, upper_data.OUTPUT_DIM),
                    dtype=torch.float32,
                    device=self.device,
                ),
                torch.empty(
                    (self.rows_per_group, self.maximum_k + 1, upper_data.PELVIS_DIM),
                    dtype=torch.float32,
                    device=self.device,
                ),
                torch.empty(
                    (self.rows_per_group, self.maximum_k + 1),
                    dtype=torch.long,
                    device=self.device,
                ),
            )
            joints = len(runtime.full_by_mode[_mode].body_names)
            self._debug_pose[key] = (
                torch.empty(
                    (
                        self.rows_per_group,
                        self.maximum_k + 1,
                        joints,
                        3,
                    ),
                    dtype=torch.float32,
                    device=self.device,
                ),
                torch.empty(
                    (
                        self.rows_per_group,
                        self.maximum_k + 1,
                        joints,
                        3,
                        3,
                    ),
                    dtype=torch.float32,
                    device=self.device,
                ),
            )
        self.loss = torch.zeros((), dtype=torch.float32, device=self.device)
        self.ae1_loss = torch.zeros_like(self.loss)
        self.ae4_loss_raw = torch.zeros_like(self.loss)
        self.lowerarm_length_raw_mse = torch.zeros_like(self.loss)
        self.gradient_norm = torch.zeros_like(self.loss)
        self._initial_model = lower_ctl.clone_module_tensors(agent)
        self._initial_optimizer_state = {
            parameter: {
                key: value.detach().clone() if torch.is_tensor(value) else value
                for key, value in state.items()
            }
            for parameter, state in optimizer.state.items()
        }
        self.sample_()
        self.capture_seconds = self._capture()

    @staticmethod
    def _coalesce_horizons(
        horizons: tuple[int, ...],
    ) -> tuple[tuple[int, int, int], ...]:
        chunks: list[tuple[int, int, int]] = []
        start = 0
        while start < len(horizons):
            horizon = int(horizons[start])
            end = start + 1
            while end < len(horizons) and int(horizons[end]) == horizon:
                end += 1
            chunks.append((start, end, horizon))
            start = end
        return tuple(chunks)

    def _forward(
        self,
        key: tuple[str, float],
        row_slice: slice | None = None,
        debug: bool = False,
    ) -> torch.Tensor:
        category, mode = key
        runtime = self.runtimes[category]
        debug_values = self._debug[key] if debug else (None, None, None, None)
        debug_pose = self._debug_pose[key] if debug else (None, None)
        if row_slice is None:
            clip_ids = self._clip_ids[key]
            starts = self._starts[key]
            effective_k = self._effective_k[key]
            gaze = self._gaze[key]
        else:
            clip_ids = self._clip_ids[key][row_slice]
            starts = self._starts[key][row_slice]
            effective_k = self._effective_k[key][row_slice]
            gaze = self._gaze[key][row_slice]
        return ae1_cached_lower_full_corpus_static_rollout(
            self.agent,
            self.ae,
            self.mean,
            self.std,
            self.output_weights,
            runtime,
            self.caches[category],
            mode,
            clip_ids,
            starts,
            effective_k,
            gaze,
            self.maximum_k,
            self._authored_tables[category],
            self.rollout_gradient_window,
            self.ae4,
            self.ae4_input_mean,
            self.ae4_input_std,
            self.ae4_target_mean,
            self.ae4_target_std,
            self.ae4_loss_weight,
            self.ae4_to_ae1_frame_blend,
            *debug_values,
            episode_noise=(
                self._episode_noise[key] if self.episode_noise_enabled else None
            ),
            episode_noise_subtrees=(
                self._episode_noise_subtrees[key]
                if self.episode_noise_enabled
                else None
            ),
            debug_positions=debug_pose[0],
            debug_rotations=debug_pose[1],
            initial_gaze=(
                self._initial_gaze[key]
                if row_slice is None
                else self._initial_gaze[key][row_slice]
            ),
        )

    def _forward_horizon(
        self,
        key: tuple[str, float],
        row_slice: slice,
        horizon: int,
        *,
        return_terms: bool = False,
    ) -> torch.Tensor | tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """Evaluate a static captured row only through its assigned K."""

        category, mode = key
        runtime = self.runtimes[category]
        return ae1_cached_lower_full_corpus_static_rollout(
            self.agent,
            self.ae,
            self.mean,
            self.std,
            self.output_weights,
            runtime,
            self.caches[category],
            mode,
            self._clip_ids[key][row_slice],
            self._starts[key][row_slice],
            self._effective_k[key][row_slice],
            self._gaze[key][row_slice],
            int(horizon),
            self._authored_tables[category],
            self.rollout_gradient_window,
            self.ae4,
            self.ae4_input_mean,
            self.ae4_input_std,
            self.ae4_target_mean,
            self.ae4_target_std,
            self.ae4_loss_weight,
            self.ae4_to_ae1_frame_blend,
            return_terms=return_terms,
            episode_noise=(
                tuple(values[row_slice] for values in self._episode_noise[key])
                if self.episode_noise_enabled
                else None
            ),
            episode_noise_subtrees=(
                self._episode_noise_subtrees[key]
                if self.episode_noise_enabled
                else None
            ),
            initial_gaze=self._initial_gaze[key][row_slice],
        )

    def _scaled_horizon_terms(
        self,
        key: tuple[str, float],
        row_slice: slice,
        horizon: int,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """Return total, AE1, raw AE4, and Slash-normalized lower-arm terms."""

        ae1, ae4_raw, lowerarm_sum, _lowerarm_count = self._forward_horizon(
            key, row_slice, horizon, return_terms=True
        )
        cohort_scale = (row_slice.stop - row_slice.start) / float(self.batch_size)
        scaled_ae1 = ae1 * cohort_scale
        scaled_ae4_raw = ae4_raw * cohort_scale
        lowerarm_raw = lowerarm_sum / self._lowerarm_active_count
        total = (
            scaled_ae1
            + self.ae4_loss_weight * scaled_ae4_raw
            + LOWERARM_LENGTH_WEIGHT * lowerarm_raw
        )
        return total, scaled_ae1, scaled_ae4_raw, lowerarm_raw

    def _zero_optimizer_state(self) -> None:
        lower_ctl.restore_module_tensors(self.agent, self._initial_model)
        with torch.no_grad():
            for parameter, state in self.optimizer.state.items():
                initial_state = self._initial_optimizer_state.get(parameter, {})
                for key, value in state.items():
                    if torch.is_tensor(value):
                        initial_value = initial_state.get(key)
                        if torch.is_tensor(initial_value):
                            value.copy_(initial_value)
                        else:
                            value.zero_()
        self.optimizer.zero_grad(set_to_none=False)
        self.loss.zero_()
        self.ae1_loss.zero_()
        self.ae4_loss_raw.zero_()
        self.lowerarm_length_raw_mse.zero_()
        self.gradient_norm.zero_()

    def sample_(self) -> None:
        gaze = runtime_data.sample_gaze(
            self.batch_size, self._sampling_generator, torch.device("cpu")
        )
        self.last_zero_gaze_count = int(
            (gaze.abs().amax(dim=-1) == 0).sum()
        )
        noisy_mask = torch.zeros(self.batch_size, dtype=torch.bool)
        if self.noisy_rows_per_batch:
            noisy_rows = torch.randperm(
                self.batch_size, generator=self._sampling_generator
            )[: self.noisy_rows_per_batch]
            noisy_mask[noisy_rows] = True
        initial_gaze, random_initial_gaze_mask = sample_initialization_gaze(
            gaze,
            noisy_mask,
            self._sampling_generator,
            self.random_initial_gaze_half_per_noise_class,
        )

        def sampled_vectors(shape: tuple[int, ...], maximum: float) -> torch.Tensor:
            vectors = torch.randn(
                (*shape, 3), generator=self._sampling_generator
            )
            vectors = tl.normalize(vectors)
            magnitudes = torch.rand(
                (*shape, 1), generator=self._sampling_generator
            ) * float(maximum)
            mask_shape = (self.batch_size,) + (1,) * len(shape)
            return vectors * magnitudes * noisy_mask.reshape(mask_shape)

        pelvis_rotation = sampled_vectors(
            (self.batch_size,),
            math.radians(
                self.reset_noise_profile.get("pelvis_rotation_deg_max", 0.0)
            ),
        )
        pelvis_translation = sampled_vectors(
            (self.batch_size,),
            self.reset_noise_profile.get("pelvis_location_cm_max", 0.0) * 0.01,
        )
        fk_rotation = sampled_vectors(
            (self.batch_size, len(EPISODE_NOISE_FK_BONES)),
            math.radians(
                self.reset_noise_profile.get("fk_rotation_deg_max", 0.0)
            ),
        )
        hand_translation = sampled_vectors(
            (self.batch_size, len(EPISODE_NOISE_HAND_BONES)),
            self.reset_noise_profile.get("hand_location_cm_max", 0.0) * 0.01,
        )
        hand_rotation = sampled_vectors(
            (self.batch_size, len(EPISODE_NOISE_HAND_BONES)),
            math.radians(
                self.reset_noise_profile.get("hand_rotation_deg_max", 0.0)
            ),
        )
        self.last_noisy_count = int(noisy_mask.sum())
        self.last_random_initial_gaze_count = int(random_initial_gaze_mask.sum())
        self.last_random_initial_gaze_clean_count = int(
            (random_initial_gaze_mask & ~noisy_mask).sum()
        )
        self.last_random_initial_gaze_noisy_count = int(
            (random_initial_gaze_mask & noisy_mask).sum()
        )
        offset = 0
        for key in self.GROUPS:
            category, _mode = key
            runtime = self.runtimes[category]
            clip_ids = torch.randint(
                0,
                len(runtime.lower_clips),
                (self.rows_per_group,),
                generator=self._sampling_generator,
                device="cpu",
            )
            maxima = self._maximum_start_cpu[category].index_select(0, clip_ids)
            unit = torch.rand(
                (self.rows_per_group,), generator=self._sampling_generator
            )
            starts = 2 + torch.floor(unit * (maxima - 1).to(torch.float32)).long()
            end = offset + self.rows_per_group
            self._clip_ids[key].copy_(clip_ids.to(self.device))
            self._starts[key].copy_(starts.to(self.device))
            self._gaze[key].copy_(gaze[offset:end].to(self.device))
            self._initial_gaze[key].copy_(initial_gaze[offset:end].to(self.device))
            self._random_initial_gaze_mask[key].copy_(
                random_initial_gaze_mask[offset:end].to(self.device)
            )
            staged_noise = (
                noisy_mask[offset:end],
                pelvis_rotation[offset:end],
                pelvis_translation[offset:end],
                fk_rotation[offset:end],
                hand_translation[offset:end],
                hand_rotation[offset:end],
            )
            for destination, source in zip(
                self._episode_noise[key], staged_noise, strict=True
            ):
                destination.copy_(source.to(self.device))
            offset = end

    def _capture(self) -> float:
        started = time.perf_counter()
        side_stream = torch.cuda.Stream()
        side_stream.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(side_stream):
            for _ in range(3):
                self.sample_()
                self.optimizer.zero_grad(set_to_none=False)
                for key in self.GROUPS:
                    for start, end, row_horizon in self._group_chunks[key]:
                        total, _ae1, _ae4, _lowerarm = self._scaled_horizon_terms(
                            key, slice(start, end), row_horizon
                        )
                        total.backward()
                torch.nn.utils.clip_grad_norm_(self.agent.parameters(), 50.0)
                self.optimizer.step()
        torch.cuda.current_stream().wait_stream(side_stream)
        torch.cuda.synchronize(self.device)
        self._zero_optimizer_state()
        self.sample_()
        # Warm-up runs through the eager allocator, while CUDA Graph capture
        # owns a private pool.  Release only the now-dead eager rollout cache
        # before capture so a full K32 update is not needlessly resident twice.
        # Model parameters, gradients and AdamW state remain live and intact.
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(self.device)
        free_bytes, total_bytes = torch.cuda.mem_get_info(self.device)
        print(
            "CUDA_GRAPH_AE1_FULL_PRECAPTURE "
            f"allocated_gib={torch.cuda.memory_allocated(self.device) / 2**30:.3f} "
            f"reserved_gib={torch.cuda.memory_reserved(self.device) / 2**30:.3f} "
            f"free_gib={free_bytes / 2**30:.3f} total_gib={total_bytes / 2**30:.3f}",
            flush=True,
        )
        pool = torch.cuda.graph_pool_handle()
        # These graphs are always replayed serially, so they safely share one
        # private memory pool.  Peak capture memory is therefore the largest
        # exact-horizon cohort instead of all rollout bodies.
        # Gradients still accumulate into the same parameter buffers, producing
        # one exact full-batch mean and one optimizer update.
        with torch.cuda.graph(self._zero_graph, pool=pool):
            self.optimizer.zero_grad(set_to_none=False)
            self.loss.zero_()
            self.ae1_loss.zero_()
            self.ae4_loss_raw.zero_()
            self.lowerarm_length_raw_mse.zero_()
            self.gradient_norm.zero_()
        for key in self.GROUPS:
            for start, end, row_horizon in self._group_chunks[key]:
                with torch.cuda.graph(
                    self._graphs[(key, row_horizon)], pool=pool
                ):
                    micro_loss, micro_ae1, micro_ae4_raw, micro_lowerarm_raw = (
                        self._scaled_horizon_terms(
                            key, slice(start, end), row_horizon
                        )
                    )
                    self.loss.add_(micro_loss.detach())
                    self.ae1_loss.add_(micro_ae1.detach())
                    self.ae4_loss_raw.add_(micro_ae4_raw.detach())
                    self.lowerarm_length_raw_mse.add_(micro_lowerarm_raw.detach())
                    micro_loss.backward()
                del micro_loss, micro_ae1, micro_ae4_raw, micro_lowerarm_raw
        with torch.cuda.graph(self._update_graph, pool=pool):
            norm = torch.nn.utils.clip_grad_norm_(self.agent.parameters(), 50.0)
            self.gradient_norm.copy_(norm.detach())
            self.optimizer.step()
        torch.cuda.synchronize(self.device)
        free_bytes, total_bytes = torch.cuda.mem_get_info(self.device)
        print(
            "CUDA_GRAPH_AE1_FULL_POSTCAPTURE "
            f"allocated_gib={torch.cuda.memory_allocated(self.device) / 2**30:.3f} "
            f"reserved_gib={torch.cuda.memory_reserved(self.device) / 2**30:.3f} "
            f"peak_allocated_gib={torch.cuda.max_memory_allocated(self.device) / 2**30:.3f} "
            f"peak_reserved_gib={torch.cuda.max_memory_reserved(self.device) / 2**30:.3f} "
            f"free_gib={free_bytes / 2**30:.3f} total_gib={total_bytes / 2**30:.3f}",
            flush=True,
        )
        self._zero_optimizer_state()
        torch.cuda.synchronize(self.device)
        self.sample_()
        return time.perf_counter() - started

    def _replay_sampled(self) -> None:
        self._zero_graph.replay()
        for key in self.GROUPS:
            for _start, _end, row_horizon in self._group_chunks[key]:
                self._graphs[(key, row_horizon)].replay()
        self._update_graph.replay()

    def replay_loss_only_current(self) -> None:
        self._zero_graph.replay()
        for key in self.GROUPS:
            for _start, _end, row_horizon in self._group_chunks[key]:
                self._graphs[(key, row_horizon)].replay()

    @torch.no_grad()
    def parity_reference(self) -> float:
        total = self.agent.delta_head.weight.new_zeros(())
        for key in self.GROUPS:
            for start, end, row_horizon in self._group_chunks[key]:
                cohort_total, _ae1, _ae4, _lowerarm = self._scaled_horizon_terms(
                    key, slice(start, end), row_horizon
                )
                total = total + cohort_total
        return float(total.detach().cpu())

    def replay_current(self) -> None:
        self._replay_sampled()

    def step(self) -> None:
        self.sample_()
        self._replay_sampled()

    @torch.no_grad()
    def prepare_debug_rollout(self) -> None:
        for key in self.GROUPS:
            self._forward(key, debug=True)

    def effective_k_cpu(self) -> torch.Tensor:
        return torch.cat(
            [self._effective_k[key].detach().cpu() for key in self.GROUPS], dim=0
        )

    def gaze_cpu(self) -> torch.Tensor:
        return torch.cat(
            [self._gaze[key].detach().cpu() for key in self.GROUPS], dim=0
        )

    def noisy_mask_cpu(self) -> torch.Tensor:
        return torch.cat(
            [self._episode_noise[key][0].detach().cpu() for key in self.GROUPS],
            dim=0,
        )

    def sampled_rows(self) -> dict[str, int]:
        return {
            f"{category}_{'sheathed' if mode < 0 else 'drawn'}": self.rows_per_group
            for category, mode in self.GROUPS
        }


@torch.inference_mode()
def export_graph_rollout(
    path: Path,
    run_id: str,
    step: int,
    graph_step: DirectMseCudaGraphStep | Ae1CudaGraphStep | Ae1MixedKCudaGraphStep,
) -> None:
    runtime = graph_step.runtime
    graph_step.prepare_debug_rollout()
    clip_ids = torch.zeros_like(graph_step.starts)
    lower = graph_step.debug_lower.detach().clone()
    upper = graph_step.debug_upper.detach().clone()
    pelvis = graph_step.debug_pelvis.detach().clone()
    frames = graph_step.debug_frames.detach().clone()
    positions: list[torch.Tensor] = []
    rotations: list[torch.Tensor] = []
    root_positions: list[torch.Tensor] = []
    root_rotations: list[torch.Tensor] = []
    for frame_slot in range(graph_step.maximum_k + 1):
        root = runtime_data.root_state(
            runtime, frames[:, frame_slot], clip_ids
        )
        pos, rot = decode_rows(
            runtime,
            graph_step.mode,
            lower[:, frame_slot],
            upper[:, frame_slot],
            pelvis[:, frame_slot],
            *root,
            clip_ids,
        )
        positions.append(pos.detach().cpu())
        rotations.append(rot.detach().cpu())
        root_positions.append(root[0].detach().cpu())
        root_rotations.append(root[1].detach().cpu())
    starts = graph_step.starts.detach().cpu()
    effective = graph_step.effective_k.detach().cpu()
    relative = runtime.relatives[0]
    rows = [
        {
            "row": row,
            "clip_id": 0,
            "clip_name": Path(relative).stem,
            "clip_path": str(upper_data.SWORD_ROOT / relative),
            "start": int(starts[row]),
            "effective_k": int(effective[row]),
            "virtual": False,
            "noisy": False,
            "noisy_seed_source": "exact_cuda_graph_row",
            "has_sword": True,
            "locomotion_category": runtime_data.CATEGORY_WALK,
            "gaze_normalized": [0.0, 0.0],
        }
        for row in range(graph_step.batch_size)
    ]
    payload = exact_training_rollout_payload(
        run_id,
        step,
        runtime.full_by_mode[graph_step.mode],
        rows,
        torch.stack(positions, dim=1),
        torch.stack(rotations, dim=1),
        torch.stack(root_positions, dim=1),
        torch.stack(root_rotations, dim=1),
        frames.detach().cpu(),
    )
    payload["metadata"]["capture_source"] = "exact_cuda_graph_microbatch"
    payload["metadata"]["source_contract"] = (
        "exact state tensors copied from the captured training graph; physical "
        "pose decoding and JSON serialization occurred only after synchronization"
    )
    atomic_compact_json(path, payload)


@torch.inference_mode()
def export_full_corpus_graph_rollout(
    path: Path,
    run_id: str,
    step: int,
    graph_step: FullCorpusAe1CudaGraphStep,
) -> None:
    """Serialize the exact current staged batch for the local replayer."""

    graph_step.prepare_debug_rollout()
    all_positions: list[torch.Tensor] = []
    all_rotations: list[torch.Tensor] = []
    all_root_positions: list[torch.Tensor] = []
    all_root_rotations: list[torch.Tensor] = []
    all_frames: list[torch.Tensor] = []
    rows: list[dict[str, Any]] = []
    row_offset = 0
    for key in graph_step.GROUPS:
        category, mode = key
        runtime = graph_step.runtimes[category]
        clip_ids = graph_step._clip_ids[key]
        starts = graph_step._starts[key].detach().cpu()
        effective = graph_step._effective_k[key].detach().cpu()
        gaze = graph_step._gaze[key].detach().cpu()
        initial_gaze = graph_step._initial_gaze[key].detach().cpu()
        random_initial_gaze_mask = (
            graph_step._random_initial_gaze_mask[key].detach().cpu()
        )
        _lower, _upper, _pelvis, frames = (
            value.detach().clone() for value in graph_step._debug[key]
        )
        exact_positions, exact_rotations = (
            value.detach().clone() for value in graph_step._debug_pose[key]
        )
        staged_noise = tuple(
            value.detach().cpu() for value in graph_step._episode_noise[key]
        )
        noisy_mask = staged_noise[0]
        positions: list[torch.Tensor] = []
        rotations: list[torch.Tensor] = []
        root_positions: list[torch.Tensor] = []
        root_rotations: list[torch.Tensor] = []
        for frame_slot in range(graph_step.maximum_k + 1):
            root = runtime_data.root_state(
                runtime, frames[:, frame_slot], clip_ids
            )
            positions.append(exact_positions[:, frame_slot].cpu())
            rotations.append(exact_rotations[:, frame_slot].cpu())
            root_positions.append(root[0].detach().cpu())
            root_rotations.append(root[1].detach().cpu())
        all_positions.append(torch.stack(positions, dim=1))
        all_rotations.append(torch.stack(rotations, dim=1))
        all_root_positions.append(torch.stack(root_positions, dim=1))
        all_root_rotations.append(torch.stack(root_rotations, dim=1))
        all_frames.append(frames.detach().cpu())
        clip_ids_cpu = clip_ids.detach().cpu()
        dataset_root = (
            upper_data.SWORD_ROOT
            if mode == runtime_data.MODE_DRAWN
            else upper_data.ORIGINAL_ROOT
        )
        for local_row in range(graph_step.rows_per_group):
            clip_id = int(clip_ids_cpu[local_row])
            relative = runtime.relatives[clip_id]
            rows.append(
                {
                    "row": row_offset + local_row,
                    "clip_id": clip_id,
                    "clip_name": Path(relative).stem,
                    "clip_path": str(dataset_root / relative),
                    "start": int(starts[local_row]),
                    "effective_k": int(effective[local_row]),
                    "virtual": False,
                    "noisy": bool(noisy_mask[local_row]),
                    "noisy_seed_source": (
                        "episode_start_pose_noise"
                        if bool(noisy_mask[local_row])
                        else "clean_episode_start"
                    ),
                    "episode_start_noise": {
                        "pelvis_rotation_deg": math.degrees(
                            float(torch.linalg.norm(staged_noise[1][local_row]))
                        ),
                        "pelvis_location_cm": 100.0
                        * float(torch.linalg.norm(staged_noise[2][local_row])),
                        "fk_rotation_deg_max_sampled_bone": math.degrees(
                            float(
                                torch.linalg.norm(
                                    staged_noise[3][local_row], dim=-1
                                ).max()
                            )
                        ),
                        "hand_location_cm_max_sampled_hand": 100.0
                        * float(
                            torch.linalg.norm(
                                staged_noise[4][local_row], dim=-1
                            ).max()
                        ),
                        "hand_rotation_deg_max_sampled_hand": math.degrees(
                            float(
                                torch.linalg.norm(
                                    staged_noise[5][local_row], dim=-1
                                ).max()
                            )
                        ),
                    },
                    "has_sword": bool(mode == runtime_data.MODE_DRAWN),
                    "locomotion_category": category,
                    "gaze_normalized": [
                        float(gaze[local_row, 0]),
                        float(gaze[local_row, 1]),
                    ],
                    "initial_gaze_normalized": [
                        float(initial_gaze[local_row, 0]),
                        float(initial_gaze[local_row, 1]),
                    ],
                    "initial_gaze_random": bool(
                        random_initial_gaze_mask[local_row]
                    ),
                }
            )
        row_offset += graph_step.rows_per_group
    prototype = graph_step.runtimes[runtime_data.CATEGORY_WALK].full_by_mode[
        runtime_data.MODE_SHEATHED
    ]
    payload = exact_training_rollout_payload(
        run_id,
        step,
        prototype,
        rows,
        torch.cat(all_positions, dim=0),
        torch.cat(all_rotations, dim=0),
        torch.cat(all_root_positions, dim=0),
        torch.cat(all_root_rotations, dim=0),
        torch.cat(all_frames, dim=0),
    )
    payload["metadata"]["capture_source"] = "exact_full_corpus_cuda_graph_batch"
    payload["metadata"]["checkpoint_kind"] = CACHED_LOWER_CONTROLLER_KIND
    payload["metadata"]["controller_output_dim"] = upper_data.OUTPUT_DIM
    payload["metadata"]["pelvis_source"] = "continuous_frozen_lower_cache"
    payload["metadata"]["lower_cache_contract"] = (
        "one continuous frozen-policy rollout from frame zero per animation"
    )
    payload["metadata"]["episode_start_noise"] = {
        **graph_step.reset_noise_profile,
        "sampling": "independent_uniform_magnitude_0_to_max_uniform_sphere_direction",
        "lifetime": "current_pose_at_episode_reset_only",
        "exact_noisy_rows": int(graph_step.noisy_rows_per_batch),
        "exact_clean_rows": int(
            graph_step.batch_size - graph_step.noisy_rows_per_batch
        ),
    }
    payload["metadata"]["initialization_gaze"] = {
        **initialization_gaze_contract(
            graph_step.random_initial_gaze_half_per_noise_class
        ),
        "exact_random_clean_rows": int(
            graph_step.last_random_initial_gaze_clean_count
        ),
        "exact_random_noisy_rows": int(
            graph_step.last_random_initial_gaze_noisy_count
        ),
    }
    payload["metadata"]["source_contract"] = (
        f"exact staged BS{graph_step.batch_size} upper-only CUDA Graph rows over the continuous cached "
        "lower dataset; full pose decoding and JSON serialization occur only at "
        "the sparse export cadence"
    )
    atomic_compact_json(path, payload)


def train_direct_mse_cuda_graph(
    args: argparse.Namespace,
    runtime: runtime_data.CategoryRuntime,
    mode: float,
    agent: UpperPelvisAgent,
    optimizer: torch.optim.Optimizer,
    run_id: str,
    run_dir: Path,
    checkpoints_dir: Path,
    debug_dir: Path,
    metadata: dict[str, Any],
    writer: SummaryWriter,
    active_marker: Path,
    started: float,
) -> None:
    if args.fixed_k is None:
        raise ValueError("CUDA Graph direct-MSE training requires --fixed-k")
    maximum_k = int(args.fixed_k)
    batch_size = int(args.batch_size)
    if int(args.gradient_accumulation_steps) != 1:
        raise ValueError("Fast CUDA Graph path requires accumulation=1")

    full_clip = runtime.full_by_mode[mode]
    frame_indices = torch.arange(int(full_clip.T), dtype=torch.long)
    neutral_gaze = torch.zeros((int(full_clip.T), 2), dtype=torch.float32)
    # The only CPU pose construction in the training path: performed once,
    # before capture, then retained as a permanent GPU lookup table.
    upper_targets = upper_data.gaze_overlay_upper_state(
        full_clip, frame_indices, neutral_gaze
    ).to(device=runtime.store.device, dtype=torch.float32)
    graph_step = DirectMseCudaGraphStep(
        agent,
        optimizer,
        runtime,
        mode,
        batch_size,
        maximum_k,
        upper_targets,
    )

    if isinstance(graph_step, Ae1MixedKCudaGraphStep):
        graph_step._zero_graph.replay()
        torch.cuda.synchronize(runtime.store.device)
    eager_reference = graph_step.parity_reference()
    if isinstance(graph_step, Ae1MixedKCudaGraphStep):
        graph_step.replay_loss_only_current()
    else:
        graph_step.replay_current()
    torch.cuda.synchronize(runtime.store.device)
    graph_reference = (
        float(graph_step.loss.cpu()),
        float(graph_step.upper_mse.cpu()),
        float(graph_step.pelvis_mse.cpu()),
    )
    parity_abs = [
        abs(eager - captured)
        for eager, captured in zip(eager_reference, graph_reference)
    ]
    if not isinstance(graph_step, Ae1MixedKCudaGraphStep):
        graph_step._zero_optimizer_state()
    torch.cuda.synchronize(runtime.store.device)
    if max(parity_abs) > 2.0e-6:
        raise RuntimeError(
            "CUDA Graph/eager forward parity failed: "
            f"eager={eager_reference} graph={graph_reference} abs={parity_abs}"
        )
    graph_report = {
        "kind": graph_step.kind,
        "capture_seconds": graph_step.capture_seconds,
        "eager_reference": list(eager_reference),
        "graph_reference": list(graph_reference),
        "maximum_abs_difference": max(parity_abs),
        "upper_targets": {
            "construction": "one_time_cpu_neutral_gaze_then_permanent_gpu_tensor",
            "lookup": "gpu_index_select",
            "shape": list(upper_targets.shape),
        },
        "hot_loop": (
            "gpu_sampling + frozen_lower + controller + feedback_IK + rollout + "
            "direct_MSE + backward + grad_clip + fused_capturable_AdamW"
        ),
        "excluded_from_hot_loop": [
            "physical_pose_decode",
            "world_space_diagnostics",
            "tensorboard_serialization",
            "checkpoint_serialization",
            "replayer_json_serialization",
        ],
    }
    atomic_json(debug_dir / "cuda_graph_validation.json", graph_report)
    print(
        f"CUDA_GRAPH_READY capture_s={graph_step.capture_seconds:.3f} "
        f"parity_max_abs={max(parity_abs):.3g}",
        flush=True,
    )

    best = float("inf")
    step = 0
    last_log_time = time.perf_counter()
    last_log_step = 0
    log_every = max(1, int(args.log_every))
    export_every = max(1, int(args.rollout_export_every))
    checkpoint_every = max(1, int(args.checkpoint_every))
    while int(args.train_steps) <= 0 or step < int(args.train_steps):
        if stop_requested(args):
            break
        step += 1
        graph_step.step()
        should_log = step == 1 or step % log_every == 0
        should_checkpoint = step % checkpoint_every == 0
        should_export = step % export_every == 0
        if not (should_log or should_checkpoint or should_export):
            continue
        torch.cuda.synchronize(runtime.store.device)
        elapsed = time.perf_counter() - started
        score = float(graph_step.loss.cpu())
        upper_mse = float(graph_step.upper_mse.cpu())
        pelvis_mse = float(graph_step.pelvis_mse.cpu())
        gradient_norm = float(graph_step.gradient_norm.cpu())
        finite = all(
            math.isfinite(value)
            for value in (score, upper_mse, pelvis_mse, gradient_norm)
        )
        if not finite:
            raise RuntimeError(
                f"Non-finite CUDA Graph metrics at step {step}: "
                f"loss={score} upper={upper_mse} pelvis={pelvis_mse} grad={gradient_norm} "
                f"starts={graph_step.starts.detach().cpu().tolist()} "
                f"effective_k={graph_step.effective_k.detach().cpu().tolist()}"
            )
        best = min(best, score)
        now = time.perf_counter()
        steps_per_second = (step - last_log_step) / max(1.0e-9, now - last_log_time)
        last_log_time = now
        last_log_step = step
        effective = graph_step.effective_k.detach().cpu()
        counts = {
            str(value): int((effective == value).sum())
            for value in lower_ctl.rollout_values_for(maximum_k)
        }
        if should_log:
            writer.add_scalar("loss/total", score, step)
            writer.add_scalar("loss/upper_mse", upper_mse, step)
            writer.add_scalar("loss/pelvis_mse", pelvis_mse, step)
            writer.add_scalar("gradient_norm", gradient_norm, step)
            writer.add_scalar("Kmax", maximum_k, step)
            writer.add_scalar("performance/steps_per_second", steps_per_second, step)
            writer.add_scalar("performance/ms_per_step", 1000.0 / steps_per_second, step)
            writer.flush()
            status = {
                "run_id": run_id,
                "step": step,
                "total_loss": score,
                "upper_mse": upper_mse,
                "pelvis_mse": pelvis_mse,
                "best": best,
                "gradient_norm": gradient_norm,
                "Kmax": maximum_k,
                "effective_k_counts": counts,
                "motion_scope": args.motion_scope,
                "sampled_rows": {"walk_drawn": batch_size},
                "gaze_fixed_normalized": [0.0, 0.0],
                "learning_rate": float(args.learning_rate),
                "cuda_graph": True,
                "hot_loop": graph_step.kind,
                "steps_per_second": steps_per_second,
                "elapsed_seconds": elapsed,
                "finite": True,
            }
            atomic_json(run_dir / "status.json", status)
            print(
                f"UPPER_PELVIS_GRAPH step={step} total={score:.8g} "
                f"upper_mse={upper_mse:.8g} pelvis_mse={pelvis_mse:.8g} "
                f"grad={gradient_norm:.6g} speed={steps_per_second:.3f}step/s "
                f"elapsed_s={elapsed:.1f}",
                flush=True,
            )
        if should_checkpoint:
            save_checkpoint(
                checkpoints_dir / f"{run_id}_latest.pt",
                agent,
                optimizer,
                step,
                best,
                elapsed,
                maximum_k,
                metadata,
            )
            if step % checkpoint_every == 0:
                save_checkpoint(
                    checkpoints_dir / f"checkpoint_step_{step:06d}.pt",
                    agent,
                    optimizer,
                    step,
                    best,
                    elapsed,
                    maximum_k,
                    metadata,
                )
        if should_export:
            export_graph_rollout(
                debug_dir / "last_batch_rollout.json",
                run_id,
                step,
                graph_step,
            )
        if bool(args.smoke):
            break
    writer.close()
    active_marker.unlink(missing_ok=True)
    print(f"UPPER_PELVIS_COMPLETE run={run_id}", flush=True)


def train_ae1_cuda_graph(
    args: argparse.Namespace,
    runtime: runtime_data.CategoryRuntime,
    mode: float,
    agent: UpperPelvisAgent,
    optimizer: torch.optim.Optimizer,
    ae: torch.nn.Module,
    mean: torch.Tensor,
    std: torch.Tensor,
    output_weights: torch.Tensor,
    run_id: str,
    run_dir: Path,
    checkpoints_dir: Path,
    debug_dir: Path,
    metadata: dict[str, Any],
    writer: SummaryWriter,
    active_marker: Path,
    started: float,
    objective: str = "ae1",
) -> None:
    """Run the full fixed-K rollout with AE1 or AE22 as sole objective."""

    if args.fixed_k is None:
        raise ValueError(f"CUDA Graph {objective.upper()}-only training requires --fixed-k")
    maximum_k = int(args.fixed_k)
    batch_size = int(args.batch_size)
    if int(args.gradient_accumulation_steps) != 1:
        raise ValueError("Fast CUDA Graph path requires accumulation=1")

    full_clip = runtime.full_by_mode[mode]
    frame_indices = torch.arange(int(full_clip.T), dtype=torch.long)
    neutral_gaze = torch.zeros((int(full_clip.T), 2), dtype=torch.float32)
    # Construct the one-animation, neutral-gaze authored sequence once.  Training
    # thereafter only performs GPU index selection from this permanent tensor.
    upper_targets = upper_data.gaze_overlay_upper_state(
        full_clip, frame_indices, neutral_gaze
    ).to(device=runtime.store.device, dtype=torch.float32)
    if objective == "ae1" and batch_size == 8 and maximum_k == 32:
        graph_step = Ae1MixedKCudaGraphStep(
            agent,
            optimizer,
            ae,
            mean,
            std,
            output_weights,
            runtime,
            mode,
            upper_targets,
        )
    else:
        graph_step = Ae1CudaGraphStep(
            agent,
            optimizer,
            ae,
            mean,
            std,
            output_weights,
            runtime,
            mode,
            batch_size,
            maximum_k,
            upper_targets,
            objective,
        )

    eager_reference = graph_step.parity_reference()
    if isinstance(graph_step, Ae1MixedKCudaGraphStep):
        graph_step.replay_loss_only_current()
    else:
        graph_step.replay_current()
    torch.cuda.synchronize(runtime.store.device)
    graph_reference = float(graph_step.loss.cpu())
    parity_abs = abs(eager_reference - graph_reference)
    if not isinstance(graph_step, Ae1MixedKCudaGraphStep):
        graph_step._zero_optimizer_state()
    torch.cuda.synchronize(runtime.store.device)
    if parity_abs > 2.0e-6:
        raise RuntimeError(
            f"CUDA Graph/eager {objective.upper()} parity failed: "
            f"eager={eager_reference} graph={graph_reference} abs={parity_abs}"
        )
    graph_report = {
        "kind": graph_step.kind,
        "capture_seconds": graph_step.capture_seconds,
        "eager_reference": eager_reference,
        "graph_reference": graph_reference,
        "maximum_abs_difference": parity_abs,
        "upper_targets": {
            "construction": "one_time_cpu_neutral_gaze_then_permanent_gpu_tensor",
            "lookup": "gpu_index_select",
            "shape": list(upper_targets.shape),
        },
        "hot_loop": (
            "gpu_sampling + frozen_lower + controller + feedback_IK + physical_decode + "
            f"{objective.upper()} + backward + grad_clip + "
            + (
                "foreach_capturable_AdamW"
                if isinstance(graph_step, Ae1MixedKCudaGraphStep)
                else "fused_capturable_AdamW"
            )
        ),
        "execution_partition": (
            "four_single_use_cuda_cohort_graphs_{32:4,16:2,8:1,1:1}_then_one_AdamW_update"
            if isinstance(graph_step, Ae1MixedKCudaGraphStep)
            else "single_monolithic_cuda_graph"
        ),
        "disabled": [
            "direct_MSE_loss_or_metric",
            "AE4_load_inference_or_loss",
            "world_space_diagnostics",
            "tensorboard_serialization",
            "checkpoint_serialization",
            "replayer_json_serialization",
        ],
    }
    atomic_json(debug_dir / "cuda_graph_validation.json", graph_report)
    print(
        f"CUDA_GRAPH_{objective.upper()}_READY capture_s={graph_step.capture_seconds:.3f} "
        f"parity_max_abs={parity_abs:.3g}",
        flush=True,
    )

    best = float("inf")
    step = 0
    last_log_time = time.perf_counter()
    last_log_step = 0
    log_every = max(1, int(args.log_every))
    export_every = max(1, int(args.rollout_export_every))
    checkpoint_every = max(1, int(args.checkpoint_every))
    while int(args.train_steps) <= 0 or step < int(args.train_steps):
        if stop_requested(args):
            break
        step += 1
        graph_step.step()
        should_log = step == 1 or step % log_every == 0
        should_checkpoint = step % checkpoint_every == 0
        should_export = step % export_every == 0
        if not (should_log or should_checkpoint or should_export):
            continue

        torch.cuda.synchronize(runtime.store.device)
        elapsed = time.perf_counter() - started
        score = float(graph_step.loss.cpu())
        gradient_norm = float(graph_step.gradient_norm.cpu())
        if not (math.isfinite(score) and math.isfinite(gradient_norm)):
            raise RuntimeError(
                f"Non-finite {objective.upper()} CUDA Graph metrics at step {step}: "
                f"{objective}={score} grad={gradient_norm} "
                f"starts={graph_step.starts.detach().cpu().tolist()} "
                f"effective_k={graph_step.effective_k.detach().cpu().tolist()}"
            )
        best = min(best, score)
        now = time.perf_counter()
        steps_per_second = (step - last_log_step) / max(1.0e-9, now - last_log_time)
        last_log_time = now
        last_log_step = step
        effective = graph_step.effective_k.detach().cpu()
        counts = {
            str(value): int((effective == value).sum())
            for value in lower_ctl.rollout_values_for(maximum_k)
        }
        if should_log:
            writer.add_scalar("loss/total", score, step)
            writer.add_scalar(f"loss/{objective}", score, step)
            writer.add_scalar("gradient_norm", gradient_norm, step)
            writer.add_scalar("Kmax", maximum_k, step)
            writer.add_scalar("performance/steps_per_second", steps_per_second, step)
            writer.add_scalar("performance/ms_per_step", 1000.0 / steps_per_second, step)
            writer.flush()
            status = {
                "run_id": run_id,
                "step": step,
                "total_loss": score,
                objective: score,
                "best": best,
                "gradient_norm": gradient_norm,
                "Kmax": maximum_k,
                "effective_k_counts": counts,
                "motion_scope": args.motion_scope,
                "sampled_rows": {"walk_drawn": batch_size},
                "gaze_fixed_normalized": [0.0, 0.0],
                "learning_rate": float(args.learning_rate),
                "cuda_graph": True,
                "hot_loop": graph_step.kind,
                "direct_mse_enabled": False,
                "ae4_enabled": False,
                "steps_per_second": steps_per_second,
                "elapsed_seconds": elapsed,
                "finite": True,
            }
            atomic_json(run_dir / "status.json", status)
            print(
                f"UPPER_PELVIS_{objective.upper()}_GRAPH step={step} {objective}={score:.8g} "
                f"grad={gradient_norm:.6g} speed={steps_per_second:.3f}step/s "
                f"elapsed_s={elapsed:.1f}",
                flush=True,
            )
        if should_checkpoint:
            save_checkpoint(
                checkpoints_dir / f"{run_id}_latest.pt",
                agent,
                optimizer,
                step,
                best,
                elapsed,
                maximum_k,
                metadata,
            )
            if step % checkpoint_every == 0:
                save_checkpoint(
                    checkpoints_dir / f"checkpoint_step_{step:06d}.pt",
                    agent,
                    optimizer,
                    step,
                    best,
                    elapsed,
                    maximum_k,
                    metadata,
                )
        if should_export:
            export_graph_rollout(
                debug_dir / "last_batch_rollout.json",
                run_id,
                step,
                graph_step,
            )
        if bool(args.smoke):
            break
    writer.close()
    active_marker.unlink(missing_ok=True)
    print(f"UPPER_PELVIS_COMPLETE run={run_id}", flush=True)


def train_full_corpus_ae1_cuda_graph(
    args: argparse.Namespace,
    runtimes: dict[str, runtime_data.CategoryRuntime],
    caches: dict[str, cached_lower_data.CachedLowerCategory],
    agent: UpperCachedLowerAgent,
    optimizer: torch.optim.Optimizer,
    ae: torch.nn.Module,
    mean: torch.Tensor,
    std: torch.Tensor,
    output_weights: torch.Tensor,
    ae4: torch.nn.Module | None,
    ae4_input_mean: torch.Tensor | None,
    ae4_input_std: torch.Tensor | None,
    ae4_target_mean: torch.Tensor | None,
    ae4_target_std: torch.Tensor | None,
    ae4_loss_weight: float,
    run_id: str,
    run_dir: Path,
    checkpoints_dir: Path,
    debug_dir: Path,
    metadata: dict[str, Any],
    writer: SummaryWriter,
    active_marker: Path,
    started: float,
    initial_step: int,
    initial_best: float,
) -> None:
    """Run the full-gaze/full-corpus CUDA Graph recipe."""

    if int(args.fixed_k or 0) != 32:
        raise ValueError("Full-corpus CUDA Graph training requires --fixed-k 32")
    if int(args.batch_size) not in (32, 64):
        raise ValueError(
            "Full-corpus CUDA Graph training requires --batch-size 32 or 64"
        )
    if int(args.gradient_accumulation_steps) != 1:
        raise ValueError("Full-corpus CUDA Graph training requires accumulation=1")
    if int(args.rollout_gradient_window) < 0:
        raise ValueError(
            "--rollout-gradient-window must be zero (full) or positive"
        )

    graph_step = FullCorpusAe1CudaGraphStep(
        agent,
        optimizer,
        ae,
        mean,
        std,
        output_weights,
        runtimes,
        caches,
        int(args.seed),
        int(args.batch_size),
        int(args.rollout_gradient_window),
        ae4,
        ae4_input_mean,
        ae4_input_std,
        ae4_target_mean,
        ae4_target_std,
        float(ae4_loss_weight),
        bool(args.full_corpus_all_k32),
        bool(args.ae4_to_ae1_frame_blend),
        episode_noise_profile(args),
        bool(args.random_initial_gaze_half_per_noise_class),
    )
    eager_reference = graph_step.parity_reference()
    graph_step.replay_loss_only_current()
    torch.cuda.synchronize(graph_step.device)
    graph_reference = float(graph_step.loss.cpu())
    parity_abs = abs(eager_reference - graph_reference)
    graph_step._zero_optimizer_state()
    torch.cuda.synchronize(graph_step.device)
    if parity_abs > 2.0e-6:
        raise RuntimeError(
            "Full-corpus CUDA Graph/eager forward parity failed: "
            f"eager={eager_reference} graph={graph_reference} abs={parity_abs}"
        )
    graph_report = {
        "kind": graph_step.kind,
        "capture_seconds": graph_step.capture_seconds,
        "eager_reference": eager_reference,
        "graph_reference": graph_reference,
        "maximum_abs_difference": parity_abs,
        "physical_batch_size": graph_step.batch_size,
        "rollout_horizon": {
            "mode": "fixed_all_rows" if graph_step.all_rows_k32 else "geometric_mix",
            "maximum_k": 32,
            "effective_k_counts": {
                str(value): int((graph_step._effective_template_cpu == value).sum())
                for value in lower_ctl.rollout_values_for(32)
                if int((graph_step._effective_template_cpu == value).sum()) > 0
            },
        },
        "rollout_gradient_window": graph_step.rollout_gradient_window,
        "rollout_gradient_mode": (
            "full"
            if graph_step.rollout_gradient_window == 0
            else f"truncated_{graph_step.rollout_gradient_window}_frames"
        ),
        "balanced_groups": graph_step.sampled_rows(),
        "effective_k_counts": {
            str(value): int((graph_step._effective_template_cpu == value).sum())
            for value in lower_ctl.rollout_values_for(32)
            if int((graph_step._effective_template_cpu == value).sum()) > 0
        },
        "gaze": {
            "distribution": "uniform_normalized_yaw_pitch_-1_to_1",
            "zero_zero_probability": runtime_data.GAZE_ZERO_PROBABILITY,
            "lifetime": "constant_per_row_for_entire_rollout",
        },
        "initialization_gaze": initialization_gaze_contract(
            graph_step.random_initial_gaze_half_per_noise_class
        ),
        "ae4_rotation_loss": (
            ae4_rotation_loss_contract() if float(ae4_loss_weight) > 0.0 else None
        ),
        "ae1_ae4_temporal_blend": ae1_ae4_temporal_blend_contract(
            graph_step.ae4_to_ae1_frame_blend
        ),
        "episode_start_noise": {
            **graph_step.reset_noise_profile,
            "sampling": "independent_uniform_magnitude_0_to_max_uniform_sphere_direction",
            "lifetime": "current_pose_at_episode_reset_only",
            "exact_noisy_rows": graph_step.noisy_rows_per_batch,
            "exact_clean_rows": (
                graph_step.batch_size - graph_step.noisy_rows_per_batch
            ),
        },
        "hot_loop": (
            f"one captured BS{graph_step.batch_size} upper-only update containing four balanced group "
            + "rollouts with authored gaze overlay + continuous cached lower lookup "
            + (
                "+ one coherent decoded/re-encoded noisy reset pose "
                if graph_step.episode_noise_enabled
                else ""
            )
            + (
                "+ independently randomized initialization gaze on half of clean and half of noisy rows "
                if graph_step.random_initial_gaze_half_per_noise_class
                else ""
            )
            + "+ upper-only physical decode + AE1 + symmetric lower-arm length MSE "
            + (
                "+ frozen AE4 absolute-pose positions/hand MSE plus dead-zoned non-hand angular loss "
                if float(ae4_loss_weight) > 0.0
                else ""
            )
            + "+ backward + foreach AdamW"
        ),
        "excluded_from_hot_loop": [
            "frozen lower network inference",
            "lower cleanup and foot-roll integration",
            "pelvis output and pelvis feedback",
            "clip/start/K/gaze recipe sampling",
            "tensorboard serialization",
            "checkpoint serialization",
            "replayer pose decoding and JSON serialization",
        ]
        + ([] if graph_step.episode_noise_enabled else ["leg FK and leg IK"]),
    }
    atomic_json(debug_dir / "cuda_graph_validation.json", graph_report)
    # Publish a faithful selectable full-batch rollout immediately.  The replayer
    # must never sit empty while waiting for the first sparse export cadence.
    initial_rollout = debug_dir / f"rollout_step_{int(initial_step):06d}.json"
    export_full_corpus_graph_rollout(
        initial_rollout, run_id, int(initial_step), graph_step
    )
    atomic_copy(initial_rollout, debug_dir / "last_batch_rollout.json")
    print(
        f"CUDA_GRAPH_AE1_FULL_READY capture_s={graph_step.capture_seconds:.3f} "
        f"parity_max_abs={parity_abs:.3g}",
        flush=True,
    )

    best = float(initial_best)
    step = int(initial_step)
    last_log_time = time.perf_counter()
    last_log_step = step
    log_every = max(1, int(args.log_every))
    export_every = max(1, int(args.rollout_export_every))
    checkpoint_every = max(1, int(args.checkpoint_every))
    cumulative_zero = 0
    cumulative_rows = 0
    cumulative_noisy = 0
    cumulative_random_initial_gaze = 0
    while int(args.train_steps) <= 0 or step < int(args.train_steps):
        if stop_requested(args):
            break
        step += 1
        graph_step.step()
        cumulative_zero += int(graph_step.last_zero_gaze_count)
        cumulative_noisy += int(graph_step.last_noisy_count)
        cumulative_random_initial_gaze += int(
            graph_step.last_random_initial_gaze_count
        )
        cumulative_rows += graph_step.batch_size
        should_log = step == 1 or step % log_every == 0
        should_checkpoint = step % checkpoint_every == 0
        should_export = step % export_every == 0
        if not (should_log or should_checkpoint or should_export):
            continue
        torch.cuda.synchronize(graph_step.device)
        elapsed = time.perf_counter() - started
        score = float(graph_step.loss.cpu())
        ae1_score = float(graph_step.ae1_loss.cpu())
        ae4_raw = float(graph_step.ae4_loss_raw.cpu())
        ae4_loss = float(ae4_loss_weight) * ae4_raw
        lowerarm_length_raw_mse = float(
            graph_step.lowerarm_length_raw_mse.cpu()
        )

        lowerarm_length_loss = (
            LOWERARM_LENGTH_WEIGHT * lowerarm_length_raw_mse
        )
        gradient_norm = float(graph_step.gradient_norm.cpu())
        if not all(
            math.isfinite(value)
            for value in (
                score,
                ae1_score,
                ae4_raw,
                ae4_loss,
                lowerarm_length_raw_mse,
                lowerarm_length_loss,
                gradient_norm,
            )
        ):
            raise RuntimeError(
                f"Non-finite full-corpus CUDA Graph metrics at step {step}: "
                f"total={score} ae1={ae1_score} "
                f"ae4={ae4_loss} lowerarm={lowerarm_length_loss} grad={gradient_norm}"
            )
        best = min(best, score)
        now = time.perf_counter()
        steps_per_second = (step - last_log_step) / max(1.0e-9, now - last_log_time)
        last_log_time = now
        last_log_step = step
        effective = graph_step.effective_k_cpu()
        counts = {
            str(value): int((effective == value).sum())
            for value in lower_ctl.rollout_values_for(32)
            if int((effective == value).sum()) > 0
        }
        expected_counts = {
            str(value): int((graph_step._effective_template_cpu == value).sum())
            for value in lower_ctl.rollout_values_for(32)
            if int((graph_step._effective_template_cpu == value).sum()) > 0
        }
        if counts != expected_counts:
            raise RuntimeError(f"Full-corpus rollout-horizon counts drifted: {counts}")
        zero_fraction = cumulative_zero / max(1, cumulative_rows)
        noisy_fraction = cumulative_noisy / max(1, cumulative_rows)
        random_initial_gaze_fraction = (
            cumulative_random_initial_gaze / max(1, cumulative_rows)
        )
        if int(graph_step.last_noisy_count) != int(graph_step.noisy_rows_per_batch):
            raise RuntimeError(
                "Episode-start noisy-row count drifted: "
                f"{graph_step.last_noisy_count} != {graph_step.noisy_rows_per_batch}"
            )
        if graph_step.random_initial_gaze_half_per_noise_class:
            expected_clean_random = (
                graph_step.batch_size - graph_step.noisy_rows_per_batch
            ) // 2
            expected_noisy_random = graph_step.noisy_rows_per_batch // 2
            observed = (
                graph_step.last_random_initial_gaze_clean_count,
                graph_step.last_random_initial_gaze_noisy_count,
            )
            expected = (expected_clean_random, expected_noisy_random)
            if observed != expected:
                raise RuntimeError(
                    "Initialization-gaze quadrant counts drifted: "
                    f"clean/noisy={observed} expected={expected}"
                )
        if should_log:
            writer.add_scalar("loss/total", score, step)
            writer.add_scalar("loss/ae1", ae1_score, step)
            if float(ae4_loss_weight) > 0.0:
                writer.add_scalar("loss/ae4", ae4_loss, step)
                writer.add_scalar("metric/ae4_raw_objective", ae4_raw, step)
            writer.add_scalar(
                "loss/lowerarm_length", lowerarm_length_loss, step
            )
            writer.add_scalar(
                "metric/lowerarm_length_raw_mse",
                lowerarm_length_raw_mse,
                step,
            )
            writer.add_scalar("gradient_norm", gradient_norm, step)
            writer.add_scalar("Kmax", 32, step)
            writer.add_scalar(
                "conditioning/ae1_frame_weight_start", 0.0, step
            )
            writer.add_scalar(
                "conditioning/ae1_frame_weight_end",
                0.5 if graph_step.ae4_to_ae1_frame_blend else 1.0,
                step,
            )
            writer.add_scalar(
                "conditioning/ae4_frame_weight_start",
                1.0,
                step,
            )
            writer.add_scalar(
                "conditioning/ae4_frame_weight_end",
                0.5 if graph_step.ae4_to_ae1_frame_blend else 1.0,
                step,
            )
            writer.add_scalar("conditioning/gaze_zero_fraction", zero_fraction, step)
            writer.add_scalar(
                "conditioning/episode_start_noisy_fraction", noisy_fraction, step
            )
            writer.add_scalar(
                "conditioning/random_initial_gaze_fraction",
                random_initial_gaze_fraction,
                step,
            )
            writer.add_scalar("performance/steps_per_second", steps_per_second, step)
            writer.add_scalar("performance/ms_per_step", 1000.0 / steps_per_second, step)
            writer.flush()
            status = {
                "run_id": run_id,
                "step": step,
                "total_loss": score,
                "ae1": ae1_score,
                "ae4": ae4_loss,
                "ae4_raw_objective": ae4_raw,
                "ae4_loss_weight": float(ae4_loss_weight),
                "lowerarm_length": lowerarm_length_loss,
                "lowerarm_length_raw_mse": lowerarm_length_raw_mse,
                "lowerarm_length_weight": LOWERARM_LENGTH_WEIGHT,
                "best": best,
                "gradient_norm": gradient_norm,
                "Kmax": 32,
                "effective_k_counts": counts,
                "rollout_horizon": (
                    "fixed_all_rows_k32"
                    if graph_step.all_rows_k32
                    else "geometric_kmix32"
                ),
                "ae1_ae4_temporal_blend": ae1_ae4_temporal_blend_contract(
                    graph_step.ae4_to_ae1_frame_blend
                ),
                "motion_scope": args.motion_scope,
                "sampled_rows": graph_step.sampled_rows(),
                "gaze_zero_fraction": zero_fraction,
                "episode_start_noisy_fraction": noisy_fraction,
                "episode_start_noisy_rows": int(graph_step.last_noisy_count),
                "episode_start_clean_rows": int(
                    graph_step.batch_size - graph_step.last_noisy_count
                ),
                "episode_start_noise": graph_step.reset_noise_profile,
                "random_initial_gaze_fraction": random_initial_gaze_fraction,
                "random_initial_gaze_rows": int(
                    graph_step.last_random_initial_gaze_count
                ),
                "random_initial_gaze_clean_rows": int(
                    graph_step.last_random_initial_gaze_clean_count
                ),
                "random_initial_gaze_noisy_rows": int(
                    graph_step.last_random_initial_gaze_noisy_count
                ),
                "initialization_gaze": initialization_gaze_contract(
                    graph_step.random_initial_gaze_half_per_noise_class
                ),
                "gaze_sampling": "uniform_-1_1_with_5pct_exact_zero_constant_per_rollout",
                "learning_rate": float(args.learning_rate),
                "cuda_graph": True,
                "hot_loop": graph_step.kind,
                "direct_mse_enabled": False,
                "ae4_enabled": bool(float(ae4_loss_weight) > 0.0),
                "steps_per_second": steps_per_second,
                "elapsed_seconds": elapsed,
                "finite": True,
            }
            atomic_json(run_dir / "status.json", status)
            print(
                f"UPPER_PELVIS_AE1_FULL_GRAPH step={step} total={score:.8g} "
                f"ae1={ae1_score:.8g} ae4={ae4_loss:.8g} "
                f"lowerarm={lowerarm_length_loss:.8g} "
                f"grad={gradient_norm:.6g} gaze0={zero_fraction:.4f} "
                f"noisy={graph_step.last_noisy_count}/{graph_step.batch_size} "
                f"initgaze={graph_step.last_random_initial_gaze_count}/{graph_step.batch_size} "
                f"(clean={graph_step.last_random_initial_gaze_clean_count} "
                f"noisy={graph_step.last_random_initial_gaze_noisy_count}) "
                f"speed={steps_per_second:.3f}step/s elapsed_s={elapsed:.1f}",
                flush=True,
            )
        if should_checkpoint:
            save_cached_lower_checkpoint(
                checkpoints_dir / f"{run_id}_latest.pt",
                agent,
                optimizer,
                step,
                best,
                elapsed,
                32,
                metadata,
            )
            save_cached_lower_checkpoint(
                checkpoints_dir / f"checkpoint_step_{step:06d}.pt",
                agent,
                optimizer,
                step,
                best,
                elapsed,
                32,
                metadata,
            )
        if should_export:
            rollout_path = debug_dir / f"rollout_step_{step:06d}.json"
            export_full_corpus_graph_rollout(
                rollout_path, run_id, step, graph_step
            )
            atomic_copy(rollout_path, debug_dir / "last_batch_rollout.json")
        if bool(args.smoke):
            break
    writer.close()
    active_marker.unlink(missing_ok=True)
    print(f"UPPER_PELVIS_COMPLETE run={run_id}", flush=True)


def train(args: argparse.Namespace) -> None:
    if args.walk_pointer:
        walk_pointer = Path(args.walk_pointer).resolve()
        payload = json.loads(walk_pointer.read_text(encoding="utf-8"))
        expected_sha = str(payload.get("checkpoint_sha256", "")).upper()
        if len(expected_sha) != 64:
            raise RuntimeError(
                f"Walk override pointer has no full SHA-256: {walk_pointer}"
            )
        runtime_data.resolve_pointer(walk_pointer, expected_sha)
        runtime_data.WALK_POINTER = walk_pointer
        runtime_data.EXPECTED_WALK_SHA256 = expected_sha
    direct_mse = bool(args.direct_mse)
    ae1_only = bool(args.ae1_only)
    ae22_only = bool(args.ae22_only)
    ae4_loss_weight = float(args.ae4_loss_weight)
    if not math.isfinite(ae4_loss_weight) or ae4_loss_weight < 0.0:
        raise ValueError(f"--ae4-loss-weight must be finite and non-negative, got {ae4_loss_weight}")
    ae4_enabled = bool(ae4_loss_weight > 0.0)
    if sum((direct_mse, ae1_only, ae22_only)) > 1:
        raise ValueError("--direct-mse, --ae1-only and --ae22-only are mutually exclusive")
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    if device.type == "cuda":
        # Match the proven fast lower-controller path.  This permits TF32 on
        # supported NVIDIA GPUs while all stored states and losses remain FP32.
        torch.set_float32_matmul_precision("high")
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        torch.backends.cudnn.benchmark = True
    torch.manual_seed(int(args.seed))
    generator = torch.Generator(device="cpu").manual_seed(int(args.seed))

    walk_path, walk_pointer = runtime_data.resolve_pointer(
        runtime_data.WALK_POINTER, runtime_data.EXPECTED_WALK_SHA256
    )
    lower_paths = {runtime_data.CATEGORY_WALK: walk_path}
    lower_pointers = {runtime_data.CATEGORY_WALK: walk_pointer}
    if args.motion_scope in ("walk_run_omni", "full"):
        run_path, run_pointer = runtime_data.resolve_pointer(
            runtime_data.RUN_POINTER, runtime_data.EXPECTED_RUN_SHA256
        )
        lower_paths[runtime_data.CATEGORY_RUN] = run_path
        lower_pointers[runtime_data.CATEGORY_RUN] = run_pointer
    checkpoints = {
        category: torch.load(path, map_location="cpu", weights_only=False)
        for category, path in lower_paths.items()
    }
    configs = {
        category: runtime_data.apply_checkpoint_config(checkpoint, device)
        for category, checkpoint in checkpoints.items()
    }
    relative = (
        runtime_data.full_relative_datasets()
        if args.motion_scope == "full"
        else runtime_data.relative_datasets()
    )
    if args.motion_scope in ("walk_forward", "walk_forward_drawn"):
        relative = {
            runtime_data.CATEGORY_WALK: [
                "walk_omni/M_Neutral_Walk_Loop_F.npz"
            ]
        }
    modes = (
        (runtime_data.MODE_DRAWN,)
        if args.motion_scope == "walk_forward_drawn"
        else runtime_data.MODE_ORDER
    )
    categories = tuple(relative.keys())
    cached_full_corpus = bool(
        args.motion_scope == "full" and ae1_only and args.lower_cache
    )
    requested_episode_noise = episode_noise_profile(args)
    if requested_episode_noise["probability"] > 0.0 and not cached_full_corpus:
        raise ValueError(
            "Episode-start pose noise is supported only by the full cached-lower "
            "CUDA Graph controller path"
        )
    if bool(args.random_initial_gaze_half_per_noise_class):
        if not cached_full_corpus:
            raise ValueError(
                "Random initialization gaze is supported only by the full "
                "cached-lower CUDA Graph controller path"
            )
        if abs(requested_episode_noise["probability"] - 0.5) > 1.0e-8:
            raise ValueError(
                "Half-random initialization gaze within both pose-noise classes "
                "requires --episode-noise-probability 0.5"
            )
    if ae4_enabled and not (
        cached_full_corpus and bool(args.cuda_graph) and int(args.fixed_k or 0) == 32
    ):
        raise ValueError(
            "Weighted AE4 is supported only by the full cached-lower Kmix32 CUDA Graph path"
        )
    if bool(args.full_corpus_all_k32) and not (
        cached_full_corpus and bool(args.cuda_graph) and int(args.fixed_k or 0) == 32
    ):
        raise ValueError(
            "--full-corpus-all-k32 requires the full cached-lower K32 CUDA Graph path"
        )
    if bool(args.ae4_to_ae1_frame_blend) and not (
        bool(args.full_corpus_all_k32) and ae4_enabled
    ):
        raise ValueError(
            "--ae4-to-ae1-frame-blend requires --full-corpus-all-k32 and a positive AE4 loss"
        )
    if args.motion_scope == "full" and ae1_only and not args.lower_cache:
        raise ValueError(
            "Full-corpus AE1 training now requires --lower-cache; live frozen-lower "
            "inference and pelvis feedback are not part of the accepted contract"
        )
    frozen_models: dict[str, torch.nn.Module] = {}
    runtimes: dict[str, runtime_data.CategoryRuntime] = {}
    for category in categories:
        probe = tl.MotionClip(
            upper_data.ORIGINAL_ROOT / relative[category][0],
            configs[category],
            cyclic_animation=True,
        )
        model = visualize.load_model(
            checkpoints[category], probe, configs[category], device
        )
        model.eval().requires_grad_(False)
        frozen_models[category] = model
        runtimes[category] = runtime_data.build_category_runtime(
            category,
            relative[category],
            checkpoints[category],
            configs[category],
            model,
            device,
        )

    ae_path: Path | None = None
    ae_checkpoint: dict[str, Any] | None = None
    ae4_path: Path | None = None
    ae4_checkpoint: dict[str, Any] | None = None
    ae = mean = std = ae1_output_weights = None
    ae4 = ae4_input_mean = ae4_input_std = None
    ae4_target_mean = ae4_target_std = None
    if ae22_only:
        if not args.ae_checkpoint:
            raise ValueError("--ae22-only requires the audited --ae-checkpoint")
        ae_path = Path(args.ae_checkpoint).resolve()
        if not ae_path.is_file():
            raise FileNotFoundError(ae_path)
        ae, mean, std, ae_checkpoint = load_ae22(ae_path, device)
        ae1_output_weights = torch.ones(
            contract.PHYSICAL_DIM, dtype=torch.float32, device=device
        )
    elif not direct_mse:
        ae_path = resolve_ae_path(args.ae_checkpoint)
        if args.ae_checkpoint_sha256:
            actual_ae_sha256 = sha256_file(ae_path)
            expected_ae_sha256 = str(args.ae_checkpoint_sha256).upper()
            if actual_ae_sha256 != expected_ae_sha256:
                raise RuntimeError(
                    "Frozen AE1 SHA-256 mismatch: "
                    f"{actual_ae_sha256} != {expected_ae_sha256}: {ae_path}"
                )
        ae, mean, std, ae1_output_weights, ae_checkpoint = load_ae(ae_path, device)
        if ae4_enabled or not ae1_only:
            ae4_path = resolve_ae4_path(args.ae4_checkpoint)
            if args.ae4_checkpoint_sha256:
                actual_ae4_sha256 = sha256_file(ae4_path)
                expected_ae4_sha256 = str(args.ae4_checkpoint_sha256).upper()
                if actual_ae4_sha256 != expected_ae4_sha256:
                    raise RuntimeError(
                        "Frozen AE4 SHA-256 mismatch: "
                        f"{actual_ae4_sha256} != {expected_ae4_sha256}: {ae4_path}"
                    )
            (
                ae4,
                ae4_input_mean,
                ae4_input_std,
                ae4_target_mean,
                ae4_target_std,
                ae4_checkpoint,
            ) = ae4_data.load_checkpoint(ae4_path, device)
    lower_cache: dict[str, cached_lower_data.CachedLowerCategory] | None = None
    if cached_full_corpus:
        lower_cache = cached_lower_data.load_cache(
            Path(args.lower_cache).resolve(),
            runtimes,
            lower_paths,
            device,
            maximum_k=32,
        )
        # Preserve hand weighting from the accepted AE, but make pelvis and all
        # leg channels exact conditioning-only channels with no loss/gradient.
        assert ae1_output_weights is not None
        ae1_output_weights = ae1_output_weights * contract.physical_scoring_mask(
            device=device, dtype=ae1_output_weights.dtype
        )
        if ae4_enabled:
            assert lower_cache is not None
            prepare_cached_lower_ae4_tables(runtimes, lower_cache)
        for runtime in runtimes.values():
            runtime.model.to(torch.device("cpu"))
        for model in frozen_models.values():
            model.to(torch.device("cpu"))
        if device.type == "cuda":
            torch.cuda.empty_cache()
    agent: UpperPelvisAgent | UpperCachedLowerAgent
    agent = (
        UpperCachedLowerAgent().to(device)
        if cached_full_corpus
        else UpperPelvisAgent().to(device)
    )
    if (
        device.type == "cuda"
        and bool(args.cuda_graph)
        and bool(ae1_only)
        and int(args.batch_size) in (8, 32, 64)
        and int(args.fixed_k or 0) == 32
    ):
        # The fused AdamW kernel crashes on its second replay when fed gradients
        # accumulated by the watchdog-safe BS1 graph.  Foreach AdamW is the same
        # optimizer and remains fully capturable, but uses the stable kernel path.
        optimizer = torch.optim.AdamW(
            agent.parameters(),
            lr=float(args.learning_rate),
            weight_decay=0.0,
            foreach=True,
            fused=False,
            capturable=True,
        )
    else:
        optimizer = lower_ctl.make_adamw(
            agent.parameters(),
            float(args.learning_rate),
            device,
            capturable=bool(device.type == "cuda" and args.cuda_graph),
        )
    resume_payload: dict[str, Any] | None = None
    if args.resume_checkpoint:
        resume_path = Path(args.resume_checkpoint).resolve()
        if args.resume_checkpoint_sha256:
            actual_resume_sha256 = sha256_file(resume_path)
            expected_resume_sha256 = str(args.resume_checkpoint_sha256).upper()
            if actual_resume_sha256 != expected_resume_sha256:
                raise RuntimeError(
                    "Controller resume SHA-256 mismatch: "
                    f"{actual_resume_sha256} != {expected_resume_sha256}: {resume_path}"
                )
        resume_payload = torch.load(
            resume_path, map_location="cpu", weights_only=False
        )
        expected_kind = (
            CACHED_LOWER_CONTROLLER_KIND if cached_full_corpus else CONTROLLER_KIND
        )
        if resume_payload.get("kind") != expected_kind:
            raise RuntimeError(
                f"Cannot resume controller kind {resume_payload.get('kind')!r}; "
                f"expected {expected_kind!r}: {resume_path}"
            )
        expected_schema = (
            cached_lower_checkpoint_schema()
            if cached_full_corpus
            else checkpoint_schema()
        )
        if resume_payload.get("schema") != expected_schema:
            raise RuntimeError(
                "Controller resume schema differs from the current agent contract: "
                f"{resume_path}"
            )
        resume_metadata = dict(resume_payload.get("metadata", {}))
        if cached_full_corpus:
            immutable_resume_contract = {
                "motion_scope": "full",
                "modes": [-1.0, 1.0],
                "batch_size": int(args.batch_size),
                "gradient_accumulation_steps": 1,
                "learning_rate": float(args.learning_rate),
                "lower_cache_sha256": cached_lower_data.sha256_file(
                    Path(args.lower_cache).resolve()
                ),
                "rollout_gradient_window": int(args.rollout_gradient_window),
                "cuda_graph": True,
            }
            prior_noise = resume_metadata.get("episode_start_noise")
            mismatches = {
                key: {"checkpoint": resume_metadata.get(key), "requested": value}
                for key, value in immutable_resume_contract.items()
                if resume_metadata.get(key) != value
            }
            if isinstance(prior_noise, dict):
                requested_noise = episode_noise_profile(args)
                noise_mismatches = {
                    key: {"checkpoint": prior_noise.get(key), "requested": value}
                    for key, value in requested_noise.items()
                    if prior_noise.get(key) != value
                }
                if noise_mismatches:
                    mismatches["episode_start_noise"] = noise_mismatches
            prior_objective = str(resume_metadata.get("objective", ""))
            accepted_prior_objectives = (
                {"ae1_only", "ae1_plus_weighted_ae4"}
                if ae4_enabled
                else {"ae1_only"}
            )
            if prior_objective not in accepted_prior_objectives:
                mismatches["objective"] = {
                    "checkpoint": prior_objective,
                    "requested": sorted(accepted_prior_objectives),
                }
            if mismatches:
                raise RuntimeError(
                    "Controller resume contract mismatch: "
                    + json.dumps(mismatches, sort_keys=True)
                )
            prior_lowerarm_weight = resume_metadata.get("lowerarm_length_weight")
            if (
                prior_lowerarm_weight is not None
                and float(prior_lowerarm_weight) != LOWERARM_LENGTH_WEIGHT
            ):
                raise RuntimeError(
                    "Controller resume lower-arm loss weight differs from the "
                    f"current contract: {prior_lowerarm_weight} != "
                    f"{LOWERARM_LENGTH_WEIGHT}"
                )
            assert ae_checkpoint is not None and ae_path is not None
            prior_ae_path = Path(str(resume_metadata.get("ae1_checkpoint", "")))
            if not prior_ae_path.is_file():
                official_prior_ae_path = resolve_ae_path(None)
                if (
                    official_prior_ae_path.is_file()
                    and sha256_file(official_prior_ae_path)
                    == str(resume_metadata.get("ae1_sha256", "")).upper()
                ):
                    prior_ae_path = official_prior_ae_path
            if prior_ae_path.is_file():
                prior_ae = torch.load(
                    prior_ae_path, map_location="cpu", weights_only=False
                )
                incompatible = []
                if prior_ae.get("kind") != ae_checkpoint.get("kind"):
                    incompatible.append("kind")
                if prior_ae.get("schema") != ae_checkpoint.get("schema"):
                    incompatible.append("schema")
                for name in ("mean", "std"):
                    if not torch.equal(prior_ae[name], ae_checkpoint[name]):
                        incompatible.append(name)
                prior_state = prior_ae["model"]
                replacement_state = ae_checkpoint["model"]
                if prior_state.keys() != replacement_state.keys() or any(
                    prior_state[key].shape != replacement_state[key].shape
                    for key in prior_state.keys() & replacement_state.keys()
                ):
                    incompatible.append("model_parameter_shapes")
                if incompatible:
                    raise RuntimeError(
                        "Replacement AE1 changes the frozen-AE contract: "
                        + ", ".join(incompatible)
                    )
            elif resume_metadata.get("ae1_sha256") != sha256_file(ae_path):
                raise RuntimeError(
                    "Cannot verify replacement AE1 compatibility because the prior "
                    f"AE checkpoint is unavailable: {prior_ae_path}"
                )
            prior_ae4_sha = str(resume_metadata.get("ae4_sha256", "")).upper()
            if ae4_enabled and prior_ae4_sha and ae4_path is not None:
                if prior_ae4_sha != sha256_file(ae4_path):
                    raise RuntimeError(
                        "Cannot resume with a different frozen AE4: "
                        f"{prior_ae4_sha} != {sha256_file(ae4_path)}"
                    )
        agent.load_state_dict(resume_payload["model"], strict=True)
        optimizer.load_state_dict(resume_payload["optimizer"])
        for parameter_group in optimizer.param_groups:
            parameter_group["lr"] = float(args.learning_rate)

    groups = [(category, mode) for category in categories for mode in modes]
    if int(args.batch_size) % len(groups) != 0:
        raise ValueError(
            f"Batch {args.batch_size} must divide equally across {len(groups)} groups"
        )
    rows_per_group = int(args.batch_size) // len(groups)
    if args.resume_run_dir:
        run_dir = Path(args.resume_run_dir).resolve()
        if run_dir.parent != RUNS_ROOT.resolve():
            raise ValueError(f"Resume run must be directly under {RUNS_ROOT}: {run_dir}")
        run_id = run_dir.name
    else:
        suffix = (
            "_ik_upper_pelvis_direct_mse_gaze00"
            if direct_mse
            else (
                "_ik_upper_pelvis_ae22_only_gaze00"
                if ae22_only
                else (
                    f"_ik_upper_cached_lower_ae1_full_gaze_bs{int(args.batch_size)}_"
                    + ("allk32" if bool(args.full_corpus_all_k32) else "kmix32")
                    + ("_ae4q25" if ae4_enabled else "")
                    + (
                        "_ae4blend0to50"
                        if bool(args.ae4_to_ae1_frame_blend)
                        else ""
                    )
                    + (
                        f"_noise{int(round(float(args.episode_noise_probability) * 100.0)):02d}"
                        if float(args.episode_noise_probability) > 0.0
                        else ""
                    )
                    + (
                        "_initgaze50each_ae4rot5dz5"
                        if bool(args.random_initial_gaze_half_per_noise_class)
                        else ""
                    )
                    + (
                        ""
                        if int(args.rollout_gradient_window) == 0
                        else f"_tbptt{int(args.rollout_gradient_window)}"
                    )
                )
                if ae1_only and args.motion_scope == "full"
                else "_ik_upper_pelvis_ae1_only_gaze00"
                if ae1_only
                else "_ik_upper_pelvis_ae1_ae4x10"
            )
        )
        if ae1_only and args.motion_scope == "full" and bool(args.full_corpus_all_k32):
            suffix = (
                f"_ik_upper_cached_ae1{'ae4' if ae4_enabled else ''}_"
                f"bs{int(args.batch_size)}_allk32"
                + ("_blend" if bool(args.ae4_to_ae1_frame_blend) else "")
                + (
                    f"_noise{int(round(float(args.episode_noise_probability) * 100.0)):02d}"
                    if float(args.episode_noise_probability) > 0.0
                    else ""
                )
                + (
                    "_initgaze50each"
                    if bool(args.random_initial_gaze_half_per_noise_class)
                    else ""
                )
                + (
                    ""
                    if int(args.rollout_gradient_window) == 0
                    else f"_tbptt{int(args.rollout_gradient_window)}"
                )
            )
        run_id = time.strftime("%Y%m%d_%H%M%S") + suffix
        run_dir = RUNS_ROOT / run_id
    if args.resume_run_dir and resume_payload is None:
        raise ValueError("resume run directory requires a resume checkpoint")
    checkpoints_dir = run_dir / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    debug_dir = run_dir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    active_marker = debug_dir / "training.active.json"
    atomic_json(
        active_marker,
        {"pid": os.getpid(), "run_id": run_id, "trainer": str(Path(__file__).resolve())},
    )
    if args.current_run_file:
        current_run_file = Path(args.current_run_file).resolve()
        current_run_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = current_run_file.with_suffix(current_run_file.suffix + ".tmp")
        temporary.write_text(str(run_dir.resolve()) + "\n", encoding="utf-8")
        os.replace(temporary, current_run_file)
    writer = SummaryWriter(log_dir=str(run_dir / "tb"), flush_secs=1)
    metadata: dict[str, Any] = {
        "run_id": run_id,
        "trainer": str(Path(__file__).resolve()),
        "schema": (
            cached_lower_checkpoint_schema()
            if cached_full_corpus
            else checkpoint_schema()
        ),
        "objective": (
            "direct_upper_plus_pelvis_mse"
            if direct_mse
            else (
                "ae22_only"
                if ae22_only
                else "ae1_plus_weighted_ae4"
                if ae1_only and ae4_enabled
                else "ae1_only"
                if ae1_only
                else "ae1_plus_10x_ae4"
            )
        ),
        "lower_checkpoints": {key: str(value) for key, value in lower_paths.items()},
        "lower_selection": lower_pointers,
        "motion_scope": args.motion_scope,
        "modes": [float(mode) for mode in modes],
        "batch_size": int(args.batch_size),
        "gradient_accumulation_steps": int(args.gradient_accumulation_steps),
        "learning_rate": float(args.learning_rate),
        "loss": (
            "raw_MSE_on_authored_next_upper90_plus_pelvis9"
            if direct_mse
            else (
                "AE22_condition_only_171D_teacher_MSE_only"
                if ae22_only
                else (
                    "AE1_newest_171D_reconstruction_MSE_plus_symmetric_"
                    "lowerarm_length_MSE"
                    + ("_plus_weighted_AE4_absolute_pose_MSE" if ae4_enabled else "")
                    if cached_full_corpus
                    else "AE1_newest_171D_reconstruction_MSE_only"
                )
                if ae1_only
                else "AE1_newest_171D_reconstruction_MSE_plus_10x_AE4_absolute_upper_pose_MSE"
            )
        ),
        "gaze": (
            "uniform_normalized_-1_to_1_with_5pct_exact_0_0_constant_per_rollout"
            if ae1_only and args.motion_scope == "full"
            else "fixed_normalized_0_0"
            if direct_mse or ae1_only or ae22_only
            else "sampled_per_rollout"
        ),
        "initialization_gaze": initialization_gaze_contract(
            bool(args.random_initial_gaze_half_per_noise_class)
        ),
        "pelvis_output": (
            "removed; pelvis is immutable cached-lower conditioning"
            if cached_full_corpus
            else "live frozen-lower proposal plus learned delta"
        ),
        "lower_autoregressive_feedback": (
            "none; one continuous frozen-lower trajectory was generated offline"
            if cached_full_corpus
            else (
                "controlled pelvis plus direct-IK thigh/calf payload is written into "
                "the lower state consumed by the next frozen-NN inference"
            )
        ),
        "lower_weights_frozen": True,
        "lower_input_gradient": (
            "none; cached lower trajectory is immutable"
            if cached_full_corpus
            else "preserved through live frozen-NN inference for autoregressive credit assignment"
        ),
        "lower_motion_precomputed": bool(cached_full_corpus),
        "lower_cache": (
            str(Path(args.lower_cache).resolve()) if cached_full_corpus else None
        ),
        "lower_cache_sha256": (
            cached_lower_data.sha256_file(Path(args.lower_cache).resolve())
            if cached_full_corpus
            else None
        ),
        "ae1_scored_bones": (
            list(contract.SCORED_UPPER_PHYSICAL_BONES)
            if cached_full_corpus
            else list(contract.PHYSICAL_BONES)
        ),
        "ae1_conditioning_only_bones": (
            list(contract.CACHED_LOWER_PHYSICAL_BONES)
            if cached_full_corpus
            else []
        ),
        "detach_rollout_gradient": bool(args.detach_rollout_gradient),
        "rollout_gradient_window": int(args.rollout_gradient_window),
        "rollout_gradient_mode": (
            "full"
            if int(args.rollout_gradient_window) == 0
            else f"truncated_{int(args.rollout_gradient_window)}_frames"
        ),
        "cuda_graph": bool(args.cuda_graph),
        "cuda_graph_hot_loop": (
            (
                "four_single_use_cuda_cohort_graphs_K32_16_8_1_plus_foreach_AdamW"
                if bool(args.ae1_only)
                and int(args.batch_size) == 8
                and int(args.fixed_k or 0) == 32
                else f"upper_only_cached_lower_reusable_exact_horizon_cohort_graphs_shared_pool_plus_one_BS{int(args.batch_size)}_AdamW_update"
                if bool(args.ae1_only)
                and args.motion_scope == "full"
                and int(args.batch_size) in (32, 64)
                and int(args.fixed_k or 0) == 32
                else "full_fixed_K_rollout_plus_backward_plus_fused_AdamW"
            )
            if bool(args.cuda_graph)
            else "disabled"
        ),
        "tensorboard_url": "http://127.0.0.1:6006/#timeseries",
        "direct_mse_enabled": bool(direct_mse),
        "ae1_enabled": bool(not direct_mse and not ae22_only),
        "ae22_enabled": bool(ae22_only),
        "ae4_enabled": bool(ae4_enabled or (not direct_mse and not ae1_only and not ae22_only)),
    }
    if cached_full_corpus:
        noise_profile = episode_noise_profile(args)
        metadata.update(
            {
                "lowerarm_length_weight": LOWERARM_LENGTH_WEIGHT,
                "lowerarm_length_contract": (
                    "mean squared signed wrist-to-elbow length error over both "
                    "implicit lower arms; symmetric for stretching and squeezing; "
                    "fixed target is each clip runtime IK lower-arm length"
                ),
                "lowerarm_length_calibration": {
                    "source_run": (
                        "20260815_052900_ik_upper_cached_lower_ae1_full_gaze_"
                        "bs64_kmix32"
                    ),
                    "source_step": 21750,
                    "source_rollout": "debug/rollout_step_021750.json",
                    "raw_mse": 0.004669475199618261,
                    "target_weighted_loss": 0.075,
                    "coefficient": LOWERARM_LENGTH_WEIGHT,
                },
                "episode_start_noise": {
                    **noise_profile,
                    "sampling": "independent_uniform_magnitude_0_to_max_uniform_sphere_direction",
                    "lifetime": "current_pose_at_episode_reset_only",
                    "affected_pose": (
                        "local FK rotations on core and upperarms; direct hand "
                        "root-relative translation and rotation; cached frozen-lower "
                        "pelvis, thighs, calves, and feet remain untouched"
                    ),
                    "exact_noisy_rows": int(
                        round(noise_profile["probability"] * int(args.batch_size))
                    ),
                    "exact_clean_rows": int(args.batch_size)
                    - int(
                        round(noise_profile["probability"] * int(args.batch_size))
                    ),
                },
                "rollout_horizon": {
                    "mode": (
                        "fixed_all_rows_k32"
                        if bool(args.full_corpus_all_k32)
                        else "geometric_kmix32"
                    ),
                    "K": 32,
                    "rows": int(args.batch_size),
                },
                "ae1_ae4_temporal_blend": ae1_ae4_temporal_blend_contract(
                    bool(args.ae4_to_ae1_frame_blend)
                ),
            }
        )
        if ae4_enabled:
            assert ae4_path is not None and ae4_checkpoint is not None
            metadata.update(
                {
                    "ae4_checkpoint": str(ae4_path),
                    "ae4_sha256": sha256_file(ae4_path),
                    "ae4_step": int(ae4_checkpoint.get("step", -1)),
                    "ae4_loss_weight": ae4_loss_weight,
                    "ae4_loss_contract": (
                        "normalized absolute position and full-hand transform MSE against "
                        "frozen condition-only AE4; non-hand rotation uses dead-zoned "
                        "root-local geodesic angular error"
                    ),
                    "ae4_rotation_loss": ae4_rotation_loss_contract(),
                }
            )
    if resume_payload is not None:
        metadata.update(
            {
                "resumed_from_checkpoint": str(Path(args.resume_checkpoint).resolve()),
                "resumed_from_checkpoint_sha256": sha256_file(
                    Path(args.resume_checkpoint).resolve()
                ),
                "resumed_from_step": int(resume_payload.get("step", 0)),
                "resume_mode": (
                    "same_run" if args.resume_run_dir else "new_run_new_tensorboard_curve"
                ),
            }
        )
        prior_ae_sha256 = str(
            dict(resume_payload.get("metadata", {})).get("ae1_sha256", "")
        ).upper()
        if (
            cached_full_corpus
            and dict(resume_payload.get("metadata", {})).get(
                "lowerarm_length_weight"
            )
            is None
        ):
            metadata["best_metric_reset_on_resume"] = (
                "prior checkpoint predates lowerarm length loss"
            )
        if (
            not direct_mse
            and not ae22_only
            and ae_path is not None
            and prior_ae_sha256
            and prior_ae_sha256 != sha256_file(ae_path)
        ):
            prior_metadata = dict(resume_payload.get("metadata", {}))
            metadata["frozen_ae1_replacement"] = {
                "prior_checkpoint": prior_metadata.get("ae1_checkpoint"),
                "prior_sha256": prior_ae_sha256,
                "prior_step": prior_metadata.get("ae1_step"),
                "replacement_checkpoint": str(ae_path),
                "replacement_sha256": sha256_file(ae_path),
                "replacement_step": int(ae_checkpoint.get("step", -1)),
                "agent_model_optimizer_resumed_unchanged": True,
            }
    if not direct_mse:
        assert ae_path is not None and ae_checkpoint is not None
        metadata.update(
            {
                f"{'ae22' if ae22_only else 'ae1'}_checkpoint": str(ae_path),
                f"{'ae22' if ae22_only else 'ae1'}_sha256": sha256_file(ae_path),
                f"{'ae22' if ae22_only else 'ae1'}_step": int(ae_checkpoint.get("step", -1)),
                "ae1_physical_scoring_weights": (
                    dict(ae_checkpoint.get("schema", {})).get("scoring_weights", {})
                    if not ae22_only
                    else {"default_transform_weight": 1.0}
                ),
            }
        )
        if not ae1_only and not ae22_only:
            assert ae4_path is not None and ae4_checkpoint is not None
            metadata.update(
                {
                    "ae4_checkpoint": str(ae4_path),
                    "ae4_sha256": sha256_file(ae4_path),
                    "ae4_step": int(ae4_checkpoint.get("step", -1)),
                    "ae4_loss_weight": AE4_LOSS_WEIGHT,
                }
            )
    atomic_json(run_dir / "config.json", metadata)
    if resume_payload is None:
        if cached_full_corpus:
            assert isinstance(agent, UpperCachedLowerAgent)
            save_cached_lower_checkpoint(
                checkpoints_dir / f"{run_id}_init.pt",
                agent,
                optimizer,
                0,
                float("inf"),
                0.0,
                int(args.fixed_k or 2),
                metadata,
            )
        else:
            assert isinstance(agent, UpperPelvisAgent)
            save_checkpoint(
                checkpoints_dir / f"{run_id}_init.pt",
                agent,
                optimizer,
                0,
                float("inf"),
                0.0,
                int(args.fixed_k or 2),
                metadata,
            )
        best = float("inf")
        initial_elapsed = 0.0
        step = 0
    else:
        best = float(resume_payload.get("best", float("inf")))
        prior_loss_metadata = dict(resume_payload.get("metadata", {}))
        if (
            cached_full_corpus
            and prior_loss_metadata.get("lowerarm_length_weight")
            != LOWERARM_LENGTH_WEIGHT
        ):
            # The historical best is an AE1-only number and cannot be compared
            # with the new combined objective.  Model, optimizer and RNG state
            # still resume exactly; only best-checkpoint bookkeeping restarts.
            best = float("inf")
            metadata["best_metric_reset_on_resume"] = (
                "prior checkpoint predates lowerarm length loss"
            )
        if cached_full_corpus and ae4_enabled and (
            prior_loss_metadata.get("ae4_sha256") != sha256_file(ae4_path)
            or float(prior_loss_metadata.get("ae4_loss_weight", -1.0))
            != ae4_loss_weight
            or prior_loss_metadata.get("ae4_rotation_loss")
            != ae4_rotation_loss_contract()
        ):
            best = float("inf")
            metadata["best_metric_reset_on_resume"] = (
                "weighted AE4 objective was added, recalibrated, or changed"
            )
        if cached_full_corpus and (
            prior_loss_metadata.get("rollout_horizon")
            != metadata.get("rollout_horizon")
            or prior_loss_metadata.get("ae1_ae4_temporal_blend")
            != metadata.get("ae1_ae4_temporal_blend")
        ):
            best = float("inf")
            metadata["best_metric_reset_on_resume"] = (
                "rollout horizon or AE1/AE4 temporal blend changed"
            )
        if (
            cached_full_corpus
            and prior_loss_metadata.get("initialization_gaze")
            != initialization_gaze_contract(
                bool(args.random_initial_gaze_half_per_noise_class)
            )
        ):
            best = float("inf")
            metadata["best_metric_reset_on_resume"] = (
                "episode initialization-gaze distribution changed"
            )
        initial_elapsed = float(resume_payload.get("elapsed_seconds", 0.0))
        step = int(resume_payload.get("step", 0))
        if not args.resume_run_dir:
            if cached_full_corpus:
                assert isinstance(agent, UpperCachedLowerAgent)
                save_cached_lower_checkpoint(
                    checkpoints_dir / f"{run_id}_init.pt",
                    agent,
                    optimizer,
                    step,
                    best,
                    initial_elapsed,
                    int(args.fixed_k or 2),
                    metadata,
                )
            else:
                assert isinstance(agent, UpperPelvisAgent)
                save_checkpoint(
                    checkpoints_dir / f"{run_id}_init.pt",
                    agent,
                    optimizer,
                    step,
                    best,
                    initial_elapsed,
                    int(args.fixed_k or 2),
                    metadata,
                )
    # Resume-time objective/distribution checks may add provenance after the
    # initial config write. Publish that final metadata too so config.json and
    # the init checkpoint agree exactly.
    atomic_json(run_dir / "config.json", metadata)
    started = time.perf_counter() - initial_elapsed
    if bool(args.cuda_graph):
        if device.type != "cuda":
            raise ValueError("--cuda-graph requires --device cuda")
        full_corpus_graph = (
            args.motion_scope == "full"
            and bool(ae1_only)
            and int(args.batch_size) in (32, 64)
            and int(args.fixed_k or 0) == 32
            and groups == list(FullCorpusAe1CudaGraphStep.GROUPS)
        )
        if full_corpus_graph:
            assert ae is not None and mean is not None and std is not None
            assert ae1_output_weights is not None
            assert lower_cache is not None
            assert isinstance(agent, UpperCachedLowerAgent)
            train_full_corpus_ae1_cuda_graph(
                args,
                runtimes,
                lower_cache,
                agent,
                optimizer,
                ae,
                mean,
                std,
                ae1_output_weights,
                ae4,
                ae4_input_mean,
                ae4_input_std,
                ae4_target_mean,
                ae4_target_std,
                ae4_loss_weight,
                run_id,
                run_dir,
                checkpoints_dir,
                debug_dir,
                metadata,
                writer,
                active_marker,
                started,
                step,
                best,
            )
        elif len(groups) != 1 or groups[0] != (
            runtime_data.CATEGORY_WALK,
            runtime_data.MODE_DRAWN,
        ):
            raise ValueError(
                "CUDA Graph path requires either the exact full BS32/BS64 recipe or "
                "walk_forward_drawn only"
            )
        elif direct_mse:
            train_direct_mse_cuda_graph(
                args,
                runtimes[runtime_data.CATEGORY_WALK],
                runtime_data.MODE_DRAWN,
                agent,
                optimizer,
                run_id,
                run_dir,
                checkpoints_dir,
                debug_dir,
                metadata,
                writer,
                active_marker,
                started,
            )
        elif ae1_only or ae22_only:
            assert ae is not None and mean is not None and std is not None
            assert ae1_output_weights is not None
            train_ae1_cuda_graph(
                args,
                runtimes[runtime_data.CATEGORY_WALK],
                runtime_data.MODE_DRAWN,
                agent,
                optimizer,
                ae,
                mean,
                std,
                ae1_output_weights,
                run_id,
                run_dir,
                checkpoints_dir,
                debug_dir,
                metadata,
                writer,
                active_marker,
                started,
                "ae22" if ae22_only else "ae1",
            )
        else:
            raise ValueError("--cuda-graph requires --direct-mse, --ae1-only or --ae22-only")
        return
    while int(args.train_steps) <= 0 or step < int(args.train_steps):
        if stop_requested(args):
            break
        step += 1
        optimizer.zero_grad(set_to_none=True)
        accumulated_metrics = {category: 0.0 for category in categories}
        accumulated_total = 0.0
        accumulated_ae1 = 0.0
        accumulated_ae4 = 0.0
        accumulated_gt_mse = 0.0
        captured_rollout: tuple[
            list[dict[str, Any]],
            torch.Tensor,
            torch.Tensor,
            torch.Tensor,
            torch.Tensor,
            torch.Tensor,
        ] | None = None
        for _accumulation in range(int(args.gradient_accumulation_steps)):
            elapsed = time.perf_counter() - started
            if args.fixed_k is not None:
                maximum_k = int(args.fixed_k)
            else:
                stage = min(
                    len(ROLLOUT_SCHEDULE) - 1,
                    int(elapsed // ROLLOUT_STAGE_SECONDS),
                )
                maximum_k = int(ROLLOUT_SCHEDULE[stage])
            effective_k = runtime_data.sample_effective_rollout_k(
                int(args.batch_size), maximum_k, device
            )
            gaze = (
                torch.zeros(
                    (int(args.batch_size), 2),
                    dtype=torch.float32,
                    device=device,
                )
                if direct_mse
                else runtime_data.sample_gaze(
                    int(args.batch_size), generator, device
                )
            )
            lower_states: dict[tuple[str, float], dict[str, torch.Tensor]] = {}
            upper_states: dict[tuple[str, float], dict[str, torch.Tensor]] = {}
            cursor = 0
            for key in groups:
                category, mode = key
                runtime = runtimes[category]
                clip_ids, starts = runtime_data.sample_runtime_rows(
                    runtime, rows_per_group, maximum_k, generator, device
                )
                state = runtime_data.lower_initial_state(runtime, starts, clip_ids)
                lower_states[key] = state
                upper_states[key] = context_state(
                    runtime,
                    mode,
                    state,
                    gaze[cursor : cursor + rows_per_group],
                    device,
                )
                cursor += rows_per_group

            rollout_losses: list[torch.Tensor] = []
            rollout_ae1_losses: list[torch.Tensor] = []
            rollout_ae4_losses: list[torch.Tensor] = []
            rollout_gt_mse: list[torch.Tensor] = []
            category_sums = {category: agent.delta_head.weight.new_zeros(()) for category in categories}
            cursor_base = {key: i * rows_per_group for i, key in enumerate(groups)}
            capture_rollout = (
                _accumulation == int(args.gradient_accumulation_steps) - 1
            )
            debug_rows: list[dict[str, Any]] = []
            debug_positions_frames: list[torch.Tensor] = []
            debug_rotations_frames: list[torch.Tensor] = []
            debug_root_position_frames: list[torch.Tensor] = []
            debug_root_rotation_frames: list[torch.Tensor] = []
            debug_source_frames: list[torch.Tensor] = []
            if capture_rollout:
                for key in groups:
                    category, mode = key
                    runtime = runtimes[category]
                    state = lower_states[key]
                    offset = cursor_base[key]
                    selected_gaze = gaze[offset : offset + rows_per_group]
                    for local_row in range(rows_per_group):
                        clip_id = int(state["clip_ids"][local_row].detach().cpu())
                        relative = runtime.relatives[clip_id]
                        debug_rows.append(
                            {
                                "row": len(debug_rows),
                                "clip_id": clip_id,
                                "clip_name": Path(relative).stem,
                                "clip_path": str(
                                    (upper_data.SWORD_ROOT if mode == runtime_data.MODE_DRAWN else upper_data.ORIGINAL_ROOT)
                                    / relative
                                ),
                                "start": int(state["cur_idx"][local_row].detach().cpu()),
                                "effective_k": int(
                                    effective_k[offset + local_row].detach().cpu()
                                ),
                                "virtual": False,
                                "noisy": False,
                                "noisy_seed_source": "exact_training_row",
                                "has_sword": bool(mode == runtime_data.MODE_DRAWN),
                                "locomotion_category": category,
                                "gaze_normalized": [
                                    float(value)
                                    for value in selected_gaze[local_row].detach().cpu().tolist()
                                ],
                            }
                        )
            for rollout_step in range(maximum_k):
                row_losses: list[torch.Tensor] = []
                row_ae1_losses: list[torch.Tensor] = []
                row_ae4_losses: list[torch.Tensor] = []
                row_gt_mses: list[torch.Tensor] = []
                step_current_positions: dict[tuple[str, float], torch.Tensor] = {}
                step_current_rotations: dict[tuple[str, float], torch.Tensor] = {}
                step_next_positions: dict[tuple[str, float], torch.Tensor] = {}
                step_next_rotations: dict[tuple[str, float], torch.Tensor] = {}
                step_current_root_positions: dict[tuple[str, float], torch.Tensor] = {}
                step_current_root_rotations: dict[tuple[str, float], torch.Tensor] = {}
                step_next_root_positions: dict[tuple[str, float], torch.Tensor] = {}
                step_next_root_rotations: dict[tuple[str, float], torch.Tensor] = {}
                step_current_sources: dict[tuple[str, float], torch.Tensor] = {}
                step_next_sources: dict[tuple[str, float], torch.Tensor] = {}
                for key in groups:
                    category, mode = key
                    runtime = runtimes[category]
                    lower_state = lower_states[key]
                    upper_state = upper_states[key]
                    clip_ids = lower_state["clip_ids"]
                    next_lower = lower_next_live(runtime, lower_state)
                    next_indices = lower_state["cur_idx"] + 1
                    current_root = runtime_data.root_state(
                        runtime, lower_state["cur_idx"], clip_ids
                    )
                    previous_root = runtime_data.root_state(
                        runtime, lower_state["cur_idx"] - 1, clip_ids
                    )
                    next_root = runtime_data.root_state(runtime, next_indices, clip_ids)
                    frozen_next_pelvis = pelvis_heading(
                        next_lower, next_root[1], next_root[2]
                    )
                    pelvis_prior = contract.pelvis_proposal(frozen_next_pelvis)
                    rest = runtime.rest_offsets_by_mode[mode].index_select(0, clip_ids)
                    frozen_next_base = runtime_data.base_upper_from_lower(
                        next_lower, *next_root, runtime.full_by_mode[mode], rest
                    )
                    upper_prior = upper_data.clean_upper_state(
                        frozen_next_base
                        + upper_state["current_upper"]
                        - upper_state["current_base"]
                    )
                    roots = runtime.store.get_input_root_features(
                        clip_ids, lower_state["cur_idx"]
                    )
                    feet_current = runtime_data.foot_heading_features(
                        runtime.store,
                        lower_state["cur"],
                        current_root[1],
                        current_root[2],
                    )
                    feet_next = runtime_data.foot_heading_features(
                        runtime.store, next_lower, next_root[1], next_root[2]
                    )
                    offset = cursor_base[key]
                    selected_gaze = gaze[offset : offset + rows_per_group]
                    controller_input = torch.cat(
                        (
                            upper_state["previous_upper"],
                            upper_prior,
                            upper_state["previous_pelvis"],
                            upper_state["current_pelvis"],
                            pelvis_prior,
                            roots,
                            torch.full(
                                (rows_per_group, 1),
                                float(mode),
                                dtype=torch.float32,
                                device=device,
                            ),
                            feet_current,
                            feet_next,
                            selected_gaze,
                        ),
                        dim=-1,
                    )
                    raw = agent(controller_input)
                    next_upper, next_pelvis, _applied = contract.apply_agent_output(
                        upper_prior, pelvis_prior, raw
                    )
                    transition, _current_globals, _next_globals = physical_delta(
                        runtime,
                        mode,
                        lower_state["cur"],
                        next_lower,
                        upper_state["current_upper"],
                        next_upper,
                        upper_state["current_pelvis"],
                        next_pelvis,
                        current_root,
                        next_root,
                        clip_ids,
                    )
                    if capture_rollout:
                        step_current_positions[key] = _current_globals[0].detach()
                        step_current_rotations[key] = _current_globals[1].detach()
                        step_next_positions[key] = _next_globals[0].detach()
                        step_next_rotations[key] = _next_globals[1].detach()
                        step_current_root_positions[key] = current_root[0].detach()
                        step_current_root_rotations[key] = current_root[1].detach()
                        step_next_root_positions[key] = next_root[0].detach()
                        step_next_root_rotations[key] = next_root[1].detach()
                        step_current_sources[key] = lower_state["cur_idx"].detach()
                        step_next_sources[key] = next_indices.detach()
                    target_transition = authored_transition_delta_rows(
                        runtime,
                        mode,
                        clip_ids,
                        lower_state["cur_idx"],
                        selected_gaze,
                        device,
                    )
                    row_gt_mses.append(
                        (transition.detach() - target_transition).square().mean(dim=-1)
                    )
                    if bool(torch.any(clip_ids != clip_ids[0])):
                        feedback = torch.empty_like(next_lower)
                        for clip_id in torch.unique(clip_ids, sorted=True).tolist():
                            feedback_selection = torch.nonzero(
                                clip_ids == int(clip_id), as_tuple=False
                            ).flatten()
                            feedback = feedback.index_copy(
                                0,
                                feedback_selection,
                                contract.feedback_lower_state(
                                    runtime.lower_clips[int(clip_id)],
                                    next_lower.index_select(0, feedback_selection),
                                    next_pelvis.index_select(0, feedback_selection),
                                    *tuple(
                                        value.index_select(0, feedback_selection)
                                        for value in next_root
                                    ),
                                ),
                            )
                        next_lower_feedback = feedback
                    else:
                        next_lower_feedback = contract.feedback_lower_state(
                            runtime.lower_clips[
                                int(clip_ids[0].detach().cpu())
                            ],
                            next_lower,
                            next_pelvis,
                            *next_root,
                        )
                    controlled_next_base = runtime_data.base_upper_from_lower(
                        next_lower_feedback,
                        *next_root,
                        runtime.full_by_mode[mode],
                        rest,
                    )
                    current_row = torch.cat((controller_input, transition), dim=-1)
                    if direct_mse:
                        target_upper = runtime_data.upper_overlay_runtime_rows(
                            runtime,
                            mode,
                            clip_ids,
                            next_indices,
                            selected_gaze,
                            device,
                        )
                        authored_next_lower = runtime.store.get_target_output(
                            clip_ids, next_indices
                        )
                        target_pelvis = pelvis_heading(
                            authored_next_lower, next_root[1], next_root[2]
                        )
                        upper_mse = (next_upper - target_upper).square().mean(dim=-1)
                        pelvis_mse = (next_pelvis - target_pelvis).square().mean(dim=-1)
                        row_loss = torch.cat(
                            (next_upper - target_upper, next_pelvis - target_pelvis),
                            dim=-1,
                        ).square().mean(dim=-1)
                        # These two internal streams are reported under explicit
                        # upper/pelvis names in direct-MSE mode below.
                        ae1_row_loss = upper_mse
                        ae4_row_loss = pelvis_mse
                    else:
                        assert mean is not None and std is not None and ae is not None
                        assert ae1_output_weights is not None
                        assert ae4 is not None
                        assert ae4_input_mean is not None and ae4_input_std is not None
                        assert ae4_target_mean is not None and ae4_target_std is not None
                        window = torch.cat((upper_state["context_row"], current_row), dim=-1)
                        normalized = (window - mean) / std
                        reconstructed = ae(normalized)
                        ae1_row_loss = weighted_physical_mse(
                            reconstructed[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END]
                            - normalized[:, NEWEST_OUTPUT_START:NEWEST_OUTPUT_END],
                            ae1_output_weights,
                        )
                        ae4_condition, ae4_candidate = ae4_condition_and_candidate(
                            runtime,
                            mode,
                            clip_ids,
                            lower_state["prev"],
                            upper_state["previous_upper"],
                            upper_state["previous_pelvis"],
                            previous_root,
                            _current_globals,
                            current_root,
                            _next_globals,
                            next_root,
                            roots,
                            selected_gaze,
                        )
                        ae4_proposal = ae4_data.predict_absolute(
                            ae4,
                            ae4_condition,
                            ae4_input_mean,
                            ae4_input_std,
                            ae4_target_mean,
                            ae4_target_std,
                        ).detach()
                        ae4_row_loss = ae4_absolute_pose_loss(
                            ae4_candidate, ae4_proposal, ae4_target_std
                        )
                        row_loss = ae1_row_loss + AE4_LOSS_WEIGHT * ae4_row_loss
                    row_losses.append(row_loss)
                    row_ae1_losses.append(ae1_row_loss)
                    row_ae4_losses.append(ae4_row_loss)
                    if args.detach_rollout_gradient:
                        current_row = current_row.detach()
                        next_upper = next_upper.detach()
                        next_pelvis = next_pelvis.detach()
                        controlled_next_base = controlled_next_base.detach()
                        next_lower_feedback = next_lower_feedback.detach()
                    upper_state["context_row"] = current_row
                    upper_state["previous_upper"] = upper_state["current_upper"].detach() if args.detach_rollout_gradient else upper_state["current_upper"]
                    upper_state["current_upper"] = next_upper
                    upper_state["current_base"] = controlled_next_base
                    upper_state["previous_pelvis"] = upper_state["current_pelvis"].detach() if args.detach_rollout_gradient else upper_state["current_pelvis"]
                    upper_state["current_pelvis"] = next_pelvis
                    advance_lower(
                        runtime, lower_state, next_lower_feedback, next_indices
                    )

                if capture_rollout:
                    if rollout_step == 0:
                        debug_positions_frames.append(
                            torch.cat([step_current_positions[key] for key in groups], dim=0)
                        )
                        debug_rotations_frames.append(
                            torch.cat([step_current_rotations[key] for key in groups], dim=0)
                        )
                        debug_root_position_frames.append(
                            torch.cat([step_current_root_positions[key] for key in groups], dim=0)
                        )
                        debug_root_rotation_frames.append(
                            torch.cat([step_current_root_rotations[key] for key in groups], dim=0)
                        )
                        debug_source_frames.append(
                            torch.cat([step_current_sources[key] for key in groups], dim=0)
                        )
                    debug_positions_frames.append(
                        torch.cat([step_next_positions[key] for key in groups], dim=0)
                    )
                    debug_rotations_frames.append(
                        torch.cat([step_next_rotations[key] for key in groups], dim=0)
                    )
                    debug_root_position_frames.append(
                        torch.cat([step_next_root_positions[key] for key in groups], dim=0)
                    )
                    debug_root_rotation_frames.append(
                        torch.cat([step_next_root_rotations[key] for key in groups], dim=0)
                    )
                    debug_source_frames.append(
                        torch.cat([step_next_sources[key] for key in groups], dim=0)
                    )
                all_rows = torch.cat(row_losses, dim=0)
                all_ae1_rows = torch.cat(row_ae1_losses, dim=0)
                all_ae4_rows = torch.cat(row_ae4_losses, dim=0)
                all_gt_mse = torch.cat(row_gt_mses, dim=0)
                active = (effective_k > rollout_step).to(dtype=all_rows.dtype)
                weighted = all_rows * active / effective_k.to(dtype=all_rows.dtype)
                weighted_ae1 = (
                    all_ae1_rows * active / effective_k.to(dtype=all_ae1_rows.dtype)
                )
                weighted_ae4 = (
                    all_ae4_rows * active / effective_k.to(dtype=all_ae4_rows.dtype)
                )
                weighted_gt_mse = (
                    all_gt_mse * active / effective_k.to(dtype=all_gt_mse.dtype)
                )
                rollout_losses.append(weighted.mean())
                rollout_ae1_losses.append(weighted_ae1.mean())
                rollout_ae4_losses.append(weighted_ae4.mean())
                rollout_gt_mse.append(weighted_gt_mse.mean())
                for category in categories:
                    selections = [
                        slice(cursor_base[key], cursor_base[key] + rows_per_group)
                        for key in groups
                        if key[0] == category
                    ]
                    values = torch.cat([weighted_ae1[selection] for selection in selections])
                    category_sums[category] = category_sums[category] + values.mean()
            if capture_rollout:
                captured_rollout = (
                    debug_rows,
                    torch.stack(debug_positions_frames, dim=1),
                    torch.stack(debug_rotations_frames, dim=1),
                    torch.stack(debug_root_position_frames, dim=1),
                    torch.stack(debug_root_rotation_frames, dim=1),
                    torch.stack(debug_source_frames, dim=1),
                )
            micro_loss = torch.stack(rollout_losses).sum()
            micro_ae1 = torch.stack(rollout_ae1_losses).sum()
            micro_ae4 = torch.stack(rollout_ae4_losses).sum()
            micro_gt_mse = torch.stack(rollout_gt_mse).sum()
            (micro_loss / float(args.gradient_accumulation_steps)).backward()
            accumulated_total += float(micro_loss.detach().cpu())
            accumulated_ae1 += float(micro_ae1.detach().cpu())
            accumulated_ae4 += float(micro_ae4.detach().cpu())
            accumulated_gt_mse += float(micro_gt_mse.detach().cpu())
            for category in categories:
                accumulated_metrics[category] += float(category_sums[category].detach().cpu())

        gradient_norm = torch.nn.utils.clip_grad_norm_(agent.parameters(), 50.0)
        optimizer.step()
        elapsed = time.perf_counter() - started
        score = accumulated_total / float(args.gradient_accumulation_steps)
        ae1_score = accumulated_ae1 / float(args.gradient_accumulation_steps)
        ae4_score = accumulated_ae4 / float(args.gradient_accumulation_steps)
        gt_mse = accumulated_gt_mse / float(args.gradient_accumulation_steps)
        maximum_k = int(args.fixed_k) if args.fixed_k is not None else int(
            ROLLOUT_SCHEDULE[
                min(len(ROLLOUT_SCHEDULE) - 1, int(elapsed // ROLLOUT_STAGE_SECONDS))
            ]
        )
        improved = score < best
        if improved:
            best = score
            save_checkpoint(
                checkpoints_dir / f"{run_id}_best.pt",
                agent,
                optimizer,
                step,
                best,
                elapsed,
                maximum_k,
                metadata,
            )
        if step == 1 or step % int(args.checkpoint_every) == 0:
            save_checkpoint(
                checkpoints_dir / f"{run_id}_latest.pt",
                agent,
                optimizer,
                step,
                best,
                elapsed,
                maximum_k,
                metadata,
            )
            if step % int(args.checkpoint_every) == 0:
                save_checkpoint(
                    checkpoints_dir / f"checkpoint_step_{step:06d}.pt",
                    agent,
                    optimizer,
                    step,
                    best,
                    elapsed,
                    maximum_k,
                    metadata,
                )
        writer.add_scalar("loss/total", score, step)
        if direct_mse:
            writer.add_scalar("loss/upper_mse", ae1_score, step)
            writer.add_scalar("loss/pelvis_mse", ae4_score, step)
            for category in categories:
                writer.add_scalar(
                    f"loss/upper_mse_{category}",
                    accumulated_metrics[category]
                    / float(args.gradient_accumulation_steps),
                    step,
                )
        else:
            writer.add_scalar("loss/ae1", ae1_score, step)
            writer.add_scalar("loss/ae4", ae4_score, step)
            for category in categories:
                writer.add_scalar(
                    f"loss/ae1_{category}",
                    accumulated_metrics[category]
                    / float(args.gradient_accumulation_steps),
                    step,
                )
        writer.add_scalar("metric/gt_mse", gt_mse, step)
        writer.add_scalar("gradient_norm", float(gradient_norm), step)
        writer.add_scalar("Kmax", maximum_k, step)
        writer.flush()
        status = {
            "run_id": run_id,
            "step": step,
            "total_loss": score,
            "gt_mse": gt_mse,
            "best": best,
            "gradient_norm": float(gradient_norm),
            "Kmax": maximum_k,
            "motion_scope": args.motion_scope,
            "batch_size": int(args.batch_size),
            "gradient_accumulation_steps": int(args.gradient_accumulation_steps),
            "learning_rate": float(args.learning_rate),
            "sampled_rows": {
                f"{category}_{'drawn' if mode == runtime_data.MODE_DRAWN else 'sheathed'}": rows_per_group
                for category, mode in groups
            },
            "effective_k_counts": runtime_data.effective_rollout_k_counts(
                int(args.batch_size), maximum_k
            ),
            "elapsed_seconds": elapsed,
            "finite": all(
                math.isfinite(value)
                for value in (score, ae1_score, ae4_score, gt_mse, best, float(gradient_norm))
            ),
        }
        if direct_mse:
            status.update(
                {
                    "upper_mse": ae1_score,
                    "pelvis_mse": ae4_score,
                    "gaze_fixed_normalized": [0.0, 0.0],
                }
            )
        else:
            status.update(
                {
                    "ae1": ae1_score,
                    "ae4": ae4_score,
                    "ae4_weight": AE4_LOSS_WEIGHT,
                }
            )
        atomic_json(run_dir / "status.json", status)
        if captured_rollout is None:
            raise RuntimeError("Optimizer step is missing its exact rollout capture")
        capture_rows, capture_positions, capture_rotations, capture_root_positions, capture_root_rotations, capture_sources = captured_rollout
        prototype_category, prototype_mode = groups[0]
        replay_payload = exact_training_rollout_payload(
            run_id,
            step,
            runtimes[prototype_category].full_by_mode[prototype_mode],
            capture_rows,
            capture_positions,
            capture_rotations,
            capture_root_positions,
            capture_root_rotations,
            capture_sources,
        )
        atomic_compact_json(debug_dir / "last_batch_rollout.json", replay_payload)
        objective_values = (
            f"upper_mse={ae1_score:.8g} pelvis_mse={ae4_score:.8g}"
            if direct_mse
            else f"ae1={ae1_score:.8g} ae4={ae4_score:.8g}"
        )
        print(
            f"UPPER_PELVIS step={step} total={score:.8g} {objective_values} "
            f"best={best:.8g} grad={float(gradient_norm):.6g} "
            f"Kmax={maximum_k} elapsed_s={elapsed:.1f}",
            flush=True,
        )
        if bool(args.smoke):
            break
    writer.close()
    active_marker.unlink(missing_ok=True)
    print(f"UPPER_PELVIS_COMPLETE run={run_id}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ae-checkpoint")
    parser.add_argument("--ae-checkpoint-sha256", help=argparse.SUPPRESS)
    parser.add_argument(
        "--lower-cache",
        help=(
            "Continuous frame-zero frozen-lower dataset. Required by the accepted "
            "full-corpus upper-only CUDA Graph contract."
        ),
    )
    parser.add_argument(
        "--walk-pointer",
        help="Run-scoped frozen walk pointer; does not alter the global official pointer.",
    )
    parser.add_argument(
        "--direct-mse",
        action="store_true",
        help="Train only against raw authored next upper-pose plus pelvis MSE.",
    )
    parser.add_argument(
        "--ae1-only",
        action="store_true",
        help="Train with accepted AE1 as the only objective; do not load or call AE4/MSE.",
    )
    parser.add_argument(
        "--ae22-only",
        action="store_true",
        help="Train with audited root-relative condition-only AE22 as the sole objective.",
    )
    parser.add_argument(
        "--ae4-checkpoint",
        help="Frozen condition-only absolute-pose AE4 used by the weighted full-graph loss.",
    )
    parser.add_argument("--ae4-checkpoint-sha256", help=argparse.SUPPRESS)
    parser.add_argument(
        "--ae4-loss-weight",
        type=float,
        default=0.0,
        help=(
            "Coefficient on the AE4 absolute-pose objective; zero disables AE4. "
            "Non-hand rotations use the configured geodesic dead-zone term."
        ),
    )
    parser.add_argument(
        "--motion-scope",
        choices=("walk_forward", "walk_forward_drawn", "walk_run_omni", "full"),
        default="walk_run_omni",
    )
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=5.0e-6)
    parser.add_argument("--fixed-k", type=int)
    parser.add_argument(
        "--full-corpus-all-k32",
        action="store_true",
        help="Use K=32 for every row in the full-corpus CUDA Graph batch.",
    )
    parser.add_argument(
        "--ae4-to-ae1-frame-blend",
        action="store_true",
        help=(
            "Linearly blend from AE4=80%%/AE1=20%% at seed frame 0 to "
            "AE4=50%%/AE1=50%% at predicted frame 32."
        ),
    )
    parser.add_argument("--train-steps", type=int, default=0)
    parser.add_argument("--checkpoint-every", type=int, default=25)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--cuda-graph", action="store_true")
    parser.add_argument("--log-every", type=int, default=10)
    parser.add_argument("--rollout-export-every", type=int, default=250)
    parser.add_argument("--episode-noise-probability", type=float, default=0.0)
    parser.add_argument(
        "--episode-noise-pelvis-rotation-deg", type=float, default=0.0
    )
    parser.add_argument(
        "--episode-noise-pelvis-location-cm", type=float, default=0.0
    )
    parser.add_argument("--episode-noise-fk-rotation-deg", type=float, default=0.0)
    parser.add_argument(
        "--episode-noise-hand-location-cm", type=float, default=0.0
    )
    parser.add_argument(
        "--episode-noise-hand-rotation-deg", type=float, default=0.0
    )
    parser.add_argument(
        "--random-initial-gaze-half-per-noise-class",
        action="store_true",
        help=(
            "Within both clean and noisy reset-pose classes, author exactly half "
            "of initial poses from an independent uniform gaze while leaving the "
            "actual rollout gaze-input distribution unchanged."
        ),
    )
    parser.add_argument("--current-run-file")
    parser.add_argument("--stop-file")
    parser.add_argument("--resume-checkpoint", help=argparse.SUPPRESS)
    parser.add_argument("--resume-checkpoint-sha256", help=argparse.SUPPRESS)
    parser.add_argument("--resume-run-dir", help=argparse.SUPPRESS)
    parser.add_argument("--detach-rollout-gradient", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--rollout-gradient-window",
        type=int,
        default=0,
        help=(
            "Backpropagation-through-time window for cached-lower rollouts; "
            "0 keeps the full rollout graph, 1 is frame-local, and 2 gives "
            "each prediction one additional future frame of credit."
        ),
    )
    train(parser.parse_args())


if __name__ == "__main__":
    main()
