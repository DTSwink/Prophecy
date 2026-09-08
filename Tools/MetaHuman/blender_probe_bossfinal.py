"""Read-only structural audit of bossfinalsave.blend."""

import json
from pathlib import Path

import bpy


OUT = Path(
    r"C:\Users\singerie\Documents\Unreal Projects\Prophecy"
    r"\Saved\BlenderExchange\BossFinal_SourceProbe.json"
)


def object_report(obj):
    report = {
        "name": obj.name,
        "type": obj.type,
        "parent": obj.parent.name if obj.parent else None,
        "location": list(obj.location),
        "rotation_mode": obj.rotation_mode,
        "rotation_euler": list(obj.rotation_euler),
        "scale": list(obj.scale),
        "world_scale": list(obj.matrix_world.to_scale()),
        "collections": [collection.name for collection in obj.users_collection],
        "hidden": obj.hide_get(),
        "hide_viewport": obj.hide_viewport,
        "modifiers": [
            {
                "name": modifier.name,
                "type": modifier.type,
                "object": (
                    modifier.object.name
                    if modifier.type == "ARMATURE" and modifier.object
                    else None
                ),
            }
            for modifier in obj.modifiers
        ],
    }
    if obj.type == "MESH":
        used_groups = set()
        zero_weight_vertices = 0
        maximum_influences = 0
        maximum_sum_error = 0.0
        for vertex in obj.data.vertices:
            weights = [
                membership.weight
                for membership in vertex.groups
                if membership.weight > 1.0e-8
            ]
            total = sum(weights)
            zero_weight_vertices += int(total <= 1.0e-8)
            maximum_influences = max(maximum_influences, len(weights))
            if total > 1.0e-8:
                maximum_sum_error = max(maximum_sum_error, abs(total - 1.0))
            used_groups.update(
                membership.group
                for membership in vertex.groups
                if membership.weight > 1.0e-8
            )
        report.update(
            {
                "mesh_data": obj.data.name,
                "vertex_count": len(obj.data.vertices),
                "polygon_count": len(obj.data.polygons),
                "vertex_group_count": len(obj.vertex_groups),
                "vertex_group_names": [group.name for group in obj.vertex_groups],
                "used_group_names": [
                    obj.vertex_groups[index].name for index in sorted(used_groups)
                ],
                "zero_weight_vertices": zero_weight_vertices,
                "maximum_influences": maximum_influences,
                "maximum_weight_sum_error": maximum_sum_error,
                "smooth_polygons": sum(poly.use_smooth for poly in obj.data.polygons),
                "attributes": [
                    {
                        "name": attribute.name,
                        "domain": attribute.domain,
                        "type": attribute.data_type,
                    }
                    for attribute in obj.data.attributes
                ],
                "material_slots": [
                    {
                        "index": index,
                        "slot_name": slot.name,
                        "material": slot.material.name if slot.material else None,
                        "polygon_count": sum(
                            polygon.material_index == index
                            for polygon in obj.data.polygons
                        ),
                    }
                    for index, slot in enumerate(obj.material_slots)
                ],
            }
        )
    elif obj.type == "ARMATURE":
        identity = (
            (1.0, 0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0, 0.0),
            (0.0, 0.0, 0.0, 1.0),
        )
        pose_deltas = {
            bone.name: max(
                abs(bone.matrix_basis[row][column] - identity[row][column])
                for row in range(4)
                for column in range(4)
            )
            for bone in obj.pose.bones
        }
        report.update(
            {
                "armature_data": obj.data.name,
                "bone_count": len(obj.data.bones),
                "bone_names": [bone.name for bone in obj.data.bones],
                "parents": {
                    bone.name: bone.parent.name if bone.parent else None
                    for bone in obj.data.bones
                },
                "connected_bones": [
                    bone.name for bone in obj.data.bones if bone.use_connect
                ],
                "animation_action": (
                    obj.animation_data.action.name
                    if obj.animation_data and obj.animation_data.action
                    else None
                ),
                "posed_bones": sorted(
                    name for name, delta in pose_deltas.items() if delta > 1.0e-8
                ),
                "maximum_pose_basis_delta": max(pose_deltas.values(), default=0.0),
                "nla_tracks": (
                    [track.name for track in obj.animation_data.nla_tracks]
                    if obj.animation_data
                    else []
                ),
            }
        )
    return report


report = {
    "blend_file": bpy.data.filepath,
    "current_frame": bpy.context.scene.frame_current,
    "frame_range": [
        bpy.context.scene.frame_start,
        bpy.context.scene.frame_end,
    ],
    "objects": [object_report(obj) for obj in bpy.data.objects],
    "materials": [
        {
            "name": material.name,
            "use_nodes": material.use_nodes,
            "images": sorted(
                {
                    node.image.name
                    for node in (
                        material.node_tree.nodes
                        if material.use_nodes and material.node_tree
                        else ()
                    )
                    if node.type == "TEX_IMAGE" and node.image
                }
            ),
        }
        for material in bpy.data.materials
    ],
    "images": [
        {
            "name": image.name,
            "filepath": image.filepath,
            "packed": image.packed_file is not None,
            "source": image.source,
            "size": list(image.size),
        }
        for image in bpy.data.images
    ],
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
print(
    "BOSSFINAL_PROBE="
    + json.dumps(
        {
            "blend_file": report["blend_file"],
            "object_count": len(report["objects"]),
            "output": str(OUT),
        },
        sort_keys=True,
    )
)
