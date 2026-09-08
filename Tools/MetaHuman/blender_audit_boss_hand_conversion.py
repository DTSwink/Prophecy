"""Audit and render Boss hand deformation from fitted bind to UEFN rest.

This is diagnostic only. It opens the current immutable source and the
generated clean file, compares matching topology edge lengths and vertex
weights, and renders close hand views with a clean joint-head skeleton.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


PROJECT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy")
SOURCE = Path(r"C:\Users\singerie\Documents\Blender\bossfinalsave.blend")
CLEAN = Path(
    os.environ.get(
        "BOSS_HAND_AUDIT_CLEAN",
        str(
            PROJECT
            / "Saved"
            / "BlenderExchange"
            / "BossUEFN"
            / "Boss_UEFN_ExportClean.blend"
        ),
    )
)
MANUAL_RIG = (
    PROJECT
    / "Saved"
    / "BlenderExchange"
    / "ManualRig_CleanWorkingRig_with_NativeExportRig.blend"
)
AUDIT_TAG = os.environ.get("BOSS_HAND_AUDIT_TAG", "Current")
OUT_DIR = (
    PROJECT
    / "Saved"
    / "BlenderShots"
    / "BossUEFN"
    / "HandAudit"
    / AUDIT_TAG
)
AUDIT = Path(
    os.environ.get(
        "BOSS_HAND_AUDIT_JSON",
        str(
            PROJECT
            / "Saved"
            / "BlenderExchange"
            / "BossUEFN"
            / f"Boss_UEFN_HandConversionAudit_{AUDIT_TAG}.json"
        ),
    )
)

FAMILIES = ("thumb", "index", "middle", "ring", "pinky")


def evaluated_world_positions(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        return [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
    finally:
        evaluated.to_mesh_clear()


def find_source_objects():
    mesh = bpy.data.objects.get("boss")
    rig = bpy.data.objects.get("UEFN_WORKING_CLEAN_RIG.001")
    if mesh is None or mesh.type != "MESH":
        raise RuntimeError("Source Boss mesh not found")
    if rig is None or rig.type != "ARMATURE":
        raise RuntimeError("Source Boss bind rig not found")
    return mesh, rig


def find_clean_objects():
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    rigs = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    if len(meshes) != 1 or len(rigs) != 1:
        raise RuntimeError("Expected exactly one clean mesh and armature")
    return meshes[0], rigs[0]


def vertex_weights(mesh):
    names = {group.index: group.name for group in mesh.vertex_groups}
    return [
        {
            names[item.group]: float(item.weight)
            for item in vertex.groups
            if item.group in names and item.weight > 1.0e-8
        }
        for vertex in mesh.data.vertices
    ]


def finger_family(name):
    for family in FAMILIES:
        if name.startswith(family + "_"):
            return family
    return None


def side_hand_names(side):
    suffix = "_" + side
    return {
        name
        for family in FAMILIES
        for name in (
            f"{family}_metacarpal{suffix}",
            f"{family}_01{suffix}",
            f"{family}_02{suffix}",
            f"{family}_03{suffix}",
        )
    } | {f"hand_{side}"}


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


def concise_weights(weights):
    return [
        [name, round(weight, 5)]
        for name, weight in sorted(
            weights.items(), key=lambda item: item[1], reverse=True
        )[:8]
    ]


def group_total(weights, names):
    return sum(weights.get(name, 0.0) for name in names)


def analyze_edges(edges, source_positions, target_positions, weights):
    report = {"sides": {}, "global_worst_edges": []}
    all_bad = []
    for side in ("l", "r"):
        hand_names = side_hand_names(side)
        side_vertices = {
            index
            for index, item in enumerate(weights)
            if group_total(item, hand_names) >= 0.50
        }
        side_report = {"vertex_count": len(side_vertices), "families": {}}
        for family in FAMILIES:
            family_names = {
                name
                for name in hand_names
                if finger_family(name) == family
            }
            ratios = []
            records = []
            for first, second in edges:
                if first not in side_vertices or second not in side_vertices:
                    continue
                if (
                    group_total(weights[first], family_names) < 0.50
                    or group_total(weights[second], family_names) < 0.50
                ):
                    continue
                before = (
                    source_positions[first] - source_positions[second]
                ).length
                after = (
                    target_positions[first] - target_positions[second]
                ).length
                if before <= 1.0e-8:
                    continue
                ratio = after / before
                ratios.append(ratio)
                records.append((ratio, first, second, before, after))
                all_bad.append(
                    (abs(math.log(max(ratio, 1.0e-12))), side, family)
                    + records[-1]
                )
            ordered = sorted(records)
            side_report["families"][family] = {
                "edge_count": len(ratios),
                "minimum_ratio": min(ratios) if ratios else None,
                "p01_ratio": percentile(ratios, 0.01),
                "p05_ratio": percentile(ratios, 0.05),
                "median_ratio": percentile(ratios, 0.50),
                "p95_ratio": percentile(ratios, 0.95),
                "p99_ratio": percentile(ratios, 0.99),
                "maximum_ratio": max(ratios) if ratios else None,
                "compressed_below_0_70": sum(
                    ratio < 0.70 for ratio in ratios
                ),
                "stretched_above_1_30": sum(
                    ratio > 1.30 for ratio in ratios
                ),
                "worst_compressed": [
                    {
                        "ratio": ratio,
                        "vertices": [first, second],
                        "source_length_m": before,
                        "target_length_m": after,
                        "weights": [
                            concise_weights(weights[first]),
                            concise_weights(weights[second]),
                        ],
                    }
                    for ratio, first, second, before, after in ordered[:5]
                ],
                "worst_stretched": [
                    {
                        "ratio": ratio,
                        "vertices": [first, second],
                        "source_length_m": before,
                        "target_length_m": after,
                        "weights": [
                            concise_weights(weights[first]),
                            concise_weights(weights[second]),
                        ],
                    }
                    for ratio, first, second, before, after in ordered[-5:][::-1]
                ],
            }

        contamination = []
        for index in sorted(side_vertices):
            family_totals = {
                family: sum(
                    weight
                    for name, weight in weights[index].items()
                    if finger_family(name) == family
                    and name.endswith("_" + side)
                    and "_metacarpal_" not in name
                )
                for family in FAMILIES
            }
            dominant = max(family_totals, key=family_totals.get)
            dominant_weight = family_totals[dominant]
            foreign = sum(family_totals.values()) - dominant_weight
            if dominant_weight >= 0.50 and foreign >= 0.02:
                contamination.append(
                    {
                        "vertex": index,
                        "dominant_family": dominant,
                        "dominant_weight": dominant_weight,
                        "foreign_finger_weight": foreign,
                        "weights": concise_weights(weights[index]),
                    }
                )
        contamination.sort(
            key=lambda item: item["foreign_finger_weight"], reverse=True
        )
        side_report["cross_finger_contamination"] = {
            "vertex_count": len(contamination),
            "worst": contamination[:30],
        }
        report["sides"][side] = side_report

    all_bad.sort(reverse=True)
    for item in all_bad[:30]:
        _, side, family, ratio, first, second, before, after = item
        report["global_worst_edges"].append(
            {
                "side": side,
                "family": family,
                "ratio": ratio,
                "vertices": [first, second],
                "source_length_m": before,
                "target_length_m": after,
                "weights": [
                    concise_weights(weights[first]),
                    concise_weights(weights[second]),
                ],
            }
        )
    return report


def bone_report(source_rig, target_rig, target_scale):
    report = {}
    for side in ("l", "r"):
        side_report = {}
        names = [f"hand_{side}"]
        for family in FAMILIES:
            if family != "thumb":
                names.append(f"{family}_metacarpal_{side}")
            names.extend(
                f"{family}_{number:02d}_{side}" for number in (1, 2, 3)
            )
        for name in names:
            source_bone = source_rig.data.bones[name]
            target_bone = target_rig.data.bones[name]
            source_head = (
                source_rig.matrix_world @ source_bone.head_local
            )
            target_head = (
                target_rig.matrix_world @ target_bone.head_local
            ) / target_scale
            source_length = (
                source_rig.matrix_world @ source_bone.tail_local
                - source_head
            ).length
            target_tail = (
                target_rig.matrix_world @ target_bone.tail_local
            ) / target_scale
            target_length = (target_tail - target_head).length
            side_report[name] = {
                "source_head_m": list(source_head),
                "target_head_m": list(target_head),
                "head_displacement_m": (target_head - source_head).length,
                "source_display_length_m": source_length,
                "target_display_length_m": target_length,
                "display_length_ratio": (
                    target_length / source_length
                    if source_length > 1.0e-8
                    else None
                ),
            }
        report[side] = side_report
    return report


def look_at(camera, target):
    camera.rotation_euler = (
        Vector(target) - camera.location
    ).to_track_quat("-Z", "Y").to_euler()


def add_joint_sphere(location, name, display_scale):
    bpy.ops.mesh.primitive_ico_sphere_add(
        subdivisions=2,
        radius=0.0032 * display_scale,
        location=location,
    )
    obj = bpy.context.object
    obj.name = name
    obj.color = (1.0, 0.18, 0.02, 1.0)
    return obj


def add_joint_link(start, end, name, display_scale):
    delta = end - start
    if delta.length < 1.0e-7:
        return None
    midpoint = (start + end) * 0.5
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=12,
        radius=0.0014 * display_scale,
        depth=delta.length,
        location=midpoint,
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = delta.to_track_quat("Z", "Y").to_euler()
    obj.color = (1.0, 0.42, 0.02, 1.0)
    return obj


def render_hands(mesh, rig, positions, weights, display_scale):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studio_light = "paint.sl"
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.world.color = (0.025, 0.025, 0.025)
    mesh.color = (0.48, 0.53, 0.60, 1.0)
    rig.hide_render = True

    camera_data = bpy.data.cameras.new("BossHandAuditCamera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 0.22 * display_scale
    camera = bpy.data.objects.new("BossHandAuditCamera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera

    images = {}
    for side in ("l", "r"):
        hand_names = side_hand_names(side)
        indices = [
            index
            for index, item in enumerate(weights)
            if group_total(item, hand_names) >= 0.50
        ]
        center = sum((positions[index] for index in indices), Vector()) / len(
            indices
        )
        created = []
        useful_names = [f"hand_{side}"]
        for family in FAMILIES:
            if family != "thumb":
                useful_names.append(f"{family}_metacarpal_{side}")
            useful_names.extend(
                f"{family}_{number:02d}_{side}" for number in (1, 2, 3)
            )
        heads = {
            name: rig.matrix_world @ rig.data.bones[name].head_local
            for name in useful_names
        }
        for name, location in heads.items():
            created.append(
                add_joint_sphere(
                    location, "JOINT_" + name, display_scale
                )
            )
            parent = rig.data.bones[name].parent
            if parent and parent.name in heads:
                link = add_joint_link(
                    heads[parent.name],
                    location,
                    f"LINK_{parent.name}_TO_{name}",
                    display_scale,
                )
                if link:
                    created.append(link)

        for view, y_sign in (("Dorsal", -1.0), ("Palm", 1.0)):
            camera.location = center + Vector(
                (
                    0.0,
                    y_sign * 0.55 * display_scale,
                    0.015 * display_scale,
                )
            )
            look_at(camera, center)
            output = OUT_DIR / f"Boss_UEFN_Rest_{side}_{view}.png"
            scene.render.filepath = str(output)
            bpy.ops.render.render(write_still=True)
            images[f"{side}_{view}"] = str(output)

        for obj in created:
            bpy.data.objects.remove(obj, do_unlink=True)
    return images


def audit_uefn_reference_mesh():
    """Measure the same fitted->native change on Epic's own UEFN mesh."""
    bpy.ops.wm.open_mainfile(filepath=str(MANUAL_RIG))
    bpy.context.scene.frame_set(0)
    mesh = bpy.data.objects.get("UEFN_NATIVE_EXPORT_REFERENCE_MESH")
    rig = bpy.data.objects.get("UEFN_NATIVE_EXPORT_RIG")
    if mesh is None or mesh.type != "MESH":
        raise RuntimeError("UEFN native reference mesh not found")
    if rig is None or rig.type != "ARMATURE":
        raise RuntimeError("UEFN native reference rig not found")
    fitted_positions = evaluated_world_positions(mesh)
    weights = vertex_weights(mesh)
    edges = [(edge.vertices[0], edge.vertices[1]) for edge in mesh.data.edges]
    saved_pose_maximum = max(
        max(
            abs(
                pose_bone.matrix_basis[row][column]
                - (1.0 if row == column else 0.0)
            )
            for row in range(4)
            for column in range(4)
        )
        for pose_bone in rig.pose.bones
    )
    rig.animation_data_clear()
    for pose_bone in rig.pose.bones:
        pose_bone.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    native_positions = evaluated_world_positions(mesh)
    return {
        "file": str(MANUAL_RIG),
        "vertex_count": len(fitted_positions),
        "saved_pose_maximum_matrix_basis_delta": saved_pose_maximum,
        "edge_deformation": analyze_edges(
            edges, fitted_positions, native_positions, weights
        ),
    }


def main():
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    bpy.context.scene.frame_set(0)
    source_mesh, source_rig = find_source_objects()
    source_positions = evaluated_world_positions(source_mesh)
    weights = vertex_weights(source_mesh)
    edges = [(edge.vertices[0], edge.vertices[1]) for edge in source_mesh.data.edges]
    source_bones = {
        bone.name: {
            "head": list(source_rig.matrix_world @ bone.head_local),
            "tail": list(source_rig.matrix_world @ bone.tail_local),
        }
        for bone in source_rig.data.bones
    }

    bpy.ops.wm.open_mainfile(filepath=str(CLEAN))
    bpy.context.scene.frame_set(0)
    target_mesh, target_rig = find_clean_objects()
    target_positions = evaluated_world_positions(target_mesh)
    if len(target_positions) != len(source_positions):
        raise RuntimeError("Source/target topology differs")
    edge_scale_samples = []
    for first, second in edges[:: max(1, len(edges) // 2000)]:
        source_length = (
            source_positions[first] - source_positions[second]
        ).length
        target_length = (
            target_positions[first] - target_positions[second]
        ).length
        if source_length > 1.0e-8:
            edge_scale_samples.append(target_length / source_length)
    target_scale = percentile(edge_scale_samples, 0.50)
    if target_scale is None or not (50.0 <= target_scale <= 150.0):
        raise RuntimeError(
            f"Unexpected source/clean display scale: {target_scale}"
        )
    normalized_target_positions = [
        position / target_scale for position in target_positions
    ]

    # Recreate a tiny source armature only for a readable bone comparison.
    source_armature = bpy.data.armatures.new("TEMP_SOURCE_BONE_AUDIT")
    source_rig_copy = bpy.data.objects.new(
        "TEMP_SOURCE_BONE_AUDIT", source_armature
    )
    bpy.context.scene.collection.objects.link(source_rig_copy)
    bpy.context.view_layer.objects.active = source_rig_copy
    source_rig_copy.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for name, item in source_bones.items():
        bone = source_armature.edit_bones.new(name)
        bone.head = item["head"]
        bone.tail = item["tail"]
    bpy.ops.object.mode_set(mode="OBJECT")

    report = {
        "source": str(SOURCE),
        "clean": str(CLEAN),
        "vertex_count": len(source_positions),
        "edge_count": len(edges),
        "clean_display_scale": target_scale,
        "edge_deformation": analyze_edges(
            edges,
            source_positions,
            normalized_target_positions,
            weights,
        ),
        "bones": bone_report(source_rig_copy, target_rig, target_scale),
    }
    bpy.data.objects.remove(source_rig_copy, do_unlink=True)
    report["images"] = render_hands(
        target_mesh,
        target_rig,
        target_positions,
        weights,
        target_scale,
    )
    report["uefn_reference_mesh_control"] = audit_uefn_reference_mesh()
    AUDIT.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    summary = {
        "audit": str(AUDIT),
        "images": report["images"],
        "families": {
            side: {
                family: {
                    key: value
                    for key, value in report["edge_deformation"]["sides"][
                        side
                    ]["families"][family].items()
                    if key
                    in {
                        "edge_count",
                        "minimum_ratio",
                        "p05_ratio",
                        "median_ratio",
                        "p95_ratio",
                        "maximum_ratio",
                        "compressed_below_0_70",
                        "stretched_above_1_30",
                    }
                }
                for family in FAMILIES
            }
            for side in ("l", "r")
        },
        "cross_finger_contamination": {
            side: report["edge_deformation"]["sides"][side][
                "cross_finger_contamination"
            ]["vertex_count"]
            for side in ("l", "r")
        },
        "uefn_reference_families": {
            side: {
                family: {
                    key: value
                    for key, value in report["uefn_reference_mesh_control"][
                        "edge_deformation"
                    ]["sides"][side]["families"][family].items()
                    if key
                    in {
                        "edge_count",
                        "minimum_ratio",
                        "p05_ratio",
                        "median_ratio",
                        "p95_ratio",
                        "maximum_ratio",
                        "compressed_below_0_70",
                        "stretched_above_1_30",
                    }
                }
                for family in FAMILIES
            }
            for side in ("l", "r")
        },
    }
    print("BOSS_HAND_CONVERSION_AUDIT=" + json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
