"""Quick headless preview of the MTM-converted body in climb/cliff poses."""

import math
import os
import sys

import bpy
from mathutils import Vector

EXCHANGE = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\BlenderExchange"
OUT_DIR = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\BlenderShots"
FPS = 30

SHOTS = [
    ("Anim_Climb.fbx", "Climb", 2.0),
    ("Anim_CliffCatch.fbx", "CliffCatch", 0.8),
]


def look_at(camera, target):
    direction = target - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


bpy.ops.wm.open_mainfile(filepath=os.path.join(EXCHANGE, "Body_UEFN78.blend"))
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "SINGLE"
scene.display.shading.single_color = (0.75, 0.75, 0.78)
scene.render.resolution_x = 1200
scene.render.resolution_y = 1200

body_arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
mesh_obj = next(o for o in bpy.data.objects if o.type == "MESH")
body_matrix = body_arm.matrix_world.copy()
mesh_relative = body_matrix.inverted() @ mesh_obj.matrix_world.copy()

camera_data = bpy.data.cameras.new("Cam")
camera_data.clip_start = 0.01
camera_data.clip_end = 1000.0
camera = bpy.data.objects.new("Cam", camera_data)
scene.collection.objects.link(camera)
scene.camera = camera

modifier = next(m for m in mesh_obj.modifiers if m.type == "ARMATURE")

for anim_file, label, sample_time in SHOTS:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(
        filepath=os.path.join(EXCHANGE, anim_file),
        ignore_leaf_bones=False,
        automatic_bone_orientation=False,
    )
    imported = [o for o in set(bpy.data.objects) - before]
    anim_arm = next(o for o in imported if o.type == "ARMATURE")
    anim_arm.matrix_world = body_matrix
    modifier.object = anim_arm
    for obj in imported:
        obj.hide_render = True

    scene.frame_set(int(round(sample_time * FPS)))
    bpy.context.view_layer.update()
    mesh_obj.matrix_world = anim_arm.matrix_world @ mesh_relative
    bpy.context.view_layer.update()

    head = anim_arm.matrix_world @ anim_arm.pose.bones["head"].head
    pelvis = anim_arm.matrix_world @ anim_arm.pose.bones["pelvis"].head
    center = (head + pelvis) / 2.0
    camera.location = center + Vector((1.5, -1.5, 0.2))
    look_at(camera, center)
    camera_data.lens = 40
    out = os.path.join(OUT_DIR, "Rebuild_{}_full.png".format(label))
    scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print("SHOT|{}".format(out))

    for side in ("r", "l"):
        hand = anim_arm.matrix_world @ anim_arm.pose.bones["hand_" + side].head
        lower = anim_arm.matrix_world @ anim_arm.pose.bones["lowerarm_" + side].head
        focus = (hand + lower) / 2.0
        axis = (hand - lower).normalized()
        side_dir = axis.cross(Vector((0.0, 0.0, 1.0)))
        if side_dir.length < 0.3:
            side_dir = axis.cross(Vector((0.0, 1.0, 0.0)))
        side_dir.normalize()
        camera.location = focus + side_dir * 0.45 + Vector((0.0, 0.0, 0.12))
        look_at(camera, focus)
        camera_data.lens = 50
        out = os.path.join(OUT_DIR, "Rebuild_{}_hand_{}.png".format(label, side))
        scene.render.filepath = out
        bpy.ops.render.render(write_still=True)
        print("SHOT|{}".format(out))

    modifier.object = body_arm
    for obj in imported:
        bpy.data.objects.remove(obj, do_unlink=True)

print("MTM_PREVIEW_DONE")
sys.stdout.flush()
