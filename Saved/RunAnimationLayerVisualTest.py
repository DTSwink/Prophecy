import json
import os
import time
import traceback

import unreal


LEVEL = "/Game/testNN"
ANIMATION = (
    "/Game/Characters/UEFN_Mannequin/Animations/Walk/"
    "M_Neutral_Walk_Loop_F.M_Neutral_Walk_Loop_F"
)
OUTPUT_DIR = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "AnimationLayerVisualTest",
)

STATE = {
    "handle": None,
    "stage": "load",
    "next_time": time.time() + 1.0,
    "actor": None,
    "animation": None,
    "results": [],
    "errors": [],
}


def log(message):
    unreal.log("[AnimationLayerVisualTest] " + message)


def game_world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


def begin_play():
    if game_world() is not None:
        return
    subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if subsystem and hasattr(subsystem, "editor_request_begin_play"):
        subsystem.editor_request_begin_play()
    else:
        unreal.EditorLevelLibrary.editor_play_simulate()


def find_agent(world):
    for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
        class_name = actor.get_class().get_name()
        if "ProphecyManualPoseAgent" in class_name or "ProphecyAgent" in class_name:
            if hasattr(actor, "play_nn_animation_layer"):
                return actor
    return None


def request_shot(world, label):
    path = os.path.join(OUTPUT_DIR, label + ".png")
    if os.path.exists(path):
        os.remove(path)
    command = 'HighResShot filename="{}" 1280x720'.format(path.replace("\\", "/"))
    unreal.SystemLibrary.execute_console_command(world, command)
    STATE["results"].append({"shot": label, "path": path})
    log("requested screenshot " + path)


def record(label, **values):
    row = {"event": label, "time": time.time()}
    row.update(values)
    STATE["results"].append(row)
    log("{} {}".format(label, values))


def layer_state():
    value = STATE["actor"].get_nn_animation_layer_state()
    if value is None or value is False:
        return None
    if isinstance(value, tuple):
        values = list(value)
        if values and isinstance(values[0], bool):
            if not values.pop(0):
                return None
        if len(values) >= 2:
            return float(values[-2]), float(values[-1])
    return None


def finish():
    if STATE["handle"] is not None:
        unreal.unregister_slate_post_tick_callback(STATE["handle"])
        STATE["handle"] = None
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    report_path = os.path.join(OUTPUT_DIR, "report.json")
    with open(report_path, "w", encoding="utf-8") as output:
        json.dump(
            {
                "level": LEVEL,
                "animation": ANIMATION,
                "results": STATE["results"],
                "errors": STATE["errors"],
            },
            output,
            indent=2,
        )
    log("finished: " + report_path)


def tick(_delta_seconds):
    try:
        now = time.time()
        if now < STATE["next_time"]:
            return

        if STATE["stage"] == "load":
            STATE["animation"] = unreal.load_asset(ANIMATION)
            if STATE["animation"] is None:
                raise RuntimeError("Could not load " + ANIMATION)
            STATE["stage"] = "begin_play"
            STATE["next_time"] = now + 1.0
            return

        if STATE["stage"] == "begin_play":
            begin_play()
            STATE["stage"] = "wait_agent"
            STATE["next_time"] = now + 1.0
            return

        world = game_world()
        if world is None:
            STATE["next_time"] = now + 0.25
            return

        if STATE["stage"] == "wait_agent":
            actor = find_agent(world)
            if actor is None:
                STATE["next_time"] = now + 0.25
                return
            STATE["actor"] = actor
            ok = actor.play_nn_animation_layer(
                STATE["animation"], unreal.Name("None"), 0.40, 0.40, 0.50, False
            )
            if not ok:
                STATE["next_time"] = now + 0.25
                return
            record("full_body_started", actor=actor.get_path_name())
            STATE["stage"] = "capture_full"
            STATE["next_time"] = now + 1.25
            return

        if STATE["stage"] == "capture_full":
            current = layer_state()
            if current is None or current[0] < 0.60 or current[1] < 0.95:
                STATE["next_time"] = now + 0.10
                return
            request_shot(world, "01_full_body_mid")
            record("full_body_active", playback=current[0], weight=current[1])
            STATE["stage"] = "wait_full_finish"
            STATE["next_time"] = now + 0.10
            return

        if STATE["stage"] == "wait_full_finish":
            current = layer_state()
            if current is not None:
                STATE["next_time"] = now + 0.10
                return
            record("full_body_finished", active=False)
            request_shot(world, "02_full_body_returned_to_nn")
            STATE["stage"] = "start_upper"
            STATE["next_time"] = now + 1.0
            return

        if STATE["stage"] == "start_upper":
            ok = STATE["actor"].play_nn_animation_layer(
                STATE["animation"], unreal.Name("spine_01"), 0.40, 0.60, 0.50, True
            )
            if not ok:
                raise RuntimeError("spine_01 animation layer did not start")
            record("upper_body_started")
            STATE["stage"] = "capture_upper"
            STATE["next_time"] = now + 1.25
            return

        if STATE["stage"] == "capture_upper":
            current = layer_state()
            if current is None or current[0] < 0.60 or current[1] < 0.95:
                STATE["next_time"] = now + 0.10
                return
            request_shot(world, "03_spine_01_mid")
            record("upper_body_active", playback=current[0], weight=current[1])
            STATE["actor"].stop_nn_animation_layer(0.75)
            record("upper_body_stop_requested")
            STATE["stage"] = "capture_upper_blend_out"
            STATE["next_time"] = now + 0.35
            return

        if STATE["stage"] == "capture_upper_blend_out":
            current = layer_state()
            if current is None or current[1] >= 0.80 or current[1] <= 0.15:
                STATE["next_time"] = now + 0.05
                return
            request_shot(world, "04_spine_01_blending_out")
            record("upper_body_blending_out", playback=current[0], weight=current[1])
            STATE["stage"] = "capture_upper_return"
            STATE["next_time"] = now + 0.10
            return

        if STATE["stage"] == "capture_upper_return":
            current = layer_state()
            if current is not None:
                STATE["next_time"] = now + 0.10
                return
            record("upper_body_finished", active=False)
            request_shot(world, "05_spine_01_returned_to_nn")
            STATE["stage"] = "finish"
            STATE["next_time"] = now + 1.0
            return

        if STATE["stage"] == "finish":
            finish()
            STATE["stage"] = "done"

    except Exception:
        STATE["errors"].append(traceback.format_exc())
        log(STATE["errors"][-1])
        finish()
        STATE["stage"] = "failed"


os.makedirs(OUTPUT_DIR, exist_ok=True)
STATE["handle"] = unreal.register_slate_post_tick_callback(tick)
log("scheduled")
