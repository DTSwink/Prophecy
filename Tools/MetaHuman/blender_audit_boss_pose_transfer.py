"""Read-only audit of the fitted working rig -> native UEFN pose transfer."""

from __future__ import annotations

import json
from pathlib import Path

import bpy
from mathutils import Matrix


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
SOURCE = Path(r"C:\Users\singerie\Documents\Blender\bossfinalsave.blend")
OUTPUT = (
    PROJECT
    / "Saved"
    / "BlenderExchange"
    / "BossUEFN"
    / "Boss_WorkingToNativePoseAudit.json"
)

MESH = "boss"
WORKING = "UEFN_WORKING_CLEAN_RIG.001"
NATIVE = "UEFN_NATIVE_EXPORT_RIG"


def matrix_delta(left, right):
    return max(
        abs(left[row][column] - right[row][column])
        for row in range(4)
        for column in range(4)
    )


def matrix_rows(matrix):
    return [[float(value) for value in row] for row in matrix]


def evaluated_positions(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    data = evaluated.to_mesh()
    try:
        return [evaluated.matrix_world @ vertex.co for vertex in data.vertices]
    finally:
        evaluated.to_mesh_clear()


def position_delta(left, right):
    distances = [(a - b).length for a, b in zip(left, right)]
    return {
        "maximum_m": max(distances),
        "mean_m": sum(distances) / len(distances),
    }


def bone_depth(bone):
    result = 0
    while bone.parent:
        result += 1
        bone = bone.parent
    return result


def main():
    if Path(bpy.data.filepath).resolve() != SOURCE.resolve():
        raise RuntimeError("Run this audit on bossfinalsave.blend")

    scene = bpy.context.scene
    scene.frame_set(0)
    mesh = bpy.data.objects[MESH]
    working = bpy.data.objects[WORKING]
    native = bpy.data.objects[NATIVE]
    bpy.context.view_layer.update()

    names = {bone.name for bone in working.data.bones}
    if names != {bone.name for bone in native.data.bones}:
        raise RuntimeError("Working/native bone sets differ")

    original_surface = evaluated_positions(mesh)
    original_pose = {
        bone.name: bone.matrix_basis.copy() for bone in working.pose.bones
    }
    original_pose_position = working.data.pose_position

    fitted_comparison = []
    for name in sorted(names):
        working_rest = working.data.bones[name].matrix_local
        native_fitted = native.pose.bones[name].matrix
        fitted_comparison.append(
            {
                "bone": name,
                "matrix_delta": matrix_delta(working_rest, native_fitted),
                "head_delta_m": (
                    working_rest.translation - native_fitted.translation
                ).length
                * working.matrix_world.to_scale().length
                / (3.0 ** 0.5),
            }
        )

    # This is the systematic operation under test: pose the already-skinned
    # working armature to the complete native UEFN rest matrices. No edit-bone
    # positions, mesh vertices, weights, or bone tails are changed.
    for pose_bone in working.pose.bones:
        pose_bone.matrix_basis = Matrix.Identity(4)
    working.data.pose_position = "POSE"
    bpy.context.view_layer.update()
    target_pose = {
        bone.name: native.data.bones[bone.name].matrix_local.copy()
        for bone in working.data.bones
    }
    for bone in sorted(working.data.bones, key=bone_depth):
        if bone.parent:
            rest_from_parent = (
                bone.parent.matrix_local.inverted_safe()
                @ bone.matrix_local
            )
            basis = (
                target_pose[bone.parent.name]
                @ rest_from_parent
            ).inverted_safe() @ target_pose[bone.name]
        else:
            basis = (
                bone.matrix_local.inverted_safe() @ target_pose[bone.name]
            )
        working.pose.bones[bone.name].matrix_basis = basis
        bpy.context.view_layer.update()
    bpy.context.view_layer.update()

    transferred_comparison = []
    for name in sorted(names):
        actual = working.pose.bones[name].matrix
        target = native.data.bones[name].matrix_local
        transferred_comparison.append(
            {
                "bone": name,
                "matrix_delta": matrix_delta(actual, target),
                "head_delta_armature_units": (
                    actual.translation - target.translation
                ).length,
            }
        )
    native_surface = evaluated_positions(mesh)

    report = {
        "source": str(SOURCE),
        "working_pose_position_on_open": original_pose_position,
        "mesh_armature_modifier": [
            modifier.object.name
            for modifier in mesh.modifiers
            if modifier.type == "ARMATURE" and modifier.object
        ],
        "working_native_object_matrix_delta": matrix_delta(
            working.matrix_world, native.matrix_world
        ),
        "working_rest_vs_stored_native_fitted_pose": {
            "maximum_matrix_delta": max(
                item["matrix_delta"] for item in fitted_comparison
            ),
            "maximum_head_delta_m": max(
                item["head_delta_m"] for item in fitted_comparison
            ),
            "worst": sorted(
                fitted_comparison,
                key=lambda item: item["matrix_delta"],
                reverse=True,
            )[:20],
        },
        "working_pose_vs_native_rest_after_full_pose_transfer": {
            "maximum_matrix_delta": max(
                item["matrix_delta"] for item in transferred_comparison
            ),
            "maximum_head_delta_armature_units": max(
                item["head_delta_armature_units"]
                for item in transferred_comparison
            ),
            "worst": sorted(
                transferred_comparison,
                key=lambda item: item["matrix_delta"],
                reverse=True,
            )[:20],
            "debug": {
                name: {
                    "working_rest": matrix_rows(
                        working.data.bones[name].matrix_local
                    ),
                    "target": matrix_rows(target_pose[name]),
                    "actual": matrix_rows(working.pose.bones[name].matrix),
                    "basis": matrix_rows(
                        working.pose.bones[name].matrix_basis
                    ),
                    "inherit_scale": working.data.bones[name].inherit_scale,
                    "use_local_location": (
                        working.data.bones[name].use_local_location
                    ),
                    "use_inherit_rotation": (
                        working.data.bones[name].use_inherit_rotation
                    ),
                }
                for name in (
                    "pelvis",
                    "spine_01",
                    "clavicle_l",
                    "upperarm_l",
                    "lowerarm_l",
                    "hand_l",
                    "index_01_l",
                )
            },
        },
        "mesh_deformation_from_fitted_to_native_pose": position_delta(
            original_surface, native_surface
        ),
        "vertex_count": len(native_surface),
    }

    # Restore the source scene in memory. This script never saves.
    for name, basis in original_pose.items():
        working.pose.bones[name].matrix_basis = basis
    working.data.pose_position = original_pose_position
    bpy.context.view_layer.update()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        "BOSS_POSE_TRANSFER_AUDIT="
        + json.dumps(
            {
                "output": str(OUTPUT),
                "pose_matrix_maximum_delta": report[
                    "working_pose_vs_native_rest_after_full_pose_transfer"
                ]["maximum_matrix_delta"],
                "mesh_maximum_deformation_m": report[
                    "mesh_deformation_from_fitted_to_native_pose"
                ]["maximum_m"],
            }
        )
    )


if __name__ == "__main__":
    main()
