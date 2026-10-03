import os

import bpy
from mathutils import Vector

PROJECT = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy"
EXCHANGE = os.path.join(PROJECT, "Saved", "BlenderExchange")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(
    filepath=os.path.join(EXCHANGE, "Body_MH342.fbx"),
    ignore_leaf_bones=False,
    automatic_bone_orientation=False,
)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
mesh = next(o for o in bpy.data.objects if o.type == "MESH")

verts_world = [mesh.matrix_world @ v.co for v in mesh.data.vertices]

CHECK = [
    "hand_r", "index_01_r", "index_02_r", "index_03_r",
    "middle_01_r", "middle_03_r", "thumb_01_r", "thumb_03_r",
    "pinky_03_r", "lowerarm_r", "foot_r", "ball_r", "head", "pelvis",
    "upperarm_r", "spine_03", "calf_r",
]
for name in CHECK:
    bone = arm.data.bones.get(name)
    if bone is None:
        continue
    bone_world = arm.matrix_world @ bone.head_local
    nearest = min((v - bone_world).length for v in verts_world)
    print("BINDDIST|{}|bone={}|nearest_vertex={}".format(
        name, tuple(round(v, 4) for v in bone_world), round(nearest, 4)))
print("BIND_CHECK_DONE")
