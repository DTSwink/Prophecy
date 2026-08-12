from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import onnx
import torch


DEFAULT_STEPPER_ROOT = Path(r"C:\Users\singerie\Documents\Cursor\stepper")
DEFAULT_CHECKPOINT = Path(
    "training/runs/"
    "20260617_234645_ik_ik_full_RESUME_best47200_k32fixed_s05_rootaccelx01_i_e8b756b3/"
    "checkpoints/"
    "20260617_234645_ik_ik_full_RESUME_best47200_k32fixed_s05_rootaccelx01_i_e8b756b3_init.pt"
)
DEFAULT_SEED_CLIP = Path("ue5/animation_run_omni_only/npz_final/M_Neutral_Run_Loop_F.npz")
DEFAULT_OUTPUT_DIR = Path("Content/locomotion/NN")

INPUT_DIM = 152
STATE_DIM = 41
MODEL_OUTPUT_DIM = 43
VISIBLE_BONE_NAMES = (
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
RUNTIME_OUTPUT_DIM = MODEL_OUTPUT_DIM
RUNTIME_FOOT_ROLL_INTEGRATION_STEPS = 4


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def resolved(root: Path, path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (root / path).resolve()


class UnrealLowerBodyPolicy(torch.nn.Module):
    """Compact NNE boundary; deterministic rollout cleanup stays native."""

    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, controller_input: torch.Tensor) -> torch.Tensor:
        return self.model(controller_input)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the accepted lower-body controller for Unreal NNE.")
    parser.add_argument("--stepper-root", type=Path, default=DEFAULT_STEPPER_ROOT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--seed-clip", type=Path, default=DEFAULT_SEED_CLIP)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--onnx-name", default="prophecy_lower_body_run_b100.onnx")
    parser.add_argument("--contract-name", default="prophecy_lower_body_runtime.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[2]
    stepper_root = args.stepper_root.resolve()
    checkpoint_path = resolved(stepper_root, args.checkpoint)
    clip_path = resolved(stepper_root, args.seed_clip)
    output_dir = resolved(project_root, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(stepper_root))
    from training.ik import ik_core as tl
    from training.ik import train_simple_ae_controller as simple_ctl
    from training.ik import visualize

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    visualize.apply_simple_controller_policy(checkpoint)
    cfg = tl.TrainConfig()
    visualize.apply_config_dict(cfg, checkpoint["config"])
    cfg.device = "cpu"
    cfg.cyclic_animation = True

    clip = tl.MotionClip(clip_path, cfg, cyclic_animation=True)
    store = simple_ctl.SimpleClipStore([clip], cfg, torch.device("cpu"))
    model = visualize.load_model(checkpoint, clip, cfg, torch.device("cpu"))
    model.eval()

    input_dim, state_dim = tl.make_batch_dims(clip, cfg)
    model_output_dim = tl.controller_output_dim(clip, cfg)
    if (input_dim, state_dim, model_output_dim) != (INPUT_DIM, STATE_DIM, MODEL_OUTPUT_DIM):
        raise RuntimeError(
            f"Accepted policy contract changed: got {input_dim}->{model_output_dim} with state {state_dim}, "
            f"expected {INPUT_DIM}->{MODEL_OUTPUT_DIM} with state {STATE_DIM}."
        )

    wrapper = UnrealLowerBodyPolicy(model).eval()
    clip_ids = torch.zeros(args.batch_size, dtype=torch.long)
    prev_idx = torch.zeros(args.batch_size, dtype=torch.long)
    cur_idx = torch.ones(args.batch_size, dtype=torch.long)
    prev_vec, prev_pelvis, prev_payload = simple_ctl.target_state(store, clip_ids, prev_idx)
    cur_vec, cur_pelvis, cur_payload = simple_ctl.target_state(store, clip_ids, cur_idx)
    example_input = simple_ctl.build_controller_input(
        store,
        clip_ids,
        cur_idx,
        prev_vec,
        cur_vec,
        prev_pelvis,
        cur_pelvis,
        prev_payload,
        cur_payload,
    )

    with torch.no_grad():
        example_output = wrapper(example_input)
    if tuple(example_output.shape) != (args.batch_size, RUNTIME_OUTPUT_DIM):
        raise RuntimeError(f"Policy output is {tuple(example_output.shape)}, expected {(args.batch_size, RUNTIME_OUTPUT_DIM)}")
    if not torch.isfinite(example_output).all():
        raise RuntimeError("Policy produced NaN or Inf values.")

    onnx_path = output_dir / args.onnx_name
    with torch.no_grad():
        torch.onnx.export(
            wrapper,
            (example_input,),
            onnx_path,
            input_names=["controller_input"],
            output_names=["policy_output"],
            opset_version=18,
            do_constant_folding=True,
            dynamo=False,
        )
    exported = onnx.load(onnx_path)
    onnx.checker.check_model(exported)

    seed_path = output_dir / args.contract_name
    contract = {
        "schema_version": 1,
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": sha256_file(checkpoint_path),
        "seed_clip_path": str(clip_path),
        "seed_clip_sha256": sha256_file(clip_path),
        "onnx_path": str(onnx_path),
        "onnx_sha256": sha256_file(onnx_path),
        "batch_size": int(args.batch_size),
        "input_dim": INPUT_DIM,
        "model_output_dim": MODEL_OUTPUT_DIM,
        "runtime_output_dim": RUNTIME_OUTPUT_DIM,
        "state_dim": STATE_DIM,
        "future_window": int(cfg.future_window),
        "max_speed_scale_final": float(cfg.max_speed_scale_final),
        "max_turn_rate_scale_final": float(cfg.max_turn_rate_scale_final),
        "pose_delta_scale_final": float(cfg.pose_delta_scale_final),
        "output_reference_root": tl.normalized_output_reference_root(),
        "output_prediction_mode": tl.normalized_output_prediction_mode(),
        "body_mode": tl.normalized_body_mode(cfg.body_mode),
        "body_names": list(clip.body_names),
        "parents_body": list(clip.parents_body_list),
        "local_offsets_m": clip.local_offsets.tolist(),
        "visible_bone_names": list(VISIBLE_BONE_NAMES),
        "ik_limb_specs": [
            {
                "side": str(spec["side"]),
                "kind": str(spec["kind"]),
                "start": int(spec["start"]),
                "mid": int(spec["mid"]),
                "end": int(spec["end"]),
                "toe": int(spec["toe"]),
            }
            for spec in clip.ik_limb_specs
        ],
        "ik_limb_lengths_m": store.ik_limb_lengths.tolist(),
        "ik_local_pole_axes": clip.tensors(torch.device("cpu"))["ik_local_pole_axis"].tolist(),
        "ik_toe_offsets_m": store.ik_toe_offsets.tolist(),
        "ik_toe_axes": store.ik_toe_axis.tolist(),
        "ik_toe_alpha_rad": float(tl.IK_TOE_ALPHA),
        "foot_roll": {
            "foot_half_dims_m": store.foot_roll_foot_half_dims.tolist(),
            "toe_half_dims_m": store.foot_roll_toe_half_dims.tolist(),
            "sole_vertical_offset_m": float(simple_ctl.FOOT_ROLL_SOLE_VERTICAL_OFFSET_M),
            "up_axis": int(simple_ctl.FOOT_ROLL_UP_AXIS),
            "integration_steps": RUNTIME_FOOT_ROLL_INTEGRATION_STEPS,
            "side_blend_deg": float(cfg.foot_roll_side_blend_deg),
            "pin_ste_scale": float(simple_ctl.FOOT_ROLL_PIN_STE_SCALE),
            "pin_mode": str(simple_ctl.FOOT_ROLL_PIN_MODE),
            "ground_y": float(store.foot_roll_ground_y_tensor),
            "height_pin_gate_enabled": bool(simple_ctl.FOOT_ROLL_HEIGHT_PIN_GATE),
            "near_floor_full_height_m": float(simple_ctl.FOOT_ROLL_NEAR_FLOOR_PIN_FULL_HEIGHT_M),
            "near_floor_fade_height_m": float(simple_ctl.FOOT_ROLL_NEAR_FLOOR_PIN_FADE_HEIGHT_M),
            "near_floor_minimum_pin_probability": float(simple_ctl.FOOT_ROLL_NEAR_FLOOR_PIN_MIN_PROB),
        },
        "output_layout": {
            "state_residual": [0, STATE_DIM],
            "foot_pin_logits": [STATE_DIM, MODEL_OUTPUT_DIM],
        },
        "seed_prev_state": prev_vec[0].tolist(),
        "seed_cur_state": cur_vec[0].tolist(),
        "seed_phase_states": store.target_output.tolist(),
        "seed_root_rotation_rows": clip.root_rot[0].tolist(),
    }
    seed_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

    print(f"Exported {onnx_path}")
    print(f"Contract {seed_path}")
    print(f"ONNX SHA256 {contract['onnx_sha256']}")
    print(f"Checkpoint SHA256 {contract['checkpoint_sha256']}")


if __name__ == "__main__":
    main()
