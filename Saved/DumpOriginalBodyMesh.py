import json
import os

import unreal

SOURCE = "/Game/MetaHumans/test/Body/SKM_test_BodyMesh"
OUTPUT = os.path.join(unreal.Paths.project_saved_dir(), "PoseFit", "original_mesh.json")

body = unreal.load_asset(SOURCE)
if not isinstance(body, unreal.SkeletalMesh):
    raise RuntimeError("Could not load original body")

dynamic_mesh = unreal.DynamicMesh()
asset_options = unreal.GeometryScriptCopyMeshFromAssetOptions()
read_lod = unreal.GeometryScriptMeshReadLOD(
    lod_type=unreal.GeometryScriptLODType.SOURCE_MODEL, lod_index=0
)
_, outcome = unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(
    body, dynamic_mesh, asset_options, read_lod
)
if outcome != unreal.GeometryScriptOutcomePins.SUCCESS:
    raise RuntimeError("Could not extract dynamic mesh")

modifier = unreal.SkinWeightModifier()
if not modifier.set_skeletal_mesh(body):
    raise RuntimeError("Could not read weights")

num = modifier.get_num_vertices()
positions = []
weights = []
for index in range(num):
    p, valid = unreal.GeometryScript_MeshQueries.get_vertex_position(dynamic_mesh, index)
    if not valid:
        raise RuntimeError("Invalid vertex {}".format(index))
    positions.append([p.x, p.y, p.z])
    weights.append({
        str(name): float(value)
        for name, value in modifier.get_vertex_weights(index).items()
        if float(value) > 0.00005
    })

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
with open(OUTPUT, "w", encoding="utf-8") as handle:
    json.dump({"num_vertices": num, "positions": positions, "weights": weights}, handle)
print("DUMP_ORIGINAL_DONE|{}".format(num))
