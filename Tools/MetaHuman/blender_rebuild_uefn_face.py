"""Build the static face mesh + reusable weight template on the UEFN skeleton.

Same repose approach as blender_rebuild_uefn_body.py: the ORIGINAL face mesh
(consistent MetaHuman rig) is posed so its UEFN-shared bones (spine_04/05,
neck_01/02, head, clavicles) land on the exact UEFN reference transforms, the
pose is applied as rest, and every non-UEFN bone (about 700 facial joints,
plus helpers) folds into its nearest shared ancestor - for facial joints that
is `head`, which is exact since they never move without facial animation.

Outputs:
  Saved/BlenderExchange/Face_UEFN.fbx     face mesh on UEFN-subset skeleton
  Saved/BlenderExchange/Face_UEFN.blend
  Tools/MetaHuman/face_weight_template.json  per-vertex-index weights for
      stamping onto any other MetaHuman face (identical topology).

Run headless:
  blender --background --python Tools/MetaHuman/blender_rebuild_uefn_face.py
"""

import json
import os
import sys

import bpy

PROJECT = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy"
SNAPSHOT = os.path.join(PROJECT, "Tools", "MetaHuman", "skeleton_snapshots.json")
EXCHANGE = os.path.join(PROJECT, "Saved", "BlenderExchange")
FACE_FBX = os.path.join(EXCHANGE, "Face_Original_MH.fbx")
UEFN_FBX = os.path.join(EXCHANGE, "UEFN_Mannequin.fbx")
OUT_FBX = os.path.join(EXCHANGE, "Face_UEFN.fbx")
OUT_BLEND = os.path.join(EXCHANGE, "Face_UEFN.blend")
TEMPLATE = os.path.join(PROJECT, "Tools", "MetaHuman", "face_weight_template.json")


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
    meshes = [o for o in new_objects if o.type == "MESH"]
    return armature, meshes, new_objects


def main():
    with open(SNAPSHOT, "r", encoding="utf-8") as handle:
        snapshot = json.load(handle)
    uefn_names = {b["name"] for b in snapshot["uefn_reference"]["bones"]}

    bpy.ops.wm.read_factory_settings(use_empty=True)
    arm, meshes, _ = import_fbx(FACE_FBX)
    mesh = max(meshes, key=lambda m: len(m.data.vertices))
    donor_arm, _donor_meshes, donor_objects = import_fbx(UEFN_FBX)
    donor_rest = {b.name: b.matrix_local.copy() for b in donor_arm.data.bones}
    donor_length = {b.name: b.length for b in donor_arm.data.bones}
    print("IMPORTED|face_bones={}|verts={}|groups={}|meshes={}".format(
        len(arm.data.bones), len(mesh.data.vertices), len(mesh.vertex_groups),
        [m.name for m in meshes]))

    shared_in_face = [b.name for b in arm.data.bones if b.name in uefn_names]
    print("SHARED_IN_FACE|{}".format(sorted(shared_in_face)))

    # Fold map: nearest UEFN-shared ancestor within the face armature.
    parent = {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones}
    fold = {}
    for bone in arm.data.bones:
        name = bone.name
        if name in uefn_names:
            continue
        ancestor = parent.get(name)
        while ancestor and ancestor not in uefn_names:
            ancestor = parent.get(ancestor)
        if ancestor is None:
            raise RuntimeError("No shared ancestor for face bone " + name)
        fold[name] = ancestor
    to_head = sum(1 for v in fold.values() if v == "head")
    print("FOLD_MAP|{} bones|{} fold to head".format(len(fold), to_head))

    # 1) Pose shared bones onto the UEFN reference, apply as rest.
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
    print("POSED|shared={}".format(posed))

    for m in meshes:
        bpy.context.view_layer.objects.active = m
        baked = m.modifiers.new(name="BakePose", type="ARMATURE")
        baked.object = arm
        while m.modifiers.find(baked.name) > 0:
            bpy.ops.object.modifier_move_up(modifier=baked.name)
        bpy.ops.object.modifier_apply(modifier=baked.name)

    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode="OBJECT")

    # 2) Fold non-UEFN groups on every face mesh part (eyes, teeth, lashes...).
    for m in meshes:
        folded = 0
        for src_name, dst_name in fold.items():
            src = m.vertex_groups.get(src_name)
            if src is None:
                continue
            dst = m.vertex_groups.get(dst_name)
            if dst is None:
                dst = m.vertex_groups.new(name=dst_name)
            gi = src.index
            for v in m.data.vertices:
                for g in v.groups:
                    if g.group == gi and g.weight > 0.0:
                        dst.add([v.index], g.weight, "ADD")
                        break
            m.vertex_groups.remove(src)
            folded += 1
        bad = sum(
            1 for v in m.data.vertices
            if abs(sum(g.weight for g in v.groups) - 1.0) > 0.01
        )
        print("MESH_FOLDED|{}|groups_folded={}|bad_sums={}|final_groups={}".format(
            m.name, folded, bad, [g.name for g in m.vertex_groups]))
        if bad:
            raise RuntimeError("Weight mass lost on {} ({})".format(m.name, bad))

    # 3) Delete non-UEFN bones, snap kept bones exactly onto the donor rest.
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
    print("BONES_REMOVED|{}|remaining={}".format(
        removed, [b.name for b in arm.data.bones]))

    # 4) Save the per-vertex weight template of the main face mesh.
    template = []
    group_names = {g.index: g.name for g in mesh.vertex_groups}
    for v in mesh.data.vertices:
        template.append({
            group_names[g.group]: round(g.weight, 6)
            for g in v.groups if g.weight > 0.0
        })
    with open(TEMPLATE, "w", encoding="utf-8") as handle:
        json.dump({
            "source_mesh": "SKM_test_FaceMesh LOD0 (Blender import order)",
            "num_vertices": len(template),
            "weights": template,
        }, handle)
    print("TEMPLATE_SAVED|verts={}".format(len(template)))

    keep = set(meshes) | {arm}
    for obj in list(bpy.data.objects):
        if obj not in keep:
            bpy.data.objects.remove(obj, do_unlink=True)
    if arm.name != "root":
        arm.name = "root"

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)

    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    for m in meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = arm
    # Bake the UE-import 0.01 object scale into the data so the FBX round-trips
    # at true centimeter size instead of arriving 100x too large in UE.
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
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
    print("FACE_REBUILD_DONE")
    sys.stdout.flush()


main()
