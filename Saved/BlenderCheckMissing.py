import json

import bpy

SNAPSHOT = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy\Tools\MetaHuman\skeleton_snapshots.json"
BODY_FBX = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\BlenderExchange\Body_MH342.fbx"

with open(SNAPSHOT, "r", encoding="utf-8") as handle:
    data = json.load(handle)
uefn = {b["name"] for b in data["uefn_reference"]["bones"]}
mh = {b["name"] for b in data["fitted_metahuman_body_reference"]["bones"]}
shared = uefn & mh

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=BODY_FBX, ignore_leaf_bones=False, automatic_bone_orientation=False)
armature = next(o for o in bpy.data.objects if o.type == "ARMATURE")
imported = {b.name for b in armature.data.bones}
print("IMPORT_NO_IGNORE|bones={}".format(len(imported)))
print("MISSING_SHARED|{}".format(sorted(shared - imported)))
print("MISSING_MH_ONLY|{}".format(sorted((mh - uefn) - imported)))
print("ARMATURE_OBJ|{}".format(armature.name))
mesh_obj = next(o for o in bpy.data.objects if o.type == "MESH")
groups = {g.name for g in mesh_obj.vertex_groups}
print("GROUPS_MISSING_BONE|{}".format(sorted(groups - imported)))
print("CHECK_DONE")
