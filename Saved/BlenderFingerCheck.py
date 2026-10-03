import os

import bpy
from mathutils import Vector

PROJECT = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy"
EXCHANGE = os.path.join(PROJECT, "Saved", "BlenderExchange")

bpy.ops.wm.open_mainfile(filepath=os.path.join(EXCHANGE, "Body_UEFN78.blend"))
body_arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
mesh_obj = next(o for o in bpy.data.objects if o.type == "MESH")
body_matrix = body_arm.matrix_world.copy()
mesh_relative = body_matrix.inverted() @ mesh_obj.matrix_world.copy()

before = set(bpy.data.objects)
bpy.ops.import_scene.fbx(
    filepath=os.path.join(EXCHANGE, "UEFN_Mannequin.fbx"),
    ignore_leaf_bones=False,
    automatic_bone_orientation=False,
)
mann_objs = [o for o in set(bpy.data.objects) - before]
mann_meshes = [o for o in mann_objs if o.type == "MESH"]

before = set(bpy.data.objects)
bpy.ops.import_scene.fbx(
    filepath=os.path.join(EXCHANGE, "Anim_CliffCatch.fbx"),
    ignore_leaf_bones=False,
    automatic_bone_orientation=False,
)
anim_arm = next(o for o in (set(bpy.data.objects) - before) if o.type == "ARMATURE")

mod = next(m for m in mesh_obj.modifiers if m.type == "ARMATURE")
mod.object = anim_arm
mann_rel = {}
for m in mann_meshes:
    mm = next(x for x in m.modifiers if x.type == "ARMATURE")
    mm.object = anim_arm
    mann_rel[m.name] = body_matrix.inverted() @ m.matrix_world.copy()

bpy.context.scene.frame_set(18)
bpy.context.view_layer.update()
mesh_obj.matrix_world = anim_arm.matrix_world @ mesh_relative
for m in mann_meshes:
    m.matrix_world = anim_arm.matrix_world @ mann_rel[m.name]
bpy.context.view_layer.update()

pb = anim_arm.pose.bones
for name in ("hand_r", "index_01_r", "index_03_r", "middle_03_r"):
    world = anim_arm.matrix_world @ pb[name].head
    print("CARRIER|{}|{}".format(name, tuple(round(v, 3) for v in world)))

depsgraph = bpy.context.evaluated_depsgraph_get()


def group_centroid(obj, group_name):
    vg = obj.vertex_groups.get(group_name)
    if vg is None:
        return None, 0
    gi = vg.index
    eval_obj = obj.evaluated_get(depsgraph)
    eval_mesh = eval_obj.to_mesh()
    total = Vector((0.0, 0.0, 0.0))
    weight_sum = 0.0
    count = 0
    for v_orig, v_eval in zip(obj.data.vertices, eval_mesh.vertices):
        for g in v_orig.groups:
            if g.group == gi and g.weight > 0.4:
                total += (eval_obj.matrix_world @ v_eval.co) * g.weight
                weight_sum += g.weight
                count += 1
                break
    eval_obj.to_mesh_clear()
    if weight_sum == 0:
        return None, 0
    return total / weight_sum, count


for gname in ("index_03_r", "middle_03_r", "hand_r"):
    c, n = group_centroid(mesh_obj, gname)
    print("REDUCED|{}|centroid={}|n={}".format(
        gname, tuple(round(v, 3) for v in c) if c else None, n))
    for m in mann_meshes:
        c2, n2 = group_centroid(m, gname)
        if c2 is not None:
            print("MANNEQUIN|{}|{}|centroid={}|n={}".format(
                m.name, gname, tuple(round(v, 3) for v in c2), n2))
print("FINGER_CHECK_DONE")
