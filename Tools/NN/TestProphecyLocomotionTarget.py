"""Short PIE-only check that target readback is distinct from current motion."""
import json
from pathlib import Path
import traceback
import unreal

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
assert world
actor = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)[0]
actor.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
actor.set_nn_inference_enabled(True)
actor.call_method("StopNNAttack")
# Isolate the getter from user-authored Blueprint Tick input; only the PIE copy changes.
was_ticking = actor.is_actor_tick_enabled()
actor.set_actor_tick_enabled(False)
actor.stop_locomotion_input()
state = {"handle": None, "phase": 0, "deadline": unreal.GameplayStatics.get_time_seconds(world) + 1,
         "saw_turn_gap": False, "saw_brake_gap": False, "rows": [], "stop_target": None}


def finish(error=None):
    if state["handle"]:
        unreal.unregister_slate_post_tick_callback(state["handle"])
        state["handle"] = None
    actor.stop_locomotion_input()
    actor.set_actor_tick_enabled(was_ticking)
    output = Path(unreal.Paths.project_dir()).resolve() / "Saved/LocomotionInput/target_runtime.json"
    output.write_text(json.dumps({"passed": error is None, "error": error,
        "turn_target_differs_from_current": state["saw_turn_gap"],
        "zero_target_while_braking": state["saw_brake_gap"], "samples": state["rows"]}, indent=2))
    print("Target readback regression", "passed" if error is None else error)


def tick(delta):
    try:
        now = unreal.GameplayStatics.get_time_seconds(world)
        if state["phase"] == 0:
            if now < state["deadline"]:
                return
            target = actor.call_method("GetLocomotionTarget")
            assert target is not None
            assert target[1] == 0
            actor.set_locomotion_input(unreal.Vector(1, 0, 0), False, unreal.Vector(1, 0, 0), 1, 1)
            state["phase"] = 1
            state["deadline"] = now + 2
            return
        target_velocity, target_speed, target_facing, run = actor.call_method("GetLocomotionTarget")
        velocity, facing, current_run = actor.get_locomotion_state()
        if len(state["rows"]) < 180:
            state["rows"].append({"phase": state["phase"], "target_speed": target_speed,
                "speed": velocity.length(), "target_facing": [target_facing.x, target_facing.y],
                "facing": [facing.x, facing.y], "target_velocity": [target_velocity.x, target_velocity.y]})
        if state["phase"] == 1:
            if target_speed > 0:
                assert target_facing.x > 0.999 and abs(target_facing.y) < 1e-6
                assert target_velocity.x > 0 and abs(target_velocity.y) < 1e-6, target_velocity
                state["saw_turn_gap"] |= facing.x < 0.98
            if now >= state["deadline"]:
                assert abs(target_speed - 200.001788) < 0.1 and not run
                assert state["saw_turn_gap"], "Target should point to new heading before current facing catches up"
                actor.stop_locomotion_input()
                state["phase"] = 2
                state["deadline"] = now + 1
        elif state["phase"] == 2:
            if target_speed == 0:
                state["saw_brake_gap"] |= velocity.length() > 0.1
                assert target_facing.x > 0.999
            if now >= state["deadline"]:
                assert state["saw_brake_gap"], "Stop goal should be zero while current speed is still braking"
                assert target_speed == 0 and velocity.length() < 0.1
                finish()
    except Exception:
        finish(traceback.format_exc())


state["handle"] = unreal.register_slate_post_tick_callback(tick)
print("Target readback regression started (4 game seconds)")
