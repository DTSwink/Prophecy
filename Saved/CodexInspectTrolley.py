import bpy
import bmesh
import json
import sys


fbx_path = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=fbx_path, use_anim=False)

report = []
for obj in bpy.context.scene.objects:
    if obj.type != "MESH":
        continue
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    remaining = set(bm.verts)
    components = []
    while remaining:
        seed = remaining.pop()
        stack = [seed]
        component = [seed]
        while stack:
            vert = stack.pop()
            for edge in vert.link_edges:
                other = edge.other_vert(vert)
                if other in remaining:
                    remaining.remove(other)
                    stack.append(other)
                    component.append(other)
        coords = [obj.matrix_world @ vert.co for vert in component]
        mins = [min(co[i] for co in coords) for i in range(3)]
        maxs = [max(co[i] for co in coords) for i in range(3)]
        components.append({
            "vertices": len(component),
            "min": mins,
            "max": maxs,
            "dimensions": [maxs[i] - mins[i] for i in range(3)],
            "center": [(mins[i] + maxs[i]) * 0.5 for i in range(3)],
            "coords": [[co.x, co.y, co.z] for co in coords] if len(component) <= 32 else None,
        })
    bm.free()
    report.append({
        "name": obj.name,
        "vertices": len(mesh.vertices),
        "polygons": len(mesh.polygons),
        "dimensions": list(obj.dimensions),
        "location": list(obj.location),
        "rotation": list(obj.rotation_euler),
        "scale": list(obj.scale),
        "components": sorted(components, key=lambda item: item["vertices"], reverse=True),
    })

print("CODEX_REPORT=" + json.dumps(report))
print("CODEX_SMALL=" + json.dumps([
    component
    for obj_report in report
    for component in obj_report["components"]
    if component["vertices"] == 24
]))
