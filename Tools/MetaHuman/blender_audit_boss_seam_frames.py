"""Audit normal/tangent continuity at the Boss Body/Face material boundary."""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
BLEND = PROJECT / "Saved/BlenderExchange/BossUEFN/Boss_UEFN_ExportClean.blend"
FBX = PROJECT / "Saved/BlenderExchange/BossUEFN/SKM_Boss_UEFN.fbx"
OUTPUT = PROJECT / "Saved/BlenderExchange/BossUEFN/Boss_SeamFrameAudit.json"


def angle(left, right):
    if left.length_squared == 0.0 or right.length_squared == 0.0:
        return 0.0
    dot = max(-1.0, min(1.0, left.normalized().dot(right.normalized())))
    return math.degrees(math.acos(dot))


def average(vectors):
    value = Vector((0.0, 0.0, 0.0))
    for vector in vectors:
        value += vector
    if value.length_squared:
        value.normalize()
    return value


def frame_report(mesh):
    mesh.data.calc_tangents()
    scale = 10000.0
    groups = {}
    for polygon in mesh.data.polygons:
        if polygon.material_index not in (0, 7):
            continue
        label = "body" if polygon.material_index == 0 else "face"
        for loop_index in polygon.loop_indices:
            loop = mesh.data.loops[loop_index]
            position = mesh.data.vertices[loop.vertex_index].co
            key = tuple(round(value * scale) for value in position)
            group = groups.setdefault(
                key, {"body_normals": [], "face_normals": [],
                      "body_tangents": [], "face_tangents": []}
            )
            group[label + "_normals"].append(
                mesh.data.corner_normals[loop_index].vector.copy()
            )
            group[label + "_tangents"].append(loop.tangent.copy())
    seam = []
    for key, group in groups.items():
        if not group["body_normals"] or not group["face_normals"]:
            continue
        body_normal = average(group["body_normals"])
        face_normal = average(group["face_normals"])
        body_tangent = average(group["body_tangents"])
        face_tangent = average(group["face_tangents"])
        seam.append(
            {
                "position_key": key,
                "normal_angle_deg": angle(body_normal, face_normal),
                "tangent_angle_deg": angle(body_tangent, face_tangent),
                "body_loops": len(group["body_normals"]),
                "face_loops": len(group["face_normals"]),
            }
        )
    return {
        "seam_positions": len(seam),
        "normal_angle_deg": {
            "maximum": max((item["normal_angle_deg"] for item in seam), default=0.0),
            "mean": (
                sum(item["normal_angle_deg"] for item in seam) / len(seam)
                if seam else 0.0
            ),
        },
        "tangent_angle_deg": {
            "maximum": max((item["tangent_angle_deg"] for item in seam), default=0.0),
            "mean": (
                sum(item["tangent_angle_deg"] for item in seam) / len(seam)
                if seam else 0.0
            ),
        },
        "worst": sorted(
            seam,
            key=lambda item: max(
                item["normal_angle_deg"], item["tangent_angle_deg"]
            ),
            reverse=True,
        )[:20],
    }


def main():
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    blend_mesh = bpy.data.objects["SKM_Boss_UEFN"]
    report = {"blend": frame_report(blend_mesh)}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(
        filepath=str(FBX),
        use_custom_normals=True,
        use_anim=False,
        ignore_leaf_bones=False,
        force_connect_children=False,
        automatic_bone_orientation=False,
        axis_forward="-Z",
        axis_up="Y",
    )
    fbx_meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    if len(fbx_meshes) != 1:
        raise RuntimeError("Unexpected FBX mesh count")
    report["fbx_roundtrip"] = frame_report(fbx_meshes[0])
    OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("BOSS_SEAM_FRAME_AUDIT=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
