import json
import os

import unreal


MESH_PATH = "/Game/_mygame/assets/boat/StaticMeshes/SM_Boat_Inside"
OUTPUT_PATH = os.path.join(
    unreal.Paths.project_saved_dir(), "CodexBoatInsideGeometry.json"
)

mesh = unreal.EditorAssetLibrary.load_asset(MESH_PATH)
if not mesh:
    raise RuntimeError("Missing static mesh: " + MESH_PATH)

description = mesh.get_static_mesh_description(0)
if not description:
    raise RuntimeError("SM_Boat_Inside has no LOD 0 mesh description")

vertices = []
for index in range(description.get_vertex_count()):
    vertex_id = unreal.VertexID(index)
    if not description.is_vertex_valid(vertex_id):
        vertices.append(None)
        continue
    position = description.get_vertex_position(vertex_id)
    vertices.append([position.x, position.y, position.z])

triangles = []
for index in range(description.get_triangle_count()):
    triangle_id = unreal.TriangleID(index)
    if not description.is_triangle_valid(triangle_id):
        continue
    # UE 5.7's Python wrapper currently exposes three stale scratch entries
    # before the triangle's real three vertex IDs. Keep the valid tail.
    triangle_vertices = description.get_triangle_vertices(triangle_id)
    triangles.append([vertex_id.id_value for vertex_id in triangle_vertices[-3:]])

inside_actor = None
ocean_actor = None
for actor in unreal.EditorLevelLibrary.get_all_level_actors():
    if actor.get_actor_label() == "SM_Boat_Inside":
        inside_actor = actor
    elif actor.get_actor_label() == "ocean":
        ocean_actor = actor

if not inside_actor or not ocean_actor:
    raise RuntimeError("Expected level actors SM_Boat_Inside and ocean")

inside_component = inside_actor.get_components_by_class(unreal.StaticMeshComponent)[0]
ocean_component = ocean_actor.get_components_by_class(unreal.StaticMeshComponent)[0]

def transform_payload(component):
    transform = component.get_world_transform()
    return {
        "location": [
            transform.translation.x,
            transform.translation.y,
            transform.translation.z,
        ],
        "rotation": [
            transform.rotation.x,
            transform.rotation.y,
            transform.rotation.z,
            transform.rotation.w,
        ],
        "scale": [
            transform.scale3d.x,
            transform.scale3d.y,
            transform.scale3d.z,
        ],
    }

payload = {
    "mesh_path": MESH_PATH,
    "vertices": vertices,
    "triangles": triangles,
    "inside_actor": transform_payload(inside_component),
    "ocean_actor": transform_payload(ocean_component),
}

with open(OUTPUT_PATH, "w", encoding="utf-8") as output_file:
    json.dump(payload, output_file, separators=(",", ":"))

print(
    json.dumps(
        {
            "output": OUTPUT_PATH,
            "vertex_count": len(vertices),
            "triangle_count": len(triangles),
        },
        indent=2,
    )
)
