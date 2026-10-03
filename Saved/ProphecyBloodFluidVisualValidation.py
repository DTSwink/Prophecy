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
CAMERA_LABEL = "BTP_Live_SelectedWall_Camera"
SPAWN_LOCATION = unreal.Vector(-625.0, 805.0, 80.0)
SPAWN_ROTATION = unreal.Rotator(45.0, 0.0, 0.0)

STATE = {
    "handle": None,
    "step": "init",
    "next_step_time": time.time(),
    "screenshots": [],
    "errors": [],
}


def log(message):
    unreal.log(f"[ProphecyBloodFluidVisualValidation] {message}")


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


def get_editor_world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def destroy_validation_actors():
    for actor in list(unreal.ObjectIterator(unreal.Actor)):
        try:
            if not actor.get_world() or actor.get_world().get_path_name() != "/Game/vfxmap.vfxmap":
                continue
            tags = [str(t) for t in actor.tags]
            if TAG in tags:
                unreal.EditorLevelLibrary.destroy_actor(actor)
        except Exception:
            pass


def validation_camera():
    for actor in unreal.ObjectIterator(unreal.Actor):
        try:
            if not actor.get_world() or actor.get_world().get_path_name() != "/Game/vfxmap.vfxmap":
                continue
            if actor.get_actor_label() == CAMERA_LABEL:
                return actor
        except Exception:
            pass
    raise RuntimeError(f"Could not find camera {CAMERA_LABEL}")


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
    comp.advance_simulation_by_time(1.2, 1.0 / 60.0)
    return actor


def request_screenshot(label):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"{label}_{int(time.time())}.png")
    camera = validation_camera()
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
    STATE["screenshots"].append(path)
    log(f"Requested {label}: {path}")
    return path


def finish():
    try:
        set_mode("fluid")
    except Exception as exc:
        STATE["errors"].append(f"Could not restore fluid mode: {exc}")
    try:
        destroy_validation_actors()
    except Exception:
        pass
    if STATE["handle"] is not None:
        unreal.unregister_slate_post_tick_callback(STATE["handle"])
        STATE["handle"] = None
    os.makedirs(OUT_DIR, exist_ok=True)
    out_json = os.path.join(OUT_DIR, "latest_visual_validation.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(STATE, f, indent=2, default=str)
    log(f"Validation finished: {out_json}")


def tick(_delta_time):
    try:
        now = time.time()
        if now < STATE["next_step_time"]:
            return

        if STATE["step"] == "init":
            destroy_validation_actors()
            set_mode("raw")
            spawn_blood_actor()
            STATE["step"] = "raw_shot"
            STATE["next_step_time"] = now + 0.75
            return

        if STATE["step"] == "raw_shot":
            STATE["step"] = "fluid_spawn"
            STATE["next_step_time"] = now + 1.0
            request_screenshot("A_raw_NS_bloodsplat_no_fluid_pp")
            return

        if STATE["step"] == "fluid_spawn":
            destroy_validation_actors()
            set_mode("fluid")
            spawn_blood_actor()
            STATE["step"] = "fluid_shot"
            STATE["next_step_time"] = now + 0.75
            return

        if STATE["step"] == "fluid_shot":
            STATE["step"] = "finish"
            STATE["next_step_time"] = now + 1.0
            request_screenshot("B_fluid_NS_bloodsplat_pp")
            return

        if STATE["step"] == "finish":
            finish()
            STATE["step"] = "done"
            return

    except Exception:
        STATE["errors"].append(traceback.format_exc())
        finish()


def start():
    STATE["handle"] = unreal.register_slate_post_tick_callback(tick)
    print(json.dumps({"ok": True, "scheduled": True}, indent=2))


start()
