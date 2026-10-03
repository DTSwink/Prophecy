import os

import bpy

PROJECT = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy"
EXCHANGE = os.path.join(PROJECT, "Saved", "BlenderExchange")

bpy.ops.wm.open_mainfile(filepath=os.path.join(EXCHANGE, "Body_UEFN78.blend"))
body = next(o for o in bpy.data.objects if o.type == "ARMATURE")
mesh = next(o for o in bpy.data.objects if o.type == "MESH")
print("BODY_MW|{}".format([tuple(round(v, 4) for v in row) for row in body.matrix_world]))
print("MESH_MW|{}".format([tuple(round(v, 4) for v in row) for row in mesh.matrix_world]))
print("MESH_PARENT|{}|MOD_TARGETS|{}".format(
    mesh.parent.name if mesh.parent else None,
    [(m.type, getattr(m, "object", None) and m.object.name) for m in mesh.modifiers]))

before = set(bpy.data.objects)
bpy.ops.import_scene.fbx(
    filepath=os.path.join(EXCHANGE, "Anim_Climb.fbx"),
    ignore_leaf_bones=False,
    automatic_bone_orientation=False,
)
imported = list(set(bpy.data.objects) - before)
anim_arm = next(o for o in imported if o.type == "ARMATURE")
print("ANIM_MW|{}".format([tuple(round(v, 4) for v in row) for row in anim_arm.matrix_world]))
ab = anim_arm.data.bones.get("pelvis")
print("ANIM_REST_PELVIS|{}".format(tuple(round(v, 4) for v in ab.head_local)))
bb = body.data.bones.get("pelvis")
print("BODY_REST_PELVIS|{}".format(tuple(round(v, 4) for v in bb.head_local)))

scene = bpy.context.scene
print("SCENE_FPS|{}|frame_range={}..{}".format(scene.render.fps, scene.frame_start, scene.frame_end))
for frame in (0, 30, 60):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    apb_head = anim_arm.pose.bones.get("head")
    apb_hand = anim_arm.pose.bones.get("hand_r")
    print("ANIM_EVAL|f{}|head_world={}|handR_world={}".format(
        frame,
        tuple(round(v, 4) for v in (anim_arm.matrix_world @ apb_head.head)),
        tuple(round(v, 4) for v in (anim_arm.matrix_world @ apb_hand.head))))
print("DEBUG_DONE")
