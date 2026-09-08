"""Import the untouched UEFN mannequin rig and mesh into a verified Blender file.

The Unreal FBX export represents the UE ``root`` joint as the Blender armature
object named ``root``. The other 87 joints remain Blender bones. This is the
expected round-trip representation and must not be "fixed" by renaming the
armature or adding an extra Blender root bone.

The deform armature is imported with automatic bone orientation disabled so
the FBX bind/rest data remains intact. A separate cyan curve visualizes the
parent-child joint links without changing the deform skeleton.
"""

import json
import math
import os
from pathlib import Path

import bpy
from mathutils import Vector


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
EXCHANGE = PROJECT / "Saved" / "BlenderExchange"
SHOTS = PROJECT / "Saved" / "BlenderShots"
SOURCE_FBX = EXCHANGE / "UEFN_Mannequin_RigMesh.fbx"
SOURCE_ANIM_FBX = EXCHANGE / "Anim_Idle.fbx"
SNAPSHOT = PROJECT / "Tools" / "MetaHuman" / "skeleton_snapshots.json"
OUT_BLEND = EXCHANGE / "UEFN_Mannequin_RigMesh.blend"
OUT_AUDIT = EXCHANGE / "UEFN_Mannequin_RigMesh_Audit.json"
FRONT_SHOT = SHOTS / "UEFN_RigMesh_Front.png"
SIDE_SHOT = SHOTS / "UEFN_RigMesh_Side.png"


def import_fbx(filepath, use_anim=False):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(
        filepath=str(filepath),
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
    return list(set(bpy.data.objects) - before)


def mapped_ue_position(translation_cm):
    # Unreal is left-handed X-forward/Y-right/Z-up. Blender's FBX conversion
    # keeps X/Z and negates Y in the armature's centimeter-space bone data.
    return Vector((
        float(translation_cm[0]),
        -float(translation_cm[1]),
        float(translation_cm[2]),
    ))


def ensure_collection(name):
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    return collection


def move_to_collection(obj, collection):
    for current in list(obj.users_collection):
        current.objects.unlink(obj)
    collection.objects.link(obj)


def add_visual_guide(armature, deform_names):
    guide_collection = ensure_collection("VISUAL_GUIDE_DO_NOT_EXPORT")
    guide_collection.color_tag = "COLOR_04"

    curve_data = bpy.data.curves.new("UEFN_Deform_Hierarchy_Links", type="CURVE")
    curve_data.dimensions = "3D"
    curve_data.bevel_depth = 0.003
    curve_data.bevel_resolution = 2
    curve_data.resolution_u = 1

    world_origin = armature.matrix_world.translation
    for bone in armature.data.bones:
        if bone.name not in deform_names:
            continue

        head = armature.matrix_world @ bone.head_local
        parent = bone.parent
        while parent is not None and parent.name not in deform_names:
            parent = parent.parent
        start = (
            armature.matrix_world @ parent.head_local
            if parent is not None
            else world_origin
        )

        if (head - start).length < 1e-5:
            # Root-level zero-length links need a visible direction. Use the
            # imported bone tail, which is display-only here.
            tail = armature.matrix_world @ bone.tail_local
            if (tail - head).length < 1e-5:
                continue
            start = head
            head = tail

        spline = curve_data.splines.new("POLY")
        spline.points.add(1)
        spline.points[0].co = (*start, 1.0)
        spline.points[1].co = (*head, 1.0)

    guide = bpy.data.objects.new(
        "UEFN_DeformSkeleton_VisualGuide_DO_NOT_EXPORT",
        curve_data,
    )
    guide.color = (0.02, 0.8, 1.0, 1.0)
    guide.show_in_front = True
    guide_collection.objects.link(guide)

    material = bpy.data.materials.new("M_UEFN_SkeletonGuide_Cyan")
    material.diffuse_color = (0.02, 0.8, 1.0, 1.0)
    curve_data.materials.append(material)
    return guide


def add_readme(audit):
    text = bpy.data.texts.new("README_UEFN_RIG")
    text.write(
        "UEFN mannequin rig + mesh exported from Unreal Engine 5.7.\n\n"
        "AUTHORITATIVE DEFORM RIG\n"
        "- Armature object: root\n"
        "- Mesh object: SKM_UEFN_Mannequin\n"
        "- The UE root joint is represented by the armature object named root.\n"
        "- The other 87 UE joints are Blender bones.\n"
        "- Do NOT rename root to Armature.\n"
        "- Do NOT add another root bone.\n"
        "- Do NOT apply Automatic Bone Orientation.\n"
        "- Do NOT delete leaf bones.\n"
        "- Do NOT apply the FBX centimeter wrapper transform.\n\n"
        "DISPLAY\n"
        "- The cyan VISUAL_GUIDE_DO_NOT_EXPORT collection shows only weighted\n"
        "  anatomical links, without modifying the complete rig or its matrices.\n"
        "- Never include that collection in an FBX export.\n\n"
        "ROUND TRIP\n"
        "- Export only root + SKM_UEFN_Mannequin.\n"
        "- Keep leaf bones disabled on Blender export.\n"
        "- Preserve object transforms; do not apply transforms to the rig.\n\n"
        "AUDIT SUMMARY\n"
        + json.dumps(audit, indent=2, sort_keys=True)
    )


def look_at(camera, target):
    direction = target - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


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
        scene.world = bpy.data.worlds.new("UEFN_AuditWorld")
    scene.world.color = (0.025, 0.025, 0.025)

    mesh.color = (0.32, 0.36, 0.42, 1.0)
    corners = [mesh.matrix_world @ Vector(corner) for corner in mesh.bound_box]
    minimum = Vector((
        min(v.x for v in corners),
        min(v.y for v in corners),
        min(v.z for v in corners),
    ))
    maximum = Vector((
        max(v.x for v in corners),
        max(v.y for v in corners),
        max(v.z for v in corners),
    ))
    center = (minimum + maximum) * 0.5
    height = maximum.z - minimum.z
    distance = height * 1.35

    camera_data = bpy.data.cameras.new("UEFN_AuditCamera")
    camera_data.lens = 52
    camera_data.clip_start = 0.01
    camera_data.clip_end = 100.0
    camera = bpy.data.objects.new("UEFN_AuditCamera", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    scene.camera = camera

    camera.location = center + Vector((0.0, -distance, height * 0.03))
    look_at(camera, center)
    scene.render.filepath = str(FRONT_SHOT)
    bpy.ops.render.render(write_still=True)

    camera.location = center + Vector((distance, 0.0, height * 0.03))
    look_at(camera, center)
    scene.render.filepath = str(SIDE_SHOT)
    bpy.ops.render.render(write_still=True)

    bpy.data.objects.remove(camera, do_unlink=True)
    bpy.data.cameras.remove(camera_data)


def main():
    EXCHANGE.mkdir(parents=True, exist_ok=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    if not SOURCE_FBX.is_file():
        raise RuntimeError("Missing Unreal FBX export: " + str(SOURCE_FBX))
    if not SNAPSHOT.is_file():
        raise RuntimeError("Missing skeleton snapshot: " + str(SNAPSHOT))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "METERS"

    imported = import_fbx(SOURCE_FBX, use_anim=False)
    armatures = [obj for obj in imported if obj.type == "ARMATURE"]
    meshes = [obj for obj in imported if obj.type == "MESH"]
    if len(armatures) != 1 or len(meshes) != 1:
        raise RuntimeError(
            "Expected one armature and one mesh, got armatures={} meshes={}".format(
                len(armatures), len(meshes)
            )
        )
    armature = armatures[0]
    mesh = meshes[0]
    if armature.name != "root":
        raise RuntimeError(
            "UE root node was not preserved as armature object 'root': "
            + armature.name
        )

    with SNAPSHOT.open("r", encoding="utf-8") as handle:
        snapshot = json.load(handle)["uefn_reference"]
    expected_bones = {entry["name"]: entry for entry in snapshot["bones"]}
    expected_blender_names = set(expected_bones) - {"root"}
    actual_names = {bone.name for bone in armature.data.bones}
    missing = sorted(expected_blender_names - actual_names)
    unexpected = sorted(actual_names - expected_blender_names)
    if missing or unexpected:
        raise RuntimeError(
            "Bone set mismatch. Missing={} Unexpected={}".format(
                missing, unexpected
            )
        )

    parent_errors = []
    head_errors = []
    determinant_errors = []
    for bone in armature.data.bones:
        entry = expected_bones[bone.name]
        expected_parent = entry["parent"]
        if expected_parent == "root":
            expected_parent = None
        actual_parent = bone.parent.name if bone.parent else None
        if actual_parent != expected_parent:
            parent_errors.append({
                "bone": bone.name,
                "expected": expected_parent,
                "actual": actual_parent,
            })

        expected_head = mapped_ue_position(entry["global"]["translation_cm"])
        head_delta_cm = (bone.head_local - expected_head).length
        head_errors.append((head_delta_cm, bone.name))

        determinant = bone.matrix_local.to_3x3().determinant()
        determinant_errors.append((abs(determinant - 1.0), bone.name, determinant))

    head_errors.sort(reverse=True)
    determinant_errors.sort(reverse=True)
    if parent_errors:
        raise RuntimeError("Hierarchy mismatch: " + json.dumps(parent_errors))
    if head_errors[0][0] > 0.01:
        raise RuntimeError(
            "Imported joint heads do not match UE reference; worst={}".format(
                head_errors[0]
            )
        )
    if determinant_errors[0][0] > 1e-4:
        raise RuntimeError(
            "Non-orthonormal rest matrix detected; worst={}".format(
                determinant_errors[0]
            )
        )

    armature_modifiers = [
        modifier for modifier in mesh.modifiers if modifier.type == "ARMATURE"
    ]
    if (
        len(armature_modifiers) != 1
        or armature_modifiers[0].object != armature
    ):
        raise RuntimeError("Mesh is not bound to the imported root armature")

    unknown_groups = sorted(
        group.name
        for group in mesh.vertex_groups
        if group.name not in actual_names
    )
    if unknown_groups:
        raise RuntimeError("Vertex groups without bones: " + str(unknown_groups))

    unweighted_vertices = 0
    max_weight_sum_error = 0.0
    for vertex in mesh.data.vertices:
        total = sum(group.weight for group in vertex.groups)
        if total <= 1e-8:
            unweighted_vertices += 1
        max_weight_sum_error = max(max_weight_sum_error, abs(total - 1.0))
    if unweighted_vertices:
        raise RuntimeError(
            "{} unweighted vertices in mannequin mesh".format(unweighted_vertices)
        )
    if max_weight_sum_error > 1e-4:
        raise RuntimeError(
            "Vertex weights are not normalized; max error={}".format(
                max_weight_sum_error
            )
        )

    animation_rest_audit = {
        "available": SOURCE_ANIM_FBX.is_file(),
        "shared_bones": 0,
        "max_translation_delta_cm": None,
        "max_rotation_delta_deg": None,
    }
    if SOURCE_ANIM_FBX.is_file():
        animation_objects = import_fbx(SOURCE_ANIM_FBX, use_anim=True)
        animation_arms = [
            obj for obj in animation_objects if obj.type == "ARMATURE"
        ]
        if len(animation_arms) != 1:
            raise RuntimeError(
                "Expected one animation armature, got {}".format(
                    len(animation_arms)
                )
            )
        animation_arm = animation_arms[0]
        shared = sorted(actual_names & {b.name for b in animation_arm.data.bones})
        max_translation = 0.0
        max_rotation = 0.0
        for name in shared:
            source_matrix = armature.data.bones[name].matrix_local
            anim_matrix = animation_arm.data.bones[name].matrix_local
            max_translation = max(
                max_translation,
                (source_matrix.translation - anim_matrix.translation).length,
            )
            max_rotation = max(
                max_rotation,
                source_matrix.to_quaternion()
                .rotation_difference(anim_matrix.to_quaternion())
                .angle,
            )
        animation_rest_audit.update({
            "shared_bones": len(shared),
            "max_translation_delta_cm": max_translation,
            "max_rotation_delta_deg": math.degrees(max_rotation),
        })
        if len(shared) != len(actual_names):
            raise RuntimeError(
                "UEFN animation rest skeleton does not contain every mesh bone"
            )
        if max_translation > 0.01 or math.degrees(max_rotation) > 0.01:
            raise RuntimeError(
                "Mesh/animation rest matrices disagree: "
                + json.dumps(animation_rest_audit)
            )
        for obj in animation_objects:
            bpy.data.objects.remove(obj, do_unlink=True)

    deform_collection = ensure_collection("UEFN_DEFORM_RIG_EXPORT_THESE")
    deform_collection.color_tag = "COLOR_05"
    for obj in imported:
        move_to_collection(obj, deform_collection)

    armature.data.display_type = "STICK"
    armature.show_in_front = True
    armature.data.show_names = False
    armature.data.show_axes = False
    mesh.name = "SKM_UEFN_Mannequin"
    mesh.data.name = "SKM_UEFN_Mannequin_Mesh"
    mesh.show_in_front = False

    deform_names = {group.name for group in mesh.vertex_groups}
    guide = add_visual_guide(armature, deform_names)

    world_corners = [mesh.matrix_world @ Vector(corner) for corner in mesh.bound_box]
    world_dimensions = [
        max(v[i] for v in world_corners) - min(v[i] for v in world_corners)
        for i in range(3)
    ]
    if not 1.5 < world_dimensions[2] < 2.0:
        raise RuntimeError(
            "Mannequin world height is not human scale in meters: "
            + str(world_dimensions)
        )

    audit = {
        "source_fbx": str(SOURCE_FBX),
        "output_blend": str(OUT_BLEND),
        "ue_reference_bone_count": int(snapshot["bone_count"]),
        "blender_armature_object": armature.name,
        "blender_bone_count": len(actual_names),
        "root_representation": "armature object named root",
        "missing_bones": missing,
        "unexpected_bones": unexpected,
        "hierarchy_error_count": len(parent_errors),
        "max_joint_head_error_cm": head_errors[0][0],
        "max_joint_head_error_bone": head_errors[0][1],
        "max_rest_matrix_determinant_error": determinant_errors[0][0],
        "vertex_count": len(mesh.data.vertices),
        "polygon_count": len(mesh.data.polygons),
        "vertex_group_count": len(mesh.vertex_groups),
        "unweighted_vertices": unweighted_vertices,
        "max_weight_sum_error": max_weight_sum_error,
        "world_dimensions_m": world_dimensions,
        "armature_world_scale": list(armature.matrix_world.to_scale()),
        "mesh_world_scale": list(mesh.matrix_world.to_scale()),
        "automatic_bone_orientation": False,
        "ignore_leaf_bones": False,
        "use_prepost_rot": True,
        "animation_rest_audit": animation_rest_audit,
        "visual_guide": guide.name,
        "visual_guide_is_deforming": False,
    }

    add_readme(audit)
    render_views(mesh)

    OUT_AUDIT.write_text(
        json.dumps(audit, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND))

    print("UEFN_BLEND_AUDIT=" + json.dumps(audit, sort_keys=True))
    print("UEFN_BLEND_SAVED=" + str(OUT_BLEND))
    print("UEFN_FRONT_SHOT=" + str(FRONT_SHOT))
    print("UEFN_SIDE_SHOT=" + str(SIDE_SHOT))


main()
