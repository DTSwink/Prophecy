"""Check wrist vertices for lowerarm+hand co-influence after rebuild."""

import os
import sys

import bpy

EXCHANGE = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\BlenderExchange"

bpy.ops.wm.open_mainfile(filepath=os.path.join(EXCHANGE, "Body_UEFN78.blend"))
mesh = next(o for o in bpy.data.objects if o.type == "MESH")
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")

group_names = {g.index: g.name for g in mesh.vertex_groups}
print("BONES|{}|GROUPS|{}".format(len(arm.data.bones), len(mesh.vertex_groups)))
print("BONE_LIST|{}".format(sorted(b.name for b in arm.data.bones)))

# Wrist region: near hand_r bone head in rest pose.
hand_bone = arm.data.bones["hand_r"]
hand_pos = hand_bone.head_local
print("HAND_R|{}".format(tuple(round(v, 2) for v in hand_pos)))

both = 0
lower_only = 0
hand_only = 0
neither = 0
samples = []
for v in mesh.data.vertices:
    d = (v.co - hand_pos).length
    if d > 8.0:
        continue
    weights = {group_names[g.group]: g.weight for g in v.groups if g.weight > 0.01}
    has_lower = "lowerarm_r" in weights
    has_hand = "hand_r" in weights
    if has_lower and has_hand:
        both += 1
        if len(samples) < 3:
            samples.append((v.index, round(d, 2), weights))
    elif has_lower:
        lower_only += 1
    elif has_hand:
        hand_only += 1
    else:
        neither += 1

print("WRIST_ZONE|both={}|lower_only={}|hand_only={}|neither={}".format(
    both, lower_only, hand_only, neither))
for s in samples:
    print("  SAMPLE|v={}|dist={}|w={}".format(s[0], s[1], s[2]))
print("WRIST_CHECK_DONE")
sys.stdout.flush()
