import json
import os
import time
import traceback

import unreal


TAG = "ProphecyBloodFluidValidation"
OUT_DIR = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "BloodFluidAB",
)
AB_SCRIPT = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "ProphecyBloodFluidABTest.py",
)

SYSTEM_PATH = "/Game/_mygame/blood2/NS_bloodsplat.NS_bloodsplat"
SPAWN_LOCATION = unreal.Vector(-625.0, 900.0, 95.0)
SPAWN_ROTATION = unreal.Rotator(45.0, 0.0, 0.0)
SPAWN_SCALE = unreal.Vector(0.38, 0.38, 0.38)
CAMERA_LOCATION = unreal.Vector(-650.0, -240.0, 230.0)
CAMERA_TARGET = unreal.Vector(-625.0, 900.0, 105.0)
CAMERA_FOV = 62.0


def load_ab_helpers():
    namespace = {
        "unreal": unreal,
        "PROPHECY_AB_SKIP_AUTORUN": True,
    }
    with open(AB_SCRIPT, "r", encoding="utf-8") as f:
        exec(compile(f.read(), AB_SCRIPT, "exec"), namespace)
    return namespace


HELPERS = load_ab_helpers()
set_mode = HELPERS["set_mode"]


def destroy_validation_actors():
    for actor in list(unreal.ObjectIterator(unreal.Actor)):
        try:
            if not actor.get_world() or actor.get_world().get_path_name() != "/Game/vfxmap.vfxmap":
                continue
            if TAG in [str(t) for t in actor.tags]:
                unreal.EditorLevelLibrary.destroy_actor(actor)
        except Exception:
            pass


def spawn_camera():
    camera_rotation = unreal.MathLibrary.find_look_at_rotation(CAMERA_LOCATION, CAMERA_TARGET)
    camera = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.CameraActor,
        CAMERA_LOCATION,
        camera_rotation,
        transient=True,
    )
    camera.tags = list(camera.tags) + [TAG]
    try:
        camera.set_actor_label("TMP_BloodFluidValidation_Camera")
        camera.camera_component.set_editor_property("field_of_view", CAMERA_FOV)
    except Exception:
        pass
    return camera


def spawn_blood_actor():
    system = unreal.load_asset(SYSTEM_PATH)
    if not system:
        raise RuntimeError(f"Missing Niagara system {SYSTEM_PATH}")

    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.NiagaraActor,
        SPAWN_LOCATION,
        SPAWN_ROTATION,
        transient=True,
    )
    actor.tags = list(actor.tags) + [TAG]
    actor.set_actor_scale3d(SPAWN_SCALE)
    try:
        actor.set_actor_label("TMP_BloodFluidValidation_NS_bloodsplat")
    except Exception:
        pass

    comp = actor.get_editor_property("niagara_component")
    comp.set_asset(system)
    comp.set_editor_property("auto_activate", True)
    comp.set_render_custom_depth(True)
    comp.set_custom_depth_stencil_value(42)
    comp.set_render_in_main_pass(True)
    comp.set_render_in_depth_pass(True)
    comp.activate(True)
    comp.reset_system()
    comp.advance_simulation_by_time(1.15, 1.0 / 60.0)
    return actor


def capture(mode, label):
    destroy_validation_actors()
    mode_result = set_mode(mode)
    camera = spawn_camera()
    blood_actor = spawn_blood_actor()

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"{label}_{int(time.time())}.png")
    unreal.AutomationLibrary.finish_loading_before_screenshot()
    unreal.AutomationLibrary.take_high_res_screenshot(
        1280,
        720,
        path,
        camera,
        False,
        False,
        unreal.ComparisonTolerance.LOW,
        label,
        0.1,
        True,
    )
    return {
        "mode": mode,
        "label": label,
        "screenshot": path,
        "mode_result": mode_result,
        "camera": camera.get_path_name(),
        "blood_actor": blood_actor.get_path_name(),
    }


try:
    mode = globals().get("MODE", "fluid")
    label = globals().get("LABEL", f"{mode}_NS_bloodsplat")
    result = capture(mode, label)
    print(json.dumps({"ok": True, **result}, indent=2, default=str))
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
