import os
import time
import traceback

import unreal


ASSET_DIR = "/Game/Prophecy/BloodTexturePainting"
OUT_DIR = os.path.normpath(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "BloodTexturePainting"))
TAG = "ProphecyBloodTexturePaintingValidation"


def log(message):
    unreal.log(f"[ProphecyBloodTexturePaintingValidation] {message}")


def load_asset(path):
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if not asset:
        raise RuntimeError(f"Missing asset: {path}")
    return asset


def ensure_out_dir():
    os.makedirs(OUT_DIR, exist_ok=True)


def world():
    try:
        return unreal.EditorLevelLibrary.get_editor_world()
    except Exception:
        return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def destroy_old_validation_actors():
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        tags = [str(t) for t in actor.tags]
        if TAG in tags:
            unreal.EditorLevelLibrary.destroy_actor(actor)


def add_tag(actor):
    actor.tags = list(actor.tags) + [TAG]
    return actor


def set_label(actor, label):
    try:
        actor.set_actor_label(label)
    except Exception:
        pass


def spawn_static_mesh(label, mesh_path, location, rotation, scale, material):
    mesh = load_asset(mesh_path)
    actor = add_tag(unreal.EditorLevelLibrary.spawn_actor_from_object(mesh, location, rotation, transient=False))
    set_label(actor, label)
    actor.set_actor_scale3d(scale)
    comp = actor.get_component_by_class(unreal.StaticMeshComponent)
    if not comp:
        raise RuntimeError(f"{label}: no StaticMeshComponent")
    comp.set_material(0, material)
    comp.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    comp.set_collision_profile_name("BlockAll")
    return actor


def spawn_plane(label, location, rotation, scale, material):
    return spawn_static_mesh(label, "/Engine/BasicShapes/Plane.Plane", location, rotation, scale, material)


def spawn_cube(label, location, rotation, scale, material):
    return spawn_static_mesh(label, "/Engine/BasicShapes/Cube.Cube", location, rotation, scale, material)


def spawn_camera(label, location, rotation, fov=45.0):
    actor = add_tag(unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.CameraActor, location, rotation, transient=False))
    set_label(actor, label)
    try:
        actor.camera_component.set_editor_property("field_of_view", fov)
    except Exception:
        pass
    return actor


def wait_for_file(path, timeout_seconds=15.0):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return True
        time.sleep(0.25)
    return False


def take_viewport_screenshot(path, camera=None):
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
        "Prophecy blood texture painting validation",
        0.1,
        True,
    )
    # HighRes screenshots are written on later editor ticks. Do not wait here:
    # this script runs inside the editor callback and blocking it also blocks
    # the tick that completes the screenshot task.
    log(f"Requested viewport screenshot: {path}")
    return path


def create_brush_rt_png():
    w = world()
    brush = load_asset(f"{ASSET_DIR}/M_BloodBrush_Circle.M_BloodBrush_Circle")
    rt = unreal.RenderingLibrary.create_render_target2d(
        w,
        512,
        512,
        unreal.TextureRenderTargetFormat.RTF_RGBA8,
        unreal.LinearColor(0.0, 0.0, 0.0, 1.0),
        False,
        False,
    )
    unreal.RenderingLibrary.clear_render_target2d(w, rt, unreal.LinearColor(0.0, 0.0, 0.0, 1.0))
    unreal.RenderingLibrary.draw_material_to_render_target(w, rt, brush)

    filename = "BrushRT_white_disk.png"
    unreal.RenderingLibrary.export_render_target(w, rt, OUT_DIR, filename)
    path = os.path.join(OUT_DIR, filename)
    if not wait_for_file(path, 20.0):
        raise RuntimeError(f"Brush RT export was not written: {path}")

    center = unreal.RenderingLibrary.read_render_target_pixel(w, rt, 256, 256)
    corner = unreal.RenderingLibrary.read_render_target_pixel(w, rt, 8, 8)
    log(f"BrushRT pixels center={center} corner={corner}")
    return path


def create_material_blend_scene_png():
    destroy_old_validation_actors()
    clean = load_asset(f"{ASSET_DIR}/M_Test_BloodMaskBlend_Clean.M_Test_BloodMaskBlend_Clean")
    full = load_asset(f"{ASSET_DIR}/M_Test_BloodMaskBlend_FullBlood.M_Test_BloodMaskBlend_FullBlood")

    spawn_cube(
        "BTP_Validation_Clean_Mask0",
        unreal.Vector(-120.0, 0.0, 110.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(1.4, 0.08, 1.4),
        clean,
    )
    spawn_cube(
        "BTP_Validation_FullBlood_Mask1",
        unreal.Vector(120.0, 0.0, 110.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(1.4, 0.08, 1.4),
        full,
    )

    light = add_tag(unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(-250.0, -260.0, 520.0), unreal.Rotator(-45.0, -25.0, 0.0), transient=False))
    set_label(light, "BTP_Validation_KeyLight")
    try:
        light.get_component_by_class(unreal.DirectionalLightComponent).set_editor_property("intensity", 4.0)
    except Exception:
        pass

    camera = spawn_camera(
        "BTP_Validation_Camera_CleanFull",
        unreal.Vector(0.0, -520.0, 130.0),
        unreal.Rotator(0.0, -2.5, 90.0),
        38.0,
    )

    unreal.EditorLevelLibrary.editor_invalidate_viewports()
    path = os.path.join(OUT_DIR, "MF_BloodPaintMaskBlend_clean_vs_fullblood.png")
    return take_viewport_screenshot(path, camera)


def create_find_collision_uv_probe():
    # Milestone A proof: trace three points on a clean validation plane and log UVs.
    material = load_asset(f"{ASSET_DIR}/M_Test_BloodMaskBlend_Clean.M_Test_BloodMaskBlend_Clean")
    plane = spawn_plane(
        "BTP_Validation_UVProbe",
        unreal.Vector(0.0, 260.0, 90.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(2.0, 2.0, 1.0),
        material,
    )
    w = world()
    points = [(-70.0, 205.0), (0.0, 260.0), (70.0, 315.0)]
    uvs = []
    for x, y in points:
        hit = unreal.SystemLibrary.line_trace_single(
            w,
            unreal.Vector(x, y, 240.0),
            unreal.Vector(x, y, -60.0),
            unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
            True,
            [],
            unreal.DrawDebugTrace.NONE,
            True,
        )
        uv = unreal.GameplayStatics.find_collision_uv(hit, 0) if hit else None
        uvs.append((x, y, uv))
    log(f"FindCollisionUV probe: {uvs}")
    return uvs


def main():
    ensure_out_dir()
    brush_path = create_brush_rt_png()
    material_path = create_material_blend_scene_png()
    uv_probe = create_find_collision_uv_probe()
    log(f"VALIDATION_OUTPUT brush={brush_path}")
    log(f"VALIDATION_OUTPUT material={material_path}")
    log(f"VALIDATION_OUTPUT uv_probe={uv_probe}")


try:
    main()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
