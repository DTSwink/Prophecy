# Blender: inspect the user's speech-poses FBX (frames, bones, which frames are keyed, per-frame pose difference)
import bpy, sys, json, math
p = sys.argv[sys.argv.index('--') + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
before = set(bpy.data.objects)
if hasattr(bpy.ops.wm, 'fbx_import'): bpy.ops.wm.fbx_import(filepath=p)
else: bpy.ops.import_scene.fbx(filepath=p)
objs = [o for o in bpy.data.objects if o not in before]
print('OBJECTS', [(o.name, o.type) for o in objs])
arm = [o for o in objs if o.type == 'ARMATURE'][0]
print('BONES', len(arm.data.bones), [b.name for b in arm.data.bones][:12])
act = arm.animation_data.action if arm.animation_data else None
print('ACTION', act.name if act else None, tuple(act.frame_range) if act else None, 'fps', bpy.context.scene.render.fps)
keys = set()
if act:
    fcs = act.fcurves if hasattr(act, 'fcurves') and act.fcurves else [fc for l in act.layers for s in l.strips for cb in s.channelbags for fc in cb.fcurves]
    for fc in fcs:
        for k in fc.keyframe_points: keys.add(round(k.co[0], 2))
print('KEYED FRAMES', sorted(keys)[:60], 'count', len(keys))
f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
sc = bpy.context.scene
def pose():
    return {b.name: b.matrix_basis.to_quaternion().copy() for b in arm.pose.bones}
sc.frame_set(f0); ref = pose()
for f in range(f0, f1 + 1):
    sc.frame_set(f); cur = pose()
    diffs = sorted(((math.degrees(ref[n].rotation_difference(cur[n]).angle), n) for n in cur), reverse=True)[:4]
    print('FRAME', f, [(n, round(d, 1)) for d, n in diffs])
