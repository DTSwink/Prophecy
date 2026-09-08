"""Find the stored UEFN pose that matches Boss's fitted working bind joints."""

from __future__ import annotations

import json
import math
from pathlib import Path

import bpy


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
SOURCE = Path(r"C:\Users\singerie\Documents\Blender\bossfinalsave.blend")
OUTPUT = (
    PROJECT
    / "Saved"
    / "BlenderExchange"
    / "BossUEFN"
    / "Boss_BindDriverCandidates.json"
)
BOUND_RIG = "UEFN_WORKING_CLEAN_RIG.001"
CANDIDATES = (
    "UEFN_NATIVE_EXPORT_RIG",
    "SOURCE_UEFN_ModifiedPose_root",
    "UEFN_WORKING_CLEAN_RIG",
)


def bone_world_matrix(rig, name, state):
    matrix = (
        rig.data.bones[name].matrix_local
        if state == "REST"
        else rig.pose.bones[name].matrix
    )
    return rig.matrix_world @ matrix


def pair_report(bound, candidate, candidate_state):
    shared = sorted(
        set(bound.data.bones.keys()) & set(candidate.data.bones.keys())
    )
    rows = []
    for name in shared:
        expected = bone_world_matrix(bound, name, "REST")
        actual = bone_world_matrix(candidate, name, candidate_state)
        head_delta = (expected.translation - actual.translation).length
        rotation_delta = math.degrees(
            expected.to_quaternion().rotation_difference(
                actual.to_quaternion()
            ).angle
        )
        rows.append(
            {
                "bone": name,
                "head_delta_m": head_delta,
                "rotation_delta_deg": rotation_delta,
            }
        )
    return {
        "candidate": candidate.name,
        "state": candidate_state,
        "shared_bones": len(shared),
        "maximum_head_delta_m": max(row["head_delta_m"] for row in rows),
        "rms_head_delta_m": math.sqrt(
            sum(row["head_delta_m"] ** 2 for row in rows) / len(rows)
        ),
        "maximum_rotation_delta_deg": max(
            row["rotation_delta_deg"] for row in rows
        ),
        "worst_heads": sorted(
            rows, key=lambda row: row["head_delta_m"], reverse=True
        )[:15],
    }


def main():
    if Path(bpy.data.filepath).resolve() != SOURCE.resolve():
        raise RuntimeError("Run on bossfinalsave.blend")
    bpy.context.scene.frame_set(0)
    bpy.context.view_layer.update()
    bound = bpy.data.objects[BOUND_RIG]
    reports = []
    for name in CANDIDATES:
        candidate = bpy.data.objects.get(name)
        if candidate is None:
            continue
        reports.append(pair_report(bound, candidate, "REST"))
        reports.append(pair_report(bound, candidate, "POSE"))
    reports.sort(key=lambda row: row["maximum_head_delta_m"])
    payload = {
        "source": str(SOURCE),
        "bound_rig": BOUND_RIG,
        "candidates": reports,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(
        "BOSS_BIND_DRIVER_CANDIDATE="
        + json.dumps(
            {
                "output": str(OUTPUT),
                "best": reports[0],
            }
        )
    )


if __name__ == "__main__":
    main()
