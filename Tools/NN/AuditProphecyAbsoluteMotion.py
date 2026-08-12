from __future__ import annotations

import argparse
import base64
import csv
import importlib
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_UNREAL = Path(r"C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe")
DEFAULT_REFERENCE_HTML = Path(
    r"C:\Users\singerie\Documents\Cursor\stepper\training\ik\rollout_traces"
    r"\20260618_final_policy_runF\model_comparison.html"
)
DEFAULT_REFERENCE_CLIP = Path(
    r"C:\Users\singerie\Documents\Cursor\stepper\ue5\animation_run_omni_only"
    r"\npz_final\M_Neutral_Run_Loop_F.npz"
)
DEFAULT_TRACE = PROJECT_ROOT / "Saved" / "ProphecyNN" / "absolute_motion_trace.csv"
DEFAULT_REPORT = PROJECT_ROOT / "Saved" / "ProphecyNN" / "absolute_motion_report.json"
DEFAULT_WALK_RUNTIME = PROJECT_ROOT / "Content" / "locomotion" / "NN" / "prophecy_lower_body_walk_runtime.json"
VISIBLE_BONES = (
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run and score the Unreal RunF pose in the absolute world frame."
    )
    parser.add_argument("--unreal", type=Path, default=DEFAULT_UNREAL)
    parser.add_argument("--reference-html", type=Path, default=DEFAULT_REFERENCE_HTML)
    parser.add_argument("--reference-clip", type=Path, default=DEFAULT_REFERENCE_CLIP)
    parser.add_argument("--trace", type=Path, default=DEFAULT_TRACE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--render-hz", type=float, default=120.0)
    parser.add_argument(
        "--walk",
        action="store_true",
        help="Use the approved Walk policy and the Stepper Model Viewer as the pose authority.",
    )
    parser.add_argument("--position-tolerance-mm", type=float, default=2.1)
    parser.add_argument("--root-tolerance-mm", type=float, default=0.1)
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Score an existing trace without launching Unreal.",
    )
    parser.add_argument(
        "--local-space-baseline",
        action="store_true",
        help="Disable viewer-matched global-pose interpolation to reproduce the old local-space baseline.",
    )
    return parser.parse_args()


def load_reference(html_path: Path, clip_path: Path) -> tuple[list[str], np.ndarray, np.ndarray, np.ndarray]:
    html = html_path.read_text(encoding="utf-8")
    match = re.search(
        r'<script id="motion-data" type="application/json">(.*?)</script>',
        html,
        flags=re.DOTALL,
    )
    if not match:
        raise RuntimeError(f"motion-data was not found in {html_path}")
    item = json.loads(match.group(1))[0]
    frame_count = int(item["frame_count"])
    bone_count = int(item["bone_count"])
    bone_names = list(item["bone_names"])
    positions = np.frombuffer(base64.b64decode(item["pred_ar_b64"]), dtype=np.float32).reshape(
        frame_count, bone_count, 3
    )
    pins = np.frombuffer(base64.b64decode(item["pinned_ar_b64"]), dtype=np.int8)
    visible_indices = [bone_names.index(name) for name in VISIBLE_BONES]

    with np.load(clip_path, allow_pickle=False) as clip:
        root_positions = np.asarray(clip["model_global_joint_pos_m"][:, 0], dtype=np.float64)
    if root_positions.shape != (frame_count, 3):
        raise RuntimeError(
            f"Reference roots are {root_positions.shape}; expected {(frame_count, 3)}"
        )

    # The residual output for pose frame k is authored in root frame k-1.
    # Seed frame 1 is already local to root frame 1, so frames 1 and 2 share
    # the same displayed capsule root before the normal one-frame progression.
    display_roots = root_positions.copy()
    display_roots[1] = root_positions[1]
    display_roots[2:] = root_positions[1:-1]
    return list(VISIBLE_BONES), positions[:, visible_indices].astype(np.float64), pins, display_roots


def load_walk_reference(runtime_path: Path) -> tuple[list[str], np.ndarray, np.ndarray, np.ndarray]:
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    checkpoint_path = Path(runtime["checkpoint_path"]).resolve()
    clip_path = Path(runtime["seed_clip_path"]).resolve()
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"Walk checkpoint is missing: {checkpoint_path}")
    if not clip_path.is_file():
        raise FileNotFoundError(f"Walk seed clip is missing: {clip_path}")

    # Execute the installed viewer pipeline without changing it. This makes the
    # viewer's recurrent rollout, pinning, foot roll and FK the audit authority.
    training_dir = checkpoint_path.parents[3]
    sys.path.insert(0, str(training_dir))
    viewer = importlib.import_module("model_viewer_app")
    app = viewer.ModelViewerApp()
    app.withdraw()
    try:
        actor = app.add_checkpoint_actor(checkpoint_path, clip_path)
        actor.apply_ik_controller_policy()
        with np.load(clip_path, allow_pickle=False) as clip:
            root_positions = np.asarray(clip["model_global_joint_pos_m"][:, 0], dtype=np.float64)
        actor.generate_to(len(root_positions) - 1)
        visible_indices = [actor.bone_names.index(name) for name in VISIBLE_BONES]
        positions = np.asarray(actor.generated_pos, dtype=np.float64)[:, visible_indices]
        pin_states = np.asarray(actor.generated_pin_states, dtype=np.float64)
        if pin_states.shape != (len(positions), 2):
            raise RuntimeError(
                f"Viewer Walk pin states are {pin_states.shape}; expected {(len(positions), 2)}"
            )
        # The legacy report stores one pinned side per frame. When Walk marks
        # both feet, choose left deterministically; both ankles are still scored
        # independently by the all-visible-bones and both-ankles criteria.
        pins = np.where(pin_states[:, 0] >= pin_states[:, 1], 0, 1).astype(np.int8)
    finally:
        app.destroy()

    if positions.shape[0] != root_positions.shape[0]:
        raise RuntimeError(
            f"Viewer Walk frames are {positions.shape[0]}; seed root frames are {root_positions.shape[0]}"
        )
    display_roots = root_positions.copy()
    display_roots[1] = root_positions[1]
    display_roots[2:] = root_positions[1:-1]
    return list(VISIBLE_BONES), positions, pins, display_roots


def launch_unreal(args: argparse.Namespace) -> None:
    unreal = args.unreal.resolve()
    project = (PROJECT_ROOT / "GameAnimationSample3.uproject").resolve()
    trace = args.trace.resolve()
    saved_root = (PROJECT_ROOT / "Saved").resolve()
    try:
        trace.relative_to(saved_root)
    except ValueError as exc:
        raise RuntimeError(f"Refusing to replace a trace outside {saved_root}: {trace}") from exc
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.unlink(missing_ok=True)

    log_path = (PROJECT_ROOT / "Saved" / "Logs" / "ProphecyAbsoluteMotionAudit.log").resolve()
    command = [
        str(unreal),
        str(project),
        "/Game/locomotion",
        "-game",
        "-nullrhi",
        "-nosound",
        "-unattended",
        "-NoSplash",
        "-ProphecyNNAbsoluteMotionAudit",
        "-ProphecyNNAuditExit",
        f"-ProphecyNNAuditRenderHz={max(1.0, args.render_hz):g}",
        "-ProphecyNNLocomotionRuntime=NNERuntimeORTCpu",
        f"-abslog={log_path}",
    ]
    if args.local_space_baseline:
        command.append("-ProphecyNNDisableViewerGlobalInterpolation")
    if args.walk:
        command.append("-ProphecyNNAuditWalk")
    completed = subprocess.run(command, cwd=PROJECT_ROOT, timeout=180.0, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"Unreal absolute-motion audit exited with code {completed.returncode}; see {log_path}"
        )
    if not trace.is_file():
        raise RuntimeError(f"Unreal did not produce {trace}; see {log_path}")


def interpolate(values: np.ndarray, phases: np.ndarray) -> np.ndarray:
    lower = np.floor(phases).astype(np.int64)
    upper = np.minimum(lower + 1, values.shape[0] - 1)
    alpha_shape = (len(phases),) + (1,) * (values.ndim - 1)
    alpha = (phases - lower).reshape(alpha_shape)
    return values[lower] * (1.0 - alpha) + values[upper] * alpha


def load_trace(path: Path, bones: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise RuntimeError(f"Trace is empty: {path}")

    phases = np.asarray([float(row["phase"]) for row in rows], dtype=np.float64)
    roots_ue = np.asarray(
        [[float(row[f"root_{axis}_cm"]) for axis in "xyz"] for row in rows],
        dtype=np.float64,
    )
    positions_ue = np.asarray(
        [
            [
                [float(row[f"{bone}_{axis}_cm"]) for axis in "xyz"]
                for bone in bones
            ]
            for row in rows
        ],
        dtype=np.float64,
    )
    # Unreal world (X,Y,Z) -> training world (X,up Y,forward Z), in meters.
    roots_training = roots_ue[:, [0, 2, 1]] / 100.0
    positions_training = positions_ue[:, :, [0, 2, 1]] / 100.0
    return phases, roots_training, positions_training


def metric(values_m: np.ndarray) -> dict[str, float]:
    flat = np.asarray(values_m, dtype=np.float64).reshape(-1)
    return {
        "median_mm": float(np.median(flat) * 1000.0),
        "p95_mm": float(np.percentile(flat, 95.0) * 1000.0),
        "max_mm": float(np.max(flat) * 1000.0),
    }


def analyze(args: argparse.Namespace) -> dict[str, object]:
    if args.walk:
        bones, reference_positions, pins, reference_roots = load_walk_reference(DEFAULT_WALK_RUNTIME)
    else:
        bones, reference_positions, pins, reference_roots = load_reference(
            args.reference_html, args.reference_clip
        )
    phases, actual_roots, actual_positions = load_trace(args.trace, bones)
    max_reference_frame = float(reference_positions.shape[0] - 1)
    valid = (phases >= 1.0) & (phases <= max_reference_frame)
    phases = phases[valid]
    actual_roots = actual_roots[valid]
    actual_positions = actual_positions[valid]
    if not phases.size:
        raise RuntimeError(
            f"Trace has no samples in canonical {'WalkF' if args.walk else 'RunF'} "
            f"frames 1..{int(max_reference_frame)}"
        )

    expected_roots = interpolate(reference_roots, phases)
    world_offset = actual_roots[0] - expected_roots[0]
    aligned_roots = actual_roots - world_offset
    aligned_positions = actual_positions - world_offset.reshape(1, 1, 3)
    expected_positions = interpolate(reference_positions, phases)

    root_error = np.linalg.norm(aligned_roots - expected_roots, axis=1)
    bone_error = np.linalg.norm(aligned_positions - expected_positions, axis=2)
    integer_mask = np.abs(phases - np.rint(phases)) <= 1.0e-4

    pin_frames = np.clip(np.rint(phases).astype(np.int64), 0, len(pins) - 1)
    pinned_bone_indices = np.where(pins[pin_frames] == 0, bones.index("foot_l"), bones.index("foot_r"))
    pinned_error = bone_error[np.arange(len(phases)), pinned_bone_indices]
    foot_indices = [bones.index("foot_l"), bones.index("foot_r")]
    foot_error = bone_error[:, foot_indices]
    lower_frames = np.clip(np.floor(phases).astype(np.int64), 0, reference_positions.shape[0] - 2)
    stable_foot_mask = np.zeros_like(foot_error, dtype=bool)
    for foot_column, bone_index in enumerate(foot_indices):
        endpoint_motion = np.linalg.norm(
            reference_positions[lower_frames + 1, bone_index]
            - reference_positions[lower_frames, bone_index],
            axis=1,
        )
        stable_foot_mask[:, foot_column] = endpoint_motion < 0.02

    per_bone = {bone: metric(bone_error[:, index]) for index, bone in enumerate(bones)}
    report: dict[str, object] = {
        "schema_version": 1,
        "criterion": (
            "viewer-matched global lower-body interpolation in the absolute Unreal world frame "
            f"versus approved {'WalkF' if args.walk else 'RunF'}"
        ),
        "samples": int(len(phases)),
        "phase_min": float(phases.min()),
        "phase_max": float(phases.max()),
        "alignment_offset_training_m": world_offset.tolist(),
        "root": metric(root_error),
        "all_visible_bones": metric(bone_error),
        "pinned_foot_bone": metric(pinned_error),
        "both_ankles": metric(foot_error),
        "stable_ankles": metric(foot_error[stable_foot_mask]),
        "policy_frame_visible_bones": metric(bone_error[integer_mask]) if np.any(integer_mask) else None,
        "per_bone": per_bone,
        "position_tolerance_mm": float(args.position_tolerance_mm),
        "root_tolerance_mm": float(args.root_tolerance_mm),
    }
    report["pass"] = bool(
        report["all_visible_bones"]["max_mm"] <= args.position_tolerance_mm
        and report["both_ankles"]["max_mm"] <= args.position_tolerance_mm
        and report["policy_frame_visible_bones"]["max_mm"] <= args.position_tolerance_mm
        and report["root"]["max_mm"] <= args.root_tolerance_mm
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    args = parse_args()
    if not args.analyze_only:
        launch_unreal(args)
    report = analyze(args)
    print(json.dumps(report, indent=2))
    if not report["pass"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
