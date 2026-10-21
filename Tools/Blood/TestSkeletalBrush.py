"""Brief owned Play: confirm actual wound hits use distinct brush radii."""
import json, pathlib, re, time, traceback, unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
le = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(), "User Play is active"
root = pathlib.Path(unreal.Paths.project_dir()).resolve()
out = root / "Saved/Diagnostics/SkeletalBloodBrush"
log = root / "Saved/Logs/GameAnimationSample3.log"
s = {"world": None, "start": time.monotonic(), "handle": None, "offset": log.stat().st_size}
def finish(error=None):
    unreal.unregister_slate_post_tick_callback(s["handle"])
    if s["world"] and ed.get_game_world() == s["world"]:
        le.editor_request_end_play()
    (out / "runtime.json").write_text(json.dumps({
        "error": error, "radii": s.get("radii"), "accepted": s.get("accepted")
    }, indent=2), encoding="utf-8")
def tick(dt):
    try:
        w = ed.get_game_world()
        if not w:
            if s["world"] or time.monotonic() - s["start"] > 30: finish("Play unavailable")
            return
        if not s["world"]:
            s["world"], s["start"] = w, time.monotonic()
            for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
                if isinstance(a, unreal.ProphecyBloodTexturePaintManager):
                    a.set_editor_property("debug_print_hits", True)
                if a.get_class().get_name().startswith("A_DecalManager_C"):
                    s["radii"] = {"skeletal": a.get_editor_property("Skeletal Brush Radius"),
                                  "other": a.get_editor_property("brush radius")}
        now = time.monotonic()
        if now - s.get("last_read", s["start"]) < 0.5: return
        s["last_read"] = now
        with log.open("rb") as f:
            f.seek(s["offset"])
            text = f.read().decode("utf-8", errors="replace")
        hits = re.findall(r"BloodPaint accepted: (\w+) slot=\d+ UV=.*?radius=([\d.]+)", text)
        skel = sorted({float(r) for c, r in hits if "SkeletalMesh" in c})
        other = sorted({float(r) for c, r in hits if "StaticMesh" in c})
        s["accepted"] = {"skeletal": skel, "static": other, "count": len(hits)}
        if (not skel or not other) and now - s["start"] < 20: return
        assert skel == [s["radii"]["skeletal"]], s["accepted"]
        assert other == [s["radii"]["other"]], s["accepted"]
        finish()
    except Exception: finish(traceback.format_exc())
s["handle"] = unreal.register_slate_post_tick_callback(tick)
le.editor_request_begin_play()
print("SKELETAL_BRUSH_TEST_STARTED")
