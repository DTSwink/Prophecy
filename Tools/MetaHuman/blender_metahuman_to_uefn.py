"""Convert original MetaHuman body to UEFN skeleton using MetahumanToManny
cleanup operators + UEFN bone pruning.

This follows the established MetahumanToManny workflow instead of reinventing
weight folding. The addon handles twist naming, toe chains, finger bulges, and
seam welding. We then prune to the exact UEFN bone set from
skeleton_snapshots.json and export with standard UE FBX settings.

Run:
  blender --background --python Tools/MetaHuman/blender_metahuman_to_uefn.py
"""

import importlib
import json
import os
import sys

import bpy

PROJECT = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy"
SNAPSHOT = os.path.join(PROJECT, "Tools", "MetaHuman", "skeleton_snapshots.json")
EXCHANGE = os.path.join(PROJECT, "Saved", "BlenderExchange")
BODY_FBX = os.path.join(EXCHANGE, "Body_Original_MH.fbx")
OUT_BLEND = os.path.join(EXCHANGE, "Body_UEFN_MTM.blend")
OUT_FBX = os.path.join(EXCHANGE, "Body_UEFN_MTM.fbx")

sys.path.insert(0, os.path.join(PROJECT, "Tools", "MetaHuman"))
from blender_ue_export import export_skeletal_fbx, ensure_cm_scene


def enable_mtm():
    """Load MetahumanToManny operators in headless mode."""
    addons_root = os.path.join(
        os.environ.get("APPDATA", ""),
        "Blender Foundation", "Blender", "5.1", "scripts", "addons",
    )
    if addons_root not in sys.path:
        sys.path.insert(0, addons_root)
    import MetahumanToManny as mtm
    importlib.reload(mtm)
    mtm.register()
    print("MTM_LOADED")


def import_fbx(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(
        filepath=path,
        ignore_leaf_bones=False,
        automatic_bone_orientation=False,
        use_custom_normals=True,
    )
    new_objects = [o for o in set(bpy.data.objects) - before]
    arm = next(o for o in new_objects if o.type == "ARMATURE")
    mesh = max((o for o in new_objects if o.type == "MESH"), key=lambda m: len(m.data.vertices))
    return arm, mesh


def fold_and_prune(mesh, arm, uefn_names, parent_map):
    """Fold non-UEFN vertex groups into nearest UEFN ancestor, then delete bones."""
    fold = {}
    for bone in arm.data.bones:
        name = bone.name
        if name in uefn_names:
            continue
        ancestor = parent_map.get(name)
        while ancestor and ancestor not in uefn_names:
            ancestor = parent_map.get(ancestor)
        if ancestor:
            fold[name] = ancestor

    folded = 0
    for src_name, dst_name in sorted(fold.items()):
        src = mesh.vertex_groups.get(src_name)
        if src is None:
            continue
        dst = mesh.vertex_groups.get(dst_name)
        if dst is None:
            dst = mesh.vertex_groups.new(name=dst_name)
        gi = src.index
        for v in mesh.data.vertices:
            for g in v.groups:
                if g.group == gi and g.weight > 0.0:
                    dst.add([v.index], g.weight, "ADD")
                    break
        mesh.vertex_groups.remove(src)
        folded += 1
    print("FOLDED|{}".format(folded))

    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    removed = 0
    for bone in list(arm.data.edit_bones):
        if bone.name not in uefn_names:
            arm.data.edit_bones.remove(bone)
            removed += 1
    bpy.ops.object.mode_set(mode="OBJECT")
    return removed


def main():
    with open(SNAPSHOT, "r", encoding="utf-8") as handle:
        snapshot = json.load(handle)
    uefn_names = {b["name"] for b in snapshot["uefn_reference"]["bones"]}
    print("UEFN_BONES|{}".format(len(uefn_names)))

    enable_mtm()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ensure_cm_scene()
    arm, mesh = import_fbx(BODY_FBX)
    print("IMPORTED|bones={}|verts={}|groups={}".format(
        len(arm.data.bones), len(mesh.data.vertices), len(mesh.vertex_groups)))

    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.in_place_conversion()
    print("MTM_CONVERSION|bones={}|groups={}".format(
        len(arm.data.bones), len(mesh.vertex_groups)))

    parent_map = {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones}
    removed = fold_and_prune(mesh, arm, uefn_names, parent_map)
    print("UEFN_PRUNE|removed={}|remaining={}".format(removed, len(arm.data.bones)))

    leftover_groups = [g.name for g in mesh.vertex_groups if g.name not in uefn_names]
    if leftover_groups:
        print("WARN|leftover_groups={}".format(len(leftover_groups)))
        for name in leftover_groups:
            mesh.vertex_groups.remove(mesh.vertex_groups[name])

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    export_skeletal_fbx(OUT_FBX, arm, [mesh])
    print("EXPORTED|{}|bytes={}".format(OUT_FBX, os.path.getsize(OUT_FBX)))
    print("MTM_UEFN_DONE")
    sys.stdout.flush()


main()
