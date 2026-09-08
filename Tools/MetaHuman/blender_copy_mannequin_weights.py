"""Copy UEFN mannequin weights onto repose-aligned MetaHuman body via
nearest-face transfer with matched world-space scale."""

import importlib
import json
import os
import sys

import bpy
from mathutils import Vector

PROJECT = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy"
SNAPSHOT = os.path.join(PROJECT, "Tools", "MetaHuman", "skeleton_snapshots.json")
EXCHANGE = os.path.join(PROJECT, "Saved", "BlenderExchange")
OUT_BLEND = os.path.join(EXCHANGE, "Body_UEFN_CopyW.blend")
OUT_FBX = os.path.join(EXCHANGE, "Body_UEFN_CopyW.fbx")

sys.path.insert(0, os.path.join(PROJECT, "Tools", "MetaHuman"))
from blender_ue_export import export_skeletal_fbx, ensure_cm_scene


def world_bounds(obj):
    coords = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def import_fbx(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path, ignore_leaf_bones=False, automatic_bone_orientation=False)
    new = [o for o in set(bpy.data.objects) - before]
    return new


def repose_to_uefn(arm, mesh, donor_arm):
    donor_rest = {b.name: b.matrix_local.copy() for b in donor_arm.data.bones}
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    ordered = sorted(arm.pose.bones, key=lambda p: sum(1 for _ in p.parent_recursive))
    for pb in ordered:
        t = donor_rest.get(pb.name)
        if t is not None:
            pb.matrix = t
            bpy.context.view_layer.update()
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.objects.active = mesh
    mod = mesh.modifiers.new("Bake", "ARMATURE")
    mod.object = arm
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def main():
    with open(SNAPSHOT, "r", encoding="utf-8") as f:
        uefn_names = {b["name"] for b in json.load(f)["uefn_reference"]["bones"]}

    bpy.ops.wm.read_factory_settings(use_empty=True)
    ensure_cm_scene()
    orig = import_fbx(os.path.join(EXCHANGE, "Body_Original_MH.fbx"))
    arm = next(o for o in orig if o.type == "ARMATURE")
    mesh = max((o for o in orig if o.type == "MESH"), key=lambda m: len(m.data.vertices))
    donor_objs = import_fbx(os.path.join(EXCHANGE, "UEFN_Mannequin.fbx"))
    donor_arm = next(o for o in donor_objs if o.type == "ARMATURE")
    donor_mesh = next(o for o in donor_objs if o.type == "MESH")

    repose_to_uefn(arm, mesh, donor_arm)
    print("REPOSED|hand_r_dist_check")

    # Scale donor to match body world height.
    bb = world_bounds(mesh)
    db = world_bounds(donor_mesh)
    mh = bb[5] - bb[4]
    dh = db[5] - db[4]
    factor = mh / dh if dh > 0 else 1.0
    for obj in (donor_mesh, donor_arm):
        obj.scale = tuple(s * factor for s in obj.scale)
    bpy.context.view_layer.update()
    # Align donor pelvis to body pelvis.
    body_pelvis = arm.matrix_world @ arm.data.bones["pelvis"].head_local
    donor_pelvis = donor_arm.matrix_world @ donor_arm.data.bones["pelvis"].head_local
    delta = body_pelvis - donor_pelvis
    donor_arm.location += delta
    bpy.context.view_layer.update()
    print("ALIGNED|factor={:.3f}|body_h={:.2f}|donor_h={:.2f}".format(factor, mh, dh))

    for vg in list(mesh.vertex_groups):
        mesh.vertex_groups.remove(vg)
    for name in sorted(uefn_names):
        if arm.data.bones.get(name):
            mesh.vertex_groups.new(name=name)

    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = donor_mesh
    bpy.ops.object.data_transfer(
        use_reverse_transfer=False,
        data_type="VGROUP_WEIGHTS",
        vert_mapping="POLYINTERP_NEAREST",
        layers_select_src="ALL",
        layers_select_dst="NAME",
        mix_mode="REPLACE",
    )
    print("TRANSFERRED|groups={}".format(len(mesh.vertex_groups)))

    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.vertex_group_limit_total(group_select_mode="ALL", limit=8)
    bpy.ops.object.vertex_group_normalize_all(group_select_mode="ALL", lock_active=False)

    # Remove non-UEFN bones from armature.
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for bone in list(arm.data.edit_bones):
        if bone.name not in uefn_names:
            arm.data.edit_bones.remove(bone)
    for bone in arm.data.edit_bones:
        t = donor_arm.data.bones.get(bone.name)
        if t:
            bone.matrix = t.matrix_local.copy()
            bone.length = t.length
    bpy.ops.object.mode_set(mode="OBJECT")
    print("BONES|{}".format(len(arm.data.bones)))

    for obj in donor_objs:
        bpy.data.objects.remove(obj, do_unlink=True)

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    export_skeletal_fbx(OUT_FBX, arm, [mesh])
    print("EXPORTED|{}".format(OUT_FBX))
    print("COPYW_DONE")
    sys.stdout.flush()


main()
