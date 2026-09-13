"""Measure the recorded idle/runner test, including GT seeds and visible upper poses."""
import collections
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

PROJECT = Path(__file__).resolve().parents[2]
DIRECTORY = PROJECT / "Saved/Diagnostics/SlashContacts"
capture = json.loads((DIRECTORY / "HalfPair.json").read_text())
gt = json.loads((PROJECT / "Content/locomotion/NN/prophecy_slash_half_gt.json").read_text())
steps = [json.loads(line) for line in (DIRECTORY / "live_steps.jsonl").open(encoding="utf-8-sig")]
grouped = collections.defaultdict(list)
for row in steps:
    grouped[(row["family"].lower(), row["time"])].append(row)
report = {"reason": capture["reason"], "events": capture["events"], "cases": {}}
assert capture["reason"] == "Complete"
for case, family in enumerate(("hookl", "headbutt", "slashl")):
    pairs = [v for (f, _), v in grouped.items() if f == family and len(v) == 2]
    assert pairs
    expected = np.asarray(gt["families"][family]["lower_previous"] + gt["families"][family]["lower_current"], dtype=np.float32)
    seed_error = max(float(np.max(np.abs(np.asarray(r["input"][:82]) - expected))) for r in pairs[0])
    input_error = max(float(np.max(np.abs(np.asarray(a["input"]) - b["input"]))) for a, b in pairs)
    output_error = max(float(np.max(np.abs(np.asarray(a["output"]) - b["output"]))) for a, b in pairs)
    presented = collections.defaultdict(list)
    for row in capture["rows"]:
        if row["case"] == case:
            presented[row["t"]].append(row)
    pos_error = rot_error = pelvis_angle = 0.0
    count = 0
    for rows in presented.values():
        a, b = rows
        if not a["attack"] or not b["attack"] or a["frame"] < 2:
            continue
        pa, pb = a["future"]["pelvis"], b["future"]["pelvis"]
        for name, x in a["future"].items():
            if name == "pelvis" or name.startswith(("thigh_", "calf_", "foot_", "ball_")):
                continue
            y = b["future"][name]
            error = np.asarray(x["p"]) - pa["p"] - np.asarray(y["p"]) + pb["p"]
            pos_error = max(pos_error, float(np.linalg.norm(error)))
            rot_error = max(rot_error, float((Rotation.from_quat(x["q"]).inv() * Rotation.from_quat(y["q"])).magnitude() * 180 / np.pi))
        pelvis_angle = max(pelvis_angle, float((Rotation.from_quat(pa["q"]).inv() * Rotation.from_quat(pb["q"])).magnitude() * 180 / np.pi))
        count += 1
    result = dict(paired_policy_steps=len(pairs), gt_lower_seed_max_error=seed_error,
                  input_max_error=input_error, output_max_error=output_error,
                  published_pairs=count, upper_position_max_mm=pos_error * 10,
                  upper_rotation_max_degrees=rot_error, real_pelvis_max_difference_degrees=pelvis_angle,
                  final_armed_hit=pairs[-1][0]["output"][431:433])
    assert seed_error == 0 and input_error < 1e-5 and output_error < 1e-5
    assert pos_error < 0.001 and rot_error < 0.001
    report["cases"][family] = result
report["root_displacement_cm"] = {}
for name in {r["actor"] for r in capture["rows"]}:
    rows = [r for r in capture["rows"] if r["actor"] == name]
    report["root_displacement_cm"][name] = (np.asarray(rows[-1]["root"]) - rows[0]["root"]).tolist()
report["passed"] = True
(DIRECTORY / "HalfPairSummary.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
