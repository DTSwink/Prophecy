"""Stage 2: add the current ally2 body and face to the verified posed UEFN rig.

The UEFN armature remains posed but keeps its original rest matrices.  The
MetaHuman body and face are imported in their own reference states and retain
their source armatures only as removable provenance.  No weights, geometry, or
rest transforms are modified.
"""

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
EXCHANGE = PROJECT / "Saved" / "BlenderExchange"
SHOTS = PROJECT / "Saved" / "BlenderShots"
STAGE1_BLEND = EXCHANGE / "ManualRig_Stage1_UEFN_Posed.blend"
BODY_FBX = EXCHANGE / "ManualRig_ally2_Body.fbx"
FACE_FBX = EXCHANGE / "ManualRig_ally2_Face.fbx"
OUT_BLEND = EXCHANGE / "ManualRig_UEFN_Posed_with_ally2_Meshes.blend"
OUT_AUDIT = EXCHANGE / "ManualRig_UEFN_Posed_with_ally2_Meshes_Audit.json"
FRONT_SHOT = SHOTS / "ManualRig_Final_Alignment_Front.png"
SIDE_SHOT = SHOTS / "ManualRig_Final_Alignment_Side.png"
THREE_QUARTER_SHOT = SHOTS / "ManualRig_Final_Alignment_ThreeQuarter.png"
UPPER_SHOT = SHOTS / "ManualRig_Final_Alignment_UpperBody.png"
LOWER_SHOT = SHOTS / "ManualRig_Final_Alignment_Legs.png"


def import_fbx(path):
    before_objects = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(
        filepath=str(path),
        use_manual_orientation=False,
        global_scale=1.0,
        bake_space_transform=False,
        use_custom_normals=True,
        use_anim=False,
        ignore_leaf_bones=False,
        force_connect_children=False,
        automatic_bone_orientation=False,
        primary_bone_axis="Y",
        secondary_bone_axis="X",
        use_prepost_rot=True,
        axis_forward="-Z",
        axis_up="Y",
    )
    return list(set(bpy.data.objects) - before_objects)


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
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    collection.color_tag = color_tag
    return collection


def move_objects(objects, collection):
    for obj in objects:
        for current in list(obj.users_collection):
            current.objects.unlink(obj)
        collection.objects.link(obj)


def weight_audit(mesh, rig):
    modifiers = [modifier for modifier in mesh.modifiers if modifier.type == "ARMATURE"]
    if len(modifiers) != 1 or modifiers[0].object != rig:
        raise RuntimeError(
            "{} is not bound to its imported armature".format(mesh.name)
        )
    bone_names = {bone.name for bone in rig.data.bones}
    unknown_groups = sorted(
        group.name for group in mesh.vertex_groups if group.name not in bone_names
    )
    if unknown_groups:
        raise RuntimeError(
            "{} has vertex groups without bones: {}".format(mesh.name, unknown_groups)
        )
    unweighted = 0
    max_error = 0.0
    for vertex in mesh.data.vertices:
        total = sum(group.weight for group in vertex.groups)
        unweighted += int(total <= 1e-8)
        max_error = max(max_error, abs(total - 1.0))
    if unweighted or max_error > 1e-4:
        raise RuntimeError(
            "{} weight audit failed: unweighted={} max_error={}".format(
                mesh.name, unweighted, max_error
            )
        )
    return {
        "vertex_count": len(mesh.data.vertices),
        "polygon_count": len(mesh.data.polygons),
        "bone_count": len(rig.data.bones) + 1,
        "vertex_group_count": len(mesh.vertex_groups),
        "unweighted_vertices": unweighted,
        "max_weight_sum_error": max_error,
        "armature_modifier_target": rig.name,
    }


def pose_is_rest(rig):
    max_translation = 0.0
    max_rotation = 0.0
    max_scale = 0.0
    for bone in rig.pose.bones:
        basis = bone.matrix_basis
        max_translation = max(max_translation, basis.translation.length)
        max_rotation = max(max_rotation, math.degrees(basis.to_quaternion().angle))
        max_scale = max(max_scale, (basis.to_scale() - Vector((1.0, 1.0, 1.0))).length)
    return max_translation, max_rotation, max_scale


def evaluated_vertices_world(mesh):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = mesh.evaluated_get(depsgraph)
    evaluated_mesh = evaluated.to_mesh()
    try:
        return [evaluated.matrix_world @ vertex.co for vertex in evaluated_mesh.vertices]
    finally:
        evaluated.to_mesh_clear()


def world_bounds(meshes):
    vertices = []
    for mesh in meshes:
        vertices.extend(evaluated_vertices_world(mesh))
    minimum = Vector(tuple(min(v[i] for v in vertices) for i in range(3)))
    maximum = Vector(tuple(max(v[i] for v in vertices) for i in range(3)))
    return minimum, maximum


def shared_joint_audit(uefn_rig, body_rig):
    names = sorted(
        {bone.name for bone in uefn_rig.pose.bones}
        & {bone.name for bone in body_rig.pose.bones}
        & {
            "pelvis", "spine_01", "spine_02", "spine_03", "spine_04", "spine_05",
            "neck_01", "neck_02", "head", "clavicle_l", "upperarm_l",
            "lowerarm_l", "hand_l", "clavicle_r", "upperarm_r", "lowerarm_r",
            "hand_r", "thigh_l", "calf_l", "foot_l", "ball_l", "thigh_r",
            "calf_r", "foot_r", "ball_r",
        }
    )
    rows = []
    for name in names:
        uefn_position = (
            uefn_rig.matrix_world @ uefn_rig.pose.bones[name].matrix
        ).translation
        body_position = (
            body_rig.matrix_world @ body_rig.pose.bones[name].matrix
        ).translation
        rows.append({
            "bone": name,
            "head_position_delta_m": (uefn_position - body_position).length,
        })
    rows.sort(key=lambda row: row["head_position_delta_m"], reverse=True)
    return rows


def look_at(camera, target):
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()


def render_views(uefn_mesh, body_mesh, face_mesh):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "WORLD"
    scene.display.shading.show_specular_highlight = True
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 1400
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new("ManualRig_Final_World")
    scene.world.color = (0.025, 0.025, 0.025)

    uefn_mesh.color = (0.82, 0.31, 0.045, 1.0)
    uefn_mesh.show_wire = True
    uefn_mesh.show_all_edges = True
    body_mesh.color = (0.42, 0.48, 0.58, 1.0)
    face_mesh.color = (0.64, 0.49, 0.42, 1.0)

    minimum, maximum = world_bounds((uefn_mesh, body_mesh, face_mesh))
    center = (minimum + maximum) * 0.5
    height = maximum.z - minimum.z
    distance = height * 1.45
    camera_data = bpy.data.cameras.new("ManualRig_Final_Camera")
    camera_data.lens = 55
    camera_data.clip_start = 0.01
    camera_data.clip_end = 100.0
    camera = bpy.data.objects.new("ManualRig_Final_Camera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera

    def render(location, target, output):
        camera.location = location
        look_at(camera, target)
        scene.render.filepath = str(output)
        bpy.ops.render.render(write_still=True)

    render(center + Vector((0.0, -distance, height * 0.02)), center, FRONT_SHOT)
    render(center + Vector((distance, 0.0, height * 0.02)), center, SIDE_SHOT)
    render(
        center + Vector((distance * 0.75, -distance * 0.75, height * 0.06)),
        center,
        THREE_QUARTER_SHOT,
    )
    upper_target = Vector((center.x, center.y, minimum.z + height * 0.69))
    render(upper_target + Vector((0.0, -height * 0.95, 0.02)), upper_target, UPPER_SHOT)
    lower_target = Vector((center.x, center.y, minimum.z + height * 0.27))
    render(lower_target + Vector((0.0, -height * 0.95, 0.02)), lower_target, LOWER_SHOT)

    bpy.data.objects.remove(camera, do_unlink=True)
    bpy.data.cameras.remove(camera_data)
    return minimum, maximum


def add_readme(audit):
    text = bpy.data.texts.new("README_MANUAL_UEFN_RIGGING_SOURCES")
    text.write(
        "Manual rigging source scene for ally2 -> untouched UEFN skeleton.\n\n"
        "KEEP\n"
        "- UEFN deform armature: root\n"
        "- UEFN posed mesh: SKM_UEFN_Mannequin_Posed\n"
        "- MetaHuman source meshes: ally2_Body_Mesh and ally2_Face_Mesh\n\n"
        "REMOVABLE\n"
        "- ally2_Body_SourceRig and ally2_Face_SourceRig after you transfer/author weights\n"
        "- SOURCE_UEFN_POSE_DO_NOT_EXPORT and UEFN_POSE_GUIDE_DO_NOT_EXPORT\n\n"
        "RULES\n"
        "- The UEFN pose is a pose, not a new rest/bind skeleton.\n"
        "- Do not apply Automatic Bone Orientation or armature transforms.\n"
        "- Do not add an extra root bone: UE root is the armature object named root.\n"
        "- Export only the final UEFN armature and intended skinned mesh(es).\n\n"
        + json.dumps(audit, indent=2, sort_keys=True)
    )


def main():
    for path in (STAGE1_BLEND, BODY_FBX, FACE_FBX):
        if not path.is_file():
            raise RuntimeError("Missing source: " + str(path))
    SHOTS.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(STAGE1_BLEND))

    uefn_rig = bpy.data.objects.get("root")
    uefn_mesh = bpy.data.objects.get("SKM_UEFN_Mannequin_Posed")
    if uefn_rig is None or uefn_rig.type != "ARMATURE":
        raise RuntimeError("Stage 1 UEFN armature is missing")
    if uefn_mesh is None or uefn_mesh.type != "MESH":
        raise RuntimeError("Stage 1 UEFN mesh is missing")

    body_objects = import_fbx(BODY_FBX)
    face_objects = import_fbx(FACE_FBX)
    body_rig = exactly_one(body_objects, "ARMATURE")
    body_mesh = exactly_one(body_objects, "MESH")
    body_wrapper = exactly_one(body_objects, "EMPTY")
    face_rig = exactly_one(face_objects, "ARMATURE")
    face_mesh = exactly_one(face_objects, "MESH")
    face_wrapper = exactly_one(face_objects, "EMPTY")

    body_collection = ensure_collection("METAHUMAN_ALLY2_BODY_SOURCE", "COLOR_03")
    face_collection = ensure_collection("METAHUMAN_ALLY2_FACE_SOURCE", "COLOR_06")
    move_objects(body_objects, body_collection)
    move_objects(face_objects, face_collection)

    body_wrapper.name = "ally2_Body_FBX_CentimeterWrapper"
    body_rig.name = "ally2_Body_SourceRig"
    body_rig.data.name = "ally2_Body_MetaHumanRig"
    body_mesh.name = "ally2_Body_Mesh"
    body_mesh.data.name = "ally2_Body_Geometry"
    face_wrapper.name = "ally2_Face_FBX_CentimeterWrapper"
    face_rig.name = "ally2_Face_SourceRig"
    face_rig.data.name = "ally2_Face_MetaHumanRig"
    face_mesh.name = "ally2_Face_Mesh"
    face_mesh.data.name = "ally2_Face_Geometry"

    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    body_rest = pose_is_rest(body_rig)
    face_rest = pose_is_rest(face_rig)
    # Blender's FBX pre/post-rotation reconstruction leaves sub-micrometer
    # numerical translation/scale residue in matrix_basis; this is not a pose.
    if body_rest[0] > 1e-3 or body_rest[1] > 1e-4 or body_rest[2] > 1e-5:
        raise RuntimeError("MetaHuman body imported with an unexpected pose: {}".format(body_rest))
    if face_rest[0] > 1e-3 or face_rest[1] > 1e-4 or face_rest[2] > 1e-5:
        raise RuntimeError("MetaHuman face imported with an unexpected pose: {}".format(face_rest))

    body_weights = weight_audit(body_mesh, body_rig)
    face_weights = weight_audit(face_mesh, face_rig)
    shared_names = (
        {bone.name for bone in body_rig.pose.bones}
        & {bone.name for bone in face_rig.pose.bones}
    )
    shared_errors = []
    for name in shared_names:
        body_matrix = body_rig.matrix_world @ body_rig.pose.bones[name].matrix
        face_matrix = face_rig.matrix_world @ face_rig.pose.bones[name].matrix
        shared_errors.append({
            "bone": name,
            "translation_delta_m": (body_matrix.translation - face_matrix.translation).length,
            "rotation_delta_deg": math.degrees(
                body_matrix.to_quaternion().rotation_difference(face_matrix.to_quaternion()).angle
            ),
        })
    shared_errors.sort(
        key=lambda row: (row["translation_delta_m"], row["rotation_delta_deg"]),
        reverse=True,
    )
    max_shared_translation = max(row["translation_delta_m"] for row in shared_errors)
    max_shared_rotation = max(row["rotation_delta_deg"] for row in shared_errors)
    # Separate Unreal face/body FBXs can reconstruct the same shared joint with
    # a small roll difference because FBX bones have no native Blender-style
    # tail orientation.  Translation is the seam-critical quantity here; the
    # source armatures are retained only as removable provenance.
    if max_shared_translation > 1e-5 or max_shared_rotation > 0.5:
        raise RuntimeError(
            "MetaHuman body/face reference skeletons are not aligned: {}".format(
                shared_errors[:5]
            )
        )

    # The MetaHuman source rigs are intentionally retained but hidden so the
    # user's manual work starts with the authoritative UEFN armature visible.
    body_rig.hide_set(True)
    face_rig.hide_set(True)
    body_rig.data.display_type = "STICK"
    face_rig.data.display_type = "STICK"
    body_rig.show_in_front = True
    face_rig.show_in_front = True
    uefn_rig.hide_set(False)
    uefn_rig.show_in_front = True

    joint_rows = shared_joint_audit(uefn_rig, body_rig)
    minimum, maximum = render_views(uefn_mesh, body_mesh, face_mesh)
    dimensions = list(maximum - minimum)
    if not 1.5 < dimensions[2] < 2.0:
        raise RuntimeError("Combined source scene is not human-scale: " + str(dimensions))

    audit = {
        "stage1_blend": str(STAGE1_BLEND),
        "body_fbx": str(BODY_FBX),
        "face_fbx": str(FACE_FBX),
        "output_blend": str(OUT_BLEND),
        "uefn_armature": uefn_rig.name,
        "uefn_mesh": uefn_mesh.name,
        "uefn_pose_is_rest_pose": False,
        "metahuman_body": body_weights,
        "metahuman_face": face_weights,
        "metahuman_body_pose_basis_max": body_rest,
        "metahuman_face_pose_basis_max": face_rest,
        "metahuman_body_face_shared_bones": len(shared_names),
        "metahuman_body_face_max_shared_translation_delta_m": max_shared_translation,
        "metahuman_body_face_max_shared_rotation_delta_deg": max_shared_rotation,
        "uefn_pose_to_metahuman_rest_key_joint_deltas": joint_rows,
        "world_dimensions_m": dimensions,
        "automatic_bone_orientation": False,
        "source_armatures_retained": True,
        "source_armatures_hidden_by_default": True,
        "geometry_or_weights_modified": False,
    }
    add_readme(audit)
    OUT_AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8")

    bpy.ops.object.select_all(action="DESELECT")
    uefn_rig.select_set(True)
    uefn_mesh.select_set(True)
    body_mesh.select_set(True)
    face_mesh.select_set(True)
    bpy.context.view_layer.objects.active = uefn_rig
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND))
    print("MANUAL_RIG_STAGE2=" + json.dumps(audit, sort_keys=True))


main()
