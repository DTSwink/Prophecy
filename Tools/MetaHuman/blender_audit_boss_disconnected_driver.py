"""Prove the fitted-bind disconnected-driver conversion without saving."""

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
    / "Boss_DisconnectedDriverAudit.json"
)

MESH = "boss"
SOURCE_RIG = "UEFN_WORKING_CLEAN_RIG.001"
NATIVE_RIG = "UEFN_NATIVE_EXPORT_RIG"
UEFN_FBX = (
    PROJECT
    / "Saved"
    / "BlenderExchange"
    / "ManualRig_UEFN_Mannequin_RigMesh.fbx"
)


def matrix_delta(left, right):
    return max(
        abs(left[row][column] - right[row][column])
        for row in range(4)
        for column in range(4)
    )


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
        "rms_m": math.sqrt(
            sum(distance * distance for distance in distances) / len(distances)
        ),
        "mean_m": sum(distances) / len(distances),
    }


def depth(bone):
    return len(bone.parent_recursive)


def import_auto_oriented_native_target():
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(
        filepath=str(UEFN_FBX),
        use_manual_orientation=False,
        global_scale=1.0,
        bake_space_transform=False,
        use_custom_normals=True,
        use_anim=False,
        ignore_leaf_bones=False,
        force_connect_children=False,
        automatic_bone_orientation=True,
        primary_bone_axis="Y",
        secondary_bone_axis="X",
        use_prepost_rot=True,
        axis_forward="-Z",
        axis_up="Y",
    )
    created = list(set(bpy.data.objects) - before)
    armatures = [obj for obj in created if obj.type == "ARMATURE"]
    if len(armatures) != 1:
        raise RuntimeError("Expected one auto-oriented UEFN target armature")
    return armatures[0]


def connect_primary_target_chains(rig):
    chains = [
        (
            "pelvis",
            "spine_01",
            "spine_02",
            "spine_03",
            "spine_04",
            "spine_05",
            "neck_01",
            "neck_02",
            "head",
        ),
    ]
    for side in ("l", "r"):
        chains.extend(
            [
                (
                    f"clavicle_{side}",
                    f"upperarm_{side}",
                    f"lowerarm_{side}",
                    f"hand_{side}",
                    f"middle_metacarpal_{side}",
                    f"middle_01_{side}",
                    f"middle_02_{side}",
                    f"middle_03_{side}",
                ),
                (
                    f"thigh_{side}",
                    f"calf_{side}",
                    f"foot_{side}",
                    f"ball_{side}",
                ),
                (
                    f"index_metacarpal_{side}",
                    f"index_01_{side}",
                    f"index_02_{side}",
                    f"index_03_{side}",
                ),
                (
                    f"pinky_metacarpal_{side}",
                    f"pinky_01_{side}",
                    f"pinky_02_{side}",
                    f"pinky_03_{side}",
                ),
                (
                    f"ring_metacarpal_{side}",
                    f"ring_01_{side}",
                    f"ring_02_{side}",
                    f"ring_03_{side}",
                ),
                (
                    f"thumb_01_{side}",
                    f"thumb_02_{side}",
                    f"thumb_03_{side}",
                ),
            ]
        )
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    rig.hide_set(False)
    rig.hide_viewport = False
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    edit_bones = rig.data.edit_bones
    for chain in chains:
        for parent_name, child_name in zip(chain, chain[1:]):
            parent = edit_bones[parent_name]
            child = edit_bones[child_name]
            parent.tail = child.head.copy()
            child.use_connect = True
    for side in ("l", "r"):
        foot = edit_bones[f"foot_{side}"]
        ball = edit_bones[f"ball_{side}"]
        direction = ball.head - foot.head
        if direction.length > 1.0e-8:
            ball.tail = ball.head + direction.normalized() * 4.0
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()


def disconnect_without_changing_rest(rig):
    before = {
        bone.name: bone.matrix_local.copy() for bone in rig.data.bones
    }
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    rig.hide_set(False)
    rig.hide_viewport = False
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    for bone in rig.data.edit_bones:
        bone.use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()
    return max(
        matrix_delta(matrix, rig.data.bones[name].matrix_local)
        for name, matrix in before.items()
    )


def main():
    if Path(bpy.data.filepath).resolve() != SOURCE.resolve():
        raise RuntimeError("Run on bossfinalsave.blend")
    scene = bpy.context.scene
    scene.frame_set(0)
    mesh = bpy.data.objects[MESH]
    source = bpy.data.objects[SOURCE_RIG]
    native = bpy.data.objects[NATIVE_RIG]
    if set(source.data.bones.keys()) != set(native.data.bones.keys()):
        raise RuntimeError("Source/native bone-name sets differ")

    source_surface = evaluated_positions(mesh)
    auto_native = import_auto_oriented_native_target()
    if set(source.data.bones.keys()) != set(auto_native.data.bones.keys()):
        raise RuntimeError("Source/auto-native bone-name sets differ")
    auto_native.animation_data_clear()
    for pose_bone in auto_native.pose.bones:
        pose_bone.matrix_basis.identity()
    connect_primary_target_chains(auto_native)
    bpy.context.view_layer.update()

    native_head_deltas = []
    for name in source.data.bones.keys():
        auto_head = (
            auto_native.matrix_world
            @ auto_native.data.bones[name].matrix_local
        ).translation
        native_head = (
            native.matrix_world
            @ native.data.bones[name].matrix_local
        ).translation
        native_head_deltas.append((auto_head - native_head).length)

    driver = source.copy()
    driver.data = source.data.copy()
    driver.name = "TEMP_BOSS_FITTED_BIND_DRIVER"
    driver.data.name = "TEMP_BOSS_FITTED_BIND_ARMATURE"
    scene.collection.objects.link(driver)
    driver.animation_data_clear()
    driver.parent = None
    driver.matrix_world = source.matrix_world.copy()
    for pose_bone in driver.pose.bones:
        pose_bone.matrix_basis.identity()
    bpy.context.view_layer.update()
    disconnect_rest_error = disconnect_without_changing_rest(driver)

    modifiers = [
        modifier for modifier in mesh.modifiers
        if modifier.type == "ARMATURE"
    ]
    if len(modifiers) != 1:
        raise RuntimeError("Boss does not have exactly one Armature modifier")
    modifiers[0].object = driver
    bpy.context.view_layer.update()
    bind_swap_error = position_delta(
        source_surface, evaluated_positions(mesh)
    )

    # Use the automatic-orientation import only as a target convention. It has
    # the same native UEFN joint heads as the untouched FBX rig, but its axes
    # match the already-skinned working rig. This avoids treating FBX tail
    # display axes as a real deformation.
    for pose_bone in driver.pose.bones:
        pose_bone.matrix_basis.identity()
    for bone in sorted(driver.data.bones, key=depth):
        driver.pose.bones[bone.name].matrix = (
            auto_native.data.bones[bone.name].matrix_local.copy()
        )
        bpy.context.view_layer.update()

    pose_rows = []
    for name in driver.data.bones.keys():
        actual = driver.pose.bones[name].matrix
        target = auto_native.data.bones[name].matrix_local
        pose_rows.append(
            {
                "bone": name,
                "matrix_delta": matrix_delta(actual, target),
                "head_delta_armature_units": (
                    actual.translation - target.translation
                ).length,
            }
        )
    target_surface = evaluated_positions(mesh)
    report = {
        "source": str(SOURCE),
        "method": (
            "duplicate_actual_boss_bind_armature_disconnect_only_then_pose_"
            "all_87_bones_to_auto_oriented_native_uefn_rest_target"
        ),
        "auto_oriented_target_vs_untouched_native_maximum_head_delta_m": max(
            native_head_deltas
        ),
        "driver_rest_matrix_change_from_disconnect": disconnect_rest_error,
        "surface_change_when_switching_modifier_to_identical_driver": (
            bind_swap_error
        ),
        "driver_pose_vs_native_rest": {
            "maximum_matrix_delta": max(
                row["matrix_delta"] for row in pose_rows
            ),
            "maximum_head_delta_armature_units": max(
                row["head_delta_armature_units"] for row in pose_rows
            ),
            "worst": sorted(
                pose_rows, key=lambda row: row["matrix_delta"], reverse=True
            )[:15],
        },
        "mesh_deformation_fitted_to_native": position_delta(
            source_surface, target_surface
        ),
        "target_bounds_m": {
            "minimum": [
                min(point[axis] for point in target_surface)
                for axis in range(3)
            ],
            "maximum": [
                max(point[axis] for point in target_surface)
                for axis in range(3)
            ],
        },
        "vertex_count": len(target_surface),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        "BOSS_DISCONNECTED_DRIVER_AUDIT="
        + json.dumps(
            {
                "output": str(OUTPUT),
                "disconnect_rest_error": disconnect_rest_error,
                "bind_swap_maximum_m": bind_swap_error["maximum_m"],
                "pose_matrix_maximum_delta": report[
                    "driver_pose_vs_native_rest"
                ]["maximum_matrix_delta"],
                "mesh_deformation_maximum_m": report[
                    "mesh_deformation_fitted_to_native"
                ]["maximum_m"],
            }
        )
    )


if __name__ == "__main__":
    main()
