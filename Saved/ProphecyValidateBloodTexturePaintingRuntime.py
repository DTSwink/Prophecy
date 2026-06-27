import json
import os
import random
import time
import traceback

import unreal


OUT_DIR = os.path.normpath(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "BloodTexturePainting"))
TAG = "ProphecyBloodTexturePaintingRuntimeValidation"
OLD_ASSET_TAG = "ProphecyBloodTexturePaintingValidation"
MODE = globals().get("PROPHECY_BLOOD_RUNTIME_MODE", "setup_debug")
PERF_SHOT = globals().get("PROPHECY_BLOOD_PERF_SHOT", "stress")


def log(message):
    unreal.log(f"[ProphecyBloodTexturePaintingRuntime] {message}")


def world():
    try:
        return unreal.EditorLevelLibrary.get_editor_world()
    except Exception:
        return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def load_asset(path):
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if not asset:
        raise RuntimeError(f"Missing asset: {path}")
    return asset


def add_tag(actor):
    actor.tags = list(actor.tags) + [TAG]
    return actor


def set_label(actor, label):
    try:
        actor.set_actor_label(label)
    except Exception:
        pass


def destroy_old_validation_actors():
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        tags = [str(t) for t in actor.tags]
        if TAG in tags or OLD_ASSET_TAG in tags:
            unreal.EditorLevelLibrary.destroy_actor(actor)


def find_validation_actor(label):
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        if TAG in [str(t) for t in actor.tags]:
            try:
                if actor.get_actor_label() == label:
                    return actor
            except Exception:
                pass
    return None


def spawn_camera(label, location, rotation, fov=38.0):
    actor = add_tag(unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.CameraActor, location, rotation, transient=False))
    set_label(actor, label)
    try:
        actor.camera_component.set_editor_property("field_of_view", fov)
    except Exception:
        pass
    return actor


def spawn_stats_plate(label, text, location, rotation, world_size=18.0):
    actor = add_tag(unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.TextRenderActor, location, rotation, transient=False))
    set_label(actor, label)
    component = actor.get_component_by_class(unreal.TextRenderComponent)
    try:
        component.set_text(text)
        component.set_editor_property("world_size", world_size)
        component.set_text_render_color(unreal.Color(255, 245, 230, 255))
        component.set_editor_property("horizontal_alignment", unreal.HorizTextAligment.EHTA_LEFT)
    except Exception:
        pass
    return actor


def request_screenshot(path, camera):
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass

    unreal.AutomationLibrary.finish_loading_before_screenshot()
    unreal.AutomationLibrary.take_high_res_screenshot(
        1280,
        720,
        path,
        camera,
        False,
        False,
        unreal.ComparisonTolerance.LOW,
        "Prophecy runtime blood texture painting validation",
        0.1,
        True,
    )
    log(f"Requested screenshot: {path}")


def setup_runtime_scene_and_capture_debug():
    os.makedirs(OUT_DIR, exist_ok=True)
    destroy_old_validation_actors()
    w = world()

    clean_material = load_asset("/Game/Prophecy/BloodTexturePainting/M_Test_BloodMaskBlend_Clean.M_Test_BloodMaskBlend_Clean")
    brush_material = load_asset("/Game/Prophecy/BloodTexturePainting/M_BloodBrush_Circle.M_BloodBrush_Circle")
    blood_material = load_asset("/Game/Prophecy/BloodTexturePainting/M_BloodPaint_RuntimeTest.M_BloodPaint_RuntimeTest")
    cube_mesh = load_asset("/Engine/BasicShapes/Cube.Cube")

    target = add_tag(unreal.EditorLevelLibrary.spawn_actor_from_object(cube_mesh, unreal.Vector(0.0, 0.0, 130.0), unreal.Rotator(0.0, 0.0, 0.0), transient=False))
    set_label(target, "BTP_Runtime_Target")
    target.set_actor_scale3d(unreal.Vector(3.0, 0.08, 2.0))
    target_component = target.get_component_by_class(unreal.StaticMeshComponent)
    target_component.set_material(0, clean_material)
    target_component.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    target_component.set_collision_profile_name("BlockAll")

    manager = add_tag(unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.ProphecyBloodTexturePaintManager, unreal.Vector(0.0, -180.0, 80.0), unreal.Rotator(0.0, 0.0, 0.0), transient=False))
    set_label(manager, "BTP_Runtime_Manager")
    manager.brush_material = brush_material
    manager.default_blood_material_template = blood_material
    manager.paint_uv_channel = 0
    manager.require_paintable_tag = False
    manager.default_brush_size_pixels = 128.0
    manager.flush_every_tick = False
    manager.debug_print_hits = True
    manager.debug_draw_hit_locations = False
    manager.set_debug_show_mask_on_painted_materials(True)

    light = add_tag(unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(-260.0, -360.0, 520.0), unreal.Rotator(0.0, -45.0, -25.0), transient=False))
    set_label(light, "BTP_Runtime_KeyLight")
    try:
        light.get_component_by_class(unreal.DirectionalLightComponent).set_editor_property("intensity", 4.0)
    except Exception:
        pass

    camera = spawn_camera("BTP_Runtime_Camera", unreal.Vector(0.0, -560.0, 132.0), unreal.Rotator(0.0, -1.0, 90.0), 34.0)

    hit = unreal.SystemLibrary.line_trace_single(
        w,
        unreal.Vector(0.0, -520.0, 130.0),
        unreal.Vector(0.0, 180.0, 130.0),
        unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
        True,
        [manager],
        unreal.DrawDebugTrace.NONE,
        True,
    )
    if not hit:
        raise RuntimeError("Runtime validation trace missed the target cube")

    accepted = manager.try_paint_from_hit(hit, 30.0, 1.0, -1)
    if not accepted:
        raise RuntimeError("TryPaintFromHit rejected the validation hit")

    manager.flush_pending_blood_stamps()
    rt = manager.get_first_paint_render_target()
    if not rt:
        raise RuntimeError("Manager did not create a paint render target")

    unreal.RenderingLibrary.export_render_target(w, rt, OUT_DIR, "M_C_RT_after_first_hit.png")
    log(f"Exported RT: {os.path.join(OUT_DIR, 'M_C_RT_after_first_hit.png')}")
    log(manager.get_debug_stats_string())

    unreal.EditorLevelLibrary.editor_invalidate_viewports()
    request_screenshot(os.path.join(OUT_DIR, "M_C_Mesh_debug_mask.png"), camera)


def ensure_nanite_cube_asset():
    asset_path = "/Game/Prophecy/BloodTexturePainting/SM_BloodPaint_NaniteCube"
    if not unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        mesh = unreal.EditorAssetLibrary.duplicate_asset("/Engine/BasicShapes/Cube.Cube", asset_path)
    else:
        mesh = unreal.EditorAssetLibrary.load_asset(asset_path)

    if not mesh:
        raise RuntimeError("Could not create/load SM_BloodPaint_NaniteCube")

    subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    settings = subsystem.get_nanite_settings(mesh)
    settings.set_editor_property("enabled", True)
    settings.set_editor_property("fallback_relative_error", 0.0)
    settings.set_editor_property("fallback_percent_triangles", 1.0)
    settings.set_editor_property("keep_percent_triangles", 1.0)
    subsystem.set_nanite_settings(mesh, settings, True)
    unreal.EditorAssetLibrary.save_loaded_asset(mesh)
    log(f"Nanite test mesh settings: {subsystem.get_nanite_settings(mesh)}")
    return mesh


def setup_nanite_scene_and_capture():
    os.makedirs(OUT_DIR, exist_ok=True)
    destroy_old_validation_actors()
    w = world()

    clean_material = load_asset("/Game/Prophecy/BloodTexturePainting/M_Test_BloodMaskBlend_Clean.M_Test_BloodMaskBlend_Clean")
    brush_material = load_asset("/Game/Prophecy/BloodTexturePainting/M_BloodBrush_Circle.M_BloodBrush_Circle")
    blood_material = load_asset("/Game/Prophecy/BloodTexturePainting/M_BloodPaint_RuntimeTest.M_BloodPaint_RuntimeTest")
    nanite_mesh = ensure_nanite_cube_asset()

    target = add_tag(unreal.EditorLevelLibrary.spawn_actor_from_object(nanite_mesh, unreal.Vector(0.0, 0.0, 130.0), unreal.Rotator(0.0, 0.0, 0.0), transient=False))
    set_label(target, "BTP_Nanite_Target")
    target.set_actor_scale3d(unreal.Vector(3.0, 0.08, 2.0))
    target_component = target.get_component_by_class(unreal.StaticMeshComponent)
    target_component.set_material(0, clean_material)
    target_component.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    target_component.set_collision_profile_name("BlockAll")

    manager = add_tag(unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.ProphecyBloodTexturePaintManager, unreal.Vector(0.0, -180.0, 80.0), unreal.Rotator(0.0, 0.0, 0.0), transient=False))
    set_label(manager, "BTP_Nanite_Manager")
    manager.brush_material = brush_material
    manager.default_blood_material_template = blood_material
    manager.paint_uv_channel = 0
    manager.require_paintable_tag = False
    manager.default_brush_size_pixels = 128.0
    manager.flush_every_tick = False
    manager.debug_print_hits = True
    manager.debug_draw_hit_locations = False
    manager.set_debug_show_mask_on_painted_materials(False)

    light = add_tag(unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(-260.0, -360.0, 520.0), unreal.Rotator(0.0, -45.0, -25.0), transient=False))
    set_label(light, "BTP_Nanite_KeyLight")
    try:
        light.get_component_by_class(unreal.DirectionalLightComponent).set_editor_property("intensity", 4.0)
    except Exception:
        pass

    camera = spawn_camera("BTP_Nanite_Camera", unreal.Vector(0.0, -560.0, 132.0), unreal.Rotator(0.0, -1.0, 90.0), 34.0)

    hit = unreal.SystemLibrary.line_trace_single(
        w,
        unreal.Vector(0.0, -520.0, 130.0),
        unreal.Vector(0.0, 180.0, 130.0),
        unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
        True,
        [manager],
        unreal.DrawDebugTrace.NONE,
        True,
    )
    if not hit:
        raise RuntimeError("Nanite validation trace missed")

    accepted = manager.try_paint_from_hit(hit, 30.0, 1.0, -1)
    if not accepted:
        raise RuntimeError("TryPaintFromHit rejected Nanite validation hit")

    manager.flush_pending_blood_stamps()
    rt = manager.get_first_paint_render_target()
    if not rt:
        raise RuntimeError("Nanite validation did not create a paint RT")

    unreal.RenderingLibrary.export_render_target(w, rt, OUT_DIR, "M_D_Nanite_RT_after_hit.png")
    log(f"Exported Nanite RT: {os.path.join(OUT_DIR, 'M_D_Nanite_RT_after_hit.png')}")
    log(manager.get_debug_stats_string())
    request_screenshot(os.path.join(OUT_DIR, "M_D_Nanite_blood_hit_result.png"), camera)


def capture_final_blood():
    os.makedirs(OUT_DIR, exist_ok=True)
    manager = find_validation_actor("BTP_Runtime_Manager")
    camera = find_validation_actor("BTP_Runtime_Camera")
    if not manager or not camera:
        raise RuntimeError("Runtime validation manager/camera missing; run setup_debug first")

    manager.set_debug_show_mask_on_painted_materials(False)
    unreal.EditorLevelLibrary.editor_invalidate_viewports()
    log(manager.get_debug_stats_string())
    request_screenshot(os.path.join(OUT_DIR, "M_C_Mesh_final_blood.png"), camera)


def capture_batching():
    os.makedirs(OUT_DIR, exist_ok=True)
    w = world()
    manager = find_validation_actor("BTP_Runtime_Manager")
    target = find_validation_actor("BTP_Runtime_Target")
    camera = find_validation_actor("BTP_Runtime_Camera")
    if not manager or not target or not camera:
        raise RuntimeError("Runtime validation actors missing; run setup_debug first")

    target_component = target.get_component_by_class(unreal.StaticMeshComponent)
    if not target_component:
        raise RuntimeError("Runtime validation target has no StaticMeshComponent")

    manager.set_debug_show_mask_on_painted_materials(True)
    for uv in [
        unreal.Vector2D(0.25, 0.25),
        unreal.Vector2D(0.75, 0.25),
        unreal.Vector2D(0.25, 0.75),
        unreal.Vector2D(0.75, 0.75),
        unreal.Vector2D(0.50, 0.50),
    ]:
        if not manager.debug_paint_uv(target_component, uv, 72.0, 1.0, 0):
            raise RuntimeError(f"DebugPaintUV rejected {uv}")

    manager.flush_pending_blood_stamps()
    rt = manager.get_first_paint_render_target()
    if not rt:
        raise RuntimeError("No RT after batching pass")

    unreal.RenderingLibrary.export_render_target(w, rt, OUT_DIR, "M_E_RT_batched_stamps.png")
    log(f"Exported batched RT: {os.path.join(OUT_DIR, 'M_E_RT_batched_stamps.png')}")
    log(manager.get_debug_stats_string())
    unreal.EditorLevelLibrary.editor_invalidate_viewports()
    request_screenshot(os.path.join(OUT_DIR, "M_E_Mesh_batch_debug_mask.png"), camera)


def setup_budget_scene_and_capture():
    os.makedirs(OUT_DIR, exist_ok=True)
    destroy_old_validation_actors()

    clean_material = load_asset("/Game/Prophecy/BloodTexturePainting/M_Test_BloodMaskBlend_Clean.M_Test_BloodMaskBlend_Clean")
    brush_material = load_asset("/Game/Prophecy/BloodTexturePainting/M_BloodBrush_Circle.M_BloodBrush_Circle")
    blood_material = load_asset("/Game/Prophecy/BloodTexturePainting/M_BloodPaint_RuntimeTest.M_BloodPaint_RuntimeTest")
    cube_mesh = load_asset("/Engine/BasicShapes/Cube.Cube")

    targets = []
    for index, x in enumerate([-170.0, 170.0]):
        target = add_tag(unreal.EditorLevelLibrary.spawn_actor_from_object(cube_mesh, unreal.Vector(x, 0.0, 130.0), unreal.Rotator(0.0, 0.0, 0.0), transient=False))
        set_label(target, f"BTP_Budget_Target_{index}")
        target.set_actor_scale3d(unreal.Vector(1.5, 0.08, 1.5))
        component = target.get_component_by_class(unreal.StaticMeshComponent)
        component.set_material(0, clean_material)
        component.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
        component.set_collision_profile_name("BlockAll")
        targets.append(component)

    manager = add_tag(unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.ProphecyBloodTexturePaintManager, unreal.Vector(0.0, -180.0, 80.0), unreal.Rotator(0.0, 0.0, 0.0), transient=False))
    set_label(manager, "BTP_Budget_Manager")
    manager.brush_material = brush_material
    manager.default_blood_material_template = blood_material
    manager.paint_uv_channel = 0
    manager.require_paintable_tag = False
    manager.max_active_paint_r_ts = 1
    manager.default_brush_size_pixels = 96.0
    manager.flush_every_tick = False
    manager.debug_print_hits = True
    manager.debug_draw_hit_locations = False
    manager.set_debug_show_mask_on_painted_materials(False)

    light = add_tag(unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(-260.0, -360.0, 520.0), unreal.Rotator(0.0, -45.0, -25.0), transient=False))
    set_label(light, "BTP_Budget_KeyLight")
    try:
        light.get_component_by_class(unreal.DirectionalLightComponent).set_editor_property("intensity", 4.0)
    except Exception:
        pass

    camera = spawn_camera("BTP_Budget_Camera", unreal.Vector(0.0, -620.0, 132.0), unreal.Rotator(0.0, -1.0, 90.0), 40.0)

    first_ok = manager.debug_paint_uv(targets[0], unreal.Vector2D(0.5, 0.5), 96.0, 1.0, 0)
    second_ok = manager.debug_paint_uv(targets[1], unreal.Vector2D(0.5, 0.5), 96.0, 1.0, 0)
    manager.flush_pending_blood_stamps()

    result_text = "\n".join([
        "Budget limit validation",
        f"MaxActivePaintRTs={manager.max_active_paint_r_ts}",
        f"FirstPaintAccepted={first_ok}",
        f"SecondPaintAccepted={second_ok}",
        manager.get_debug_stats_string(),
        "Expected: first accepted, second rejected with paint budget exceeded.",
    ])
    log(result_text.replace("\n", " | "))
    with open(os.path.join(OUT_DIR, "M_F_BudgetLimit_triggered.txt"), "w", encoding="utf-8") as output:
        output.write(result_text + "\n")

    unreal.EditorLevelLibrary.editor_invalidate_viewports()
    request_screenshot(os.path.join(OUT_DIR, "M_F_BudgetLimit_triggered.png"), camera)


def setup_performance_scene_and_capture():
    os.makedirs(OUT_DIR, exist_ok=True)
    destroy_old_validation_actors()
    perf_shot = str(PERF_SHOT).lower()

    clean_material = load_asset("/Game/Prophecy/BloodTexturePainting/M_Test_BloodMaskBlend_Clean.M_Test_BloodMaskBlend_Clean")
    brush_material = load_asset("/Game/Prophecy/BloodTexturePainting/M_BloodBrush_Circle.M_BloodBrush_Circle")
    blood_material = load_asset("/Game/Prophecy/BloodTexturePainting/M_BloodPaint_RuntimeTest.M_BloodPaint_RuntimeTest")
    cube_mesh = load_asset("/Engine/BasicShapes/Cube.Cube")

    timings = {}
    target_components = []
    columns = 40
    rows = 25
    count = columns * rows

    start = time.perf_counter()
    for index in range(count):
        col = index % columns
        row = index // columns
        x = (col - (columns - 1) * 0.5) * 45.0
        z = 70.0 + row * 45.0
        target = add_tag(unreal.EditorLevelLibrary.spawn_actor_from_object(cube_mesh, unreal.Vector(x, 0.0, z), unreal.Rotator(0.0, 0.0, 0.0), transient=False))
        set_label(target, f"BTP_Perf_Target_{index:04d}")
        target.set_actor_scale3d(unreal.Vector(0.25, 0.03, 0.25))
        component = target.get_component_by_class(unreal.StaticMeshComponent)
        component.set_material(0, clean_material)
        component.set_collision_enabled(unreal.CollisionEnabled.QUERY_ONLY)
        component.set_collision_profile_name("BlockAll")
        target_components.append(component)
    timings["spawn_1000_clean_seconds"] = time.perf_counter() - start

    manager = add_tag(unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.ProphecyBloodTexturePaintManager, unreal.Vector(0.0, -300.0, 80.0), unreal.Rotator(0.0, 0.0, 0.0), transient=False))
    set_label(manager, "BTP_Perf_Manager")
    manager.brush_material = brush_material
    manager.default_blood_material_template = blood_material
    manager.paint_uv_channel = 0
    manager.require_paintable_tag = False
    manager.max_active_paint_r_ts = 1200
    manager.max_stamps_per_frame = 2000
    manager.max_stamps_per_rt_per_frame = 8
    manager.default_rt_resolution_small = 64
    manager.default_rt_resolution_medium = 64
    manager.default_rt_resolution_large = 64
    manager.default_brush_size_pixels = 18.0
    manager.flush_every_tick = False
    manager.debug_print_hits = False
    manager.debug_draw_hit_locations = False
    manager.set_debug_show_mask_on_painted_materials(False)

    light = add_tag(unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(-650.0, -900.0, 1500.0), unreal.Rotator(0.0, -45.0, -25.0), transient=False))
    set_label(light, "BTP_Perf_KeyLight")
    try:
        light.get_component_by_class(unreal.DirectionalLightComponent).set_editor_property("intensity", 3.0)
    except Exception:
        pass

    camera = spawn_camera("BTP_Perf_Camera", unreal.Vector(0.0, -2550.0, 620.0), unreal.Rotator(0.0, -5.0, 90.0), 48.0)

    def write_perf_summary(extra):
        perf_summary = {
            "note": "Editor validation pass. The stat-unit screenshot names are generated, but camera automation may not capture UE viewport stat overlays; use the in-world stats plate and timings as preliminary evidence until a packaged/PIE profiler pass is captured.",
            "requested_shot": perf_shot,
            "object_count": count,
            "rt_resolution": 64,
            "timings_seconds": timings,
        }
        perf_summary.update(extra)
        with open(os.path.join(OUT_DIR, "M_G_editor_stress_summary.json"), "w", encoding="utf-8") as output:
            json.dump(perf_summary, output, indent=2)
        log("Performance stress summary: " + json.dumps(perf_summary, sort_keys=True))

    def capture_perf_phase(file_name, title, stats, extra=None):
        extra = extra or {}
        write_perf_summary({"capture_title": title, "capture_stats": stats, **extra})
        plate_lines = [
            title,
            stats,
            f"Objects: {count}  RT: 64x64 RGBA8",
            "Automation camera shot; profiler overlay may not be included.",
        ]
        if timings:
            compact_timings = ", ".join([f"{key}={value:.4f}s" for key, value in timings.items() if key != "spawn_1000_clean_seconds"])
            if compact_timings:
                plate_lines.append(compact_timings)
        spawn_stats_plate(
            f"BTP_Perf_Stats_{title}",
            "\n".join(plate_lines),
            unreal.Vector(-800.0, -620.0, 850.0),
            unreal.Rotator(0.0, -5.0, 90.0),
            20.0,
        )
        unreal.SystemLibrary.execute_console_command(world(), "stat unit")
        unreal.SystemLibrary.execute_console_command(world(), "stat fps")
        unreal.SystemLibrary.execute_console_command(world(), "stat gpu")
        unreal.EditorLevelLibrary.editor_invalidate_viewports()
        request_screenshot(os.path.join(OUT_DIR, file_name), camera)

    clean_stats = manager.get_debug_stats_string()
    if perf_shot == "clean":
        capture_perf_phase(
            "M_G_stat_unit_clean.png",
            "Milestone G: clean 1000 objects",
            clean_stats,
            {"stats_clean": clean_stats},
        )
        return

    start = time.perf_counter()
    for component in target_components[:100]:
        if not manager.debug_paint_uv(component, unreal.Vector2D(0.5, 0.5), 18.0, 1.0, 0):
            raise RuntimeError("100-object paint phase rejected a target")
    timings["queue_100_stamps_seconds"] = time.perf_counter() - start

    start = time.perf_counter()
    manager.flush_pending_blood_stamps()
    timings["flush_100_stamps_seconds"] = time.perf_counter() - start
    stats_after_100 = manager.get_debug_stats_string()

    if perf_shot == "100":
        capture_perf_phase(
            "M_G_stat_unit_100_painted.png",
            "Milestone G: 100 painted objects",
            stats_after_100,
            {"stats_clean": clean_stats, "stats_after_100": stats_after_100},
        )
        return

    start = time.perf_counter()
    for component in target_components[100:]:
        if not manager.debug_paint_uv(component, unreal.Vector2D(0.5, 0.5), 18.0, 1.0, 0):
            raise RuntimeError("1000-object paint phase rejected a target")
    timings["queue_remaining_900_stamps_seconds"] = time.perf_counter() - start

    start = time.perf_counter()
    manager.flush_pending_blood_stamps()
    timings["flush_remaining_900_stamps_seconds"] = time.perf_counter() - start
    stats_after_1000 = manager.get_debug_stats_string()

    if perf_shot == "1000":
        capture_perf_phase(
            "M_G_stat_unit_1000_painted.png",
            "Milestone G: 1000 painted objects",
            stats_after_1000,
            {
                "stats_clean": clean_stats,
                "stats_after_100": stats_after_100,
                "stats_after_1000": stats_after_1000,
            },
        )
        return

    manager.max_stamps_per_frame = 128
    manager.max_stamps_per_rt_per_frame = 64
    random.seed(12345)
    start = time.perf_counter()
    for _ in range(512):
        uv = unreal.Vector2D(random.uniform(0.2, 0.8), random.uniform(0.2, 0.8))
        if not manager.debug_paint_uv(target_components[0], uv, 10.0, 1.0, 0):
            raise RuntimeError("heavy burst queue rejected an existing target")
    timings["queue_512_burst_one_rt_seconds"] = time.perf_counter() - start

    start = time.perf_counter()
    manager.flush_pending_blood_stamps()
    timings["single_flush_512_burst_capped_seconds"] = time.perf_counter() - start
    stats_after_burst_cap = manager.get_debug_stats_string()

    burst_extra = {
        "stats_clean": clean_stats,
        "stats_after_100": stats_after_100,
        "stats_after_1000": stats_after_1000,
        "stats_after_burst_cap": stats_after_burst_cap,
    }
    if perf_shot == "burst":
        capture_perf_phase(
            "M_G_burst_stamping_stats.png",
            "Milestone G: burst stamping cap",
            stats_after_burst_cap,
            burst_extra,
        )
        return

    capture_perf_phase(
        "M_G_editor_stress_1000_painted.png",
        "Milestone G: editor stress summary",
        stats_after_burst_cap,
        burst_extra,
    )


try:
    if MODE == "setup_debug":
        setup_runtime_scene_and_capture_debug()
    elif MODE == "final_blood":
        capture_final_blood()
    elif MODE == "batching":
        capture_batching()
    elif MODE == "nanite":
        setup_nanite_scene_and_capture()
    elif MODE == "budget":
        setup_budget_scene_and_capture()
    elif MODE == "performance":
        setup_performance_scene_and_capture()
    else:
        raise RuntimeError(f"Unknown runtime validation mode: {MODE}")
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
