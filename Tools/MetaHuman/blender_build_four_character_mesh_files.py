"""Build four mesh-only Blender files from Unreal-exported MetaHuman FBXs."""

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
SOURCE_DIR = PROJECT / "Saved" / "BlenderExchange" / "FourCharacters"
OUTPUT_DIR = SOURCE_DIR
SHOT_DIR = PROJECT / "Saved" / "BlenderShots" / "FourCharacters"
COMBINED_AUDIT = OUTPUT_DIR / "BlenderMeshFiles_Audit.json"

CHARACTERS = {
    "BP_boss": ("BP_boss_Body.fbx", "BP_boss_Face.fbx"),
    "BP_Enemy": ("BP_Enemy_Body.fbx", "BP_Enemy_Face.fbx"),
    "BP_girl": ("BP_girl_Body.fbx", "BP_girl_Face.fbx"),
    "BP_savagee": ("BP_savagee_Body.fbx", "BP_savagee_Face.fbx"),
}


def import_fbx(path):
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
        automatic_bone_orientation=False,
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
            "Expected one {} object, got {}: {}".format(
                object_type, len(matches), [obj.name for obj in matches]
            )
        )
    return matches[0]


def evaluated_world_vertices(mesh):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = mesh.evaluated_get(depsgraph)
    evaluated_mesh = evaluated.to_mesh()
    try:
        return [evaluated.matrix_world @ vertex.co for vertex in evaluated_mesh.vertices]
    finally:
        evaluated.to_mesh_clear()


def pose_basis_audit(rig):
    max_translation = 0.0
    max_rotation_deg = 0.0
    max_scale_delta = 0.0
    for bone in rig.pose.bones:
        basis = bone.matrix_basis
        max_translation = max(max_translation, basis.translation.length)
        max_rotation_deg = max(max_rotation_deg, math.degrees(basis.to_quaternion().angle))
        max_scale_delta = max(
            max_scale_delta,
            (basis.to_scale() - Vector((1.0, 1.0, 1.0))).length,
        )
    return {
        "maximum_translation": max_translation,
        "maximum_rotation_deg": max_rotation_deg,
        "maximum_scale_delta": max_scale_delta,
    }


def shared_joint_audit(body_rig, face_rig):
    shared = sorted(set(body_rig.pose.bones.keys()) & set(face_rig.pose.bones.keys()))
    rows = []
    for name in shared:
        body_matrix = body_rig.matrix_world @ body_rig.pose.bones[name].matrix
        face_matrix = face_rig.matrix_world @ face_rig.pose.bones[name].matrix
        rows.append(
            {
                "bone": name,
                "translation_delta_m": (body_matrix.translation - face_matrix.translation).length,
                "rotation_delta_deg": math.degrees(
                    body_matrix.to_quaternion()
                    .rotation_difference(face_matrix.to_quaternion())
                    .angle
                ),
            }
        )
    return {
        "shared_bone_count": len(shared),
        "maximum_translation_delta_m": max(
            (row["translation_delta_m"] for row in rows), default=0.0
        ),
        "maximum_rotation_delta_deg": max(
            (row["rotation_delta_deg"] for row in rows), default=0.0
        ),
        "worst_translation_rows": sorted(
            rows, key=lambda row: row["translation_delta_m"], reverse=True
        )[:5],
    }


def strip_rig_preserving_geometry(mesh, imported_objects):
    before = evaluated_world_vertices(mesh)
    world_matrix = mesh.matrix_world.copy()
    for modifier in list(mesh.modifiers):
        if modifier.type == "ARMATURE":
            mesh.modifiers.remove(modifier)
    mesh.parent = None
    mesh.matrix_world = world_matrix
    for group in list(mesh.vertex_groups):
        mesh.vertex_groups.remove(group)
    for obj in list(imported_objects):
        if obj != mesh and obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.context.view_layer.update()
    after = evaluated_world_vertices(mesh)
    if len(before) != len(after):
        raise RuntimeError("Geometry vertex count changed while stripping rig")
    deltas = [(left - right).length for left, right in zip(before, after)]
    return {
        "vertex_count": len(mesh.data.vertices),
        "polygon_count": len(mesh.data.polygons),
        "maximum_world_vertex_delta_m": max(deltas, default=0.0),
        "remaining_modifier_count": len(mesh.modifiers),
        "remaining_vertex_group_count": len(mesh.vertex_groups),
        "world_scale": list(mesh.matrix_world.to_scale()),
    }


def world_bounds(meshes):
    vertices = []
    for mesh in meshes:
        vertices.extend(evaluated_world_vertices(mesh))
    minimum = Vector(tuple(min(vertex[index] for vertex in vertices) for index in range(3)))
    maximum = Vector(tuple(max(vertex[index] for vertex in vertices) for index in range(3)))
    return minimum, maximum


def render_views(character, body_mesh, face_mesh):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "WORLD"
    scene.display.shading.show_specular_highlight = True
    scene.render.resolution_x = 1000
    scene.render.resolution_y = 1200
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new(character + "_World")
    scene.world.color = (0.025, 0.025, 0.025)
    body_mesh.color = (0.37, 0.46, 0.62, 1.0)
    face_mesh.color = (0.66, 0.49, 0.39, 1.0)

    minimum, maximum = world_bounds((body_mesh, face_mesh))
    center = (minimum + maximum) * 0.5
    height = maximum.z - minimum.z
    camera_data = bpy.data.cameras.new(character + "_VerifyCamera")
    camera_data.lens = 55
    camera_data.clip_start = 0.01
    camera_data.clip_end = 100.0
    camera = bpy.data.objects.new(character + "_VerifyCamera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera

    outputs = {}
    for suffix, location in (
        ("Front", center + Vector((0.0, -height * 1.45, height * 0.02))),
        ("Side", center + Vector((height * 1.45, 0.0, height * 0.02))),
    ):
        output = SHOT_DIR / "{}_{}.png".format(character, suffix)
        camera.location = location
        camera.rotation_euler = (center - location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(output)
        bpy.ops.render.render(write_still=True)
        outputs[suffix.lower()] = str(output)

    bpy.data.objects.remove(camera, do_unlink=True)
    bpy.data.cameras.remove(camera_data)
    return minimum, maximum, outputs


def add_readme(character, audit):
    text = bpy.data.texts.new("README_{}_MESH_ONLY".format(character))
    text.write(
        "{} MESH-ONLY SOURCE\n\n"
        "Objects:\n"
        "- {}_Body_Mesh\n"
        "- {}_Face_Mesh\n\n"
        "No UEFN mannequin, armature, animation, modifier, or vertex group is included.\n"
        "The two source rigs were removed only after preserving evaluated world geometry.\n\n"
        "{}".format(character, character, character, json.dumps(audit, indent=2, sort_keys=True))
    )


def build_character(character, body_filename, face_filename):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    body_path = SOURCE_DIR / body_filename
    face_path = SOURCE_DIR / face_filename
    for path in (body_path, face_path):
        if not path.is_file():
            raise RuntimeError("Missing source FBX: " + str(path))

    body_objects = import_fbx(body_path)
    face_objects = import_fbx(face_path)
    body_mesh = exactly_one(body_objects, "MESH")
    body_rig = exactly_one(body_objects, "ARMATURE")
    face_mesh = exactly_one(face_objects, "MESH")
    face_rig = exactly_one(face_objects, "ARMATURE")
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()

    body_pose = pose_basis_audit(body_rig)
    face_pose = pose_basis_audit(face_rig)
    if body_pose["maximum_translation"] > 1e-3 or body_pose["maximum_rotation_deg"] > 1e-4:
        raise RuntimeError("Body FBX imported with an unexpected pose: " + str(body_pose))
    if face_pose["maximum_translation"] > 1e-3 or face_pose["maximum_rotation_deg"] > 1e-4:
        raise RuntimeError("Face FBX imported with an unexpected pose: " + str(face_pose))
    shared_joints = shared_joint_audit(body_rig, face_rig)
    if shared_joints["maximum_translation_delta_m"] > 1e-5:
        raise RuntimeError("Body and face are not aligned: " + str(shared_joints))

    body_mesh.name = character + "_Body_Mesh"
    body_mesh.data.name = character + "_Body_Geometry"
    face_mesh.name = character + "_Face_Mesh"
    face_mesh.data.name = character + "_Face_Geometry"
    body_geometry = strip_rig_preserving_geometry(body_mesh, body_objects)
    face_geometry = strip_rig_preserving_geometry(face_mesh, face_objects)
    # Removing an identity Armature modifier in Blender 5.1 changes evaluated
    # coordinates by sub-micrometer floating-point residue. Two micrometers is
    # still far below any visible or practical mesh-authoring tolerance.
    if body_geometry["maximum_world_vertex_delta_m"] > 2e-6:
        raise RuntimeError("Body geometry moved while stripping its rig: " + str(body_geometry))
    if face_geometry["maximum_world_vertex_delta_m"] > 2e-6:
        raise RuntimeError("Face geometry moved while stripping its rig: " + str(face_geometry))

    minimum, maximum, shots = render_views(character, body_mesh, face_mesh)
    dimensions = list(maximum - minimum)
    if not 1.5 < dimensions[2] < 2.1:
        raise RuntimeError("Mesh-only character is not human-scale: " + str(dimensions))

    output_blend = OUTPUT_DIR / "{}_Meshes.blend".format(character)
    audit = {
        "character": character,
        "body_fbx": str(body_path),
        "face_fbx": str(face_path),
        "output_blend": str(output_blend),
        "body_mesh": body_mesh.name,
        "face_mesh": face_mesh.name,
        "body_source_pose_basis": body_pose,
        "face_source_pose_basis": face_pose,
        "body_face_shared_joint_audit": shared_joints,
        "body_geometry": body_geometry,
        "face_geometry": face_geometry,
        "world_dimensions_m": dimensions,
        "visual_checks": shots,
        "uefn_objects_included": False,
        "armature_objects_included": False,
        "mesh_only_object_count": 2,
    }
    add_readme(character, audit)

    bpy.ops.object.select_all(action="DESELECT")
    body_mesh.select_set(True)
    face_mesh.select_set(True)
    bpy.context.view_layer.objects.active = body_mesh
    objects = list(bpy.context.scene.objects)
    if len(objects) != 2 or any(obj.type != "MESH" for obj in objects):
        raise RuntimeError("Output scene contains non-mesh objects: " + str([(obj.name, obj.type) for obj in objects]))
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))

    bpy.ops.wm.open_mainfile(filepath=str(output_blend))
    reopened = list(bpy.context.scene.objects)
    audit["post_save_reopen"] = {
        "object_count": len(reopened),
        "objects": sorted((obj.name, obj.type) for obj in reopened),
        "armature_count": sum(obj.type == "ARMATURE" for obj in reopened),
        "uefn_named_object_count": sum("UEFN" in obj.name.upper() for obj in reopened),
    }
    if (
        audit["post_save_reopen"]["object_count"] != 2
        or audit["post_save_reopen"]["armature_count"] != 0
        or audit["post_save_reopen"]["uefn_named_object_count"] != 0
    ):
        raise RuntimeError("Saved file reopen audit failed: " + str(audit["post_save_reopen"]))

    audit_path = OUTPUT_DIR / "{}_Meshes_Audit.json".format(character)
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8")
    return audit


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    reports = {}
    for character, filenames in CHARACTERS.items():
        reports[character] = build_character(character, *filenames)
    COMBINED_AUDIT.write_text(
        json.dumps(reports, indent=2, sort_keys=True), encoding="utf-8"
    )
    print("FOUR_CHARACTER_BLENDER_AUDIT=" + json.dumps(reports, sort_keys=True))


main()
