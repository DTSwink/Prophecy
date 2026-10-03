"""For every candidate body SkeletalMesh, measure how far hand/finger joints
sit from the vertices skinned to them. Consistent rig: centroid within ~2-3cm
of the bone. The stamped UEFN-joint assets show 8-17 cm."""

import unreal

registry = unreal.AssetRegistryHelpers.get_asset_registry()

candidates = []
for root in ("/Game/MetaHumans", "/Game/_mygame"):
    for data in registry.get_assets_by_path(root, recursive=True):
        if str(data.asset_class_path.asset_name) == "SkeletalMesh":
            path = str(data.package_name)
            if path not in candidates:
                candidates.append(path)

CHECK_BONES = ("hand_r", "index_03_r", "middle_01_r", "ball_r")

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
probe = actor_subsystem.spawn_actor_from_class(
    unreal.SkeletalMeshActor, unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator()
)
probe.set_actor_label("ProphecyConsistencyProbe")
component = probe.skeletal_mesh_component


def audit(path):
    mesh = unreal.load_asset(path)
    if mesh is None:
        print("AUDIT|{}|LOAD_FAILED".format(path))
        return
    component.set_skeletal_mesh_asset(mesh)

    all_bones = {str(n) for n in component.get_all_socket_names()}
    bone_positions = {}
    for bone in CHECK_BONES:
        if bone not in all_bones:
            continue
        bone_positions[bone] = component.get_socket_location(bone)
    if not bone_positions:
        print("AUDIT|{}|NO_SHARED_BONES".format(path))
        return

    dynamic_mesh = unreal.DynamicMesh()
    asset_options = unreal.GeometryScriptCopyMeshFromAssetOptions()
    read_lod = unreal.GeometryScriptMeshReadLOD(
        lod_type=unreal.GeometryScriptLODType.SOURCE_MODEL, lod_index=0
    )
    _, outcome = unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(
        mesh, dynamic_mesh, asset_options, read_lod
    )
    if outcome != unreal.GeometryScriptOutcomePins.SUCCESS:
        print("AUDIT|{}|DYNAMIC_MESH_FAILED".format(path))
        return

    modifier = unreal.SkinWeightModifier()
    if not modifier.set_skeletal_mesh(mesh):
        print("AUDIT|{}|MODIFIER_FAILED".format(path))
        return
    num = modifier.get_num_vertices()

    sums = {bone: [0.0, 0.0, 0.0, 0.0] for bone in bone_positions}
    for index in range(num):
        for name, value in modifier.get_vertex_weights(index).items():
            bone = str(name)
            if bone in sums and value > 0.4:
                p, valid = unreal.GeometryScript_MeshQueries.get_vertex_position(
                    dynamic_mesh, index
                )
                if not valid:
                    continue
                acc = sums[bone]
                acc[0] += p.x * value
                acc[1] += p.y * value
                acc[2] += p.z * value
                acc[3] += value
    del modifier

    print("AUDIT|{}|verts={}".format(path, num))
    for bone, position in bone_positions.items():
        acc = sums[bone]
        if acc[3] <= 0.0:
            print("  BONE|{}|no_weights".format(bone))
            continue
        cx, cy, cz = acc[0] / acc[3], acc[1] / acc[3], acc[2] / acc[3]
        dist = ((cx - position.x) ** 2 + (cy - position.y) ** 2 + (cz - position.z) ** 2) ** 0.5
        print("  BONE|{}|joint=({:.1f},{:.1f},{:.1f})|centroid=({:.1f},{:.1f},{:.1f})|dist_cm={:.2f}".format(
            bone, position.x, position.y, position.z, cx, cy, cz, dist))


for path in candidates:
    lower = path.lower()
    if any(k in lower for k in ("body", "carrier", "mannequin")):
        audit(path)

actor_subsystem.destroy_actor(probe)
print("CONSISTENCY_AUDIT_DONE")
