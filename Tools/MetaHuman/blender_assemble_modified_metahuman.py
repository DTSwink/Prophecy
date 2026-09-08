"""Assemble fitted MetaHuman body + head in the saved Sequencer FK pose.

The two meshes keep their original MetaHuman skinning and bind skeletons.  The
pose is baked from Unreal's FK Control Rig to an AnimSequence, exported as FBX,
and copied onto both armatures without applying it as a new rest pose.
"""

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
EXCHANGE = PROJECT / "Saved" / "BlenderExchange"
SHOTS = PROJECT / "Saved" / "BlenderShots"
BODY_FBX = EXCHANGE / "Body_MH342.fbx"
HEAD_FBX = EXCHANGE / "Face_MH.fbx"
POSE_FBX = EXCHANGE / "MetaHuman_SequencerModifiedPose_BakedAnim.fbx"
UNREAL_AUDIT = EXCHANGE / "MetaHuman_SequencerModifiedPose_UnrealAudit.json"
OUT_BLEND = EXCHANGE / "MetaHuman_BodyHead_SequencerModifiedPose.blend"
OUT_AUDIT = EXCHANGE / "MetaHuman_BodyHead_SequencerModifiedPose_Audit.json"
FRONT_SHOT = SHOTS / "MetaHuman_ModifiedPose_Front.png"
SIDE_SHOT = SHOTS / "MetaHuman_ModifiedPose_Side.png"
THREE_QUARTER_SHOT = SHOTS / "MetaHuman_ModifiedPose_ThreeQuarter.png"
HEAD_SHOT = SHOTS / "MetaHuman_ModifiedPose_HeadShoulders.png"


def import_fbx(path, use_anim):
    before_objects = set(bpy.data.objects)
    before_actions = set(bpy.data.actions)
    bpy.ops.import_scene.fbx(
        filepath=str(path),
        global_scale=1.0,
        bake_space_transform=False,
        use_custom_normals=True,
        use_anim=use_anim,
        ignore_leaf_bones=False,
        force_connect_children=False,
        automatic_bone_orientation=False,
        primary_bone_axis="Y",
        secondary_bone_axis="X",
        use_prepost_rot=True,
        axis_forward="-Z",
        axis_up="Y",
    )
    return (
        list(set(bpy.data.objects) - before_objects),
        list(set(bpy.data.actions) - before_actions),
    )


def exactly_one(objects, object_type):
    matches = [obj for obj in objects if obj.type == object_type]
    if len(matches) != 1:
        raise RuntimeError(
            "Expected one {} object, found {}: {}".format(
                object_type,
                len(matches),
                [obj.name for obj in matches],
            )
        )
    return matches[0]


def ensure_collection(name, color_tag):
    collection = bpy.data.collections.new(name)
    collection.color_tag = color_tag
    bpy.context.scene.collection.children.link(collection)
    return collection


def move_objects(objects, collection):
    for obj in objects:
        for existing in list(obj.users_collection):
            existing.objects.unlink(obj)
        collection.objects.link(obj)


def bone_depth(pose_bone):
    return len(pose_bone.parent_recursive)


def copy_pose(source, target, names):
    ordered = sorted(
        (target.pose.bones[name] for name in names),
        key=bone_depth,
    )
    for target_bone in ordered:
        target_bone.matrix = source.pose.bones[target_bone.name].matrix.copy()
        bpy.context.view_layer.update()


def weight_audit(mesh):
    unweighted = 0
    max_sum_error = 0.0
    for vertex in mesh.data.vertices:
        total = sum(group.weight for group in vertex.groups)
        if total <= 1e-8:
            unweighted += 1
        max_sum_error = max(max_sum_error, abs(total - 1.0))
    modifiers = [m for m in mesh.modifiers if m.type == "ARMATURE"]
    return {
        "vertex_count": len(mesh.data.vertices),
        "polygon_count": len(mesh.data.polygons),
        "vertex_group_count": len(mesh.vertex_groups),
        "unweighted_vertices": unweighted,
        "max_weight_sum_error": max_sum_error,
        "armature_modifier_count": len(modifiers),
        "armature_modifier_target": modifiers[0].object.name
        if len(modifiers) == 1 and modifiers[0].object else None,
    }


def matrix_pair_error(left, right):
    translation = (left.translation - right.translation).length
    rotation = math.degrees(
        left.to_quaternion().rotation_difference(right.to_quaternion()).angle
    )
    scale = (left.to_scale() - right.to_scale()).length
    return translation, rotation, scale


def evaluated_vertices_world(mesh):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = mesh.evaluated_get(depsgraph)
    evaluated_mesh = evaluated.to_mesh()
    try:
        return [evaluated.matrix_world @ vertex.co for vertex in evaluated_mesh.vertices]
    finally:
        evaluated.to_mesh_clear()


def add_pose_guide(armature):
    collection = ensure_collection("POSE_GUIDE_DO_NOT_EXPORT", "COLOR_04")
    curve = bpy.data.curves.new("Sequencer_Pose_Anatomical_Links", "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = 0.0025
    curve.bevel_resolution = 2
    curve.resolution_u = 1

    chains = [
        ("pelvis", "spine_01", "spine_02", "spine_03", "spine_04", "spine_05", "neck_01", "neck_02", "head"),
        ("spine_05", "clavicle_l", "upperarm_l", "lowerarm_l", "hand_l"),
        ("spine_05", "clavicle_r", "upperarm_r", "lowerarm_r", "hand_r"),
        ("pelvis", "thigh_l", "calf_l", "foot_l", "ball_l"),
        ("pelvis", "thigh_r", "calf_r", "foot_r", "ball_r"),
    ]
    for chain in chains:
        for parent_name, child_name in zip(chain, chain[1:]):
            if parent_name not in armature.pose.bones or child_name not in armature.pose.bones:
                continue
            start = armature.matrix_world @ armature.pose.bones[parent_name].head
            end = armature.matrix_world @ armature.pose.bones[child_name].head
            spline = curve.splines.new("POLY")
            spline.points.add(1)
            spline.points[0].co = (*start, 1.0)
            spline.points[1].co = (*end, 1.0)

    guide = bpy.data.objects.new("Sequencer_Pose_Guide_DO_NOT_EXPORT", curve)
    guide.color = (0.02, 0.8, 1.0, 1.0)
    guide.show_in_front = True
    collection.objects.link(guide)
    material = bpy.data.materials.new("M_SequencerPoseGuide_Cyan")
    material.diffuse_color = (0.02, 0.8, 1.0, 1.0)
    curve.materials.append(material)
    return guide


def look_at(camera, target):
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()


def render_views(body_mesh, head_mesh):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "WORLD"
    scene.display.shading.show_specular_highlight = True
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 1200
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new("MetaHuman_AuditWorld")
    scene.world.color = (0.025, 0.025, 0.025)

    body_mesh.color = (0.34, 0.39, 0.48, 1.0)
    head_mesh.color = (0.67, 0.48, 0.39, 1.0)
    vertices = evaluated_vertices_world(body_mesh) + evaluated_vertices_world(head_mesh)
    minimum = Vector((
        min(v.x for v in vertices),
        min(v.y for v in vertices),
        min(v.z for v in vertices),
    ))
    maximum = Vector((
        max(v.x for v in vertices),
        max(v.y for v in vertices),
        max(v.z for v in vertices),
    ))
    center = (minimum + maximum) * 0.5
    height = maximum.z - minimum.z
    distance = height * 1.45

    camera_data = bpy.data.cameras.new("MetaHuman_AuditCamera")
    camera_data.lens = 55
    camera_data.clip_start = 0.01
    camera_data.clip_end = 100.0
    camera = bpy.data.objects.new("MetaHuman_AuditCamera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera

    camera.location = center + Vector((0.0, -distance, height * 0.02))
    look_at(camera, center)
    scene.render.filepath = str(FRONT_SHOT)
    bpy.ops.render.render(write_still=True)

    camera.location = center + Vector((distance, 0.0, height * 0.02))
    look_at(camera, center)
    scene.render.filepath = str(SIDE_SHOT)
    bpy.ops.render.render(write_still=True)

    camera.location = center + Vector((distance * 0.75, -distance * 0.75, height * 0.06))
    look_at(camera, center)
    scene.render.filepath = str(THREE_QUARTER_SHOT)
    bpy.ops.render.render(write_still=True)

    head_center = body_mesh.matrix_world @ body_mesh.parent.pose.bones["neck_01"].head
    head_center.z += 0.10
    camera.location = head_center + Vector((0.0, -0.72, 0.03))
    look_at(camera, head_center)
    scene.render.filepath = str(HEAD_SHOT)
    bpy.ops.render.render(write_still=True)

    bpy.data.objects.remove(camera, do_unlink=True)
    bpy.data.cameras.remove(camera_data)
    return minimum, maximum


def add_readme(audit):
    text = bpy.data.texts.new("README_MODIFIED_METAHUMAN_POSE")
    text.write(
        "Fitted MetaHuman body + face in the saved Unreal Sequencer FK pose.\n\n"
        "SOURCES\n"
        "- Body: Body_MH342.fbx (original 342-joint MetaHuman skinning)\n"
        "- Head: Face_MH.fbx (original full MetaHuman face skinning)\n"
        "- Pose: /Game/_mygame/MetaHumans/NewLevelSequence, UE frame 0\n"
        "- Pose was baked to an AnimSequence in memory; no Unreal asset was saved.\n\n"
        "IMPORTANT\n"
        "- This is a pose, not a changed rest/bind skeleton.\n"
        "- No vertex weights or bone matrices were regenerated in Blender.\n"
        "- Body_Rig_root and Head_Rig_root are separate because MetaHuman body and\n"
        "  face are separate skeletal meshes. Shared bones are pose-identical.\n"
        "- The SOURCE_BAKED_SEQUENCER_POSE_DO_NOT_EXPORT and POSE_GUIDE_DO_NOT_EXPORT\n"
        "  collections are references only.\n\n"
        "AUDIT\n" + json.dumps(audit, indent=2, sort_keys=True)
    )


def main():
    EXCHANGE.mkdir(parents=True, exist_ok=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    for path in (BODY_FBX, HEAD_FBX, POSE_FBX, UNREAL_AUDIT):
        if not path.is_file():
            raise RuntimeError("Missing source: " + str(path))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "METERS"
    scene.frame_start = 1
    scene.frame_end = 1

    body_objects, _ = import_fbx(BODY_FBX, use_anim=False)
    head_objects, _ = import_fbx(HEAD_FBX, use_anim=False)
    pose_objects, pose_actions = import_fbx(POSE_FBX, use_anim=True)
    body_rig = exactly_one(body_objects, "ARMATURE")
    body_mesh = exactly_one(body_objects, "MESH")
    body_wrapper = exactly_one(body_objects, "EMPTY")
    head_rig = exactly_one(head_objects, "ARMATURE")
    head_mesh = exactly_one(head_objects, "MESH")
    head_wrapper = exactly_one(head_objects, "EMPTY")
    pose_rig = exactly_one(pose_objects, "ARMATURE")
    if len(pose_actions) != 1:
        raise RuntimeError("Expected one baked pose action, found {}".format(len(pose_actions)))

    body_collection = ensure_collection("METAHUMAN_BODY_SKINNED", "COLOR_05")
    head_collection = ensure_collection("METAHUMAN_HEAD_SKINNED", "COLOR_03")
    source_collection = ensure_collection(
        "SOURCE_BAKED_SEQUENCER_POSE_DO_NOT_EXPORT",
        "COLOR_01",
    )
    move_objects(body_objects, body_collection)
    move_objects(head_objects, head_collection)
    move_objects(pose_objects, source_collection)

    body_wrapper.name = "Body_FBX_CentimeterWrapper"
    body_rig.name = "Body_Rig_root"
    body_rig.data.name = "Body_Rig_342_Joints"
    body_mesh.name = "Body_Skinned"
    head_wrapper.name = "Head_FBX_CentimeterWrapper"
    head_rig.name = "Head_Rig_root"
    head_rig.data.name = "Head_Rig_875_Joints"
    head_mesh.name = "Head_Skinned"
    pose_rig.name = "SOURCE_SequencerPose_root"
    pose_actions[0].name = "SOURCE_Sequencer_Modified_Pose"
    source_collection.hide_viewport = True
    source_collection.hide_render = True

    body_rig.data.display_type = "STICK"
    head_rig.data.display_type = "STICK"
    body_rig.show_in_front = True
    head_rig.show_in_front = True
    body_rig.data.show_names = False
    head_rig.data.show_names = False

    with UNREAL_AUDIT.open("r", encoding="utf-8") as handle:
        unreal_audit = json.load(handle)

    scene.frame_set(1)
    bpy.context.view_layer.update()

    body_names = {bone.name for bone in body_rig.pose.bones}
    head_names = {bone.name for bone in head_rig.pose.bones}
    pose_names = {bone.name for bone in pose_rig.pose.bones}
    if body_names != pose_names:
        raise RuntimeError(
            "Body and baked pose bone sets differ: missing={} extra={}".format(
                sorted(body_names - pose_names),
                sorted(pose_names - body_names),
            )
        )

    # The FBX root joint is represented by the armature object.  Match that
    # object transform first, then copy the component-space pose matrices.
    body_rig.matrix_world = pose_rig.matrix_world.copy()
    head_rig.matrix_world = pose_rig.matrix_world.copy()
    copy_pose(pose_rig, body_rig, body_names)
    shared_names = body_names & head_names
    copy_pose(body_rig, head_rig, shared_names)
    bpy.context.view_layer.update()

    # Audit the baked FBX against component-space transforms captured directly
    # from Unreal. Blender's FBX conversion maps UE (X,Y,Z) to (X,-Y,Z).
    sample_errors = []
    for name, expected in unreal_audit["sample_global_pose"].items():
        mapped = Vector((
            expected["translation_cm"][0],
            -expected["translation_cm"][1],
            expected["translation_cm"][2],
        ))
        if name == "root":
            actual = pose_rig.matrix_world.translation * 100.0
        else:
            actual = (
                pose_rig.matrix_world @ pose_rig.pose.bones[name].matrix
            ).translation * 100.0
        sample_errors.append(((actual - mapped).length, name))
    sample_errors.sort(reverse=True)

    body_pose_errors = []
    for name in body_names:
        delta = body_rig.pose.bones[name].matrix - pose_rig.pose.bones[name].matrix
        body_pose_errors.append((
            max(abs(value) for row in delta for value in row),
            name,
        ))
    body_pose_errors.sort(reverse=True)

    rest_errors = []
    shared_pose_errors = []
    for name in shared_names:
        rest_t, rest_r, rest_s = matrix_pair_error(
            body_rig.data.bones[name].matrix_local,
            head_rig.data.bones[name].matrix_local,
        )
        rest_errors.append((rest_t, rest_r, rest_s, name))
        pose_t, pose_r, pose_s = matrix_pair_error(
            body_rig.pose.bones[name].matrix,
            head_rig.pose.bones[name].matrix,
        )
        shared_pose_errors.append((pose_t, pose_r, pose_s, name))
    rest_errors.sort(reverse=True)
    shared_pose_errors.sort(reverse=True)

    body_weights = weight_audit(body_mesh)
    head_weights = weight_audit(head_mesh)
    if body_weights["unweighted_vertices"] or head_weights["unweighted_vertices"]:
        raise RuntimeError("Unweighted vertices found: body={} head={}".format(
            body_weights["unweighted_vertices"],
            head_weights["unweighted_vertices"],
        ))
    if body_weights["armature_modifier_target"] != body_rig.name:
        raise RuntimeError("Body Armature modifier is not bound to Body_Rig_root")
    if head_weights["armature_modifier_target"] != head_rig.name:
        raise RuntimeError("Head Armature modifier is not bound to Head_Rig_root")
    if sample_errors[0][0] > 0.01:
        raise RuntimeError("Baked pose does not match Unreal sample: " + str(sample_errors[0]))
    if rest_errors[0][0] > 0.01 or rest_errors[0][1] > 0.01:
        raise RuntimeError("Body/head shared rest skeletons disagree: " + str(rest_errors[0]))
    if shared_pose_errors[0][0] > 1e-4 or shared_pose_errors[0][1] > 1e-4:
        raise RuntimeError("Body/head shared poses disagree: " + str(shared_pose_errors[0]))

    guide = add_pose_guide(body_rig)
    minimum, maximum = render_views(body_mesh, head_mesh)
    dimensions = maximum - minimum

    audit = {
        "unreal_sequence": unreal_audit["sequence"],
        "unreal_frame": unreal_audit["frame"],
        "unreal_assets_saved": False,
        "body_source": str(BODY_FBX),
        "head_source": str(HEAD_FBX),
        "pose_source": str(POSE_FBX),
        "output_blend": str(OUT_BLEND),
        "body_armature": body_rig.name,
        "body_bone_count_without_fbx_root_object": len(body_names),
        "head_armature": head_rig.name,
        "head_bone_count_without_fbx_root_object": len(head_names),
        "shared_body_head_bone_count": len(shared_names),
        "body_weights": body_weights,
        "head_weights": head_weights,
        "max_unreal_pose_translation_error_cm": sample_errors[0][0],
        "max_unreal_pose_translation_error_bone": sample_errors[0][1],
        "max_body_pose_matrix_copy_error": body_pose_errors[0][0],
        "max_body_pose_matrix_copy_error_bone": body_pose_errors[0][1],
        "max_body_head_shared_rest_translation_error_cm": rest_errors[0][0],
        "max_body_head_shared_rest_rotation_error_deg": rest_errors[0][1],
        "max_body_head_shared_rest_error_bone": rest_errors[0][3],
        "max_body_head_shared_pose_translation_error_cm": shared_pose_errors[0][0],
        "max_body_head_shared_pose_rotation_error_deg": shared_pose_errors[0][1],
        "max_body_head_shared_pose_error_bone": shared_pose_errors[0][3],
        "evaluated_world_bounds_min_m": list(minimum),
        "evaluated_world_bounds_max_m": list(maximum),
        "evaluated_world_dimensions_m": list(dimensions),
        "pose_guide": guide.name,
        "automatic_bone_orientation": False,
        "ignore_leaf_bones": False,
        "use_prepost_rot": True,
        "pose_applied_as_rest_pose": False,
        "weights_modified_in_blender": False,
    }
    add_readme(audit)
    OUT_AUDIT.write_text(
        json.dumps(audit, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    bpy.ops.object.select_all(action="DESELECT")
    body_rig.select_set(True)
    body_mesh.select_set(True)
    head_rig.select_set(True)
    head_mesh.select_set(True)
    bpy.context.view_layer.objects.active = body_rig
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND))
    print("MODIFIED_METAHUMAN_AUDIT=" + json.dumps(audit, sort_keys=True))
    print("MODIFIED_METAHUMAN_BLEND=" + str(OUT_BLEND))
    print("MODIFIED_METAHUMAN_FRONT=" + str(FRONT_SHOT))
    print("MODIFIED_METAHUMAN_SIDE=" + str(SIDE_SHOT))
    print("MODIFIED_METAHUMAN_THREE_QUARTER=" + str(THREE_QUARTER_SHOT))
    print("MODIFIED_METAHUMAN_HEAD=" + str(HEAD_SHOT))


main()
