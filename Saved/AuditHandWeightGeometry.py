import unreal


body = unreal.load_asset("/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody")
mesh = unreal.DynamicMesh()
unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(
    body,
    mesh,
    unreal.GeometryScriptCopyMeshFromAssetOptions(),
    unreal.GeometryScriptMeshReadLOD(lod_type=unreal.GeometryScriptLODType.SOURCE_MODEL, lod_index=0),
)
_, infos = unreal.GeometryScript_BoneWeights.get_all_bones_info(mesh)
bones = {str(info.name): info for info in infos}
lowerarm = bones["lowerarm_l"]
hand = bones["hand_l"]
lp = lowerarm.world_transform.translation
hp = hand.world_transform.translation
axis_raw = (hp.x - lp.x, hp.y - lp.y, hp.z - lp.z)
axis_length = sum(value * value for value in axis_raw) ** 0.5
axis = tuple(value / axis_length for value in axis_raw)
rows = []
for vertex_id in range(7622):
    _, weights, valid = unreal.GeometryScript_BoneWeights.get_vertex_bone_weights(mesh, vertex_id)
    if not valid:
        continue
    weight_map = {weight.bone_index: weight.weight for weight in weights}
    hand_weight = weight_map.get(hand.index, 0.0)
    lowerarm_weight = weight_map.get(lowerarm.index, 0.0)
    if hand_weight <= 0.001:
        continue
    position, valid = unreal.GeometryScript_MeshQueries.get_vertex_position(mesh, vertex_id)
    offset = (position.x - hp.x, position.y - hp.y, position.z - hp.z)
    longitudinal = sum(offset[index] * axis[index] for index in range(3))
    radial_vector = tuple(offset[index] - axis[index] * longitudinal for index in range(3))
    radial = sum(value * value for value in radial_vector) ** 0.5
    rows.append((longitudinal, radial, hand_weight, lowerarm_weight, vertex_id, position, weights))

for row in sorted(rows, key=lambda value: value[0]):
    longitudinal, radial, hand_weight, lowerarm_weight, vertex_id, position, weights = row
    if -8.0 <= longitudinal <= 2.5:
        print("HAND_POINT|v={}|long={:.3f}|rad={:.3f}|hand={:.3f}|p=({:.3f},{:.3f},{:.3f})|weights={}".format(
            vertex_id, longitudinal, radial, hand_weight, position.x, position.y, position.z,
            ",".join("{}:{:.3f}".format(info.name, weight.weight) for weight in weights for info in infos if info.index == weight.bone_index)))
