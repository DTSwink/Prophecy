import json
import unreal


world = unreal.EditorLevelLibrary.get_game_world()
if world is None:
    raise RuntimeError("PIE is not running")

agents = [
    actor for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
    if actor.get_simulation_mode() == unreal.ProphecyAgentSimulationMode.PHYSICAL
]
if not agents:
    raise RuntimeError("No Physical ProphecyAgent exists in PIE")

agent = agents[0]
mesh = agent.get_agent_mesh()
mesh.set_collision_response_to_all_channels(unreal.CollisionResponseType.ECR_IGNORE)

lib = unreal.ConstraintInstanceBlueprintLibrary
targets = []
for index, accessor in enumerate(mesh.get_constraints(False)):
    result = lib.get_angular_orientation_target(accessor)
    target = result[-1] if isinstance(result, tuple) else result
    targets.append({
        "index": index,
        "pitch": round(target.pitch, 6),
        "yaw": round(target.yaw, 6),
        "roll": round(target.roll, 6),
    })

print("PHYSICAL_TARGETS=" + json.dumps({
    "agent": agent.get_name(),
    "collision": str(mesh.get_collision_enabled()),
    "targets": targets,
}, separators=(",", ":")))
