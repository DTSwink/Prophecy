"""Measure the physical Body/Face collar angle in Epic's original Boss meshes."""

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
REFERENCE = (
    PROJECT
    / "Saved"
    / "BlenderExchange"
    / "FourCharacters"
    / "BP_boss_Meshes.blend"
)
OUTPUT = (
    PROJECT
    / "Saved"
    / "BlenderExchange"
    / "BossUEFN"
    / "Boss_OriginalGeometricSeamAudit.json"
)


def boundary_vertices(obj):
    edge_faces = [0] * len(obj.data.edges)
    edge_lookup = {
        tuple(sorted(edge.vertices)): edge.index for edge in obj.data.edges
    }
    for polygon in obj.data.polygons:
        vertices = list(polygon.vertices)
        for offset, first in enumerate(vertices):
            second = vertices[(offset + 1) % len(vertices)]
            edge_faces[edge_lookup[tuple(sorted((first, second)))]] += 1
    return {
        vertex
        for edge in obj.data.edges
        if edge_faces[edge.index] == 1
        for vertex in edge.vertices
    }


def polygons_by_vertex(obj):
    result = [[] for _vertex in obj.data.vertices]
    for polygon in obj.data.polygons:
        for vertex in polygon.vertices:
            result[vertex].append(polygon.index)
    return result


def world_position(obj, index):
    return obj.matrix_world @ obj.data.vertices[index].co


def geometric_normal(obj, polygon_indices):
    normal_matrix = obj.matrix_world.to_3x3().inverted().transposed()
    result = Vector((0.0, 0.0, 0.0))
    total = 0.0
    for index in polygon_indices:
        polygon = obj.data.polygons[index]
        area = max(polygon.area, 1.0e-12)
        result += (normal_matrix @ polygon.normal).normalized() * area
        total += area
    return (result / total).normalized()


def angle_degrees(left, right):
    return math.degrees(
        math.acos(
            max(-1.0, min(1.0, left.normalized().dot(right.normalized())))
        )
    )


bpy.ops.wm.open_mainfile(filepath=str(REFERENCE))
body = bpy.data.objects["BP_boss_Body_Mesh"]
face = bpy.data.objects["BP_boss_Face_Mesh"]
body.data.update()
face.data.update()

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
body_polygons = polygons_by_vertex(body)
face_polygons = polygons_by_vertex(face)

pairs = []
for body_index in body_boundary:
    _position, face_index, distance = face_tree.find(
        world_position(body, body_index)
    )
    if distance > 0.01:
        continue
    _position, reverse_body, _reverse_distance = body_tree.find(
        world_position(face, face_index)
    )
    if reverse_body != body_index:
        continue
    body_normal = geometric_normal(body, body_polygons[body_index])
    face_normal = geometric_normal(face, face_polygons[face_index])
    pairs.append(
        {
            "body_vertex": body_index,
            "face_vertex": face_index,
            "distance_m": distance,
            "geometric_normal_angle_deg": angle_degrees(
                body_normal, face_normal
            ),
            "body_position_m": list(world_position(body, body_index)),
            "face_position_m": list(world_position(face, face_index)),
        }
    )

angles = [pair["geometric_normal_angle_deg"] for pair in pairs]
report = {
    "pair_count": len(pairs),
    "maximum_distance_m": max(
        (pair["distance_m"] for pair in pairs), default=0.0
    ),
    "geometric_normal_angle_deg": {
        "minimum": min(angles, default=0.0),
        "maximum": max(angles, default=0.0),
        "mean": sum(angles) / len(angles) if angles else 0.0,
    },
    "worst": sorted(
        pairs,
        key=lambda item: item["geometric_normal_angle_deg"],
        reverse=True,
    )[:12],
}
OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
print("BOSS_ORIGINAL_GEOMETRIC_SEAM_AUDIT=" + json.dumps(report))
