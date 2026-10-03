import bpy
import sys

FBX = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\BlenderExchange\Body_UEFN78.fbx"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=FBX, ignore_leaf_bones=False, automatic_bone_orientation=False)

for obj in bpy.data.objects:
    print("OBJ|{}|{}|scale={}".format(obj.type, obj.name, tuple(round(s, 4) for s in obj.scale)))
    if obj.type == "ARMATURE":
        for name in ("pelvis", "head", "hand_r"):
            b = obj.data.bones.get(name)
            if b:
                w = obj.matrix_world @ b.head_local
                print("BONE|{}|world=({:.3f},{:.3f},{:.3f})".format(name, w.x, w.y, w.z))
    if obj.type == "MESH":
        import mathutils
        zs = [(obj.matrix_world @ v.co).z for v in obj.data.vertices]
        xs = [(obj.matrix_world @ v.co).x for v in obj.data.vertices]
        print("MESH|{}|verts={}|z=[{:.3f},{:.3f}]|x=[{:.3f},{:.3f}]".format(
            obj.name, len(obj.data.vertices), min(zs), max(zs), min(xs), max(xs)))
print("VERIFY_DONE")
sys.stdout.flush()
