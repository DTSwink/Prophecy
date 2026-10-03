import json
import os
import time
import traceback

import unreal


TAG = "ProphecyBloodFluidDiagCompare"
CAMERA_LABEL = "TMP_BloodFluidDiagCompare_Camera"
OUT_DIR = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "BloodFluidAB",
    "DiagCompare",
)
DIAG_SCRIPT = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "ProphecyCreateBloodFluidDiagnosticCompare.py",
)
WIDTH = 1024
HEIGHT = 768
STAGES = list(range(8))

STATE = {
    "handle": None,
    "step": "init",
    "stage_index": 0,
    "shots": [],
    "errors": [],
    "started_at": time.time(),
    "next_step_time": time.time(),
}


def log(message):
    unreal.log(f"[ProphecyBloodDiagCompare] {message}")


def load_diag_helpers():
    namespace = {
        "unreal": unreal,
        "PROPHECY_BLOOD_DIAG_SKIP_AUTORUN": True,
    }
    with open(DIAG_SCRIPT, "r", encoding="utf-8") as f:
        exec(compile(f.read(), DIAG_SCRIPT, "exec"), namespace)
    return namespace


HELPERS = load_diag_helpers()
enable_diagnostic = HELPERS["enable_diagnostic"]
set_stage = HELPERS["set_stage"]
restore = HELPERS["restore"]


def editor_world():
    try:
        return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    except Exception:
        return unreal.EditorLevelLibrary.get_editor_world()


def pie_world():
    try:
        worlds = list(unreal.EditorLevelLibrary.get_pie_worlds(True))
        return worlds[0] if worlds else None
    except Exception:
        try:
            return unreal.EditorLevelLibrary.get_game_world()
        except Exception:
            return None


def destroy_tagged_editor_actors():
    world = editor_world()
    if not world:
        return
    for actor in list(unreal.ActorIterator(world)):
        try:
            if TAG in [str(tag) for tag in actor.tags]:
                unreal.EditorLevelLibrary.destroy_actor(actor)
        except Exception:
            pass


def current_view_transform():
    subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    info = subsystem.get_level_viewport_camera_info()
    if info:
        return info[0], info[1]
    return unreal.Vector(-650.0, -240.0, 230.0), unreal.Rotator(-8.0, 0.0, 90.0)


def spawn_editor_camera():
    destroy_tagged_editor_actors()
    location, rotation = current_view_transform()
    camera = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.CameraActor,
        location,
        rotation,
        transient=False,
    )
    camera.tags = list(camera.tags) + [TAG]
    try:
        camera.set_actor_label(CAMERA_LABEL)
    except Exception:
        pass
    try:
        camera.camera_component.set_editor_property("field_of_view", 70.0)
    except Exception:
        pass
    return camera


def find_camera(world):
    if not world:
        return None
    for actor in unreal.ActorIterator(world):
        try:
            if actor.get_actor_label() == CAMERA_LABEL:
                return actor
            if TAG in [str(tag) for tag in actor.tags]:
                if actor.get_class().get_name() == "CameraActor":
                    return actor
        except Exception:
            pass
    return None


def capture(label, stage, camera):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"{label}_stage{stage:02d}.png")
    unreal.AutomationLibrary.finish_loading_before_screenshot()
    unreal.AutomationLibrary.take_high_res_screenshot(
        WIDTH,
        HEIGHT,
        path,
        camera,
        False,
        False,
        unreal.ComparisonTolerance.LOW,
        f"{label}_stage{stage:02d}",
        0.1,
        True,
    )
    STATE["shots"].append(path)
    log(f"Requested {path}")
    return path


def request_begin_play():
    subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not subsystem.is_in_play_in_editor():
        subsystem.editor_request_begin_play()


def request_end_play():
    subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if subsystem.is_in_play_in_editor():
        subsystem.editor_request_end_play()


def finish():
    try:
        request_end_play()
    except Exception:
        pass
    out_json = os.path.join(OUT_DIR, "latest_diag_compare.json")
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(STATE, f, indent=2, default=str)
    if STATE["handle"] is not None:
        unreal.unregister_slate_post_tick_callback(STATE["handle"])
        STATE["handle"] = None
    log(f"Diagnostic compare finished: {out_json}")


def tick(_delta_time):
    try:
        now = time.time()
        if now < STATE["next_step_time"]:
            return

        if STATE["step"] == "init":
            request_end_play()
            STATE["camera_path"] = spawn_editor_camera().get_path_name()
            enable_diagnostic(0)
            STATE["step"] = "editor_capture"
            STATE["stage_index"] = 0
            STATE["next_step_time"] = now + 0.75
            return

        if STATE["step"] == "editor_capture":
            stage = STAGES[STATE["stage_index"]]
            set_stage(stage)
            camera = find_camera(editor_world())
            if camera is None:
                raise RuntimeError("Missing editor diagnostic camera")
            capture("editor", stage, camera)
            STATE["stage_index"] += 1
            if STATE["stage_index"] >= len(STAGES):
                STATE["step"] = "start_pie"
                STATE["stage_index"] = 0
                STATE["next_step_time"] = now + 1.0
            else:
                STATE["next_step_time"] = now + 0.35
            return

        if STATE["step"] == "start_pie":
            request_begin_play()
            STATE["step"] = "pie_wait"
            STATE["next_step_time"] = now + 2.0
            return

        if STATE["step"] == "pie_wait":
            world = pie_world()
            camera = find_camera(world)
            if not world or not camera:
                STATE["next_step_time"] = now + 0.5
                return
            enable_diagnostic(0)
            STATE["step"] = "pie_capture"
            STATE["stage_index"] = 0
            STATE["next_step_time"] = now + 0.5
            return

        if STATE["step"] == "pie_capture":
            stage = STAGES[STATE["stage_index"]]
            set_stage(stage)
            camera = find_camera(pie_world())
            if camera is None:
                raise RuntimeError("Missing PIE diagnostic camera")
            capture("pie", stage, camera)
            STATE["stage_index"] += 1
            if STATE["stage_index"] >= len(STAGES):
                STATE["step"] = "finish"
                STATE["next_step_time"] = now + 1.0
            else:
                STATE["next_step_time"] = now + 0.35
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
    print(json.dumps({"ok": True, "scheduled": True, "out_dir": OUT_DIR}, indent=2))


start()
