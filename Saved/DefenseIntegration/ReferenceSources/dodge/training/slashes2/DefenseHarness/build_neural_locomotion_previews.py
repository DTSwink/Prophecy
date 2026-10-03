from __future__ import annotations

"""Build the complete checkpoint-driven locomotion bank used by Defense Harness.

The harness never runs Torch in the browser.  This builder materializes the
accepted frozen lower policy followed by the accepted frozen upper policy into
small render-only NPZs.  Each row begins at a deterministic backstage-random
source frame: visible frames 0/1 are the two coherently perturbed primers and
frame 2 is the first neural prediction.
"""

import argparse
import gc
import hashlib
import json
import math
import sys
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import torch


HERE = Path(__file__).resolve().parent
SLASH2_ROOT = HERE.parent
PROJECT_ROOT = HERE.parents[2]
IK_ROOT = PROJECT_ROOT / "training" / "ik"
OUTPUT_ROOT = HERE / "neural_preview_npz"
MANIFEST_PATH = HERE / "neural_preview_manifest.json"
SELECTION_MANIFEST = HERE / "selection_manifest.json"
PREVIEW_CONTRACT = "defense_harness_neural_locomotion_preview_v1"
PREVIEW_SEED = 2_026_08_29
PREVIEW_FRAME_COUNT = 18
LOWER_INIT_NOISE_STRENGTH_MAX = 0.7  # Includes pelvis position/rotation channels.
UPPER_INIT_NOISE_STRENGTH_MAX = 0.01  # Upper noise never perturbs the pelvis.
VARIANT_BLOCK_COUNT = 5
CASES_PER_KIND_PER_BLOCK = 5
GAZE_CASES_PER_LOCOMOTION = CASES_PER_KIND_PER_BLOCK * VARIANT_BLOCK_COUNT
ATTACK_CASES_PER_LOCOMOTION = CASES_PER_KIND_PER_BLOCK * VARIANT_BLOCK_COUNT
CASES_PER_LOCOMOTION = GAZE_CASES_PER_LOCOMOTION + ATTACK_CASES_PER_LOCOMOTION
PRIMER_LENGTH_POLICY = "fixed_elbows_knees_radial_hands_feet_authored_lengths_v1"
PRIMER_ENDPOINT_TOLERANCE_M = 1e-4  # Authored root matrices are only approximately orthonormal.

WALK_CHECKPOINT = (
    PROJECT_ROOT
    / "training/runs/20260705_142401_ik_walk_finetune_legcap30_idlepin03_from_final"
    / "checkpoints/20260705_142401_ik_walk_finetune_legcap30_idlepin03_from_final_best.pt"
)
RUN_CHECKPOINT = (
    PROJECT_ROOT
    / "training/runs/20260617_234645_ik_ik_full_RESUME_best47200_k32fixed_s05_rootaccelx01_i_e8b756b3"
    / "checkpoints/20260617_234645_ik_ik_full_RESUME_best47200_k32fixed_s05_rootaccelx01_i_e8b756b3_init.pt"
)
UPPER_CHECKPOINT = (
    PROJECT_ROOT
    / "training/runs/20260816_051748_ik_upper_cached_ae1ae4_bs64_allk32_ble_hbb0ff7d69b"
    / "checkpoints/20260816_051748_ik_upper_cached_ae1ae4_bs64_allk32_blend_noise50_initgaze50each_latest.pt"
)

TEST_SOURCE_SPECS = (
    {
        "key": "runB",
        "label": "runB",
        "category": "run",
        "relative": "run_omni/M_Neutral_Run_Loop_B.npz",
        "checkpoint": RUN_CHECKPOINT,
    },
    {
        "key": "walkF",
        "label": "walkF",
        "category": "walk",
        "relative": "walk_omni/M_Neutral_Walk_Loop_F.npz",
        "checkpoint": WALK_CHECKPOINT,
    },
)

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SLASH2_ROOT))
sys.path.insert(0, str(IK_ROOT))

import ik_core as tl  # noqa: E402
import train_simple_ae_controller as lower_ctl  # noqa: E402
import train_upper_pose_autoencoder as upper_data  # noqa: E402
import train_upper_pose_controller as runtime_data  # noqa: E402
import train_upper_pose_controller_pelvis as upper_controller  # noqa: E402
import upper_pose_pelvis_contract as pelvis_contract  # noqa: E402
import visualize  # noqa: E402


def source_specs() -> list[dict[str, object]]:
    """Keep the original twenty case indices, then append the full matched corpus."""
    grouped = runtime_data.full_relative_datasets()
    specs = [dict(spec) for spec in TEST_SOURCE_SPECS]
    existing = {str(spec["relative"]) for spec in specs}
    for relative in sorted(path for rows in grouped.values() for path in rows):
        if relative in existing:
            continue
        group, filename = relative.split("/", 1)
        stem = Path(filename).stem
        category = "walk" if "Stand_" in stem or group.startswith("walk_") else "run"
        label = stem.removeprefix("M_Neutral_")
        if "Stand_Idle" in stem:
            label = "idle" if group.startswith("walk_") else "idle (run corpus)"
        specs.append({"key": f"{group}__{stem}", "label": label, "category": category,
                      "relative": relative, "checkpoint": WALK_CHECKPOINT if category == "walk" else RUN_CHECKPOINT})
    if len(specs) != 465:
        raise RuntimeError(f"Expected all 465 locomotions, got {len(specs)}")
    return specs


@dataclass(frozen=True)
class PreviewCase:
    source_key: str
    source_label: str
    category: str
    relative: str
    lower_checkpoint: Path
    ordinal: int
    init_kind: str
    mode: float
    gaze: tuple[float, float]
    source_start: int
    latest_source_start: int
    lower_noise_strength: float
    upper_noise_strength: float
    noise_seed: int
    attack_difficulty: str | None = None
    attack_name: str | None = None
    attack_initialization: int | None = None
    attack_frame: int | None = None
    attack_path: Path | None = None


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def checkpoint_init_noise(checkpoint: dict[str, Any]) -> dict[str, Any]:
    policy = dict(dict(checkpoint.get("metadata", {})).get("policy", {}))
    noise = policy.get("init_noise")
    if not isinstance(noise, dict) or not bool(noise.get("enabled")):
        raise RuntimeError("Accepted lower checkpoint has no enabled init-noise contract")
    return dict(noise)


def build_runtime(
    spec: dict[str, object], device: torch.device, relatives: list[str] | None = None,
) -> tuple[runtime_data.CategoryRuntime, dict[str, Any]]:
    checkpoint_path = Path(spec["checkpoint"]).resolve()
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    cfg = runtime_data.apply_checkpoint_config(checkpoint, device)
    relative = str(spec["relative"])
    probe = tl.MotionClip(
        runtime_data.ORIGINAL_ROOT / relative,
        cfg,
        cyclic_animation=runtime_data.is_cyclic(relative),
    )
    model = visualize.load_model(checkpoint, probe, cfg, device)
    model.eval().requires_grad_(False)
    runtime = runtime_data.build_category_runtime(
        str(spec["category"]), relatives or [relative], checkpoint, cfg, model, device
    )
    return runtime, checkpoint


def sampling_runtimes(specs):
    """Read clip bounds one at a time; do not keep both full policy banks live."""
    result = {}
    for category in ("run", "walk"):
        selected = [spec for spec in specs if spec["category"] == category]
        checkpoint = torch.load(Path(selected[0]["checkpoint"]), map_location="cpu", weights_only=False)
        cfg = runtime_data.apply_checkpoint_config(checkpoint, torch.device("cpu"))
        clips = []
        for spec in selected:
            clip = tl.MotionClip(runtime_data.ORIGINAL_ROOT / str(spec["relative"]), cfg,
                                 cyclic_animation=runtime_data.is_cyclic(str(spec["relative"])))
            clips.append(SimpleNamespace(T=clip.T, cyclic_animation=clip.cyclic_animation,
                                         cyclic_period=clip.cyclic_period))
            del clip
        result[category] = SimpleNamespace(cfg=SimpleNamespace(future_window=cfg.future_window),
                                           relatives=[str(spec["relative"]) for spec in selected], lower_clips=clips)
        del checkpoint
        gc.collect()
    return result


def wait_for_memory(stage, reserve_gib=1.5):
    """Back off between bounded operations instead of pressuring the desktop."""
    if sys.platform != "win32":
        return
    import ctypes
    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in
            ("total_physical", "available_physical", "total_page", "available_page",
             "total_virtual", "available_virtual", "extended_virtual")]
    reported = False
    while True:
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise RuntimeError("Cannot read system memory guard; generation held")
        if status.available_physical >= reserve_gib * 2**30 and status.available_page >= 6 * 2**30:
            if reported:
                print(f"Memory reserve recovered; resuming {stage}", flush=True)
            return
        if not reported:
            print(f"Memory guard waiting before {stage}: free RAM {status.available_physical / 2**30:.2f} GiB, "
                  f"free commit {status.available_page / 2**30:.2f} GiB", flush=True)
            reported = True
        time.sleep(5)


def load_upper_agent(device: torch.device) -> tuple[upper_controller.UpperCachedLowerAgent, dict[str, Any]]:
    checkpoint = torch.load(UPPER_CHECKPOINT, map_location="cpu", weights_only=False)
    if checkpoint.get("kind") != upper_controller.CACHED_LOWER_CONTROLLER_KIND:
        raise RuntimeError(f"Not the accepted cached-lower upper checkpoint: {UPPER_CHECKPOINT}")
    if checkpoint.get("schema") != upper_controller.cached_lower_checkpoint_schema():
        raise RuntimeError("Accepted upper checkpoint schema changed")
    model = upper_controller.UpperCachedLowerAgent().to(device)
    model.load_state_dict(checkpoint["model"], strict=True)
    model.eval().requires_grad_(False)
    return model, checkpoint


def concat_noise_batches(
    rows: list[lower_ctl.InitPoseNoiseBatch],
) -> lower_ctl.InitPoseNoiseBatch:
    if not rows:
        raise ValueError("Cannot concatenate an empty lower noise batch")
    return lower_ctl.InitPoseNoiseBatch(
        noisy_rows=torch.cat([row.noisy_rows for row in rows], dim=0),
        position_deltas=tuple(
            torch.cat([row.position_deltas[index] for row in rows], dim=0)
            for index in range(len(rows[0].position_deltas))
        ),
        scalar_deltas=tuple(
            torch.cat([row.scalar_deltas[index] for row in rows], dim=0)
            for index in range(len(rows[0].scalar_deltas))
        ),
        rotation_deltas=tuple(
            torch.cat([row.rotation_deltas[index] for row in rows], dim=0)
            for index in range(len(rows[0].rotation_deltas))
        ),
        global_yaw_delta=torch.cat([row.global_yaw_delta for row in rows], dim=0),
    )


def lower_noise_batch(
    runtime: runtime_data.CategoryRuntime,
    checkpoint: dict[str, Any],
    case: PreviewCase,
) -> lower_ctl.InitPoseNoiseBatch:
    contract = checkpoint_init_noise(checkpoint)
    base_strength = float(contract.get("fixed_strength_scale", 1.0))
    torch.manual_seed(int(case.noise_seed))
    if runtime.store.device.type == "cuda":
        torch.cuda.manual_seed_all(int(case.noise_seed))
    return lower_ctl.sample_fixed_init_pose_noise_batch(
        runtime.store,
        1,
        clean_fraction=0.0,
        device=runtime.store.device,
        dtype=torch.float32,
        strength_scale=base_strength * float(case.lower_noise_strength),
    )


def upper_noise_vectors(
    case: PreviewCase,
    checkpoint: dict[str, Any],
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    profile = dict(dict(checkpoint.get("metadata", {})).get("episode_start_noise", {}))
    required = (
        "pelvis_rotation_deg_max",
        "pelvis_location_cm_max",
        "fk_rotation_deg_max",
        "hand_location_cm_max",
        "hand_rotation_deg_max",
    )
    if any(name not in profile for name in required):
        raise RuntimeError("Accepted upper checkpoint episode-noise profile changed")
    if float(profile["pelvis_rotation_deg_max"]) != 0.0 or float(profile["pelvis_location_cm_max"]) != 0.0:
        raise RuntimeError("Accepted cached-lower upper noise may not perturb the pelvis")
    generator = torch.Generator(device="cpu").manual_seed(int(case.noise_seed) ^ 0x55AA_2197)
    scale = float(case.upper_noise_strength)

    def sampled_vectors(shape: tuple[int, ...], maximum: float) -> torch.Tensor:
        direction = tl.normalize(torch.randn((*shape, 3), generator=generator, dtype=torch.float32))
        magnitude = torch.rand((*shape, 1), generator=generator, dtype=torch.float32)
        return (direction * magnitude * float(maximum) * scale).to(device)

    return (
        sampled_vectors((1,), math.radians(float(profile["pelvis_rotation_deg_max"]))),
        sampled_vectors((1,), float(profile["pelvis_location_cm_max"]) * 0.01),
        sampled_vectors(
            (1, len(upper_controller.EPISODE_NOISE_FK_BONES)),
            math.radians(float(profile["fk_rotation_deg_max"])),
        ),
        sampled_vectors(
            (1, len(upper_controller.EPISODE_NOISE_HAND_BONES)),
            float(profile["hand_location_cm_max"]) * 0.01,
        ),
        sampled_vectors(
            (1, len(upper_controller.EPISODE_NOISE_HAND_BONES)),
            math.radians(float(profile["hand_rotation_deg_max"])),
        ),
    )


@lru_cache(maxsize=1)
def current_attack_initializers():
    from DefenseHarness import build_defense_harness as builder
    manifest, grouped = builder.load_actual_attack_rows()
    rows = {str(row["_path"]): row for values in grouped.values() for row in values}
    return builder, manifest, grouped, rows


@lru_cache(maxsize=32)
def attack_initializer_pose(path: str):
    builder, _, _, rows = current_attack_initializers()
    if path in rows:
        names, _, positions, rotations, _, _ = builder.read_actual_attack(rows[path])
        return names, positions, rotations
    with np.load(path, allow_pickle=False) as data:
        return ([str(value) for value in data["bone_names"]],
                np.asarray(data["controller_render_global_joint_pos_m"], dtype=np.float32),
                np.asarray(data["controller_render_global_rot"], dtype=np.float32))


def slash_upper_state(
    case: PreviewCase,
    full_clip: tl.MotionClip,
    device: torch.device,
) -> torch.Tensor:
    if case.attack_path is None or case.attack_frame is None:
        raise RuntimeError("Attack initializer is missing its sampled pose")
    names, all_positions, all_rotations = attack_initializer_pose(str(case.attack_path))
    by_name = {name: index for index, name in enumerate(names)}
    missing = [name for name in full_clip.body_names if name not in by_name]
    if missing:
        raise RuntimeError(
            f"Attack initializer lacks required bones {missing}: {case.attack_path}"
        )
    selected = [by_name[name] for name in full_clip.body_names]
    frame = int(case.attack_frame)
    raw_positions = np.asarray(all_positions[frame : frame + 1], dtype=np.float32)
    raw_rotations = np.asarray(all_rotations[frame : frame + 1], dtype=np.float32)
    source_root_position = torch.from_numpy(raw_positions[:, by_name["root"]]).to(device)
    source_root_rotation = torch.from_numpy(raw_rotations[:, by_name["root"]]).to(device)
    positions = torch.from_numpy(np.asarray(raw_positions[:, selected], dtype=np.float32)).to(device)
    rotations = torch.from_numpy(np.asarray(raw_rotations[:, selected], dtype=np.float32)).to(device)
    heading = tl.yaw_to_row_matrix(tl.heading_yaw_from_root(source_root_rotation))
    return upper_data.upper_state_from_global_pose_and_heading(
        full_clip, positions, rotations, source_root_position, heading
    )


def seed_upper_rows(
    runtime: runtime_data.CategoryRuntime,
    case: PreviewCase,
    lower_state: dict[str, torch.Tensor],
    upper_checkpoint: dict[str, Any],
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor]:
    mode = float(case.mode)
    full_clip = runtime.full_clips_by_mode[mode][runtime.relatives.index(case.relative)]
    clip_ids = lower_state["clip_ids"]
    primer_indices = torch.tensor(
        [case.source_start, case.source_start + 1], dtype=torch.long, device=device
    )
    if case.init_kind == "gaze":
        gaze = torch.tensor([case.gaze, case.gaze], dtype=torch.float32, device=device)
        upper = runtime_data.upper_overlay_runtime_rows(
            runtime, mode, clip_ids.repeat(2), primer_indices, gaze, device
        )
    elif case.init_kind == "attack":
        upper = slash_upper_state(case, full_clip, device).repeat(2, 1)
    else:
        raise RuntimeError(f"Unknown preview initializer {case.init_kind!r}")

    lower_rows = torch.cat((lower_state["prev"], lower_state["cur"]), dim=0)
    roots = runtime_data.root_state(runtime, primer_indices, clip_ids.repeat(2))
    pelvis_rows = upper_controller.pelvis_heading(lower_rows, roots[1], roots[2])
    positions, rotations = upper_controller.decode_rows(
        runtime,
        mode,
        lower_rows,
        upper,
        pelvis_rows,
        *roots,
        clip_ids.repeat(2),
    )
    pelvis_rotation, pelvis_translation, fk_rotation, hand_translation, hand_rotation = upper_noise_vectors(
        case, upper_checkpoint, device
    )
    repeated = (
        pelvis_rotation.repeat(2, 1),
        pelvis_translation.repeat(2, 1),
        fk_rotation.repeat(2, 1, 1),
        hand_translation.repeat(2, 1, 1),
        hand_rotation.repeat(2, 1, 1),
    )
    positions, rotations = upper_controller.apply_episode_start_pose_noise(
        full_clip,
        positions,
        rotations,
        torch.ones(2, dtype=torch.bool, device=device),
        *repeated,
        {
            name: upper_controller._episode_noise_subtree_indices(full_clip, name).to(device)
            for name in (
                "pelvis",
                *upper_controller.EPISODE_NOISE_FK_BONES,
                *upper_controller.EPISODE_NOISE_HAND_BONES,
            )
        },
    )
    encoded = upper_data.upper_state_from_global_pose_and_heading(
        full_clip, positions, rotations, roots[0], roots[2]
    )
    return encoded[0:1], encoded[1:2]


def project_primer_endpoints(full_clip, positions, rotations, geometry):
    """Final reset pass: preserve every joint except hands, feet, and their toes."""
    corrected = positions.clone()
    for limb_index, limb in enumerate(full_clip.ik_limb_specs):
        mid, end = int(limb["mid"]), int(limb["end"])
        delta = positions[:, end] - positions[:, mid]
        distance = torch.linalg.vector_norm(delta, dim=-1, keepdim=True)
        # A coincident endpoint has no radial direction; reuse its authored
        # lower-segment axis in the existing mid-joint frame, as FK does.
        fallback = torch.bmm(geometry["local_offsets"][:, end, None], rotations[:, mid]).squeeze(1)
        axis = torch.where(distance > 1e-8, delta / distance.clamp_min(1e-8), tl.normalize(fallback))
        corrected[:, end] = positions[:, mid] + axis * geometry["ik_limb_lengths"][:, limb_index, 1:2]
        if limb.get("toe") is not None:
            toe = int(limb["toe"])
            corrected[:, toe] = positions[:, toe] + corrected[:, end] - positions[:, end]
    return corrected


def finalize_primers(runtime, mode, lower, roots, clip_ids, positions, rotations):
    """Encode the final correction into BOTH histories, not a render-only repair.

    The noisy primers have already passed through the runtime leg solver. Once
    their feet are projected around those fixed knees, ordinary FK is the exact
    decoder: another pelvis/leg IK solve would unnecessarily move the knees.
    Predictions after the two primers retain the unmodified runtime decoder.
    """
    full_clip, lower_clip = runtime.full_by_mode[mode], runtime.lower_clip
    geometry = {name: value.index_select(0, clip_ids)
                for name, value in runtime.full_geometry_by_mode[mode].items()}
    corrected = project_primer_endpoints(full_clip, positions, rotations, geometry)
    upper = upper_data.upper_state_from_global_pose_and_heading(full_clip, corrected, rotations, roots[0], roots[2])
    lower = lower.clone()
    by_name = {name: index for index, name in enumerate(full_clip.body_names)}
    payload_offset = 9 + lower_clip.Jcore * 6
    for limb, payload in zip(lower_clip.ik_limb_specs, lower_clip.ik_payload_slices):
        start = by_name[lower_clip.body_names[int(limb["start"])]]
        end = by_name[lower_clip.body_names[int(limb["end"])]]
        pos_slice, rot_slice = payload["pos"], payload["start_rot6"]
        lower[:, payload_offset + pos_slice.start:payload_offset + pos_slice.stop] = torch.bmm(
            (corrected[:, end] - roots[0])[:, None], roots[1].transpose(-1, -2)).squeeze(1)
        lower[:, payload_offset + rot_slice.start:payload_offset + rot_slice.stop] = tl.rotmat_to_6d(
            rotations[:, start] @ roots[1].transpose(-1, -2))
    pelvis = upper_controller.pelvis_heading(lower, roots[1], roots[2])
    full = pelvis_contract._compose_full_vector(full_clip, lower_clip, lower, upper, pelvis, roots[1], roots[2])
    pose, _ = tl.output_to_pose(full, full_clip)
    decoded_positions, decoded_rotations, _ = tl.fk_from_pose(
        full_clip, roots[0], roots[1], pose, lower.device, geometry_tensors=geometry)
    # Fail before inference/publication if the NN history cannot represent the
    # approved fixed-pelvis/elbow/knee correction. Never silently move them.
    error = float((decoded_positions - corrected).abs().max())
    if not np.isfinite(error) or error > PRIMER_ENDPOINT_TOLERANCE_M:
        row, joint, axis = np.unravel_index(int((decoded_positions - corrected).abs().argmax()), corrected.shape)
        raise RuntimeError(f"Primer encoding changed corrected/fixed joint positions by {error:.8g} m: "
                           f"{runtime.relatives[int(clip_ids[row])]} row {row}, {full_clip.body_names[joint]}, axis {axis}")
    length_error = max(float((torch.linalg.vector_norm(
        decoded_positions[:, int(limb["end"])] - decoded_positions[:, int(limb["mid"])], dim=-1)
        - geometry["ik_limb_lengths"][:, index, 1]).abs().max())
        for index, limb in enumerate(full_clip.ik_limb_specs))
    moved = {int(limb["end"]) for limb in full_clip.ik_limb_specs}
    moved.update(int(limb["toe"]) for limb in full_clip.ik_limb_specs if limb.get("toe") is not None)
    fixed = [index for index in range(full_clip.J) if index not in moved]
    fixed_error = float((decoded_positions[:, fixed] - positions[:, fixed]).abs().max())
    if not np.isfinite(fixed_error) or fixed_error > 2e-5:
        raise RuntimeError(f"Primer encoding moved a fixed joint by {fixed_error:.8g} m")
    if not np.isfinite(length_error) or length_error > PRIMER_ENDPOINT_TOLERANCE_M:
        raise RuntimeError(f"Primer forearm/calf authored-length error: {length_error:.8g} m")
    audit = getattr(runtime, "primer_length_audit", {})
    audit["max_encoding_position_error_m"] = max(audit.get("max_encoding_position_error_m", 0.0), error)
    audit["max_forearm_calf_length_error_m"] = max(audit.get("max_forearm_calf_length_error_m", 0.0), length_error)
    audit["max_fixed_joint_change_m"] = max(audit.get("max_fixed_joint_change_m", 0.0), fixed_error)
    runtime.primer_length_audit = audit
    return lower, upper, decoded_positions, decoded_rotations


@torch.inference_mode()
def rollout_case(
    runtime: runtime_data.CategoryRuntime,
    lower_checkpoint: dict[str, Any],
    upper_agent: upper_controller.UpperCachedLowerAgent,
    upper_checkpoint: dict[str, Any],
    case: PreviewCase,
    device: torch.device,
) -> tuple[np.ndarray, np.ndarray, float]:
    runtime.install_policy()
    starts = torch.tensor([case.source_start + 1], dtype=torch.long, device=device)
    clip_ids = torch.full_like(starts, runtime.relatives.index(case.relative))
    lower_state = runtime_data.lower_initial_state(runtime, starts, clip_ids)
    noise = lower_noise_batch(runtime, lower_checkpoint, case)
    lower_state["prev"] = lower_ctl.apply_init_pose_noise_batch(runtime.store, lower_state["prev"], noise)
    lower_state["cur"] = lower_ctl.apply_init_pose_noise_batch(runtime.store, lower_state["cur"], noise)
    payload_slice = lower_ctl.payload_slice(runtime.store)
    lower_state["prev_pelvis"] = lower_state["prev"][:, :3]
    lower_state["cur_pelvis"] = lower_state["cur"][:, :3]
    lower_state["prev_payload"] = lower_state["prev"][:, payload_slice]
    lower_state["cur_payload"] = lower_state["cur"][:, payload_slice]

    previous_upper, current_upper = seed_upper_rows(
        runtime, case, lower_state, upper_checkpoint, device
    )
    mode = float(case.mode)
    full_clip = runtime.full_clips_by_mode[mode][runtime.relatives.index(case.relative)]
    clip_ids = lower_state["clip_ids"]
    primer_indices = torch.tensor(
        [case.source_start, case.source_start + 1], dtype=torch.long, device=device
    )
    lower_primer = torch.cat((lower_state["prev"], lower_state["cur"]), dim=0)
    primer_roots = runtime_data.root_state(runtime, primer_indices, clip_ids.repeat(2))
    primer_pelvis = upper_controller.pelvis_heading(
        lower_primer, primer_roots[1], primer_roots[2]
    )
    primer_upper = torch.cat((previous_upper, current_upper), dim=0)
    primer_positions, primer_rotations = upper_controller.decode_rows(
        runtime,
        mode,
        lower_primer,
        primer_upper,
        primer_pelvis,
        *primer_roots,
        clip_ids.repeat(2),
    )
    lower_primer, primer_upper, primer_positions, primer_rotations = finalize_primers(
        runtime, mode, lower_primer, primer_roots, clip_ids.repeat(2), primer_positions, primer_rotations)
    lower_state["prev"], lower_state["cur"] = lower_primer[:1], lower_primer[1:]
    bind_state_views(runtime, lower_state)
    previous_upper, current_upper = primer_upper[:1], primer_upper[1:]
    position_rows = [primer_positions[0].cpu(), primer_positions[1].cpu()]
    rotation_rows = [primer_rotations[0].cpu(), primer_rotations[1].cpu()]

    previous_root = runtime_data.root_state(
        runtime, torch.tensor([case.source_start], dtype=torch.long, device=device), clip_ids
    )
    current_root = runtime_data.root_state(runtime, lower_state["cur_idx"], clip_ids)
    previous_pelvis = upper_controller.pelvis_heading(
        lower_state["prev"], previous_root[1], previous_root[2]
    )
    current_pelvis = upper_controller.pelvis_heading(
        lower_state["cur"], current_root[1], current_root[2]
    )
    rest = runtime.rest_offsets_by_mode[mode].index_select(0, clip_ids)
    current_base = runtime_data.base_upper_from_lower(
        lower_state["cur"], *current_root, full_clip, rest
    )
    gaze = torch.tensor([case.gaze], dtype=torch.float32, device=device)
    sword = torch.full((1, 1), mode, dtype=torch.float32, device=device)

    for _step in range(PREVIEW_FRAME_COUNT - 2):
        next_lower = upper_controller.lower_next_live(runtime, lower_state)
        next_index = lower_state["cur_idx"] + 1
        current_root = runtime_data.root_state(runtime, lower_state["cur_idx"], clip_ids)
        next_root = runtime_data.root_state(runtime, next_index, clip_ids)
        next_pelvis = upper_controller.pelvis_heading(next_lower, next_root[1], next_root[2])
        next_base = runtime_data.base_upper_from_lower(
            next_lower, *next_root, full_clip, rest
        )
        upper_prior = upper_data.clean_upper_state(
            next_base + current_upper - current_base
        )
        current_feet = runtime_data.foot_heading_features(
            runtime.store,
            lower_state["cur"],
            current_root[1],
            current_root[2],
        )
        next_feet = runtime_data.foot_heading_features(
            runtime.store, next_lower, next_root[1], next_root[2]
        )
        controller_input = torch.cat(
            (
                previous_upper,
                upper_prior,
                previous_pelvis,
                current_pelvis,
                next_pelvis,
                runtime.store.get_input_root_features(clip_ids, lower_state["cur_idx"]),
                sword,
                current_feet,
                next_feet,
                gaze,
            ),
            dim=-1,
        )
        if tuple(controller_input.shape) != (1, upper_controller.INPUT_DIM):
            raise RuntimeError(f"Upper controller input changed: {tuple(controller_input.shape)}")
        next_upper = upper_data.clean_upper_state(
            upper_prior + upper_agent(controller_input)
        )
        next_positions, next_rotations = upper_controller.decode_rows(
            runtime,
            mode,
            next_lower,
            next_upper,
            next_pelvis,
            *next_root,
            clip_ids,
        )
        position_rows.append(next_positions[0].cpu())
        rotation_rows.append(next_rotations[0].cpu())
        upper_controller.advance_lower(runtime, lower_state, next_lower, next_index)
        previous_upper = current_upper
        current_upper = next_upper
        previous_pelvis = current_pelvis
        current_pelvis = next_pelvis
        current_base = next_base

    positions = torch.stack(position_rows).numpy().astype(np.float32, copy=False)
    rotations = torch.stack(rotation_rows).numpy().astype(np.float32, copy=False)
    if positions.shape[0] != PREVIEW_FRAME_COUNT or rotations.shape[0] != PREVIEW_FRAME_COUNT:
        raise RuntimeError("Neural preview frame count changed")
    if not np.isfinite(positions).all() or not np.isfinite(rotations).all():
        raise RuntimeError(f"Neural preview produced non-finite transforms: {case}")
    return positions, rotations, float(full_clip.fps)


@torch.inference_mode()
def prepare_batch(runtime, lower_checkpoint, upper_checkpoint, cases, device, attack_cache):
    """The original per-case noise draws, applied together without changing RNG ownership."""
    runtime.install_policy()
    starts = torch.tensor([case.source_start + 1 for case in cases], device=device)
    clip_ids = torch.tensor([runtime.relatives.index(case.relative) for case in cases], device=device)
    state = runtime_data.lower_initial_state(runtime, starts, clip_ids)
    noise = concat_noise_batches([lower_noise_batch(runtime, lower_checkpoint, case) for case in cases])
    state["prev"] = lower_ctl.apply_init_pose_noise_batch(runtime.store, state["prev"], noise)
    state["cur"] = lower_ctl.apply_init_pose_noise_batch(runtime.store, state["cur"], noise)
    bind_state_views(runtime, state)
    mode, count = cases[0].mode, len(cases)
    full_clip = runtime.full_by_mode[mode]
    indices = torch.cat((starts - 1, starts))
    doubled_ids = clip_ids.repeat(2)
    gaze = torch.tensor([case.gaze for case in cases], dtype=torch.float32, device=device)
    upper = runtime_data.upper_overlay_runtime_rows(runtime, mode, doubled_ids, indices, gaze.repeat(2, 1), device)
    for row, case in enumerate(cases):
        if case.init_kind == "attack":
            key = (str(case.attack_path), case.attack_frame, tuple(full_clip.body_names))
            if key not in attack_cache:
                attack_cache[key] = slash_upper_state(case, full_clip, device)
            upper[row] = upper[row + count] = attack_cache[key][0]
    lower = torch.cat((state["prev"], state["cur"]))
    roots = runtime_data.root_state(runtime, indices, doubled_ids)
    pelvis = upper_controller.pelvis_heading(lower, roots[1], roots[2])
    positions, rotations = upper_controller.decode_rows_vectorized(runtime, mode, lower, upper, pelvis, *roots, doubled_ids)
    noise_rows = [upper_noise_vectors(case, upper_checkpoint, device) for case in cases]
    noise_values = [torch.cat([row[index] for row in noise_rows]).repeat((2,) + (1,) * (noise_rows[0][index].ndim - 1)) for index in range(5)]
    positions, rotations = upper_controller.apply_episode_start_pose_noise(
        full_clip, positions, rotations, torch.ones(2 * count, dtype=torch.bool, device=device),
        *noise_values, {name: upper_controller._episode_noise_subtree_indices(full_clip, name).to(device)
                        for name in ("pelvis", *upper_controller.EPISODE_NOISE_FK_BONES, *upper_controller.EPISODE_NOISE_HAND_BONES)})
    upper = upper_data.upper_state_from_global_pose_and_heading(full_clip, positions, rotations, roots[0], roots[2])
    # Decode the encoded primers exactly as the reference path does.
    primer_positions, primer_rotations = upper_controller.decode_rows_vectorized(runtime, mode, lower, upper, pelvis, *roots, doubled_ids)
    lower, upper, primer_positions, primer_rotations = finalize_primers(
        runtime, mode, lower, roots, doubled_ids, primer_positions, primer_rotations)
    state["prev"], state["cur"] = lower[:count], lower[count:]
    bind_state_views(runtime, state)
    previous_root = runtime_data.root_state(runtime, starts - 1, clip_ids)
    current_root = runtime_data.root_state(runtime, starts, clip_ids)
    rest = runtime.rest_offsets_by_mode[mode].index_select(0, clip_ids)
    values = {"previous_upper": upper[:count], "current_upper": upper[count:],
              "previous_pelvis": upper_controller.pelvis_heading(state["prev"], previous_root[1], previous_root[2]),
              "current_pelvis": upper_controller.pelvis_heading(state["cur"], current_root[1], current_root[2]),
              "current_base": runtime_data.base_upper_from_lower(state["cur"], *current_root, full_clip, rest),
              "gaze": gaze}
    return state, values, primer_positions.reshape(2, count, *primer_positions.shape[1:]).transpose(0, 1), primer_rotations.reshape(2, count, *primer_rotations.shape[1:]).transpose(0, 1)


def bind_state_views(runtime, state):
    payload = lower_ctl.payload_slice(runtime.store)
    state["prev_pelvis"], state["cur_pelvis"] = state["prev"][:, :3], state["cur"][:, :3]
    state["prev_payload"], state["cur_payload"] = state["prev"][:, payload], state["cur"][:, payload]


class CapturedRollout:
    """One fixed-batch neural frame captured once, then reused across all clips in a category/mode."""
    @torch.inference_mode()
    def __init__(self, runtime, mode, upper_agent, state, values):
        self.runtime, self.mode, self.upper_agent = runtime, mode, upper_agent
        self.state = {key: value.clone() for key, value in state.items() if key not in ("prev_pelvis", "cur_pelvis", "prev_payload", "cur_payload")}
        bind_state_views(runtime, self.state)
        self.values = {key: value.clone() for key, value in values.items()}
        self.sword = torch.full((len(state["cur_idx"]), 1), mode, device=state["cur"].device)
        stream = torch.cuda.Stream()
        stream.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(stream):
            for _ in range(2):
                self.load(state, values)
                self.step()
        torch.cuda.current_stream().wait_stream(stream)
        self.load(state, values)
        self.graph = torch.cuda.CUDAGraph()
        with torch.cuda.graph(self.graph):
            self.output = self.step()
        self.load(state, values)

    def load(self, state, values):
        for key in ("clip_ids", "cur_idx", "older", "prev", "cur"):
            self.state[key].copy_(state[key])
        for key, value in values.items():
            self.values[key].copy_(value)

    def step(self):
        runtime, mode, state, value = self.runtime, self.mode, self.state, self.values
        clip_ids = state["clip_ids"]
        next_lower = upper_controller.lower_next_live(runtime, state)
        next_index = state["cur_idx"] + 1
        current_root = runtime_data.root_state(runtime, state["cur_idx"], clip_ids)
        next_root = runtime_data.root_state(runtime, next_index, clip_ids)
        next_pelvis = upper_controller.pelvis_heading(next_lower, next_root[1], next_root[2])
        rest = runtime.rest_offsets_by_mode[mode].index_select(0, clip_ids)
        next_base = runtime_data.base_upper_from_lower(next_lower, *next_root, runtime.full_by_mode[mode], rest)
        prior = upper_data.clean_upper_state(next_base + value["current_upper"] - value["current_base"])
        current_feet = runtime_data.foot_heading_features(runtime.store, state["cur"], current_root[1], current_root[2])
        next_feet = runtime_data.foot_heading_features(runtime.store, next_lower, next_root[1], next_root[2])
        inputs = torch.cat((value["previous_upper"], prior, value["previous_pelvis"], value["current_pelvis"], next_pelvis,
                            runtime.store.get_input_root_features(clip_ids, state["cur_idx"]), self.sword, current_feet, next_feet, value["gaze"]), dim=-1)
        next_upper = upper_data.clean_upper_state(prior + self.upper_agent(inputs))
        positions, rotations = upper_controller.decode_rows_vectorized(runtime, mode, next_lower, next_upper, next_pelvis, *next_root, clip_ids)
        state["older"].copy_(state["prev"])
        state["prev"].copy_(state["cur"])
        state["cur"].copy_(next_lower)
        state["cur_idx"].copy_(next_index)
        value["previous_upper"].copy_(value["current_upper"])
        value["current_upper"].copy_(next_upper)
        value["previous_pelvis"].copy_(value["current_pelvis"])
        value["current_pelvis"].copy_(next_pelvis)
        value["current_base"].copy_(next_base)
        return positions, rotations

    @torch.inference_mode()
    def rollout(self, state, values, primer_positions, primer_rotations):
        self.load(state, values)
        count = primer_positions.shape[0]
        positions = primer_positions.new_empty((count, PREVIEW_FRAME_COUNT, *primer_positions.shape[2:]))
        rotations = primer_rotations.new_empty((count, PREVIEW_FRAME_COUNT, *primer_rotations.shape[2:]))
        positions[:, :2], rotations[:, :2] = primer_positions, primer_rotations
        for frame in range(2, PREVIEW_FRAME_COUNT):
            self.graph.replay()
            positions[:, frame].copy_(self.output[0])
            rotations[:, frame].copy_(self.output[1])
        return positions.cpu().numpy(), rotations.cpu().numpy()


def attack_templates(rng: np.random.Generator) -> list[dict[str, object]]:
    selection = json.loads(SELECTION_MANIFEST.read_text(encoding="utf-8"))
    attacks = [str(value) for value in selection["attacks"]]
    difficulties = [str(value) for value in selection["modes"]]
    if not difficulties:
        raise RuntimeError("Attack initializer selection has no generated difficulties")
    chosen = [attacks[int(index)] for index in rng.choice(len(attacks), size=CASES_PER_KIND_PER_BLOCK, replace=False)]
    templates: list[dict[str, object]] = []
    for attack in chosen:
        difficulty = difficulties[int(rng.integers(0, len(difficulties)))]
        available = [int(value) for value in selection["identities"][f"{difficulty}:{attack}"]]
        initialization = available[int(rng.integers(0, len(available)))]
        _, _, grouped, _ = current_attack_initializers()
        matched = [row for row in grouped[(difficulty, attack)] if int(row["initializationIndex"]) == initialization]
        if len(matched) != 1:
            raise RuntimeError(f"Attack initializer selection does not resolve: {difficulty}:{attack}:{initialization}")
        path = Path(matched[0]["_path"])
        frame_count = int(attack_initializer_pose(str(path))[1].shape[0])
        templates.append(
            {
                "difficulty": difficulty,
                "attack": attack,
                "initialization": initialization,
                "frame": int(rng.integers(0, frame_count)),
                "path": path,
            }
        )
    return templates


def preview_cases(
    runtimes: dict[str, runtime_data.CategoryRuntime],
    specs: list[dict[str, object]],
) -> list[PreviewCase]:
    # Append complete corpus blocks, never interleave new rows into old indices.
    # Block zero is exactly the original ten-variant RNG stream and construction.
    return [case for block in range(VARIANT_BLOCK_COUNT)
            for case in preview_case_block(runtimes, specs, block)]


def preview_case_block(
    runtimes: dict[str, runtime_data.CategoryRuntime],
    specs: list[dict[str, object]],
    block: int,
) -> list[PreviewCase]:
    rng = np.random.default_rng(PREVIEW_SEED + block)
    ordinal_offset = block * CASES_PER_KIND_PER_BLOCK
    attack_rows = attack_templates(rng)
    cases: list[PreviewCase] = []
    for spec in specs:
        runtime = runtimes[str(spec["category"])]
        clip = runtime.lower_clips[runtime.relatives.index(str(spec["relative"]))]
        latest_current = runtime_data.valid_start_max(
            clip,
            PREVIEW_FRAME_COUNT - 2,
            int(runtime.cfg.future_window),
        )
        latest_primer = latest_current - 1
        if latest_primer < 1:
            raise RuntimeError(f"{spec['key']} is too short for the neural preview")
        modes = np.asarray(
            [runtime_data.MODE_SHEATHED, runtime_data.MODE_SHEATHED, runtime_data.MODE_DRAWN, runtime_data.MODE_DRAWN, runtime_data.MODE_DRAWN],
            dtype=np.float32,
        )
        rng.shuffle(modes)
        for ordinal in range(CASES_PER_KIND_PER_BLOCK):
            source_start = int(rng.integers(1, latest_primer + 1))
            strength = float(rng.random())
            gaze_values = tuple(float(value) for value in rng.uniform(-1.0, 1.0, size=2))
            cases.append(
                PreviewCase(
                    source_key=str(spec["key"]),
                    source_label=str(spec["label"]),
                    category=str(spec["category"]),
                    relative=str(spec["relative"]),
                    lower_checkpoint=Path(spec["checkpoint"]),
                    ordinal=ordinal + ordinal_offset,
                    init_kind="gaze",
                    mode=float(modes[ordinal]),
                    gaze=gaze_values,
                    source_start=source_start,
                    latest_source_start=latest_primer,
                    lower_noise_strength=strength * LOWER_INIT_NOISE_STRENGTH_MAX,
                    upper_noise_strength=strength * UPPER_INIT_NOISE_STRENGTH_MAX,
                    noise_seed=int(rng.integers(1, 2**31 - 1)),
                )
            )
        for ordinal, attack in enumerate(attack_rows):
            source_start = int(rng.integers(1, latest_primer + 1))
            strength = float(rng.random())
            cases.append(
                PreviewCase(
                    source_key=str(spec["key"]),
                    source_label=str(spec["label"]),
                    category=str(spec["category"]),
                    relative=str(spec["relative"]),
                    lower_checkpoint=Path(spec["checkpoint"]),
                    ordinal=ordinal + ordinal_offset,
                    init_kind="attack",
                    mode=runtime_data.MODE_DRAWN,
                    gaze=(0.0, 0.0),
                    source_start=source_start,
                    latest_source_start=latest_primer,
                    lower_noise_strength=strength * LOWER_INIT_NOISE_STRENGTH_MAX,
                    upper_noise_strength=strength * UPPER_INIT_NOISE_STRENGTH_MAX,
                    noise_seed=int(rng.integers(1, 2**31 - 1)),
                    attack_difficulty=str(attack["difficulty"]),
                    attack_name=str(attack["attack"]),
                    attack_initialization=int(attack["initialization"]),
                    attack_frame=int(attack["frame"]),
                    attack_path=Path(attack["path"]),
                )
            )
    return cases


def case_filename(case: PreviewCase) -> str:
    return f"{case.source_key}__{case.init_kind}_{case.ordinal + 1:02d}.npz"


def case_label(case: PreviewCase) -> str:
    noise = f"noise lower/pelvis {case.lower_noise_strength:.3f}, upper {case.upper_noise_strength:.4f}"
    if case.init_kind == "gaze":
        sword = "drawn" if case.mode == runtime_data.MODE_DRAWN else "sheathed"
        return (
            f"{case.source_label} · gaze {case.ordinal + 1}/{GAZE_CASES_PER_LOCOMOTION} · {sword} · "
            f"({case.gaze[0]:+.2f}, {case.gaze[1]:+.2f}) · {noise}"
        )
    return (
        f"{case.source_label} · attack init {case.ordinal + 1}/{ATTACK_CASES_PER_LOCOMOTION} · "
        f"{case.attack_difficulty} {case.attack_name} "
        f"#{case.attack_initialization:04d} F{case.attack_frame} · {noise}"
    )


def source_identity(specs: list[dict[str, object]]) -> dict[str, object]:
    attack_builder, _, _, _ = current_attack_initializers()
    return {
        "contract": PREVIEW_CONTRACT,
        "seed": PREVIEW_SEED,
        "frame_count": PREVIEW_FRAME_COUNT,
        "initialization_noise_strength_ranges": {
            "lower_and_pelvis": [0.0, LOWER_INIT_NOISE_STRENGTH_MAX],
            "upper": [0.0, UPPER_INIT_NOISE_STRENGTH_MAX],
        },
        "walk_checkpoint": {"path": str(WALK_CHECKPOINT), "sha256": file_sha256(WALK_CHECKPOINT)},
        "run_checkpoint": {"path": str(RUN_CHECKPOINT), "sha256": file_sha256(RUN_CHECKPOINT)},
        "upper_checkpoint": {"path": str(UPPER_CHECKPOINT), "sha256": file_sha256(UPPER_CHECKPOINT)},
        "selection_manifest_sha256": file_sha256(SELECTION_MANIFEST),
        "attack_initializer_dataset_sha256": file_sha256(attack_builder.ACTUAL_ATTACK_MANIFEST),
        "attack_initializer_pose_policy": "current_inferred_attacks_harness_root_v1",
        "attack_initializer_difficulty_policy": "uniform_over_selection_manifest_modes_per_attack_case",
        "generator": "full_corpus_batched_cuda_graph_v2",
        "primer_length_policy": PRIMER_LENGTH_POLICY,
        "variant_policy": "append_corpus_blocks_5_gaze_5_attack_seed_plus_block_v1",
        "variant_block_count": VARIANT_BLOCK_COUNT,
        "cases_per_locomotion": CASES_PER_LOCOMOTION,
        "ik_core_sha256": file_sha256(Path(tl.__file__)),
        "sources": [{"key": spec["key"], "relative": spec["relative"], "category": spec["category"],
                     "authored_sha256": file_sha256(runtime_data.ORIGINAL_ROOT / str(spec["relative"])),
                     "drawn_sha256": file_sha256(runtime_data.DRAWN_ROOT / str(spec["relative"]))} for spec in specs],
    }


def existing_cache_hit(identity: dict[str, object]) -> bool:
    if not MANIFEST_PATH.is_file():
        return False
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    files = manifest.get("cases", [])
    return manifest.get("source_identity") == identity and len(files) == len(identity["sources"]) * CASES_PER_LOCOMOTION and all(
        (OUTPUT_ROOT / str(row.get("file", ""))).is_file() for row in files
    )


def validate_pose_rotations(rotations: np.ndarray, context: str) -> float:
    """Reject malformed rotations before publishing neural poses to the harness."""
    error = float(np.max(np.abs(rotations @ np.swapaxes(rotations, -1, -2) - np.eye(3))))
    determinant_error = float(np.max(np.abs(np.linalg.det(rotations) - 1.0)))
    if not np.isfinite(error) or max(error, determinant_error) > 1e-4:
        raise RuntimeError(f"Invalid pose rotations in {context}: orthogonality={error}, determinant={determinant_error}")
    return error


def validate_sampled_case(index, case, row):
    expected = {"case_index": index, "source_key": case.source_key, "source_relative": case.relative,
                "init_kind": case.init_kind, "noise_seed": case.noise_seed,
                "source_start_frame": case.source_start, "latest_source_start_frame": case.latest_source_start,
                "gaze_normalized": list(case.gaze), "lower_noise_strength_0_to_1": case.lower_noise_strength,
                "upper_noise_strength_0_to_1": case.upper_noise_strength,
                "mode": "drawn" if case.mode == runtime_data.MODE_DRAWN else "sheathed"}
    if any(row.get(key) != value for key, value in expected.items()):
        raise RuntimeError(f"Regeneration changed sampled setup {index}: {case_filename(case)}")
    if case.init_kind == "attack":
        attack = row["attack_initializer"]
        if (attack["difficulty"], attack["attack"], attack["initialization"], attack["frame"], attack["source"]) != (
            case.attack_difficulty, case.attack_name, case.attack_initialization, case.attack_frame, str(case.attack_path)
        ):
            raise RuntimeError(f"Regeneration changed attack initializer at {index}")


def initialization_noise_ranges(identity):
    """Read the split contract, or the historical shared-strength contract."""
    if "initialization_noise_strength_ranges" in identity:
        return identity["initialization_noise_strength_ranges"]
    shared = identity.get("initialization_noise_strength_range", [0.0, 1.0])
    return {"lower_and_pelvis": shared, "upper": shared}


def verify_preserved_sampling(identity, cases):
    """Primer/noise-scale changes retain all other draws and normalized noise."""
    if not MANIFEST_PATH.is_file():
        return 0
    previous = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    without_primer = lambda value: {key: item for key, item in value.items()
                                   if key not in {"primer_length_policy", "initialization_noise_strength_range",
                                                  "initialization_noise_strength_ranges"}}
    if without_primer(previous.get("source_identity", {})) != without_primer(identity):
        return 0
    if len(previous["cases"]) != len(cases):
        raise RuntimeError("Primer/noise-scale regeneration changed the case count")
    old_ranges = initialization_noise_ranges(previous["source_identity"])
    new_ranges = initialization_noise_ranges(identity)
    for limits in [*old_ranges.values(), *new_ranges.values()]:
        if limits[0] != 0 or limits[1] <= 0:
            raise RuntimeError("Cannot certify preserved normalized noise for these ranges")
    for index, (case, row) in enumerate(zip(cases, previous["cases"])):
        adjusted = dict(row)
        for key, value, channel in (("lower_noise_strength_0_to_1", case.lower_noise_strength, "lower_and_pelvis"),
                                    ("upper_noise_strength_0_to_1", case.upper_noise_strength, "upper")):
            if not math.isclose(row[key] / old_ranges[channel][1], value / new_ranges[channel][1], rel_tol=0, abs_tol=1e-15):
                raise RuntimeError(f"Noise-scale regeneration changed normalized noise draw {index}")
            adjusted[key] = value
        validate_sampled_case(index, case, adjusted)
    print(f"Verified all {len(cases)} setups and normalized noise draws unchanged; ranges {old_ranges} -> {new_ranges}", flush=True)
    return len(cases)


def reuse_compatible_prefix(identity, cases, bank_name, rows):
    """Copy compatible old variants losslessly; expanding must not alter snapshots."""
    if not MANIFEST_PATH.is_file():
        return 0, 0.0
    previous = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    old_identity = previous.get("source_identity", {})
    expansion_keys = {"variant_policy", "variant_block_count", "cases_per_locomotion"}
    base = lambda value: {key: item for key, item in value.items() if key not in expansion_keys}
    if base(old_identity) != base(identity) or old_identity.get("variant_policy") not in (None, identity["variant_policy"]):
        return 0, 0.0
    old_rows = previous.get("cases", [])
    if len(old_rows) >= len(cases):
        return 0, 0.0
    reused, rotation_error = 0, 0.0
    for index, old_row in enumerate(old_rows):
        case = cases[index]
        expected = {"case_index": index, "source_key": case.source_key, "init_kind": case.init_kind,
                    "noise_seed": case.noise_seed, "source_start_frame": case.source_start,
                    "gaze_normalized": list(case.gaze), "lower_noise_strength_0_to_1": case.lower_noise_strength,
                    "upper_noise_strength_0_to_1": case.upper_noise_strength,
                    "mode": "drawn" if case.mode == runtime_data.MODE_DRAWN else "sheathed"}
        if any(old_row.get(key) != value for key, value in expected.items()):
            raise RuntimeError(f"Expansion changed existing variant {index}: {case_filename(case)}")
        if case.init_kind == "attack":
            attack = old_row["attack_initializer"]
            if (attack["difficulty"], attack["attack"], attack["initialization"], attack["frame"]) != (
                case.attack_difficulty, case.attack_name, case.attack_initialization, case.attack_frame
            ):
                raise RuntimeError(f"Expansion changed attack initializer at {index}")
        if rows[index] is not None:
            continue
        with np.load(OUTPUT_ROOT / old_row["file"], allow_pickle=False) as data:
            payload = {key: data[key] for key in data.files}
        positions = payload["controller_render_global_joint_pos_m"]
        if positions.shape != (PREVIEW_FRAME_COUNT, 26, 3) or not np.isfinite(positions).all():
            raise RuntimeError(f"Invalid preserved variant {index}")
        rotation_error = max(rotation_error, validate_pose_rotations(payload["controller_render_global_rot"], old_row["file"]))
        metadata = json.loads(str(payload["defense_harness_preview_json"].item()))
        if any(metadata.get(key) != value for key, value in expected.items()):
            raise RuntimeError(f"Old NPZ/manifest mismatch at {index}")
        metadata["label"] = case_label(case)
        payload["defense_harness_preview_json"] = np.asarray(canonical_json(metadata))
        filename = f"{bank_name}/{case_filename(case)}"
        output = OUTPUT_ROOT / filename
        temporary = output.with_suffix(".tmp.npz")
        np.savez_compressed(temporary, **payload)
        temporary.replace(output)
        rows[index] = {"file": filename, **metadata}
        reused += 1
    return reused, rotation_error


def build(force: bool, device: torch.device, *, smoke_test: bool = False, batch_size: int = 64) -> dict[str, object]:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    started = time.perf_counter()
    specs = source_specs()
    if smoke_test:
        specs = specs[:2]
    print(f"Inspecting {len(specs)} locomotions / {len(specs) * CASES_PER_LOCOMOTION} variants", flush=True)
    identity = source_identity(specs)
    if not smoke_test and not force and existing_cache_hit(identity):
        print("neural locomotion preview cache: hit")
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    bank_name = "bank_" + hashlib.sha256(canonical_json(identity).encode()).hexdigest()[:16]
    bank_root = OUTPUT_ROOT / bank_name
    bank_root.mkdir(exist_ok=True)
    if device.type != "cuda":
        raise RuntimeError("Full-bank generation requires CUDA; no silent slow CPU fallback")
    wait_for_memory('sampling metadata', 3.0)
    cases = preview_cases(sampling_runtimes(specs), specs)
    preserved_sampling_count = verify_preserved_sampling(identity, cases)
    rows: list[dict[str, object] | None] = [None] * len(cases)
    attack_cache: dict[tuple, torch.Tensor] = {}
    completed = 0
    parity = []
    max_rotation_orthogonality_error = 0.0
    reused_prefix_count = 0
    if not force:
        for index, case in enumerate(cases):
            filename = f"{bank_name}/{case_filename(case)}"
            output = OUTPUT_ROOT / filename
            if output.is_file():
                with np.load(output, allow_pickle=False) as data:
                    metadata = json.loads(str(data["defense_harness_preview_json"].item()))
                    if metadata.get("case_index") != index or metadata.get("noise_seed") != case.noise_seed:
                        raise RuntimeError(f"Partial bank identity mismatch: {output}")
                    if data["controller_render_global_joint_pos_m"].shape != (PREVIEW_FRAME_COUNT, 26, 3):
                        raise RuntimeError(f"Partial bank shape mismatch: {output}")
                    max_rotation_orthogonality_error = max(max_rotation_orthogonality_error, validate_pose_rotations(data["controller_render_global_rot"], filename))
                rows[index] = {"file": filename, **metadata}
                completed += 1
        if completed:
            print(f"Reusing {completed} atomically completed variants", flush=True)
        reused_prefix_count, prefix_error = reuse_compatible_prefix(identity, cases, bank_name, rows)
        completed += reused_prefix_count
        max_rotation_orthogonality_error = max(max_rotation_orthogonality_error, prefix_error)
        if reused_prefix_count:
            print(f"Preserved {reused_prefix_count} existing variants bit-for-bit at their original indices", flush=True)
    checkpoint_hashes = {str(WALK_CHECKPOINT): identity["walk_checkpoint"]["sha256"], str(RUN_CHECKPOINT): identity["run_checkpoint"]["sha256"]}
    primer_audits = {}
    upper_agent, upper_checkpoint = load_upper_agent(device)
    for category in ("run", "walk"):
        if not any(rows[index] is None and case.category == category for index, case in enumerate(cases)):
            print(f"{category}: all saved rows verified; no policy/clip bank loaded", flush=True)
            continue
        wait_for_memory(f'loading {category}', 4.0)
        selected_specs = [spec for spec in specs if spec['category'] == category]
        print(f"Loading only {category}: {len(selected_specs)} clips (one checkpoint)", flush=True)
        runtime, lower_checkpoint = build_runtime(selected_specs[0], device, [str(spec['relative']) for spec in selected_specs])
        for mode in runtime_data.MODE_ORDER:
            selected = [(index, case) for index, case in enumerate(cases) if rows[index] is None and case.category == category and case.mode == mode]
            runner = None
            for offset in range(0, len(selected), batch_size):
                wait_for_memory(f'{category}/{mode} batch {offset}')
                batch = selected[offset:offset + batch_size]
                batch_cases = [case for _, case in batch]
                padded = batch_cases + [batch_cases[-1]] * (batch_size - len(batch_cases))
                with torch.inference_mode():
                    prepared = prepare_batch(runtime, lower_checkpoint, upper_checkpoint, padded, device, attack_cache)
                    if runner is None:
                        print(f"Capturing {category} / {'drawn' if mode == runtime_data.MODE_DRAWN else 'sheathed'} / batch {batch_size}", flush=True)
                        runner = CapturedRollout(runtime, mode, upper_agent, prepared[0], prepared[1])
                    positions, rotations = runner.rollout(*prepared)
                if offset == 0:
                    for row_index in sorted({0, len(batch_cases) - 1}):
                        reference_pos, reference_rot, _ = rollout_case(runtime, lower_checkpoint, upper_agent, upper_checkpoint, batch_cases[row_index], device)
                        position_error = float(np.max(np.abs(reference_pos - positions[row_index])))
                        rotation_error = float(np.max(np.abs(reference_rot - rotations[row_index])))
                        parity.append({"category": category, "mode": mode, "case": batch_cases[row_index].source_key,
                                       "position_max_abs_m": position_error, "rotation_max_abs": rotation_error})
                        print(f"Parity {category}/{mode}: position {position_error:.8g} m, rotation {rotation_error:.8g}", flush=True)
                        if position_error > 2e-4 or rotation_error > 5e-4:
                            raise RuntimeError(f"Batched/scalar parity failed: {parity[-1]}")
                if not np.isfinite(positions).all() or not np.isfinite(rotations).all():
                    raise RuntimeError(f"Non-finite generated poses: {category}/{mode}/{offset}")
                max_rotation_orthogonality_error = max(max_rotation_orthogonality_error, validate_pose_rotations(rotations[:len(batch)], f"{category}/{mode}/{offset}"))
                for row_index, (index, case) in enumerate(batch):
                    rows[index] = write_case(index, case, runtime, positions[row_index], rotations[row_index], bank_name, checkpoint_hashes, identity, device)
                completed += len(batch)
                elapsed = time.perf_counter() - started
                print(f"[{completed}/{len(cases)}] {elapsed:.1f}s elapsed | GPU peak {torch.cuda.max_memory_allocated()/2**30:.2f} GiB", flush=True)
            del runner
            gc.collect()
            torch.cuda.empty_cache()
        primer_audits[category] = dict(getattr(runtime, "primer_length_audit", {}))
        # Completed categories are never sampled again. Release their loaded
        # clip stores and models before the next category; no math/RNG changes.
        del lower_checkpoint
        del runtime
        gc.collect()
        torch.cuda.empty_cache()
    manifest = {"contract": PREVIEW_CONTRACT, "source_identity": identity, "case_count": len(rows),
                "cases_per_locomotion": CASES_PER_LOCOMOTION, "gaze_cases_per_locomotion": GAZE_CASES_PER_LOCOMOTION,
                "attack_cases_per_locomotion": ATTACK_CASES_PER_LOCOMOTION,
                "locomotions": [str(spec["key"]) for spec in specs], "cases": rows,
                "generation": {"seconds": time.perf_counter() - started, "batch_size": batch_size,
                               "execution": "reused single-frame CUDA graphs; batched float32 inference",
                               "peak_gpu_bytes": torch.cuda.max_memory_allocated(), "reference_parity": parity,
                               "preserved_prefix_count": reused_prefix_count,
                               "preserved_sampling_count": preserved_sampling_count,
                               "primer_length_audit": primer_audits,
                               "max_rotation_orthogonality_error": max_rotation_orthogonality_error}}
    destination = bank_root / "manifest.json" if smoke_test else MANIFEST_PATH
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return manifest


def write_case(index, case, runtime, positions, rotations, bank_name, checkpoint_hashes, identity, device):
    """Publish each finished row atomically; publish the bank manifest only after all rows pass."""
    filename = f"{bank_name}/{case_filename(case)}"
    delay = (
        (case.source_start - 1) / float(max(1, case.latest_source_start - 1))
        if case.latest_source_start > 1
        else 0.0
    )
    metadata = {
        "contract": PREVIEW_CONTRACT,
        "case_index": index,
        "label": case_label(case),
        "source_key": case.source_key,
        "source_label": case.source_label,
        "source_relative": case.relative,
        "category": case.category,
        "source_start_frame": case.source_start,
        "latest_source_start_frame": case.latest_source_start,
        "backstage_delay_normalized": delay,
        "timeline_contract": "frame_0_phase_minus_2_noisy_primer; frame_1_phase_minus_1_noisy_primer; frame_2_first_lower_then_upper_neural_prediction",
        "init_kind": case.init_kind,
        "mode": "drawn" if case.mode == runtime_data.MODE_DRAWN else "sheathed",
        "has_sword": bool(case.mode == runtime_data.MODE_DRAWN),
        "gaze_normalized": list(case.gaze),
        "lower_noise_strength_0_to_1": case.lower_noise_strength,
        "upper_noise_strength_0_to_1": case.upper_noise_strength,
        "noise_seed": case.noise_seed,
        "attack_initializer": (
            {
                "difficulty": case.attack_difficulty,
                "attack": case.attack_name,
                "initialization": case.attack_initialization,
                "frame": case.attack_frame,
                "source": str(case.attack_path),
            }
            if case.init_kind == "attack"
            else None
        ),
        "lower_checkpoint": str(case.lower_checkpoint),
        "lower_checkpoint_sha256": checkpoint_hashes[str(case.lower_checkpoint)],
        "upper_checkpoint": str(UPPER_CHECKPOINT),
        "upper_checkpoint_sha256": identity["upper_checkpoint"]["sha256"],
        "primer_noise": "one lower noise sample and one upper noise sample reused coherently on both visible primer frames",
        "primer_length_policy": PRIMER_LENGTH_POLICY,
    }
    output = OUTPUT_ROOT / filename
    clip_id = runtime.relatives.index(case.relative)
    full_clip = runtime.full_clips_by_mode[case.mode][clip_id]
    source_indices = torch.arange(
        case.source_start,
        case.source_start + PREVIEW_FRAME_COUNT,
        dtype=torch.long,
        device=device,
    )
    root_positions, root_rotations, _root_heading = runtime_data.root_state(
        runtime, source_indices, torch.full_like(source_indices, clip_id)
    )
    positions = np.concatenate(
        (root_positions.cpu().numpy().astype(np.float32, copy=False)[:, None], positions),
        axis=1,
    )
    rotations = np.concatenate(
        (root_rotations.cpu().numpy().astype(np.float32, copy=False)[:, None], rotations),
        axis=1,
    )
    parents = [-1]
    for joint, parent in enumerate(full_clip.parents_body_list):
        parents.append(0 if int(parent) < 0 and joint == 0 else int(parent) + 1)
    temporary = output.with_suffix(".tmp.npz")
    np.savez_compressed(
        temporary,
        bone_names=np.asarray(["root", *full_clip.body_names]),
        parents=np.asarray(parents, dtype=np.int32),
        fps=np.float32(full_clip.fps),
        controller_render_global_joint_pos_m=positions,
        controller_render_global_rot=rotations,
        defense_harness_preview_json=np.asarray(canonical_json(metadata)),
    )
    temporary.replace(output)
    return {"file": filename, **metadata}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Defense Harness neural locomotion previews")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--smoke-test", action="store_true", help="Validate only runB/walkF without publishing the harness manifest")
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    if sys.platform == 'win32':
        import ctypes
        kernel = ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
        kernel.SetPriorityClass.restype = ctypes.c_int
        if not kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x4000):
            raise RuntimeError('Unable to set below-normal worker priority')
    manifest = build(bool(args.force), torch.device(args.device), smoke_test=args.smoke_test, batch_size=args.batch_size)
    print(f"{'Validated smoke bank' if args.smoke_test else 'Wrote '+str(MANIFEST_PATH)} ({manifest['case_count']} cases)")


if __name__ == "__main__":
    main()
