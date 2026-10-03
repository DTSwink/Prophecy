"""Render the ORIGINAL MH342 mesh driven by UEFN animation via per-bone
copy-transform constraints on shared bones (helpers ride along rigidly).
This is the theoretical best case for any shared-bone-only reduction.
"""

import math
import os

import bpy
from mathutils import Vector

PROJECT = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy"
EXCHANGE = os.path.join(PROJECT, "Saved", "BlenderExchange")
OUT_DIR = os.path.join(PROJECT, "Saved", "BlenderShots")

SHOTS = [
    ("Anim_CliffCatch.fbx", "CliffCatch", (0.6,)),
    ("Anim_Climb.fbx", "Climb", (2.0,)),
]
FPS = 30


def look_at(camera, target):
    direction = target - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(
    filepath=os.path.join(EXCHANGE, "Body_MH342.fbx"),
    ignore_leaf_bones=False,
    automatic_bone_orientation=False,
    use_custom_normals=True,
)
body_arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
mesh_obj = next(o for o in bpy.data.objects if o.type == "MESH")

scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "SINGLE"
scene.display.shading.single_color = (0.75, 0.75, 0.78)
scene.render.resolution_x = 1400
scene.render.resolution_y = 1400
scene.render.fps = FPS

camera_data = bpy.data.cameras.new("Cam")
camera_data.clip_start = 0.01
camera_data.clip_end = 1000.0
camera = bpy.data.objects.new("Cam", camera_data)
scene.collection.objects.link(camera)
scene.camera = camera
light_data = bpy.data.lights.new("Sun", type="SUN")
light_data.energy = 3.0
light = bpy.data.objects.new("Sun", light_data)
light.rotation_euler = (math.radians(50), math.radians(10), math.radians(30))
scene.collection.objects.link(light)

for anim_file, label, times in SHOTS:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(
        filepath=os.path.join(EXCHANGE, anim_file),
        ignore_leaf_bones=False,
        automatic_bone_orientation=False,
    )
    imported = [o for o in set(bpy.data.objects) - before]
    anim_arm = next(o for o in imported if o.type == "ARMATURE")
    anim_bones = {b.name for b in anim_arm.data.bones}
    for obj in imported:
        obj.hide_render = True

    # Constrain every shared pose bone to the carrier.
    constraints = []
    for pose_bone in body_arm.pose.bones:
        if pose_bone.name in anim_bones:
            con = pose_bone.constraints.new("COPY_TRANSFORMS")
            con.target = anim_arm
            con.subtarget = pose_bone.name
            constraints.append((pose_bone, con))
    print("CONSTRAINED|{}|{}".format(label, len(constraints)))

    # Follow the carrier's object-level root motion too.
    body_matrix = body_arm.matrix_world.copy()
    mesh_relative = body_matrix.inverted() @ mesh_obj.matrix_world.copy()

    for sample_time in times:
        frame = int(round(sample_time * FPS))
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        body_arm.matrix_world = anim_arm.matrix_world
        mesh_obj.matrix_world = anim_arm.matrix_world @ mesh_relative
        bpy.context.view_layer.update()

        tag = "{}_{:.1f}s".format(label, sample_time).replace(".", "p")
        depsgraph = bpy.context.evaluated_depsgraph_get()

        head = body_arm.matrix_world @ body_arm.pose.bones["head"].head
        pelvis = body_arm.matrix_world @ body_arm.pose.bones["pelvis"].head
        center = (head + pelvis) / 2.0
        camera.location = center + Vector((1.7, -1.7, 0.2))
        look_at(camera, center)
        camera_data.lens = 40
        scene.render.filepath = os.path.join(OUT_DIR, "Truth342_{}_full.png".format(tag))
        bpy.ops.render.render(write_still=True)
        print("SHOT|Truth342_{}_full".format(tag))

        for side in ("r", "l"):
            hand = body_arm.matrix_world @ body_arm.pose.bones["hand_" + side].head
            middle = body_arm.matrix_world @ body_arm.pose.bones["middle_01_" + side].head
            lower = body_arm.matrix_world @ body_arm.pose.bones["lowerarm_" + side].head
            focus = (hand + middle) / 2.0
            arm_axis = (hand - lower).normalized()
            side_dir = arm_axis.cross(Vector((0.0, 0.0, 1.0)))
            if side_dir.length < 0.3:
                side_dir = arm_axis.cross(Vector((0.0, 1.0, 0.0)))
            side_dir.normalize()
            camera.location = focus + side_dir * 0.45 + Vector((0.0, 0.0, 0.12))
            look_at(camera, focus)
            camera_data.lens = 50
            scene.render.filepath = os.path.join(OUT_DIR, "Truth342_{}_hand{}_A.png".format(tag, side.upper()))
            bpy.ops.render.render(write_still=True)
            print("SHOT|Truth342_{}_hand{}_A".format(tag, side.upper()))

    for pose_bone, con in constraints:
        pose_bone.constraints.remove(con)
    body_arm.matrix_world = body_matrix
    for obj in imported:
        bpy.data.objects.remove(obj, do_unlink=True)

print("TRUTH_DONE")
