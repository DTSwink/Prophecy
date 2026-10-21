"""Owned short Play capture. Reads existing cut state without altering tuning."""
import json, pathlib, sys, time, traceback, unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
le = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(), "User Play is active"
out = pathlib.Path(unreal.Paths.project_saved_dir()) / "Diagnostics/SwordSkeletonPenetration"
log = pathlib.Path(unreal.Paths.project_log_dir()) / "GameAnimationSample3.log"
pen_tag = "probe-after" if "--after" in sys.argv else "probe"
pen_probe = {"start": time.monotonic(), "world": None, "handle": None, "samples": [],
             "log_offset": log.stat().st_size, "last": None}
def pen_finish(error=None):
    unreal.unregister_slate_post_tick_callback(pen_probe["handle"])
    if pen_probe["world"] and ed.get_game_world() == pen_probe["world"]:
        le.editor_request_end_play()
    with log.open("rb") as f:
        f.seek(pen_probe["log_offset"])
        text = f.read().decode("utf-8", errors="replace")
    (out / (pen_tag + "-log.txt")).write_text(text, encoding="utf-8")
    (out / (pen_tag + ".json")).write_text(json.dumps({"error": error, "samples": pen_probe["samples"]}, indent=2), encoding="utf-8")
def pen_tick(dt):
    try:
        w = ed.get_game_world()
        if w and not pen_probe["world"]:
            pen_probe["world"] = w
            pen_probe["play_start"] = time.monotonic()
        if not w:
            if pen_probe["world"] or time.monotonic() - pen_probe["start"] > 25:
                pen_finish("Play ended or startup timeout")
            return
        sample = []
        for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
            if a.get_class().get_name().startswith("A_Sword_C"):
                item = {"actor": a.get_name()}
                for p in ["active", "cuts", "actors hit", "temp bonename", "temp transform", "temp pike",
                          "process cut", "increment id cut", "current vel", "current tip vel",
                          "current location", "current rotation", "impulse cut threshold", "prints debug"]:
                    try: item[p] = str(a.get_editor_property(p))
                    except Exception: pass
                item["constraints"] = [c.get_name() for c in a.get_components_by_class(unreal.PhysicsConstraintComponent)]
                if "--after" in sys.argv:
                    try:
                        item["cut_depths"] = [a.call_method("get current depth", (cut, False)) for cut in a.get_editor_property("cuts")]
                        lib = unreal.get_default_object(unreal.load_class(None, "/Script/GameAnimationSample3.ProphecyJoltStandardPhysicsLibrary"))
                        item["native_forces"] = {c.get_name(): str(lib.call_method("GetConstraintForce", (c,)))
                                                 for c in a.get_components_by_class(unreal.PhysicsConstraintComponent)
                                                 if c.get_name() != "dont"}
                    except Exception as exc:
                        item["detail_error"] = str(exc)
                sample.append(item)
            elif isinstance(a, unreal.SkeletalMeshActor):
                c = a.skeletal_mesh_component
                sample.append({"skeleton": a.get_name(), "collision": str(c.get_collision_enabled()),
                               "object_type": str(c.get_collision_object_type()),
                               "components": [c.get_class().get_name() for c in a.get_components_by_class(unreal.ActorComponent)]})
        key = json.dumps(sample)
        if key != pen_probe["last"] and len(pen_probe["samples"]) < 250:
            pen_probe["samples"].append({"seconds": time.monotonic() - pen_probe["play_start"], "actors": sample})
            pen_probe["last"] = key
        if time.monotonic() - pen_probe["play_start"] > 4:
            pen_finish()
    except Exception:
        pen_finish(traceback.format_exc())
pen_probe["handle"] = unreal.register_slate_post_tick_callback(pen_tick)
le.editor_request_begin_play()
print("Owned four-second sword/skeleton probe started")
