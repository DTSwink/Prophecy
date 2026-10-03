import unreal


body = unreal.load_asset("/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody_WristBlendTest")
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
for info in infos:
    if str(info.name) in ("lowerarm_l", "hand_l", "lowerarm_r", "hand_r"):
        local = info.local_transform.translation
        world = info.world_transform.translation
        print("BONE|{}|index={}|local=({:.3f},{:.3f},{:.3f})|world=({:.3f},{:.3f},{:.3f})".format(
            info.name, info.index, local.x, local.y, local.z, world.x, world.y, world.z))

minimum = unreal.Vector(1e9, 1e9, 1e9)
maximum = unreal.Vector(-1e9, -1e9, -1e9)
nearest = []
for vertex_id in range(7622):
    position, valid = unreal.GeometryScript_MeshQueries.get_vertex_position(mesh, vertex_id)
    if not valid:
        continue
    minimum.x = min(minimum.x, position.x)
    minimum.y = min(minimum.y, position.y)
    minimum.z = min(minimum.z, position.z)
    maximum.x = max(maximum.x, position.x)
    maximum.y = max(maximum.y, position.y)
    maximum.z = max(maximum.z, position.z)
print("BOUNDS|min=({:.3f},{:.3f},{:.3f})|max=({:.3f},{:.3f},{:.3f})".format(
    minimum.x, minimum.y, minimum.z, maximum.x, maximum.y, maximum.z))

for side, hand_point, lowerarm_point in (
    ("l", (51.973, 4.088, 102.694), (37.685, -5.793, 116.754)),
    ("r", (-51.973, 4.088, 102.694), (-37.685, -5.793, 116.754)),
):
    axis_raw = (
        hand_point[0] - lowerarm_point[0],
        hand_point[1] - lowerarm_point[1],
        hand_point[2] - lowerarm_point[2],
    )
    axis_length = sum(value * value for value in axis_raw) ** 0.5
    axis = tuple(value / axis_length for value in axis_raw)
    histogram = {}
    samples = []
    for vertex_id in range(7622):
        position, valid = unreal.GeometryScript_MeshQueries.get_vertex_position(mesh, vertex_id)
        if not valid:
            continue
        offset = (position.x - hand_point[0], position.y - hand_point[1], position.z - hand_point[2])
        longitudinal = sum(offset[index] * axis[index] for index in range(3))
        radial_vector = tuple(offset[index] - axis[index] * longitudinal for index in range(3))
        radial = sum(value * value for value in radial_vector) ** 0.5
        if radial <= 6.0:
            bucket = int(longitudinal // 2.0) * 2
            histogram[bucket] = histogram.get(bucket, 0) + 1
            if -12.0 <= longitudinal <= 4.0:
                samples.append((radial, longitudinal, vertex_id, position))
    print("HIST|{}|{}".format(side, ",".join("{}:{}".format(key, histogram[key]) for key in sorted(histogram))))
    for radial, longitudinal, vertex_id, position in sorted(samples)[:10]:
        print("SAMPLE|{}|v={}|long={:.3f}|rad={:.3f}|p=({:.3f},{:.3f},{:.3f})".format(
            side, vertex_id, longitudinal, radial, position.x, position.y, position.z))
