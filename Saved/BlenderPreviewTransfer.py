"""Quick A/B render: folded weights vs mannequin-transferred weights on the
climb and cliff-catch poses."""

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
    ("Anim_Sprint.fbx", "Sprint", 0.28),
]


def look_at(camera, target):
    direction = target - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def render_variant(blend_name, variant):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(EXCHANGE, blend_name))
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "SINGLE"
    scene.display.shading.single_color = (0.75, 0.75, 0.78)
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 1200
    scene.render.fps = FPS

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
    light_data = bpy.data.lights.new("Key", type="SUN")
    light_data.energy = 3.0
    light = bpy.data.objects.new("Key", light_data)
    light.rotation_euler = (math.radians(50), math.radians(10), math.radians(30))
    scene.collection.objects.link(light)

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
        scene.render.filepath = os.path.join(
            OUT_DIR, "AB_{}_{}_full.png".format(variant, label))
        bpy.ops.render.render(write_still=True)
        print("SHOT|{}".format(scene.render.filepath))

        # Shoulder closeup (where the fins were).
        shoulder = anim_arm.matrix_world @ anim_arm.pose.bones["upperarm_l"].head
        camera.location = shoulder + Vector((0.5, -0.5, 0.15))
        look_at(camera, shoulder)
        camera_data.lens = 50
        scene.render.filepath = os.path.join(
            OUT_DIR, "AB_{}_{}_shoulderL.png".format(variant, label))
        bpy.ops.render.render(write_still=True)
        print("SHOT|{}".format(scene.render.filepath))

        modifier.object = body_arm
        for obj in imported:
            bpy.data.objects.remove(obj, do_unlink=True)


render_variant("Body_UEFN78.blend", "Fold")
render_variant("Body_UEFN78_transfer.blend", "Transfer")
print("AB_DONE")
sys.stdout.flush()
