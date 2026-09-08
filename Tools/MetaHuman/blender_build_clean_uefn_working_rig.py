"""Create the clean Blender working rig plus untouched UEFN export rig.

The visible working armature is imported with Automatic Bone Orientation for
normal Blender bone heads/tails.  The hidden native armature remains untouched
and is the only armature intended for final Unreal/UEFN export.
"""

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
EXCHANGE = PROJECT / "Saved" / "BlenderExchange"
SHOTS = PROJECT / "Saved" / "BlenderShots"
SOURCE_BLEND = EXCHANGE / "ManualRig_UEFN_Posed_with_ally2_Meshes.blend"
UEFN_FBX = EXCHANGE / "ManualRig_UEFN_Mannequin_RigMesh.fbx"
OUTPUT_BLEND = EXCHANGE / "ManualRig_CleanWorkingRig_with_NativeExportRig.blend"
OUTPUT_AUDIT = EXCHANGE / "ManualRig_CleanWorkingRig_Audit.json"
FRONT_SHOT = SHOTS / "ManualRig_CleanWorkingRig_Front.png"
SIDE_SHOT = SHOTS / "ManualRig_CleanWorkingRig_Side.png"


def import_clean_fbx(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(
        filepath=str(path),
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
    return list(set(bpy.data.objects) - before)


def exactly_one(objects, object_type):
    matches = [obj for obj in objects if obj.type == object_type]
    if len(matches) != 1:
        raise RuntimeError(
            "Expected one {} object, found {}: {}".format(
                object_type, len(matches), [obj.name for obj in matches]
            )
        )
    return matches[0]


def ensure_collection(name, color):
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    collection.color_tag = color
    return collection


def move_objects(objects, collection):
    for obj in objects:
        for current in list(obj.users_collection):
            current.objects.unlink(obj)
        collection.objects.link(obj)


def evaluated_vertices_world(mesh):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = mesh.evaluated_get(depsgraph)
    evaluated_mesh = evaluated.to_mesh()
    try:
        return [evaluated.matrix_world @ vertex.co for vertex in evaluated_mesh.vertices]
    finally:
        evaluated.to_mesh_clear()


def matrix_max_element_delta(left, right):
    return max(
        abs(left[row][column] - right[row][column])
        for row in range(4)
        for column in range(4)
    )


def map_native_pose_to_clean(native_rig, clean_rig):
    native_names = {bone.name for bone in native_rig.data.bones}
    clean_names = {bone.name for bone in clean_rig.data.bones}
    if native_names != clean_names:
        raise RuntimeError(
            "Working/native bone names differ: missing={} extra={}".format(
                sorted(native_names - clean_names), sorted(clean_names - native_names)
            )
        )

    # C_pose * inverse(C_rest) = N_pose * inverse(N_rest).  Therefore both
    # armatures produce the same skin deformation even though their rest axes
    # and Blender bone tails are different.
    for clean_pose_bone in sorted(
        clean_rig.pose.bones, key=lambda bone: len(bone.parent_recursive)
    ):
        name = clean_pose_bone.name
        native_pose_world = native_rig.matrix_world @ native_rig.pose.bones[name].matrix
        native_rest_world = native_rig.matrix_world @ native_rig.data.bones[name].matrix_local
        clean_rest_world = clean_rig.matrix_world @ clean_rig.data.bones[name].matrix_local
        clean_pose_world = (
            native_pose_world
            @ native_rest_world.inverted_safe()
            @ clean_rest_world
        )
        clean_pose_bone.matrix = clean_rig.matrix_world.inverted_safe() @ clean_pose_world
        bpy.context.view_layer.update()


def fit_clean_rest_to_native_pose(native_rig, clean_rig):
    """Place Blender-oriented edit bones directly in the approved fitted pose."""
    clean_world = clean_rig.matrix_world.copy()
    clean_world_inverse = clean_world.inverted_safe()
    targets = {}
    for clean_bone in clean_rig.data.bones:
        name = clean_bone.name
        native_pose_world = native_rig.matrix_world @ native_rig.pose.bones[name].matrix
        native_rest_world = native_rig.matrix_world @ native_rig.data.bones[name].matrix_local
        deformation_world = native_pose_world @ native_rest_world.inverted_safe()
        clean_head_world = clean_world @ clean_bone.head_local
        clean_tail_world = clean_world @ clean_bone.tail_local
        targets[name] = (
            clean_world_inverse @ (deformation_world @ clean_head_world),
            clean_world_inverse @ (deformation_world @ clean_tail_world),
        )

    bpy.ops.object.mode_set(mode="OBJECT") if bpy.context.mode != "OBJECT" else None
    bpy.ops.object.select_all(action="DESELECT")
    clean_rig.hide_set(False)
    clean_rig.select_set(True)
    bpy.context.view_layer.objects.active = clean_rig
    bpy.ops.object.mode_set(mode="EDIT")
    for name, (head, tail) in targets.items():
        edit_bone = clean_rig.data.edit_bones[name]
        edit_bone.head = head
        edit_bone.tail = tail
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()


def connect_primary_working_chains(clean_rig):
    """Make the Blender-only rig read as continuous anatomical chains.

    Automatic Bone Orientation chooses the nearest/first child when a UEFN
    joint has several twist children. That leaves the main upperarm->lowerarm
    and thigh->calf bones spatially correct at their heads, but visually short
    and disconnected. This function changes only working-rig edit-bone tails
    and connection flags. Names, parents, joint heads, weights, and the hidden
    native export armature remain untouched.
    """
    chains = [
        ("pelvis", "spine_01", "spine_02", "spine_03", "spine_04", "spine_05", "neck_01", "neck_02", "head"),
    ]
    for side in ("l", "r"):
        chains.extend(
            [
                (f"clavicle_{side}", f"upperarm_{side}", f"lowerarm_{side}", f"hand_{side}", f"middle_metacarpal_{side}", f"middle_01_{side}", f"middle_02_{side}", f"middle_03_{side}"),
                (f"thigh_{side}", f"calf_{side}", f"foot_{side}", f"ball_{side}"),
                (f"index_metacarpal_{side}", f"index_01_{side}", f"index_02_{side}", f"index_03_{side}"),
                (f"pinky_metacarpal_{side}", f"pinky_01_{side}", f"pinky_02_{side}", f"pinky_03_{side}"),
                (f"ring_metacarpal_{side}", f"ring_01_{side}", f"ring_02_{side}", f"ring_03_{side}"),
                (f"thumb_01_{side}", f"thumb_02_{side}", f"thumb_03_{side}"),
            ]
        )

    bpy.ops.object.mode_set(mode="OBJECT") if bpy.context.mode != "OBJECT" else None
    bpy.ops.object.select_all(action="DESELECT")
    clean_rig.hide_set(False)
    clean_rig.select_set(True)
    bpy.context.view_layer.objects.active = clean_rig
    bpy.ops.object.mode_set(mode="EDIT")
    edit_bones = clean_rig.data.edit_bones
    connected_pairs = []
    for chain in chains:
        for parent_name, child_name in zip(chain, chain[1:]):
            parent = edit_bones[parent_name]
            child = edit_bones[child_name]
            parent.tail = child.head.copy()
            child.use_connect = True
            connected_pairs.append((parent_name, child_name))

    # Give the terminal toe/ball bones a short forward continuation instead of
    # Blender FBX importer's arbitrary long downward end-bone tail.
    for side in ("l", "r"):
        foot = edit_bones[f"foot_{side}"]
        ball = edit_bones[f"ball_{side}"]
        direction = ball.head - foot.head
        if direction.length > 1e-8:
            ball.tail = ball.head + direction.normalized() * 4.0

    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()
    return connected_pairs


def connected_chain_audit(rig, connected_pairs):
    gaps = []
    disconnected = []
    for parent_name, child_name in connected_pairs:
        parent = rig.data.bones[parent_name]
        child = rig.data.bones[child_name]
        gaps.append((parent.tail_local - child.head_local).length)
        if not child.use_connect:
            disconnected.append(child_name)
    return {
        "pair_count": len(connected_pairs),
        "maximum_tail_to_child_head_gap_cm": max(gaps, default=0.0),
        "children_missing_connect_flag": disconnected,
    }


def joint_alignment(native_rig, clean_rig):
    deltas = []
    for name in native_rig.pose.bones.keys():
        native_head = (native_rig.matrix_world @ native_rig.pose.bones[name].matrix).translation
        clean_head = (clean_rig.matrix_world @ clean_rig.pose.bones[name].matrix).translation
        deltas.append((native_head - clean_head).length)
    return {
        "joint_count": len(deltas),
        "maximum_head_delta_m": max(deltas),
        "rms_head_delta_m": math.sqrt(sum(delta * delta for delta in deltas) / len(deltas)),
    }


def conform_working_reference_geometry(native_mesh, clean_mesh):
    """Make the non-export working rig's rest state the approved fitted pose."""
    native_world_vertices = evaluated_vertices_world(native_mesh)

    if len(native_world_vertices) != len(clean_mesh.data.vertices):
        raise RuntimeError("Working/native reference vertex counts differ")
    world_to_clean = clean_mesh.matrix_world.inverted_safe()
    for vertex, native_world in zip(clean_mesh.data.vertices, native_world_vertices):
        vertex.co = world_to_clean @ native_world
    clean_mesh.data.update()
    bpy.context.view_layer.update()


def vertex_alignment(native_mesh, working_mesh):
    native_vertices = evaluated_vertices_world(native_mesh)
    working_vertices = evaluated_vertices_world(working_mesh)
    if len(native_vertices) != len(working_vertices):
        raise RuntimeError("Native and working UEFN meshes have different vertex counts")
    deltas = [
        (native - working).length
        for native, working in zip(native_vertices, working_vertices)
    ]
    return {
        "vertex_count": len(deltas),
        "maximum_world_delta_m": max(deltas),
        "rms_world_delta_m": math.sqrt(
            sum(delta * delta for delta in deltas) / len(deltas)
        ),
    }


def bone_visual_audit(rig):
    lengths = [bone.length for bone in rig.data.bones]
    child_head_errors = []
    for bone in rig.data.bones:
        children = list(bone.children)
        if not children:
            continue
        nearest_child = min(children, key=lambda child: (child.head_local - bone.tail_local).length)
        child_head_errors.append((bone.tail_local - nearest_child.head_local).length)
    return {
        "bone_count": len(lengths),
        "minimum_bone_length_cm": min(lengths),
        "maximum_bone_length_cm": max(lengths),
        "median_bone_length_cm": sorted(lengths)[len(lengths) // 2],
        "maximum_tail_to_nearest_child_head_cm": max(child_head_errors, default=0.0),
    }


def hide_visual_helpers(rig):
    hidden = []
    visible = []
    for bone in rig.data.bones:
        # Keep every bone in the armature, but hide the overlapping twist and
        # control/attachment chains by default so the primary deform chains
        # read like a normal Blender skeleton.  They can be revealed with
        # Alt-H whenever the user intentionally wants to weight to them.
        bone.hide = (
            bone.name.startswith("ik_")
            or bone.name.startswith("weapon_")
            or bone.name == "attach"
            or "_twist_" in bone.name
        )
        # Blender 5.1 stores pose-mode visibility/selection on PoseBone rather
        # than Bone, so set both layers explicitly. FBX import leaves every
        # pose bone selected, which otherwise keeps the helper shapes visible.
        pose_bone = rig.pose.bones.get(bone.name)
        if pose_bone:
            pose_bone.hide = bone.hide
            pose_bone.select = not bone.hide
        (hidden if bone.hide else visible).append(bone.name)
    return sorted(visible), sorted(hidden)


def world_bounds(meshes):
    vertices = []
    for mesh in meshes:
        vertices.extend(evaluated_vertices_world(mesh))
    minimum = Vector(tuple(min(vertex[index] for vertex in vertices) for index in range(3)))
    maximum = Vector(tuple(max(vertex[index] for vertex in vertices) for index in range(3)))
    return minimum, maximum


def render_views(working_mesh, body_mesh, face_mesh):
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
    working_mesh.color = (0.82, 0.31, 0.045, 1.0)
    body_mesh.color = (0.42, 0.48, 0.58, 1.0)
    face_mesh.color = (0.64, 0.49, 0.42, 1.0)

    minimum, maximum = world_bounds((working_mesh, body_mesh, face_mesh))
    center = (minimum + maximum) * 0.5
    height = maximum.z - minimum.z
    camera_data = bpy.data.cameras.new("CleanWorkingRig_Verify_Camera")
    camera_data.lens = 55
    camera_data.clip_start = 0.01
    camera_data.clip_end = 100.0
    camera = bpy.data.objects.new("CleanWorkingRig_Verify_Camera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera

    for location, output in (
        (center + Vector((0.0, -height * 1.45, height * 0.02)), FRONT_SHOT),
        (center + Vector((height * 1.45, 0.0, height * 0.02)), SIDE_SHOT),
    ):
        camera.location = location
        camera.rotation_euler = (center - location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(output)
        bpy.ops.render.render(write_still=True)

    bpy.data.objects.remove(camera, do_unlink=True)
    bpy.data.cameras.remove(camera_data)


def add_readme(audit):
    for name in ("README_MANUAL_UEFN_RIGGING_SOURCES", "README_UEFN_CONTROL_RIG"):
        old = bpy.data.texts.get(name)
        if old:
            bpy.data.texts.remove(old)
    text = bpy.data.texts.new("README_CLEAN_WORKING_AND_NATIVE_EXPORT_RIGS")
    text.write(
        "MANUAL UEFN SKINNING SETUP\n\n"
        "VISIBLE WORKING ARMATURE\n"
        "- UEFN_WORKING_CLEAN_RIG\n"
        "- Imported with Blender Automatic Bone Orientation.\n"
        "- Main anatomical chains were then connected by moving only Blender\n"
        "  working-rig bone tails; joint heads, parents, and names are unchanged.\n"
        "- Use this armature for selecting bones and painting/assigning weights.\n\n"
        "- Primary deform chains are visible. Twist, IK, weapon, and attachment\n"
        "  bones are retained but hidden for clarity; use Alt-H to reveal them.\n\n"
        "HIDDEN AUTHORITATIVE EXPORT ARMATURE\n"
        "- UEFN_NATIVE_EXPORT_RIG\n"
        "- Its native FBX rest matrices were not modified.\n"
        "- Do not edit its rest pose or apply Automatic Bone Orientation to it.\n"
        "- This is the armature to use for the final Unreal/UEFN export.\n\n"
        "The two armatures have identical bone names and hierarchy. Vertex group\n"
        "names created while weighting on the working rig therefore transfer to the\n"
        "native export rig without renaming. Do not export both armatures.\n\n"
        + json.dumps(audit, indent=2, sort_keys=True)
    )


def main():
    for path in (SOURCE_BLEND, UEFN_FBX):
        if not path.is_file():
            raise RuntimeError("Missing source: " + str(path))
    SHOTS.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE_BLEND))
    bpy.context.scene.frame_set(1)

    native_rig = bpy.data.objects.get("root")
    native_mesh = bpy.data.objects.get("SKM_UEFN_Mannequin_Posed")
    body_mesh = bpy.data.objects.get("ally2_Body_Mesh")
    face_mesh = bpy.data.objects.get("ally2_Face_Mesh")
    if not native_rig or native_rig.type != "ARMATURE":
        raise RuntimeError("Untouched native UEFN armature is missing")
    if not all(mesh and mesh.type == "MESH" for mesh in (native_mesh, body_mesh, face_mesh)):
        raise RuntimeError("One or more required source meshes are missing")

    native_rest_before = {
        bone.name: bone.matrix_local.copy() for bone in native_rig.data.bones
    }
    clean_objects = import_clean_fbx(UEFN_FBX)
    clean_rig = exactly_one(clean_objects, "ARMATURE")
    clean_mesh = exactly_one(clean_objects, "MESH")
    clean_wrapper = exactly_one(clean_objects, "EMPTY")
    working_collection = ensure_collection("UEFN_BLENDER_WORKING_RIG", "COLOR_04")
    move_objects(clean_objects, working_collection)

    clean_wrapper.name = "UEFN_WORKING_FBX_WRAPPER"
    clean_rig.name = "UEFN_WORKING_CLEAN_RIG"
    clean_rig.data.name = "UEFN_WORKING_CLEAN_ARMATURE"
    clean_mesh.name = "UEFN_WORKING_REFERENCE_MESH"
    clean_mesh.data.name = "UEFN_WORKING_REFERENCE_GEOMETRY"
    native_rig.name = "UEFN_NATIVE_EXPORT_RIG"
    native_rig.data.name = "UEFN_NATIVE_EXPORT_ARMATURE"
    native_mesh.name = "UEFN_NATIVE_EXPORT_REFERENCE_MESH"

    fit_clean_rest_to_native_pose(native_rig, clean_rig)
    connected_pairs = connect_primary_working_chains(clean_rig)
    bpy.context.view_layer.update()
    connection_audit = connected_chain_audit(clean_rig, connected_pairs)
    if (
        connection_audit["maximum_tail_to_child_head_gap_cm"] > 1e-6
        or connection_audit["children_missing_connect_flag"]
    ):
        raise RuntimeError("Primary working chains are not connected: " + str(connection_audit))
    joints = joint_alignment(native_rig, clean_rig)
    if joints["maximum_head_delta_m"] > 2e-4:
        raise RuntimeError("Clean/native joint heads do not align: " + str(joints))
    conform_working_reference_geometry(native_mesh, clean_mesh)
    alignment = vertex_alignment(native_mesh, clean_mesh)
    if alignment["maximum_world_delta_m"] > 2e-5:
        raise RuntimeError("Clean/native posed meshes do not align: " + str(alignment))

    native_rest_error = max(
        matrix_max_element_delta(matrix, native_rig.data.bones[name].matrix_local)
        for name, matrix in native_rest_before.items()
    )
    if native_rest_error > 1e-8:
        raise RuntimeError("Native UEFN rest skeleton was modified")

    clean_modifiers = [modifier for modifier in clean_mesh.modifiers if modifier.type == "ARMATURE"]
    if len(clean_modifiers) != 1 or clean_modifiers[0].object != clean_rig:
        raise RuntimeError("Working UEFN mesh is not bound to the clean working rig")
    native_modifiers = [modifier for modifier in native_mesh.modifiers if modifier.type == "ARMATURE"]
    if len(native_modifiers) != 1 or native_modifiers[0].object != native_rig:
        raise RuntimeError("Native UEFN mesh is not bound to the native export rig")

    clean_rig.data.display_type = "OCTAHEDRAL"
    clean_rig.data.show_names = False
    clean_rig.data.show_axes = False
    clean_rig.show_in_front = True
    clean_rig.hide_set(False)
    clean_mesh.hide_set(False)
    clean_mesh.show_wire = False
    visible_primary_bones, hidden_helper_bones = hide_visual_helpers(clean_rig)
    native_rig.hide_set(True)
    native_rig.hide_render = True
    native_mesh.hide_set(True)
    native_mesh.hide_render = True
    for collection_name in ("UEFN_POSE_GUIDE_DO_NOT_EXPORT", "SOURCE_UEFN_POSE_DO_NOT_EXPORT"):
        collection = bpy.data.collections.get(collection_name)
        if collection:
            collection.hide_viewport = True
            collection.hide_render = True

    render_views(clean_mesh, body_mesh, face_mesh)
    visual_audit = bone_visual_audit(clean_rig)
    audit = {
        "source_blend": str(SOURCE_BLEND),
        "source_uefn_fbx": str(UEFN_FBX),
        "output_blend": str(OUTPUT_BLEND),
        "blender_version": bpy.app.version_string,
        "working_armature": clean_rig.name,
        "working_armature_automatic_bone_orientation": True,
        "working_reference_mesh": clean_mesh.name,
        "native_export_armature": native_rig.name,
        "native_export_armature_automatic_bone_orientation": False,
        "native_export_reference_mesh": native_mesh.name,
        "native_rest_max_matrix_element_delta": native_rest_error,
        "bone_name_sets_identical": True,
        "working_mesh_modifier_target": clean_modifiers[0].object.name,
        "native_mesh_modifier_target": native_modifiers[0].object.name,
        "working_vs_native_fitted_pose": alignment,
        "working_vs_native_joint_heads_after_working_rest_build": joints,
        "working_armature_uses_fitted_pose_as_working_rest": True,
        "working_primary_chain_connection_audit": connection_audit,
        "working_bone_visual_audit": visual_audit,
        "visible_primary_bone_count": len(visible_primary_bones),
        "hidden_working_helper_or_twist_bone_count": len(hidden_helper_bones),
        "hidden_working_helper_or_twist_bones": hidden_helper_bones,
        "metahuman_body_mesh": body_mesh.name,
        "metahuman_face_mesh": face_mesh.name,
        "native_or_metahuman_geometry_or_weights_modified": False,
        "working_reference_geometry_conformed_to_native_fitted_pose": True,
    }
    add_readme(audit)
    OUTPUT_AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8")

    bpy.ops.object.mode_set(mode="OBJECT") if bpy.context.mode != "OBJECT" else None
    bpy.ops.object.select_all(action="DESELECT")
    clean_rig.select_set(True)
    bpy.context.view_layer.objects.active = clean_rig
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_BLEND))
    print("CLEAN_WORKING_RIG_AUDIT=" + json.dumps(audit, sort_keys=True))


main()
