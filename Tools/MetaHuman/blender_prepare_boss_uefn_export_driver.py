"""Build Boss on native UEFN rest by deforming the existing skinned asset.

The Boss mesh is already correctly skinned to its fitted Blender working rig.
This script duplicates that exact bind armature, disconnects only the
temporary driver's Blender connection flags, poses it to an auto-oriented
import of the native UEFN rest pose, and lets the existing Armature modifier
move the mesh. The evaluated result is then baked and rebound at identity to
the untouched native UEFN FBX armature.

No source edit bones, source vertices, source weights, or source file are
modified or saved.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
SOURCE = Path(r"C:\Users\singerie\Documents\Blender\bossfinalsave.blend")
UEFN_FBX = (
    PROJECT
    / "Saved"
    / "BlenderExchange"
    / "ManualRig_UEFN_Mannequin_RigMesh.fbx"
)
OUTPUT_DIR = PROJECT / "Saved" / "BlenderExchange" / "BossUEFN"
OUTPUT_BLEND = OUTPUT_DIR / "Boss_UEFN_ExportClean.blend"
OUTPUT_FBX = OUTPUT_DIR / "SKM_Boss_UEFN.fbx"
OUTPUT_AUDIT = OUTPUT_DIR / "Boss_UEFN_ExportAudit.json"

MESH_NAME = "boss"
BOUND_RIG_NAME = "UEFN_WORKING_CLEAN_RIG.001"
NATIVE_RIG_NAME = "UEFN_NATIVE_EXPORT_RIG"
EXPORT_MESH_NAME = "SKM_Boss_UEFN"
EXPORT_RIG_NAME = "root"
EXPECTED_BONES = 87
EXPECTED_VERTICES = 11374
MAX_INFLUENCES = 8

MATERIAL_LAYOUT = (
    ("body_shader_shader", 7, 15196),
    ("teeth_shader_shader", 0, 796),
    ("eyeLeft_shader_shader", 1, 216),
    ("eyeRight_shader_shader", 2, 216),
    ("eyeshell_shader_shader", 3, 196),
    ("eyeEdge_shader_shader", 4, 150),
    ("eyelashes_HiLOD_shader_shader", 5, 250),
    ("head_LOD3_shader_shader", 6, 5048),
)

sys.path.insert(0, str(Path(__file__).parent))
from blender_ue_export import ensure_cm_scene, export_skeletal_fbx


def require_object(name, object_type):
    obj = bpy.data.objects.get(name)
    if obj is None or obj.type != object_type:
        raise RuntimeError(f"Missing {object_type} object: {name}")
    return obj


def matrix_delta(left, right):
    return max(
        abs(left[row][column] - right[row][column])
        for row in range(4)
        for column in range(4)
    )


def hierarchy(rig):
    return {
        bone.name: bone.parent.name if bone.parent else None
        for bone in rig.data.bones
    }


def evaluated_world_positions(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    data = evaluated.to_mesh()
    try:
        if len(data.vertices) != len(obj.data.vertices):
            raise RuntimeError(
                f"Evaluated topology changed for {obj.name}: "
                f"{len(obj.data.vertices)} -> {len(data.vertices)}"
            )
        return [
            evaluated.matrix_world @ vertex.co for vertex in data.vertices
        ]
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


def normalized_vertex_weights(mesh, valid_bones):
    index_to_name = {
        group.index: group.name
        for group in mesh.vertex_groups
        if group.name in valid_bones
    }
    result = []
    for vertex in mesh.data.vertices:
        values = [
            (index_to_name[item.group], item.weight)
            for item in vertex.groups
            if (
                item.group in index_to_name
                and item.weight > 1.0e-10
            )
        ]
        values.sort(key=lambda item: item[1], reverse=True)
        values = values[:MAX_INFLUENCES]
        total = sum(weight for _name, weight in values)
        if total <= 1.0e-10:
            raise RuntimeError(f"Unweighted Boss vertex: {vertex.index}")
        result.append(
            {
                name: weight / total
                for name, weight in values
            }
        )
    return result


def write_normalized_weights(mesh, weights, valid_bones):
    for group in list(mesh.vertex_groups):
        if group.name not in valid_bones:
            mesh.vertex_groups.remove(group)
    groups = {
        name: mesh.vertex_groups.get(name)
        or mesh.vertex_groups.new(name=name)
        for name in sorted(valid_bones)
    }
    all_vertices = range(len(mesh.data.vertices))
    for group in groups.values():
        group.remove(all_vertices)
    for vertex_index, values in enumerate(weights):
        for name, weight in values.items():
            groups[name].add([vertex_index], weight, "REPLACE")


def weight_audit(mesh, valid_bones):
    group_names = {group.index: group.name for group in mesh.vertex_groups}
    zero = 0
    maximum_influences = 0
    maximum_sum_error = 0.0
    unknown = set()
    for vertex in mesh.data.vertices:
        memberships = [
            item for item in vertex.groups if item.weight > 1.0e-8
        ]
        total = sum(item.weight for item in memberships)
        zero += int(total <= 1.0e-8)
        maximum_influences = max(maximum_influences, len(memberships))
        if total > 1.0e-8:
            maximum_sum_error = max(
                maximum_sum_error, abs(total - 1.0)
            )
        for item in memberships:
            name = group_names[item.group]
            if name not in valid_bones:
                unknown.add(name)
    return {
        "vertices": len(mesh.data.vertices),
        "zero_weight_vertices": zero,
        "maximum_influences": maximum_influences,
        "maximum_weight_sum_error": maximum_sum_error,
        "unknown_groups": sorted(unknown),
    }


def repair_material_regions(mesh):
    old_indices = [polygon.material_index for polygon in mesh.data.polygons]
    old_to_new = {
        old_index: new_index
        for new_index, (_name, old_index, _count) in enumerate(MATERIAL_LAYOUT)
    }
    unknown = sorted(set(old_indices) - set(old_to_new))
    if unknown:
        raise RuntimeError(f"Unexpected Boss material indices: {unknown}")
    mesh.data.materials.clear()
    for name, _old_index, _count in MATERIAL_LAYOUT:
        material = bpy.data.materials.get(name)
        if material is None:
            material = bpy.data.materials.new(name=name)
        mesh.data.materials.append(material)
    for polygon, old_index in zip(mesh.data.polygons, old_indices):
        polygon.material_index = old_to_new[old_index]
    mesh.data.update()
    counts = [
        sum(polygon.material_index == index for polygon in mesh.data.polygons)
        for index in range(len(MATERIAL_LAYOUT))
    ]
    expected = [count for _name, _old, count in MATERIAL_LAYOUT]
    if counts != expected:
        raise RuntimeError(f"Material-region counts changed: {counts}")
    return [
        {
            "index": index,
            "slot_name": name,
            "polygon_count": counts[index],
        }
        for index, (name, _old, _count) in enumerate(MATERIAL_LAYOUT)
    ]


def prepare_smooth_normals(mesh):
    custom_normal = mesh.data.attributes.get("custom_normal")
    if custom_normal:
        mesh.data.attributes.remove(custom_normal)
    sharp_edge = mesh.data.attributes.get("sharp_edge")
    if sharp_edge:
        mesh.data.attributes.remove(sharp_edge)
    for polygon in mesh.data.polygons:
        polygon.use_smooth = True
    for edge in mesh.data.edges:
        edge.use_edge_sharp = False
    mesh.data.update()


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
    rigs = [obj for obj in created if obj.type == "ARMATURE"]
    if len(rigs) != 1:
        raise RuntimeError("Expected one auto-oriented UEFN target rig")
    return rigs[0], created


def connect_primary_target_chains(rig):
    """Match the Blender-only orientation convention of the Boss bind rig."""
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


def duplicate_disconnected_bind_driver(source):
    driver = source.copy()
    driver.data = source.data.copy()
    driver.name = "TEMP_BOSS_FITTED_BIND_DRIVER"
    driver.data.name = "TEMP_BOSS_FITTED_BIND_ARMATURE"
    bpy.context.scene.collection.objects.link(driver)
    driver.animation_data_clear()
    driver.parent = None
    driver.matrix_world = source.matrix_world.copy()
    for pose_bone in driver.pose.bones:
        pose_bone.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()

    before = {
        bone.name: bone.matrix_local.copy() for bone in driver.data.bones
    }
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    driver.hide_set(False)
    driver.hide_viewport = False
    driver.select_set(True)
    bpy.context.view_layer.objects.active = driver
    bpy.ops.object.mode_set(mode="EDIT")
    for bone in driver.data.edit_bones:
        bone.use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()
    rest_error = max(
        matrix_delta(matrix, driver.data.bones[name].matrix_local)
        for name, matrix in before.items()
    )
    return driver, rest_error


def bone_depth(bone):
    return len(bone.parent_recursive)


def pose_driver_to_target(driver, target):
    for pose_bone in driver.pose.bones:
        pose_bone.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    for bone in sorted(driver.data.bones, key=bone_depth):
        driver.pose.bones[bone.name].matrix = (
            target.data.bones[bone.name].matrix_local.copy()
        )
        bpy.context.view_layer.update()
    rows = [
        matrix_delta(
            driver.pose.bones[name].matrix,
            target.data.bones[name].matrix_local,
        )
        for name in driver.data.bones.keys()
    ]
    return max(rows)


def bake_world_positions(mesh, world_positions):
    world_inverse = mesh.matrix_world.inverted_safe()
    for vertex, world_position in zip(
        mesh.data.vertices, world_positions
    ):
        vertex.co = world_inverse @ world_position
    mesh.data.update()


def remove_armature_modifiers(mesh):
    for modifier in list(mesh.modifiers):
        if modifier.type == "ARMATURE":
            mesh.modifiers.remove(modifier)


def detach_preserving_world(obj):
    world = obj.matrix_world.copy()
    obj.parent = None
    obj.matrix_world = world


def bind_to_rig(mesh, rig):
    remove_armature_modifiers(mesh)
    mesh_world = mesh.matrix_world.copy()
    mesh.parent = rig
    mesh.matrix_parent_inverse = rig.matrix_world.inverted_safe()
    mesh.matrix_world = mesh_world
    modifier = mesh.modifiers.new("UEFN Native Skeleton", "ARMATURE")
    modifier.object = rig
    modifier.use_vertex_groups = True
    modifier.use_bone_envelopes = False
    modifier.use_deform_preserve_volume = False


def clear_pose(rig):
    rig.animation_data_clear()
    for pose_bone in rig.pose.bones:
        pose_bone.matrix_basis = Matrix.Identity(4)
    rig.data.pose_position = "POSE"
    bpy.context.view_layer.update()


def remove_everything_except(keep):
    for obj in list(bpy.data.objects):
        if obj not in keep:
            bpy.data.objects.remove(obj, do_unlink=True)
    for collection in list(bpy.data.collections):
        if collection.users == 0:
            bpy.data.collections.remove(collection)


def add_readme(audit):
    text = bpy.data.texts.get("README_BOSS_UEFN_EXPORT")
    if text is None:
        text = bpy.data.texts.new("README_BOSS_UEFN_EXPORT")
    text.clear()
    text.write(
        "BOSS - NATIVE UEFN SKELETAL EXPORT\n\n"
        "This clean file contains only the untouched native-rest UEFN\n"
        "armature and the Boss mesh deformed into that exact pose.\n\n"
        "METHOD\n"
        "- The existing Boss skin and fitted bind rig were used directly.\n"
        "- A temporary disconnected duplicate was posed as one complete rig\n"
        "  to Blender's auto-oriented view of native UEFN rest.\n"
        "- The Armature modifier moved the mesh; no inverse-skin vertex solve\n"
        "  and no manual joint correction was used.\n"
        "- The evaluated mesh was baked, then rebound at identity to the\n"
        "  untouched native FBX rig. The temporary driver was discarded.\n\n"
        "Do not enable Automatic Bone Orientation on the export rig.\n\n"
        + json.dumps(audit, indent=2, sort_keys=True)
    )


def main():
    if Path(bpy.data.filepath).resolve() != SOURCE.resolve():
        raise RuntimeError(f"Unexpected source file: {bpy.data.filepath}")
    if not UEFN_FBX.is_file():
        raise RuntimeError(f"Missing native UEFN FBX: {UEFN_FBX}")
    scene = bpy.context.scene
    scene.frame_set(0)
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    mesh = require_object(MESH_NAME, "MESH")
    bound_rig = require_object(BOUND_RIG_NAME, "ARMATURE")
    native_rig = require_object(NATIVE_RIG_NAME, "ARMATURE")
    if len(mesh.data.vertices) != EXPECTED_VERTICES:
        raise RuntimeError(
            f"Unexpected Boss topology: {len(mesh.data.vertices)}"
        )
    names = {bone.name for bone in native_rig.data.bones}
    if len(names) != EXPECTED_BONES:
        raise RuntimeError(f"Unexpected native bone count: {len(names)}")
    if names != {bone.name for bone in bound_rig.data.bones}:
        raise RuntimeError("Boss bind/native bone-name sets differ")
    if hierarchy(native_rig) != hierarchy(bound_rig):
        raise RuntimeError("Boss bind/native hierarchies differ")
    modifiers = [
        modifier for modifier in mesh.modifiers
        if modifier.type == "ARMATURE"
    ]
    if len(modifiers) != 1 or modifiers[0].object != bound_rig:
        raise RuntimeError(
            "Boss is not driven by its expected fitted working rig"
        )

    source_surface = evaluated_world_positions(mesh)
    weights = normalized_vertex_weights(mesh, names)
    native_rest_before = {
        bone.name: bone.matrix_local.copy()
        for bone in native_rig.data.bones
    }

    auto_native, _auto_objects = import_auto_oriented_native_target()
    if names != {bone.name for bone in auto_native.data.bones}:
        raise RuntimeError("Auto-oriented target bone-name set differs")
    clear_pose(auto_native)
    connect_primary_target_chains(auto_native)
    head_deltas = [
        (
            (
                auto_native.matrix_world
                @ auto_native.data.bones[name].matrix_local
            ).translation
            - (
                native_rig.matrix_world
                @ native_rig.data.bones[name].matrix_local
            ).translation
        ).length
        for name in names
    ]
    auto_native_head_delta = max(head_deltas)
    if auto_native_head_delta > 2.0e-6:
        raise RuntimeError(
            "Auto-oriented native target changed UEFN joint heads: "
            + str(auto_native_head_delta)
        )

    driver, disconnect_rest_error = duplicate_disconnected_bind_driver(
        bound_rig
    )
    modifiers[0].object = driver
    bpy.context.view_layer.update()
    driver_bind_swap = position_delta(
        source_surface, evaluated_world_positions(mesh)
    )
    if driver_bind_swap["maximum_m"] > 2.0e-6:
        raise RuntimeError(
            "Temporary driver does not reproduce Boss bind: "
            + str(driver_bind_swap)
        )

    driver_pose_error = pose_driver_to_target(driver, auto_native)
    if driver_pose_error > 5.0e-5:
        raise RuntimeError(
            "Temporary driver did not reach native target: "
            + str(driver_pose_error)
        )
    target_surface = evaluated_world_positions(mesh)
    source_to_native = position_delta(source_surface, target_surface)

    # Freeze exactly what the existing Armature modifier produced.
    bake_world_positions(mesh, target_surface)
    remove_armature_modifiers(mesh)
    detach_preserving_world(mesh)
    write_normalized_weights(mesh, weights, names)
    material_report = repair_material_regions(mesh)
    prepare_smooth_normals(mesh)

    # Rebind to the authoritative untouched FBX skeleton at identity.
    clear_pose(native_rig)
    detach_preserving_world(native_rig)
    bind_to_rig(mesh, native_rig)
    bpy.context.view_layer.update()
    native_rebind = position_delta(
        target_surface, evaluated_world_positions(mesh)
    )
    if native_rebind["maximum_m"] > 2.0e-6:
        raise RuntimeError(
            "Native-rest rebind moved the baked Boss mesh: "
            + str(native_rebind)
        )
    native_rest_error = max(
        matrix_delta(matrix, native_rig.data.bones[name].matrix_local)
        for name, matrix in native_rest_before.items()
    )
    if native_rest_error > 1.0e-8:
        raise RuntimeError("Authoritative native rest matrices changed")

    weights_report = weight_audit(mesh, names)
    if (
        weights_report["zero_weight_vertices"]
        or weights_report["unknown_groups"]
        or weights_report["maximum_influences"] > MAX_INFLUENCES
        or weights_report["maximum_weight_sum_error"] > 1.0e-5
    ):
        raise RuntimeError("Boss export weights failed: " + str(weights_report))

    # Promote the imported centimeter wrapper scale into the isolated scene.
    # With scale_length=0.01 this exports a ~167 cm character to Unreal.
    native_rig.scale = tuple(value * 100.0 for value in native_rig.scale)
    bpy.context.view_layer.update()

    mesh.name = EXPORT_MESH_NAME
    mesh.data.name = EXPORT_MESH_NAME + "_Geometry"
    native_rig.name = EXPORT_RIG_NAME
    native_rig.data.name = "UEFN_Native_Export_Armature"
    native_rig.hide_set(False)
    native_rig.hide_viewport = False
    native_rig.hide_render = False
    native_rig.data.display_type = "STICK"
    native_rig.show_in_front = True
    mesh.hide_set(False)
    mesh.hide_viewport = False
    mesh.hide_render = False
    remove_everything_except({mesh, native_rig})
    ensure_cm_scene()
    scene.frame_start = 0
    scene.frame_end = 0
    scene.frame_set(0)

    audit = {
        "source_blend": str(SOURCE),
        "source_file_saved_or_modified": False,
        "native_uefn_fbx": str(UEFN_FBX),
        "output_blend": str(OUTPUT_BLEND),
        "output_fbx": str(OUTPUT_FBX),
        "method": (
            "existing_skinned_boss_armature_modifier_driven_by_"
            "temporary_disconnected_fitted_bind_driver_to_auto_oriented_"
            "native_uefn_rest_then_baked_and_rebound_to_untouched_native_rig"
        ),
        "inverse_skinning_used": False,
        "manual_bone_adjustments_used": False,
        "source_geometry_edits_used": False,
        "bone_count": len(native_rig.data.bones),
        "bone_names": [bone.name for bone in native_rig.data.bones],
        "hierarchy": hierarchy(native_rig),
        "temporary_driver_disconnect_rest_matrix_delta": (
            disconnect_rest_error
        ),
        "temporary_driver_bind_swap_surface_delta": driver_bind_swap,
        "temporary_driver_pose_matrix_maximum_delta": driver_pose_error,
        "auto_oriented_target_vs_native_joint_head_maximum_delta_m": (
            auto_native_head_delta
        ),
        "source_fitted_to_native_surface_deformation": source_to_native,
        "native_rest_rebind_surface_delta": native_rebind,
        "native_rest_matrix_delta": native_rest_error,
        "vertex_count": len(mesh.data.vertices),
        "polygon_count": len(mesh.data.polygons),
        "materials": material_report,
        "weight_audit": weights_report,
        "centimeter_wrapper_scale_promoted": 100.0,
        "clean_scene_object_names": sorted(
            obj.name for obj in bpy.data.objects
        ),
    }
    add_readme(audit)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(
        filepath=str(OUTPUT_BLEND), check_existing=False
    )
    export_skeletal_fbx(str(OUTPUT_FBX), native_rig, [mesh])
    if not OUTPUT_FBX.is_file() or OUTPUT_FBX.stat().st_size < 100_000:
        raise RuntimeError("FBX export missing or implausibly small")
    audit["fbx_bytes"] = OUTPUT_FBX.stat().st_size
    OUTPUT_AUDIT.write_text(
        json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(
        "BOSS_UEFN_DRIVER_EXPORT_COMPLETE="
        + json.dumps(
            {
                "blend": str(OUTPUT_BLEND),
                "fbx": str(OUTPUT_FBX),
                "audit": str(OUTPUT_AUDIT),
                "bind_swap_maximum_m": driver_bind_swap["maximum_m"],
                "native_rebind_maximum_m": native_rebind["maximum_m"],
                "driver_pose_matrix_maximum_delta": driver_pose_error,
                "fbx_bytes": OUTPUT_FBX.stat().st_size,
            }
        )
    )


if __name__ == "__main__":
    main()
