"""Render focused wrist/ankle checks for current Blender variants.

All positions are centimeters: imported Unreal FBX geometry is about 160
Blender coordinate units tall even when scene.unit_settings.scale_length=0.01.
"""

import math
import os

import bpy
from mathutils import Vector


PROJECT = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy"
EXCHANGE = os.path.join(PROJECT, "Saved", "BlenderExchange")
OUT_DIR = os.path.join(PROJECT, "Saved", "BlenderJointAudit")
FPS = 30

VARIANTS = (
    ("ReducedMH", "Body_UEFN78.blend"),
    ("Ancestor", "Body_UEFN78_Ancestor.blend"),
    ("CopyW", "Body_UEFN_CopyW.blend"),
)

CLIPS = (
    ("Climb", "Anim_Climb.fbx", 2.0),
    ("CliffCatch", "Anim_CliffCatch.fbx", 0.8),
)

JOINTS = (
    ("wrist_r", "lowerarm_r", "hand_r", 38.0),
    ("wrist_l", "lowerarm_l", "hand_l", 38.0),
    ("ankle_r", "calf_r", "foot_r", 44.0),
    ("ankle_l", "calf_l", "foot_l", 44.0),
)


def _look_at(camera, target):
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()


def _render(scene, path):
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("SHOT|" + path)


def _scene_camera(scene):
    camera_data = bpy.data.cameras.new("JointAuditCamera")
    camera_data.clip_start = 0.1
    camera_data.clip_end = 1000.0
    camera_data.lens = 62.0
    camera = bpy.data.objects.new("JointAuditCamera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    return camera


def _configure_scene(scene):
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "SINGLE"
    scene.display.shading.single_color = (0.63, 0.68, 0.78)
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "BOTH"
    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new("JointAuditWorld")
    scene.world.color = (0.035, 0.035, 0.035)
    scene.render.fps = FPS


def _main_objects():
    mesh = max(
        (obj for obj in bpy.data.objects if obj.type == "MESH"),
        key=lambda obj: len(obj.data.vertices),
    )
    modifier = next(mod for mod in mesh.modifiers if mod.type == "ARMATURE")
    return mesh, modifier.object, modifier


def _render_variant(label, blend_name):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(EXCHANGE, blend_name))
    scene = bpy.context.scene
    _configure_scene(scene)
    camera = _scene_camera(scene)
    mesh, body_armature, modifier = _main_objects()
    body_world = body_armature.matrix_world.copy()
    mesh_relative = body_world.inverted() @ mesh.matrix_world.copy()

    for clip_label, clip_file, sample_time in CLIPS:
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(
            filepath=os.path.join(EXCHANGE, clip_file),
            ignore_leaf_bones=False,
            automatic_bone_orientation=False,
        )
        imported = list(set(bpy.data.objects) - before)
        anim_armature = next(obj for obj in imported if obj.type == "ARMATURE")
        for obj in imported:
            obj.hide_render = True
        anim_armature.matrix_world = body_world
        modifier.object = anim_armature

        scene.frame_set(int(round(sample_time * FPS)))
        mesh.matrix_world = anim_armature.matrix_world @ mesh_relative
        bpy.context.view_layer.update()

        for joint_label, parent_name, child_name, distance in JOINTS:
            parent = anim_armature.matrix_world @ anim_armature.pose.bones[parent_name].head
            child = anim_armature.matrix_world @ anim_armature.pose.bones[child_name].head
            axis = (child - parent).normalized()
            side = axis.cross(Vector((0.0, 0.0, 1.0)))
            if side.length < 0.2:
                side = axis.cross(Vector((0.0, 1.0, 0.0)))
            side.normalize()
            focus = child - axis * 1.0
            camera.location = focus + side * distance + Vector((0.0, 0.0, 5.0))
            _look_at(camera, focus)
            _render(
                scene,
                os.path.join(
                    OUT_DIR,
                    "{}_{}_{}.png".format(label, clip_label, joint_label),
                ),
            )

        modifier.object = body_armature
        for obj in imported:
            bpy.data.objects.remove(obj, do_unlink=True)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    requested = {
        item.strip()
        for item in os.environ.get("PROPHECY_MH_AUDIT_VARIANTS", "").split(",")
        if item.strip()
    }
    for label, blend_name in VARIANTS:
        if requested and label not in requested:
            continue
        _render_variant(label, blend_name)
    print("JOINT_RENDER_DONE")


main()
