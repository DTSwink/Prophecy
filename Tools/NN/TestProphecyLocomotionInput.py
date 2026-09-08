"""PIE-only public-node regression; no input bindings, Blueprint assets or maps are saved."""
import json
import math
from pathlib import Path
import traceback
import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
assert world, "Start PIE in testNN first"
actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
assert actors, "No Prophecy agent"
actor = actors[0]
assert actor.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
actor.set_nn_inference_enabled(True)
actor.call_method("StopNNAttack")
actor.stop_locomotion_input()
actor.set_editor_property("use_blueprint_locomotion_input", False)
output = Path(unreal.Paths.project_dir()).resolve() / "Saved/LocomotionInput/runtime.json"
output.parent.mkdir(parents=True, exist_ok=True)
zero = unreal.Vector(0, 0, 0)
forward = unreal.Vector(0, 1, 0)
right = unreal.Vector(1, 0, 0)
state = {"handle": None, "index": -1, "deadline": 0, "rows": []}


def command(value):
    unreal.SystemLibrary.execute_console_command(world, value)


def set_input(move, run=False, facing=forward, speed=1.0, turn=1.0):
    actor.set_locomotion_input(move, run, facing, speed, turn)


def read():
    result = actor.get_locomotion_state()
    assert result is not None, "Mover not registered"
    velocity, facing, running = result
    location = actor.get_actor_location()
    return {
        "velocity_cm_s": [velocity.x, velocity.y, velocity.z],
        "speed_cm_s": math.hypot(velocity.x, velocity.y),
        "facing": [facing.x, facing.y, facing.z],
        "running": running,
        "position_cm": [location.x, location.y, location.z],
    }


def held_keys():
    command("Prophecy.SlashAuditInput Z 1")
    command("Prophecy.SlashAuditInput LeftShift 1")


def release_keys():
    command("Prophecy.SlashAuditInput Z 0")
    command("Prophecy.SlashAuditInput LeftShift 0")


def finish(error=None):
    if state["handle"]:
        unreal.unregister_slate_post_tick_callback(state["handle"])
        state["handle"] = None
    release_keys()
    actor.stop_locomotion_input()
    output.write_text(json.dumps({"passed": error is None, "error": error, "cases": state["rows"]}, indent=2))
    unreal.log("Locomotion input regression saved " + str(output))


def validate(name, row):
    speed = row["speed_cm_s"]
    velocity = row["velocity_cm_s"]
    facing = row["facing"]
    if name == "native_keys_disabled":
        assert speed < 0.1 and not row["running"], row
    elif name == "walk_persistent":
        assert abs(speed - 200.001788) < 1.0 and velocity[1] > 199 and not row["running"], row
    elif name == "run_only_setter":
        assert abs(speed - 500.0) < 2.0 and velocity[1] > 498 and row["running"], row
    elif name in ("stop_brakes", "yaw_only", "speed_scale_zero", "override_disabled"):
        assert speed < 0.1, row
        if name == "yaw_only":
            assert facing[0] > 0.999, row
    elif name == "half_stick":
        assert abs(speed - 100.000894) < 1.0 and velocity[1] > 99, row
    elif name == "half_speed_scale":
        assert abs(speed - 100.000894) < 1.0 and velocity[1] > 99, row
    elif name == "strafe":
        assert velocity[0] > 50 and abs(velocity[1]) < 1 and facing[1] > 0.999, row
    elif name == "turn_scale_zero":
        assert speed < 0.1 and facing[0] > 0.999, row
    elif name == "diagonal_clamp":
        request = actor.get_locomotion_input()
        move = request.world_move_input
        assert abs(math.hypot(move.x, move.y) - 1.0) < 1e-6 and move.z == 0, request
        assert speed > 100 and abs(velocity[0] - velocity[1]) < 1, row
    elif name == "release_preserves_facing":
        assert speed < 0.1 and abs(facing[0] - math.sqrt(0.5)) < 0.001 and abs(facing[1] - math.sqrt(0.5)) < 0.001, row


cases = [
    ("native_keys_disabled", 1.0, held_keys),
    ("walk_persistent", 2.5, lambda: (release_keys(), set_input(forward))),
    ("run_only_setter", 3.0, lambda: actor.set_locomotion_running(True)),
    ("stop_brakes", 2.5, actor.stop_locomotion_input),
    ("half_stick", 2.5, lambda: set_input(unreal.Vector(0, 0.5, 123))),
    ("half_speed_scale", 2.0, lambda: set_input(forward, speed=0.5)),
    ("strafe", 2.5, lambda: set_input(right)),
    ("yaw_only", 2.5, lambda: set_input(zero, facing=right)),
    ("turn_scale_zero", 1.0, lambda: set_input(zero, facing=forward, turn=0)),
    ("speed_scale_zero", 2.5, lambda: set_input(forward, speed=0)),
    ("diagonal_clamp", 3.0, lambda: set_input(unreal.Vector(1, 1, 99), facing=unreal.Vector(1, 1, 0))),
    ("release_preserves_facing", 2.5, actor.stop_locomotion_input),
    ("override_disabled", 1.0, lambda: actor.set_editor_property("use_blueprint_locomotion_input", False)),
]


def tick(delta):
    try:
        now = unreal.GameplayStatics.get_time_seconds(world)
        if now < state["deadline"]:
            return
        if state["index"] >= 0:
            name = cases[state["index"]][0]
            row = read()
            row["case"] = name
            state["rows"].append(row)
            validate(name, row)
        state["index"] += 1
        if state["index"] == len(cases):
            finish()
            return
        _, seconds, action = cases[state["index"]]
        action()
        state["deadline"] = now + seconds
    except Exception:
        finish(traceback.format_exc())


state["handle"] = unreal.register_slate_post_tick_callback(tick)
print("Public locomotion input regression started; approximately 30 game seconds")
