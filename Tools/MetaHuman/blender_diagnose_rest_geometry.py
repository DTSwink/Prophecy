"""Print transform, topology, and weighted-centroid diagnostics for body sources."""

import os

import bpy
from mathutils import Vector


PROJECT = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy"
EXCHANGE = os.path.join(PROJECT, "Saved", "BlenderExchange")
VARIANTS = (
    ("OriginalMH", "fbx", "Body_Original_MH.fbx"),
    ("FittedMH342", "fbx", "Body_MH342.fbx"),
    ("ReducedUEFN", "blend", "Body_UEFN78.blend"),
)


def load(kind, filename):
    path = os.path.join(EXCHANGE, filename)
    if kind == "blend":
        bpy.ops.wm.open_mainfile(filepath=path)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(
            filepath=path,
            ignore_leaf_bones=False,
            automatic_bone_orientation=False,
            use_custom_normals=True,
        )
    mesh = max(
        (obj for obj in bpy.data.objects if obj.type == "MESH"),
        key=lambda obj: len(obj.data.vertices),
    )
    modifier = next(mod for mod in mesh.modifiers if mod.type == "ARMATURE")
    armature = modifier.object
    armature.data.pose_position = "REST"
    bpy.context.view_layer.update()
    return mesh, armature


def weighted_centroid(mesh, group_name, threshold=0.0):
    group = mesh.vertex_groups.get(group_name)
    if group is None:
        return None
    total = 0.0
    centroid = Vector()
    for vertex in mesh.data.vertices:
        for membership in vertex.groups:
            if membership.group == group.index and membership.weight > threshold:
                centroid += (mesh.matrix_world @ vertex.co) * membership.weight
                total += membership.weight
                break
    return centroid / total if total else None


def fmt(value):
    if isinstance(value, Vector):
        return "({:.5f},{:.5f},{:.5f})".format(*value)
    return str(value)


for label, kind, filename in VARIANTS:
    mesh, armature = load(kind, filename)
    world_corners = [mesh.matrix_world @ Vector(corner) for corner in mesh.bound_box]
    low = Vector((min(v.x for v in world_corners), min(v.y for v in world_corners), min(v.z for v in world_corners)))
    high = Vector((max(v.x for v in world_corners), max(v.y for v in world_corners), max(v.z for v in world_corners)))
    print("VARIANT|{}|verts={}|polys={}|groups={}|bones={}".format(
        label, len(mesh.data.vertices), len(mesh.data.polygons),
        len(mesh.vertex_groups), len(armature.data.bones)))
    print("OBJECT|{}|mesh_matrix={}|arm_matrix={}".format(
        label, tuple(round(x, 6) for row in mesh.matrix_world for x in row),
        tuple(round(x, 6) for row in armature.matrix_world for x in row)))
    print("BOUNDS|{}|low={}|high={}|size={}".format(label, fmt(low), fmt(high), fmt(high - low)))
    for name in ("lowerarm_r", "hand_r", "calf_r", "foot_r"):
        bone = armature.data.bones.get(name)
        head = armature.matrix_world @ bone.head_local if bone else None
        centroid = weighted_centroid(mesh, name)
        distance = (centroid - head).length if centroid is not None and head is not None else None
        print("LANDMARK|{}|{}|bone={}|centroid={}|distance={}".format(
            label, name, fmt(head), fmt(centroid),
            "{:.5f}".format(distance) if distance is not None else "None"))
    print("GROUPS|{}|lowerarm={}|calf={}".format(
        label,
        ",".join(group.name for group in mesh.vertex_groups if "lowerarm" in group.name),
        ",".join(group.name for group in mesh.vertex_groups if "calf" in group.name)))

print("REST_GEOMETRY_DIAGNOSTIC_DONE")
