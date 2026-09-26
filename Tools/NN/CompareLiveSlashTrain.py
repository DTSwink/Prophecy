"""Compare a live 25-bone slash trace against ValidateCurrentSlashChain's oracle.

The trace must include native_position/native_rotation and anchor on every row.
Nothing is realigned at attack boundaries. Missing diagnostic writes are reported,
not mistaken for shortened attacks or silently compared to the next frame.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation


def compare(trace, oracle, geometry):
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    if not rows or len({row['actor'] for row in rows}) != 1:
        raise ValueError('Expected a nonempty trace of one agent; filter mixed-agent traces first.')
    reference = json.loads(oracle.read_text())
    source = json.loads(geometry.read_text())
    first = rows[0]["anchor"]
    origin = np.array(first[:3])
    basis = Rotation.from_quat(first[3:]).as_matrix()
    source_position = np.array(source["root_position"])
    source_rotation = np.array(source["root_rotation"])
    mirror = np.diag([1, -1, 1])
    groups = []
    for row in rows:
        if not groups or row["frame"] <= groups[-1][-1]["frame"]:
            groups.append([])
        groups[-1].append(row)
    errors, angles, segments = [], [], []
    latches_match = True
    for group, segment in zip(groups, reference["segments"]):
        expected_count = segment["finalFrame"] - segment["startFrame"] + 1
        wanted_frames = set(range(2, expected_count + 2))
        actual_frames = {row["frame"] for row in group}
        segments.append(dict(family=segment["family"], expected_steps=expected_count,
                             family_match=all(row['family'].lower()==segment['family'].lower() for row in group),
                             observed_steps=len(group), missing=sorted(wanted_frames-actual_frames),
                             extra=sorted(actual_frames-wanted_frames)))
        for row in group:
            frame = row["frame"] - 2
            if frame < 0 or frame >= expected_count:
                continue
            output = np.array(row["output"])
            wanted = np.array(reference["expected"][segment["startFrame"]-2+frame])
            root = np.array(row["native_position"])
            rotation = np.array(row["native_rotation"]).reshape(3, 3)
            anchor = row["anchor"]
            carrier = Rotation.from_quat(anchor[3:]).as_matrix()
            local = (output[131:206].reshape(25, 3)-root) @ rotation.T
            world = local @ mirror * 100 @ carrier.T + anchor[:3]
            aligned = ((world-origin) @ basis / 100 @ mirror) @ source_rotation + source_position
            errors.extend((np.linalg.norm(aligned-wanted[131:206].reshape(25, 3), axis=1)*1000).tolist())
            local_rotations = output[206:431].reshape(25, 3, 3) @ rotation.T
            world_rotations = mirror @ local_rotations @ mirror @ carrier.T
            aligned_rotations = mirror @ world_rotations @ basis @ mirror @ source_rotation
            expected_rotations = wanted[206:431].reshape(25, 3, 3)
            angles.extend(np.degrees((Rotation.from_matrix(expected_rotations).inv() *
                                     Rotation.from_matrix(aligned_rotations)).magnitude()).tolist())
            latches_match &= bool(np.array_equal(output[431:433] > .5, wanted[431:433] > .5))
    complete = len(groups) == len(reference["segments"]) and all(s['family_match'] and not s["missing"] and not s["extra"] for s in segments)
    return dict(complete=complete, attack_count=len(groups), policy_steps=len(rows),
                armed_hit_match=latches_match, max_position_mm=max(errors),
                rms_position_mm=float(np.sqrt(np.mean(np.square(errors)))),
                max_rotation_degrees=max(angles), segments=segments)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--oracle", type=Path, required=True)
    parser.add_argument("--geometry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.trace, args.oracle, args.geometry)
    args.output.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({k: v for k, v in result.items() if k != "segments"}, indent=2))
    if not result["complete"]:
        raise SystemExit("Incomplete trace: inspect missing/extra frames before claiming parity.")
