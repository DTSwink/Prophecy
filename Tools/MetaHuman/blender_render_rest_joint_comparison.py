"""Render isolated rest-pose wrist/ankle silhouettes before weight iteration."""

import os

import bpy
from mathutils import Vector


PROJECT = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy"
EXCHANGE = os.path.join(PROJECT, "Saved", "BlenderExchange")
OUT_DIR = os.path.join(PROJECT, "Saved", "BlenderRestJointAudit")

VARIANTS = (
    ("OriginalMH", "fbx", "Body_Original_MH.fbx"),
    ("FittedMH342", "fbx", "Body_MH342.fbx"),
    ("ReducedUEFN", "blend", "Body_UEFN78.blend"),
    ("ReducedUEFN_DQ", "blend", "Body_UEFN78_DQ.blend"),
    ("RepairA", "blend", "Body_UEFN78_RepairA.blend"),
    ("RepairB", "blend", "Body_UEFN78_RepairB.blend"),
    ("RepairC", "blend", "Body_UEFN78_RepairC.blend"),
    ("CopyW", "blend", "Body_UEFN_CopyW.blend"),
)

JOINTS = (
    ("wrist_r", "lowerarm_r", "hand_r", 25.0),
    ("wrist_l", "lowerarm_l", "hand_l", 25.0),
    ("ankle_r", "calf_r", "foot_r", 34.0),
    ("ankle_l", "calf_l", "foot_l", 34.0),
)


def _look_at(camera, target):
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()


def _load(kind, filename):
    path = os.path.join(EXCHANGE, filename)
    if kind == "blend":
        bpy.ops.wm.open_mainfile(filepath=path)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(
            filepath=path,
            ignore_leaf_bones=False,
            automatic_bone_orientation=False,
            use_custom_normals=True,
        )
    mesh = max(
        (obj for obj in bpy.data.objects if obj.type == "MESH"),
        key=lambda obj: len(obj.data.vertices),
    )
    modifier = next(mod for mod in mesh.modifiers if mod.type == "ARMATURE")
    armature = modifier.object
    armature.data.pose_position = "REST"
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE":
            obj.hide_render = True
    bpy.context.view_layer.update()
    return mesh, armature


def _configure_scene(scene):
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "SINGLE"
    scene.display.shading.single_color = (0.58, 0.66, 0.78)
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "BOTH"
    scene.display.shading.curvature_ridge_factor = 1.4
    scene.display.shading.curvature_valley_factor = 1.4
    scene.render.resolution_x = 1000
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    if scene.world is None:
        scene.world = bpy.data.worlds.new("RestAuditWorld")
    scene.world.color = (0.025, 0.025, 0.025)


def _camera(scene):
    data = bpy.data.cameras.new("RestAuditCamera")
    data.type = "ORTHO"
    data.clip_start = 0.1
    data.clip_end = 1000.0
    camera = bpy.data.objects.new("RestAuditCamera", data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    return camera


def _render_variant(label, kind, filename):
    mesh, armature = _load(kind, filename)
    scene = bpy.context.scene
    _configure_scene(scene)
    camera = _camera(scene)
    arm_world = armature.matrix_world
    # UE FBX imports retain a 0.01 object scale, whereas the rebuilt .blend is
    # applied in centimetres.  Derive a per-file world scale so every shot is
    # an actual close-up rather than accepting a tiny silhouette as evidence.
    world_corners = [mesh.matrix_world @ Vector(corner) for corner in mesh.bound_box]
    body_height = max(v.z for v in world_corners) - min(v.z for v in world_corners)
    world_scale = body_height / 143.5
    camera.data.clip_start = max(0.0001, 0.1 * world_scale)
    camera.data.clip_end = max(10.0, 1000.0 * world_scale)

    for joint_label, parent_name, child_name, ortho_scale in JOINTS:
        parent = arm_world @ armature.data.bones[parent_name].head_local
        child = arm_world @ armature.data.bones[child_name].head_local
        axis = (child - parent).normalized()
        side = axis.cross(Vector((0.0, 0.0, 1.0)))
        if side.length < 0.2:
            side = axis.cross(Vector((0.0, 1.0, 0.0)))
        side.normalize()
        top = axis.cross(side).normalized()
        focus = child - axis * 1.5 * world_scale
        camera.data.ortho_scale = ortho_scale * world_scale
        for view_name, direction in (("side", side), ("top", top)):
            camera.location = focus + direction * 80.0 * world_scale
            _look_at(camera, focus)
            path = os.path.join(
                OUT_DIR, "{}_{}_{}.png".format(label, joint_label, view_name)
            )
            scene.render.filepath = path
            bpy.ops.render.render(write_still=True)
            print("REST_SHOT|" + path)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for label, kind, filename in VARIANTS:
        _render_variant(label, kind, filename)
    print("REST_JOINT_COMPARISON_DONE")


main()
