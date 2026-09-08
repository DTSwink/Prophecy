"""Audit wrist/ankle skinning before an Unreal reimport.

The report deliberately separates three failure classes:
  * non-unit object/bone scale or a mismatched rest pose;
  * a rigid skin-weight seam (no vertices bridge the two joint families);
  * linear-blend volume loss on vertices that genuinely blend the families.

Run headless:
  blender --background --python Tools/MetaHuman/blender_audit_joint_deformation.py
"""

import json
import math
import os
import statistics

import bpy
from mathutils import Vector


PROJECT = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy"
EXCHANGE = os.path.join(PROJECT, "Saved", "BlenderExchange")
SNAPSHOT = os.path.join(PROJECT, "Tools", "MetaHuman", "skeleton_snapshots.json")
FPS = 30

VARIANTS = (
    ("ReducedMH", "Body_UEFN78.blend"),
    ("Ancestor", "Body_UEFN78_Ancestor.blend"),
    ("CopyW", "Body_UEFN_CopyW.blend"),
)

CLIPS = (
    ("Climb", "Anim_Climb.fbx", 2.0),
    ("CliffCatch", "Anim_CliffCatch.fbx", 0.8),
)

JOINTS = (
    (
        "wrist_r",
        "lowerarm_r",
        "hand_r",
        ("lowerarm_r", "lowerarm_twist_01_r", "lowerarm_twist_02_r"),
        ("hand_r",),
        9.0,
    ),
    (
        "wrist_l",
        "lowerarm_l",
        "hand_l",
        ("lowerarm_l", "lowerarm_twist_01_l", "lowerarm_twist_02_l"),
        ("hand_l",),
        9.0,
    ),
    (
        "ankle_r",
        "calf_r",
        "foot_r",
        ("calf_r", "calf_twist_01_r", "calf_twist_02_r"),
        ("foot_r",),
        11.0,
    ),
    (
        "ankle_l",
        "calf_l",
        "foot_l",
        ("calf_l", "calf_twist_01_l", "calf_twist_02_l"),
        ("foot_l",),
        11.0,
    ),
)


def _fmt_vec(value):
    return "({:.5f},{:.5f},{:.5f})".format(value.x, value.y, value.z)


def _main_mesh_and_armature():
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    mesh = max(meshes, key=lambda item: len(item.data.vertices))
    modifiers = [m for m in mesh.modifiers if m.type == "ARMATURE"]
    if not modifiers:
        raise RuntimeError("Main mesh has no Armature modifier")
    modifier = modifiers[-1]
    armature = modifier.object
    if armature is None:
        raise RuntimeError("Armature modifier has no object")
    return mesh, armature, modifier


def _weights_for_vertex(mesh, vertex, group_names):
    index_to_name = {g.index: g.name for g in mesh.vertex_groups}
    result = {}
    for member in vertex.groups:
        name = index_to_name.get(member.group)
        if name in group_names and member.weight > 1.0e-6:
            result[name] = member.weight
    return result


def _family_weight(weights, family):
    return sum(weights.get(name, 0.0) for name in family)


def _joint_zone(mesh, armature, parent_name, child_name, radius):
    parent = armature.data.bones[parent_name]
    child = armature.data.bones[child_name]
    joint = child.head_local
    axis = joint - parent.head_local
    length = axis.length
    if length <= 1.0e-8:
        raise RuntimeError("Degenerate joint axis: " + child_name)
    axis.normalize()
    result = []
    for vertex in mesh.data.vertices:
        rel = vertex.co - joint
        axial = rel.dot(axis)
        radial = (rel - axis * axial).length
        if -radius * 1.5 <= axial <= radius * 0.75 and radial <= radius:
            result.append((vertex.index, axial, radial))
    return result


def _seam_stats(mesh, zone, parent_family, child_family):
    names = set(parent_family) | set(child_family)
    zone_ids = {item[0] for item in zone}
    kinds = {}
    bridge = parent_only = child_only = neither = 0
    for vertex_id in zone_ids:
        weights = _weights_for_vertex(mesh, mesh.data.vertices[vertex_id], names)
        parent_weight = _family_weight(weights, parent_family)
        child_weight = _family_weight(weights, child_family)
        has_parent = parent_weight > 0.01
        has_child = child_weight > 0.01
        if has_parent and has_child:
            bridge += 1
            kinds[vertex_id] = "bridge"
        elif has_parent:
            parent_only += 1
            kinds[vertex_id] = "parent"
        elif has_child:
            child_only += 1
            kinds[vertex_id] = "child"
        else:
            neither += 1
            kinds[vertex_id] = "neither"

    hard_edges = 0
    edge_uses = {}
    for polygon in mesh.data.polygons:
        for edge_key in polygon.edge_keys:
            key = tuple(sorted(edge_key))
            edge_uses[key] = edge_uses.get(key, 0) + 1
    boundary_edges = 0
    boundary_vertices = set()
    for edge in mesh.data.edges:
        a, b = edge.vertices
        if a not in zone_ids or b not in zone_ids:
            continue
        if edge_uses.get(tuple(sorted((a, b))), 0) == 1:
            boundary_edges += 1
            boundary_vertices.update((a, b))
        pair = {kinds[a], kinds[b]}
        if pair == {"parent", "child"}:
            hard_edges += 1
    return (
        bridge,
        parent_only,
        child_only,
        neither,
        hard_edges,
        boundary_edges,
        len(boundary_vertices),
    )


def _evaluated_positions(mesh):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = mesh.evaluated_get(depsgraph)
    evaluated_mesh = evaluated.to_mesh()
    try:
        return [evaluated.matrix_world @ vertex.co for vertex in evaluated_mesh.vertices]
    finally:
        evaluated.to_mesh_clear()


def _median_ratios(mesh, armature, zone, parent_name, child_name, positions):
    rest_parent = mesh.matrix_world @ armature.data.bones[parent_name].head_local
    rest_child = mesh.matrix_world @ armature.data.bones[child_name].head_local
    rest_axis = (rest_child - rest_parent).normalized()
    pose_parent = armature.matrix_world @ armature.pose.bones[parent_name].head
    pose_child = armature.matrix_world @ armature.pose.bones[child_name].head
    pose_axis = (pose_child - pose_parent).normalized()

    bins = {(-9.0, -6.0): [], (-6.0, -3.0): [], (-3.0, 0.0): [], (0.0, 3.0): []}
    for vertex_id, axial, _ in zone:
        source_world = mesh.matrix_world @ mesh.data.vertices[vertex_id].co
        source_rel = source_world - rest_child
        rest_radius = (source_rel - rest_axis * source_rel.dot(rest_axis)).length
        posed_rel = positions[vertex_id] - pose_child
        posed_radius = (posed_rel - pose_axis * posed_rel.dot(pose_axis)).length
        if rest_radius <= 1.0e-5:
            continue
        for limits in bins:
            if limits[0] <= axial < limits[1]:
                bins[limits].append(posed_radius / rest_radius)
                break
    return {
        limits: statistics.median(values) if values else None
        for limits, values in bins.items()
    }


def _pose_scale_error(armature):
    worst = (0.0, None, None)
    for bone in armature.pose.bones:
        scale = bone.matrix.to_scale()
        error = max(abs(scale.x - 1.0), abs(scale.y - 1.0), abs(scale.z - 1.0))
        if error > worst[0]:
            worst = (error, bone.name, scale)
    return worst


def _audit_variant(label, blend_name):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(EXCHANGE, blend_name))
    mesh, body_armature, modifier = _main_mesh_and_armature()
    print(
        "VARIANT|{}|verts={}|bones={}|mesh_scale={}|arm_scale={}|preserve_volume={}".format(
            label,
            len(mesh.data.vertices),
            len(body_armature.data.bones),
            _fmt_vec(mesh.scale),
            _fmt_vec(body_armature.scale),
            modifier.use_deform_preserve_volume,
        )
    )
    group_totals = {group.name: 0.0 for group in mesh.vertex_groups}
    index_to_name = {group.index: group.name for group in mesh.vertex_groups}
    for vertex in mesh.data.vertices:
        for member in vertex.groups:
            group_totals[index_to_name[member.group]] += member.weight
    zero_groups = sorted(name for name, total in group_totals.items() if total <= 1.0e-8)
    print("ZERO_GROUPS|{}|{}".format(label, zero_groups))

    zones = {}
    for joint in JOINTS:
        name, parent, child, parent_family, child_family, radius = joint
        zone = _joint_zone(mesh, body_armature, parent, child, radius)
        zones[name] = zone
        stats = _seam_stats(mesh, zone, parent_family, child_family)
        print(
            "SEAM|{}|{}|zone={}|bridge={}|parent_only={}|child_only={}|neither={}|hard_edges={}|boundary_edges={}|boundary_verts={}".format(
                label, name, len(zone), *stats
            )
        )

    original_target = modifier.object
    original_mesh_world = mesh.matrix_world.copy()
    original_arm_world = body_armature.matrix_world.copy()
    mesh_relative = original_arm_world.inverted() @ original_mesh_world
    for clip_label, clip_file, sample_time in CLIPS:
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(
            filepath=os.path.join(EXCHANGE, clip_file),
            ignore_leaf_bones=False,
            automatic_bone_orientation=False,
        )
        imported = list(set(bpy.data.objects) - before)
        anim_armature = next(obj for obj in imported if obj.type == "ARMATURE")
        anim_armature.matrix_world = original_arm_world
        modifier.object = anim_armature
        bpy.context.scene.frame_set(int(round(sample_time * FPS)))
        # The imported clips carry root motion on the armature object.  Follow
        # that object transform just as the Unreal component does; otherwise
        # mesh vertices and pose-bone axes are measured in different spaces.
        mesh.matrix_world = anim_armature.matrix_world @ mesh_relative
        bpy.context.view_layer.update()

        scale_error, scale_bone, scale = _pose_scale_error(anim_armature)
        print(
            "POSE_SCALE|{}|{}|max_error={:.8f}|bone={}|scale={}".format(
                label, clip_label, scale_error, scale_bone, _fmt_vec(scale)
            )
        )

        for preserve in (False, True):
            modifier.use_deform_preserve_volume = preserve
            bpy.context.view_layer.update()
            positions = _evaluated_positions(mesh)
            for joint in JOINTS:
                name, parent, child, _, _, _ = joint
                ratios = _median_ratios(
                    mesh, anim_armature, zones[name], parent, child, positions
                )
                encoded = ",".join(
                    "{}..{}={}".format(
                        int(limits[0]),
                        int(limits[1]),
                        "na" if value is None else "{:.4f}".format(value),
                    )
                    for limits, value in ratios.items()
                )
                print(
                    "RADIUS|{}|{}|{}|preserve={}|{}".format(
                        label, clip_label, name, int(preserve), encoded
                    )
                )

        modifier.object = original_target
        modifier.use_deform_preserve_volume = False
        for obj in imported:
            bpy.data.objects.remove(obj, do_unlink=True)


def _audit_original_helpers():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(
        filepath=os.path.join(EXCHANGE, "Body_Original_MH.fbx"),
        ignore_leaf_bones=False,
        automatic_bone_orientation=False,
        use_custom_normals=True,
    )
    mesh, armature, _ = _main_mesh_and_armature()
    with open(SNAPSHOT, "r", encoding="utf-8") as handle:
        snapshot = json.load(handle)
    uefn_names = {bone["name"] for bone in snapshot["uefn_reference"]["bones"]}

    index_to_name = {group.index: group.name for group in mesh.vertex_groups}
    for side in ("r", "l"):
        for joint_name, child_name, radius in (
            ("wrist_" + side, "hand_" + side, 10.0),
            ("ankle_" + side, "foot_" + side, 12.0),
        ):
            child = armature.data.bones[child_name]
            joint = child.head_local
            totals = {}
            counts = {}
            centroids = {}
            for vertex in mesh.data.vertices:
                if (vertex.co - joint).length > radius:
                    continue
                for member in vertex.groups:
                    if member.weight <= 1.0e-4:
                        continue
                    name = index_to_name[member.group]
                    totals[name] = totals.get(name, 0.0) + member.weight
                    counts[name] = counts.get(name, 0) + 1
                    centroids[name] = centroids.get(name, Vector()) + vertex.co * member.weight

            helpers = []
            for name, total in totals.items():
                if name in uefn_names:
                    continue
                bone = armature.data.bones.get(name)
                centroid = centroids[name] / total
                helpers.append(
                    (
                        -total,
                        name,
                        counts[name],
                        total,
                        (centroid - joint).length,
                        bone.parent.name if bone and bone.parent else None,
                    )
                )
            for _, name, count, total, distance, parent in sorted(helpers)[:24]:
                print(
                    "HELPER|{}|{}|verts={}|total={:.4f}|centroid_dist={:.4f}|parent={}".format(
                        joint_name, name, count, total, distance, parent
                    )
                )


def main():
    requested = {
        item.strip()
        for item in os.environ.get("PROPHECY_MH_AUDIT_VARIANTS", "").split(",")
        if item.strip()
    }
    for label, blend_name in VARIANTS:
        if requested and label not in requested:
            continue
        _audit_variant(label, blend_name)
    _audit_original_helpers()
    print("JOINT_AUDIT_DONE")


main()
