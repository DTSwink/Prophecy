"""Read-only probe of the live Allysave3 boss weight-transfer scene."""

import json
from pathlib import Path

import bpy
from mathutils import Vector


OUT = Path(r"C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\BlenderExchange\BossWeightTransfer_LiveProbe.json")
NAMES = (
    "ally2_Body_Mesh",
    "ally2_Face_Mesh",
    "boss",
    "UEFN_WORKING_CLEAN_RIG.001",
)


def evaluated_world_bounds(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        points = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
    finally:
        evaluated.to_mesh_clear()
    if not points:
        return None
    minimum = Vector(tuple(min(point[index] for point in points) for index in range(3)))
    maximum = Vector(tuple(max(point[index] for point in points) for index in range(3)))
    return {"minimum": list(minimum), "maximum": list(maximum), "dimensions": list(maximum - minimum)}


def object_report(obj):
    report = {
        "name": obj.name,
        "type": obj.type,
        "parent": obj.parent.name if obj.parent else None,
        "hide_viewport": obj.hide_viewport,
        "hide_get": obj.hide_get(),
        "location": list(obj.location),
        "rotation_euler": list(obj.rotation_euler),
        "scale": list(obj.scale),
        "world_scale": list(obj.matrix_world.to_scale()),
        "modifiers": [
            {
                "name": modifier.name,
                "type": modifier.type,
                "object": modifier.object.name if modifier.type == "ARMATURE" and modifier.object else None,
            }
            for modifier in obj.modifiers
        ],
        "animation_action": (
            obj.animation_data.action.name
            if obj.animation_data and obj.animation_data.action
            else None
        ),
    }
    if obj.type == "MESH":
        weighted_vertices = 0
        zero_weight_vertices = 0
        weight_sum_error = 0.0
        used_groups = set()
        for vertex in obj.data.vertices:
            total = sum(item.weight for item in vertex.groups)
            weighted_vertices += int(total > 1e-8)
            zero_weight_vertices += int(total <= 1e-8)
            if total > 1e-8:
                weight_sum_error = max(weight_sum_error, abs(total - 1.0))
            used_groups.update(item.group for item in vertex.groups if item.weight > 1e-8)
        report.update(
            {
                "vertex_count": len(obj.data.vertices),
                "polygon_count": len(obj.data.polygons),
                "vertex_group_count": len(obj.vertex_groups),
                "vertex_group_names": [group.name for group in obj.vertex_groups],
                "used_group_names": [obj.vertex_groups[index].name for index in sorted(used_groups)],
                "weighted_vertices": weighted_vertices,
                "zero_weight_vertices": zero_weight_vertices,
                "maximum_weight_sum_error": weight_sum_error,
                "bounds": evaluated_world_bounds(obj),
            }
        )
    elif obj.type == "ARMATURE":
        action = obj.animation_data.action if obj.animation_data else None
        curves = getattr(action, "fcurves", []) if action else []
        report.update(
            {
                "bone_count": len(obj.data.bones),
                "pose_bone_count": len(obj.pose.bones),
                "action_frame_range": list(action.frame_range) if action else None,
                "keyed_pose_bones": sorted(
                    {
                        curve.data_path.split('pose.bones["', 1)[1].split('"]', 1)[0]
                        for curve in curves
                        if 'pose.bones["' in curve.data_path
                    }
                ) if action else [],
            }
        )
    return report


report = {
    "blend_file": bpy.data.filepath,
    "is_dirty": bpy.data.is_dirty,
    "current_frame": bpy.context.scene.frame_current,
    "frame_start": bpy.context.scene.frame_start,
    "frame_end": bpy.context.scene.frame_end,
    "active_object": bpy.context.view_layer.objects.active.name if bpy.context.view_layer.objects.active else None,
    "selected_objects": [obj.name for obj in bpy.context.selected_objects],
    "objects": {},
}
for name in NAMES:
    obj = bpy.data.objects.get(name)
    report["objects"][name] = object_report(obj) if obj else None

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
print("BOSS_WEIGHT_TRANSFER_PROBE=" + json.dumps(report, sort_keys=True))
