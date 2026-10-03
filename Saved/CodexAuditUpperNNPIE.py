import json
import math
import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if not world:
    raise RuntimeError("PIE world is not running")

agents = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
if not agents:
    raise RuntimeError("No ProphecyAgent exists in PIE")

agent = agents[0]
meshes = agent.get_components_by_class(unreal.SkeletalMeshComponent)
mesh = next(
    (
        item
        for item in meshes
        if item.get_name() == "Mesh" and item.get_skinned_asset() is not None
    ),
    None,
)
if mesh is None:
    mesh = next((item for item in meshes if item.get_skinned_asset() is not None), None)
if mesh is None:
    raise RuntimeError("ProphecyAgent has no skeletal mesh")

rows = {}
authored_rows = {}
for bone_name in (
    "pelvis",
    "spine_01",
    "spine_02",
    "spine_03",
    "spine_04",
    "spine_05",
    "clavicle_l",
    "clavicle_r",
    "neck_01",
    "neck_02",
    "head",
    "upperarm_l",
    "lowerarm_l",
    "hand_l",
    "upperarm_r",
    "lowerarm_r",
    "hand_r",
    "foot_l",
    "foot_r",
):
    if mesh.get_bone_index(bone_name) < 0:
        raise RuntimeError("Missing bone " + bone_name)
    transform = mesh.get_bone_transform(
        bone_name, unreal.RelativeTransformSpace.RTS_WORLD
    )
    location = transform.translation
    rotation = transform.rotation
    values = (
        location.x,
        location.y,
        location.z,
        rotation.x,
        rotation.y,
        rotation.z,
        rotation.w,
    )
    if not all(math.isfinite(value) for value in values):
        raise RuntimeError("Non-finite transform for " + bone_name)
    rows[bone_name] = [round(float(value), 6) for value in values]
    result = agent.get_authored_body_world_target(bone_name)
    if not result[0]:
        raise RuntimeError("No authored NN target for " + bone_name)
    current_target = result[2]
    target_values = (
        current_target.translation.x,
        current_target.translation.y,
        current_target.translation.z,
        current_target.rotation.x,
        current_target.rotation.y,
        current_target.rotation.z,
        current_target.rotation.w,
    )
    if not all(math.isfinite(value) for value in target_values):
        raise RuntimeError("Non-finite authored transform for " + bone_name)
    authored_rows[bone_name] = [round(float(value), 6) for value in target_values]

print(
    "UPPER_NN_POSE="
    + json.dumps(
        {
            "agent": agent.get_name(),
            "mesh": mesh.get_name(),
            "asset": mesh.get_skinned_asset().get_path_name(),
            "components": [
                {
                    "name": item.get_name(),
                    "asset": (
                        item.get_skinned_asset().get_path_name()
                        if item.get_skinned_asset() is not None
                        else None
                    ),
                    "visible": item.is_visible(),
                    "simulating": item.is_any_simulating_physics(),
                    "anim": (
                        item.get_anim_instance().get_class().get_name()
                        if item.get_anim_instance() is not None
                        else None
                    ),
                }
                for item in meshes
            ],
            "time": unreal.GameplayStatics.get_time_seconds(world),
            "rows": rows,
            "authored_rows": authored_rows,
        },
        separators=(",", ":"),
    )
)
