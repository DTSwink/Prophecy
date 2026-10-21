"""Observe the current injury setup; own Play only if none already exists."""
import pathlib, time, traceback, unreal, json
exec((pathlib.Path(unreal.Paths.project_dir()) / "Tools/Blood/InspectInjuryBlood.py").read_text(encoding="utf-8"))
le = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
blood_probe = {"owned": not bool(ed.get_game_world()), "world": ed.get_game_world(),
               "start": time.monotonic(), "handle": None, "samples": []}
def finish_blood_probe(error=None):
    unreal.unregister_slate_post_tick_callback(blood_probe["handle"])
    if blood_probe["owned"] and blood_probe["world"] and ed.get_game_world() == blood_probe["world"]:
        le.editor_request_end_play()
    (out / "probe.json").write_text(json.dumps({"error": error, "owned": blood_probe["owned"],
                                               "samples": blood_probe["samples"]}, indent=2), encoding="utf-8")
def tick_blood_probe(dt):
    try:
        world = ed.get_game_world()
        if not world:
            if blood_probe["world"] or time.monotonic() - blood_probe["start"] > 20:
                finish_blood_probe("Play ended or startup timeout")
            return
        if not blood_probe["world"]:
            blood_probe["world"] = world
            blood_probe["start"] = time.monotonic()
        elapsed = time.monotonic() - blood_probe["start"]
        if elapsed >= [1.5, 4, 8][len(blood_probe["samples"])]:
            blood_probe["samples"].append({"seconds": elapsed, "actors": capture(world, "runtime")})
        if len(blood_probe["samples"]) == 3:
            finish_blood_probe()
    except Exception:
        finish_blood_probe(traceback.format_exc())
blood_probe["handle"] = unreal.register_slate_post_tick_callback(tick_blood_probe)
if blood_probe["owned"]:
    le.editor_request_begin_play()
print("INJURY_BLOOD_PROBE_STARTED owned=" + str(blood_probe["owned"]))
