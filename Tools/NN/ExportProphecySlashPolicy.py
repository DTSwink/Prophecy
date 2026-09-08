"""Export the accepted Slash2 transition, including its authoritative geometry.

The game supplies previous/current native states and a target. No recorded
future pose, attack timeline, or training prior is embedded in the model.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil
import sys

PROJECT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT / "Saved/SlashPythonDependencies"))

import numpy as np
import onnx
import torch

PROJECT = Path(__file__).resolve().parents[2]
STEPPER = Path(r"C:\Users\singerie\Documents\Cursor\stepper")
SLASH = STEPPER / "training/slashes2"
CHECKPOINT = STEPPER / "training/runs/done slash 2 2/checkpoints/good.pt"
CHECKPOINT_SHA = "6a76321d6e1525c9e6bcfcedcd0ce46676b03dd15dd277c2bd87f6c834239072"
REFERENCE = STEPPER / "training/runs/20260906_good_pt_easy_slashL_unreal_parity_random_row1091"
for folder in (STEPPER, STEPPER / "training/ik", SLASH):
    sys.path.insert(0, str(folder))
import train_slash_controller as slash
from ProphecyOnnxStaticShapes import fold_static_empty_tensors, fold_constants_for_unreal


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else hashlib.sha256(stream.read()).hexdigest()


class SlashStep(torch.nn.Module):
    """272 input floats -> 437 output floats, independent rows at 30 Hz."""

    def __init__(self, runtime, lower, upper, batch):
        super().__init__()
        self.runtime = runtime
        self.lower = lower
        self.upper = upper
        self.frozen = runtime.frozen_walk
        self.batch = batch
        self.register_buffer("ids", torch.zeros(batch, dtype=torch.long))
        self.register_buffer("frame", torch.ones(batch, dtype=torch.long))
        self.register_buffer("zero", torch.zeros(batch, dtype=torch.long))
        self.register_buffer("root_features", runtime.lower_store.get_input_root_features(self.ids, self.frame))
        root_pos, root_rot, _, _ = runtime.lower_store.root_state(self.ids, self.frame)
        self.register_buffer("root_pos", root_pos)
        self.register_buffer("root_rot", root_rot)

    def forward(self, values):
        rt = self.runtime
        prev_l, cur_l = values[:, :41], values[:, 41:82]
        prev_u, cur_u = values[:, 82:172], values[:, 172:262]
        target, labels = values[:, 262:265], values[:, 265:270]
        armed, hit = values[:, 270], values[:, 271]
        # Native pelvis is in root axes; learned Slash states use the held
        # current-pelvis-to-target heading. Both histories use that one heading.
        pelvis_world = (cur_l[:, :3].unsqueeze(1) @ self.root_rot).squeeze(1) + self.root_pos
        heading = slash.target_codec.target_facing_heading(pelvis_world, target)
        to_lower = lambda state: slash.lower_root_state_to_hybrid(rt.lower_store, self.ids, self.frame, state, target, heading)
        to_upper = lambda state: slash.upper_root_state_to_hybrid(rt.lower_store, self.ids, self.frame, state, target, heading)
        previous_lower = to_lower(prev_l)
        current_lower = to_lower(cur_l)
        previous_upper = to_upper(prev_u)
        current_upper = to_upper(cur_u)
        scale = rt.cfg.pose_delta_scale_final
        frozen_input = torch.cat((cur_l, prev_l, (cur_l[:, :3] - prev_l[:, :3]) / scale,
                                  (cur_l[:, 9:] - prev_l[:, 9:]) / scale, self.root_features), dim=-1)
        frozen_transition = slash.frozen_walk_forward(rt, rt.lower_batched_store, frozen_input, cur_l, prev_l)
        frozen_next_root = slash.ik_ctl.advance_transition_output(rt.lower_store, self.ids, self.frame, frozen_transition)
        frozen_next = to_lower(frozen_next_root)
        dyaw = torch.zeros_like(armed[:, None])
        lower_input = slash.build_lower_learned_input(current_lower, frozen_next, labels, dyaw, dyaw, target)
        raw_lower, _ = self.lower(lower_input)
        delta, pin_commands = slash.split_lower_output(raw_lower)
        next_lower, pin = slash.clean_lower_hybrid_delta(rt, rt.lower_batched_store, self.ids,
            self.frame, self.frame + 1, current_lower, frozen_next, delta, pin_commands, target, heading)
        current_base = slash.base_upper_hybrid_from_lower(rt, self.ids, self.ids, self.frame, current_lower, target, heading)
        next_base = slash.base_upper_hybrid_from_lower(rt, self.ids, self.ids, self.frame + 1, next_lower, target, heading)
        next_prior = slash.carry_upper_hybrid_deviation(current_upper, current_base, next_base)
        upper_input = slash.build_upper_learned_input(previous_upper, next_prior, target, labels,
            previous_lower, current_lower, next_lower, armed, hit)
        upper_delta, probabilities = self.upper(upper_input)
        next_upper = slash.clean_upper_state(next_prior + upper_delta)
        next_armed, next_hit = slash.advance_phase_latches(armed, hit, probabilities, rt.recipe.gate_threshold)
        pos, rot = slash.hybrid_full_fk_globals(rt, self.ids, self.ids, self.frame + 1,
            next_lower, next_upper, target, heading)
        next_lower_root = slash.lower_hybrid_state_to_root(rt.lower_store, self.ids, self.frame + 1, next_lower, target, heading)
        next_upper_root = slash.upper_hybrid_state_to_root(rt.lower_store, self.ids, self.frame + 1, next_upper, target, heading)
        return torch.cat((next_lower_root, next_upper_root, pos.flatten(1), rot.flatten(1),
                          next_armed[:, None], next_hit[:, None], probabilities, pin), dim=-1)


def prepare(batch):
    selection = json.loads((REFERENCE / "selection.json").read_text())
    assert sha(CHECKPOINT) == CHECKPOINT_SHA
    for info in selection["files"].values():
        if isinstance(info, dict):
            assert sha(REFERENCE / info["path"]) == info["sha256"]
    # The original loader uses the filename to identify the family. Preserve
    # every NPZ byte while giving this staging copy the required family prefix.
    source = REFERENCE / "good_pt_easy_slashL_inference_source.npz"
    staged = PROJECT / "Saved/SlashParity/slashL__unreal_parity.npz"
    staged.parent.mkdir(parents=True, exist_ok=True)
    if not staged.exists() or sha(staged) != sha(source):
        shutil.copy2(source, staged)
    checkpoint, recipe, lower, upper = slash.load_slash2_rollout_session(CHECKPOINT, torch.device("cpu"))
    # This teacher is a loss/diagnostic, never a controller input or output.
    recipe = replace(recipe, predictive_pin_checkpoint=None)
    runtime = slash.load_runtime(recipe, torch.device("cpu"), attack_paths=[staged], inference_only=True)
    data = runtime.attacks
    ids = torch.zeros(2, dtype=torch.long)
    frames = torch.arange(2)
    with runtime.policy_context(), torch.inference_mode():
        target = data.targets_world[:1].expand(2, -1)
        lower_root = slash.lower_hybrid_state_to_root(runtime.lower_store, ids, frames,
            data.trajectory_lower[0, :2], target, data.trajectory_heading[0, :2])
        upper_root = slash.upper_hybrid_state_to_root(runtime.lower_store, ids, frames,
            torch.stack((data.initial_previous_upper[0], data.initial_current_upper[0])),
            target, data.trajectory_heading[0, :2])
        values = torch.cat((lower_root[0], lower_root[1], upper_root[0], upper_root[1],
                            target[0], data.labels[0], torch.zeros(2)))[None].repeat(batch, 1)
    # Frozen root features must be constant throughout the reference, otherwise
    # the proposed idle carrier would be a different model invocation.
    frames = torch.arange(20)
    ids = torch.zeros_like(frames)
    features = runtime.lower_store.get_input_root_features(ids, frames)
    roots, rotations, _, _ = runtime.lower_store.root_state(ids, frames)
    if not torch.allclose(features, features[:1].expand_as(features), atol=1e-6, rtol=0):
        raise ValueError("Reference contains moving frozen roots; cannot use an idle carrier")
    if not torch.allclose(roots, roots[:1].expand_as(roots), atol=1e-6, rtol=0) or not torch.allclose(rotations, rotations[:1].expand_as(rotations), atol=1e-6, rtol=0):
        raise ValueError("Reference root changes")
    return runtime, SlashStep(runtime, lower, upper, batch).eval(), values, selection


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--contract-only", action="store_true")
    args = parser.parse_args()
    torch.set_num_threads(2)
    runtime, model, initial, selection = prepare(args.batch_size)
    reference = json.loads((REFERENCE / "rollout_unreal.json").read_text())
    state = initial.clone()
    errors = []
    with runtime.policy_context(), torch.inference_mode():
        for frame in range(2, 20):
            output = model(state)
            pos = output[0, 131:206].reshape(25, 3).numpy()
            rot = output[0, 206:431].reshape(25, 3, 3).numpy()
            expected = reference["frames"][frame]
            errors.append({"frame": frame,
                "max_position_m": float(np.max(np.linalg.norm(pos - np.asarray(expected["globalJointPositionsM"]), axis=-1))),
                "max_matrix_error": float(np.max(np.abs(rot - np.asarray(expected["globalJointRotations3x3"])))),
                "armed": float(output[0, 431]), "hit": float(output[0, 432]),
                "latches_match": bool(float(output[0, 431]) == expected["armedLatch"] and float(output[0, 432]) == expected["hitLatch"])})
            state = torch.cat((state[:, 41:82], output[:, :41], state[:, 172:262], output[:, 41:131],
                               state[:, 262:270], output[:, 431:433]), dim=-1)
        report = {"checkpoint_sha256": CHECKPOINT_SHA, "batch": args.batch_size,
            "position_max_m": max(r["max_position_m"] for r in errors),
            "matrix_max_abs": max(r["max_matrix_error"] for r in errors),
            "latches_match": all(r["latches_match"] for r in errors), "frames": errors}
        report_path = PROJECT / "Saved/SlashParity/python_step_parity.json"
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2), flush=True)
        if report["position_max_m"] > 0.0001 or report["matrix_max_abs"] > 0.001 or not report["latches_match"]:
            raise RuntimeError("Complete transition failed the recorded rollout parity gate")
        if args.export or args.contract_only:
            dest = PROJECT / "Content/locomotion/NN"
            dest.mkdir(parents=True, exist_ok=True)
            path = dest / f"prophecy_slash_step_b{args.batch_size}.onnx"
            if args.export:
                torch.onnx.export(model, (initial,), path, input_names=["state"], output_names=["next_state_pose"],
                                  opset_version=18, dynamo=True, external_data=False, optimize=False,
                                  artifacts_dir=str(PROJECT / "Saved/SlashParity"), report=True)
            exported = onnx.load(path)
            print("Folded empty optional FK tensors:", fold_static_empty_tensors(exported), flush=True)
            onnx.save(exported, path)
            folded = PROJECT / "Saved/SlashParity" / f"slash_basic_b{args.batch_size}.onnx"
            fold_constants_for_unreal(path, folded)
            shutil.copy2(folded, path)
            tails = {}
            for family in slash.ATTACK_LABELS:
                source = next(p for p in (SLASH / "final_gt_attack_dataset_npz").glob("*.npz")
                              if p.stem.lower() == family)
                with np.load(source, allow_pickle=False) as data:
                    count = int(data["frame_count"])
                    tails[family] = slash.authored_post_hit_tail_steps(count, float(data["attack_hit_frame"]))
            contract = {"checkpoint_path": str(CHECKPOINT), "checkpoint_sha256": CHECKPOINT_SHA,
                "model_file": path.name, "post_hit_tail_steps": tails,
                "checkpoint_step": 265458, "onnx_sha256": sha(path), "batch_size": args.batch_size,
                "input_dim": 272, "output_dim": 437, "bone_names": runtime.full_clip.body_names,
                "parents": runtime.full_clip.parents_body_list,
                "root_position_m": model.root_pos[0].tolist(), "root_rotation": model.root_rot[0].tolist(),
                "seed_input": initial[0].tolist(), "startup_expected": model(initial)[0].tolist(),
                "reference_directory": str(REFERENCE), "attack_labels": slash.ATTACK_LABELS,
                "gate_threshold": runtime.recipe.gate_threshold, "python_parity": report}
            (dest / "prophecy_slash_runtime.json").write_text(json.dumps(contract, indent=2) + "\n")
            print(f"Exported {path}: {path.stat().st_size} bytes", flush=True)


if __name__ == "__main__":
    main()
