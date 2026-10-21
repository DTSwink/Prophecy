"""Owned-Play coverage of automatic callback discovery and activation/reuse."""
import json, pathlib, time, traceback, unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
le = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(), "User Play is active"
out = pathlib.Path(unreal.Paths.project_saved_dir()).resolve() / "Diagnostics/BloodAutoCallbacks"
state = {"world": None, "handle": None, "start": time.monotonic(), "phase": 0, "frames": 0,
         "components": {}, "results": [], "owned_actors": []}
def stop(error=None):
    unreal.unregister_slate_post_tick_callback(state["handle"])
    if state["world"] and ed.get_game_world() == state["world"]:
        le.editor_request_end_play()
    (out / "runtime.json").write_text(json.dumps({"error": error, "results": state["results"]}, indent=2), encoding="utf-8")
def export_component(c):
    t = unreal.AssetExportTask()
    t.object, t.filename = c, str(out / "component-check.txt")
    t.exporter = unreal.ObjectExporterT3D()
    t.automated, t.prompt, t.replace_identical = True, False, True
    assert unreal.Exporter.run_asset_export_task(t)
    text = (out / "component-check.txt").read_text(encoding="utf-8-sig")
    return next((line for line in text.splitlines() if "OverrideParameters=" in line), "")
def check(name, c, expected):
    text = export_component(c)
    if expected:
        ok = (":PersistentLevel." + expected.get_name() + "'") in text and "UObjects=" in text
    else:
        ok = "User.decal_callback" not in text
    state["results"].append({"case": name, "passed": ok, "component": c.get_name(),
                              "expected": expected.get_path_name() if expected else None,
                              "callback_store": text[text.find("UObjects="):] if "UObjects=" in text else ""})
    assert ok, name
def spawn_actor(cls, w):
    gs = unreal.get_default_object(unreal.GameplayStatics)
    tr = unreal.Transform(location=unreal.Vector(0, 0, -10000))
    a = gs.call_method("BeginDeferredActorSpawnFromClass", (w, cls, tr,
        unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN, None, unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
    a = gs.call_method("FinishSpawningActor", (a, tr, unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
    state["owned_actors"].append(a)
    return a
def spawn(name, active=False, pool=unreal.NCPoolMethod.NONE, asset=None):
    c = unreal.NiagaraFunctionLibrary.spawn_system_at_location(
        state["world"], asset or state["asset"], unreal.Vector(0, 0, -10000),
        auto_destroy=False, auto_activate=active, pooling_method=pool, pre_cull_check=False)
    assert c, name
    if not asset:
        c.set_variable_float("User.spawn rate", 0)
    state["components"][name] = c
    return c
def tick(dt):
    try:
        if time.monotonic() - state["start"] > 35:
            raise RuntimeError("Callback test timeout")
        w = ed.get_game_world()
        if not w:
            if state["world"]: stop("Play ended")
            return
        state["world"] = w
        state["frames"] += 1
        if state["phase"] == 0 and state["frames"] >= 3:
            actors = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor)
            manager = next(a for a in actors if a.get_class().get_name().startswith("A_DecalManager_C"))
            state["manager"] = manager
            state["asset"] = unreal.load_asset("/Game/_mygame/blood2/NS_bloodsplat")
            for a in actors:
                if isinstance(a, unreal.NiagaraActor):
                    c = a.get_component_by_class(unreal.NiagaraComponent)
                    if c.get_asset() == state["asset"]:
                        check("placed actor resolves to PIE manager", c, manager)
                        c.set_paused(True)  # Diagnostic Play only; avoid user's high preview emission rate.
            spawn("auto-activated spawn", True)
            spawn("delayed activation")
            wrong = spawn("Blueprint asset corrected")
            wrong.set_variable_object("User.decal_callback", unreal.load_asset("/Game/_mygame/blood2/A_DecalManager"))
            explicit = spawn("explicit valid callback preserved")
            state["explicit"] = spawn_actor(unreal.ProphecyBloodStainRenderer, w)
            explicit.set_variable_object("User.decal_callback", state["explicit"])
            spawn("pooled first activation", pool=unreal.NCPoolMethod.MANUAL_RELEASE)
            anchor = state["owned_actors"][0].get_editor_property("root_component")
            attached = unreal.NiagaraFunctionLibrary.spawn_system_attached(
                state["asset"], anchor, "", unreal.Vector(), unreal.Rotator(),
                unreal.AttachLocation.KEEP_RELATIVE_OFFSET, False, False, unreal.NCPoolMethod.NONE, False)
            attached.set_variable_float("User.spawn rate", 0)
            state["components"]["attached component"] = attached
            fire = unreal.load_asset("/Game/_mygame/assets/Fire/NS_Fire")
            assert fire
            spawn("unrelated system untouched", asset=fire)
            state["phase"], state["frames"] = 1, 0
        elif state["phase"] == 1 and state["frames"] >= 3:
            for name, c in state["components"].items():
                if name not in ["auto-activated spawn", "unrelated system untouched"]:
                    c.activate(True)
            state["phase"], state["frames"] = 2, 0
        elif state["phase"] == 2 and state["frames"] >= 3:
            for name, c in state["components"].items():
                expected = None if name == "unrelated system untouched" else (
                    state["explicit"] if name == "explicit valid callback preserved" else state["manager"])
                check(name, c, expected)
            pool = state["components"]["pooled first activation"]
            state["pooled_name"] = pool.get_name()
            pool.release_to_pool()
            state["phase"], state["frames"] = 3, 0
        elif state["phase"] == 3 and state["frames"] >= 3:
            c = spawn("pooled reuse", pool=unreal.NCPoolMethod.MANUAL_RELEASE)
            state["results"].append({"case": "same pool component reused",
                                     "passed": c.get_name() == state["pooled_name"]})
            assert c.get_name() == state["pooled_name"]
            c.set_variable_object("User.decal_callback", None)
            c.activate(True)
            state["phase"], state["frames"] = 4, 0
        elif state["phase"] == 4 and state["frames"] >= 3:
            check("pooled reuse rebinds cleared callback", state["components"]["pooled reuse"], state["manager"])
            stop()
    except Exception:
        stop(traceback.format_exc())
state["handle"] = unreal.register_slate_post_tick_callback(tick)
le.editor_request_begin_play()
print("AUTO_CALLBACK_TEST_STARTED")
