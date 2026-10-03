import bpy
import json
import math
import os
import sys


def triangle_area_3d(a, b, c):
    return ((b - a).cross(c - a)).length * 0.5


def triangle_area_2d(a, b, c):
    return abs((b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)) * 0.5


def inspect(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.fbx_import(filepath=path)
    result = {"file": path, "objects": []}
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        mesh = obj.data
        mesh.calc_loop_triangles()
        uv_layer = mesh.uv_layers.active.data if mesh.uv_layers.active else None
        zero_uv = 0
        stretched = 0
        ratios = []
        by_material = {}
        for tri in mesh.loop_triangles:
            verts = [obj.matrix_world @ mesh.vertices[index].co for index in tri.vertices]
            area_3d = triangle_area_3d(*verts)
            area_uv = 0.0
            if uv_layer:
                uvs = [uv_layer[index].uv for index in tri.loops]
                area_uv = triangle_area_2d(*uvs)
            if area_uv < 1.0e-10:
                zero_uv += 1
            elif area_3d > 1.0e-10:
                ratio = area_3d / area_uv
                ratios.append(ratio)
            slot = str(tri.material_index)
            bucket = by_material.setdefault(slot, {"triangles": 0, "zero_uv": 0, "ratios": []})
            bucket["triangles"] += 1
            bucket["zero_uv"] += int(area_uv < 1.0e-10)
            if area_uv >= 1.0e-10 and area_3d > 1.0e-10:
                bucket["ratios"].append(area_3d / area_uv)

        if ratios:
            ordered = sorted(ratios)
            median = ordered[len(ordered) // 2]
            stretched = sum(r > median * 20.0 or r < median / 20.0 for r in ratios)
        else:
            median = None
        for bucket in by_material.values():
            br = sorted(bucket.pop("ratios"))
            bucket["median_world_area_per_uv_area"] = br[len(br) // 2] if br else None
            bucket["min_world_area_per_uv_area"] = br[0] if br else None
            bucket["max_world_area_per_uv_area"] = br[-1] if br else None
        result["objects"].append(
            {
                "name": obj.name,
                "vertices": len(mesh.vertices),
                "polygons": len(mesh.polygons),
                "triangles": len(mesh.loop_triangles),
                "uv_layers": [layer.name for layer in mesh.uv_layers],
                "zero_area_uv_triangles": zero_uv,
                "extreme_uv_density_triangles": stretched,
                "median_world_area_per_uv_area": median,
                "smooth_polygons": sum(poly.use_smooth for poly in mesh.polygons),
                "flat_polygons": sum(not poly.use_smooth for poly in mesh.polygons),
                "materials": [slot.material.name if slot.material else None for slot in obj.material_slots],
                "by_material": by_material,
            }
        )
    return result


paths = sys.argv[sys.argv.index("--") + 1 :]
print("CODEX_JSON=" + json.dumps([inspect(path) for path in paths], separators=(",", ":")))
