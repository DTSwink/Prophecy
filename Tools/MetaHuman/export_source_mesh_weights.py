import json
import os

import unreal

SOURCE_BODY = "/Game/MetaHumans/test_UEFNExactFull/Body/SKM_test_UEFNFit_BodyMesh"
OUTPUT = os.path.join(unreal.Paths.project_saved_dir(), "PoseFit", "source_mesh.json")

body = unreal.load_asset(SOURCE_BODY)
if not isinstance(body, unreal.SkeletalMesh):
    raise RuntimeError("Could not load source fitted body")

dynamic_mesh = unreal.DynamicMesh()
asset_options = unreal.GeometryScriptCopyMeshFromAssetOptions()
read_lod = unreal.GeometryScriptMeshReadLOD(
    lod_type=unreal.GeometryScriptLODType.SOURCE_MODEL, lod_index=0
)
_, outcome = unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(
    body, dynamic_mesh, asset_options, read_lod
)
if outcome != unreal.GeometryScriptOutcomePins.SUCCESS:
    raise RuntimeError("Could not extract source dynamic mesh")

modifier = unreal.SkinWeightModifier()
if not modifier.set_skeletal_mesh(body):
    raise RuntimeError("Could not read source weights")

num_vertices = modifier.get_num_vertices()
positions = []
weights = []
for vertex_id in range(num_vertices):
    position, valid = unreal.GeometryScript_MeshQueries.get_vertex_position(
        dynamic_mesh, vertex_id
    )
    if not valid:
        raise RuntimeError("Invalid vertex id {}".format(vertex_id))
    positions.append([position.x, position.y, position.z])
    vertex_weights = {
        str(name): float(value)
        for name, value in modifier.get_vertex_weights(vertex_id).items()
        if float(value) > 0.00005
    }
    weights.append(vertex_weights)

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
with open(OUTPUT, "w", encoding="utf-8") as handle:
    json.dump({"num_vertices": num_vertices, "positions": positions, "weights": weights}, handle)
print("EXPORT_MESH_DONE|vertices={}|output={}".format(num_vertices, OUTPUT))
