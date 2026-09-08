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
    "20260816_051748_ik_upper_cached_ae1ae4_bs64_allk32_ble_hbb0ff7d69b/"
    "checkpoints/"
    "20260816_051748_ik_upper_cached_ae1ae4_bs64_allk32_blend_noise50_"
    "initgaze50each_latest.pt"
)
DEFAULT_REFERENCE_CLIP = Path(
    "training/slashes2/walk_run_sword_prep/authored_pruned_npz/"
    "walk_omni/M_Neutral_Walk_Loop_F.npz"
)
DEFAULT_OUTPUT_DIR = Path("Content/locomotion/NN")

INPUT_DIM = 281
OUTPUT_DIM = 90
UPPER_BONES = (
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
    "lowerarm_l",
    "hand_l",
    "upperarm_r",
    "lowerarm_r",
    "hand_r",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def resolved(root: Path, path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (root / path).resolve()


class UpperPolicy(torch.nn.Module):
    def __init__(self, model: torch.nn.Module) -> None:
        super().__init__()
        self.model = model

    def forward(self, controller_input: torch.Tensor) -> torch.Tensor:
        return self.model(controller_input)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export the cached-lower upper-body controller for Unreal NNE."
    )
    parser.add_argument("--stepper-root", type=Path, default=DEFAULT_STEPPER_ROOT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--reference-clip", type=Path, default=DEFAULT_REFERENCE_CLIP)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--onnx-name", default="prophecy_upper_body_b100.onnx")
    parser.add_argument("--contract-name", default="prophecy_upper_body_runtime.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[2]
    stepper_root = args.stepper_root.resolve()
    checkpoint_path = resolved(stepper_root, args.checkpoint)
    reference_clip_path = resolved(stepper_root, args.reference_clip)
    output_dir = resolved(project_root, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(stepper_root))
    from training.ik import ik_core as tl
    from training.ik import train_upper_pose_autoencoder as upper_data
    from training.ik import train_upper_pose_controller_pelvis as upper_ctl

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if checkpoint.get("kind") != upper_ctl.CACHED_LOWER_CONTROLLER_KIND:
        raise RuntimeError(f"Unexpected checkpoint kind: {checkpoint.get('kind')!r}")
    schema = checkpoint.get("schema", {})
    if (int(schema.get("input_dim", -1)), int(schema.get("output_dim", -1))) != (
        INPUT_DIM,
        OUTPUT_DIM,
    ):
        raise RuntimeError(f"Unexpected checkpoint schema: {schema!r}")

    model = upper_ctl.UpperCachedLowerAgent()
    model.load_state_dict(checkpoint["model"])
    model.eval()
    wrapper = UpperPolicy(model).eval()
    example_input = torch.zeros((int(args.batch_size), INPUT_DIM), dtype=torch.float32)
    audit_generator = torch.Generator(device="cpu").manual_seed(0x50524F50)
    audit_input = torch.rand(
        (INPUT_DIM,), generator=audit_generator, dtype=torch.float32
    ) * 2.0 - 1.0
    with torch.no_grad():
        example_output = wrapper(example_input)
        audit_output = wrapper(audit_input.unsqueeze(0).repeat(int(args.batch_size), 1))[0]
    if tuple(example_output.shape) != (int(args.batch_size), OUTPUT_DIM):
        raise RuntimeError(f"Unexpected output shape: {tuple(example_output.shape)}")
    if not torch.isfinite(example_output).all():
        raise RuntimeError("Upper controller produced NaN or Inf values.")
    if tuple(audit_output.shape) != (OUTPUT_DIM,) or not torch.isfinite(audit_output).all():
        raise RuntimeError("Upper controller startup-audit output is invalid.")

    onnx_path = output_dir / args.onnx_name
    with torch.no_grad():
        torch.onnx.export(
            wrapper,
            (example_input,),
            onnx_path,
            input_names=["controller_input"],
            output_names=["upper_pose_delta"],
            opset_version=18,
            do_constant_folding=True,
            dynamo=False,
        )
    exported = onnx.load(onnx_path)
    onnx.checker.check_model(exported)

    cfg = upper_data.motion_config()
    clip = tl.MotionClip(reference_clip_path, cfg, cyclic_animation=True)
    tensors = clip.tensors(torch.device("cpu"))
    arm_specs = [spec for spec in clip.ik_limb_specs if str(spec["kind"]) == "arm"]
    if len(arm_specs) != 2:
        raise RuntimeError(f"Expected two arm IK specifications, got {arm_specs!r}")

    rest_offsets = upper_data.rest_offsets_from_pelvis(clip)
    contract = {
        "schema_version": 1,
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": sha256_file(checkpoint_path),
        "checkpoint_step": int(checkpoint.get("step", -1)),
        "checkpoint_kind": str(checkpoint.get("kind", "")),
        "reference_clip_path": str(reference_clip_path),
        "reference_clip_sha256": sha256_file(reference_clip_path),
        "onnx_path": str(onnx_path),
        "onnx_sha256": sha256_file(onnx_path),
        "batch_size": int(args.batch_size),
        "input_dim": INPUT_DIM,
        "output_dim": OUTPUT_DIM,
        "startup_audit": {
            "input": audit_input.tolist(),
            "expected_output": audit_output.tolist(),
            "maximum_absolute_error": 1.0e-3,
        },
        "upper_bones": list(UPPER_BONES),
        "core_bones": list(upper_data.CORE_BONES),
        "arm_specs": [
            {
                "side": str(spec["side"]),
                "start": int(spec["start"]),
                "mid": int(spec["mid"]),
                "end": int(spec["end"]),
                "start_name": clip.body_names[int(spec["start"])],
                "mid_name": clip.body_names[int(spec["mid"])],
                "end_name": clip.body_names[int(spec["end"])],
            }
            for spec in arm_specs
        ],
        "body_names": list(clip.body_names),
        "parents_body": list(clip.parents_body_list),
        "local_offsets_m": clip.local_offsets.tolist(),
        "rest_offsets_from_pelvis_m": rest_offsets.tolist(),
        "arm_limb_lengths_m": [
            tensors["ik_limb_lengths"][clip.ik_limb_specs.index(spec)].tolist()
            for spec in arm_specs
        ],
        "arm_local_pole_axes": [
            tensors["ik_local_pole_axis"][clip.ik_limb_specs.index(spec)].tolist()
            for spec in arm_specs
        ],
        "input_layout": {
            "previous_upper": [0, 90],
            "stiff_next_upper": [90, 180],
            "previous_pelvis": [180, 189],
            "current_pelvis": [189, 198],
            "next_pelvis": [198, 207],
            "root_and_future_roots": [207, 242],
            "has_sword": [242, 243],
            "current_feet": [243, 261],
            "next_feet": [261, 279],
            "gaze": [279, 281],
        },
        "gaze": {
            "yaw_limit_degrees": float(upper_data.GAZE_YAW_LIMIT_DEG),
            "pitch_limit_degrees": float(upper_data.GAZE_PITCH_LIMIT_DEG),
            "runtime_values_are_normalized": True,
        },
        "upper_state_layout": {
            "core_local_rot6": [0, 60],
            "left_hand_position_heading": [60, 63],
            "left_hand_rotation_heading6": [63, 69],
            "left_upperarm_rotation_heading6": [69, 75],
            "right_hand_position_heading": [75, 78],
            "right_hand_rotation_heading6": [78, 84],
            "right_upperarm_rotation_heading6": [84, 90],
        },
    }
    contract_path = output_dir / args.contract_name
    contract_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {onnx_path}")
    print(f"Contract {contract_path}")
    print(f"ONNX SHA256 {contract['onnx_sha256']}")
    print(f"Checkpoint SHA256 {contract['checkpoint_sha256']}")


if __name__ == "__main__":
    main()
