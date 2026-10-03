import json
import os
import time
import traceback

import unreal


AB_SCRIPT = os.path.join(unreal.Paths.project_saved_dir(), "ProphecyBloodFluidABTest.py")
AB_SCRIPT = unreal.Paths.convert_relative_path_to_full(AB_SCRIPT)

STATE = {
    "handle": None,
    "started_at": time.time(),
    "next_step_time": time.time(),
    "step": "init",
    "shots": [],
    "errors": [],
}


def log(message):
    unreal.log(f"[ProphecyBloodFluidABCapture] {message}")


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
take_screenshot = HELPERS["take_screenshot"]


def begin_play_or_simulate():
    subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if subsystem and hasattr(subsystem, "is_in_play_in_editor") and subsystem.is_in_play_in_editor():
        return "already_in_pie"
    if subsystem and hasattr(subsystem, "editor_request_begin_play"):
        subsystem.editor_request_begin_play()
        return "requested_begin_play"
    unreal.EditorLevelLibrary.editor_play_simulate()
    return "simulate"


def request_shot(label):
    path = take_screenshot(label)
    STATE["shots"].append(path)
    return path


def finish():
    try:
        set_mode("fluid")
    except Exception as exc:
        STATE["errors"].append(f"Could not leave fluid mode active: {exc}")
    if STATE["handle"] is not None:
        unreal.unregister_slate_post_tick_callback(STATE["handle"])
        STATE["handle"] = None
    out_path = os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
        "BloodFluidAB",
        "latest_ab_capture.json",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(STATE, f, indent=2, default=str)
    log(f"AB capture finished: {out_path}")


def tick(_delta_time):
    try:
        now = time.time()
        if now < STATE["next_step_time"]:
            return

        if STATE["step"] == "init":
            set_mode("raw")
            STATE["play_result"] = begin_play_or_simulate()
            STATE["step"] = "wait_raw"
            STATE["next_step_time"] = now + 3.0
            log("A/B capture: raw mode, waiting for fountain")
            return

        if STATE["step"] == "wait_raw":
            STATE["step"] = "wait_fluid"
            STATE["next_step_time"] = now + 1.0
            request_shot("A_raw_no_fluid_pp")
            set_mode("fluid")
            log("A/B capture: switched to fluid mode")
            return

        if STATE["step"] == "wait_fluid":
            STATE["step"] = "settle"
            STATE["next_step_time"] = now + 1.0
            request_shot("B_fluid_pp_enabled")
            return

        if STATE["step"] == "settle":
            finish()
            STATE["step"] = "done"
            return

    except Exception:
        STATE["errors"].append(traceback.format_exc())
        finish()


def start_capture():
    STATE["handle"] = unreal.register_slate_post_tick_callback(tick)
    log("AB capture scheduled")
    print(json.dumps({"ok": True, "scheduled": True}, indent=2))


start_capture()
