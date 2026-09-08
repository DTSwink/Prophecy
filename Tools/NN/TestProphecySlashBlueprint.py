"""PIE-only test of the actual Blueprint entry points and rendered pose.

Run with the bridge. Does not save any assets. Output includes every observed
30 Hz attack frame, finiteness, gate completion, and kinematic mesh readback.
"""
import json
import math
from pathlib import Path
import time
import traceback
import unreal

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
assert world is not None, "Start the flat map in PIE first"
actor = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)[0]
assert actor.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
mesh = actor.get_pose_reference_mesh()
mesh.visibility_based_anim_tick_option = unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES
mesh.enable_update_rate_optimizations = False
output = Path(unreal.Paths.project_dir()).resolve() / "Saved/SlashParity/blueprint_runtime.json"
cases = ["slashL", "kickR", "headbutt", "jabL", "jabR", "hookL", "hookR", "overL", "overR", "pike", "slashR", "slashLD", "slashRD", "slashLU", "slashRU", "kickL"]
state = {"case": -1, "last_frame": -1, "next_start": time.monotonic(), "handle": None, "records": [], "frames": [], "half_on": False, "half_off": False, "start_time": 0.0}


def finish(error=None):
    if state["handle"] is not None:
        unreal.unregister_slate_post_tick_callback(state["handle"])
        state["handle"] = None
    report = {"records": state["records"], "frames": state["frames"], "error": error}
    output.write_text(json.dumps(report, indent=2))
    unreal.log("Slash Blueprint audit saved " + str(output))


def tick(delta):
    try:
        now = time.monotonic()
        current = actor.call_method("GetNNAttackState")
        if not current:
            if state["start_time"]:
                state["records"].append({"attack": cases[state["case"]], "completed": True, "last_observed_frame": state["last_frame"], "saw_hit": any(f["hit"] for f in state["frames"] if f["case"] == state["case"])})
                state["start_time"] = 0.0
                state["next_start"] = now + 0.75
            if now < state["next_start"]:
                return
            state["case"] += 1
            if state["case"] >= len(cases):
                finish()
                return
            name = cases[state["case"]]
            target = actor.get_actor_transform().transform_location(unreal.Vector(-45, 110, 10))
            if name.lower().startswith("kick"):
                assert not actor.call_method("TriggerNNAttack", args=(unreal.Name(name), target, True)), "Kick incorrectly accepted half mode"
            assert actor.call_method("TriggerNNAttack", args=(unreal.Name(name), target, False)), "Trigger failed for " + name
            state["last_frame"] = -1
            state["half_on"] = state["half_off"] = False
            state["start_time"] = now
            current = actor.call_method("GetNNAttackState")
        name, half, armed, hit, frame = current
        if frame == state["last_frame"]:
            return
        state["last_frame"] = frame
        if frame > 120:
            raise RuntimeError(f"{name} did not finish after 120 policy frames")
        if str(name).lower().startswith("kick"):
            assert not actor.call_method("SetNNHalfAttackEnabled", args=(True,))
        elif frame >= 4 and not state["half_on"]:
            assert actor.call_method("SetNNHalfAttackEnabled", args=(True,))
            assert actor.call_method("GetNNAttackState")[-1] == frame, "Half toggle reset history"
            state["half_on"] = True
        elif frame >= 8 and not state["half_off"]:
            assert actor.call_method("SetNNHalfAttackEnabled", args=(False,))
            assert actor.call_method("GetNNAttackState")[-1] == frame, "Full toggle reset history"
            state["half_off"] = True
        names, future, interpolated, alpha = actor.read_nn_future_world_pose()
        mesh = actor.get_pose_reference_mesh()
        maximum = 0.0
        worst_bone = ""
        positions = {}
        for bone, predicted in zip(names, interpolated):
            position = predicted.translation
            assert all(math.isfinite(v) for v in (position.x, position.y, position.z))
            realized = mesh.get_socket_transform(bone, unreal.RelativeTransformSpace.RTS_WORLD).translation
            error = math.sqrt((position.x-realized.x)**2 + (position.y-realized.y)**2 + (position.z-realized.z)**2)
            if error > maximum:
                maximum, worst_bone = error, str(bone)
            positions[str(bone)] = [position.x, position.y, position.z]
        state["frames"].append({"case": state["case"], "attack": str(name), "frame": frame, "half": half, "armed": armed, "hit": hit, "alpha": alpha, "rendered_max_error_cm": maximum, "worst_bone": worst_bone, "positions": positions})
    except Exception:
        finish(traceback.format_exc())


actor.call_method("StopNNAttack")
state["handle"] = unreal.register_slate_post_tick_callback(tick)
print("Slash Blueprint audit running", output)
