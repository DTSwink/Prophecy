"""PIE-only moving half/full Slash regression. Uses the actual input and BP nodes.

No assets are saved. Slate callback samples only; it never evaluates the mesh.
"""
import json
import math
from pathlib import Path
import time
import traceback
import unreal

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
original_max_fps = unreal.SystemLibrary.get_console_variable_float_value("t.MaxFPS")
actor = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)[0]
mesh = actor.get_pose_reference_mesh()
actor.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
mesh.visibility_based_anim_tick_option = unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES
mesh.enable_update_rate_optimizations = False
output = Path(unreal.Paths.project_dir()).resolve() / "Saved/SlashParity/moving_runtime.json"
state = {"handle": None, "phase": 0, "start": time.monotonic(), "frames": [], "origins": [], "cases": [], "case": -1, "last_frame": -1}
cases = [("slashL", False, 60), ("slashR", True, 30), ("hookL", True, 5), ("kickR", False, 60)]


def command(value):
    unreal.SystemLibrary.execute_console_command(world, value)


def finish(error=None):
    if state["handle"]:
        unreal.unregister_slate_post_tick_callback(state["handle"])
        state["handle"] = None
    actor.stop_locomotion_input()
    actor.set_locomotion_running(False)
    command(f"t.MaxFPS {original_max_fps}")
    actor.set_upper_nn_gaze(0.0, 0.0)
    output.write_text(json.dumps({"cases": state["cases"], "frames": state["frames"], "error": error}, indent=2))
    unreal.log("Moving Slash audit saved " + str(output))


def tick(delta):
    try:
        now = time.monotonic()
        if state["phase"] == 0:
            state["case"] += 1
            if state["case"] == len(cases):
                finish()
                return
            name, half, fps = cases[state["case"]]
            command(f"t.MaxFPS {fps}")
            direction = actor.get_agent_camera().get_forward_vector()
            length = math.hypot(direction.x, direction.y)
            direction = unreal.Vector(direction.x / length, direction.y / length, 0)
            actor.set_locomotion_input(direction, half, direction, 1.0, 1.0)
            state["start"] = now
            state["origin"] = actor.get_actor_location()
            state["phase"] = 1
            return
        if state["phase"] == 1:
            if now - state["start"] < 1.0:
                return
            name, half, fps = cases[state["case"]]
            location = actor.get_actor_location()
            origin = state["origin"]
            distance = math.hypot(location.x-origin.x, location.y-origin.y)
            assert distance > 20, f"Input did not move the capsule: {distance} cm"
            target = actor.get_actor_transform().transform_location(unreal.Vector(-45, 110, 10))
            assert actor.call_method("TriggerNNAttack", args=(unreal.Name(name), target, half))
            state["cases"].append({"attack": name, "half": half, "fps": fps, "pre_attack_travel_cm": distance})
            state["attack_origin"] = location
            state["phase"] = 2
            state["last_frame"] = -1
        current = actor.call_method("GetNNAttackState")
        if not current:
            location = actor.get_actor_location()
            origin = state["attack_origin"]
            distance = math.hypot(location.x-origin.x, location.y-origin.y)
            state["cases"][-1]["attack_travel_cm"] = distance
            if cases[state["case"]][1]:
                assert distance > 30, f"Half mode stopped locomotion: {distance} cm"
            state["phase"] = 0
            return
        name, half, armed, hit, frame = current
        assert frame < 120, "Attack did not terminate"
        if frame == state["last_frame"]:
            return
        state["last_frame"] = frame
        bones, future, interpolated, alpha = actor.read_nn_future_world_pose()
        error = 0.0
        for bone, pose in zip(bones, interpolated):
            expected = pose.translation
            actual = mesh.get_socket_transform(bone, unreal.RelativeTransformSpace.RTS_WORLD).translation
            error = max(error, math.sqrt((actual.x-expected.x)**2 + (actual.y-expected.y)**2 + (actual.z-expected.z)**2))
        assert error < 0.1, f"Rendered pose differs from data by {error} cm"
        state["frames"].append({"attack": str(name), "half": half, "frame": frame, "hit": hit, "alpha": alpha, "rendered_error_cm": error})
    except Exception:
        finish(traceback.format_exc())


if not actor.get_agent_camera():
    # Some older Blueprint instances have no serialized native camera. This
    # component exists only in PIE and is not a change to the user's Blueprint.
    camera = actor.call_method("AddComponentByClass", args=(unreal.CameraComponent.static_class(), False, unreal.Transform(), False))
    offset = unreal.Vector(-370, -220, 100)
    camera.set_relative_location_and_rotation(offset, unreal.MathLibrary.find_look_at_rotation(offset, unreal.Vector(0, 0, 10)), False, True)
    command("Prophecy.SlashAuditCamera")
assert actor.get_agent_camera(), "Test agent needs a camera for camera-relative input"
actor.call_method("StopNNAttack")
actor.set_upper_nn_gaze(0.25, -0.2)
assert abs(actor.upper_nn_gaze_yaw_normalized - 0.25) < 1e-6
assert abs(actor.upper_nn_gaze_pitch_normalized + 0.2) < 1e-6
state["handle"] = unreal.register_slate_post_tick_callback(tick)
print("Moving Slash audit running", output)
