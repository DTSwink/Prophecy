"""Owned Play clock comparison; restore cap and leave every asset unchanged."""
import json, pathlib, time, traceback, unreal

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
le = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(), "User Play left untouched"
out = pathlib.Path(unreal.Paths.project_saved_dir()).resolve() / "Diagnostics/SceneClock"
out.mkdir(parents=True, exist_ok=True)
stamp = str(time.time_ns())
old_cap = unreal.SystemLibrary.get_console_variable_float_value("t.MaxFPS")
s = {"world": None, "start": time.perf_counter(), "handle": None,
     "phase": 0, "frames": 0, "rows": [], "snapshots": []}
def command(w, value):
    unreal.SystemLibrary.execute_console_command(w, value)
def snapshot(label):
    path = out / (stamp + "-" + label + ".json")
    command(s["world"], 'Prophecy.Jolt.VisualStatus "' + str(path) + '"')
    s["snapshots"].append(str(path))
def finish(error=None):
    unreal.unregister_slate_post_tick_callback(s["handle"])
    command(ed.get_game_world() or ed.get_editor_world(), f"t.MaxFPS {old_cap}")
    if s["world"] and ed.get_game_world() == s["world"]:
        le.editor_request_end_play()
    result = {"error": error, "restored_cap": old_cap, "samples": s["rows"],
              "snapshots": s["snapshots"]}
    (out / "comparison.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("SCENE_CLOCK_DONE", error, len(s["rows"]))
def tick(_):
    try:
        now = time.perf_counter()
        if now - s["start"] > 40: return finish("Timeout")
        w = ed.get_game_world()
        if not w:
            if s["world"]: return finish("Play ended externally")
            return
        if not s["world"]:
            s["world"] = w
            command(w, "getall Engine bUseFixedFrameRate")
            command(w, "getall Engine FixedFrameRate")
            command(w, "t.MaxFPS 60")
        s["frames"] += 1
        if s["frames"] == 20:
            snapshot(f"phase{s['phase']}-start")
        if s["frames"] >= 20:
            s["rows"].append({"phase": s["phase"], "frame": s["frames"],
                             "wall": now, "world": unreal.GameplayStatics.get_time_seconds(w),
                             "dt": unreal.GameplayStatics.get_world_delta_seconds(w)})
        if s["frames"] == 45:
            snapshot(f"phase{s['phase']}-end")
            if s["phase"] == 1: return finish()
            s["phase"], s["frames"] = 1, 0
            command(w, "t.MaxFPS 15")
    except Exception:
        finish(traceback.format_exc())
s["handle"] = unreal.register_slate_post_tick_callback(tick)
le.editor_request_begin_play()
print("SCENE_CLOCK_TEST_STARTED")
