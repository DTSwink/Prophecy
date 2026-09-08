"""Stage 1: import and verify the untouched UEFN rig in the saved fitted pose.

The deform skeleton is imported exactly as encoded by Unreal's FBX exporter:
automatic bone orientation is disabled and FBX pre/post rotations are honored.
The previously saved one-frame pose is imported separately and copied onto the
deform armature as a pose, never as a new rest/bind skeleton.
"""

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
EXCHANGE = PROJECT / "Saved" / "BlenderExchange"
SHOTS = PROJECT / "Saved" / "BlenderShots"
MESH_FBX = EXCHANGE / "ManualRig_UEFN_Mannequin_RigMesh.fbx"
POSE_FBX = EXCHANGE / "ManualRig_UEFN_ModifiedPose.fbx"
SNAPSHOT = PROJECT / "Tools" / "MetaHuman" / "skeleton_snapshots.json"
OUT_BLEND = EXCHANGE / "ManualRig_Stage1_UEFN_Posed.blend"
OUT_AUDIT = EXCHANGE / "ManualRig_Stage1_UEFN_Posed_Audit.json"
FRONT_SHOT = SHOTS / "ManualRig_Stage1_UEFN_Front.png"
SIDE_SHOT = SHOTS / "ManualRig_Stage1_UEFN_Side.png"
THREE_QUARTER_SHOT = SHOTS / "ManualRig_Stage1_UEFN_ThreeQuarter.png"


def import_fbx(path, use_anim):
    before_objects = set(bpy.data.objects)
    before_actions = set(bpy.data.actions)
    bpy.ops.import_scene.fbx(
        filepath=str(path),
        use_manual_orientation=False,
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
                object_type, len(matches), [obj.name for obj in matches]
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
        for current in list(obj.users_collection):
            current.objects.unlink(obj)
        collection.objects.link(obj)


def bone_depth(pose_bone):
    return len(pose_bone.parent_recursive)


def copy_pose(source, target, names):
    for target_bone in sorted(
        (target.pose.bones[name] for name in names), key=bone_depth
    ):
        target_bone.matrix = source.pose.bones[target_bone.name].matrix.copy()
        bpy.context.view_layer.update()


def matrix_error(left, right):
    return (
        (left.translation - right.translation).length,
        math.degrees(
            left.to_quaternion().rotation_difference(right.to_quaternion()).angle
        ),
        (left.to_scale() - right.to_scale()).length,
    )


def evaluated_vertices_world(mesh):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = mesh.evaluated_get(depsgraph)
    evaluated_mesh = evaluated.to_mesh()
    try:
        return [evaluated.matrix_world @ vertex.co for vertex in evaluated_mesh.vertices]
    finally:
        evaluated.to_mesh_clear()


def add_pose_guide(armature):
    collection = ensure_collection("UEFN_POSE_GUIDE_DO_NOT_EXPORT", "COLOR_04")
    curve = bpy.data.curves.new("UEFN_ModifiedPose_AnatomicalLinks", "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = 0.0025
    curve.bevel_resolution = 2
    curve.resolution_u = 1
    chains = [
        ("pelvis", "spine_01", "spine_02", "spine_03", "spine_04", "spine_05", "neck_01", "neck_02", "head"),
        ("spine_05", "clavicle_l", "upperarm_l", "lowerarm_l", "hand_l", "middle_01_l", "middle_02_l", "middle_03_l"),
        ("spine_05", "clavicle_r", "upperarm_r", "lowerarm_r", "hand_r", "middle_01_r", "middle_02_r", "middle_03_r"),
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

    guide = bpy.data.objects.new("UEFN_ModifiedPose_Guide_DO_NOT_EXPORT", curve)
    guide.color = (0.02, 0.8, 1.0, 1.0)
    guide.show_in_front = True
    collection.objects.link(guide)
    material = bpy.data.materials.new("M_UEFN_PoseGuide_Cyan")
    material.diffuse_color = (0.02, 0.8, 1.0, 1.0)
    curve.materials.append(material)
    return guide


def look_at(camera, target):
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()


def render_views(mesh):
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
        scene.world = bpy.data.worlds.new("ManualRig_Stage1_World")
    scene.world.color = (0.025, 0.025, 0.025)
    mesh.color = (0.46, 0.31, 0.13, 1.0)

    vertices = evaluated_vertices_world(mesh)
    minimum = Vector(tuple(min(v[i] for v in vertices) for i in range(3)))
    maximum = Vector(tuple(max(v[i] for v in vertices) for i in range(3)))
    center = (minimum + maximum) * 0.5
    height = maximum.z - minimum.z
    distance = height * 1.35

    camera_data = bpy.data.cameras.new("ManualRig_Stage1_Camera")
    camera_data.lens = 55
    camera_data.clip_start = 0.01
    camera_data.clip_end = 100.0
    camera = bpy.data.objects.new("ManualRig_Stage1_Camera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera

    for location, output in (
        (center + Vector((0.0, -distance, height * 0.02)), FRONT_SHOT),
        (center + Vector((distance, 0.0, height * 0.02)), SIDE_SHOT),
        (center + Vector((distance * 0.75, -distance * 0.75, height * 0.06)), THREE_QUARTER_SHOT),
    ):
        camera.location = location
        look_at(camera, center)
        scene.render.filepath = str(output)
        bpy.ops.render.render(write_still=True)

    bpy.data.objects.remove(camera, do_unlink=True)
    bpy.data.cameras.remove(camera_data)
    return minimum, maximum


def add_readme(audit):
    text = bpy.data.texts.new("README_STAGE1_UEFN_POSED_RIG")
    text.write(
        "Untouched UEFN deform rig and mesh in the saved fitted pose.\n\n"
        "The pose is not the current level pose. It comes from the persistent\n"
        "/Game/_mygame/MetaHumans/Poses/AS_UEFN_ModifiedPose_Source asset.\n\n"
        "Do not apply Automatic Bone Orientation, object transforms, or this pose\n"
        "as a rest pose. The FBX root joint is the armature object named root;\n"
        "the remaining 87 joints are Blender bones. The cyan curve is display-only.\n\n"
        + json.dumps(audit, indent=2, sort_keys=True)
    )


def main():
    EXCHANGE.mkdir(parents=True, exist_ok=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    for path in (MESH_FBX, POSE_FBX, SNAPSHOT):
        if not path.is_file():
            raise RuntimeError("Missing source: " + str(path))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "METERS"
    scene.frame_start = 1
    scene.frame_end = 1

    mesh_objects, _ = import_fbx(MESH_FBX, use_anim=False)
    pose_objects, pose_actions = import_fbx(POSE_FBX, use_anim=True)
    deform_rig = exactly_one(mesh_objects, "ARMATURE")
    mesh = exactly_one(mesh_objects, "MESH")
    mesh_wrapper = exactly_one(mesh_objects, "EMPTY")
    pose_rig = exactly_one(pose_objects, "ARMATURE")
    if len(pose_actions) != 1:
        raise RuntimeError("Expected one pose action, found {}".format(len(pose_actions)))

    deform_collection = ensure_collection("UEFN_DEFORM_RIG_AND_MESH", "COLOR_05")
    source_collection = ensure_collection("SOURCE_UEFN_POSE_DO_NOT_EXPORT", "COLOR_01")
    move_objects(mesh_objects, deform_collection)
    move_objects(pose_objects, source_collection)
    source_collection.hide_viewport = True
    source_collection.hide_render = True

    mesh_wrapper.name = "UEFN_FBX_CentimeterWrapper"
    deform_rig.name = "root"
    deform_rig.data.name = "UEFN_88_Joint_DeformRig"
    mesh.name = "SKM_UEFN_Mannequin_Posed"
    mesh.data.name = "SKM_UEFN_Mannequin_Mesh"
    pose_rig.name = "SOURCE_UEFN_ModifiedPose_root"
    pose_actions[0].name = "SOURCE_UEFN_ModifiedPose"

    scene.frame_set(1)
    bpy.context.view_layer.update()
    deform_names = {bone.name for bone in deform_rig.pose.bones}
    pose_names = {bone.name for bone in pose_rig.pose.bones}
    if deform_names != pose_names:
        raise RuntimeError(
            "Mesh and pose bone sets differ: missing={} extra={}".format(
                sorted(deform_names - pose_names), sorted(pose_names - deform_names)
            )
        )

    rest_errors = []
    for name in deform_names:
        translation, rotation, scale = matrix_error(
            deform_rig.data.bones[name].matrix_local,
            pose_rig.data.bones[name].matrix_local,
        )
        rest_errors.append((translation, rotation, scale, name))
    rest_errors.sort(reverse=True)
    max_rest_translation_cm = max(row[0] for row in rest_errors)
    max_rest_rotation_deg = max(row[1] for row in rest_errors)
    max_rest_scale_error = max(row[2] for row in rest_errors)
    if max_rest_translation_cm > 0.01 or max_rest_rotation_deg > 0.01:
        raise RuntimeError("Mesh/pose rest skeleton mismatch: {}".format(rest_errors[:5]))

    deform_rig.matrix_world = pose_rig.matrix_world.copy()
    copy_pose(pose_rig, deform_rig, deform_names)
    bpy.context.view_layer.update()

    with SNAPSHOT.open("r", encoding="utf-8") as handle:
        reference = json.load(handle)["uefn_reference"]
    expected_names = {entry["name"] for entry in reference["bones"]} - {"root"}
    if deform_names != expected_names:
        raise RuntimeError(
            "Imported UEFN hierarchy differs from the audited snapshot: missing={} extra={}".format(
                sorted(expected_names - deform_names), sorted(deform_names - expected_names)
            )
        )

    modifiers = [modifier for modifier in mesh.modifiers if modifier.type == "ARMATURE"]
    if len(modifiers) != 1 or modifiers[0].object != deform_rig:
        raise RuntimeError("UEFN mesh is not bound to the imported deform rig")

    unknown_groups = sorted(
        group.name for group in mesh.vertex_groups if group.name not in deform_names
    )
    if unknown_groups:
        raise RuntimeError("Vertex groups without deform bones: " + str(unknown_groups))
    unweighted = 0
    max_weight_error = 0.0
    for vertex in mesh.data.vertices:
        total = sum(group.weight for group in vertex.groups)
        unweighted += int(total <= 1e-8)
        max_weight_error = max(max_weight_error, abs(total - 1.0))
    if unweighted or max_weight_error > 1e-4:
        raise RuntimeError(
            "Invalid UEFN skin weights: unweighted={} max_error={}".format(
                unweighted, max_weight_error
            )
        )

    deform_rig.data.display_type = "STICK"
    deform_rig.show_in_front = True
    deform_rig.data.show_names = False
    deform_rig.data.show_axes = False
    guide = add_pose_guide(deform_rig)
    minimum, maximum = render_views(mesh)
    dimensions = list(maximum - minimum)
    if not 1.5 < dimensions[2] < 2.0:
        raise RuntimeError("Posed UEFN height is not human-scale: " + str(dimensions))

    audit = {
        "mesh_fbx": str(MESH_FBX),
        "pose_fbx": str(POSE_FBX),
        "output_blend": str(OUT_BLEND),
        "root_representation": "armature object named root",
        "uefn_joint_count": len(deform_names) + 1,
        "blender_bone_count": len(deform_names),
        "vertex_count": len(mesh.data.vertices),
        "polygon_count": len(mesh.data.polygons),
        "unweighted_vertices": unweighted,
        "max_weight_sum_error": max_weight_error,
        "max_mesh_pose_rest_translation_delta_cm": max_rest_translation_cm,
        "max_mesh_pose_rest_rotation_delta_deg": max_rest_rotation_deg,
        "max_mesh_pose_rest_scale_error": max_rest_scale_error,
        "world_dimensions_m": dimensions,
        "automatic_bone_orientation": False,
        "ignore_leaf_bones": False,
        "use_prepost_rot": True,
        "pose_applied_as_rest_pose": False,
        "pose_frame": 1,
        "visual_guide": guide.name,
    }
    add_readme(audit)
    OUT_AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8")

    bpy.ops.object.select_all(action="DESELECT")
    deform_rig.select_set(True)
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = deform_rig
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND))
    print("MANUAL_RIG_STAGE1=" + json.dumps(audit, sort_keys=True))


main()
