"""Experiment: replace Boss hand weights from the fitted UEFN reference mesh.

The source file is never saved. The transfer is evaluated in the fitted pose
already stored in bossfinalsave.blend, is constrained to the same side/finger
family, and writes separate experiment outputs for visual/metric validation.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blender_prepare_boss_uefn_export_driver as driver
from blender_transfer_boss_weights import (
    SurfaceWeightSampler,
    body_vertex_weights,
    evaluated_world_mesh,
    normalize,
)


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
OUT_DIR = PROJECT / "Saved" / "BlenderExchange" / "BossUEFN"
OUTPUT_BLEND = OUT_DIR / "Boss_UEFN_ExportClean_HandTemplate.blend"
OUTPUT_FBX = OUT_DIR / "SKM_Boss_UEFN_HandTemplate.fbx"
OUTPUT_AUDIT = OUT_DIR / "Boss_UEFN_HandTemplateExportAudit.json"
FAMILIES = ("thumb", "index", "middle", "ring", "pinky")
MAX_SAMPLE_DISTANCE_M = 0.03


def family_names(family, side):
    names = {
        f"{family}_{number:02d}_{side}" for number in (1, 2, 3)
    }
    if family != "thumb":
        names.add(f"{family}_metacarpal_{side}")
    return names


def side_names(side):
    result = {f"hand_{side}"}
    for family in FAMILIES:
        result.update(family_names(family, side))
    return result


def total(weights, names):
    return sum(weights.get(name, 0.0) for name in names)


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    position = fraction * (len(ordered) - 1)
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return ordered[low]
    blend = position - low
    return ordered[low] * (1.0 - blend) + ordered[high] * blend


def triangle_samplers(reference, valid_bones):
    vertices, triangles = evaluated_world_mesh(reference)
    weights = body_vertex_weights(reference, valid_bones)
    samplers = {}

    for side in ("l", "r"):
        current_side_names = side_names(side)
        side_triangles = []
        family_triangles = {family: [] for family in FAMILIES}
        for triangle in triangles:
            side_score = sum(
                total(weights[index], current_side_names)
                for index in triangle
            ) / 3.0
            if side_score < 0.15:
                continue
            side_triangles.append(triangle)
            scores = {
                family: sum(
                    total(weights[index], family_names(family, side))
                    for index in triangle
                )
                / 3.0
                for family in FAMILIES
            }
            winner = max(scores, key=scores.get)
            if scores[winner] >= 0.10:
                family_triangles[winner].append(triangle)

        if not side_triangles:
            raise RuntimeError(f"No UEFN reference hand triangles for {side}")
        samplers[(side, None)] = SurfaceWeightSampler(
            vertices, side_triangles, weights
        )
        for family, selected in family_triangles.items():
            if not selected:
                raise RuntimeError(
                    f"No UEFN reference triangles for {family}_{side}"
                )
            samplers[(side, family)] = SurfaceWeightSampler(
                vertices, selected, weights
            )
    return samplers


def write_all_weights(mesh, all_weights, valid_bones):
    mesh.vertex_groups.clear()
    groups = {
        name: mesh.vertex_groups.new(name=name)
        for name in sorted(valid_bones)
    }
    assignments = defaultdict(list)
    for vertex_index, weights in enumerate(all_weights):
        for name, weight in weights.items():
            if name in groups and weight > 0.0:
                assignments[name].append((vertex_index, weight))
    for name, values in assignments.items():
        group = groups[name]
        for vertex_index, weight in values:
            group.add([vertex_index], weight, "REPLACE")


def main():
    if Path(bpy.data.filepath).resolve() != driver.SOURCE.resolve():
        raise RuntimeError(f"Unexpected source: {bpy.data.filepath}")
    bpy.context.scene.frame_set(0)
    boss = bpy.data.objects.get(driver.MESH_NAME)
    reference = bpy.data.objects.get("UEFN_WORKING_REFERENCE_MESH")
    rig = bpy.data.objects.get(driver.BOUND_RIG_NAME)
    if boss is None or boss.type != "MESH":
        raise RuntimeError("Boss mesh missing")
    if reference is None or reference.type != "MESH":
        raise RuntimeError("Fitted UEFN reference mesh missing")
    if rig is None or rig.type != "ARMATURE":
        raise RuntimeError("Boss bind rig missing")

    valid_bones = {bone.name for bone in rig.data.bones}
    original = driver.normalized_vertex_weights(boss, valid_bones)
    replacement = [dict(weights) for weights in original]
    samplers = triangle_samplers(reference, valid_bones)
    boss_positions = driver.evaluated_world_positions(boss)

    distances = []
    counts = defaultdict(int)
    skipped_distance = 0
    for index, (position, weights) in enumerate(
        zip(boss_positions, original)
    ):
        side_scores = {
            side: total(weights, side_names(side)) for side in ("l", "r")
        }
        side = max(side_scores, key=side_scores.get)
        if side_scores[side] < 0.20:
            continue
        family_scores = {
            family: total(weights, family_names(family, side))
            for family in FAMILIES
        }
        family = max(family_scores, key=family_scores.get)
        if family_scores[family] < 0.20:
            family = None
        sampled, distance = samplers[(side, family)].sample(position)
        if not sampled or distance > MAX_SAMPLE_DISTANCE_M:
            skipped_distance += 1
            continue
        replacement[index] = normalize(sampled)
        distances.append(distance)
        counts[f"{side}:{family or 'palm'}"] += 1

    if len(distances) < 500:
        raise RuntimeError(
            f"Implausibly few hand vertices transferred: {len(distances)}"
        )
    write_all_weights(boss, replacement, valid_bones)

    transfer_report = {
        "method": (
            "nearest_face_barycentric_from_fitted_uefn_reference_mesh_"
            "constrained_by_side_and_finger_family"
        ),
        "source_reference": reference.name,
        "transferred_vertices": len(distances),
        "skipped_for_distance": skipped_distance,
        "maximum_allowed_distance_m": MAX_SAMPLE_DISTANCE_M,
        "distance_m": {
            "minimum": min(distances),
            "median": percentile(distances, 0.50),
            "p95": percentile(distances, 0.95),
            "maximum": max(distances),
        },
        "counts": dict(sorted(counts.items())),
        "source_file_saved_or_modified": False,
    }

    driver.OUTPUT_BLEND = OUTPUT_BLEND
    driver.OUTPUT_FBX = OUTPUT_FBX
    driver.OUTPUT_AUDIT = OUTPUT_AUDIT
    driver.main()
    audit = json.loads(OUTPUT_AUDIT.read_text(encoding="utf-8"))
    audit["hand_template_transfer"] = transfer_report
    OUTPUT_AUDIT.write_text(
        json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(
        "BOSS_UEFN_HAND_TEMPLATE_EXPERIMENT="
        + json.dumps(
            {
                "blend": str(OUTPUT_BLEND),
                "fbx": str(OUTPUT_FBX),
                "audit": str(OUTPUT_AUDIT),
                "transfer": transfer_report,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
