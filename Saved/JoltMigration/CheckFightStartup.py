"""Brief automatic initialization check, without screenshots or visual assessment."""
import json
import sys
import time
from datetime import datetime
from pathlib import Path
import unreal

root = Path(unreal.Paths.project_dir()).resolve()
output = root / "Saved/JoltMigration/FightStartup-20260910"
report_path = output / ("startup-" + datetime.now().strftime("%H%M%S") + ".json")
assert (output / "placement.json").exists() and not report_path.exists()
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not levels.is_in_play_in_editor(), "Preserve an existing user play session"
startup_check_state = {"handle": None, "deadline": time.monotonic() + 60.0, "frames": 0, "equip_results": None}
equip_for_check = '--equip-swords' in sys.argv

def check_fight_startup(delta_seconds):
    state = startup_check_state
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if world and levels.is_in_play_in_editor():
        state["frames"] += 1
        if equip_for_check and state["frames"] == 6:
            agents = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
            state["equip_results"] = [a.equip_sword(True) for a in agents]
    if state["frames"] < 12 and time.monotonic() < state["deadline"]:
        return
    unreal.unregister_slate_post_tick_callback(state["handle"])
    state["handle"] = None
    report = {"success": False, "visual_test": False, "error": "", "observed_editor_frames": state["frames"],
              "explicit_test_equip": equip_for_check, "equip_results": state["equip_results"]}
    try:
        assert world and levels.is_in_play_in_editor(), "PIE did not start"
        cls = unreal.load_class(None, "/Script/GameAnimationSample3.ProphecyJoltFightSetup")
        setups = unreal.GameplayStatics.get_all_actors_of_class(world, cls)
        assert len(setups) == 1
        setup = setups[0]
        report["started_agents"] = setup.get_editor_property("StartedAgentCount")
        report["startup_error"] = setup.get_editor_property("LastError")
        scene = setup.get_editor_property("SceneCollision")
        report["scene_enabled"] = scene.is_scene_collision_enabled()
        report["scene_error"] = scene.get_last_error()
        agents = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
        report["agents"] = [{"name": a.get_name(), "jolt": a.is_jolt_physical_animation_enabled(),
                             "mode": str(a.get_simulation_mode()), "macd": a.is_macd_enabled(),
                             "mesh": a.get_pose_reference_mesh().get_path_name(),
                             "asset": a.get_pose_reference_mesh().get_editor_property("skeletal_mesh_asset").get_path_name(),
                             "anim": str(a.get_pose_reference_mesh().get_anim_instance()),
                             "chaos_sim": a.get_pose_reference_mesh().is_any_simulating_physics(),
                             "collision": str(a.get_pose_reference_mesh().get_collision_enabled())} for a in agents]
        native_path = Path.home() / ".codex/tmp/ProphecyJolt" / ("FightStartup-20260910-" + report_path.stem + "-native.json")
        assert not native_path.exists()
        unreal.SystemLibrary.execute_console_command(world, "Prophecy.Jolt.VisualStatus " + native_path.as_posix())
        report["native"] = json.loads(native_path.read_text(encoding="utf-8-sig"))
        assert len(agents) == 2 and report["started_agents"] == 2
        assert all(a["jolt"] and not a["macd"] for a in report["agents"])
        assert all(not a["chaos_sim"] and "QUERY_ONLY" in a["collision"] for a in report["agents"])
        assert report["scene_enabled"] and not report["scene_error"] and not report["startup_error"]
        native = report["native"]
        assert native["initialized"] and not native["faulted"] and not native["world_error"]
        assert native["completed_steps"] > 0 and native["scene_bodies"] > 0
        assert all(not a.get("stopped", False) and not a.get("error") and not a.get("sword_error") for a in native["agents"])
        assert all(a.get("sword_jolt", False) for a in native["agents"] if a.get("sword"))
        if equip_for_check:
            assert state["equip_results"] == [True, True]
            assert all(a.get('sword') and a.get('sword_jolt') for a in native['agents'])
            assert native['grip_joints'] == 2
        report["success"] = True
    except Exception as error:
        report["error"] = repr(error)
    finally:
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if levels.is_in_play_in_editor():
            levels.editor_request_end_play()
        print("FIGHT_STARTUP_CHECK " + json.dumps(report))

startup_check_state["handle"] = unreal.register_slate_post_tick_callback(check_fight_startup)
levels.editor_request_begin_play()
print("BRIEF_STARTUP_CHECK_REQUESTED")
