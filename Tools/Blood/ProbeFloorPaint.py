"""Owned diagnostic Play: actual wound paint statistics and floor mask."""
import json, pathlib, time, traceback, unreal, sys
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
le = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(), "User Play is active"
out = pathlib.Path(unreal.Paths.project_saved_dir()).resolve() / "Diagnostics/FloorPaintFix"
out.mkdir(parents=True, exist_ok=True)
s = {"world": None, "start": time.monotonic(), "handle": None, "rows": []}
def export(obj, name):
    t = unreal.AssetExportTask()
    t.object, t.filename = obj, str(out / (name + ".txt"))
    t.exporter = unreal.ObjectExporterT3D()
    t.automated, t.prompt, t.replace_identical = True, False, True
    unreal.Exporter.run_asset_export_task(t)
def finish(error=None):
    unreal.unregister_slate_post_tick_callback(s["handle"])
    if s["world"] and ed.get_game_world() == s["world"]:
        le.editor_request_end_play()
    (out / "probe.json").write_text(json.dumps({"error": error, "rows": s["rows"]}, indent=2), encoding="utf-8")
def tick(dt):
    try:
        w = ed.get_game_world()
        if not w:
            if s["world"] or time.monotonic() - s["start"] > 30: finish("No Play world")
            return
        if not s["world"]:
            s["world"], s["start"] = w, time.monotonic()
            for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.ProphecyBloodTexturePaintManager):
                a.set_editor_property("debug_log_rejected_hits", True)
                a.set_editor_property("debug_print_hits", True)
        if time.monotonic() - s["start"] < 6: return
        floor_comp = None
        decal_points = []
        for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
            if isinstance(a, unreal.ProphecyBloodTexturePaintManager):
                s["rows"].append({"paint": a.get_debug_stats_string(), "actor": a.get_name()})
                export(a, "paint-manager")
            if a.get_actor_label() == "Floor":
                c = a.get_component_by_class(unreal.StaticMeshComponent)
                floor_comp = c
                m = c.get_material(0)
                s["rows"].append({"floor": a.get_path_name(), "transform": str(a.get_actor_transform()),
                                  "mesh": c.static_mesh.get_path_name(), "material": m.get_path_name()})
                export(a, "floor")
                export(m, "floor-material")
                if isinstance(m, unreal.MaterialInstanceDynamic):
                    rt = m.get_texture_parameter_value("BloodMaskRT")
                    if rt:
                        unreal.RenderingLibrary.export_render_target(w, rt, str(out), "floor-mask.png")
            for g in a.get_components_by_class(unreal.ProphecyFoliageDecalGridComponent):
                for d in g.get_active_foliage_grid_decals():
                    decal_points.append(d.get_world_location())
                    if "--capture" in sys.argv: d.set_visibility(False)
        if "--capture" in sys.argv and floor_comp:
            # Only owned Play: exclude foliage projectors to prove these are surface stains.
            center = sum(decal_points, unreal.Vector()) / len(decal_points) if decal_points else unreal.Vector(2210, 260, 0)
            pos = center + unreal.Vector(180, -220, 380)
            tr = unreal.Transform(location=pos, rotation=unreal.MathLibrary.find_look_at_rotation(pos, center))
            gs = unreal.get_default_object(unreal.GameplayStatics)
            cam = gs.call_method("BeginDeferredActorSpawnFromClass", (w, unreal.SceneCapture2D, tr,
                unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN, None, unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
            cam = gs.call_method("FinishSpawningActor", (cam, tr, unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
            cap = cam.get_component_by_class(unreal.SceneCaptureComponent2D)
            cap.capture_every_frame = cap.capture_on_movement = False
            cap.capture_source = unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR
            cap.fov_angle = 45
            rt = unreal.RenderingLibrary.create_render_target2d(w, 800, 700, unreal.TextureRenderTargetFormat.RTF_RGBA8)
            cap.texture_target = rt
            mid = floor_comp.get_material(0)
            for name, material, intensity in [
                ("painted", mid, 1),
                ("empty-mask", mid, 0),
                ("original", unreal.load_asset("/Engine/OpenWorldTemplate/LandscapeMaterial/MI_ProcGrid"), None)]:
                floor_comp.set_material(0, material)
                if intensity is not None: mid.set_scalar_parameter_value("BloodIntensity", intensity)
                cap.capture_scene()
                unreal.RenderingLibrary.export_render_target(w, rt, str(out), name + ".png")
            floor_comp.set_material(0, mid)
            mid.set_scalar_parameter_value("BloodIntensity", 1)
            cam.destroy_actor()
        finish()
    except Exception: finish(traceback.format_exc())
s["handle"] = unreal.register_slate_post_tick_callback(tick)
le.editor_request_begin_play()
print("FLOOR_PAINT_PROBE_STARTED")
