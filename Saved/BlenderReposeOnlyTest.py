"""Test: repose-only mesh (no fold) driven by UEFN climb anim."""

import math
import os
import sys

import bpy
from mathutils import Vector

EXCHANGE = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\BlenderExchange"
OUT = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\BlenderShots\ReposeOnly_Climb.png"
FPS = 30

# Build repose-only: import original, pose to UEFN, apply rest, don't fold.
bpy.ops.wm.read_factory_settings(use_empty=True)
before = set(bpy.data.objects)
for path in (os.path.join(EXCHANGE, "Body_Original_MH.fbx"), os.path.join(EXCHANGE, "UEFN_Mannequin.fbx")):
    bpy.ops.import_scene.fbx(filepath=path, ignore_leaf_bones=False, automatic_bone_orientation=False)
new = [o for o in set(bpy.data.objects) - before]
arm = next(o for o in new if o.type == "ARMATURE" and "Mannequin" not in o.name)
mesh = next(o for o in new if o.type == "MESH" and "Mannequin" not in o.name)
donor = next(o for o in bpy.data.objects if o.type == "ARMATURE" and "Mannequin" in o.name)
donor_rest = {b.name: b.matrix_local.copy() for b in donor.data.bones}

bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="POSE")
ordered = sorted(arm.pose.bones, key=lambda p: sum(1 for _ in p.parent_recursive))
for pb in ordered:
    t = donor_rest.get(pb.name)
    if t is not None:
        pb.matrix = t
        bpy.context.view_layer.update()
bpy.ops.object.mode_set(mode="OBJECT")

bpy.context.view_layer.objects.active = mesh
mod = mesh.modifiers.new("Bake", "ARMATURE")
mod.object = arm
bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="POSE")
bpy.ops.pose.armature_apply(selected=False)
bpy.ops.object.mode_set(mode="OBJECT")

body_matrix = arm.matrix_world.copy()
mesh_rel = body_matrix.inverted() @ mesh.matrix_world.copy()

# Animate
before = set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=os.path.join(EXCHANGE, "Anim_Climb.fbx"), ignore_leaf_bones=False, automatic_bone_orientation=False)
anim_arm = next(o for o in set(bpy.data.objects) - before if o.type == "ARMATURE")
anim_arm.matrix_world = body_matrix
next(m for m in mesh.modifiers if m.type == "ARMATURE").object = anim_arm

scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "SINGLE"
scene.display.shading.single_color = (0.75, 0.75, 0.78)
scene.render.resolution_x = 1200
scene.render.resolution_y = 1200
cam_data = bpy.data.cameras.new("C")
cam = bpy.data.objects.new("C", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
cam_data.clip_start = 0.01
cam_data.clip_end = 1000.0

scene.frame_set(int(2.0 * FPS))
bpy.context.view_layer.update()
mesh.matrix_world = anim_arm.matrix_world @ mesh_rel
head = anim_arm.matrix_world @ anim_arm.pose.bones["head"].head
pelvis = anim_arm.matrix_world @ anim_arm.pose.bones["pelvis"].head
center = (head + pelvis) / 2
cam.location = center + Vector((1.5, -1.5, 0.2))
direction = center - cam.location
cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
scene.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("SHOT|{}".format(OUT))
print("REPOSE_ONLY_DONE")
sys.stdout.flush()
