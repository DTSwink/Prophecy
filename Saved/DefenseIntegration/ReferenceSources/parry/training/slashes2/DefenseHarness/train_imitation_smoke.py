from __future__ import annotations

"""Fixed-motion CUDA-graph smoke trainer for the new dodge imitation agents.

The supervised objective is deliberately pose-space only: direct MSE over the
cleaned 41-value lower and 90-value upper state vectors in one held authored
root frame. FK is used only for collision geometry and visualization.
"""

import argparse
import copy
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import json
import math
import os
from pathlib import Path
import random
import shutil
import sys
import time
from types import SimpleNamespace

import numpy as np
import torch

# Checkpoints produced with NumPy 2 pickle scalar constructors through the
# private ``numpy._core`` module name.  The established RunPod Torch 2.1 image
# intentionally keeps NumPy 1.24 (Torch 2.1's zero-copy NumPy bridge is not
# compatible with NumPy 2), where the same module is named ``numpy.core``.
# Alias only the serialization module names; array values and math are
# unchanged, and NumPy 2 keeps its native modules.
try:
    import numpy._core as _numpy_checkpoint_core
    import numpy._core.multiarray as _numpy_checkpoint_multiarray
except ModuleNotFoundError:
    _numpy_checkpoint_core = np.core
    _numpy_checkpoint_multiarray = np.core.multiarray
sys.modules.setdefault("numpy._core", _numpy_checkpoint_core)
sys.modules.setdefault("numpy._core.multiarray", _numpy_checkpoint_multiarray)

HERE = Path(__file__).resolve().parent
SLASHES = HERE.parent
TRAINING = SLASHES.parent
IK = TRAINING / "ik"
PARRY_DODGE = SLASHES / "ParryAndDodge"
for directory in (SLASHES, IK, PARRY_DODGE):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import ik_core as tl
import train_simple_ae_controller as ik_ctl
import train_upper_pose_autoencoder as frozen_upper_data
import train_upper_pose_controller as frozen_runtime_data
import train_upper_pose_controller_pelvis as frozen_upper_controller
import target_frame_codec
import train_slash_controller as slash2
from collision_objective import (
    DD_CONTACT_TEMPERATURE_M,
    conservative_first_contact,
    defender_obbs,
    interpolate_obb,
    load_collider_geometry,
    sat_gap,
)
from imitation_agents import CONDITION_DIM
import imitation_agents
import build_neural_locomotion_previews as neural_previews
from imitation_dataset import (
    attack_input,
    defense_conditioning,
    event_inputs,
    load_motion,
    world_attack,
    world_motion,
)
from body_mass import bone_masses_for_names


SCHEMA = "defense_imitation_mse_ccd_pin_frozen_residual_adaptive_root_v9_local_mse_tol6"
CHECKPOINT_KIND = "defense_imitation_lower_upper_frozen_residual_pin_adaptive_root_v9_local_mse_tol6"
DEFAULT_DATASET = HERE / "imitation_dataset_v2_comroot_tol6cm"
DEFAULT_RUNS = TRAINING / "runs"
DEFAULT_CCD_WEIGHT = 40.0
DEFAULT_CALF_LENGTH_WEIGHT = 4.5
DEFAULT_LOWERARM_LENGTH_WEIGHT = 4.53691442021562
DEFAULT_STEPS = 100
DEFAULT_LOG_EVERY = 100
DEFAULT_REPLAYER_EVERY = 1000
DEFAULT_CHECKPOINT_EVERY = 1000
BODY_STATE_DIM = 41 + 90
DEFAULT_PIN_LOGIT_MSE_WEIGHT = 2.0 / BODY_STATE_DIM
# Full 15k audit: the generated visible toe segment can be up to 5.052 mm
# shorter than the immutable controller offset. Direction is still exact after
# projection; allow that bounded source discrepancy and fail larger corruption.
TARGET_TOE_LENGTH_TOLERANCE_M = 6.0e-3


@dataclass
class MotionCase:
    motion_id: int
    data: dict[str, np.ndarray]
    record: dict[str, object]
    manifest: dict[str, object]
    source_path: Path
    base_data: dict[str, np.ndarray]
    base_dataset: Path


@dataclass
class SkeletonRuntime:
    runtime: SimpleNamespace
    lower_store: ik_ctl.SimpleClipStore
    lower_row_stores: tuple[ik_ctl.SimpleClipStore, ...]
    collider_geometry: object
    body_names: tuple[str, ...]
    parents: tuple[int, ...]
    mass_weights: torch.Tensor


@dataclass
class FrozenLocomotionGroup:
    rows: torch.Tensor
    runtime: frozen_runtime_data.CategoryRuntime
    clip_ids: torch.Tensor
    source_starts: torch.Tensor
    mode: float
    gaze: torch.Tensor


class AdaptiveRootStore:
    """Clip-store proxy with differentiable per-clip persistent root shifts."""

    def __init__(self, base: ik_ctl.SimpleClipStore) -> None:
        self.base = base
        self.corrections: list[tuple[torch.Tensor, torch.Tensor]] = []

    def __getattr__(self, name: str):
        return getattr(self.base, name)

    @property
    def predict_residual(self) -> bool:
        return bool(self.base.cfg.predict_residual)

    def add_correction(
        self, logical_start: torch.Tensor, correction: torch.Tensor
    ) -> None:
        if logical_start.ndim != 1 or correction.shape != (logical_start.numel(), 3):
            raise ValueError("Adaptive root corrections require one XYZ row per clip")
        self.corrections.append((logical_start, correction))

    def offset_at(self, clip_ids: torch.Tensor, indices: torch.Tensor) -> torch.Tensor:
        clip_ids = clip_ids.to(device=self.base.device, dtype=torch.long)
        indices = indices.to(device=self.base.device, dtype=torch.long)
        result = torch.zeros((indices.numel(), 3), device=self.base.device, dtype=torch.float32)
        for starts, values in self.corrections:
            selected_starts = starts.index_select(0, clip_ids)
            selected_values = values.index_select(0, clip_ids)
            result = result + (indices >= selected_starts).to(result.dtype).unsqueeze(-1) * selected_values
        return result

    def root_state(
        self, clip_ids: torch.Tensor, indices: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        position, rotation, yaw, heading = self.base.root_state(clip_ids, indices)
        return position + self.offset_at(clip_ids, indices).to(position.dtype), rotation, yaw, heading

    def get_input_root_features(
        self, clip_ids: torch.Tensor, cur_idx: torch.Tensor
    ) -> torch.Tensor:
        clip_ids = clip_ids.to(self.base.device).long()
        cur_idx = cur_idx.to(self.base.device).long()
        cyclic = self.base.cyclic.index_select(0, clip_ids)
        prev_idx = torch.where(cyclic, cur_idx - 1, (cur_idx - 1).clamp_min(0))
        prev_pos, _prev_rot, prev_yaw, prev_heading = self.root_state(clip_ids, prev_idx)
        cur_pos, _cur_rot, cur_yaw, cur_heading = self.root_state(clip_ids, cur_idx)
        delta_local = torch.matmul((cur_pos - prev_pos).unsqueeze(1), prev_heading).squeeze(1)
        root_features = torch.stack(
            (
                delta_local[:, 0] / self.base.cfg.max_speed_scale_final,
                delta_local[:, 2] / self.base.cfg.max_speed_scale_final,
                tl.wrap_angle(cur_yaw - prev_yaw) / self.base.cfg.max_turn_rate_scale_final,
            ),
            dim=-1,
        )
        steps = int(self.base.cfg.future_window)
        future_offsets = torch.arange(1, steps + 1, device=self.base.device, dtype=cur_idx.dtype)
        flat_clip_ids = clip_ids[:, None].expand(-1, steps).reshape(-1)
        flat_idx = (cur_idx[:, None] + future_offsets[None, :]).reshape(-1)
        lengths = self.base.lengths.index_select(0, flat_clip_ids).clamp_min(1)
        flat_cyclic = self.base.cyclic.index_select(0, flat_clip_ids)
        flat_idx = torch.where(flat_cyclic, flat_idx, torch.minimum(flat_idx, lengths - 1))
        future_pos, _future_rot, future_yaw, _future_heading = self.root_state(flat_clip_ids, flat_idx)
        future_pos = future_pos.reshape(cur_idx.numel(), steps, 3)
        future_yaw = future_yaw.reshape(cur_idx.numel(), steps)
        future_local = torch.matmul(
            (future_pos - cur_pos[:, None]).unsqueeze(-2), cur_heading[:, None]
        ).squeeze(-2)
        scale = future_offsets.to(future_local.dtype)[None] * self.base.cfg.max_speed_scale_final
        delta_yaw = tl.wrap_angle(future_yaw - cur_yaw[:, None])
        future_features = torch.stack(
            (
                torch.clamp(future_local[:, :, 0] / scale, -2.0, 2.0),
                torch.clamp(future_local[:, :, 2] / scale, -2.0, 2.0),
                torch.cos(delta_yaw),
                torch.sin(delta_yaw),
            ),
            dim=-1,
        ).reshape(cur_idx.numel(), steps * 4)
        return torch.cat((root_features, future_features), dim=-1).float()


class FrozenLocomotionStack:
    """Exact checkpoint stack used to author the orange locomotion bank.

    Groups are fixed for a smoke batch.  Lower policies retain gradients with
    respect to controlled feedback while all checkpoint parameters stay
    frozen.  Each lower transition goes through its checkpoint's own foot-pin
    projection before the learned lower performs the second projection.
    """

    def __init__(self, cases: list[MotionCase], device: torch.device) -> None:
        preview_manifest = json.loads(
            (HERE / "neural_preview_manifest.json").read_text(encoding="utf-8")
        )
        previews = preview_manifest["cases"]
        identities = dict(preview_manifest["source_identity"])
        expected = {
            "walk": (neural_previews.WALK_CHECKPOINT, identities["walk_checkpoint"]["sha256"]),
            "run": (neural_previews.RUN_CHECKPOINT, identities["run_checkpoint"]["sha256"]),
            "upper": (neural_previews.UPPER_CHECKPOINT, identities["upper_checkpoint"]["sha256"]),
        }
        for name, (path, digest) in expected.items():
            actual = neural_previews.file_sha256(Path(path))
            if actual.upper() != str(digest).upper():
                raise RuntimeError(
                    f"Frozen {name} checkpoint differs from dataset generation: {path}"
                )

        case_previews: list[dict[str, object]] = []
        for case in cases:
            scene = dict(case.record.get("scene", {}))
            if "locomotionIndex" not in scene:
                raise ValueError(
                    f"Motion {case.motion_id} has no locomotionIndex for frozen inference"
                )
            preview = dict(previews[int(scene["locomotionIndex"])])
            if Path(str(preview["lower_checkpoint"])).resolve() not in (
                neural_previews.WALK_CHECKPOINT.resolve(),
                neural_previews.RUN_CHECKPOINT.resolve(),
            ):
                raise RuntimeError("Dataset preview names an unaccepted lower checkpoint")
            case_previews.append(preview)

        self.upper_agent, upper_checkpoint = neural_previews.load_upper_agent(device)
        if int(upper_checkpoint.get("step", -1)) != 70750:
            raise RuntimeError("Accepted frozen upper checkpoint is not step 70750")
        self.groups: list[FrozenLocomotionGroup] = []
        grouped: dict[tuple[str, float], list[int]] = {}
        for row, (case, preview) in enumerate(zip(cases, case_previews)):
            command = np.asarray(case.data["carrier_command"], dtype=np.float32)
            carrier_mode = float(command[0])
            preview_carrier_mode = 1.0 if str(preview["mode"]) == "drawn" else 0.0
            if carrier_mode != preview_carrier_mode:
                raise RuntimeError(
                    f"Motion {case.motion_id} carrier mode differs from its frozen preview"
                )
            # The defense conditioning stores sword presence as 0/1, while the
            # accepted upper locomotion controller was trained with -1/+1.
            mode = (
                float(frozen_runtime_data.MODE_DRAWN)
                if carrier_mode > 0.5
                else float(frozen_runtime_data.MODE_SHEATHED)
            )
            grouped.setdefault((str(preview["category"]), mode), []).append(row)

        for (category, mode), rows in grouped.items():
            group_previews = [case_previews[row] for row in rows]
            relatives = [str(preview["source_relative"]) for preview in group_previews]
            spec = {
                "category": category,
                "relative": relatives[0],
                "checkpoint": (
                    neural_previews.WALK_CHECKPOINT
                    if category == "walk"
                    else neural_previews.RUN_CHECKPOINT
                ),
            }
            runtime, _checkpoint = neural_previews.build_runtime(
                spec, device, relatives
            )
            row_tensor = torch.tensor(rows, dtype=torch.long, device=device)
            group = FrozenLocomotionGroup(
                rows=row_tensor,
                runtime=runtime,
                clip_ids=torch.arange(len(rows), dtype=torch.long, device=device),
                source_starts=torch.tensor(
                    [int(preview["source_start_frame"]) for preview in group_previews],
                    dtype=torch.long,
                    device=device,
                ),
                mode=mode,
                gaze=torch.as_tensor(
                    np.stack([
                        np.asarray(cases[row].data["carrier_command"], dtype=np.float32)[1:3]
                        for row in rows
                    ]),
                    dtype=torch.float32,
                    device=device,
                ),
            )
            self._validate_authored_roots(group, cases)
            self.groups.append(group)

    @staticmethod
    @torch.no_grad()
    def _validate_authored_roots(
        group: FrozenLocomotionGroup, cases: list[MotionCase]
    ) -> None:
        runtime = group.runtime
        for local_row, global_row in enumerate(group.rows.detach().cpu().tolist()):
            case = cases[global_row]
            time_values = np.asarray(case.data["time"], dtype=np.float64)
            integer = np.isclose(time_values, np.round(time_values), atol=1.0e-9)
            indices = group.source_starts[local_row] + torch.as_tensor(
                np.round(time_values[integer]).astype(np.int64),
                device=group.source_starts.device,
            )
            clip_ids = torch.full_like(indices, local_row)
            position, rotation, _heading = frozen_runtime_data.root_state(
                runtime, indices, clip_ids
            )
            stored = np.asarray(case.base_data["root"])[integer]
            actual = torch.cat((position, rotation.reshape(-1, 9)), dim=-1).cpu().numpy()
            error = float(np.max(np.abs(actual - stored))) if actual.size else 0.0
            if error > 2.0e-5:
                raise RuntimeError(
                    f"Motion {case.motion_id} root differs from frozen source by {error:.8g}"
                )

    def propose(
        self,
        previous_lower: torch.Tensor,
        current_lower: torch.Tensor,
        previous_upper: torch.Tensor,
        current_upper: torch.Tensor,
        current_index: int,
        held_root_pos: torch.Tensor,
        held_root_rot: torch.Tensor,
        adaptive_stores: list[AdaptiveRootStore],
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        batch = int(current_lower.shape[0])
        frozen_lower = current_lower.new_zeros((batch, 41))
        frozen_upper = current_upper.new_zeros((batch, 90))
        frozen_pins = current_lower.new_zeros((batch, 2))
        if len(adaptive_stores) != len(self.groups):
            raise ValueError("One adaptive root store is required per frozen locomotion group")
        for group_index, group in enumerate(self.groups):
            runtime = group.runtime
            base_store = runtime.store
            runtime.store = adaptive_stores[group_index]
            runtime.install_policy()
            rows = group.rows
            clip_ids = group.clip_ids
            previous = previous_lower.index_select(0, rows)
            current = current_lower.index_select(0, rows)
            upper_previous = previous_upper.index_select(0, rows)
            upper_current = current_upper.index_select(0, rows)
            cur_idx = group.source_starts + int(current_index)
            try:
                payload = ik_ctl.payload_slice(runtime.store)
                controller_input = ik_ctl.build_controller_input(
                    runtime.store,
                    clip_ids,
                    cur_idx,
                    previous,
                    current,
                    previous[:, :3],
                    current[:, :3],
                    previous[:, payload],
                    current[:, payload],
                )
                raw_lower = ik_ctl.model_raw_output(
                    runtime.model, controller_input, current, runtime.store
                )
                transition, _unprojected, pin_probability = (
                    ik_ctl.clean_output_vector_pair_with_pin_prob(
                        raw_lower,
                        runtime.store,
                        current,
                        previous,
                        apply_foot_projection=True,
                    )
                )
                following, _pelvis, _payload = ik_ctl.advance_transition_state(
                    runtime.store, clip_ids, cur_idx, transition
                )

                previous_root = frozen_runtime_data.root_state(
                    runtime, cur_idx - 1, clip_ids
                )
                current_root = frozen_runtime_data.root_state(runtime, cur_idx, clip_ids)
                next_root = frozen_runtime_data.root_state(runtime, cur_idx + 1, clip_ids)
                previous_pelvis = frozen_upper_controller.pelvis_heading(
                    previous, previous_root[1], previous_root[2]
                )
                current_pelvis = frozen_upper_controller.pelvis_heading(
                    current, current_root[1], current_root[2]
                )
                next_pelvis = frozen_upper_controller.pelvis_heading(
                    following, next_root[1], next_root[2]
                )
                full_clip = runtime.full_by_mode[group.mode]
                rest = runtime.rest_offsets_by_mode[group.mode].index_select(0, clip_ids)
                current_base = frozen_runtime_data.base_upper_from_lower(
                    current, *current_root, full_clip, rest
                )
                next_base = frozen_runtime_data.base_upper_from_lower(
                    following, *next_root, full_clip, rest
                )
                upper_previous_heading = target_frame_codec.rebase_upper_state(
                    upper_previous,
                    previous_root[0],
                    previous_root[1],
                    previous_root[0],
                    previous_root[2],
                )
                upper_current_heading = target_frame_codec.rebase_upper_state(
                    upper_current,
                    current_root[0],
                    current_root[1],
                    current_root[0],
                    current_root[2],
                )
                upper_prior = frozen_upper_data.clean_upper_state(
                    next_base + upper_current_heading - current_base
                )
                current_feet = frozen_runtime_data.foot_heading_features(
                    runtime.store, current, current_root[1], current_root[2]
                )
                next_feet = frozen_runtime_data.foot_heading_features(
                    runtime.store, following, next_root[1], next_root[2]
                )
                upper_input = torch.cat(
                    (
                        upper_previous_heading,
                        upper_prior,
                        previous_pelvis,
                        current_pelvis,
                        next_pelvis,
                        runtime.store.get_input_root_features(clip_ids, cur_idx),
                        current.new_full((len(rows), 1), float(group.mode)),
                        current_feet,
                        next_feet,
                        group.gaze,
                    ),
                    dim=-1,
                )
                if int(upper_input.shape[-1]) != frozen_upper_controller.INPUT_DIM:
                    raise RuntimeError(
                        f"Frozen upper input width changed: {int(upper_input.shape[-1])}"
                    )
                upper_following = frozen_upper_data.clean_upper_state(
                    upper_prior + self.upper_agent(upper_input)
                )
                upper_following_root = frozen_runtime_data._upper_heading_state_to_root(
                    upper_following, next_root[1], next_root[2]
                )
                held_upper = target_frame_codec.rebase_upper_state(
                    upper_following_root,
                    next_root[0],
                    next_root[1],
                    held_root_pos.index_select(0, rows),
                    held_root_rot.index_select(0, rows),
                )
            finally:
                runtime.store = base_store
            frozen_lower = frozen_lower.index_copy(0, rows, transition)
            frozen_upper = frozen_upper.index_copy(0, rows, held_upper)
            frozen_pins = frozen_pins.index_copy(0, rows, pin_probability)
        return frozen_lower, frozen_upper, frozen_pins

    def new_adaptive_stores(self) -> list[AdaptiveRootStore]:
        return [AdaptiveRootStore(group.runtime.store) for group in self.groups]

    def add_root_correction(
        self,
        stores: list[AdaptiveRootStore],
        relative_frame: int,
        correction: torch.Tensor,
    ) -> None:
        for store, group in zip(stores, self.groups):
            store.add_correction(
                group.source_starts + int(relative_frame),
                correction.index_select(0, group.rows),
            )


@dataclass
class Rollout:
    mse: torch.Tensor
    pin_logit_mse_raw: torch.Tensor
    pin_logit_mse_weighted: torch.Tensor
    calf_length_raw: torch.Tensor
    calf_length_weighted: torch.Tensor
    calf_max_abs_error_m: torch.Tensor
    lowerarm_length_raw: torch.Tensor
    lowerarm_length_weighted: torch.Tensor
    lowerarm_max_abs_error_m: torch.Tensor
    ccd_raw: torch.Tensor
    ccd_weighted: torch.Tensor
    total: torch.Tensor
    frame_mse: torch.Tensor
    frame_pin_logit_mse_raw: torch.Tensor
    frame_calf_length_raw: torch.Tensor
    frame_lowerarm_length_raw: torch.Tensor
    frame_ccd_raw: torch.Tensor
    predicted_positions: torch.Tensor
    predicted_rotations: torch.Tensor
    pin_probabilities: torch.Tensor
    ccd_any_hit: torch.Tensor
    ccd_earliest_interval: torch.Tensor
    ccd_collider_index: torch.Tensor
    ccd_contact_fraction: torch.Tensor
    adaptive_root_positions: torch.Tensor
    adaptive_root_rotations: torch.Tensor


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp"
    )
    temporary.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    try:
        # On Windows, a short-lived reader (the Replayer/status poller or an
        # indexer) can temporarily deny replacement of an otherwise ordinary
        # JSON file.  Monitoring output must never terminate training.
        for attempt in range(80):
            try:
                temporary.replace(path)
                return
            except PermissionError:
                if attempt == 79:
                    print(
                        f"warning: skipped locked JSON update {path}",
                        file=sys.stderr,
                        flush=True,
                    )
                    return
                time.sleep(min(0.01 * (attempt + 1), 0.25))
    finally:
        temporary.unlink(missing_ok=True)


def load_case(dataset: Path, motion_id: int) -> MotionCase:
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != "defense_imitation_root_relative_v3":
        raise ValueError("Smoke training requires the v3 root-relative imitation dataset with pin labels")
    if not 0 <= motion_id < int(manifest["count"]):
        raise ValueError(f"motion id {motion_id} is outside the dataset")
    motion = load_motion(dataset / "motions" / f"{motion_id:05d}.npz")
    record = json.loads((dataset / "records" / f"{motion_id:05d}.json").read_text(encoding="utf-8"))
    preview_manifest = json.loads((HERE / "neural_preview_manifest.json").read_text(encoding="utf-8"))
    locomotion_index = int(dict(record["scene"])["locomotionIndex"])
    preview = dict(preview_manifest["cases"][locomotion_index])
    relative = Path(str(preview["source_relative"]))
    source = SLASHES / "walk_run_sword_prep" / "holding_sword_npz" / relative
    if not source.is_file():
        raise FileNotFoundError(f"Authored geometry source is missing: {source}")
    root_retargeting = manifest.get("root_retargeting")
    if root_retargeting:
        base_dataset = Path(str(root_retargeting["source_dataset"]))
        if not base_dataset.is_absolute():
            base_dataset = (dataset.parent / base_dataset).resolve()
        base_data = load_motion(base_dataset / "motions" / f"{motion_id:05d}.npz")
        if not np.array_equal(base_data["time"], motion["time"]):
            raise ValueError("COM-root copy and base motion have different frame timing")
    else:
        base_dataset = dataset
        base_data = motion
    return MotionCase(
        motion_id, motion, record, manifest, source, base_data, base_dataset
    )


def build_skeleton(cases: MotionCase | list[MotionCase], device: torch.device) -> SkeletonRuntime:
    rows = [cases] if isinstance(cases, MotionCase) else list(cases)
    if not rows:
        raise ValueError("At least one motion is required to build the skeleton runtime")
    cfg = tl.TrainConfig()
    slash2.configure_frozen_free_motion_cfg(cfg)
    cfg.device = str(device)
    cfg.use_torch_compile = False
    lower_clips = [
        tl.MotionClip(case.source_path, cfg, cyclic_animation=False)
        for case in rows
    ]
    full_cfg = copy.deepcopy(cfg)
    full_cfg.body_mode = tl.BODY_MODE_FULL
    full_clips = [
        tl.MotionClip(case.source_path, full_cfg, cyclic_animation=False)
        for case in rows
    ]
    body_names = tuple(str(value) for value in rows[0].manifest["bone_names"])
    parents = tuple(int(value) for value in rows[0].manifest["parents"])
    for case, lower_clip, full_clip in zip(rows, lower_clips, full_clips):
        case_names = tuple(str(value) for value in case.manifest["bone_names"])
        case_parents = tuple(int(value) for value in case.manifest["parents"])
        if case_names != body_names or case_parents != parents:
            raise ValueError("Imitation motions do not share one skeleton topology")
        if tuple(lower_clip.body_names) != body_names or tuple(full_clip.body_names) != body_names:
            raise ValueError("Dataset and authored geometry skeleton names differ")
        if tuple(lower_clip.parents_body_list) != parents:
            raise ValueError("Dataset and authored geometry parent trees differ")
    lower_row_stores = tuple(
        ik_ctl.SimpleClipStore([clip], cfg, device) for clip in lower_clips
    )
    lower_store = slash2.stack_lower_projection_store(
        lower_row_stores[0], list(lower_row_stores)
    )
    runtime = SimpleNamespace(
        lower_clip=lower_clips[0],
        full_clip=full_clips[0],
        lower_fk_geometry=slash2.stack_fk_geometry(lower_clips, device),
        full_fk_geometry=slash2.stack_fk_geometry(full_clips, device),
        attacks=None,
    )
    geometry = load_collider_geometry(list(body_names)).to(device)
    mass_weights = torch.as_tensor(
        bone_masses_for_names(list(body_names)), dtype=torch.float32, device=device
    )
    return SkeletonRuntime(
        runtime, lower_store, lower_row_stores, geometry, body_names, parents,
        mass_weights,
    )


def _toe_float(
    foot_rotation: torch.Tensor,
    toe_rotation: torch.Tensor,
    axis: torch.Tensor,
) -> torch.Tensor:
    local = toe_rotation @ foot_rotation.transpose(-1, -2)
    axis = axis.expand(local.shape[0], -1)
    reference = tl.stable_perpendicular(axis)
    rotated = torch.matmul(reference.unsqueeze(-2), local).squeeze(-2)
    rotated = tl.project_to_plane(rotated, axis)
    sine = (torch.cross(reference, rotated, dim=-1) * axis).sum(dim=-1)
    cosine = (reference * rotated).sum(dim=-1)
    return (torch.atan2(sine, cosine) / float(tl.IK_TOE_ALPHA)).clamp(-1.0, 1.0)


def body_to_agent_states(
    data: dict[str, np.ndarray],
    skeleton: SkeletonRuntime,
    device: torch.device,
    geometry_row: int = 0,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Encode stored root-local labels directly; no FK participates."""

    body = torch.as_tensor(data["body"], dtype=torch.float32, device=device)
    positions = body[..., :3]
    rotations = tl.rotation_6d_to_matrix(body[..., 3:])
    by_name = {name: index for index, name in enumerate(skeleton.body_names)}

    pelvis = by_name["pelvis"]
    lower_parts = [positions[:, pelvis], tl.rotmat_to_6d(rotations[:, pelvis])]
    payload = positions.new_zeros((positions.shape[0], skeleton.runtime.lower_clip.ik_payload_dim))
    if not 0 <= int(geometry_row) < len(skeleton.lower_row_stores):
        raise IndexError(f"geometry row {geometry_row} is outside the runtime")
    toe_axes = skeleton.runtime.lower_fk_geometry["ik_toe_axis"][geometry_row]
    toe_offsets = skeleton.runtime.lower_fk_geometry["ik_toe_offsets"][geometry_row]
    for limb, spec in enumerate(skeleton.runtime.lower_clip.ik_payload_slices):
        start = int(spec["start"])
        end = int(spec["end"])
        toe = int(spec["toe"])
        toe_delta = positions[:, toe] - positions[:, end]
        expected_length = torch.linalg.vector_norm(toe_offsets[limb])
        length_error = (
            torch.linalg.vector_norm(toe_delta, dim=-1) - expected_length
        ).abs().max()
        if float(length_error.detach().cpu()) > TARGET_TOE_LENGTH_TOLERANCE_M:
            raise ValueError(
                f"{spec['side']} toe offset is not representable: "
                f"length error {float(length_error.detach().cpu()):.8g} m"
            )
        # Controlled harness frames can carry a foot basis whose fixed toe
        # offset points to the opposite side of the visible toe. Fit the
        # smallest foot rotation that preserves the endpoint instead of
        # silently teaching a 180-degree inversion in the native 41-D target.
        end_rotation = tl.rotation_from_axis_with_reference(
            toe_offsets[limb], toe_delta, rotations[:, end]
        )
        payload[:, spec["pos"]] = positions[:, end]
        payload[:, spec["rot6"]] = tl.rotmat_to_6d(end_rotation)
        payload[:, spec["start_rot6"]] = tl.rotmat_to_6d(rotations[:, start])
        payload[:, spec["toe_float"]] = _toe_float(
            end_rotation, rotations[:, toe], toe_axes[limb]
        )[:, None]
    lower = torch.cat((*lower_parts, payload), dim=-1)
    lower = ik_ctl.clean_output_vector(
        lower, skeleton.lower_row_stores[geometry_row]
    )
    if lower.shape[-1] != 41:
        raise RuntimeError(f"lower target width {lower.shape[-1]} != 41")

    core: list[torch.Tensor] = []
    for name in slash2.CORE_BONES:
        joint = by_name[name]
        parent = skeleton.parents[joint]
        local = rotations[:, joint] @ rotations[:, parent].transpose(-1, -2)
        core.append(tl.rotmat_to_6d(local))
    upper_parts: list[torch.Tensor] = [torch.cat(core, dim=-1)]
    for _side, upper_name, _lower_name, hand_name in slash2.ARM_SPECS:
        upper = by_name[upper_name]
        hand = by_name[hand_name]
        upper_parts.extend(
            (positions[:, hand], tl.rotmat_to_6d(rotations[:, hand]), tl.rotmat_to_6d(rotations[:, upper]))
        )
    upper = slash2.clean_upper_state(torch.cat(upper_parts, dim=-1))
    if upper.shape[-1] != 90:
        raise RuntimeError(f"upper target width {upper.shape[-1]} != 90")
    return lower, upper


def _held_target(
    lower: torch.Tensor,
    upper: torch.Tensor,
    skeleton: SkeletonRuntime,
    from_root_pos: torch.Tensor,
    from_root_rot: torch.Tensor,
    to_root_pos: torch.Tensor,
    to_root_rot: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    return (
        target_frame_codec.rebase_lower_state(
            skeleton.lower_store, lower, from_root_pos, from_root_rot, to_root_pos, to_root_rot
        ),
        target_frame_codec.rebase_upper_state(
            upper, from_root_pos, from_root_rot, to_root_pos, to_root_rot
        ),
    )


def root_relative_pose_mse_frames(
    predicted_lower: torch.Tensor,
    predicted_upper: torch.Tensor,
    wanted_lower: torch.Tensor,
    wanted_upper: torch.Tensor,
) -> torch.Tensor:
    """Compare matching pose coordinates in their respective held-root frames.

    The prediction is encoded in the live adaptive-root frame, while the target
    is encoded in the corresponding authored-root frame.  Comparing those
    coordinates directly keeps pose supervision invariant to a rigid adaptive
    root translation.
    """

    if predicted_lower.shape != wanted_lower.shape:
        raise ValueError(
            f"Lower relative-pose shapes differ: {predicted_lower.shape} != {wanted_lower.shape}"
        )
    if predicted_upper.shape != wanted_upper.shape:
        raise ValueError(
            f"Upper relative-pose shapes differ: {predicted_upper.shape} != {wanted_upper.shape}"
        )
    return (
        (predicted_lower - wanted_lower).square().sum(dim=-1)
        + (predicted_upper - wanted_upper).square().sum(dim=-1)
    ) / BODY_STATE_DIM


def _decode(
    skeleton: SkeletonRuntime,
    lower: torch.Tensor,
    upper: torch.Tensor,
    root_pos: torch.Tensor,
    root_rot: torch.Tensor,
    clip_ids: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    if clip_ids.shape != (lower.shape[0],):
        raise ValueError(
            f"FK clip ids must have shape {(lower.shape[0],)}, got {tuple(clip_ids.shape)}"
        )
    return slash2.full_fk_globals(
        skeleton.runtime, clip_ids, lower, upper, root_pos, root_rot
    )


def adaptive_root_correction(
    center_of_mass: torch.Tensor,
    provisional_root: torch.Tensor,
    tolerance_m: float,
) -> torch.Tensor:
    delta = center_of_mass - provisional_root
    planar = torch.stack((delta[:, 0], torch.zeros_like(delta[:, 1]), delta[:, 2]), dim=-1)
    distance = torch.linalg.vector_norm(planar, dim=-1, keepdim=True)
    amount = torch.clamp(distance - float(tolerance_m), min=0.0)
    return torch.where(
        distance > 1.0e-8,
        planar * (amount / distance.clamp_min(1.0e-8)),
        torch.zeros_like(planar),
    )


def heading_from_root_rotation(root_rotation: torch.Tensor) -> torch.Tensor:
    forward = -root_rotation[:, 1]
    yaw = torch.atan2(forward[:, 0], forward[:, 2])
    cosine, sine = torch.cos(yaw), torch.sin(yaw)
    zero, one = torch.zeros_like(cosine), torch.ones_like(cosine)
    return torch.stack(
        (
            torch.stack((cosine, zero, sine), dim=-1),
            torch.stack((zero, one, zero), dim=-1),
            torch.stack((-sine, zero, cosine), dim=-1),
        ),
        dim=-2,
    )


def cumulative_root_shift_in_current_root(
    cumulative_shift: torch.Tensor,
    current_root_rotation: torch.Tensor,
) -> torch.Tensor:
    """Express the persistent world-space root displacement in the live root.

    The displacement is accumulated in world space.  Re-projecting the total
    every frame keeps the feature meaningful when the authored root turns.
    """

    return torch.matmul(
        cumulative_shift.unsqueeze(1),
        current_root_rotation.transpose(-1, -2),
    ).squeeze(1)


def adaptive_conditioning_frame(
    base_conditioning: torch.Tensor,
    cumulative_shift: torch.Tensor,
    adaptive_previous_root: torch.Tensor,
    adaptive_current_root: torch.Tensor,
    previous_root_rotation: torch.Tensor,
    current_root_rotation: torch.Tensor,
    cumulative_shift_local: torch.Tensor | None = None,
) -> torch.Tensor:
    """Rebase causal geometry and current root delta into the live root.

    The future route remains unchanged relative to current because the current
    cumulative shift is applied identically to every projected future root.
    Sticky target/type inputs retain the authored COM-root copy contract.
    """

    result = base_conditioning.clone()
    local_shift = (
        cumulative_root_shift_in_current_root(
            cumulative_shift, current_root_rotation
        )
        if cumulative_shift_local is None
        else cumulative_shift_local
    )
    spear = result[:, -1] >= 0.5
    # pelvis current/end (0, 9) and attack collider current/end (18, 27)
    for start in (0, 9):
        shifted = result[:, start : start + 3] - local_shift
        result[:, start : start + 3] = torch.where(
            spear[:, None], torch.zeros_like(shifted), shifted
        )
    for start in (18, 27):
        result[:, start : start + 3] = result[:, start : start + 3] - local_shift
    previous_heading = heading_from_root_rotation(previous_root_rotation)
    current_delta = torch.matmul(
        (adaptive_current_root - adaptive_previous_root).unsqueeze(1), previous_heading
    ).squeeze(1)
    result[:, 37] = current_delta[:, 0] / (5.0 / 30.0)
    result[:, 38] = current_delta[:, 2] / (5.0 / 30.0)
    return result


def ccd_avoid_loss(
    centers: torch.Tensor,
    axes: torch.Tensor,
    attack_centers: torch.Tensor,
    attack_axes: torch.Tensor,
    attack_half: torch.Tensor,
    geometry,
    valid_intervals: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Existing DD rule: only the earliest colliding interval contributes."""

    intervals = int(centers.shape[0]) - 1
    zero = centers.new_zeros(())
    if intervals <= 0:
        return (
            zero,
            centers.new_zeros((0,)),
            torch.tensor(False, device=centers.device),
            torch.tensor(0, device=centers.device),
            torch.tensor(0, device=centers.device),
            zero,
        )
    count = geometry.count
    defender_half = geometry.half_sizes_m[None].expand(intervals, -1, -1)
    defender_radius = geometry.radii_m[None].expand(intervals, -1)
    defender_offset = geometry.center_offsets_local[None].expand(intervals, -1, -1)
    attacker_half = attack_half[None].expand(intervals, -1)
    attacker_radius = torch.linalg.norm(attacker_half, dim=-1)
    attacker_offset = torch.zeros_like(attack_centers[:-1])
    first = conservative_first_contact(
        centers[:-1], axes[:-1], centers[1:], axes[1:],
        defender_half, defender_radius,
        attack_centers[:-1], attack_axes[:-1], attack_centers[1:], attack_axes[1:],
        attacker_half, attacker_radius,
        defender_center_offset_local=defender_offset,
        attacker_center_offset_local=attacker_offset,
    )
    rows = torch.arange(intervals, device=centers.device)
    selected = first.collider_index
    event_time = first.time.clamp(0.0, 1.0).detach()
    dc, da = interpolate_obb(
        centers[:-1][rows, selected], axes[:-1][rows, selected],
        centers[1:][rows, selected], axes[1:][rows, selected],
        event_time, defender_offset[rows, selected],
    )
    ac, aa = interpolate_obb(
        attack_centers[:-1], attack_axes[:-1], attack_centers[1:], attack_axes[1:],
        event_time, attacker_offset,
    )
    gap = sat_gap(dc, da, defender_half[rows, selected], ac, aa, attacker_half)
    continuous = torch.nn.functional.softplus(-gap / DD_CONTACT_TEMPERATURE_M) * DD_CONTACT_TEMPERATURE_M
    effective_hit = first.hit
    if valid_intervals is not None:
        if valid_intervals.shape != first.hit.shape:
            raise ValueError(
                f"CCD validity shape {tuple(valid_intervals.shape)} != {tuple(first.hit.shape)}"
            )
        effective_hit = effective_hit & valid_intervals
    penalties = torch.where(effective_hit.detach(), continuous, torch.zeros_like(continuous))
    any_hit = effective_hit.any()
    earliest = effective_hit.to(torch.int64).argmax()
    gather_index = earliest.reshape(1, 1)
    selected_penalty = penalties.reshape(1, intervals).gather(1, gather_index).reshape(())
    selected_collider = selected.reshape(1, intervals).gather(1, gather_index).reshape(())
    selected_fraction = event_time.reshape(1, intervals).gather(1, gather_index).reshape(())
    selected_penalty = torch.where(any_hit, selected_penalty, zero)
    frame_rows = torch.where(
        effective_hit & (rows == earliest), penalties, torch.zeros_like(penalties)
    )
    return (
        selected_penalty,
        frame_rows,
        any_hit,
        earliest,
        selected_collider,
        selected_fraction,
    )


def calf_length_error_frames(
    skeleton: SkeletonRuntime,
    positions: torch.Tensor,
    clip_ids: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Symmetric authored calf-length error for every motion/frame.

    Feet are explicit lower-body targets, so their knee-to-ankle segment is not
    structurally fixed by FK.  Penalize shortening and stretching identically.
    """

    leg_limbs = [
        (limb, spec)
        for limb, spec in enumerate(skeleton.runtime.full_clip.ik_limb_specs)
        if str(spec["kind"]) == "leg"
    ]
    if len(leg_limbs) != 2:
        raise ValueError(f"Expected two leg IK chains, got {len(leg_limbs)}")
    actual = torch.stack(
        [
            torch.linalg.vector_norm(
                positions[:, :, int(spec["end"])]
                - positions[:, :, int(spec["mid"])],
                dim=-1,
            )
            for _limb, spec in leg_limbs
        ],
        dim=-1,
    )
    geometry = slash2.select_fk_geometry(
        skeleton.runtime.full_fk_geometry, clip_ids
    )
    # Python-integer slices avoid constructing/copying an index tensor while
    # this helper is captured inside the persistent CUDA graph.
    authored = torch.stack(
        [
            geometry["ik_limb_lengths"][:, limb, 1]
            for limb, _spec in leg_limbs
        ],
        dim=-1,
    )
    error = actual - authored[:, None]
    return error.square().mean(dim=-1), error.abs().amax(dim=-1)


def lowerarm_length_error_frames(
    skeleton: SkeletonRuntime,
    positions: torch.Tensor,
    clip_ids: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Exact Slash2 symmetric elbow-to-wrist authored-length objective."""

    arm_limbs = [
        (limb, spec)
        for limb, spec in enumerate(skeleton.runtime.full_clip.ik_limb_specs)
        if str(spec["kind"]) == "arm"
    ]
    if len(arm_limbs) != 2:
        raise ValueError(f"Expected two arm IK chains, got {len(arm_limbs)}")
    actual = torch.stack(
        [
            torch.linalg.vector_norm(
                positions[:, :, int(spec["end"])]
                - positions[:, :, int(spec["mid"])],
                dim=-1,
            )
            for _limb, spec in arm_limbs
        ],
        dim=-1,
    )
    geometry = slash2.select_fk_geometry(
        skeleton.runtime.full_fk_geometry, clip_ids
    )
    authored = torch.stack(
        [
            geometry["ik_limb_lengths"][:, limb, 1]
            for limb, _spec in arm_limbs
        ],
        dim=-1,
    )
    error = actual - authored[:, None]
    return error.square().mean(dim=-1), error.abs().amax(dim=-1)


def pin_logit_mse_frames(
    pin_commands: torch.Tensor,
    pin_targets: torch.Tensor,
) -> torch.Tensor:
    """Direct left/right binary-label MSE on the lower agent's raw pin outputs."""

    if pin_commands.shape != pin_targets.shape or pin_commands.shape[-1] != 2:
        raise ValueError("Pin-logit MSE requires matching [..., left/right] tensors")
    return (pin_commands - pin_targets).square().mean(dim=-1)


def paired_base_upper_with_globals(
    skeleton: SkeletonRuntime,
    clip_ids: torch.Tensor,
    current_lower: torch.Tensor,
    next_lower: torch.Tensor,
    zero_root: torch.Tensor,
    identity_root: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Decode both lower states in one exact batched FK invocation.

    The original rollout decoded ``next_lower`` once to build the upper prior
    and a second time inside the full-body decoder.  Returning its local FK
    tensors lets the full-body pass reuse that identical result.
    """

    batch_size = int(current_lower.shape[0])
    paired_ids = torch.cat((clip_ids, clip_ids), dim=0)
    paired_zero = torch.cat((zero_root, zero_root), dim=0)
    paired_identity = torch.cat((identity_root, identity_root), dim=0)
    paired_positions, paired_rotations = slash2.lower_fk_globals(
        skeleton.runtime,
        paired_ids,
        torch.cat((current_lower, next_lower), dim=0),
        paired_zero,
        paired_identity,
    )
    paired_upper = slash2.upper_state_from_globals(
        skeleton.runtime.full_clip,
        paired_positions,
        paired_rotations,
        paired_zero,
        paired_identity,
    )
    return (
        paired_upper[:batch_size],
        paired_upper[batch_size:],
        paired_positions[batch_size:],
        paired_rotations[batch_size:],
    )


def rollout(
    lower_agent: torch.nn.Module,
    upper_agent: torch.nn.Module,
    frame_counts: tuple[int, ...],
    skeleton: SkeletonRuntime,
    target_lower: torch.Tensor,
    target_upper: torch.Tensor,
    target_pin: torch.Tensor,
    conditioning: torch.Tensor,
    roots_pos: torch.Tensor,
    roots_rot: torch.Tensor,
    base_roots_pos: torch.Tensor,
    base_roots_rot: torch.Tensor,
    target_world_com: torch.Tensor,
    attack_centers: torch.Tensor,
    attack_axes: torch.Tensor,
    attack_half: torch.Tensor,
    valid_frames: torch.Tensor,
    ccd_weight: float,
    calf_length_weight: float,
    lowerarm_length_weight: float,
    pin_logit_mse_weight: float,
    adaptive_root_tolerance_m: float,
    frozen_stack: FrozenLocomotionStack | None = None,
) -> Rollout:
    if frozen_stack is None:
        raise RuntimeError(
            "FrozenLocomotionStack is mandatory for the v6 adaptive-root residual contract"
        )
    device = target_lower.device
    previous_lower = target_lower[:, 0]
    previous_upper = target_upper[:, 0]
    current_lower = target_lower[:, 1]
    current_upper = target_upper[:, 1]
    predicted_positions: list[torch.Tensor] = []
    predicted_rotations: list[torch.Tensor] = []
    frame_mse: list[torch.Tensor] = []
    frame_pin_logit_mse: list[torch.Tensor] = []
    pin_rows: list[torch.Tensor] = []
    batch_size = int(target_lower.shape[0])
    frame_count = int(target_lower.shape[1])
    clip_ids = torch.arange(batch_size, dtype=torch.long, device=device)
    zero_root = roots_pos.new_zeros((batch_size, 3))
    identity_root = torch.eye(3, dtype=roots_rot.dtype, device=device)[None].expand(batch_size, -1, -1)
    mass_weights = skeleton.mass_weights
    adaptive_stores = frozen_stack.new_adaptive_stores()
    adaptive_previous_root = base_roots_pos[:, 0]
    primer_center = target_world_com[:, 1]
    current_correction = adaptive_root_correction(
        primer_center, base_roots_pos[:, 1], adaptive_root_tolerance_m
    )
    cumulative_shift = current_correction
    adaptive_current_root = base_roots_pos[:, 1] + cumulative_shift
    frozen_stack.add_root_correction(adaptive_stores, 1, current_correction)
    adaptive_root_rows: list[torch.Tensor] = [
        adaptive_previous_root, adaptive_current_root
    ]

    for current_index in range(1, frame_count - 1):
        next_index = current_index + 1
        held_root_pos = adaptive_current_root
        held_root_rot = base_roots_rot[:, current_index]
        held_previous_lower, held_previous_upper = _held_target(
            previous_lower,
            previous_upper,
            skeleton,
            adaptive_previous_root,
            base_roots_rot[:, current_index - 1],
            held_root_pos,
            held_root_rot,
        )
        frozen_lower, frozen_upper, _frozen_pins = frozen_stack.propose(
            previous_lower,
            current_lower,
            previous_upper,
            current_upper,
            current_index,
            held_root_pos,
            held_root_rot,
            adaptive_stores,
        )
        cumulative_shift_local = cumulative_root_shift_in_current_root(
            cumulative_shift, base_roots_rot[:, current_index]
        )
        live_conditioning = adaptive_conditioning_frame(
            conditioning[:, current_index],
            cumulative_shift,
            adaptive_previous_root,
            adaptive_current_root,
            base_roots_rot[:, current_index - 1],
            base_roots_rot[:, current_index],
            cumulative_shift_local,
        )
        lower_input = imitation_agents.build_lower_input(
            current_lower,
            frozen_lower,
            live_conditioning,
            cumulative_shift_local,
        )
        lower_output, lower_gates = lower_agent(lower_input)
        if lower_gates is not None:
            raise RuntimeError("Lower imitation agent unexpectedly emitted gates")
        lower_delta, pin_commands = slash2.split_lower_output(lower_output)
        frame_pin_logit_mse.append(
            pin_logit_mse_frames(pin_commands, target_pin[:, current_index])
        )
        next_lower, pins = slash2.clean_lower_delta(
            skeleton.runtime, skeleton.lower_store, current_lower, frozen_lower,
            lower_delta, pin_commands,
        )
        (
            frozen_base,
            controlled_base,
            next_lower_positions,
            next_lower_rotations,
        ) = paired_base_upper_with_globals(
            skeleton,
            clip_ids,
            frozen_lower,
            next_lower,
            zero_root,
            identity_root,
        )
        next_prior = slash2.carry_upper_hybrid_deviation(
            frozen_upper, frozen_base, controlled_base
        )
        upper_input = imitation_agents.build_upper_input(
            held_previous_upper,
            next_prior,
            held_previous_lower,
            current_lower,
            next_lower,
            live_conditioning,
            cumulative_shift_local,
        )
        upper_output, upper_gates = upper_agent(upper_input)
        if upper_gates is not None:
            raise RuntimeError("Upper imitation agent unexpectedly emitted gates")
        next_upper = slash2.clean_upper_state(imitation_agents.apply_upper_output(next_prior, upper_output))

        wanted_lower, wanted_upper = _held_target(
            target_lower[:, next_index], target_upper[:, next_index], skeleton,
            roots_pos[:, next_index], roots_rot[:, next_index],
            roots_pos[:, current_index], roots_rot[:, current_index],
        )
        frame_mse.append(
            root_relative_pose_mse_frames(
                next_lower,
                next_upper,
                wanted_lower,
                wanted_upper,
            )
        )
        frozen_positions = (
            torch.matmul(next_lower_positions.unsqueeze(-2), held_root_rot[:, None])
            .squeeze(-2)
            + held_root_pos[:, None]
        )
        frozen_rotations = next_lower_rotations @ held_root_rot[:, None]
        positions, rotations = slash2.full_fk_globals(
            skeleton.runtime,
            clip_ids,
            next_lower,
            next_upper,
            held_root_pos,
            held_root_rot,
            frozen_pos=frozen_positions,
            frozen_rot=frozen_rotations,
        )
        predicted_positions.append(positions)
        predicted_rotations.append(rotations)
        pin_rows.append(pins)

        center = (positions * mass_weights[None, :, None]).sum(dim=1)
        provisional_next_root = base_roots_pos[:, next_index] + cumulative_shift
        next_correction = adaptive_root_correction(
            center, provisional_next_root, adaptive_root_tolerance_m
        )
        next_cumulative_shift = cumulative_shift + next_correction
        adaptive_next_root = base_roots_pos[:, next_index] + next_cumulative_shift
        frozen_stack.add_root_correction(adaptive_stores, next_index, next_correction)
        adaptive_root_rows.append(adaptive_next_root)

        if next_index < frame_count - 1:
            next_native_lower, next_native_upper = _held_target(
                next_lower, next_upper, skeleton,
                held_root_pos, held_root_rot,
                adaptive_next_root, base_roots_rot[:, next_index],
            )
            previous_lower, previous_upper = current_lower, current_upper
            current_lower, current_upper = next_native_lower, next_native_upper
        adaptive_previous_root = adaptive_current_root
        adaptive_current_root = adaptive_next_root
        cumulative_shift = next_cumulative_shift
        current_correction = next_correction

    positions = torch.stack(predicted_positions, dim=1)
    rotations = torch.stack(predicted_rotations, dim=1)
    adaptive_roots = torch.stack(adaptive_root_rows, dim=1)
    frame_mse_tensor = torch.stack(frame_mse, dim=1)
    frame_pin_logit_mse_tensor = torch.stack(frame_pin_logit_mse, dim=1)
    predicted_mask = valid_frames[:, 2:].to(dtype=frame_mse_tensor.dtype)
    per_motion_mse = (frame_mse_tensor * predicted_mask).sum(dim=1) / predicted_mask.sum(dim=1).clamp_min(1.0)
    mse = per_motion_mse.mean()
    per_motion_pin_logit_mse = (
        (frame_pin_logit_mse_tensor * predicted_mask).sum(dim=1)
        / predicted_mask.sum(dim=1).clamp_min(1.0)
    )
    pin_logit_mse_raw = per_motion_pin_logit_mse.mean()
    pin_logit_mse_weighted = pin_logit_mse_raw * float(pin_logit_mse_weight)
    frame_calf_raw, frame_calf_max = calf_length_error_frames(
        skeleton, positions, clip_ids
    )
    per_motion_calf = (
        (frame_calf_raw * predicted_mask).sum(dim=1)
        / predicted_mask.sum(dim=1).clamp_min(1.0)
    )
    calf_length_raw = per_motion_calf.mean()
    calf_length_weighted = calf_length_raw * float(calf_length_weight)
    calf_max_abs_error_m = torch.where(
        valid_frames[:, 2:], frame_calf_max, torch.zeros_like(frame_calf_max)
    ).amax()
    frame_lowerarm_raw, frame_lowerarm_max = lowerarm_length_error_frames(
        skeleton, positions, clip_ids
    )
    per_motion_lowerarm = (
        (frame_lowerarm_raw * predicted_mask).sum(dim=1)
        / predicted_mask.sum(dim=1).clamp_min(1.0)
    )
    lowerarm_length_raw = per_motion_lowerarm.mean()
    lowerarm_length_weighted = lowerarm_length_raw * float(lowerarm_length_weight)
    lowerarm_max_abs_error_m = torch.where(
        valid_frames[:, 2:], frame_lowerarm_max, torch.zeros_like(frame_lowerarm_max)
    ).amax()
    defender_centers, defender_axes = defender_obbs(positions, rotations, skeleton.collider_geometry)
    ccd_rows: list[torch.Tensor] = []
    frame_ccd_rows: list[torch.Tensor] = []
    any_hit_rows: list[torch.Tensor] = []
    earliest_rows: list[torch.Tensor] = []
    collider_rows: list[torch.Tensor] = []
    fraction_rows: list[torch.Tensor] = []
    maximum_intervals = max(0, frame_count - 3)
    for row, _count in enumerate(frame_counts):
        # Always evaluate the one fixed padded shape. Invalid tail intervals are
        # masked after contact detection, so CUDA graphs can replay across
        # variable-length dataset batches without teaching from inert padding.
        predicted_count = int(positions.shape[1])
        result = ccd_avoid_loss(
            defender_centers[row, :predicted_count],
            defender_axes[row, :predicted_count],
            attack_centers[row, 2 : 2 + predicted_count],
            attack_axes[row, 2 : 2 + predicted_count],
            attack_half[row],
            skeleton.collider_geometry,
            valid_frames[row, 2 : 2 + predicted_count - 1]
            & valid_frames[row, 3 : 3 + predicted_count - 1],
        )
        ccd_rows.append(result[0])
        frame_ccd_rows.append(torch.nn.functional.pad(result[1], (0, maximum_intervals - int(result[1].numel()))))
        any_hit_rows.append(result[2])
        earliest_rows.append(result[3])
        collider_rows.append(result[4])
        fraction_rows.append(result[5])
    ccd_raw = torch.stack(ccd_rows).mean()
    frame_ccd = torch.stack(frame_ccd_rows)
    any_hit = torch.stack(any_hit_rows)
    earliest = torch.stack(earliest_rows)
    collider = torch.stack(collider_rows)
    contact_fraction = torch.stack(fraction_rows)
    ccd_weighted = ccd_raw * float(ccd_weight)
    return Rollout(
        mse, pin_logit_mse_raw, pin_logit_mse_weighted,
        calf_length_raw, calf_length_weighted, calf_max_abs_error_m,
        lowerarm_length_raw, lowerarm_length_weighted, lowerarm_max_abs_error_m,
        ccd_raw, ccd_weighted,
        mse + pin_logit_mse_weighted + calf_length_weighted
        + lowerarm_length_weighted + ccd_weighted,
        frame_mse_tensor, frame_pin_logit_mse_tensor,
        frame_calf_raw, frame_lowerarm_raw, frame_ccd, positions, rotations,
        torch.stack(pin_rows, dim=1), any_hit, earliest, collider, contact_fraction,
        adaptive_roots, base_roots_rot,
    )


def select_motion_rollout(
    result: Rollout,
    row: int,
    frame_count: int,
    ccd_weight: float,
    calf_length_weight: float,
    lowerarm_length_weight: float,
    pin_logit_mse_weight: float,
) -> Rollout:
    predicted_count = max(0, int(frame_count) - 2)
    interval_count = max(0, predicted_count - 1)
    frame_mse = result.frame_mse[row, :predicted_count]
    frame_pin_logit_mse = result.frame_pin_logit_mse_raw[row, :predicted_count]
    frame_calf_raw = result.frame_calf_length_raw[row, :predicted_count]
    frame_lowerarm_raw = result.frame_lowerarm_length_raw[row, :predicted_count]
    frame_ccd = result.frame_ccd_raw[row, :interval_count]
    mse = frame_mse.mean()
    pin_logit_mse_raw = frame_pin_logit_mse.mean()
    pin_logit_mse_weighted = pin_logit_mse_raw * float(pin_logit_mse_weight)
    calf_length_raw = frame_calf_raw.mean()
    calf_length_weighted = calf_length_raw * float(calf_length_weight)
    calf_max_abs_error_m = result.calf_max_abs_error_m
    lowerarm_length_raw = frame_lowerarm_raw.mean()
    lowerarm_length_weighted = lowerarm_length_raw * float(lowerarm_length_weight)
    lowerarm_max_abs_error_m = result.lowerarm_max_abs_error_m
    ccd_raw = frame_ccd.sum()
    ccd_weighted = ccd_raw * float(ccd_weight)
    return Rollout(
        mse,
        pin_logit_mse_raw,
        pin_logit_mse_weighted,
        calf_length_raw,
        calf_length_weighted,
        calf_max_abs_error_m,
        lowerarm_length_raw,
        lowerarm_length_weighted,
        lowerarm_max_abs_error_m,
        ccd_raw,
        ccd_weighted,
        mse + pin_logit_mse_weighted + calf_length_weighted
        + lowerarm_length_weighted + ccd_weighted,
        frame_mse,
        frame_pin_logit_mse,
        frame_calf_raw,
        frame_lowerarm_raw,
        frame_ccd,
        result.predicted_positions[row, :predicted_count],
        result.predicted_rotations[row, :predicted_count],
        result.pin_probabilities[row, :predicted_count],
        result.ccd_any_hit[row],
        result.ccd_earliest_interval[row],
        result.ccd_collider_index[row],
        result.ccd_contact_fraction[row],
        result.adaptive_root_positions[row, :frame_count],
        result.adaptive_root_rotations[row, :frame_count],
    )


def replayer_payload(
    result: Rollout,
    case: MotionCase,
    skeleton: SkeletonRuntime,
    target_lower: torch.Tensor,
    target_upper: torch.Tensor,
    target_pin: torch.Tensor,
    roots_pos: torch.Tensor,
    roots_rot: torch.Tensor,
    step: int,
    ccd_weight: float,
    calf_length_weight: float,
    lowerarm_length_weight: float,
    pin_logit_mse_weight: float,
    run_id: str,
    geometry_row: int,
) -> dict[str, object]:
    data = case.data
    # This is the exact cleaned native-state MSE label decoded only for display.
    # FK does not participate in the supervised loss.
    authored_target_positions, authored_target_rotations = _decode(
        skeleton,
        target_lower,
        target_upper,
        roots_pos,
        roots_rot,
        torch.full(
            (target_lower.shape[0],),
            int(geometry_row),
            dtype=torch.long,
            device=target_lower.device,
        ),
    )
    # Predicted frame n is supervised against the authored frame-n pose in the
    # authored frame-(n-1) root coordinates. Decode that local label beneath
    # adaptive root n-1 so the dashed target visualizes the relative objective.
    mse_target_lower, mse_target_upper = _held_target(
        target_lower[2:],
        target_upper[2:],
        skeleton,
        roots_pos[2:],
        roots_rot[2:],
        roots_pos[1:-1],
        roots_rot[1:-1],
    )
    predicted_count = int(mse_target_lower.shape[0])
    mse_predicted_positions, mse_predicted_rotations = _decode(
        skeleton,
        mse_target_lower,
        mse_target_upper,
        result.adaptive_root_positions[1:-1],
        result.adaptive_root_rotations[1:-1],
        torch.full(
            (predicted_count,),
            int(geometry_row),
            dtype=torch.long,
            device=target_lower.device,
        ),
    )
    mse_target_positions = torch.cat(
        (authored_target_positions[:2], mse_predicted_positions)
    )
    mse_target_rotations = torch.cat(
        (authored_target_rotations[:2], mse_predicted_rotations)
    )
    positions = torch.cat(
        (
            authored_target_positions[:2],
            result.predicted_positions,
        )
    )
    rotations = torch.cat(
        (
            authored_target_rotations[:2],
            result.predicted_rotations,
        )
    )
    defender_centers, defender_axes = defender_obbs(positions, rotations, skeleton.collider_geometry)
    attack_pos_np, attack_rot_np = world_attack(data)
    frame_count = int(positions.shape[0])
    frame_losses = torch.zeros((frame_count, 6), dtype=positions.dtype, device=positions.device)
    frame_losses[2:, 0] = result.frame_mse
    frame_losses[2:, 1] = result.frame_pin_logit_mse_raw * float(pin_logit_mse_weight)
    frame_losses[2:, 2] = result.frame_calf_length_raw * float(calf_length_weight)
    frame_losses[2:, 3] = result.frame_lowerarm_length_raw * float(lowerarm_length_weight)
    if int(result.frame_ccd_raw.numel()) > 0:
        frame_losses[3:, 4] = result.frame_ccd_raw * float(ccd_weight)
    frame_losses[:, 5] = frame_losses[:, :5].sum(dim=-1)
    contact_flags = [False] * frame_count
    contact_names: list[str | None] = [None] * frame_count
    contact_record: dict[str, object] | None = None
    if bool(result.ccd_any_hit.detach().cpu()) and frame_count > 3:
        interval = int(result.ccd_earliest_interval.detach().cpu())
        display_frame = min(frame_count - 1, 3 + interval)
        collider_index = int(result.ccd_collider_index.detach().cpu())
        fraction = float(result.ccd_contact_fraction.detach().cpu())
        interval_start = 2 + interval
        interval_end = interval_start + 1
        interval_times = np.asarray(data["time"], dtype=np.float64)
        absolute_time = float(
            interval_times[interval_start]
            + fraction * (interval_times[interval_end] - interval_times[interval_start])
        )
        contact_flags[display_frame] = True
        contact_names[display_frame] = skeleton.collider_geometry.names[collider_index]
        contact_record = {
            "phase": "ccd",
            "collider_name": skeleton.collider_geometry.names[collider_index],
            "absolute_time": absolute_time,
            "absolute_interval": [
                float(interval_times[interval_start]),
                float(interval_times[interval_end]),
            ],
            "display_frame": display_frame,
        }
    roots = data["root"]
    authored_root_pos = roots[:, :3].tolist()
    authored_root_rot = roots[:, 3:].reshape(-1, 3, 3).tolist()
    adaptive_root_pos = result.adaptive_root_positions.detach().cpu().tolist()
    adaptive_root_rot = result.adaptive_root_rotations.detach().cpu().tolist()
    hit = event_inputs(data)[:, 0].tolist()
    scene = dict(case.record["scene"])
    body_bones = [[parent, index] for index, parent in enumerate(skeleton.parents) if parent >= 0]
    payload = {
        "schema_version": 2,
        "computed_at": datetime.now().astimezone().isoformat(),
        "run_id": run_id,
        "step": int(step),
        "fps": 30.0,
        "joint_names": list(skeleton.body_names),
        "bones": body_bones,
        "rows": [{
            "row": 0,
            "clip_id": case.motion_id,
            "clip_name": f"dataset motion {case.motion_id:05d}",
            "start": 0,
            "effective_k": frame_count - 1,
            "virtual": False,
            "noisy": True,
            "noisy_seed_source": "dataset_primer",
            "attack_seed": case.motion_id,
            "attack_name": scene["attack"],
            "sample_index": scene["sampleIndex"],
        }],
        "positions": [positions.detach().cpu().tolist()],
        "basis": [rotations.detach().cpu().tolist()],
        "mse_target_positions": [mse_target_positions.detach().cpu().tolist()],
        "mse_target_basis": [mse_target_rotations.detach().cpu().tolist()],
        "controller_root_pos": [adaptive_root_pos],
        "controller_root_rot": [adaptive_root_rot],
        "authored_root_pos": [authored_root_pos],
        "authored_root_rot": [authored_root_rot],
        "frozen_root_pos": [authored_root_pos],
        "frozen_root_rot": [authored_root_rot],
        "source_frame": [data["time"].tolist()],
        "source_clip_name": [[str(scene["attack"])] * frame_count],
        "armed_latch": [[0.0, 0.0, *([1.0] * max(0, frame_count - 2))]],
        "hit_latch": [hit],
        "ccd_active": [[False, False, *([True] * max(0, frame_count - 2))]],
        "ccd_detected": [bool(result.ccd_any_hit.detach().cpu())],
        "ccd_collider": [contact_names[next((i for i, value in enumerate(contact_flags) if value), 0)]],
        "weighted_loss_names": [
            "mse", "pin_logit_mse", "calf_length", "lowerarm_length", "ccd", "total"
        ],
        "weighted_loss_terms": [frame_losses.detach().cpu().tolist()],
        "weighted_loss_rollout_totals": [[
            float(result.mse.detach().cpu()),
            float(result.pin_logit_mse_weighted.detach().cpu()),
            float(result.calf_length_weighted.detach().cpu()),
            float(result.lowerarm_length_weighted.detach().cpu()),
            float(result.ccd_weighted.detach().cpu()),
            float(result.total.detach().cpu()),
        ]],
        "controlled_pin_probabilities": [[
            [0.0, 0.0], [0.0, 0.0], *result.pin_probabilities.detach().cpu().tolist()
        ]],
        # A command emitted during transition t->t+1 is displayed on its
        # resulting pose frame t+1, just like controlled_pin_probabilities.
        "target_pin_labels": [[
            [0.0, 0.0], [0.0, 0.0],
            *target_pin[1:-1].detach().cpu().tolist(),
        ]],
        "paired_colliders": {
            "names": list(skeleton.collider_geometry.names),
            "half_sizes_m": skeleton.collider_geometry.half_sizes_m.detach().cpu().tolist(),
            "centers_m": defender_centers.detach().cpu().tolist(),
            "axes": defender_axes.detach().cpu().tolist(),
            "attacker_half_size_m": data["attack_half"].tolist(),
            "attacker_centers_m": attack_pos_np.tolist(),
            "attacker_axes": attack_rot_np.tolist(),
            "contact_flags": contact_flags,
            "contact_names": contact_names,
            "contact": contact_record,
        },
        "metadata": {
            "body_mode": "full",
            "checkpoint_kind": CHECKPOINT_KIND,
            "controller_kind": "dd",
            "capture_source": "read_only_exact_policy_rollout",
            "source_contract": "live adaptive-root rollout; direct pose MSE between corresponding live/authored root-local frames; FK only for CCD and display",
            "adaptive_root": True,
            "learned_root_shift_input": "cumulative world correction expressed in the current adaptive-root frame",
            "dual_root_markers": {
                "adaptive": "controller_root_pos",
                "authored_com_root": "authored_root_pos",
            },
            "mse_target_visualization": "cleaned native lower41+upper90 local label decoded under the live adaptive root for display only",
            "calf_length_contract": "symmetric squared knee-to-ankle error from per-motion authored length",
            "calf_length_weight": float(calf_length_weight),
            "lowerarm_length_contract": "symmetric squared elbow-to-wrist error from per-motion authored length",
            "lowerarm_length_weight": float(lowerarm_length_weight),
            "pin_logit_mse_contract": "binary AE3 transition labels supervised directly on raw lower pin commands",
            "pin_logit_mse_weight": float(pin_logit_mse_weight),
            "mode": "drawn" if float(data["carrier_command"][0]) >= 0.5 else "sheathed",
            "has_sword": bool(float(data["carrier_command"][0]) >= 0.5),
        },
        "message": f"Fixed-motion imitation batch · pose/pin MSE + calf/lowerarm length + CCD · dataset #{case.motion_id:05d}",
    }
    return payload


def export_replayer(
    run_dir: Path,
    payload: dict[str, object],
    step: int,
    motion_id: int,
    *,
    primary: bool,
) -> None:
    output = run_dir / "replayer"
    output.mkdir(parents=True, exist_ok=True)
    atomic_json(output / f"dd_step_{step:08d}_motion_{motion_id:05d}.json", payload)
    atomic_json(output / f"dd_motion_{motion_id:05d}_latest.json", payload)
    if primary:
        atomic_json(output / f"dd_step_{step:08d}.json", payload)
        atomic_json(output / "dd_latest.json", payload)
        source = (PARRY_DODGE / "paired_replayer.html").read_text(encoding="utf-8")
        (output / "index.html").write_text(
            source.replace("__DATA_FILE__", "dd_latest.json"), encoding="utf-8"
        )


def export_batch_replayers(
    run_dir: Path,
    result: Rollout,
    cases: list[MotionCase],
    skeleton: SkeletonRuntime,
    lower_targets: torch.Tensor,
    upper_targets: torch.Tensor,
    pin_targets: torch.Tensor,
    roots_pos: torch.Tensor,
    roots_rot: torch.Tensor,
    step: int,
    ccd_weight: float,
    calf_length_weight: float,
    lowerarm_length_weight: float,
    pin_logit_mse_weight: float,
    run_id: str,
    *,
    write_individual_files: bool = True,
) -> None:
    payloads: list[dict[str, object]] = []
    for row, case in enumerate(cases):
        frame_count = len(case.data["time"])
        selected = select_motion_rollout(
            result, row, frame_count, ccd_weight, calf_length_weight,
            lowerarm_length_weight, pin_logit_mse_weight,
        )
        payload = replayer_payload(
            selected,
            case,
            skeleton,
            lower_targets[row, :frame_count],
            upper_targets[row, :frame_count],
            pin_targets[row, :frame_count],
            roots_pos[row, :frame_count],
            roots_rot[row, :frame_count],
            step,
            ccd_weight,
            calf_length_weight,
            lowerarm_length_weight,
            pin_logit_mse_weight,
            run_id,
            row,
        )
        payloads.append(payload)
        if write_individual_files:
            export_replayer(
                run_dir, payload, step, case.motion_id, primary=False
            )
    combined = copy.deepcopy(payloads[0])
    row_fields = (
        "rows",
        "positions",
        "basis",
        "mse_target_positions",
        "mse_target_basis",
        "controller_root_pos",
        "controller_root_rot",
        "authored_root_pos",
        "authored_root_rot",
        "frozen_root_pos",
        "frozen_root_rot",
        "source_frame",
        "source_clip_name",
        "armed_latch",
        "hit_latch",
        "ccd_active",
        "ccd_detected",
        "ccd_collider",
        "weighted_loss_terms",
        "weighted_loss_rollout_totals",
        "controlled_pin_probabilities",
        "target_pin_labels",
    )
    for field in row_fields:
        combined[field] = [value for payload in payloads for value in payload[field]]
    for row, metadata in enumerate(combined["rows"]):
        metadata["row"] = row
    combined["paired_colliders_by_row"] = [payload["paired_colliders"] for payload in payloads]
    combined["message"] = f"Fixed-motion imitation batch · {len(payloads)} Replayer rows"
    output = run_dir / "replayer"
    atomic_json(output / f"dd_step_{step:08d}.json", combined)
    atomic_json(output / "dd_latest.json", combined)
    source = (PARRY_DODGE / "paired_replayer.html").read_text(encoding="utf-8")
    (output / "index.html").write_text(
        source.replace("__DATA_FILE__", "dd_latest.json"), encoding="utf-8"
    )


def save_checkpoint(
    run_dir: Path,
    lower: torch.nn.Module,
    upper: torch.nn.Module,
    optimizer: torch.optim.Optimizer,
    step: int,
    cases: list[MotionCase],
    ccd_weight: float,
    calf_length_weight: float,
    lowerarm_length_weight: float,
    pin_logit_mse_weight: float,
    dataset: Path,
    adaptive_root_tolerance_cm: float,
) -> Path:
    path = run_dir / "checkpoints" / f"step_{step:08d}.pt"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    torch.save({
        "kind": CHECKPOINT_KIND,
        "schema": SCHEMA,
        "step": int(step),
        "motion_ids": [case.motion_id for case in cases],
        "dataset": str(dataset.resolve()),
        "adaptive_root": {
            "enabled": True,
            "tolerance_cm": float(adaptive_root_tolerance_cm),
            "mse_reference": "corresponding live/authored root-local frames; invariant to adaptive-root world translation",
            "learned_input": "cumulative world correction expressed in the current adaptive-root frame",
            "learned_input_dim": imitation_agents.ROOT_SHIFT_INPUT_DIM,
        },
        "conditioning_dim": CONDITION_DIM,
        "lower_input_dim": imitation_agents.LOWER_INPUT_DIM,
        "upper_input_dim": imitation_agents.UPPER_INPUT_DIM,
        "frozen_locomotion": {
            "order": "frozen_lower_pin_then_frozen_upper_then_learned_lower_pin_then_learned_upper",
            "walk_checkpoint": str(neural_previews.WALK_CHECKPOINT.resolve()),
            "run_checkpoint": str(neural_previews.RUN_CHECKPOINT.resolve()),
            "upper_checkpoint": str(neural_previews.UPPER_CHECKPOINT.resolve()),
            "upper_checkpoint_step": 70750,
            "foot_pin_passes": 2,
        },
        "lower": lower.state_dict(),
        "upper": upper.state_dict(),
        "optimizer": optimizer.state_dict(),
        "loss": {
            "mse": "direct_corresponding_root_local_lower41_upper90_full_motion",
            "calf_length": "symmetric_squared_knee_to_ankle_authored_length_error",
            "calf_length_weight": float(calf_length_weight),
            "lowerarm_length": "symmetric_squared_elbow_to_wrist_authored_length_error",
            "lowerarm_length_weight": float(lowerarm_length_weight),
            "pin_logit_mse": "binary_AE3_transition_labels_vs_raw_lower_pin_commands",
            "pin_logit_mse_weight": float(pin_logit_mse_weight),
            "ccd_weight": float(ccd_weight),
        },
    }, temporary)
    temporary.replace(path)
    latest = path.parent / "latest.pt"
    shutil.copyfile(path, latest)
    return path


def prepare_tensors(
    case: MotionCase,
    skeleton: SkeletonRuntime,
    device: torch.device,
    geometry_row: int,
):
    data = case.data
    lower, upper = body_to_agent_states(data, skeleton, device, geometry_row)
    if "pin" not in data:
        raise ValueError(f"Dataset motion {case.motion_id} lacks v3 pin labels")
    pin_targets = torch.as_tensor(data["pin"], dtype=torch.float32, device=device)
    conditioning_rows = []
    for frame in range(len(data["time"])):
        if not 1 <= frame < len(data["time"]) - 1:
            conditioning_rows.append(
                torch.zeros((CONDITION_DIM,), dtype=torch.float32, device=device)
            )
            continue
        # Geometry/root-route terms start from the unshifted locomotion bank;
        # sticky target and attack type retain the COM-root copy's contract.
        row = np.asarray(defense_conditioning(case.base_data, frame)).copy()
        row[-9:] = attack_input(data)
        conditioning_rows.append(
            torch.as_tensor(row, dtype=torch.float32, device=device)
        )
    conditioning = torch.stack(conditioning_rows)
    roots_pos = torch.as_tensor(data["root"][:, :3], dtype=torch.float32, device=device)
    roots_rot = torch.as_tensor(data["root"][:, 3:].reshape(-1, 3, 3), dtype=torch.float32, device=device)
    base_roots_pos = torch.as_tensor(
        case.base_data["root"][:, :3], dtype=torch.float32, device=device
    )
    base_roots_rot = torch.as_tensor(
        case.base_data["root"][:, 3:].reshape(-1, 3, 3),
        dtype=torch.float32,
        device=device,
    )
    target_world, _target_world_rot = world_motion(data)
    target_world_com = torch.as_tensor(
        (target_world[:, 1:] * skeleton.mass_weights.detach().cpu().numpy()[None, :, None]).sum(axis=1),
        dtype=torch.float32,
        device=device,
    )
    attack_pos, attack_rot = world_attack(data)
    attack_centers = torch.as_tensor(attack_pos, dtype=torch.float32, device=device)
    attack_axes = torch.as_tensor(attack_rot, dtype=torch.float32, device=device)
    attack_half = torch.as_tensor(data["attack_half"], dtype=torch.float32, device=device)
    return (
        lower, upper, pin_targets, conditioning, roots_pos, roots_rot,
        base_roots_pos, base_roots_rot, target_world_com,
        attack_centers, attack_axes, attack_half,
    )


def prepare_batch_tensors(
    cases: list[MotionCase], skeleton: SkeletonRuntime, device: torch.device
) -> tuple[tuple[int, ...], tuple[torch.Tensor, ...]]:
    """Stack variable-length motions, repeating only their inert padded tails."""

    rows = [
        prepare_tensors(case, skeleton, device, row)
        for row, case in enumerate(cases)
    ]
    frame_counts = tuple(len(case.data["time"]) for case in cases)
    maximum = max(frame_counts)

    def pad_time(value: torch.Tensor, count: int) -> torch.Tensor:
        if count == maximum:
            return value
        tail = value[-1:].expand(maximum - count, *value.shape[1:])
        return torch.cat((value, tail), dim=0)

    stacked: list[torch.Tensor] = []
    for field in range(11):
        stacked.append(torch.stack([
            pad_time(row[field], count) for row, count in zip(rows, frame_counts)
        ]))
    stacked.append(torch.stack([row[11] for row in rows]))
    valid_frames = torch.arange(maximum, device=device)[None] < torch.tensor(
        frame_counts, dtype=torch.long, device=device
    )[:, None]
    stacked.append(valid_frames)
    return frame_counts, tuple(stacked)


def reset_after_warmup(
    modules: tuple[torch.nn.Module, ...],
    originals: list[torch.Tensor],
    optimizer: torch.optim.Optimizer,
) -> None:
    with torch.no_grad():
        for parameter, original in zip((p for module in modules for p in module.parameters()), originals):
            parameter.copy_(original)
        for state in optimizer.state.values():
            for value in state.values():
                if torch.is_tensor(value):
                    value.zero_()
    optimizer.zero_grad(set_to_none=False)


def compile_training_hot_regions(
    lower: torch.nn.Module,
    upper: torch.nn.Module,
) -> object:
    """Fuse the repeated agent/FK regions before outer CUDA-graph capture."""

    compiled_fk = torch.compile(
        slash2._slash_fast_fk_globals_fixed,
        fullgraph=True,
        dynamic=False,
        options=slash2.FAST_COMPILE_OPTIONS,
    )
    lower.forward = torch.compile(
        lower.forward,
        fullgraph=True,
        dynamic=False,
        options=slash2.FAST_COMPILE_OPTIONS,
    )
    upper.forward = torch.compile(
        upper.forward,
        fullgraph=True,
        dynamic=False,
        options=slash2.FAST_COMPILE_OPTIONS,
    )
    return compiled_fk


@contextmanager
def temporary_fk_dispatcher(dispatcher: object):
    """Use the fixed-shape compiled FK only where its shape contract holds."""

    previous = slash2.slash_fast_fk_globals
    slash2.slash_fast_fk_globals = dispatcher
    try:
        yield
    finally:
        slash2.slash_fast_fk_globals = previous


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--motion-id", type=int)
    parser.add_argument("--motion-ids", type=str)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--resume-checkpoint", type=Path)
    parser.add_argument("--seed", type=int, default=20260901)
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS)
    parser.add_argument("--ccd-weight", type=float, default=DEFAULT_CCD_WEIGHT)
    parser.add_argument(
        "--calf-length-weight", type=float, default=DEFAULT_CALF_LENGTH_WEIGHT
    )
    parser.add_argument(
        "--lowerarm-length-weight",
        type=float,
        default=DEFAULT_LOWERARM_LENGTH_WEIGHT,
    )
    parser.add_argument(
        "--pin-logit-mse-weight",
        type=float,
        default=DEFAULT_PIN_LOGIT_MSE_WEIGHT,
    )
    parser.add_argument("--learning-rate", type=float, default=1.0e-4)
    parser.add_argument("--decay-step", type=int, default=200)
    parser.add_argument("--final-learning-rate", type=float, default=1.0e-5)
    parser.add_argument("--grad-clip-norm", type=float, default=1.0)
    parser.add_argument(
        "--adaptive-root-tolerance-cm",
        type=float,
        help="Live horizontal COM deadzone; defaults to the derived dataset contract.",
    )
    parser.add_argument("--log-every", type=int, default=DEFAULT_LOG_EVERY)
    parser.add_argument(
        "--replayer-every", type=int, default=DEFAULT_REPLAYER_EVERY
    )
    parser.add_argument(
        "--checkpoint-every", type=int, default=DEFAULT_CHECKPOINT_EVERY
    )
    parser.add_argument(
        "--no-compile",
        action="store_true",
        help="Disable the loss-equivalent compiled agent/FK hot regions.",
    )
    parser.add_argument("--run-name", type=str)
    parser.add_argument("--runs-root", type=Path, default=DEFAULT_RUNS)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("The smoke contract requires CUDA; there is no eager CPU fallback")
    # Match the accepted Slash2 numerical contract explicitly.  Enabling TF32
    # would be faster but changes the pose/FK arithmetic and is not lossless.
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    if (
        args.steps < 1
        or (args.batch_size is not None and args.batch_size < 1)
        or args.log_every < 1
        or args.replayer_every < 1
        or args.checkpoint_every < 1
        or args.ccd_weight < 0
        or args.calf_length_weight < 0
        or args.lowerarm_length_weight < 0
        or args.pin_logit_mse_weight < 0
        or args.learning_rate <= 0
        or args.final_learning_rate <= 0
        or args.decay_step < 0
        or args.grad_clip_norm <= 0
        or (
            args.adaptive_root_tolerance_cm is not None
            and args.adaptive_root_tolerance_cm < 0
        )
    ):
        raise ValueError(
            "steps/cadences/rates/clip must be positive and loss weights nonnegative"
        )
    if args.motion_id is not None and args.motion_ids is not None:
        raise ValueError("Use either --motion-id or --motion-ids, not both")
    progress = json.loads((args.dataset / "progress.json").read_text(encoding="utf-8"))
    if progress.get("state") != "complete" or int(progress.get("accepted", -1)) != int(progress.get("count", -2)):
        raise RuntimeError("Imitation dataset is not complete")
    count = int(progress["accepted"])
    resume_checkpoint = None
    if args.resume_checkpoint is not None:
        resume_path = args.resume_checkpoint.resolve()
        resume_checkpoint = torch.load(resume_path, map_location="cpu")
        if (
            resume_checkpoint.get("schema") != SCHEMA
            or resume_checkpoint.get("kind") != CHECKPOINT_KIND
        ):
            raise ValueError(
                "The checkpoint does not match the relative-MSE adaptive-root contract "
                "and cannot be resumed"
            )
        motion_ids = [int(value) for value in resume_checkpoint["motion_ids"]]
        batch_size = len(motion_ids)
        if args.batch_size is not None and int(args.batch_size) != batch_size:
            raise ValueError(
                f"Resume checkpoint has batch {batch_size}, requested {args.batch_size}"
            )
    elif args.motion_ids is not None:
        motion_ids = [int(value.strip()) for value in args.motion_ids.split(",") if value.strip()]
        batch_size = int(args.batch_size) if args.batch_size is not None else len(motion_ids)
    elif args.motion_id is not None:
        motion_ids = [int(args.motion_id)]
        batch_size = int(args.batch_size) if args.batch_size is not None else 1
    else:
        batch_size = int(args.batch_size) if args.batch_size is not None else 1
        motion_ids = random.Random(args.seed).sample(range(count), batch_size)
    if len(motion_ids) != batch_size:
        raise ValueError(f"Expected {batch_size} motion ids, got {len(motion_ids)}")
    if len(set(motion_ids)) != len(motion_ids):
        raise ValueError("Fixed-motion batches require distinct motion ids")
    cases = [load_case(args.dataset.resolve(), motion_id) for motion_id in motion_ids]
    if any(not case.manifest.get("root_retargeting") for case in cases):
        raise ValueError(
            "Adaptive-root v6 smoke training requires the authored COM-root dataset copy"
        )
    dataset_tolerances = {
        float(dict(case.manifest["root_retargeting"])["tolerance_cm"])
        for case in cases
    }
    if len(dataset_tolerances) != 1:
        raise ValueError("Smoke batch mixes incompatible COM-root tolerances")
    dataset_tolerance_cm = next(iter(dataset_tolerances))
    adaptive_root_tolerance_cm = (
        dataset_tolerance_cm
        if args.adaptive_root_tolerance_cm is None
        else float(args.adaptive_root_tolerance_cm)
    )
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    device = torch.device("cuda")
    skeleton = build_skeleton(cases, device)
    frozen_stack = FrozenLocomotionStack(cases, device)
    frame_counts, tensors = prepare_batch_tensors(cases, skeleton, device)
    recipe = slash2.Recipe(batch_size=batch_size, learning_rate=float(args.learning_rate))
    lower, upper = imitation_agents.create_agents(recipe)
    lower.to(device).train()
    upper.to(device).train()
    compiled_fk = None
    if not args.no_compile:
        compiled_fk = compile_training_hot_regions(lower, upper)
    training_fk = (
        compiled_fk if compiled_fk is not None else slash2.slash_fast_fk_globals
    )
    parameters = [*lower.parameters(), *upper.parameters()]
    learning_rate = torch.tensor(float(args.learning_rate), dtype=torch.float32, device=device)
    optimizer = torch.optim.AdamW(
        parameters, lr=learning_rate,
        weight_decay=0.0, capturable=True,
    )
    start_step = 0
    if resume_checkpoint is not None:
        lower.load_state_dict(resume_checkpoint["lower"])
        upper.load_state_dict(resume_checkpoint["upper"])
        optimizer.load_state_dict(resume_checkpoint["optimizer"])
        start_step = int(resume_checkpoint["step"])
        loaded_lr = optimizer.param_groups[0]["lr"]
        if not torch.is_tensor(loaded_lr):
            loaded_lr = torch.tensor(float(loaded_lr), dtype=torch.float32, device=device)
            optimizer.param_groups[0]["lr"] = loaded_lr
        learning_rate = loaded_lr
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if resume_checkpoint is not None:
        run_dir = args.resume_checkpoint.resolve().parent.parent
        run_id = run_dir.name
    else:
        run_id = args.run_name or f"{timestamp}_dd_imitation_{len(cases)}motions_bs{batch_size}_mseccd"
        run_dir = args.runs_root.resolve() / run_id
        if run_dir.exists():
            raise FileExistsError(run_dir)
        (run_dir / "debug").mkdir(parents=True)
    config = {
        "schema": SCHEMA,
        "run_id": run_id,
        "dataset": str(args.dataset.resolve()),
        "motion_ids": motion_ids,
        "frame_counts": list(frame_counts),
        "batch_size": batch_size,
        "constant_motions": True,
        "adaptive_root": {
            "enabled": True,
            "base_dataset": str(cases[0].base_dataset.resolve()),
            "tolerance_cm": adaptive_root_tolerance_cm,
            "correction": "horizontal COM deadzone, current and all projected future roots",
            "frozen_observation": "live adaptive root and shifted future-root trajectory",
            "learned_observation": "live adaptive root plus cumulative world correction expressed in current-root space",
            "learned_shift_input_dim": imitation_agents.ROOT_SHIFT_INPUT_DIM,
        },
        "steps": int(args.steps),
        "seed": int(args.seed),
        "learning_rate": float(args.learning_rate),
        "learning_rate_schedule": {
            "initial": float(args.learning_rate),
            "initial_steps": int(args.decay_step),
            "final": float(args.final_learning_rate),
        },
        "grad_clip_norm": float(args.grad_clip_norm),
        "performance": {
            "torch_compile_hot_regions": not bool(args.no_compile),
            "outer_cuda_graph": True,
            "precision": "float32_tf32_disabled_no_amp",
            "single_batched_current_next_lower_fk": True,
            "reuse_next_lower_fk_in_full_decode": True,
            "log_every": int(args.log_every),
            "replayer_every": int(args.replayer_every),
            "checkpoint_every": int(args.checkpoint_every),
        },
        "frozen_locomotion": {
            "order": "frozen_lower_pin_then_frozen_upper_then_learned_lower_pin_then_learned_upper",
            "lower_walk_checkpoint": str(neural_previews.WALK_CHECKPOINT.resolve()),
            "lower_run_checkpoint": str(neural_previews.RUN_CHECKPOINT.resolve()),
            "upper_checkpoint": str(neural_previews.UPPER_CHECKPOINT.resolve()),
            "upper_checkpoint_step": 70750,
            "foot_pin_passes": 2,
        },
        "loss": {
            "mse": "direct lower41+upper90 pose comparison in corresponding live/authored root-local frames",
            "fk_mse": False,
            "representable_foot_targets": True,
            "per_motion_fk_geometry": True,
            "calf_length": "symmetric_squared_knee_to_ankle_authored_length_error",
            "calf_length_weight": float(args.calf_length_weight),
            "lowerarm_length": "symmetric_squared_elbow_to_wrist_authored_length_error",
            "lowerarm_length_weight": float(args.lowerarm_length_weight),
            "pin_logit_mse": "binary_AE3_transition_labels_vs_raw_lower_pin_commands",
            "pin_logit_mse_weight": float(args.pin_logit_mse_weight),
            "pin_label_detector": "legacy_AE3_sole_horizontal_displacement_le_11p5mm_no_height_gate",
            "ccd_weight": float(args.ccd_weight),
        },
        "conditioning_dim": CONDITION_DIM,
        "lower_input_dim": imitation_agents.LOWER_INPUT_DIM,
        "upper_input_dim": imitation_agents.UPPER_INPUT_DIM,
        "source_geometry": [str(case.source_path) for case in cases],
        "scenes": [case.record["scene"] for case in cases],
    }
    atomic_json(run_dir / "config.json", config)
    print(
        f"IMITATION_SMOKE run={run_id} motions={motion_ids} frames={list(frame_counts)} "
        f"batch={batch_size} resume_step={start_step}",
        flush=True,
    )

    (
        lower_targets,
        upper_targets,
        pin_targets,
        conditioning,
        roots_pos,
        roots_rot,
        base_roots_pos,
        base_roots_rot,
        target_world_com,
        attack_centers,
        attack_axes,
        attack_half,
        valid_frames,
    ) = tensors
    call = lambda: rollout(
        lower, upper, frame_counts, skeleton, lower_targets, upper_targets,
        pin_targets, conditioning,
        roots_pos, roots_rot,
        base_roots_pos, base_roots_rot, target_world_com,
        attack_centers, attack_axes, attack_half, valid_frames,
        float(args.ccd_weight), float(args.calf_length_weight),
        float(args.lowerarm_length_weight),
        float(args.pin_logit_mse_weight),
        adaptive_root_tolerance_cm * 0.01,
        frozen_stack=frozen_stack,
    )
    lower.eval(); upper.eval()
    with temporary_fk_dispatcher(training_fk), torch.no_grad():
        initial = call()
    export_batch_replayers(
        run_dir, initial, cases, skeleton, lower_targets, upper_targets, pin_targets,
        roots_pos, roots_rot, start_step, args.ccd_weight,
        args.calf_length_weight, args.lowerarm_length_weight,
        args.pin_logit_mse_weight, run_id,
    )
    del initial
    lower.train(); upper.train()

    originals = [parameter.detach().clone() for module in (lower, upper) for parameter in module.parameters()]
    optimizer_snapshot = copy.deepcopy(optimizer.state_dict()) if resume_checkpoint is not None else None
    warmup_stream = torch.cuda.Stream()
    warmup_stream.wait_stream(torch.cuda.current_stream())
    with temporary_fk_dispatcher(training_fk):
        with torch.cuda.stream(warmup_stream):
            for _ in range(3):
                optimizer.zero_grad(set_to_none=False)
                warmup_result = call()
                warmup_result.total.backward()
                optimizer.step()
        torch.cuda.current_stream().wait_stream(warmup_stream)
        torch.cuda.synchronize()
        del warmup_result
        if optimizer_snapshot is None:
            reset_after_warmup((lower, upper), originals, optimizer)
        else:
            with torch.no_grad():
                for parameter, original in zip(
                    (p for module in (lower, upper) for p in module.parameters()), originals
                ):
                    parameter.copy_(original)
            optimizer.load_state_dict(optimizer_snapshot)
            optimizer.zero_grad(set_to_none=False)
            learning_rate = optimizer.param_groups[0]["lr"]
        del originals, optimizer_snapshot
        graph = torch.cuda.CUDAGraph()
        with torch.cuda.graph(graph):
            optimizer.zero_grad(set_to_none=False)
            captured = call()
            captured.total.backward()
            captured_grad_norm = torch.nn.utils.clip_grad_norm_(
                parameters, max_norm=float(args.grad_clip_norm), foreach=True,
            )
            optimizer.step()

    try:
        from torch.utils.tensorboard import SummaryWriter
        writer = SummaryWriter(str(run_dir / "tensorboard"))
    except Exception:
        writer = None
    started = time.perf_counter()
    for step in range(start_step + 1, int(args.steps) + 1):
        if step == int(args.decay_step) + 1:
            learning_rate.fill_(float(args.final_learning_rate))
        graph.replay()
        if step == start_step + 1 or step % int(args.log_every) == 0 or step == args.steps:
            torch.cuda.synchronize()
            values = (
                float(captured.mse.detach().cpu()),
                float(captured.pin_logit_mse_weighted.detach().cpu()),
                float(captured.calf_length_weighted.detach().cpu()),
                float(captured.calf_max_abs_error_m.detach().cpu()),
                float(captured.lowerarm_length_weighted.detach().cpu()),
                float(captured.lowerarm_max_abs_error_m.detach().cpu()),
                float(captured.ccd_weighted.detach().cpu()),
                float(captured.total.detach().cpu()),
                float(captured_grad_norm.detach().cpu()),
            )
            elapsed_at_log = max(time.perf_counter() - started, 1.0e-9)
            steps_per_second = (step - start_step) / elapsed_at_log
            print(
                f"step {step}/{args.steps} mse={values[0]:.7f} pin={values[1]:.7f} "
                f"calf={values[2]:.7f} calf_max={values[3]:.5f}m "
                f"lowerarm={values[4]:.7f} lowerarm_max={values[5]:.5f}m "
                f"ccd={values[6]:.7f} total={values[7]:.7f} "
                f"lr={float(learning_rate):.1e} grad={values[8]:.6f} "
                f"steps_s={steps_per_second:.3f}",
                flush=True,
            )
            atomic_json(run_dir / "status.json", {
                "state": "running", "step": step, "steps": int(args.steps),
                "mse": values[0], "pin_logit_mse": values[1],
                "calf_length": values[2], "calf_max_abs_error_m": values[3],
                "lowerarm_length": values[4],
                "lowerarm_max_abs_error_m": values[5],
                "ccd": values[6], "total": values[7],
                "learning_rate": float(learning_rate), "grad_norm": values[8],
                "steps_per_second": steps_per_second,
            })
            if writer is not None:
                writer.add_scalar("loss/mse", values[0], step)
                writer.add_scalar("loss/pin_logit_mse", values[1], step)
                writer.add_scalar("loss/calf_length", values[2], step)
                writer.add_scalar("metric/calf_max_abs_error_m", values[3], step)
                writer.add_scalar("loss/lowerarm_length", values[4], step)
                writer.add_scalar("metric/lowerarm_max_abs_error_m", values[5], step)
                writer.add_scalar("loss/ccd", values[6], step)
                writer.add_scalar("loss/total", values[7], step)
                writer.add_scalar("optimization/lr", float(learning_rate), step)
                writer.add_scalar("optimization/grad_norm", values[8], step)
                writer.add_scalar("performance/steps_per_second", steps_per_second, step)
        periodic_step = step != int(args.steps)
        export_due = periodic_step and step % int(args.replayer_every) == 0
        checkpoint_due = periodic_step and step % int(args.checkpoint_every) == 0
        if export_due:
            lower.eval(); upper.eval()
            with temporary_fk_dispatcher(training_fk), torch.no_grad():
                evaluated = call()
            export_batch_replayers(
                run_dir, evaluated, cases, skeleton, lower_targets, upper_targets,
                pin_targets,
                roots_pos, roots_rot, step, args.ccd_weight,
                args.calf_length_weight, args.lowerarm_length_weight,
                args.pin_logit_mse_weight, run_id,
            )
            del evaluated
            lower.train(); upper.train()
        if checkpoint_due:
            save_checkpoint(
                run_dir, lower, upper, optimizer, step, cases,
                args.ccd_weight, args.calf_length_weight,
                args.lowerarm_length_weight,
                args.pin_logit_mse_weight,
                args.dataset, adaptive_root_tolerance_cm,
            )
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - started
    lower.eval(); upper.eval()
    with temporary_fk_dispatcher(training_fk), torch.no_grad():
        final = call()
    final_values = {
        "mse": float(final.mse.detach().cpu()),
        "pin_logit_mse": float(final.pin_logit_mse_weighted.detach().cpu()),
        "calf_length": float(final.calf_length_weighted.detach().cpu()),
        "calf_max_abs_error_m": float(final.calf_max_abs_error_m.detach().cpu()),
        "lowerarm_length": float(final.lowerarm_length_weighted.detach().cpu()),
        "lowerarm_max_abs_error_m": float(final.lowerarm_max_abs_error_m.detach().cpu()),
        "ccd": float(final.ccd_weighted.detach().cpu()),
        "total": float(final.total.detach().cpu()),
    }
    export_batch_replayers(
        run_dir, final, cases, skeleton, lower_targets, upper_targets, pin_targets,
        roots_pos, roots_rot, args.steps, args.ccd_weight,
        args.calf_length_weight, args.lowerarm_length_weight,
        args.pin_logit_mse_weight, run_id,
    )
    checkpoint = save_checkpoint(
        run_dir, lower, upper, optimizer, args.steps, cases,
        args.ccd_weight, args.calf_length_weight, args.lowerarm_length_weight,
        args.pin_logit_mse_weight,
        args.dataset, adaptive_root_tolerance_cm,
    )
    steps_per_second = (int(args.steps) - start_step) / max(elapsed, 1.0e-9)
    atomic_json(run_dir / "status.json", {
        "state": "complete", "step": int(args.steps), "steps": int(args.steps),
        "elapsed_seconds": elapsed, "steps_per_second": steps_per_second,
        **final_values,
    })
    if writer is not None:
        writer.flush(); writer.close()
    print(
        f"IMITATION_SMOKE_COMPLETE run={run_id} motions={motion_ids} "
        f"mse={final_values['mse']:.7f} pin={final_values['pin_logit_mse']:.7f} "
        f"calf={final_values['calf_length']:.7f} "
        f"lowerarm={final_values['lowerarm_length']:.7f} "
        f"ccd={final_values['ccd']:.7f} "
        f"seconds={elapsed:.3f} steps_s={steps_per_second:.3f} "
        f"checkpoint={checkpoint}", flush=True,
    )


if __name__ == "__main__":
    main()
