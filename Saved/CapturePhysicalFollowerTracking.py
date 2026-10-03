import builtins
import json
import math
import os
import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if not world:
    raise RuntimeError("PIE is not running")

old_state = getattr(builtins, "_prophecy_physical_follower_tracking", None)
if old_state and old_state.get("handle"):
    try:
        unreal.unregister_slate_post_tick_callback(old_state["handle"])
    except Exception:
        pass

actors = {}
for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
    class_name = actor.get_class().get_name()
    if "BP_ProphecyManualPoseAgent" in class_name:
        actors["pose"] = actor
    elif "SandboxCharacter_CMC" in class_name:
        actors["cmc"] = actor

for key, actor in actors.items():
    components = {component.get_name(): component for component in actor.get_components_by_class(unreal.ActorComponent)}
    target = components.get("Mesh") or components.get("CharacterMesh0")
    physical = components.get("PhysicalMesh")
    if not target or not physical:
        raise RuntimeError("Missing target/physical component for {}".format(key))
    actors[key] = {"actor": actor, "target": target, "physical": physical}

state = {
    "frames": [],
    "frame": 0,
    "actors": actors,
    "previous": {},
    "handle": None,
}


def vector_tuple(vector):
    return [float(vector.x), float(vector.y), float(vector.z)]


def vector_length(vector):
    return math.sqrt(vector.x * vector.x + vector.y * vector.y + vector.z * vector.z)


def post_tick(delta_seconds):
    game_world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if not game_world:
        return
    row = {
        "frame": state["frame"],
        "dt": float(delta_seconds),
        "time": float(unreal.GameplayStatics.get_time_seconds(game_world)),
    }
    for key, entry in state["actors"].items():
        target = entry["target"]
        physical = entry["physical"]
        target_pos = target.get_socket_location("pelvis")
        physical_pos = physical.get_socket_location("pelvis")
        physical_velocity = physical.get_physics_linear_velocity("pelvis")
        previous = state["previous"].get(key)
        target_step = unreal.Vector()
        if previous is not None:
            target_step = target_pos - previous
        state["previous"][key] = target_pos
        error = target_pos - physical_pos
        row[key] = {
            "target": vector_tuple(target_pos),
            "physical": vector_tuple(physical_pos),
            "target_step_cm": vector_tuple(target_step),
            "target_step_mag_cm": vector_length(target_step),
            "error_cm": vector_tuple(error),
            "error_mag_cm": vector_length(error),
            "physical_velocity_cm_s": vector_tuple(physical_velocity),
            "physical_speed_cm_s": vector_length(physical_velocity),
        }
    state["frames"].append(row)
    state["frame"] += 1
    if state["frame"] < 240:
        return

    unreal.unregister_slate_post_tick_callback(state["handle"])
    summary = {}
    for key in state["actors"]:
        samples = [frame[key] for frame in state["frames"] if key in frame]
        summary[key] = {
            "frames": len(samples),
            "max_target_step_cm": max(sample["target_step_mag_cm"] for sample in samples),
            "mean_target_step_cm": sum(sample["target_step_mag_cm"] for sample in samples) / len(samples),
            "max_error_cm": max(sample["error_mag_cm"] for sample in samples),
            "mean_error_cm": sum(sample["error_mag_cm"] for sample in samples) / len(samples),
            "max_physical_speed_cm_s": max(sample["physical_speed_cm_s"] for sample in samples),
        }
    payload = {"summary": summary, "frames": state["frames"]}
    path = os.path.join(unreal.Paths.project_saved_dir(), "PhysicalFollowerTracking.json")
    with open(path, "w", encoding="utf-8") as output:
        json.dump(payload, output, indent=2)
    unreal.log("PHYSICAL_FOLLOWER_TRACKING {} {}".format(path, summary))


state["handle"] = unreal.register_slate_post_tick_callback(post_tick)
builtins._prophecy_physical_follower_tracking = state
print("PHYSICAL_FOLLOWER_TRACKING_STARTED actors={}".format(list(actors.keys())))
