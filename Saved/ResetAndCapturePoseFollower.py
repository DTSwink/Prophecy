import builtins
import json
import math
import os
import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if not world:
    raise RuntimeError("PIE is not running")

actor = None
for candidate in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
    if "BP_ProphecyManualPoseAgent" in candidate.get_class().get_name():
        actor = candidate
        break
if not actor:
    raise RuntimeError("Pose agent not found")

components = {component.get_name(): component for component in actor.get_components_by_class(unreal.ActorComponent)}
target = components.get("Mesh")
physical = components.get("PhysicalMesh")
if not target or not physical:
    raise RuntimeError("Target or PhysicalMesh missing")

old_state = getattr(builtins, "_prophecy_pose_reset_capture", None)
if old_state and old_state.get("handle"):
    try:
        unreal.unregister_slate_post_tick_callback(old_state["handle"])
    except Exception:
        pass

bones = []
for property_name in ["physical_bones", "physical bones"]:
    try:
        bones = [str(value) for value in actor.get_editor_property(property_name)]
        break
    except Exception:
        pass

physical.set_simulate_physics(False)
physical.set_world_transform(target.get_component_transform(), False, False)
physical.set_leader_pose_component(target, True, True)
physical.tick_animation(0.0, False)
physical.refresh_bone_transforms()
physical.set_leader_pose_component(None, True, True)
physical.set_simulate_physics(True)
for bone in bones:
    physical.set_physics_linear_velocity(unreal.Vector(), False, bone)
    physical.set_physics_angular_velocity_in_radians(unreal.Vector(), False, bone)


def vec(value):
    return [float(value.x), float(value.y), float(value.z)]


def mag(value):
    return math.sqrt(value.x * value.x + value.y * value.y + value.z * value.z)


state = {"frame": 0, "rows": [], "handle": None}


def sample(delta_seconds):
    target_pos = target.get_socket_location("pelvis")
    physical_pos = physical.get_socket_location("pelvis")
    velocity = physical.get_physics_linear_velocity("pelvis")
    error = target_pos - physical_pos
    state["rows"].append({
        "frame": state["frame"],
        "game_time": float(unreal.GameplayStatics.get_time_seconds(world)),
        "slate_delta": float(delta_seconds),
        "world_delta": float(world.get_delta_seconds()),
        "target": vec(target_pos),
        "physical": vec(physical_pos),
        "error": vec(error),
        "error_mag": mag(error),
        "velocity": vec(velocity),
        "speed": mag(velocity),
    })
    state["frame"] += 1
    if state["frame"] < 120:
        return
    unreal.unregister_slate_post_tick_callback(state["handle"])
    output = os.path.join(unreal.Paths.project_saved_dir(), "PoseFollowerResetCapture.json")
    with open(output, "w", encoding="utf-8") as stream:
        json.dump(state["rows"], stream, indent=2)
    unreal.log("POSE_FOLLOWER_RESET_CAPTURE {}".format(output))


state["handle"] = unreal.register_slate_post_tick_callback(sample)
builtins._prophecy_pose_reset_capture = state
print("POSE_FOLLOWER_RESET_CAPTURE_STARTED immediate_error={} immediate_speed={}".format(
    mag(target.get_socket_location("pelvis") - physical.get_socket_location("pelvis")),
    mag(physical.get_physics_linear_velocity("pelvis"))))
