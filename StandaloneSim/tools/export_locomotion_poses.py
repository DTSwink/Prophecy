from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


CLIPS = {
    "walk": Path("ue5/animations_omni_only_full/npz/M_Neutral_Walk_Loop_F.npz"),
    "run": Path("ue5/animation_run_omni_only/npz/M_Neutral_Run_Loop_F.npz"),
    "idle": Path(
        "training/slashes2/walk_run_sword_prep/authored_pruned_npz/"
        "walk_omni/M_Neutral_Stand_Idle_Loop.npz"
    ),
}

ACTION_CLIPS = {
    "sword": (
        Path("ue5/slashes/npz_fixedroot/slashL.npz"),
        Path("ue5/slashes/npz_fixedroot/slashLD.npz"),
        Path("ue5/slashes/npz_fixedroot/slashLU.npz"),
        Path("ue5/slashes/npz_fixedroot/slashR.npz"),
        Path("ue5/slashes/npz_fixedroot/slashRD.npz"),
        Path("ue5/slashes/npz_fixedroot/slashRU.npz"),
        Path("ue5/slashes/npz_fixedroot/pike.npz"),
    ),
    "melee": (
        Path("ue5/slashes/melee_npz_fixedroot/headbutt.npz"),
        Path("ue5/slashes/melee_npz_fixedroot/hookL.npz"),
        Path("ue5/slashes/melee_npz_fixedroot/hookR.npz"),
        Path("ue5/slashes/melee_npz_fixedroot/jabL.npz"),
        Path("ue5/slashes/melee_npz_fixedroot/jabR.npz"),
        Path("ue5/slashes/melee_npz_fixedroot/KickL.npz"),
        Path("ue5/slashes/melee_npz_fixedroot/KickR.npz"),
        Path("ue5/slashes/melee_npz_fixedroot/overL.npz"),
        Path("ue5/slashes/melee_npz_fixedroot/overR.npz"),
    ),
}

DRAW_JOINTS = (
    "pelvis", "spine_01", "spine_02", "spine_03", "spine_04", "spine_05",
    "clavicle_l", "upperarm_l", "lowerarm_l", "hand_l",
    "clavicle_r", "upperarm_r", "lowerarm_r", "hand_r",
    "neck_01", "neck_02", "head",
    "thigh_l", "calf_l", "foot_l", "ball_l",
    "thigh_r", "calf_r", "foot_r", "ball_r",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export lightweight full-body locomotion poses.")
    parser.add_argument("--stepper-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def heading_yaw(root_rotation: np.ndarray) -> np.ndarray:
    forward = -root_rotation[:, 1, :]
    return np.arctan2(forward[:, 0], forward[:, 2])


def heading_matrix(yaw: np.ndarray) -> np.ndarray:
    cosine = np.cos(yaw)
    sine = np.sin(yaw)
    zero = np.zeros_like(cosine)
    one = np.ones_like(cosine)
    return np.stack(
        (
            np.stack((cosine, zero, sine), axis=-1),
            np.stack((zero, one, zero), axis=-1),
            np.stack((-sine, zero, cosine), axis=-1),
        ),
        axis=-2,
    )


def export_clip(mode: str, path: Path, source_path: Path) -> tuple[dict[str, object], list[str], list[int]]:
    with np.load(path, allow_pickle=True) as arrays:
        names = [str(name) for name in arrays["bone_names"]]
        parents = [int(parent) for parent in arrays["parents"]]
        if "model_global_joint_pos_m" in arrays.files and "model_global_matrix" in arrays.files:
            positions = np.asarray(arrays["model_global_joint_pos_m"], dtype=np.float32)
            rotations = np.asarray(arrays["model_global_matrix"][:, :, :3, :3], dtype=np.float32)
        else:
            positions = np.asarray(arrays["global_joint_pos"], dtype=np.float32) * 0.01
            rotations = np.asarray(arrays["global_matrix"][:, :, :3, :3], dtype=np.float32)
        fps = float(arrays["fps"])

    root_index = names.index("root")
    selected_indices = [names.index(name) for name in DRAW_JOINTS]
    selected_lookup = {source: target for target, source in enumerate(selected_indices)}
    root = positions[:, root_index]
    yaw = heading_yaw(rotations[:, root_index])
    heading = heading_matrix(yaw)
    local = np.einsum(
        "tjc,tcd->tjd",
        positions[:, selected_indices] - root[:, None, :],
        np.swapaxes(heading, 1, 2),
    )
    root_xz = root[:, (0, 2)]
    clip = {
        "mode": mode,
        "fps": fps,
        "frame_count": int(local.shape[0]),
        "cycle_distance_m": 0.0 if mode == "idle" else float(np.linalg.norm(root_xz[-1] - root_xz[0])),
        "source_npz": source_path.as_posix(),
        "source_sha256": digest(path),
        "positions": np.round(local, 6).tolist(),
    }
    body_parents: list[int] = []
    for source_index in selected_indices:
        parent = parents[source_index]
        while parent >= 0 and parent not in selected_lookup:
            parent = parents[parent]
        body_parents.append(selected_lookup[parent] if parent in selected_lookup else -1)
    return clip, list(DRAW_JOINTS), body_parents


def export_action_clip(category: str, path: Path, source_path: Path) -> tuple[dict[str, object], list[str], list[int]]:
    clip, names, parents = export_clip(category, path, source_path)
    clip.pop("mode")
    clip.pop("cycle_distance_m")
    clip["name"] = source_path.stem
    clip["category"] = category
    clip["duration_seconds"] = clip["frame_count"] / clip["fps"]
    return clip, names, parents


def main() -> None:
    args = parse_args()
    stepper_root = args.stepper_root.resolve()
    exported = [export_clip(mode, stepper_root / relative, relative) for mode, relative in CLIPS.items()]
    exported_actions = [
        export_action_clip(category, stepper_root / relative, relative)
        for category, paths in ACTION_CLIPS.items()
        for relative in paths
    ]
    first_names = exported[0][1]
    first_parents = exported[0][2]
    if any(names != first_names or parents != first_parents
           for _clip, names, parents in exported[1:] + exported_actions):
        raise RuntimeError("Exported source rigs do not match.")
    output = {
        "schema": "prophecy.full-body-source-poses.v2",
        "source": "authored full-body locomotion and attack clips with draw-only skeleton pruning",
        "joint_names": first_names,
        "parents": first_parents,
        "clips": [clip for clip, _names, _parents in exported],
        "action_clips": [clip for clip, _names, _parents in exported_actions],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")
    for clip in output["clips"]:
        print(
            f"{clip['mode']}: {clip['frame_count']} full-body frames, "
            f"distance={clip['cycle_distance_m']:.5f}m, source={clip['source_sha256'][:12]}"
        )
    for clip in output["action_clips"]:
        print(
            f"{clip['category']}/{clip['name']}: {clip['frame_count']} full-body frames, "
            f"duration={clip['duration_seconds']:.3f}s, source={clip['source_sha256'][:12]}"
        )


if __name__ == "__main__":
    main()
