"""Press Play with the user's exact Slow Start setup; never override its startup cap."""
import json, pathlib, time, traceback, unreal, sys
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
le = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(), "User Play left untouched"
out = pathlib.Path(unreal.Paths.project_saved_dir()) / "Diagnostics/SceneClock"
name = sys.argv[1] if len(sys.argv) > 1 else "slow-before"
old_cap = unreal.SystemLibrary.get_console_variable_float_value("t.MaxFPS")
s = {"world": None, "handle": None, "start": time.perf_counter(), "rows": [], "swords": []}
def finish(error=None):
    unreal.unregister_slate_post_tick_callback(s["handle"])
    if s["world"] and ed.get_game_world() == s["world"]:
        le.editor_request_end_play()
    s["error"], s["ending"] = error, time.perf_counter()
    s["cleanup"] = unreal.register_slate_post_tick_callback(cleanup)
def cleanup(_):
    if ed.get_game_world() == s["world"] and time.perf_counter() - s["ending"] < 10: return
    unreal.unregister_slate_post_tick_callback(s["cleanup"])
    end_cap = unreal.SystemLibrary.get_console_variable_float_value("t.MaxFPS")
    if not ed.get_game_world():
        # Restore only after observing the sword's own End Play cleanup.
        unreal.FixedFrameRateLibrary.set_fixed_frame_rate_runtime(60.0)
        unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), f"t.MaxFPS {old_cap}")
    (out / (name + ".json")).write_text(json.dumps({"error": s["error"], "swords": s["swords"],
        "rows": s["rows"], "end_play_cap_before_restore": end_cap,
        "restored_cap": old_cap}, indent=2), encoding="utf-8")
    print("SLOW_START_PROBE_DONE", name, s["error"])
def tick(_):
    try:
        now = time.perf_counter()
        if now - s["start"] > 30: return finish("Timeout")
        w = ed.get_game_world()
        if not w:
            if s["world"]: return finish("Play ended externally")
            return
        if not s["world"]:
            s["world"] = w
            for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
                if a.get_class().get_name().startswith("A_Sword_C"):
                    s["swords"].append({"name": a.get_name(), "start_slow": a.get_editor_property("start slow fps"),
                                        "slow_fps": a.get_editor_property("slow fps")})
            for command in ["getall Engine bUseFixedFrameRate", "getall Engine FixedFrameRate"]:
                unreal.SystemLibrary.execute_console_command(w, command)
        s["rows"].append({"wall": now, "dt": unreal.GameplayStatics.get_world_delta_seconds(w),
                         "world": unreal.GameplayStatics.get_time_seconds(w),
                         "cap": unreal.SystemLibrary.get_console_variable_float_value("t.MaxFPS")})
        if len(s["rows"]) >= 16: finish()
    except Exception: finish(traceback.format_exc())
s["handle"] = unreal.register_slate_post_tick_callback(tick)
le.editor_request_begin_play()
print("SLOW_START_PROBE_STARTED", name)
