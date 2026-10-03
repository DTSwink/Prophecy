import json
import unreal

world = unreal.EditorLevelLibrary.get_game_world()
agent = [
    actor for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
    if actor.get_simulation_mode() == unreal.ProphecyAgentSimulationMode.PHYSICAL
][0]
lib = unreal.ConstraintInstanceBlueprintLibrary
out = []
for index, accessor in enumerate(agent.get_agent_mesh().get_constraints(False)):
    _, parent, child = lib.get_attached_body_names(accessor)
    if str(child) not in ("thigh_l", "calf_l", "foot_l", "thigh_r", "calf_r", "foot_r"):
        continue
    values = lib.get_angular_limits(accessor)
    out.append({
        "i": index, "parent": str(parent), "child": str(child),
        "swing1": [str(values[1]), values[2]],
        "swing2": [str(values[3]), values[4]],
        "twist": [str(values[5]), values[6]],
    })
print("LIMITS=" + json.dumps(out, separators=(",", ":")))
