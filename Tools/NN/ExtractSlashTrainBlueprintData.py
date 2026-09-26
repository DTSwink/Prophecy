"""Extract the viewer's requests, not its predicted poses, for an existing-node BP replay."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--training", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    runs = args.training / "runs"
    folder = runs / "20260922_latest_chained_variants/latest_predictive_pin_x5_20260924_refresh2/seed_2026092223/complete"
    manifest = json.loads((folder / "manifest.json").read_text())
    dataset = json.loads((runs / "20260905_good_step265458_actual_attacks_100_per_family_mode_agent_hit_gt_family_tail/dataset_manifest.json").read_text())
    sources = {row["file"]: row for row in dataset["rows"]}
    rollout = np.load(folder / "rollout.npz", allow_pickle=False)
    pelvis = list(rollout["bone_names"]).index("pelvis")
    rows = []
    initial_history = None
    maximum_error = 0.0
    for segment in manifest["segments"]:
        path = Path(sources[segment["sourceFile"]]["runtimeSourcePath"])
        assert hashlib.sha256(path.read_bytes()).hexdigest() == segment["sourceSha256"]
        source = np.load(path, allow_pickle=False)
        wanted = source["attack_target_world_m"].astype(np.float64)
        if not rows:
            position = source["controller_root_pos_m"][0].astype(np.float64)
            six = source["controller_root_rot6"][0].astype(np.float64)
            right = six[:3] / np.linalg.norm(six[:3])
            back = six[3:] - right * np.dot(right, six[3:])
            back /= np.linalg.norm(back)
            rotation = np.stack((right, back, np.cross(right, back)))
            destination_position, destination_rotation = position, rotation
            # Both conditioning poses in the stationary carrier used by the viewer.
            initial_history = dict(bone_names=rollout['bone_names'].tolist(),
                reference_position=position.tolist(), reference_rotation=rotation.tolist(),
                positions=((rollout['positions'][:2].astype(np.float64)-position) @ rotation.T).tolist(),
                rotations=(rollout['rotations'][:2].astype(np.float64) @ rotation.T).tolist())
            reference = "initial attack carrier (mesh component)"
        else:
            bone = list(source["bone_names"]).index("pelvis")
            matrix = source["global_matrix"][1, bone].astype(np.float64)
            position, rotation = matrix[3, :3] / 100.0, matrix[:3, :3]
            frame = segment["conditioningFrame"]
            destination_position = rollout["positions"][frame, pelvis].astype(np.float64)
            destination_rotation = rollout["rotations"][frame, pelvis].astype(np.float64)
            reference = "current published pelvis at previous attack completion"
        local = (wanted - position) @ rotation.T
        reconstructed = local @ destination_rotation + destination_position
        error = float(np.max(np.abs(reconstructed - segment["targetWorldM"])))
        assert error < 2e-5, (segment["attackIndex"], error)
        maximum_error = max(maximum_error, error)
        # Same bone/root-local handedness conversion as LocalTrainingToUnreal.
        unreal = local * np.array([100.0, -100.0, 100.0])
        rows.append(dict(index=segment["attackIndex"], attack=segment["family"],
                         targetLocalCm=unreal.tolist(), reference=reference,
                         sourceFile=segment["sourceFile"], sourceSha256=segment["sourceSha256"],
                         referenceTargetWorldM=segment["targetWorldM"],
                         referenceStartFrame=segment["startFrame"], referenceFinalFrame=segment["finalFrame"],
                         postHitTailFrames=segment["postHitTailFrames"]))
    assert len(rows) == 30 and manifest["seed"] == 2026092223
    result = dict(seed=manifest["seed"], checkpoint="PredictivePin184064", checkpointSha256=manifest["checkpointSha256"],
                  rule="Next request after Unreal attack completion; no recorded-frame timer. First target carrier-local; later targets pelvis-local, as mapped_target in generate_latest_chain_variants.py.",
                  maximumReferenceTargetReconstructionErrorCm=maximum_error * 100.0, rows=rows,
                  initial_history=initial_history)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Extracted {len(rows)} requests; maximum reference target error {maximum_error * 100:.8f} cm")


if __name__ == "__main__":
    main()
