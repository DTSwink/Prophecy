import json
import os
import time
import traceback

import unreal


PP_DIR = "/Game/_mygame/blood2/PP_Fluid"
PP_VOLUME_WORLD = "/Game/vfxmap.vfxmap"
SCREENSHOT_DIR = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "BloodFluidAB",
)

FLUID_STACK = [
    f"{PP_DIR}/MI_PP_Blood_Extract.MI_PP_Blood_Extract",
    f"{PP_DIR}/MI_PP_Blood_BlurH.MI_PP_Blood_BlurH",
    f"{PP_DIR}/MI_PP_Blood_BlurV.MI_PP_Blood_BlurV",
    f"{PP_DIR}/MI_PP_Blood_Composite.MI_PP_Blood_Composite",
]

STENCIL_STACK = [
    f"{PP_DIR}/MI_PP_Blood_StencilDebug42.MI_PP_Blood_StencilDebug42",
]


def log(message):
    unreal.log(f"[ProphecyBloodFluidAB] {message}")


def level_post_process_volumes():
    volumes = []
    for actor in unreal.ObjectIterator(unreal.Actor):
        try:
            if actor.get_class().get_name() != "PostProcessVolume":
                continue
            world = actor.get_world()
            if not world or world.get_path_name() != PP_VOLUME_WORLD:
                continue
            volumes.append(actor)
        except Exception:
            pass
    return volumes


def blood_fluid_controllers():
    controllers = []
    for actor in unreal.ObjectIterator(unreal.Actor):
        try:
            if actor.get_class().get_name() != "ProphecyBloodFluidPostProcessController":
                continue
            world = actor.get_world()
            if not world or world.get_path_name() != PP_VOLUME_WORLD:
                continue
            controllers.append(actor)
        except Exception:
            pass
    return controllers


def set_prop_first(obj, names, value):
    for name in names:
        try:
            obj.set_editor_property(name, value)
            return name
        except Exception:
            pass
    return None


def set_controller_mode(mode):
    controllers = blood_fluid_controllers()
    if not controllers:
        return None

    controller = controllers[0]
    controller.modify()
    if mode == "raw":
        set_prop_first(controller, ("blood_fluid_post_enabled", "b_blood_fluid_post_enabled"), False)
        set_prop_first(controller, ("show_stencil_debug", "b_show_stencil_debug"), False)
    elif mode == "stencil":
        set_prop_first(controller, ("blood_fluid_post_enabled", "b_blood_fluid_post_enabled"), True)
        set_prop_first(controller, ("show_stencil_debug", "b_show_stencil_debug"), True)
    else:
        set_prop_first(controller, ("blood_fluid_post_enabled", "b_blood_fluid_post_enabled"), True)
        set_prop_first(controller, ("show_stencil_debug", "b_show_stencil_debug"), False)

    controller.apply_blood_fluid_post_process_settings()
    return controller


def load_stack(paths):
    materials = []
    for path in paths:
        material = unreal.load_asset(path)
        if not material:
            raise RuntimeError(f"Missing post-process blendable: {path}")
        materials.append(material)
    return materials


def is_blood_pp_object(obj):
    if not obj:
        return False
    path = obj.get_path_name()
    return (
        "/Game/_mygame/blood2/_PPM_blood" in path
        or "/Engine/Transient._PPM_blood" in path
        or f"{PP_DIR}/" in path
    )


def set_mode(mode):
    mode = str(mode).lower()
    if mode not in ("raw", "fluid", "stencil"):
        raise ValueError("mode must be raw, fluid, or stencil")

    controller = set_controller_mode(mode)
    if controller:
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
        return {
            "mode": mode,
            "controller": controller.get_path_name(),
            "active_blood_blendables": active_controller_stack(controller),
            "volumes": [],
        }

    if mode == "fluid":
        stack = load_stack(FLUID_STACK)
    elif mode == "stencil":
        stack = load_stack(STENCIL_STACK)
    else:
        stack = []

    volumes = level_post_process_volumes()
    if not volumes:
        raise RuntimeError(f"No PostProcessVolume found in {PP_VOLUME_WORLD}")

    changed = []
    for volume in volumes:
        volume.modify()
        volume.set_editor_property("unbound", True)
        settings = volume.get_editor_property("settings")
        old_weighted = settings.get_editor_property("weighted_blendables")
        kept = []

        try:
            for item in old_weighted.get_editor_property("array"):
                obj = item.get_editor_property("object")
                if is_blood_pp_object(obj):
                    continue
                kept.append(item)
        except Exception:
            kept = []

        for material in stack:
            item = unreal.WeightedBlendable()
            item.set_editor_property("weight", 1.0)
            item.set_editor_property("object", material)
            kept.append(item)

        new_weighted = unreal.WeightedBlendables()
        new_weighted.set_editor_property("array", kept)
        settings.set_editor_property("weighted_blendables", new_weighted)
        volume.set_editor_property("settings", settings)
        changed.append(volume.get_path_name())

    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    log(f"Mode {mode}: {len(stack)} blood PP blendables active")
    return {"mode": mode, "active_blood_blendables": [m.get_path_name() for m in stack], "volumes": changed}


def active_controller_stack(controller=None):
    result = []
    controllers = [controller] if controller else blood_fluid_controllers()
    for item_controller in controllers:
        if not item_controller:
            continue
        ppc = item_controller.get_editor_property("post_process_component")
        entries = []
        if ppc:
            try:
                weighted = ppc.get_editor_property("settings").get_editor_property("weighted_blendables")
                for item in weighted.get_editor_property("array"):
                    obj = item.get_editor_property("object")
                    entries.append({
                        "weight": float(item.get_editor_property("weight")),
                        "object": obj.get_path_name() if obj else None,
                    })
            except Exception as exc:
                entries.append({"error": str(exc)})
        result.append({
            "controller": item_controller.get_path_name(),
            "enabled": str(item_controller.get_editor_property("blood_fluid_post_enabled")),
            "stencil_debug": str(item_controller.get_editor_property("show_stencil_debug")),
            "entries": entries,
        })
    return result


def active_stack():
    result = active_controller_stack()
    for volume in level_post_process_volumes():
        settings = volume.get_editor_property("settings")
        weighted = settings.get_editor_property("weighted_blendables")
        entries = []
        try:
            for item in weighted.get_editor_property("array"):
                obj = item.get_editor_property("object")
                entries.append({
                    "weight": float(item.get_editor_property("weight")),
                    "object": obj.get_path_name() if obj else None,
                    "is_blood_pp": is_blood_pp_object(obj),
                })
        except Exception as exc:
            entries.append({"error": str(exc)})
        result.append({"volume": volume.get_path_name(), "entries": entries})
    return result


def take_screenshot(label, width=1280, height=720):
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    safe_label = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in str(label))
    path = os.path.join(SCREENSHOT_DIR, f"{safe_label}_{int(time.time())}.png")
    unreal.AutomationLibrary.finish_loading_before_screenshot()
    unreal.AutomationLibrary.take_high_res_screenshot(
        width,
        height,
        path,
        None,
        False,
        False,
        unreal.ComparisonTolerance.LOW,
        f"Blood fluid A/B {safe_label}",
        0.1,
        True,
    )
    log(f"Requested screenshot {path}")
    return path


def run_from_globals():
    mode = globals().get("MODE", None)
    shot = bool(globals().get("TAKE_SCREENSHOT", False))
    payload = {"ok": True}
    if mode:
        payload["mode_result"] = set_mode(mode)
    payload["active_stack"] = active_stack()
    if shot:
        payload["screenshot"] = take_screenshot(mode or "current")
    print(json.dumps(payload, indent=2))


if not bool(globals().get("PROPHECY_AB_SKIP_AUTORUN", False)):
    try:
        run_from_globals()
    except Exception:
        unreal.log_error(traceback.format_exc())
        raise
