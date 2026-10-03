import bpy
import bmesh
import json
import math
import os
import statistics
import sys


def tri_area_3d(a, b, c):
    return ((b - a).cross(c - a)).length * 0.5


def tri_area_2d(a, b, c):
    return abs((b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)) * 0.5


def polygon_uv_area(mesh, uv_data, polygon):
    points = [uv_data[index].uv for index in polygon.loop_indices]
    area = 0.0
    for index, point in enumerate(points):
        following = points[(index + 1) % len(points)]
        area += point.x * following.y - following.x * point.y
    return abs(area) * 0.5


source_path, output_path = sys.argv[sys.argv.index("--") + 1 :]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.fbx_import(filepath=source_path)

mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
if len(mesh_objects) != 1:
    raise RuntimeError(f"Expected one mesh object, found {len(mesh_objects)}")

obj = mesh_objects[0]
mesh = obj.data
if not mesh.uv_layers:
    raise RuntimeError("SM_Boat_Thick2 has no UV layers")

mesh.uv_layers.active_index = 0
uv_layer = mesh.uv_layers.active
uv_data = uv_layer.data
mesh.calc_loop_triangles()

collapsed_polygon_indices = {
    polygon.index
    for polygon in mesh.polygons
    if polygon_uv_area(mesh, uv_data, polygon) < 1.0e-12
}
if len(collapsed_polygon_indices) != 107:
    raise RuntimeError(
        f"Expected the 107 new collapsed polygons, found {len(collapsed_polygon_indices)}"
    )

# Match the repaired faces to the median texel density of the existing faces
# using the same wood material slot (slot zero). This preserves the apparent
# scale of the original texture instead of merely making the UVs non-zero.
reference_ratios = []
for tri in mesh.loop_triangles:
    if tri.polygon_index in collapsed_polygon_indices or tri.material_index != 0:
        continue
    points = [mesh.vertices[index].co for index in tri.vertices]
    uvs = [uv_data[index].uv for index in tri.loops]
    area_3d = tri_area_3d(*points)
    area_uv = tri_area_2d(*uvs)
    if area_3d > 1.0e-12 and area_uv > 1.0e-12:
        reference_ratios.append(area_3d / area_uv)
if not reference_ratios:
    raise RuntimeError("Could not derive the original wood texel density")
target_ratio = statistics.median(reference_ratios)

bpy.context.view_layer.objects.active = obj
obj.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_mode(type="FACE")
edit_mesh = bmesh.from_edit_mesh(mesh)
edit_mesh.faces.ensure_lookup_table()
for face in edit_mesh.faces:
    face.select = face.index in collapsed_polygon_indices
bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
bpy.ops.uv.cube_project(
    cube_size=math.sqrt(target_ratio),
    correct_aspect=True,
    clip_to_bounds=False,
    scale_to_bounds=False,
)
bpy.ops.object.mode_set(mode="OBJECT")
uv_layer = mesh.uv_layers.active
uv_data = uv_layer.data

# Cube projection is already close to the desired density. Normalize the
# selected loops once more from the measured result for an exact match.
mesh.calc_loop_triangles()
new_ratios = []
post_zero_uv = 0
post_zero_geometry = 0
selected_triangle_count = 0
for tri in mesh.loop_triangles:
    if tri.polygon_index not in collapsed_polygon_indices:
        continue
    selected_triangle_count += 1
    points = [mesh.vertices[index].co for index in tri.vertices]
    uvs = [uv_data[index].uv for index in tri.loops]
    area_3d = tri_area_3d(*points)
    area_uv = tri_area_2d(*uvs)
    post_zero_geometry += int(area_3d <= 1.0e-12)
    post_zero_uv += int(area_uv <= 1.0e-12)
    if area_3d > 1.0e-12 and area_uv > 1.0e-12:
        new_ratios.append(area_3d / area_uv)
expected_renderable_triangles = selected_triangle_count - post_zero_geometry
if len(new_ratios) != expected_renderable_triangles or post_zero_uv != post_zero_geometry:
    raise RuntimeError(
        "UV repair validation mismatch: "
        f"selected={selected_triangle_count} valid={len(new_ratios)} "
        f"zero_uv={post_zero_uv} zero_geometry={post_zero_geometry}"
    )

current_ratio = statistics.median(new_ratios)
uv_scale = math.sqrt(current_ratio / target_ratio)
selected_loop_indices = [
    loop_index
    for polygon in mesh.polygons
    if polygon.index in collapsed_polygon_indices
    for loop_index in polygon.loop_indices
]
center_x = statistics.mean(uv_data[index].uv.x for index in selected_loop_indices)
center_y = statistics.mean(uv_data[index].uv.y for index in selected_loop_indices)
for index in selected_loop_indices:
    uv = uv_data[index].uv
    uv.x = center_x + (uv.x - center_x) * uv_scale
    uv.y = center_y + (uv.y - center_y) * uv_scale

mesh.update()
mesh.calc_loop_triangles()
remaining_collapsed = 0
final_ratios = []
for tri in mesh.loop_triangles:
    if tri.polygon_index not in collapsed_polygon_indices:
        continue
    points = [mesh.vertices[index].co for index in tri.vertices]
    uvs = [uv_data[index].uv for index in tri.loops]
    area_3d = tri_area_3d(*points)
    area_uv = tri_area_2d(*uvs)
    if area_3d > 1.0e-12 and area_uv < 1.0e-12:
        remaining_collapsed += 1
    elif area_3d > 1.0e-12:
        final_ratios.append(area_3d / area_uv)
if remaining_collapsed:
    raise RuntimeError(f"UV repair left {remaining_collapsed} collapsed triangles")

os.makedirs(os.path.dirname(output_path), exist_ok=True)
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.export_scene.fbx(
    filepath=output_path,
    use_selection=True,
    global_scale=1.0,
    apply_unit_scale=True,
    use_space_transform=True,
    bake_space_transform=False,
    object_types={"MESH"},
    use_mesh_modifiers=True,
    mesh_smooth_type="FACE",
    use_tspace=True,
    use_triangles=False,
    bake_anim=False,
    add_leaf_bones=False,
    path_mode="AUTO",
    axis_forward="-Z",
    axis_up="Y",
)

print(
    "CODEX_RESULT="
    + json.dumps(
        {
            "source": source_path,
            "output": output_path,
            "vertices": len(mesh.vertices),
            "polygons": len(mesh.polygons),
            "triangles": len(mesh.loop_triangles),
            "repaired_polygons": len(collapsed_polygon_indices),
            "repaired_triangles": len(final_ratios),
            "degenerate_source_triangles_ignored": post_zero_geometry,
            "remaining_collapsed_triangles": remaining_collapsed,
            "target_world_area_per_uv_area": target_ratio,
            "final_world_area_per_uv_area": statistics.median(final_ratios),
            "uv_layers": [layer.name for layer in mesh.uv_layers],
            "materials": [
                slot.material.name if slot.material else None
                for slot in obj.material_slots
            ],
        },
        separators=(",", ":"),
    )
)
