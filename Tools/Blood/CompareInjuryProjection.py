"""Owned Play A/B of decal depth placement; no saved asset edits."""
import unreal, pathlib, time, traceback, json, sys
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
le = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(), "User Play is active"
out = pathlib.Path(unreal.Paths.project_saved_dir()).resolve() / "Diagnostics/InjuryBlood"
bc = {"world": None, "start": time.monotonic(), "handle": None, "originals": [], "camera": None, "phase": 0}
def bc_finish(error=None):
    unreal.unregister_slate_post_tick_callback(bc["handle"])
    for d, pos in bc["originals"]:
        d.set_world_location(pos, False, True)
    if bc["camera"]:
        bc["camera"].destroy_actor()
    if bc["world"] and ed.get_game_world() == bc["world"]:
        le.editor_request_end_play()
    (out / ("verification.json" if "--verify" in sys.argv else "comparison.json")).write_text(
        json.dumps({"error": error, "decals": len(bc["originals"]), "floor": bc.get("floor"),
                    "positions": [str(p) for d, p in bc["originals"]]}), encoding="utf-8")
def bc_tick(dt):
    try:
        w = ed.get_game_world()
        if not w:
            if bc["world"] or time.monotonic() - bc["start"] > 25:
                bc_finish("Play ended or timed out")
            return
        if not bc["world"]:
            bc["world"] = w
            bc["start"] = time.monotonic()
        if time.monotonic() - bc["start"] < 8:
            return
        if bc["phase"] == 1:
            bc["capture"].capture_scene()
            if "--verify" in sys.argv:
                unreal.RenderingLibrary.export_render_target(w, bc["rt"], str(out), "projection-fixed.png")
                bc_finish()
                return
            unreal.RenderingLibrary.export_render_target(w, bc["rt"], str(out), "projection-before.png")
            for d, p in bc["originals"]:
                d.set_world_location(unreal.Vector(p.x, p.y, -0.5), False, True)
            bc["phase"] = 2
            return
        if bc["phase"] == 2:
            bc["capture"].capture_scene()
            unreal.RenderingLibrary.export_render_target(w, bc["rt"], str(out), "projection-centered.png")
            bc_finish()
            return
        gs = unreal.get_default_object(unreal.GameplayStatics)
        pos = unreal.Vector(2220, -80, 360)
        rot = unreal.MathLibrary.find_look_at_rotation(pos, unreal.Vector(2210, 260, 0))
        tr = unreal.Transform(location=pos, rotation=rot)
        cam = gs.call_method("BeginDeferredActorSpawnFromClass", (w, unreal.SceneCapture2D, tr,
            unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN, None, unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
        bc["camera"] = gs.call_method("FinishSpawningActor", (cam, tr, unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
        c = cam.get_component_by_class(unreal.SceneCaptureComponent2D)
        c.capture_every_frame = False
        c.capture_on_movement = False
        c.capture_source = unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR
        c.fov_angle = 45
        rt = unreal.RenderingLibrary.create_render_target2d(w, 800, 700, unreal.TextureRenderTargetFormat.RTF_RGBA8)
        c.texture_target = rt
        bc["capture"], bc["rt"] = c, rt
        for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
            if a.get_actor_label() == "Floor":
                bc["floor"] = {"receives_decals": a.static_mesh_component.get_editor_property("receives_decals"),
                               "location": str(a.get_actor_location()),
                               "material": str(a.static_mesh_component.get_material(0))}
            for g in a.get_components_by_class(unreal.ProphecyFoliageDecalGridComponent):
                bc["originals"] += [(d, d.get_world_location()) for d in g.get_active_foliage_grid_decals()]
        bc["phase"] = 1
    except Exception:
        bc_finish(traceback.format_exc())
bc["handle"] = unreal.register_slate_post_tick_callback(bc_tick)
le.editor_request_begin_play()
print("INJURY_PROJECTION_COMPARISON_STARTED")
