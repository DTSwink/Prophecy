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
mesh = agents[0].get_agent_mesh()
bones = {}
for name in ("pelvis", "thigh_l", "calf_l", "foot_l", "thigh_r", "calf_r", "foot_r"):
    transform = mesh.get_socket_transform(name, unreal.RelativeTransformSpace.RTS_WORLD)
    location = transform.translation
    bones[name] = [round(location.x, 4), round(location.y, 4), round(location.z, 4)]
print("PHYSICAL_BODIES=" + json.dumps({
    "awake": mesh.is_any_rigid_body_awake(),
    "bones": bones,
}, separators=(",", ":")))
