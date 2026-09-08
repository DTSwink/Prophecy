"""Capture actual live attack poses, following the actor; no saved map changes."""
import json
from pathlib import Path
import time
import traceback
import unreal

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
actor = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)[0]
assert actor.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
mesh = actor.get_pose_reference_mesh()
mesh.visibility_based_anim_tick_option = unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES
mesh.enable_update_rate_optimizations = False
if not actor.get_agent_camera():
    actor.call_method("AddComponentByClass", args=(unreal.CameraComponent.static_class(), False, unreal.Transform(), False))
    unreal.SystemLibrary.execute_console_command(world, "Prophecy.SlashAuditCamera")
camera = actor.get_agent_camera()
assert camera
camera_offset = unreal.Vector(-370, -220, 100)
camera.set_relative_location_and_rotation(camera_offset, unreal.MathLibrary.find_look_at_rotation(camera_offset, unreal.Vector(0, 0, 10)), False, True)
camera.set_field_of_view(55)
unreal.GameplayStatics.get_player_controller(world, 0).set_view_target_with_blend(actor, 0)
root = Path(unreal.Paths.project_dir()).resolve() / "Saved/SlashParity"
state = {"handle": None, "case": -1, "captured": False, "resume": 0, "shots": [], "next": time.monotonic()}
cases = [("slashL", False, 7), ("slashR", True, 12), ("kickL", False, 8)]


def finish(error=None):
    unreal.GameplayStatics.set_game_paused(world, False)
    actor.stop_locomotion_input()
    if state["handle"]:
        unreal.unregister_slate_post_tick_callback(state["handle"])
        state["handle"] = None
    (root / "live_screenshots.json").write_text(json.dumps({"shots": state["shots"], "error": error}, indent=2))


def tick(delta):
    try:
        now = time.monotonic()
        if state["resume"]:
            if now < state["resume"]:
                return
            unreal.GameplayStatics.set_game_paused(world, False)
            state["resume"] = 0
        current = actor.call_method("GetNNAttackState")
        if not current:
            if now < state["next"]:
                return
            state["case"] += 1
            if state["case"] == len(cases):
                finish()
                return
            name, half, capture_frame = cases[state["case"]]
            if half:
                direction = actor.get_actor_right_vector()
                actor.set_locomotion_input(direction, False, direction, 1.0, 1.0)
            else:
                actor.stop_locomotion_input()
            target = actor.get_actor_transform().transform_location(unreal.Vector(-45, 110, 10))
            assert actor.call_method("TriggerNNAttack", args=(unreal.Name(name), target, half))
            state["captured"] = False
            current = actor.call_method("GetNNAttackState")
        name, half, armed, hit, frame = current
        if frame > 120:
            raise RuntimeError("Attack failed to complete")
        if frame >= cases[state["case"]][2] and not state["captured"]:
            unreal.GameplayStatics.set_game_paused(world, True)
            output = root / f"live_{name}_{'half' if half else 'full'}_frame{frame}.png"
            unreal.SystemLibrary.execute_console_command(world, f'HighResShot filename="{output.as_posix()}" 1280x720')
            state["shots"].append({"attack": str(name), "half": half, "frame": frame, "path": str(output)})
            state["captured"] = True
            state["resume"] = now + 1.0
            state["next"] = now + 2.0
    except Exception:
        finish(traceback.format_exc())


actor.call_method("StopNNAttack")
state["handle"] = unreal.register_slate_post_tick_callback(tick)
print("Live attack capture running")
