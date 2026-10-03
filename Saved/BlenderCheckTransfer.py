import os
import sys

import bpy
from mathutils import Vector

EXCHANGE = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\BlenderExchange"

bpy.ops.wm.open_mainfile(filepath=os.path.join(EXCHANGE, "Body_UEFN78_transfer.blend"))
mesh = next(o for o in bpy.data.objects if o.type == "MESH")
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")

group_names = {g.index: g.name for g in mesh.vertex_groups}
print("GROUPS|{}".format(len(mesh.vertex_groups)))

# Sample vertices in known regions: foot (z<15), hand (x<-50), shoulder.
samples = {"foot": None, "hand": None, "shoulder": None}
for v in mesh.data.vertices:
    if samples["foot"] is None and v.co.z < 10:
        samples["foot"] = v
    if samples["hand"] is None and v.co.x < -55:
        samples["hand"] = v
    if samples["shoulder"] is None and abs(v.co.x - 15) < 2 and v.co.z > 138:
        samples["shoulder"] = v

for label, v in samples.items():
    if v is None:
        print("SAMPLE|{}|none".format(label))
        continue
    weights = {group_names[g.group]: round(g.weight, 3) for g in v.groups if g.weight > 0.01}
    print("SAMPLE|{}|v={}|co=({:.1f},{:.1f},{:.1f})|weights={}".format(
        label, v.index, v.co.x, v.co.y, v.co.z, weights))

# Total weight stats.
zero = sum(1 for v in mesh.data.vertices if sum(g.weight for g in v.groups) < 0.5)
print("LOW_WEIGHT_VERTS|{}".format(zero))
print("CHECK_DONE")
sys.stdout.flush()
