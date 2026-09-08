"""Reduce the fitted MetaHuman body to the 78 shared UEFN bones in Blender.

Run headless:
  blender --background --python Tools/MetaHuman/blender_reduce_body_to_uefn.py

Approach (validated against the MetahumanToManny addon): keep the original
continuous MetaHuman skinning and additively merge every MetaHuman-only
vertex group into its nearest shared ancestor bone, then delete the
MetaHuman-only bones. Undriven helpers follow their parent rigidly, so this
fold is deformation-identical to a MetaHuman with its post-process AnimBP
disabled. No weight smoothing is needed: summing smooth fields stays smooth.
"""

import json
import os
import sys

import bpy

PROJECT = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy"
SNAPSHOT = os.path.join(PROJECT, "Tools", "MetaHuman", "skeleton_snapshots.json")
BODY_FBX = os.path.join(PROJECT, "Saved", "BlenderExchange", "Body_MH342.fbx")
UEFN_FBX = os.path.join(PROJECT, "Saved", "BlenderExchange", "UEFN_Mannequin.fbx")
OUT_FBX = os.path.join(PROJECT, "Saved", "BlenderExchange", "Body_UEFN78.fbx")
OUT_BLEND = os.path.join(PROJECT, "Saved", "BlenderExchange", "Body_UEFN78.blend")


def build_fold_map():
    """Map each MetaHuman-only bone to its nearest shared (UEFN) ancestor."""
    with open(SNAPSHOT, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    uefn_names = {b["name"] for b in data["uefn_reference"]["bones"]}
    mh_bones = data["fitted_metahuman_body_reference"]["bones"]
    parent = {b["name"]: b["parent"] for b in mh_bones}

    fold = {}
    for bone in mh_bones:
        name = bone["name"]
        if name in uefn_names:
            continue
        ancestor = parent.get(name)
        while ancestor and ancestor not in uefn_names:
            ancestor = parent.get(ancestor)
        if ancestor is None:
            raise RuntimeError("No shared ancestor for bone: " + name)
        fold[name] = ancestor
    return uefn_names, fold


def merge_group(mesh_obj, src_name, dst_name):
    """Add src group weights into dst group, then remove src. Fast path."""
    src = mesh_obj.vertex_groups.get(src_name)
    if src is None:
        return 0
    dst = mesh_obj.vertex_groups.get(dst_name)
    if dst is None:
        dst = mesh_obj.vertex_groups.new(name=dst_name)
    src_index = src.index
    touched = 0
    for vertex in mesh_obj.data.vertices:
        weight = 0.0
        for group_entry in vertex.groups:
            if group_entry.group == src_index:
                weight = group_entry.weight
                break
        if weight > 0.0:
            dst.add([vertex.index], weight, "ADD")
            touched += 1
    mesh_obj.vertex_groups.remove(src)
    return touched


def main():
    uefn_names, fold = build_fold_map()
    print("FOLD_MAP|{} MetaHuman-only bones".format(len(fold)))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    # ignore_leaf_bones must stay False: this FBX comes from Unreal and has no
    # Blender-style "_end" terminators; True silently drops real leaf bones.
    bpy.ops.import_scene.fbx(
        filepath=BODY_FBX,
        ignore_leaf_bones=False,
        automatic_bone_orientation=False,
        use_custom_normals=True,
    )

    armature = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    mesh_obj = next(o for o in bpy.data.objects if o.type == "MESH")
    print("IMPORTED|bones={}|verts={}|groups={}".format(
        len(armature.data.bones), len(mesh_obj.data.vertices), len(mesh_obj.vertex_groups)))

    # Fold weights of MetaHuman-only groups into their shared ancestors.
    # Order does not matter: fold targets are always shared bones.
    folded = 0
    for src_name, dst_name in sorted(fold.items()):
        touched = merge_group(mesh_obj, src_name, dst_name)
        if touched:
            print("MERGE|{}->{}|verts={}".format(src_name, dst_name, touched))
            folded += 1

    # Any remaining group must be a shared UEFN bone.
    leftover = [g.name for g in mesh_obj.vertex_groups if g.name not in uefn_names]
    if leftover:
        raise RuntimeError("Unexpected leftover groups: {}".format(leftover))

    # Verify per-vertex weight sums survived the fold.
    bad = 0
    for vertex in mesh_obj.data.vertices:
        total = sum(entry.weight for entry in vertex.groups)
        if abs(total - 1.0) > 0.01:
            bad += 1
    print("WEIGHT_SUM_CHECK|out_of_tolerance={}".format(bad))
    if bad:
        raise RuntimeError("{} vertices lost weight mass during fold".format(bad))

    # Delete MetaHuman-only bones from the armature.
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT")
    removed = 0
    for bone_name in list(fold.keys()):
        edit_bone = armature.data.edit_bones.get(bone_name)
        if edit_bone is not None:
            armature.data.edit_bones.remove(edit_bone)
            removed += 1
    bpy.ops.object.mode_set(mode="OBJECT")
    print("BONES_REMOVED|{}|remaining={}".format(removed, len(armature.data.bones)))

    # The UE-exported "root" bone becomes the Blender armature *object*; UE's
    # FBX importer reconstructs it from the root node on reimport, so the
    # armature must keep the name "root" (and must not be called "Armature").
    if armature.name != "root":
        raise RuntimeError("Armature object is named {!r}, expected 'root'".format(armature.name))

    remaining = {b.name for b in armature.data.bones}
    with open(SNAPSHOT, "r", encoding="utf-8") as handle:
        mh_names = {b["name"] for b in json.load(handle)["fitted_metahuman_body_reference"]["bones"]}
    expected = (uefn_names & mh_names) - {"root"}
    if remaining != expected:
        raise RuntimeError(
            "Bone set mismatch. Missing: {} Unexpected: {}".format(
                sorted(expected - remaining), sorted(remaining - expected)))

    print("GROUPS_FINAL|{}|folded_groups={}".format(len(mesh_obj.vertex_groups), folded))

    # Snap the remaining bones' rest transforms to the exact UEFN reference
    # pose, using the exported UEFN mannequin FBX as the donor so both sides
    # share the same FBX->Blender conventions. The fitted body deviates on the
    # twist bones (up to 8.8 cm pivot offset along the limb axis); UEFN
    # animations key those pivots at UEFN positions, so the bind must match.
    # Twist pivots sliding along their own rotation axis are
    # deformation-neutral, so the mesh needs no compensation.
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(
        filepath=UEFN_FBX,
        ignore_leaf_bones=False,
        automatic_bone_orientation=False,
    )
    donor_objects = list(set(bpy.data.objects) - before)
    donor_arm = next(o for o in donor_objects if o.type == "ARMATURE")
    if donor_arm.matrix_world != armature.matrix_world:
        raise RuntimeError("Donor armature object transform differs from body")
    donor_rest = {}
    donor_length = {}
    for bone in donor_arm.data.bones:
        donor_rest[bone.name] = bone.matrix_local.copy()
        donor_length[bone.name] = bone.length

    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT")
    snapped = 0
    for edit_bone in armature.data.edit_bones:
        if edit_bone.name not in donor_rest:
            raise RuntimeError("UEFN donor is missing bone: " + edit_bone.name)
        old_head = edit_bone.head.copy()
        edit_bone.matrix = donor_rest[edit_bone.name]
        edit_bone.length = donor_length[edit_bone.name]
        if (edit_bone.head - old_head).length > 1e-4:
            snapped += 1
    bpy.ops.object.mode_set(mode="OBJECT")
    print("REST_SNAPPED|moved_bones={}".format(snapped))

    for obj in donor_objects:
        bpy.data.objects.remove(obj, do_unlink=True)

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)

    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.export_scene.fbx(
        filepath=OUT_FBX,
        use_selection=True,
        object_types={"ARMATURE", "MESH"},
        add_leaf_bones=False,
        apply_scale_options="FBX_SCALE_UNITS",
        mesh_smooth_type="FACE",
        use_tspace=False,
        bake_anim=False,
    )
    print("EXPORTED|{}|bytes={}".format(OUT_FBX, os.path.getsize(OUT_FBX)))
    print("REDUCE_DONE")
    sys.stdout.flush()


main()
