import unreal


body = unreal.load_asset("/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody")
mesh = unreal.DynamicMesh()
_, outcome = unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(
    body,
    mesh,
    unreal.GeometryScriptCopyMeshFromAssetOptions(),
    unreal.GeometryScriptMeshReadLOD(
        lod_type=unreal.GeometryScriptLODType.SOURCE_MODEL, lod_index=0
    ),
)
_, infos = unreal.GeometryScript_BoneWeights.get_all_bones_info(mesh)
bones = {str(info.name): info for info in infos}

for side in ("l", "r"):
    lowerarm = bones["lowerarm_" + side]
    hand = bones["hand_" + side]
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
        if hand_weight <= 0.001 and lowerarm_weight <= 0.001:
            continue
        position, valid_position = unreal.GeometryScript_MeshQueries.get_vertex_position(mesh, vertex_id)
        offset = (position.x - hp.x, position.y - hp.y, position.z - hp.z)
        longitudinal = sum(offset[index] * axis[index] for index in range(3))
        radial_vector = tuple(offset[index] - axis[index] * longitudinal for index in range(3))
        radial = sum(value * value for value in radial_vector) ** 0.5
        rows.append((longitudinal, radial, hand_weight, lowerarm_weight, vertex_id, position))
    print("WRIST_WEIGHT_RANGE|{}|count={}|long={:.3f}..{:.3f}|rad={:.3f}..{:.3f}".format(
        side, len(rows), min(row[0] for row in rows), max(row[0] for row in rows),
        min(row[1] for row in rows), max(row[1] for row in rows)))
    transition = [row for row in rows if row[2] > 0.001 and row[3] > 0.001]
    if transition:
        print("TRANSITION_RANGE|{}|count={}|long={:.3f}..{:.3f}|rad={:.3f}..{:.3f}".format(
            side, len(transition), min(row[0] for row in transition), max(row[0] for row in transition),
            min(row[1] for row in transition), max(row[1] for row in transition)))
    else:
        print("TRANSITION_RANGE|{}|count=0".format(side))
    for row in sorted(transition, key=lambda value: value[0])[:12]:
        longitudinal, radial, hand_weight, lowerarm_weight, vertex_id, position = row
        print("TRANSITION|{}|v={}|long={:.3f}|rad={:.3f}|hand={:.3f}|lower={:.3f}|p=({:.3f},{:.3f},{:.3f})".format(
            side, vertex_id, longitudinal, radial, hand_weight, lowerarm_weight,
            position.x, position.y, position.z))
    for row in sorted(rows, key=lambda value: value[0]):
        longitudinal, radial, hand_weight, lowerarm_weight, vertex_id, position = row
        if -14.0 <= longitudinal <= -4.0 and (hand_weight > 0.05 or lowerarm_weight > 0.05):
            print("BAND|{}|v={}|long={:.3f}|rad={:.3f}|hand={:.3f}|lower={:.3f}|p=({:.3f},{:.3f},{:.3f})".format(
                side, vertex_id, longitudinal, radial, hand_weight, lowerarm_weight,
                position.x, position.y, position.z))
