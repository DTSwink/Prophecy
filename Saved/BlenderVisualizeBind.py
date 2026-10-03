import math
import os

import bpy
from mathutils import Vector

PROJECT = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy"
EXCHANGE = os.path.join(PROJECT, "Saved", "BlenderExchange")
OUT_DIR = os.path.join(PROJECT, "Saved", "BlenderShots")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(
    filepath=os.path.join(EXCHANGE, "Body_MH342.fbx"),
    ignore_leaf_bones=False,
    automatic_bone_orientation=False,
)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
mesh = next(o for o in bpy.data.objects if o.type == "MESH")

scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "OBJECT"
scene.render.resolution_x = 1600
scene.render.resolution_y = 1600
mesh.color = (0.7, 0.7, 0.75, 1.0)

# Red marker spheres on every hand-related bone head.
marker_mat = None
for bone in arm.data.bones:
    n = bone.name
    if not n.endswith("_r"):
        continue
    if not any(k in n for k in ("hand", "index", "middle", "ring", "pinky", "thumb", "wrist", "metacarpal", "lowerarm")):
        continue
    world = arm.matrix_world @ bone.head_local
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.004, location=world, segments=12, ring_count=8)
    marker = bpy.context.active_object
    marker.color = (1.0, 0.1, 0.1, 1.0)

camera_data = bpy.data.cameras.new("Cam")
camera_data.clip_start = 0.001
camera_data.clip_end = 1000.0
camera = bpy.data.objects.new("Cam", camera_data)
scene.collection.objects.link(camera)
scene.camera = camera
light_data = bpy.data.lights.new("Sun", type="SUN")
light_data.energy = 3.0
light = bpy.data.objects.new("Sun", light_data)
light.rotation_euler = (math.radians(50), math.radians(10), math.radians(30))
scene.collection.objects.link(light)

hand = arm.matrix_world @ arm.data.bones["hand_r"].head_local
for tag, offset in (("front", Vector((0.0, -0.5, 0.0))), ("side", Vector((-0.5, 0.0, 0.0))), ("top", Vector((0.0, 0.0, 0.5)))):
    camera.location = hand + offset
    direction = hand - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    camera_data.lens = 50
    scene.render.filepath = os.path.join(OUT_DIR, "BindCheck_handR_{}.png".format(tag))
    bpy.ops.render.render(write_still=True)
    print("SHOT|BindCheck_handR_{}".format(tag))
print("VIS_DONE")
