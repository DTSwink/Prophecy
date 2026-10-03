import math

import unreal


SOURCE_BODY = "/Game/MetaHumans/test_UEFNExactFull/Body/SKM_test_UEFNFit_BodyMesh"
UEFN_MESH = "/Game/_mygame/SKM_UEFN_Mannequin"
SOURCE_BLUEPRINT = "/Game/MetaHumans/test_UEFNExactFull/BP_test_UEFNExactFull"
FACE_ANIM = "/Game/MetaHumans/Common/Face/Face_AnimBP"
BODY_OUTPUT = "/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody_WristBlendTest"
BLUEPRINT_OUTPUT = "/Game/_mygame/MetaHumans/BP_test_UEFNDirect_WristBlendTest"


def subtract(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def length(value):
    return math.sqrt(dot(value, value))


def normalize(value):
    scale = 1.0 / length(value)
    return (value[0] * scale, value[1] * scale, value[2] * scale)


def smoothstep(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


for path in (BLUEPRINT_OUTPUT, BODY_OUTPUT):
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        if not unreal.EditorAssetLibrary.delete_asset(path):
            raise RuntimeError("Could not delete existing test asset: " + path)

unreal.SystemLibrary.execute_console_command(
    None,
    "Prophecy.MetaHuman.BuildUEFNBody {} {} {}".format(
        SOURCE_BODY, UEFN_MESH, BODY_OUTPUT
    ),
)
body = unreal.load_asset(BODY_OUTPUT)
if not isinstance(body, unreal.SkeletalMesh):
    raise RuntimeError("Could not build/load wrist-blend test body")

dynamic_mesh = unreal.DynamicMesh()
asset_options = unreal.GeometryScriptCopyMeshFromAssetOptions()
read_lod = unreal.GeometryScriptMeshReadLOD(
    lod_type=unreal.GeometryScriptLODType.SOURCE_MODEL,
    lod_index=0,
)
_, extract_outcome = unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(
    body, dynamic_mesh, asset_options, read_lod
)
if extract_outcome != unreal.GeometryScriptOutcomePins.SUCCESS:
    raise RuntimeError("Could not extract wrist-blend target dynamic mesh")

_, bone_infos = unreal.GeometryScript_BoneWeights.get_all_bones_info(dynamic_mesh)
bones = {str(info.name): info for info in bone_infos}

weight_modifier = unreal.SkinWeightModifier()
if not weight_modifier.set_skeletal_mesh(body):
    raise RuntimeError("Could not edit wrist-blend target skin weights")

selected_counts = {}
for side in ("l", "r"):
    lowerarm = bones["lowerarm_" + side]
    hand = bones["hand_" + side]
    lowerarm_point = (
        lowerarm.world_transform.translation.x,
        lowerarm.world_transform.translation.y,
        lowerarm.world_transform.translation.z,
    )
    hand_point = (
        hand.world_transform.translation.x,
        hand.world_transform.translation.y,
        hand.world_transform.translation.z,
    )
    axis = normalize(subtract(hand_point, lowerarm_point))
    selected = 0
    for vertex_id in range(7622):
        position, valid = unreal.GeometryScript_MeshQueries.get_vertex_position(
            dynamic_mesh, vertex_id
        )
        if not valid:
            continue
        offset = subtract((position.x, position.y, position.z), hand_point)
        longitudinal = dot(offset, axis)
        current_weights = {
            str(name): float(weight)
            for name, weight in weight_modifier.get_vertex_weights(vertex_id).items()
        }
        lowerarm_name = "lowerarm_" + side
        hand_name = "hand_" + side
        if current_weights.get(lowerarm_name, 0.0) < 0.99:
            continue
        if longitudinal < -10.0 or longitudinal > -2.0:
            continue
        hand_weight = smoothstep((longitudinal + 10.0) / 8.0)
        if not weight_modifier.set_vertex_weights(
            vertex_id,
            {
                lowerarm_name: 1.0 - hand_weight,
                hand_name: hand_weight,
            },
            True,
        ):
            raise RuntimeError("Could not set wrist weights on vertex {}".format(vertex_id))
        selected += 1
    selected_counts[side] = selected

if not weight_modifier.commit_weights_to_skeletal_mesh():
    raise RuntimeError("Could not commit wrist-blend skin weights to test body")

mesh_editor = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
if not mesh_editor.remove_lods(body, [1, 2]):
    raise RuntimeError("Could not remove lower test LODs")
if not mesh_editor.regenerate_lod(body, 3, True, False):
    raise RuntimeError("Could not regenerate test LODs")
unreal.EditorAssetLibrary.save_loaded_asset(body, only_if_is_dirty=False)

unreal.SystemLibrary.execute_console_command(
    None,
    "Prophecy.MetaHuman.BuildUEFNBlueprint {} {} {} {}".format(
        SOURCE_BLUEPRINT, BODY_OUTPUT, FACE_ANIM, BLUEPRINT_OUTPUT
    ),
)
blueprint = unreal.load_asset(BLUEPRINT_OUTPUT)
if not isinstance(blueprint, unreal.Blueprint):
    raise RuntimeError("Could not build wrist-blend test Blueprint")
unreal.EditorAssetLibrary.save_loaded_asset(blueprint, only_if_is_dirty=False)

print(
    "WRIST_BLEND_TEST_BUILT|body={}|blueprint={}|left_vertices={}|right_vertices={}|longitudinal=-10..-2".format(
        body.get_path_name(),
        blueprint.get_path_name(),
        selected_counts["l"],
        selected_counts["r"],
    )
)
