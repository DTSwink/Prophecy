"""Measure the physical crease at the welded Boss Body/Face collar.

Run with Boss_UEFN_ExportClean.blend open.  This deliberately uses polygon
geometry normals rather than authored/custom split normals so it can
distinguish a real surface-angle discontinuity from a shading-only seam.
"""

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
OUTPUT = (
    PROJECT
    / "Saved"
    / "BlenderExchange"
    / "BossUEFN"
    / "Boss_GeometricSeamAudit.json"
)


def angle_degrees(left, right):
    left = left.normalized()
    right = right.normalized()
    return math.degrees(
        math.acos(max(-1.0, min(1.0, left.dot(right))))
    )


def averaged_polygon_normal(mesh, polygon_indices):
    result = Vector((0.0, 0.0, 0.0))
    total_area = 0.0
    for index in polygon_indices:
        polygon = mesh.polygons[index]
        weight = max(polygon.area, 1.0e-12)
        result += polygon.normal * weight
        total_area += weight
    if total_area:
        result /= total_area
    return result.normalized()


def stats(values):
    return {
        "count": len(values),
        "minimum": min(values, default=0.0),
        "maximum": max(values, default=0.0),
        "mean": sum(values) / len(values) if values else 0.0,
    }


mesh_object = bpy.data.objects.get("SKM_Boss_UEFN")
if mesh_object is None or mesh_object.type != "MESH":
    raise RuntimeError("SKM_Boss_UEFN mesh is missing")

mesh = mesh_object.data
mesh.update()

polygons_by_vertex = [[] for _vertex in mesh.vertices]
for polygon in mesh.polygons:
    for vertex_index in polygon.vertices:
        polygons_by_vertex[vertex_index].append(polygon.index)

body_vertices = {
    vertex_index
    for polygon in mesh.polygons
    if polygon.material_index == 0
    for vertex_index in polygon.vertices
}
face_vertices = {
    vertex_index
    for polygon in mesh.polygons
    if polygon.material_index == 7
    for vertex_index in polygon.vertices
}
shared_vertices = sorted(body_vertices & face_vertices)

vertex_angles = []
vertex_details = []
for vertex_index in shared_vertices:
    body_polygons = [
        index
        for index in polygons_by_vertex[vertex_index]
        if mesh.polygons[index].material_index == 0
    ]
    face_polygons = [
        index
        for index in polygons_by_vertex[vertex_index]
        if mesh.polygons[index].material_index == 7
    ]
    body_normal = averaged_polygon_normal(mesh, body_polygons)
    face_normal = averaged_polygon_normal(mesh, face_polygons)
    angle = angle_degrees(body_normal, face_normal)
    vertex_angles.append(angle)
    vertex_details.append(
        {
            "vertex": vertex_index,
            "angle_deg": angle,
            "position_cm": list(mesh.vertices[vertex_index].co),
            "body_polygons": body_polygons,
            "face_polygons": face_polygons,
        }
    )

# Blender's mesh edge table plus polygon loop edges lets us locate the actual
# material boundary and measure the dihedral between the adjacent surface
# triangles on either side.
polygons_by_edge = [[] for _edge in mesh.edges]
for polygon in mesh.polygons:
    for edge_index in polygon.edge_keys:
        pass
edge_lookup = {
    tuple(sorted(edge.vertices)): edge.index for edge in mesh.edges
}
for polygon in mesh.polygons:
    vertices = list(polygon.vertices)
    for offset, first in enumerate(vertices):
        second = vertices[(offset + 1) % len(vertices)]
        polygons_by_edge[edge_lookup[tuple(sorted((first, second)))]].append(
            polygon.index
        )

boundary_edges = []
edge_angles = []
for edge in mesh.edges:
    if not set(edge.vertices).issubset(shared_vertices):
        continue
    linked = polygons_by_edge[edge.index]
    body_polygons = [
        index for index in linked if mesh.polygons[index].material_index == 0
    ]
    face_polygons = [
        index for index in linked if mesh.polygons[index].material_index == 7
    ]
    if not body_polygons or not face_polygons:
        continue
    body_normal = averaged_polygon_normal(mesh, body_polygons)
    face_normal = averaged_polygon_normal(mesh, face_polygons)
    angle = angle_degrees(body_normal, face_normal)
    edge_angles.append(angle)
    boundary_edges.append(
        {
            "edge": edge.index,
            "vertices": list(edge.vertices),
            "angle_deg": angle,
            "body_polygons": body_polygons,
            "face_polygons": face_polygons,
        }
    )

report = {
    "blend_file": bpy.data.filepath,
    "vertex_count": len(mesh.vertices),
    "polygon_count": len(mesh.polygons),
    "shared_boundary_vertices": len(shared_vertices),
    "boundary_edges": len(boundary_edges),
    "vertex_geometric_normal_angle_deg": stats(vertex_angles),
    "edge_dihedral_angle_deg": stats(edge_angles),
    "worst_vertices": sorted(
        vertex_details, key=lambda item: item["angle_deg"], reverse=True
    )[:12],
    "worst_edges": sorted(
        boundary_edges, key=lambda item: item["angle_deg"], reverse=True
    )[:12],
}
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
print("BOSS_GEOMETRIC_SEAM_AUDIT=" + json.dumps(report, sort_keys=True))
