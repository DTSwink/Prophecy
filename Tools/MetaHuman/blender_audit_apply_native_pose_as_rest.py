"""Audit Blender's Apply Pose as Rest operation on the fitted UEFN rig."""

import json
from pathlib import Path

import bpy


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
OUTPUT = (
    PROJECT
    / "Saved"
    / "BlenderExchange"
    / "BossUEFN"
    / "Boss_ApplyFittedPoseAudit.json"
)


def matrix_delta(left, right):
    return max(
        abs(left[row][column] - right[row][column])
        for row in range(4)
        for column in range(4)
    )


rig = bpy.data.objects["UEFN_NATIVE_EXPORT_RIG"]
if bpy.context.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")
before = {
    pose_bone.name: {
        "matrix": pose_bone.matrix.copy(),
        "head": pose_bone.head.copy(),
        "tail": pose_bone.tail.copy(),
    }
    for pose_bone in rig.pose.bones
}
bpy.ops.object.select_all(action="DESELECT")
rig.hide_set(False)
rig.hide_viewport = False
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="POSE")
bpy.ops.pose.armature_apply(selected=False)
bpy.ops.object.mode_set(mode="OBJECT")
bpy.context.view_layer.update()

details = []
for bone in rig.data.bones:
    source = before[bone.name]
    details.append(
        {
            "bone": bone.name,
            "matrix_delta": matrix_delta(
                bone.matrix_local, source["matrix"]
            ),
            "head_delta_m": (bone.head_local - source["head"]).length,
            "tail_delta_m": (bone.tail_local - source["tail"]).length,
        }
    )
report = {
    "maximum_matrix_delta": max(
        item["matrix_delta"] for item in details
    ),
    "maximum_head_delta_m": max(
        item["head_delta_m"] for item in details
    ),
    "maximum_tail_delta_m": max(
        item["tail_delta_m"] for item in details
    ),
    "worst_matrix": sorted(
        details, key=lambda item: item["matrix_delta"], reverse=True
    )[:12],
    "worst_head": sorted(
        details, key=lambda item: item["head_delta_m"], reverse=True
    )[:12],
}
OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
print("BOSS_APPLY_FITTED_POSE_AUDIT=" + json.dumps(report))
