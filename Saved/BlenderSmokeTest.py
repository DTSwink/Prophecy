import bpy
import sys

FBX = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\BlenderExchange\Body_MH342.fbx"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=FBX, ignore_leaf_bones=True, automatic_bone_orientation=False)

for obj in bpy.data.objects:
    print("OBJ|{}|{}".format(obj.type, obj.name))
    if obj.type == "ARMATURE":
        print("ARMATURE_BONES|{}".format(len(obj.data.bones)))
        roots = [b.name for b in obj.data.bones if b.parent is None]
        print("ROOT_BONES|{}".format(roots))
        print("OBJ_SCALE|{}|{}".format(obj.name, tuple(obj.scale)))
    if obj.type == "MESH":
        print("MESH|{}|verts={}|groups={}".format(obj.name, len(obj.data.vertices), len(obj.vertex_groups)))

print("SMOKE_DONE")
sys.stdout.flush()
