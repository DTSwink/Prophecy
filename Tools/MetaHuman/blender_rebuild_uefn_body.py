"""Rebuild the MetaHuman body on the untouched UEFN skeleton, fixing the
mesh/skeleton bind mismatch, then fold helper weights and export.

Root cause being fixed: SKM_test_UEFNFit_BodyMesh has UEFN-stamped joints but
its geometry stayed in the MetaHuman rest pose; hand joints sit 15-17 cm from
the skin weighted to them, which breaks every large arm rotation regardless of
weights.

Approach (correspondence-free): start from the ORIGINAL SKM_test_BodyMesh,
whose mesh and skeleton are consistent (hand centroid-to-joint ~1.8 cm).
Pose its shared bones onto the exact UEFN reference transforms (donor:
UEFN_Mannequin.fbx export) - MetaHuman-only helpers keep identity local pose
and ride along - then apply the pose as the new rest. The LBS repose both
moves the mesh into the UEFN bind pose and conforms limb proportions to the
UEFN joint placement in one step. Finally fold every MetaHuman-only vertex
group into its nearest shared ancestor, delete MetaHuman-only bones, export.

Run headless:
  blender --background --python Tools/MetaHuman/blender_rebuild_uefn_body.py
"""

import importlib
import json
import os
import sys

import bpy
from mathutils import Vector

PROJECT = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy"
SNAPSHOT = os.path.join(PROJECT, "Tools", "MetaHuman", "skeleton_snapshots.json")
EXCHANGE = os.path.join(PROJECT, "Saved", "BlenderExchange")
ORIGINAL_FBX = os.path.join(EXCHANGE, "Body_Original_MH.fbx")
UEFN_FBX = os.path.join(EXCHANGE, "UEFN_Mannequin.fbx")
# Ancestor folding is deformation-identical for undriven MetaHuman helpers:
# each removed helper rides its nearest surviving parent rigidly, so adding its
# smooth weight field to that parent preserves the original result.  "current"
# remains available only to reproduce the superseded manual wrist experiment.
REDUCTION_MODE = os.environ.get("PROPHECY_MH_REDUCTION_MODE", "ancestor")
OUTPUT_TAG = os.environ.get("PROPHECY_MH_OUTPUT_TAG", "")
PRESERVE_VOLUME = os.environ.get("PROPHECY_MH_PRESERVE_VOLUME", "1") != "0"
OUT_FBX = os.path.join(EXCHANGE, "Body_UEFN78{}.fbx".format(OUTPUT_TAG))
OUT_BLEND = os.path.join(EXCHANGE, "Body_UEFN78{}.blend".format(OUTPUT_TAG))

sys.path.insert(0, os.path.join(PROJECT, "Tools", "MetaHuman"))
from blender_ue_export import export_skeletal_fbx, ensure_cm_scene


def enable_mtm():
    addons_root = os.path.join(
        os.environ.get("APPDATA", ""),
        "Blender Foundation", "Blender", "5.1", "scripts", "addons",
    )
    if addons_root not in sys.path:
        sys.path.insert(0, addons_root)
    import MetahumanToManny as mtm
    importlib.reload(mtm)
    mtm.register()


def run_mtm_cleanup(mesh, arm):
    """MTM weight cleanup only — no Manny bone deletion."""
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.cleanup_bone_weights()
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.cleanup_all_vertex_groups()
    bpy.ops.object.fix_seams()
    print("MTM_CLEANUP|groups={}".format(len(mesh.vertex_groups)))


def import_fbx(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(
        filepath=path,
        ignore_leaf_bones=False,
        automatic_bone_orientation=False,
        use_custom_normals=True,
    )
    new_objects = [o for o in set(bpy.data.objects) - before]
    armature = next(o for o in new_objects if o.type == "ARMATURE")
    mesh = next(o for o in new_objects if o.type == "MESH")
    return armature, mesh, new_objects


def smooth_joint_transition(mesh, arm, bone_a, bone_b, radius=4.0, blend=0.35):
    """Blend weights between two adjacent bones in a spherical joint zone."""
    ba = arm.data.bones.get(bone_a)
    bb = arm.data.bones.get(bone_b)
    vg_a = mesh.vertex_groups.get(bone_a)
    vg_b = mesh.vertex_groups.get(bone_b)
    if not all((ba, bb, vg_a, vg_b)):
        return 0
    joint = (ba.tail_local + bb.head_local) / 2.0
    gi_a, gi_b = vg_a.index, vg_b.index
    changed = 0
    for v in mesh.data.vertices:
        if (v.co - joint).length > radius:
            continue
        wa = wb = 0.0
        for g in v.groups:
            if g.group == gi_a:
                wa = g.weight
            elif g.group == gi_b:
                wb = g.weight
        if wa > 0.01 and wb > 0.01:
            continue
        if wa > 0.01 and wb < 0.01:
            share = wa * blend
            vg_b.add([v.index], share, "ADD")
            vg_a.add([v.index], -share, "ADD")
            changed += 1
        elif wb > 0.01 and wa < 0.01:
            share = wb * blend
            vg_a.add([v.index], share, "ADD")
            vg_b.add([v.index], -share, "ADD")
            changed += 1
    return changed


def normalize_weights(mesh):
    for v in mesh.data.vertices:
        total = sum(g.weight for g in v.groups)
        if total <= 0.0 or abs(total - 1.0) < 0.001:
            continue
        for g in v.groups:
            mesh.vertex_groups[g.group].add([v.index], g.weight / total, "REPLACE")


def group_centroid_distance(mesh_obj, arm_obj, group_name, threshold=0.4):
    vg = mesh_obj.vertex_groups.get(group_name)
    bone = arm_obj.data.bones.get(group_name)
    if vg is None or bone is None:
        return None
    gi = vg.index
    centroid = Vector((0.0, 0.0, 0.0))
    wsum = 0.0
    for v in mesh_obj.data.vertices:
        for g in v.groups:
            if g.group == gi and g.weight > threshold:
                centroid += v.co * g.weight
                wsum += g.weight
                break
    if wsum == 0.0:
        return None
    return ((centroid / wsum) - bone.head_local).length


def main():
    if REDUCTION_MODE not in {"current", "ancestor"}:
        raise RuntimeError("Unknown reduction mode: " + REDUCTION_MODE)
    print("REDUCTION_MODE|{}|tag={}|preserve_volume={}".format(
        REDUCTION_MODE, OUTPUT_TAG, PRESERVE_VOLUME))
    with open(SNAPSHOT, "r", encoding="utf-8") as handle:
        snapshot = json.load(handle)
    uefn_names = {b["name"] for b in snapshot["uefn_reference"]["bones"]}
    mh_bones = snapshot["fitted_metahuman_body_reference"]["bones"]
    mh_parent = {b["name"]: b["parent"] for b in mh_bones}

    fold = {}
    for bone in mh_bones:
        name = bone["name"]
        if name in uefn_names:
            continue
        ancestor = mh_parent.get(name)
        while ancestor and ancestor not in uefn_names:
            ancestor = mh_parent.get(ancestor)
        if ancestor is None:
            raise RuntimeError("No shared ancestor for " + name)
        fold[name] = ancestor

    bpy.ops.wm.read_factory_settings(use_empty=True)
    ensure_cm_scene()
    enable_mtm()
    arm, mesh, _ = import_fbx(ORIGINAL_FBX)
    donor_arm, donor_mesh, donor_objects = import_fbx(UEFN_FBX)
    donor_rest = {b.name: b.matrix_local.copy() for b in donor_arm.data.bones}
    donor_length = {b.name: b.length for b in donor_arm.data.bones}
    print("IMPORTED|orig_bones={}|verts={}|groups={}".format(
        len(arm.data.bones), len(mesh.data.vertices), len(mesh.vertex_groups)))

    before_dist = group_centroid_distance(mesh, arm, "hand_r")
    print("BEFORE_CONSISTENCY|hand_r|dist={:.4f}".format(before_dist))

    # 1) Pose shared bones onto the UEFN reference, parents before children.
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    ordered = list(arm.pose.bones)

    def depth(pose_bone):
        d = 0
        p = pose_bone.parent
        while p:
            d += 1
            p = p.parent
        return d

    ordered.sort(key=depth)
    posed = 0
    for pose_bone in ordered:
        target = donor_rest.get(pose_bone.name)
        if target is None:
            continue
        pose_bone.matrix = target
        bpy.context.view_layer.update()
        posed += 1
    bpy.ops.object.mode_set(mode="OBJECT")
    print("POSED|shared_bones={}".format(posed))

    # 2) Bake the posed shape into the mesh, then apply pose as rest.
    bpy.context.view_layer.objects.active = mesh
    baked = mesh.modifiers.new(name="BakePose", type="ARMATURE")
    baked.object = arm
    # The source and UEFN bind poses differ by large compound rotations at the
    # wrist and ankle. Linear blend skinning collapses the joint cross-section
    # during this one-time geometry conversion, leaving a cuff-shaped defect in
    # the new *rest mesh*. Dual-quaternion deformation preserves that volume.
    baked.use_deform_preserve_volume = PRESERVE_VOLUME
    while mesh.modifiers.find(baked.name) > 0:
        bpy.ops.object.modifier_move_up(modifier=baked.name)
    bpy.ops.object.modifier_apply(modifier=baked.name)

    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode="OBJECT")

    worst = 0.0
    for bone in arm.data.bones:
        target = donor_rest.get(bone.name)
        if target is None:
            continue
        worst = max(worst, (bone.matrix_local.translation - target.translation).length)
    print("REST_MATCH|worst_shared_translation={:.6f}".format(worst))

    after_dist = group_centroid_distance(mesh, arm, "hand_r")
    print("AFTER_CONSISTENCY|hand_r|dist={:.4f}".format(after_dist))

    # 2b) MTM weight cleanup on the repose-consistent mesh before folding.
    run_mtm_cleanup(mesh, arm)

    # 3) Fold MetaHuman-only groups into shared ancestors.
    # Wrist helpers must split between lowerarm and hand, not dump全部 into hand.
    WRIST_SPLIT = {
        "wrist_inner_l": ("lowerarm_l", "hand_l"),
        "wrist_outer_l": ("lowerarm_l", "hand_l"),
        "wrist_inner_r": ("lowerarm_r", "hand_r"),
        "wrist_outer_r": ("lowerarm_r", "hand_r"),
    }
    folded = 0
    for src_name, dst_name in sorted(fold.items()):
        src = mesh.vertex_groups.get(src_name)
        if src is None:
            continue
        gi = src.index
        if REDUCTION_MODE == "current" and src_name in WRIST_SPLIT:
            arm_bone, hand_bone = WRIST_SPLIT[src_name]
            vg_arm = mesh.vertex_groups.get(arm_bone)
            vg_hand = mesh.vertex_groups.get(hand_bone)
            if vg_arm is None:
                vg_arm = mesh.vertex_groups.new(name=arm_bone)
            if vg_hand is None:
                vg_hand = mesh.vertex_groups.new(name=hand_bone)
            ba = arm.data.bones[arm_bone]
            bh = arm.data.bones[hand_bone]
            span = (bh.head_local - ba.tail_local).length or 1.0
            for v in mesh.data.vertices:
                for g in v.groups:
                    if g.group != gi or g.weight <= 0.0:
                        continue
                    t = (v.co - ba.tail_local).length / span
                    t = max(0.0, min(1.0, t))
                    vg_arm.add([v.index], g.weight * (1.0 - t), "ADD")
                    vg_hand.add([v.index], g.weight * t, "ADD")
                    break
        else:
            dst = mesh.vertex_groups.get(dst_name)
            if dst is None:
                dst = mesh.vertex_groups.new(name=dst_name)
            for v in mesh.data.vertices:
                for g in v.groups:
                    if g.group == gi and g.weight > 0.0:
                        dst.add([v.index], g.weight, "ADD")
                        break
        mesh.vertex_groups.remove(src)
        folded += 1
    normalize_weights(mesh)
    print("FOLDED|{}".format(folded))

    # 3b) Blend lowerarm/hand transitions — folding helper bones leaves a hard
    # seam with zero co-influenced verts at the wrist.
    blended = 0
    if REDUCTION_MODE == "current":
        for a, b in (
            ("lowerarm_r", "hand_r"), ("lowerarm_l", "hand_l"),
            ("upperarm_r", "lowerarm_r"), ("upperarm_l", "lowerarm_l"),
            ("clavicle_r", "upperarm_r"), ("clavicle_l", "upperarm_l"),
        ):
            blended += smooth_joint_transition(mesh, arm, a, b, radius=5.0, blend=0.4)
    normalize_weights(mesh)
    print("BLENDED|verts={}".format(blended))

    leftover = [g.name for g in mesh.vertex_groups if g.name not in uefn_names]
    if leftover:
        raise RuntimeError("Leftover groups: {}".format(leftover))

    bad = sum(
        1 for v in mesh.data.vertices
        if abs(sum(g.weight for g in v.groups) - 1.0) > 0.01
    )
    print("WEIGHT_SUM_CHECK|bad={}".format(bad))
    if bad:
        raise RuntimeError("Weight mass lost on {} vertices".format(bad))

    # 4) Delete MetaHuman-only bones; snap kept bones exactly onto the donor.
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    removed = 0
    for name in list(fold.keys()):
        eb = arm.data.edit_bones.get(name)
        if eb is not None:
            arm.data.edit_bones.remove(eb)
            removed += 1
    for eb in arm.data.edit_bones:
        eb.matrix = donor_rest[eb.name]
        eb.length = donor_length[eb.name]
    bpy.ops.object.mode_set(mode="OBJECT")
    print("BONES_REMOVED|{}|remaining={}".format(removed, len(arm.data.bones)))

    for check in ("hand_r", "index_03_r", "foot_r", "head"):
        dist = group_centroid_distance(mesh, arm, check)
        if dist is not None:
            print("FINAL_CONSISTENCY|{}|dist={:.4f}".format(check, dist))

    keep = {arm, mesh}
    for obj in list(bpy.data.objects):
        if obj not in keep:
            bpy.data.objects.remove(obj, do_unlink=True)
    if arm.name != "root":
        arm.name = "root"

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    export_skeletal_fbx(OUT_FBX, arm, [mesh])
    print("EXPORTED|{}|bytes={}".format(OUT_FBX, os.path.getsize(OUT_FBX)))
    print("REBUILD_DONE")
    sys.stdout.flush()


main()
