import json
import unreal

world = unreal.EditorLevelLibrary.get_game_world()
agent = [
    actor for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
    if actor.get_simulation_mode() == unreal.ProphecyAgentSimulationMode.PHYSICAL
][0]
mesh = agent.get_agent_mesh()
pairs = (
    ("pelvis", "thigh_l"), ("thigh_l", "calf_l"), ("calf_l", "foot_l"),
    ("pelvis", "thigh_r"), ("thigh_r", "calf_r"), ("calf_r", "foot_r"),
    ("spine_05", "upperarm_l"), ("upperarm_l", "lowerarm_l"),
    ("spine_05", "upperarm_r"), ("upperarm_r", "lowerarm_r"),
)
out = {}
for parent, child in pairs:
    parent_t = mesh.get_socket_transform(parent, unreal.RelativeTransformSpace.RTS_WORLD)
    child_t = mesh.get_socket_transform(child, unreal.RelativeTransformSpace.RTS_WORLD)
    relative = unreal.MathLibrary.make_relative_transform(child_t, parent_t)
    rotation = relative.rotation.rotator()
    out[parent + ">" + child] = [
        round(rotation.pitch, 5), round(rotation.yaw, 5), round(rotation.roll, 5)
    ]
print("RELATIVE_POSE=" + json.dumps(out, separators=(",", ":")))
