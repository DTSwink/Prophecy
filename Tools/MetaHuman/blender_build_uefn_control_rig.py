"""Build a usable Rigify control rig over the untouched UEFN deform skeleton.

The UEFN FBX armature must keep its imported rest matrices for Unreal
compatibility.  UE to Rigify therefore drives that source/deform armature from
a separate Blender-native control rig.  The source armature is hidden in the
finished file; it remains the armature bound to the UEFN mesh.
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
EXCHANGE = PROJECT / "Saved" / "BlenderExchange"
SHOTS = PROJECT / "Saved" / "BlenderShots"
SOURCE_BLEND = EXCHANGE / "ManualRig_UEFN_Posed_with_ally2_Meshes.blend"
OUTPUT_BLEND = EXCHANGE / "ManualRig_UEFN_ControlRig_with_ally2_Meshes.blend"
OUTPUT_AUDIT = EXCHANGE / "ManualRig_UEFN_ControlRig_Audit.json"
VERIFY_SHOT = SHOTS / "ManualRig_ControlRig_PosePreservation.png"
ADDON_ROOT = Path(r"C:\Users\singerie\AppData\Local\Temp\BlenderTools-polyhammer\src\addons")


def register_addons():
    if not (ADDON_ROOT / "ue2rigify" / "__init__.py").is_file():
        raise RuntimeError("UE to Rigify source is missing: " + str(ADDON_ROOT))
    addon_root = str(ADDON_ROOT)
    if addon_root not in sys.path:
        sys.path.insert(0, addon_root)

    import ue2rigify

    # Blender 5's Rigify registration expects its AddonPreferences entry to
    # exist, so enable both modules through Blender's preference operator.
    if "rigify" not in bpy.context.preferences.addons:
        result = bpy.ops.preferences.addon_enable(module="rigify")
        if result != {"FINISHED"}:
            raise RuntimeError("Could not enable Blender's bundled Rigify addon")
    if "ue2rigify" not in bpy.context.preferences.addons:
        result = bpy.ops.preferences.addon_enable(module="ue2rigify")
        if result != {"FINISHED"}:
            raise RuntimeError("Could not enable UE to Rigify")
    return ue2rigify


def evaluated_vertices_world(mesh):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = mesh.evaluated_get(depsgraph)
    evaluated_mesh = evaluated.to_mesh()
    try:
        return [evaluated.matrix_world @ vertex.co for vertex in evaluated_mesh.vertices]
    finally:
        evaluated.to_mesh_clear()


def evaluated_bounds(meshes):
    vertices = []
    for mesh in meshes:
        vertices.extend(evaluated_vertices_world(mesh))
    minimum = Vector(tuple(min(vertex[index] for vertex in vertices) for index in range(3)))
    maximum = Vector(tuple(max(vertex[index] for vertex in vertices) for index in range(3)))
    return minimum, maximum


def max_vertex_delta(before, after):
    if len(before) != len(after):
        raise RuntimeError("Vertex count changed during control-rig conversion")
    deltas = [(left - right).length for left, right in zip(before, after)]
    return max(deltas), math.sqrt(sum(delta * delta for delta in deltas) / len(deltas))


def matrix_delta(left, right):
    return (
        (left.translation - right.translation).length,
        math.degrees(left.to_quaternion().rotation_difference(right.to_quaternion()).angle),
        (left.to_scale() - right.to_scale()).length,
    )


def key_current_pose(rig):
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 1
    scene.frame_set(1)
    if rig.animation_data:
        rig.animation_data_clear()
    action = bpy.data.actions.new("UEFN_ModifiedPose_For_ControlRig")
    rig.animation_data_create()
    rig.animation_data.action = action

    for bone in rig.pose.bones:
        bone.keyframe_insert(data_path="location", frame=1, group=bone.name)
        if bone.rotation_mode == "QUATERNION":
            bone.keyframe_insert(data_path="rotation_quaternion", frame=1, group=bone.name)
        elif bone.rotation_mode == "AXIS_ANGLE":
            bone.keyframe_insert(data_path="rotation_axis_angle", frame=1, group=bone.name)
        else:
            bone.keyframe_insert(data_path="rotation_euler", frame=1, group=bone.name)
        bone.keyframe_insert(data_path="scale", frame=1, group=bone.name)
    scene.frame_set(1)
    bpy.context.view_layer.update()
    return action


def exercise_control(control_rig, source_rig):
    control_name = "upper_arm_fk.L"
    source_name = "upperarm_l"
    control = control_rig.pose.bones.get(control_name)
    source = source_rig.pose.bones.get(source_name)
    if control is None or source is None:
        raise RuntimeError("Expected UEFN arm control mapping is missing")

    original_control_matrix = control.matrix_basis.copy()
    original_source_matrix = source.matrix.copy()
    rotation = Quaternion(control.y_axis, math.radians(3.0)).to_matrix().to_4x4()
    control.matrix_basis = original_control_matrix @ rotation
    bpy.context.view_layer.update()
    moved_source_matrix = source.matrix.copy()
    moved_translation, moved_rotation, _ = matrix_delta(original_source_matrix, moved_source_matrix)

    control.matrix_basis = original_control_matrix
    bpy.context.view_layer.update()
    restored_translation, restored_rotation, restored_scale = matrix_delta(
        original_source_matrix, source.matrix
    )
    if moved_translation < 1e-7 and moved_rotation < 0.1:
        raise RuntimeError("Rigify arm control did not drive the UEFN source bone")
    if restored_translation > 1e-6 or restored_rotation > 1e-4 or restored_scale > 1e-6:
        raise RuntimeError("Control-rig exercise did not restore the source pose exactly")
    return {
        "control": control_name,
        "driven_source_bone": source_name,
        "test_rotation_degrees": 3.0,
        "observed_source_translation_m": moved_translation,
        "observed_source_rotation_degrees": moved_rotation,
        "restore_translation_error_m": restored_translation,
        "restore_rotation_error_degrees": restored_rotation,
        "restore_scale_error": restored_scale,
    }


def calibrate_source_constraints(source_rig, object_world, pose_world):
    """Zero the generated driver offsets at the already-approved fitted pose.

    UE to Rigify's UEFN template maps every native source bone to a Rigify DEF
    bone through a parent/child empty pair.  Its stock offsets describe Epic's
    template reference pose; this project starts from a custom fitted pose.
    Re-seating each child empty on the approved source transform preserves that
    pose exactly while retaining the same live driver relationship.
    """
    calibrated = 0
    for constraint in source_rig.constraints:
        if constraint.name == "Constraints" and constraint.target:
            constraint.target.rotation_mode = "QUATERNION"
            for _ in range(6):
                current = source_rig.matrix_world.copy()
                correction = object_world @ current.inverted_safe()
                constraint.target.matrix_world = correction @ constraint.target.matrix_world
                bpy.context.view_layer.update()
            calibrated += 1

    for bone in sorted(source_rig.pose.bones, key=lambda item: len(item.parent_recursive)):
        desired = pose_world.get(bone.name)
        if desired is None:
            continue
        for constraint in bone.constraints:
            if constraint.name == "Constraints" and constraint.target:
                constraint.target.rotation_mode = "QUATERNION"
                # Copy Transforms plus a scaled FBX wrapper can introduce a
                # small TRS decomposition residue.  Correct the target in
                # world space iteratively until the driven native bone lands
                # back on the approved matrix.
                constraint.target.matrix_world = desired
                bpy.context.view_layer.update()
                for _ in range(8):
                    current = source_rig.matrix_world @ bone.matrix
                    correction = desired @ current.inverted_safe()
                    constraint.target.matrix_world = correction @ constraint.target.matrix_world
                    bpy.context.view_layer.update()
                calibrated += 1
    return calibrated


def build_additive_source_drivers(source_rig, control_rig, links):
    """Drive native bones by control deltas while preserving source shear.

    A Replace-mode transform constraint decomposes the approved source matrix
    into location/rotation/scale and loses shear.  Each delta object below is
    identity at the approved pose, then becomes C(t) * inverse(C(base)) when a
    Rigify DEF bone moves.  BEFORE_FULL applies only that delta ahead of the
    untouched original source transform.
    """
    collection = bpy.data.collections.get("UEFN_CONTROL_DELTAS_DO_NOT_EXPORT")
    if collection is None:
        collection = bpy.data.collections.new("UEFN_CONTROL_DELTAS_DO_NOT_EXPORT")
        bpy.context.scene.collection.children.link(collection)
    collection.hide_render = True

    created = 0
    baseline_errors = []
    for index, link in enumerate(links):
        source_name = link["from_socket"]
        control_name = link["to_socket"]
        if source_name != "object" and source_rig.pose.bones.get(source_name) is None:
            continue
        if control_name != "object" and control_rig.pose.bones.get(control_name) is None:
            continue

        driver = bpy.data.objects.new("UEFN_DRV_{:03d}_{}".format(index, control_name), None)
        driver.empty_display_type = "PLAIN_AXES"
        driver.empty_display_size = 0.02
        driver.rotation_mode = "QUATERNION"
        collection.objects.link(driver)
        driver_constraint = driver.constraints.new("COPY_TRANSFORMS")
        driver_constraint.name = "UEFN_Rigify_Driver"
        driver_constraint.target = control_rig
        if control_name != "object":
            driver_constraint.subtarget = control_name
        driver_constraint.owner_space = "WORLD"
        driver_constraint.target_space = "WORLD"
        bpy.context.view_layer.update()
        baseline_driver_world = driver.matrix_world.copy()

        delta = bpy.data.objects.new("UEFN_DELTA_{:03d}_{}".format(index, source_name), None)
        delta.empty_display_type = "PLAIN_AXES"
        delta.empty_display_size = 0.015
        delta.rotation_mode = "QUATERNION"
        collection.objects.link(delta)
        delta.parent = driver
        delta.matrix_parent_inverse = baseline_driver_world.inverted_safe()
        delta.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
        baseline_errors.append(
            max(abs(delta.matrix_world[row][column] - Matrix.Identity(4)[row][column])
                for row in range(4) for column in range(4))
        )

        if source_name == "object":
            source_constraint = source_rig.constraints.new("COPY_TRANSFORMS")
        else:
            source_constraint = source_rig.pose.bones[source_name].constraints.new("COPY_TRANSFORMS")
        source_constraint.name = "UEFN_Rigify_AdditiveDelta"
        source_constraint.target = delta
        source_constraint.owner_space = "WORLD"
        source_constraint.target_space = "WORLD"
        source_constraint.mix_mode = "BEFORE_FULL"
        source_constraint.remove_target_shear = False
        created += 1

    bpy.context.view_layer.update()
    maximum_baseline_error = max(baseline_errors, default=0.0)
    if maximum_baseline_error > 1e-5:
        raise RuntimeError(
            "Control delta objects are not identity at the approved pose: {}".format(
                maximum_baseline_error
            )
        )
    return created, maximum_baseline_error


def render_pose_verification(meshes):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "WORLD"
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 1200
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world.color = (0.025, 0.025, 0.025)

    minimum, maximum = evaluated_bounds(meshes)
    center = (minimum + maximum) * 0.5
    height = maximum.z - minimum.z
    camera_data = bpy.data.cameras.new("ControlRig_Verify_Camera")
    camera_data.lens = 55
    camera_data.clip_start = 0.01
    camera_data.clip_end = 100.0
    camera = bpy.data.objects.new("ControlRig_Verify_Camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = center + Vector((0.0, -height * 1.45, height * 0.02))
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    scene.render.filepath = str(VERIFY_SHOT)
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(camera, do_unlink=True)
    bpy.data.cameras.remove(camera_data)


def add_readme(audit):
    old = bpy.data.texts.get("README_MANUAL_UEFN_RIGGING_SOURCES")
    if old:
        bpy.data.texts.remove(old)
    text = bpy.data.texts.new("README_UEFN_CONTROL_RIG")
    text.write(
        "USABLE UEFN BLENDER CONTROL RIG\n\n"
        "Pose/manipulation armature: rig (Rigify controls)\n"
        "Native Unreal deform/source armature: root (hidden; do not edit its rest pose)\n"
        "UEFN mesh still bound to: root\n"
        "MetaHuman meshes: ally2_Body_Mesh and ally2_Face_Mesh\n\n"
        "The long FBX bone tails are intentionally hidden. They are a Blender/FBX axis\n"
        "representation artifact, not the armature to manipulate. The Rigify armature\n"
        "drives the original UEFN bones through constraints.\n\n"
        "When final weighting is done, bake control animation to the source rig before\n"
        "export, then export only root plus the intended UEFN-skinned mesh objects.\n\n"
        + json.dumps(audit, indent=2, sort_keys=True)
    )


def main():
    if not SOURCE_BLEND.is_file():
        raise RuntimeError("Missing source blend: " + str(SOURCE_BLEND))
    SHOTS.mkdir(parents=True, exist_ok=True)

    register_addons()
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE_BLEND))

    source_rig = bpy.data.objects.get("root")
    uefn_mesh = bpy.data.objects.get("SKM_UEFN_Mannequin_Posed")
    body_mesh = bpy.data.objects.get("ally2_Body_Mesh")
    face_mesh = bpy.data.objects.get("ally2_Face_Mesh")
    if not source_rig or source_rig.type != "ARMATURE":
        raise RuntimeError("Native UEFN source armature 'root' is missing")
    if not all(mesh and mesh.type == "MESH" for mesh in (uefn_mesh, body_mesh, face_mesh)):
        raise RuntimeError("One or more expected mesh objects are missing")

    source_rig.hide_set(False)
    before_vertices = evaluated_vertices_world(uefn_mesh)
    before_object_world = source_rig.matrix_world.copy()
    before_rest = {bone.name: bone.matrix_local.copy() for bone in source_rig.data.bones}
    before_pose = {
        bone.name: (source_rig.matrix_world @ bone.matrix).copy()
        for bone in source_rig.pose.bones
    }
    # UE to Rigify 1.7.6 can generate rigs in Blender 5, but its animation
    # transfer still calls the removed Action.fcurves API.  Build the same
    # source -> FK -> source/deform graph directly and let Blender 5's own NLA
    # bake operator capture this single pose on the controls.
    if source_rig.animation_data:
        source_rig.animation_data_clear()
    from ue2rigify.constants import Modes
    from ue2rigify.core import scene as ue_scene
    from ue2rigify.core import templates as ue_templates
    from ue2rigify.core import utilities as ue_utilities

    props = bpy.context.scene.ue2rigify
    props.source_rig = source_rig
    props.selected_rig_template = "uefn_mannequin"
    bpy.context.view_layer.objects.active = source_rig
    source_rig.select_set(True)
    control_rig = ue_scene.create_control_rig(props)
    if not control_rig or control_rig.type != "ARMATURE":
        raise RuntimeError("Rigify control armature was not generated")

    ue_utilities.set_object_transforms(
        control_rig, ue_utilities.get_object_transforms(source_rig)
    )
    ue_scene.set_fk_ik_switch_values(control_rig, 1.0)
    ue_utilities.match_rotation_modes(props)
    ue_scene.constrain_fk_to_source(control_rig, source_rig, props)

    bpy.ops.object.mode_set(mode="OBJECT") if bpy.context.mode != "OBJECT" else None
    bpy.ops.object.select_all(action="DESELECT")
    control_rig.hide_set(False)
    control_rig.select_set(True)
    bpy.context.view_layer.objects.active = control_rig
    bpy.ops.object.mode_set(mode="POSE")
    control_action = bpy.data.actions.new("UEFN_ModifiedPose_ControlRig")
    control_rig.animation_data_create()
    control_rig.animation_data.action = control_action
    bpy.context.scene.frame_set(1)
    bpy.ops.nla.bake(
        frame_start=1,
        frame_end=1,
        step=1,
        only_selected=False,
        visual_keying=True,
        clear_constraints=False,
        clear_parents=False,
        use_current_action=True,
        clean_curves=False,
        bake_types={"POSE"},
    )

    ue_templates.set_template_files(props, mode_override=Modes.FK_TO_SOURCE.name)
    fk_links = ue_templates.get_saved_links_data(props)
    ue_scene.remove_constraints(control_rig, props, "from_socket", fk_links)

    ue_templates.set_template_files(props, mode_override=Modes.SOURCE_TO_DEFORM.name)
    source_to_deform_links = ue_templates.get_saved_links_data(props)
    additive_drivers, additive_identity_error = build_additive_source_drivers(
        source_rig, control_rig, source_to_deform_links
    )
    ue_scene.load_metadata(props)
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()

    after_vertices = evaluated_vertices_world(uefn_mesh)
    max_pose_delta, rms_pose_delta = max_vertex_delta(before_vertices, after_vertices)
    if max_pose_delta > 2e-5:
        vertex_deltas = [
            (left - right).length for left, right in zip(before_vertices, after_vertices)
        ]
        worst_vertex_index = max(range(len(vertex_deltas)), key=vertex_deltas.__getitem__)
        worst_vertex = uefn_mesh.data.vertices[worst_vertex_index]
        worst_weights = sorted(
            (
                (uefn_mesh.vertex_groups[group.group].name, group.weight)
                for group in worst_vertex.groups
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        pose_errors = []
        for name, matrix in before_pose.items():
            pose_errors.append((*matrix_delta(matrix, source_rig.matrix_world @ source_rig.pose.bones[name].matrix), name))
        pose_errors.sort(key=lambda error: max(error[0], error[1] * 0.01, error[2]), reverse=True)
        named_pose_errors = {
            error[3]: error[:3]
            for error in pose_errors
            if error[3] in {"calf_l", "calf_r", "thigh_l", "thigh_r", "lowerarm_l", "lowerarm_r"}
        }
        local_coordinate = worst_vertex.co.copy()
        before_calf = before_pose["calf_l"]
        after_calf = source_rig.matrix_world @ source_rig.pose.bones["calf_l"].matrix
        rest_calf = before_rest["calf_l"]
        armature_space_vertex = before_object_world.inverted_safe() @ uefn_mesh.matrix_world @ local_coordinate
        before_manual = before_object_world @ (
            (before_object_world.inverted_safe() @ before_calf)
            @ rest_calf.inverted_safe()
            @ armature_space_vertex
        )
        after_manual = source_rig.matrix_world @ (
            source_rig.pose.bones["calf_l"].matrix
            @ source_rig.data.bones["calf_l"].matrix_local.inverted_safe()
            @ (source_rig.matrix_world.inverted_safe() @ uefn_mesh.matrix_world @ local_coordinate)
        )
        modifier_details = [
            {
                "name": modifier.name,
                "object": modifier.object.name if modifier.object else None,
                "preserve_volume": modifier.use_deform_preserve_volume,
                "show_viewport": modifier.show_viewport,
            }
            for modifier in uefn_mesh.modifiers
            if modifier.type == "ARMATURE"
        ]
        raise RuntimeError(
            "Control conversion changed the fitted mesh pose: {:.9f} m; worst_vertex={} weights={} before={} after={} local={} manual_delta={} modifiers={}; named_errors={}; bone errors={}".format(
                max_pose_delta, worst_vertex_index, worst_weights,
                tuple(before_vertices[worst_vertex_index]), tuple(after_vertices[worst_vertex_index]),
                tuple(local_coordinate), (before_manual - after_manual).length, modifier_details,
                named_pose_errors, pose_errors[:15]
            )
        )

    rest_errors = []
    for name, matrix in before_rest.items():
        rest_errors.append((*matrix_delta(matrix, source_rig.data.bones[name].matrix_local), name))
    max_rest_translation = max(error[0] for error in rest_errors)
    max_rest_rotation = max(error[1] for error in rest_errors)
    max_rest_scale = max(error[2] for error in rest_errors)
    if max_rest_translation > 1e-8 or max_rest_rotation > 1e-5 or max_rest_scale > 1e-8:
        raise RuntimeError("Native UEFN rest matrices changed: " + str(sorted(rest_errors, reverse=True)[:5]))

    source_constraints = sum(len(bone.constraints) for bone in source_rig.pose.bones)
    custom_shape_controls = [
        bone.name for bone in control_rig.pose.bones if bone.custom_shape is not None
    ]
    if source_constraints < 20 or len(custom_shape_controls) < 20:
        raise RuntimeError(
            "Generated rig is incomplete: constraints={} shaped_controls={}".format(
                source_constraints, len(custom_shape_controls)
            )
        )
    control_test = exercise_control(control_rig, source_rig)

    guide_collection = bpy.data.collections.get("UEFN_POSE_GUIDE_DO_NOT_EXPORT")
    if guide_collection:
        guide_collection.hide_viewport = True
        guide_collection.hide_render = True
    source_rig.hide_set(True)
    source_rig.hide_render = True
    source_rig.show_in_front = False
    control_rig.hide_set(False)
    control_rig.hide_render = False
    control_rig.show_in_front = True
    control_rig.data.display_type = "BBONE"
    control_rig.data.show_names = False
    control_rig.data.show_axes = False

    render_pose_verification((uefn_mesh, body_mesh, face_mesh))

    audit = {
        "source_blend": str(SOURCE_BLEND),
        "output_blend": str(OUTPUT_BLEND),
        "blender_version": bpy.app.version_string,
        "ue_to_rigify_template": "uefn_mannequin",
        "control_armature": control_rig.name,
        "native_uefn_source_armature": source_rig.name,
        "native_source_hidden_by_default": True,
        "uefn_mesh_armature_modifier": next(
            modifier.object.name
            for modifier in uefn_mesh.modifiers
            if modifier.type == "ARMATURE"
        ),
        "native_source_bones": len(source_rig.data.bones),
        "control_rig_bones": len(control_rig.data.bones),
        "custom_shape_control_count": len(custom_shape_controls),
        "source_bone_constraint_count": source_constraints,
        "fitted_pose_additive_driver_count": additive_drivers,
        "fitted_pose_delta_identity_max_matrix_error": additive_identity_error,
        "pose_preservation_max_vertex_delta_m": max_pose_delta,
        "pose_preservation_rms_vertex_delta_m": rms_pose_delta,
        "native_rest_max_translation_delta_m": max_rest_translation,
        "native_rest_max_rotation_delta_degrees": max_rest_rotation,
        "native_rest_max_scale_delta": max_rest_scale,
        "control_drive_test": control_test,
        "automatic_bone_orientation_on_native_source": False,
        "native_bind_skeleton_modified": False,
    }
    add_readme(audit)
    OUTPUT_AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8")

    bpy.ops.object.mode_set(mode="OBJECT") if bpy.context.mode != "OBJECT" else None
    bpy.ops.object.select_all(action="DESELECT")
    control_rig.select_set(True)
    bpy.context.view_layer.objects.active = control_rig
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_BLEND))
    print("UEFN_CONTROL_RIG_AUDIT=" + json.dumps(audit, sort_keys=True))


main()
