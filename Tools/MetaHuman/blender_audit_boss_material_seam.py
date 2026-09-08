"""Measure geometry and normal continuity at the Boss Body/Face material seam."""

import json
import math
from pathlib import Path

import bpy
from mathutils.kdtree import KDTree


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
BLEND = (
    PROJECT
    / "Saved"
    / "BlenderExchange"
    / "BossUEFN"
    / "Boss_UEFN_ExportClean.blend"
)
OUTPUT = (
    PROJECT
    / "Saved"
    / "BlenderExchange"
    / "BossUEFN"
    / "Boss_UEFN_MaterialSeamAudit.json"
)
BODY_MATERIAL = 0
FACE_MATERIAL = 7


def material_vertices(mesh, material_index):
    return {
        vertex
        for polygon in mesh.data.polygons
        if polygon.material_index == material_index
        for vertex in polygon.vertices
    }


def main():
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    mesh = bpy.data.objects["SKM_Boss_UEFN"]
    body_vertices = material_vertices(mesh, BODY_MATERIAL)
    face_vertices = material_vertices(mesh, FACE_MATERIAL)
    tree = KDTree(len(face_vertices))
    for vertex_index in face_vertices:
        tree.insert(mesh.data.vertices[vertex_index].co, vertex_index)
    tree.balance()

    nearest = []
    for body_index in body_vertices:
        body_vertex = mesh.data.vertices[body_index]
        _position, face_index, distance = tree.find(body_vertex.co)
        face_vertex = mesh.data.vertices[face_index]
        dot = max(-1.0, min(1.0, body_vertex.normal.dot(face_vertex.normal)))
        nearest.append(
            {
                "body_vertex": body_index,
                "face_vertex": face_index,
                "distance_local_m": distance,
                "normal_angle_deg": math.degrees(math.acos(dot)),
                "body_position": list(body_vertex.co),
                "face_position": list(face_vertex.co),
            }
        )

    # The clean export scene stores mesh-local coordinates in centimeters.
    seam = [pair for pair in nearest if pair["distance_local_m"] <= 1.0]
    seam.sort(key=lambda pair: pair["distance_local_m"])
    reverse_tree = KDTree(len(body_vertices))
    for vertex_index in body_vertices:
        reverse_tree.insert(mesh.data.vertices[vertex_index].co, vertex_index)
    reverse_tree.balance()
    mutual_pairs = []
    for pair in seam:
        _position, reverse_body_index, _distance = reverse_tree.find(
            mesh.data.vertices[pair["face_vertex"]].co
        )
        if reverse_body_index == pair["body_vertex"]:
            mutual_pairs.append(pair)

    group_names = {group.index: group.name for group in mesh.vertex_groups}

    def weights(vertex_index):
        return {
            group_names[item.group]: item.weight
            for item in mesh.data.vertices[vertex_index].groups
            if item.weight > 1.0e-8
        }

    def weight_l1(left, right):
        return sum(
            abs(left.get(name, 0.0) - right.get(name, 0.0))
            for name in set(left) | set(right)
        )

    for pair in mutual_pairs:
        body_weights = weights(pair["body_vertex"])
        face_weights = weights(pair["face_vertex"])
        pair["body_weights"] = body_weights
        pair["face_weights"] = face_weights
        pair["weight_l1"] = weight_l1(body_weights, face_weights)

    report = {
        "blend": str(BLEND),
        "body_vertices": len(body_vertices),
        "face_vertices": len(face_vertices),
        "near_pair_counts": {
            str(threshold): sum(
                pair["distance_local_m"] <= threshold for pair in nearest
            )
            for threshold in (0.001, 0.01, 0.05, 0.1, 0.2, 0.5, 1.0)
        },
        "seam_pair_count": len(seam),
        "mutual_seam_pair_count": len(mutual_pairs),
        "mutual_unique_body_vertices": len(
            {pair["body_vertex"] for pair in mutual_pairs}
        ),
        "mutual_unique_face_vertices": len(
            {pair["face_vertex"] for pair in mutual_pairs}
        ),
        "mutual_weight_l1": {
            "maximum": max(
                (pair["weight_l1"] for pair in mutual_pairs), default=0.0
            ),
            "mean": (
                sum(pair["weight_l1"] for pair in mutual_pairs)
                / len(mutual_pairs)
                if mutual_pairs
                else 0.0
            ),
        },
        "seam_maximum_distance_local_m": max(
            (pair["distance_local_m"] for pair in seam), default=0.0
        ),
        "seam_normal_angle_deg": {
            "maximum": max(
                (pair["normal_angle_deg"] for pair in seam), default=0.0
            ),
            "mean": (
                sum(pair["normal_angle_deg"] for pair in seam) / len(seam)
                if seam
                else 0.0
            ),
            "over_5_deg": sum(
                pair["normal_angle_deg"] > 5.0 for pair in seam
            ),
            "over_15_deg": sum(
                pair["normal_angle_deg"] > 15.0 for pair in seam
            ),
        },
        "worst_normal_pairs": sorted(
            seam, key=lambda pair: pair["normal_angle_deg"], reverse=True
        )[:30],
        "mutual_pairs": mutual_pairs,
    }
    OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("BOSS_MATERIAL_SEAM_AUDIT=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
