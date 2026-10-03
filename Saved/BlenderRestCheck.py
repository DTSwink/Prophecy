import os

import bpy
from mathutils import Vector

PROJECT = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy"
EXCHANGE = os.path.join(PROJECT, "Saved", "BlenderExchange")

bpy.ops.wm.open_mainfile(filepath=os.path.join(EXCHANGE, "Body_UEFN78.blend"))
body_arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
mesh_obj = next(o for o in bpy.data.objects if o.type == "MESH")


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


for name in ("index_03_r", "middle_03_r", "index_01_r", "hand_r", "foot_r", "head"):
    bone = body_arm.data.bones.get(name)
    bone_world = body_arm.matrix_world @ bone.head_local if bone else None
    c, n = rest_centroid(mesh_obj, name)
    print("BODY_REST|{}|bone={}|centroid={}|n={}".format(
        name,
        tuple(round(v, 4) for v in bone_world) if bone_world else None,
        tuple(round(v, 4) for v in c) if c else None,
        n))

before = set(bpy.data.objects)
bpy.ops.import_scene.fbx(
    filepath=os.path.join(EXCHANGE, "UEFN_Mannequin.fbx"),
    ignore_leaf_bones=False,
    automatic_bone_orientation=False,
)
mann_objs = [o for o in set(bpy.data.objects) - before]
mann_arm = next(o for o in mann_objs if o.type == "ARMATURE")
for m in (o for o in mann_objs if o.type == "MESH"):
    for name in ("index_03_r", "hand_r"):
        bone = mann_arm.data.bones.get(name)
        bone_world = mann_arm.matrix_world @ bone.head_local if bone else None
        c, n = rest_centroid(m, name)
        if n:
            print("MANN_REST|{}|{}|bone={}|centroid={}|n={}".format(
                m.name, name,
                tuple(round(v, 4) for v in bone_world) if bone_world else None,
                tuple(round(v, 4) for v in c) if c else None,
                n))
print("REST_CHECK_DONE")
