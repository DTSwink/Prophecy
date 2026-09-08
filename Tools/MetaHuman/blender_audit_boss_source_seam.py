"""Compare the Boss collar before and after its working-rig deformation."""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
OUTPUT = (
    PROJECT
    / "Saved"
    / "BlenderExchange"
    / "BossUEFN"
    / "Boss_SourceSeamAudit.json"
)
sys.path.insert(0, str(PROJECT / "Tools" / "MetaHuman"))
import blender_prepare_boss_uefn_export as pipeline


def angle_degrees(left, right):
    return math.degrees(
        math.acos(max(-1.0, min(1.0, left.dot(right))))
    )


def metrics(obj, data):
    matrix = obj.matrix_world
    normal_matrix = matrix.to_3x3().inverted().transposed()
    body = {
        vertex
        for polygon in data.polygons
        if polygon.material_index == 0
        for vertex in polygon.vertices
    }
    face = {
        vertex
        for polygon in data.polygons
        if polygon.material_index == 7
        for vertex in polygon.vertices
    }
    face_tree = KDTree(len(face))
    for index in face:
        face_tree.insert(matrix @ data.vertices[index].co, index)
    face_tree.balance()
    body_tree = KDTree(len(body))
    for index in body:
        body_tree.insert(matrix @ data.vertices[index].co, index)
    body_tree.balance()
    polygons_by_vertex = [[] for _vertex in data.vertices]
    for polygon in data.polygons:
        for vertex in polygon.vertices:
            polygons_by_vertex[vertex].append(polygon.index)

    def geometric_normal(index, material):
        result = Vector((0.0, 0.0, 0.0))
        for polygon_index in polygons_by_vertex[index]:
            polygon = data.polygons[polygon_index]
            if polygon.material_index == material:
                result += (
                    normal_matrix @ polygon.normal
                ).normalized() * max(polygon.area, 1.0e-12)
        return result.normalized()

    pairs = []
    for body_index in body:
        _position, face_index, distance = face_tree.find(
            matrix @ data.vertices[body_index].co
        )
        if distance > 0.02:
            continue
        _position, reverse_body, _reverse_distance = body_tree.find(
            matrix @ data.vertices[face_index].co
        )
        if reverse_body != body_index:
            continue
        pairs.append(
            {
                "body": body_index,
                "face": face_index,
                "distance_m": distance,
                "angle_deg": angle_degrees(
                    geometric_normal(body_index, 0),
                    geometric_normal(face_index, 7),
                ),
            }
        )
    distances = [item["distance_m"] for item in pairs]
    angles = [item["angle_deg"] for item in pairs]
    return {
        "pairs": len(pairs),
        "distance_m": {
            "maximum": max(distances, default=0.0),
            "mean": sum(distances) / len(distances) if distances else 0.0,
        },
        "geometric_angle_deg": {
            "maximum": max(angles, default=0.0),
            "mean": sum(angles) / len(angles) if angles else 0.0,
        },
        "worst": sorted(pairs, key=lambda item: item["angle_deg"], reverse=True)[
            :8
        ],
    }


boss = bpy.data.objects["boss"]
pipeline.repair_material_regions(boss)
boss.data.update()
raw = metrics(boss, boss.data)
depsgraph = bpy.context.evaluated_depsgraph_get()
evaluated = boss.evaluated_get(depsgraph)
evaluated_mesh = evaluated.to_mesh()
try:
    evaluated_mesh.update()
    deformed = metrics(evaluated, evaluated_mesh)
finally:
    evaluated.to_mesh_clear()

report = {"raw": raw, "evaluated": deformed}
OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
print("BOSS_SOURCE_SEAM_AUDIT=" + json.dumps(report))
