import os

import bpy

PROJECT = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy"
EXCHANGE = os.path.join(PROJECT, "Saved", "BlenderExchange")

bpy.ops.wm.open_mainfile(filepath=os.path.join(EXCHANGE, "Body_UEFN78.blend"))
body = next(o for o in bpy.data.objects if o.type == "ARMATURE")

before = set(bpy.data.objects)
bpy.ops.import_scene.fbx(
    filepath=os.path.join(EXCHANGE, "Anim_Climb.fbx"),
    ignore_leaf_bones=False,
    automatic_bone_orientation=False,
)
anim_arm = next(o for o in (set(bpy.data.objects) - before) if o.type == "ARMATURE")

body_bones = {b.name: b for b in body.data.bones}
anim_bones = {b.name: b for b in anim_arm.data.bones}
shared = sorted(set(body_bones) & set(anim_bones))
print("SHARED|{} of body={} anim={}".format(len(shared), len(body_bones), len(anim_bones)))

worst = []
for name in shared:
    mb = body_bones[name].matrix_local
    ma = anim_bones[name].matrix_local
    dt = (mb.translation - ma.translation).length
    qb = mb.to_quaternion()
    qa = ma.to_quaternion()
    dq = qb.rotation_difference(qa).angle
    worst.append((max(dt, dq), name, round(dt, 5), round(dq * 57.2958, 3)))
worst.sort(reverse=True)
for _, name, dt, ddeg in worst[:15]:
    print("DIFF|{}|dtrans={}|drot_deg={}".format(name, dt, ddeg))
print("COMPARE_DONE")
