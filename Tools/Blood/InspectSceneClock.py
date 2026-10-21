"""Read current clock settings and briefly sample existing Play without changing it."""
import json, pathlib, time, unreal

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
out = pathlib.Path(unreal.Paths.project_saved_dir()) / "Diagnostics/SceneClock"
out.mkdir(parents=True, exist_ok=True)
world = ed.get_game_world()
editor_world = ed.get_editor_world()
result = {"editor_world": editor_world.get_path_name() if editor_world else None,
          "play": bool(world), "samples": [],
          "max_fps": unreal.SystemLibrary.get_console_variable_float_value("t.MaxFPS")}
for path in ["/Engine/Transient.UnrealEdEngine_0", "/Engine/Transient.EditorEngine_0"]:
    engine = unreal.find_object(None, path)
    if engine:
        result["engine"] = {"path": path}
        for name in ["use_fixed_frame_rate", "fixed_frame_rate", "smooth_frame_rate"]:
            try: result["engine"][name] = engine.get_editor_property(name)
            except Exception as e: result["engine"][name] = str(e)
physics = unreal.get_default_object(unreal.PhysicsSettings)
result["physics"] = {}
for name in ["tick_physics_async", "substepping", "max_physics_delta_time", "max_substep_delta_time", "max_substeps"]:
    try: result["physics"][name] = physics.get_editor_property(name)
    except Exception as e: result["physics"][name] = str(e)
state = {"start": time.perf_counter(), "last": None, "handle": None}
def finish():
    if state["handle"]: unreal.unregister_slate_post_tick_callback(state["handle"])
    (out / "current.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("SCENE_CLOCK", json.dumps({k: v for k, v in result.items() if k != "samples"}), "samples", len(result["samples"]))
def tick(_):
    now = time.perf_counter()
    if ed.get_game_world() != world or now - state["start"] > 3:
        return finish()
    result["samples"].append({
        "wall_delta": now - state["last"] if state["last"] else None,
        "world_delta": unreal.GameplayStatics.get_world_delta_seconds(world),
        "world_time": unreal.GameplayStatics.get_time_seconds(world),
        "paused": unreal.GameplayStatics.is_game_paused(world),
    })
    state["last"] = now
if world: state["handle"] = unreal.register_slate_post_tick_callback(tick)
else: finish()
