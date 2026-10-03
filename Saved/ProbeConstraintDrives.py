import json
import unreal

world = unreal.EditorLevelLibrary.get_game_world()
agents = [
    actor for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
    if actor.get_simulation_mode() == unreal.ProphecyAgentSimulationMode.PHYSICAL
]
mesh = agents[0].get_agent_mesh()
lib = unreal.ConstraintInstanceBlueprintLibrary
result = []
for index, accessor in enumerate(mesh.get_constraints(False)):
    _, parent, child = lib.get_attached_body_names(accessor)
    _, spring, damping, limit = lib.get_angular_drive_params(accessor)
    _, twist_pos, swing_pos = lib.get_orientation_drive_twist_and_swing(accessor)
    _, twist_vel, swing_vel = lib.get_angular_velocity_drive_twist_and_swing(accessor)
    result.append({
        "i": index, "parent": str(parent), "child": str(child),
        "spring": spring, "damping": damping, "limit": limit,
        "pos": [twist_pos, swing_pos], "vel": [twist_vel, swing_vel],
    })
print("DRIVES=" + json.dumps(result, separators=(",", ":")))
