import math
import os

import bpy
from mathutils import Vector

PROJECT = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy"
EXCHANGE = os.path.join(PROJECT, "Saved", "BlenderExchange")
OUT_DIR = os.path.join(PROJECT, "Saved", "BlenderShots")

bpy.ops.wm.open_mainfile(filepath=os.path.join(EXCHANGE, "Body_UEFN78.blend"))
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.render.resolution_x = 1200
scene.render.resolution_y = 1200
scene.render.fps = 30

body_arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
mesh_obj = next(o for o in bpy.data.objects if o.type == "MESH")
body_matrix = body_arm.matrix_world.copy()

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


def bbox_world(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    coords = [eval_obj.matrix_world @ Vector(c) for c in eval_obj.bound_box]
    lo = Vector((min(c.x for c in coords), min(c.y for c in coords), min(c.z for c in coords)))
    hi = Vector((max(c.x for c in coords), max(c.y for c in coords), max(c.z for c in coords)))
    return lo, hi


def look_at(cam_obj, target):
    direction = target - cam_obj.location
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def shot(name, center, distance):
    camera.location = center + Vector((distance, -distance, distance * 0.3))
    look_at(camera, center)
    camera_data.lens = 35
    scene.render.filepath = os.path.join(OUT_DIR, name)
    bpy.ops.render.render(write_still=True)
    print("SHOT|{}".format(name))


# Rest pose first.
scene.frame_set(1)
bpy.context.view_layer.update()
lo, hi = bbox_world(mesh_obj)
print("REST_BBOX|lo={}|hi={}".format(tuple(round(v, 2) for v in lo), tuple(round(v, 2) for v in hi)))
shot("Debug_Rest.png", (lo + hi) / 2.0, 2.5)

# Climb at 2.0s via carrier armature.
before = set(bpy.data.objects)
bpy.ops.import_scene.fbx(
    filepath=os.path.join(EXCHANGE, "Anim_Climb.fbx"),
    ignore_leaf_bones=False,
    automatic_bone_orientation=False,
)
imported = [o for o in set(bpy.data.objects) - before]
anim_arm = next(o for o in imported if o.type == "ARMATURE")
anim_arm.matrix_world = body_matrix
modifier = next(m for m in mesh_obj.modifiers if m.type == "ARMATURE")
modifier.object = anim_arm
anim_arm.hide_render = True

scene.frame_set(60)
bpy.context.view_layer.update()
lo, hi = bbox_world(mesh_obj)
print("CLIMB_BBOX|lo={}|hi={}".format(tuple(round(v, 2) for v in lo), tuple(round(v, 2) for v in hi)))
print("ANIM_ARM_MW_F60|{}".format([tuple(round(v, 3) for v in row) for row in anim_arm.matrix_world]))
center = (lo + hi) / 2.0
size = max((hi - lo).length, 1.0)
shot("Debug_Climb2s_wide.png", center, size)
shot("Debug_Climb2s_mid.png", center, size * 0.6)
print("DEBUG_RENDER_DONE")
