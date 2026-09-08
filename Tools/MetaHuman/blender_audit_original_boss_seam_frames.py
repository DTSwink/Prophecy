"""Measure authored Body/Face normal and tangent frames from the UE exports."""

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
BODY_FBX = PROJECT / "Saved/BlenderExchange/FourCharacters/BP_boss_Body.fbx"
FACE_FBX = PROJECT / "Saved/BlenderExchange/FourCharacters/BP_boss_Face.fbx"
OUTPUT = (
    PROJECT
    / "Saved/BlenderExchange/BossUEFN/Boss_OriginalSeamFrameAudit.json"
)


def angle(left, right):
    dot = max(-1.0, min(1.0, left.normalized().dot(right.normalized())))
    return math.degrees(math.acos(dot))


def average(values):
    result = Vector((0.0, 0.0, 0.0))
    for value in values:
        result += value
    result.normalize()
    return result


def boundary_vertices(mesh):
    edge_faces = {edge.index: 0 for edge in mesh.data.edges}
    for polygon in mesh.data.polygons:
        for edge_index in polygon.edge_keys:
            pass
    # Mesh edges expose is_loose but not face count; count polygon edge keys.
    key_to_edge = {
        tuple(sorted((edge.vertices[0], edge.vertices[1]))): edge.index
        for edge in mesh.data.edges
    }
    for polygon in mesh.data.polygons:
        for key in polygon.edge_keys:
            edge_faces[key_to_edge[tuple(sorted(key))]] += 1
    return {
        vertex
        for edge in mesh.data.edges
        if edge_faces[edge.index] == 1
        for vertex in edge.vertices
    }


def world_position(obj, vertex_index):
    return obj.matrix_world @ obj.data.vertices[vertex_index].co


def loop_frames(obj, vertex_index):
    obj.data.calc_tangents()
    normal_matrix = obj.matrix_world.to_3x3().inverted().transposed()
    tangent_matrix = obj.matrix_world.to_3x3()
    normals = []
    tangents = []
    for loop in obj.data.loops:
        if loop.vertex_index != vertex_index:
            continue
        normals.append(
            (normal_matrix @ obj.data.corner_normals[loop.index].vector).normalized()
        )
        tangents.append((tangent_matrix @ loop.tangent).normalized())
    return average(normals), average(tangents)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for path in (BODY_FBX, FACE_FBX):
        bpy.ops.import_scene.fbx(
            filepath=str(path),
            use_custom_normals=True,
            use_anim=False,
            ignore_leaf_bones=False,
            force_connect_children=False,
            automatic_bone_orientation=False,
            axis_forward="-Z",
            axis_up="Y",
        )
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    if len(meshes) != 2:
        raise RuntimeError("Expected Body and Face mesh")
    body = max(meshes, key=lambda obj: len(obj.data.vertices))
    face = min(meshes, key=lambda obj: len(obj.data.vertices))
    body_boundary = boundary_vertices(body)
    face_boundary = boundary_vertices(face)
    face_tree = KDTree(len(face_boundary))
    for index in face_boundary:
        face_tree.insert(world_position(face, index), index)
    face_tree.balance()
    body_tree = KDTree(len(body_boundary))
    for index in body_boundary:
        body_tree.insert(world_position(body, index), index)
    body_tree.balance()

    pairs = []
    for body_index in body_boundary:
        _position, face_index, distance = face_tree.find(
            world_position(body, body_index)
        )
        if distance > 0.002:
            continue
        _position, reverse_body, _distance = body_tree.find(
            world_position(face, face_index)
        )
        if reverse_body != body_index:
            continue
        body_normal, body_tangent = loop_frames(body, body_index)
        face_normal, face_tangent = loop_frames(face, face_index)
        pairs.append(
            {
                "body_vertex": body_index,
                "face_vertex": face_index,
                "distance_m": distance,
                "normal_angle_deg": angle(body_normal, face_normal),
                "tangent_angle_deg": angle(body_tangent, face_tangent),
            }
        )
    report = {
        "pair_count": len(pairs),
        "maximum_distance_m": max((p["distance_m"] for p in pairs), default=0.0),
        "normal_angle_deg": {
            "maximum": max((p["normal_angle_deg"] for p in pairs), default=0.0),
            "mean": sum(p["normal_angle_deg"] for p in pairs) / len(pairs),
        },
        "tangent_angle_deg": {
            "maximum": max((p["tangent_angle_deg"] for p in pairs), default=0.0),
            "mean": sum(p["tangent_angle_deg"] for p in pairs) / len(pairs),
        },
        "pairs": pairs,
    }
    OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("BOSS_ORIGINAL_SEAM_FRAME_AUDIT=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
