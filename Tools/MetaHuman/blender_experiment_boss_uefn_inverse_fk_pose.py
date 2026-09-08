"""Move Boss to UEFN rest by applying only the inverse saved UEFN FK pose.

No vertex weights, edit bones, or source geometry are changed. The Boss-bound
armature keeps its own bind proportions; it receives the exact inverse
per-bone deformation carried by the source file's authoritative native UEFN
rig, then the evaluated mesh is baked and rebound to the native rest rig.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blender_prepare_boss_uefn_export_driver as d


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
OUT_DIR = PROJECT / "Saved" / "BlenderExchange" / "BossUEFN"
OUTPUT_BLEND = OUT_DIR / "Boss_UEFN_ExportClean_InverseFK.blend"
OUTPUT_FBX = OUT_DIR / "SKM_Boss_UEFN_InverseFK.fbx"
OUTPUT_AUDIT = OUT_DIR / "Boss_UEFN_InverseFKExportAudit.json"


def local_rest_matrix(bone):
    if bone.parent is None:
        return bone.matrix_local.copy()
    return bone.parent.matrix_local.inverted_safe() @ bone.matrix_local


def pose_driver_with_canonical_local_delta(driver, canonical_fit, native_target):
    """Apply canonical fitted-UEFN -> native-UEFN local deltas to Boss."""
    desired = {}
    local_deltas = {}
    for bone in sorted(driver.data.bones, key=d.bone_depth):
        name = bone.name
        fitted_local = local_rest_matrix(
            canonical_fit.data.bones[name]
        )
        native_local = local_rest_matrix(
            native_target.data.bones[name]
        )
        delta = native_local @ fitted_local.inverted_safe()
        local_deltas[name] = delta
        boss_local = local_rest_matrix(bone)
        desired_local = delta @ boss_local
        if bone.parent is None:
            desired[name] = desired_local
        else:
            desired[name] = (
                desired[bone.parent.name] @ desired_local
            )

    for pose_bone in driver.pose.bones:
        pose_bone.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    for bone in sorted(driver.data.bones, key=d.bone_depth):
        driver.pose.bones[bone.name].matrix = desired[bone.name]
        bpy.context.view_layer.update()

    maximum_error = max(
        d.matrix_delta(driver.pose.bones[name].matrix, matrix)
        for name, matrix in desired.items()
    )
    local_delta_scale_error = max(
        max(
            abs(value - 1.0)
            for value in delta.to_scale()
        )
        for delta in local_deltas.values()
    )
    return maximum_error, local_delta_scale_error


def main():
    if Path(bpy.data.filepath).resolve() != d.SOURCE.resolve():
        raise RuntimeError(f"Unexpected source file: {bpy.data.filepath}")
    scene = bpy.context.scene
    scene.frame_set(0)
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    mesh = d.require_object(d.MESH_NAME, "MESH")
    bound_rig = d.require_object(d.BOUND_RIG_NAME, "ARMATURE")
    native_rig = d.require_object(d.NATIVE_RIG_NAME, "ARMATURE")
    canonical_fit = d.require_object("UEFN_WORKING_CLEAN_RIG", "ARMATURE")
    names = {bone.name for bone in native_rig.data.bones}
    modifiers = [
        modifier for modifier in mesh.modifiers
        if modifier.type == "ARMATURE"
    ]
    if len(modifiers) != 1 or modifiers[0].object != bound_rig:
        raise RuntimeError("Boss is not bound to expected fitted rig")

    source_surface = d.evaluated_world_positions(mesh)
    weights = d.normalized_vertex_weights(mesh, names)
    native_rest_before = {
        bone.name: bone.matrix_local.copy()
        for bone in native_rig.data.bones
    }
    native_target, _target_objects = d.import_auto_oriented_native_target()
    d.clear_pose(native_target)
    d.connect_primary_target_chains(native_target)
    d.clear_pose(canonical_fit)
    if (
        {bone.name for bone in canonical_fit.data.bones} != names
        or {bone.name for bone in native_target.data.bones} != names
    ):
        raise RuntimeError("Canonical/target bone sets differ")

    driver, disconnect_error = d.duplicate_disconnected_bind_driver(
        bound_rig
    )
    modifiers[0].object = driver
    bpy.context.view_layer.update()
    bind_swap = d.position_delta(
        source_surface, d.evaluated_world_positions(mesh)
    )
    if bind_swap["maximum_m"] > 2.0e-6:
        raise RuntimeError("Disconnected driver changed Boss bind surface")

    pose_error, local_delta_scale_error = (
        pose_driver_with_canonical_local_delta(
            driver, canonical_fit, native_target
        )
    )
    if pose_error > 5.0e-5:
        raise RuntimeError(
            f"Inverse FK pose assignment failed: {pose_error}"
        )
    target_surface = d.evaluated_world_positions(mesh)
    source_to_target = d.position_delta(source_surface, target_surface)

    d.bake_world_positions(mesh, target_surface)
    d.remove_armature_modifiers(mesh)
    d.detach_preserving_world(mesh)
    d.write_normalized_weights(mesh, weights, names)
    materials = d.repair_material_regions(mesh)
    d.prepare_smooth_normals(mesh)

    d.clear_pose(native_rig)
    d.detach_preserving_world(native_rig)
    d.bind_to_rig(mesh, native_rig)
    bpy.context.view_layer.update()
    rebind = d.position_delta(
        target_surface, d.evaluated_world_positions(mesh)
    )
    if rebind["maximum_m"] > 2.0e-6:
        raise RuntimeError("Native rebind moved inverse-FK surface")
    rest_error = max(
        d.matrix_delta(matrix, native_rig.data.bones[name].matrix_local)
        for name, matrix in native_rest_before.items()
    )
    if rest_error > 1.0e-8:
        raise RuntimeError("Native UEFN rest matrices changed")
    weight_report = d.weight_audit(mesh, names)

    native_rig.scale = tuple(value * 100.0 for value in native_rig.scale)
    bpy.context.view_layer.update()
    mesh.name = d.EXPORT_MESH_NAME
    mesh.data.name = d.EXPORT_MESH_NAME + "_Geometry"
    native_rig.name = d.EXPORT_RIG_NAME
    native_rig.data.name = "UEFN_Native_Export_Armature"
    native_rig.hide_set(False)
    native_rig.hide_viewport = False
    native_rig.hide_render = False
    native_rig.data.display_type = "STICK"
    native_rig.show_in_front = True
    mesh.hide_set(False)
    mesh.hide_viewport = False
    mesh.hide_render = False
    d.remove_everything_except({mesh, native_rig})
    d.ensure_cm_scene()
    scene.frame_start = 0
    scene.frame_end = 0
    scene.frame_set(0)

    report = {
        "source_blend": str(d.SOURCE),
        "source_file_saved_or_modified": False,
        "output_blend": str(OUTPUT_BLEND),
        "output_fbx": str(OUTPUT_FBX),
        "method": (
            "existing_boss_skin_moved_by_canonical_fitted_uefn_to_native_"
            "uefn_local_pose_deltas_then_baked_and_rebound_to_native_rest"
        ),
        "weights_changed": False,
        "edit_bones_changed": False,
        "source_geometry_changed": False,
        "temporary_driver_disconnect_rest_matrix_delta": disconnect_error,
        "temporary_driver_bind_swap_surface_delta": bind_swap,
        "canonical_local_delta_scale_maximum_error": (
            local_delta_scale_error
        ),
        "canonical_local_delta_driver_pose_matrix_maximum_delta": pose_error,
        "source_to_uefn_rest_surface_deformation": source_to_target,
        "native_rest_rebind_surface_delta": rebind,
        "native_rest_matrix_delta": rest_error,
        "vertex_count": len(mesh.data.vertices),
        "polygon_count": len(mesh.data.polygons),
        "materials": materials,
        "weight_audit": weight_report,
    }
    d.add_readme(report)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(
        filepath=str(OUTPUT_BLEND), check_existing=False
    )
    d.export_skeletal_fbx(str(OUTPUT_FBX), native_rig, [mesh])
    report["fbx_bytes"] = OUTPUT_FBX.stat().st_size
    OUTPUT_AUDIT.write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print("BOSS_INVERSE_FK_COMPLETE=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
