"""Find spike vertices in the climb pose: vertices that move very differently
from their edge-connected neighbors, then dump their vertex-group weights."""

import os
import sys
from collections import defaultdict

import bpy
from mathutils import Vector

EXCHANGE = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\BlenderExchange"
FPS = 30

bpy.ops.wm.open_mainfile(filepath=os.path.join(EXCHANGE, "Body_UEFN78.blend"))
body_arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
mesh_obj = next(o for o in bpy.data.objects if o.type == "MESH")

before = set(bpy.data.objects)
bpy.ops.import_scene.fbx(
    filepath=os.path.join(EXCHANGE, "Anim_Climb.fbx"),
    ignore_leaf_bones=False,
    automatic_bone_orientation=False,
)
imported = [o for o in set(bpy.data.objects) - before]
anim_arm = next(o for o in imported if o.type == "ARMATURE")
anim_arm.matrix_world = body_arm.matrix_world.copy()

modifier = next(m for m in mesh_obj.modifiers if m.type == "ARMATURE")
modifier.object = anim_arm

scene = bpy.context.scene
scene.frame_set(int(round(2.0 * FPS)))
bpy.context.view_layer.update()

depsgraph = bpy.context.evaluated_depsgraph_get()
eval_mesh = mesh_obj.evaluated_get(depsgraph).to_mesh()

# Rest positions from the original mesh data.
rest = [v.co.copy() for v in mesh_obj.data.vertices]
posed = [v.co.copy() for v in eval_mesh.vertices]

neighbors = defaultdict(set)
for e in mesh_obj.data.edges:
    a, b = e.vertices
    neighbors[a].add(b)
    neighbors[b].add(a)

# Spike score: how far a vertex's displacement deviates from the average
# displacement of its neighbors.
scores = []
for i in range(len(rest)):
    disp = posed[i] - rest[i]
    if not neighbors[i]:
        continue
    avg = Vector((0.0, 0.0, 0.0))
    for j in neighbors[i]:
        avg += posed[j] - rest[j]
    avg /= len(neighbors[i])
    scores.append(((disp - avg).length, i))

scores.sort(reverse=True)
group_names = {g.index: g.name for g in mesh_obj.vertex_groups}
print("TOP_SPIKES")
for score, i in scores[:25]:
    v = mesh_obj.data.vertices[i]
    weights = {group_names[g.group]: round(g.weight, 3) for g in v.groups if g.weight > 0.005}
    print("SPIKE|v={}|score={:.2f}|rest=({:.1f},{:.1f},{:.1f})|weights={}".format(
        i, score, rest[i].x, rest[i].y, rest[i].z, weights))
print("SPIKE_DIAG_DONE")
sys.stdout.flush()
