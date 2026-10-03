import bpy, sys
EXCHANGE = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\BlenderExchange"
bpy.ops.wm.open_mainfile(filepath=EXCHANGE + "/Body_UEFN_CopyW.blend")
mesh = next(o for o in bpy.data.objects if o.type == "MESH")
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
group_names = {g.index: g.name for g in mesh.vertex_groups}
hand_pos = arm.data.bones["hand_r"].head_local
both = lower_only = hand_only = 0
for v in mesh.data.vertices:
    if (v.co - hand_pos).length > 8.0:
        continue
    w = {group_names[g.group]: g.weight for g in v.groups if g.weight > 0.01}
    if "lowerarm_r" in w and "hand_r" in w:
        both += 1
    elif "lowerarm_r" in w:
        lower_only += 1
    elif "hand_r" in w:
        hand_only += 1
print("COPYW_WRIST|both={}|lower_only={}|hand_only={}".format(both, lower_only, hand_only))
sys.stdout.flush()
