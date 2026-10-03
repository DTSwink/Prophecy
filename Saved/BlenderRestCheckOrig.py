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


def rest_centroid(obj, group_name, threshold=0.4):
    vg = obj.vertex_groups.get(group_name)
    if vg is None:
        return None, 0
    gi = vg.index
    total = Vector((0.0, 0.0, 0.0))
    weight_sum = 0.0
    count = 0
    for v in obj.data.vertices:
        for g in v.groups:
            if g.group == gi and g.weight > threshold:
                total += (obj.matrix_world @ v.co) * g.weight
                weight_sum += g.weight
                count += 1
                break
    if weight_sum == 0:
        return None, 0
    return total / weight_sum, count


for name in ("index_03_r", "index_03_half_r", "index_03_bulge_r", "index_02_dip_r",
             "middle_03_r", "hand_r", "wrist_inner_r", "wrist_outer_r", "foot_r"):
    bone = arm.data.bones.get(name)
    bone_world = arm.matrix_world @ bone.head_local if bone else None
    c, n = rest_centroid(mesh, name)
    delta = None
    if c is not None and bone_world is not None:
        delta = round((c - bone_world).length, 4)
    print("ORIG_REST|{}|bone={}|centroid={}|n={}|dist={}".format(
        name,
        tuple(round(v, 4) for v in bone_world) if bone_world else None,
        tuple(round(v, 4) for v in c) if c else None,
        n, delta))
print("ORIG_CHECK_DONE")
