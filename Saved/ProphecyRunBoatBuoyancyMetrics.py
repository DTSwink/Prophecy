"""Background PIE metrics for the existing BP_Boat buoyancy setup.

Run through Tools/ProphecyEditorBridge.py.  The script schedules work on Slate
ticks, returns to the bridge immediately, and never touches desktop focus.
It owns PIE for three short cases and restores every editor-world value it
temporarily changes.  It does not save the level or create Content assets.
"""

import json
import math
import os
import statistics
import time
import traceback

import unreal


TAG = "ProphecyBoatBuoyancyMetrics"
CASES = ("empty", "cube_90kg", "character")
CASE_DURATION_SECONDS = 12.0
FINAL_WINDOW_SECONDS = 3.0
CASE_TIMEOUT_SECONDS = 90.0
CHARACTER_RELATIVE_LOCATION = unreal.Vector(-29.2983799, -12.6322797, 105.6019280)
CHARACTER_RELATIVE_YAW = 4.2599558
CUBE_RELATIVE_LOCATION = unreal.Vector(-29.2983799, -12.6322797, 70.0)
OUT_PATH = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "Profiling",
    "BoatBuoyancy",
    "latest_metrics.json",
)


STATE = {
    "tag": TAG,
    "handle": None,
    "step": "init",
    "case_index": 0,
    "case_started_real": 0.0,
    "case_started_game": 0.0,
    "last_progress_real": 0.0,
    "last_progress_game": 0.0,
    "samples": [],
    "results": [],
    "errors": [],
    "started_at": time.time(),
    "finished": False,
    "editor_character": None,
    "original_character_transform": None,
    "original_character_collision": None,
    "pcg_states": [],
}


def log(message):
    unreal.log(f"[BoatBuoyancyMetrics] {message}")


def vector_list(value):
    return [float(value.x), float(value.y), float(value.z)]


def rotator_list(value):
    return [float(value.roll), float(value.pitch), float(value.yaw)]


def editor_world():
    subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    return subsystem.get_editor_world() if subsystem else None


def pie_world():
    worlds = list(unreal.EditorLevelLibrary.get_pie_worlds(True))
    return worlds[0] if worlds else None


def level_subsystem():
    return unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)


def find_actor(world, label):
    if not world:
        return None
    for actor in unreal.ActorIterator(world):
        try:
            if actor.get_actor_label() == label:
                return actor
        except Exception:
            pass
    return None


def find_component(actor, name):
    if not actor:
        return None
    for component in actor.get_components_by_class(unreal.ActorComponent):
        if component.get_name() == name:
            return component
    return None


def transform_dict(transform):
    location = transform.translation
    rotation = transform.rotation.rotator()
    scale = transform.scale3d
    return {
        "location": vector_list(location),
        "rotation": rotator_list(rotation),
        "scale": vector_list(scale),
    }


def make_transform(data):
    loc = data["location"]
    rot = data["rotation"]
    scale = data["scale"]
    return unreal.Transform(
        location=unreal.Vector(*loc),
        rotation=unreal.Rotator(roll=rot[0], pitch=rot[1], yaw=rot[2]),
        scale=unreal.Vector(*scale),
    )


def character_test_transform(boat):
    boat_transform = boat.get_actor_transform()
    location = boat_transform.transform_location(CHARACTER_RELATIVE_LOCATION)
    boat_rotation = boat.get_actor_rotation()
    rotation = unreal.Rotator(
        roll=boat_rotation.roll,
        pitch=boat_rotation.pitch,
        yaw=boat_rotation.yaw + CHARACTER_RELATIVE_YAW,
    )
    original_scale = STATE["original_character_transform"]["scale"]
    return unreal.Transform(
        location=location,
        rotation=rotation,
        scale=unreal.Vector(*original_scale),
    )


def snapshot_and_disable_pcg(world):
    STATE["pcg_states"] = []
    for actor in unreal.ActorIterator(world):
        for component in actor.get_components_by_class(unreal.ActorComponent):
            if "PCG" not in component.get_class().get_name():
                continue
            was_active = bool(component.is_active())
            STATE["pcg_states"].append((component, was_active))
            if was_active:
                component.deactivate()
    log(f"PCG snapshot complete: {len(STATE['pcg_states'])} components, all inactive for test")


def restore_editor_state():
    character = STATE.get("editor_character")
    original_transform = STATE.get("original_character_transform")
    if character and original_transform:
        try:
            character.set_actor_transform(make_transform(original_transform), False, True)
            character.set_actor_enable_collision(bool(STATE["original_character_collision"]))
        except Exception:
            STATE["errors"].append("Character restore failed:\n" + traceback.format_exc())

    for component, was_active in STATE.get("pcg_states", []):
        try:
            if was_active:
                component.activate(False)
            else:
                component.deactivate()
        except Exception:
            STATE["errors"].append("PCG restore failed:\n" + traceback.format_exc())


def sum_simulated_mass(actor):
    total = 0.0
    details = []
    if not actor:
        return total, details
    for component in actor.get_components_by_class(unreal.PrimitiveComponent):
        try:
            if component.is_simulating_physics():
                mass = float(component.get_mass())
                total += mass
                details.append({
                    "component": component.get_name(),
                    "class": component.get_class().get_name(),
                    "mass_kg": mass,
                })
        except Exception:
            pass
    return total, details


def prepare_editor_case(case_name):
    world = editor_world()
    boat = find_actor(world, "BP_Boat")
    character = STATE["editor_character"]
    if not boat or not character:
        raise RuntimeError("BP_Boat or 'my guy' disappeared from the editor world")

    # The character is already parked away from the boat in the user's level.
    # Only the character case needs a temporary editor transform so every
    # simulated child body is duplicated into PIE at the correct pose.
    character.set_actor_transform(make_transform(STATE["original_character_transform"]), False, True)
    character.set_actor_enable_collision(bool(STATE["original_character_collision"]))
    if case_name == "character":
        character.set_actor_transform(character_test_transform(boat), False, True)
        character.set_actor_enable_collision(True)

    subsystem = level_subsystem()
    if subsystem.is_in_play_in_editor():
        raise RuntimeError("PIE was unexpectedly active before a case")
    subsystem.editor_request_begin_play()
    STATE["case_started_real"] = time.time()
    STATE["step"] = "wait_for_pie"
    log(f"Requested PIE for case={case_name}")


def configure_pie_case(case_name, world):
    boat = find_actor(world, "BP_Boat")
    character = find_actor(world, "my guy")
    cube = find_actor(world, "Cube2")
    boat_mesh = find_component(boat, "SM_Boat")
    if not boat or not boat_mesh or not character:
        raise RuntimeError("PIE copy is missing BP_Boat.SM_Boat or 'my guy'")

    unreal.GameplayStatics.set_game_paused(world, False)
    if case_name != "character":
        character.set_actor_enable_collision(False)

    load_mass = 0.0
    load_components = []
    movement_mass = 0.0

    if case_name == "cube_90kg":
        if not cube or not isinstance(cube, unreal.StaticMeshActor):
            raise RuntimeError("PIE copy is missing reusable StaticMeshActor 'Cube2'")
        cube_component = cube.static_mesh_component
        cube_component.set_simulate_physics(False)
        cube_component.set_mobility(unreal.ComponentMobility.MOVABLE)
        cube.set_actor_scale3d(unreal.Vector(0.5, 0.5, 0.5))
        cube_location = boat.get_actor_transform().transform_location(CUBE_RELATIVE_LOCATION)
        cube.set_actor_location(cube_location, False, True)
        cube.set_actor_rotation(boat.get_actor_rotation(), True)
        cube_component.set_collision_profile_name(unreal.Name("PhysicsActor"), True)
        cube_component.set_simulate_physics(True)
        cube_component.set_mass_override_in_kg(unreal.Name("None"), 90.0, True)
        cube_component.wake_all_rigid_bodies()
        load_mass = float(cube_component.get_mass())
        load_components = [{
            "component": cube_component.get_name(),
            "class": cube_component.get_class().get_name(),
            "mass_kg": load_mass,
        }]
    elif case_name == "character":
        load_mass, load_components = sum_simulated_mass(character)
        movement = find_component(character, "CharMoveComp")
        if movement:
            try:
                movement_mass = float(movement.get_editor_property("mass"))
            except Exception:
                pass

    boat_mesh.wake_all_rigid_bodies()
    STATE["active"] = {
        "world": world,
        "boat": boat,
        "boat_mesh": boat_mesh,
        "character": character,
        "cube": cube,
        "boat_mass_kg": float(boat_mesh.get_mass()),
        "simulated_load_mass_kg": load_mass,
        "movement_mass_kg": movement_mass,
        "load_components": load_components,
    }
    STATE["samples"] = []
    STATE["case_started_game"] = float(unreal.GameplayStatics.get_time_seconds(world))
    STATE["last_progress_game"] = STATE["case_started_game"]
    STATE["last_progress_real"] = time.time()
    STATE["step"] = "collect"
    log(
        f"Collecting case={case_name} boat_mass={STATE['active']['boat_mass_kg']:.3f}kg "
        f"sim_load={load_mass:.3f}kg movement_mass={movement_mass:.3f}kg"
    )


def sample_active_case(case_name):
    active = STATE["active"]
    world = active["world"]
    boat_mesh = active["boat_mesh"]
    game_time = float(unreal.GameplayStatics.get_time_seconds(world))
    elapsed = game_time - STATE["case_started_game"]
    location = boat_mesh.get_world_location()
    velocity = boat_mesh.get_physics_linear_velocity()
    rotation = boat_mesh.get_world_rotation()
    STATE["samples"].append({
        "t": elapsed,
        "z": float(location.z),
        "vz": float(velocity.z),
        "tilt": max(abs(float(rotation.roll)), abs(float(rotation.pitch))),
    })

    if game_time > STATE["last_progress_game"] + 0.01:
        STATE["last_progress_game"] = game_time
        STATE["last_progress_real"] = time.time()
    elif time.time() - STATE["last_progress_real"] > 10.0:
        raise RuntimeError(f"PIE game time stopped advancing during case={case_name}")

    if elapsed >= CASE_DURATION_SECONDS:
        result = summarize_case(case_name, STATE["samples"], active)
        STATE["results"].append(result)
        level_subsystem().editor_request_end_play()
        STATE["case_started_real"] = time.time()
        STATE["step"] = "wait_for_pie_end"
        log(
            f"Case complete: {case_name} mean_z={result['settled_mean_z']:.3f} "
            f"trend={result['settled_trend_cm_s']:.3f}cm/s std={result['settled_stddev_z']:.3f}"
        )


def summarize_case(case_name, samples, active):
    if not samples:
        raise RuntimeError(f"No samples collected for {case_name}")
    window_start = max(samples[-1]["t"] - FINAL_WINDOW_SECONDS, 0.0)
    window = [sample for sample in samples if sample["t"] >= window_start]
    times = [sample["t"] for sample in window]
    zs = [sample["z"] for sample in window]
    mean_t = statistics.fmean(times)
    mean_z = statistics.fmean(zs)
    denominator = sum((value - mean_t) ** 2 for value in times)
    trend = (
        sum((sample["t"] - mean_t) * (sample["z"] - mean_z) for sample in window) / denominator
        if denominator > 1.0e-9 else 0.0
    )
    return {
        "case": case_name,
        "sample_count": len(samples),
        "boat_mass_kg": active["boat_mass_kg"],
        "simulated_load_mass_kg": active["simulated_load_mass_kg"],
        "movement_mass_kg": active["movement_mass_kg"],
        "load_components": active["load_components"],
        "initial_z": samples[0]["z"],
        "minimum_z": min(sample["z"] for sample in samples),
        "final_z": samples[-1]["z"],
        "settled_mean_z": mean_z,
        "settled_stddev_z": statistics.pstdev(zs) if len(zs) > 1 else 0.0,
        "settled_trend_cm_s": trend,
        "settled_mean_abs_vz": statistics.fmean(abs(sample["vz"]) for sample in window),
        "maximum_tilt_deg": max(sample["tilt"] for sample in samples),
        "minimum_relative_to_initial_cm": min(sample["z"] - samples[0]["z"] for sample in samples),
        "duration_game_seconds": samples[-1]["t"],
    }


def apply_verdicts():
    if len(STATE["results"]) != len(CASES):
        return
    empty = next(result for result in STATE["results"] if result["case"] == "empty")
    baseline = empty["settled_mean_z"]
    sink_delta = max(75.0, 4.0 * empty["settled_stddev_z"])
    threshold = baseline - sink_delta
    for result in STATE["results"]:
        continued_descent = (
            result["settled_trend_cm_s"] < -10.0
            and result["final_z"] < baseline - 50.0
        )
        sunk = (
            result["settled_mean_z"] < threshold
            or result["minimum_z"] < baseline - 250.0
            or continued_descent
        )
        settled = (
            abs(result["settled_trend_cm_s"]) < 5.0
            and result["settled_stddev_z"] < 25.0
            and result["settled_mean_abs_vz"] < 25.0
        )
        result["empty_baseline_z"] = baseline
        result["sink_threshold_z"] = threshold
        result["depth_below_empty_mean_cm"] = baseline - result["settled_mean_z"]
        result["verdict"] = "SINKING" if sunk else "FLOATING"
        result["settled"] = bool(settled)


def write_report():
    apply_verdicts()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    report = {
        "ok": not STATE["errors"],
        "pipeline": "live editor bridge -> Slate post-tick state machine -> copied PIE world",
        "map": "/Game/mybasic",
        "cases": list(CASES),
        "case_duration_seconds": CASE_DURATION_SECONDS,
        "final_window_seconds": FINAL_WINDOW_SECONDS,
        "criteria": {
            "sinking": "mean below max(75 cm, 4x empty std), or 250 cm deep excursion, or final descent faster than 10 cm/s while 50 cm below empty",
            "settled": "abs trend <5 cm/s, stddev <25 cm, mean abs vertical speed <25 cm/s",
        },
        "results": STATE["results"],
        "errors": STATE["errors"],
        "elapsed_wall_seconds": time.time() - STATE["started_at"],
        "temporary_content_assets_created": 0,
        "level_saved": False,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    log(f"Report written: {OUT_PATH}")


def finish():
    try:
        subsystem = level_subsystem()
        if subsystem and subsystem.is_in_play_in_editor():
            subsystem.editor_request_end_play()
    except Exception:
        STATE["errors"].append("PIE shutdown failed:\n" + traceback.format_exc())
    restore_editor_state()
    write_report()
    if STATE["handle"] is not None:
        unreal.unregister_slate_post_tick_callback(STATE["handle"])
        STATE["handle"] = None
    STATE["finished"] = True
    STATE["step"] = "done"
    log(f"DONE results={len(STATE['results'])} errors={len(STATE['errors'])}")


def tick(_delta_seconds):
    try:
        case_name = CASES[STATE["case_index"]] if STATE["case_index"] < len(CASES) else None

        if STATE["step"] == "init":
            subsystem = level_subsystem()
            if subsystem.is_in_play_in_editor():
                raise RuntimeError("Refusing to start because PIE is already active")
            world = editor_world()
            boat = find_actor(world, "BP_Boat")
            character = find_actor(world, "my guy")
            if not world or not boat or not character or not find_component(boat, "SM_Boat"):
                raise RuntimeError("Editor world is missing BP_Boat.SM_Boat or actor label 'my guy'")
            STATE["editor_character"] = character
            STATE["original_character_transform"] = transform_dict(character.get_actor_transform())
            STATE["original_character_collision"] = bool(character.get_actor_enable_collision())
            snapshot_and_disable_pcg(world)
            prepare_editor_case(case_name)
            return

        if STATE["step"] == "wait_for_pie":
            world = pie_world()
            if world:
                configure_pie_case(case_name, world)
                return
            if time.time() - STATE["case_started_real"] > CASE_TIMEOUT_SECONDS:
                raise RuntimeError(f"Timed out waiting for PIE world for case={case_name}")
            return

        if STATE["step"] == "collect":
            if not pie_world():
                raise RuntimeError(f"PIE ended unexpectedly during case={case_name}")
            sample_active_case(case_name)
            return

        if STATE["step"] == "wait_for_pie_end":
            if pie_world() or level_subsystem().is_in_play_in_editor():
                if time.time() - STATE["case_started_real"] > CASE_TIMEOUT_SECONDS:
                    raise RuntimeError(f"Timed out ending PIE for case={case_name}")
                return
            restore_editor_state()
            STATE["case_index"] += 1
            if STATE["case_index"] >= len(CASES):
                finish()
                return
            STATE["step"] = "prepare_next"
            STATE["case_started_real"] = time.time()
            return

        if STATE["step"] == "prepare_next":
            # Give Unreal a short editor tick boundary between PIE sessions.
            if time.time() - STATE["case_started_real"] < 0.75:
                return
            prepare_editor_case(CASES[STATE["case_index"]])
            return

    except Exception:
        STATE["errors"].append(traceback.format_exc())
        unreal.log_error("[BoatBuoyancyMetrics] " + STATE["errors"][-1])
        finish()


def start():
    global PROPHECY_BOAT_METRIC_STATE
    existing = globals().get("PROPHECY_BOAT_METRIC_STATE")
    if existing and not existing.get("finished", False):
        raise RuntimeError("Boat buoyancy metric run is already active")
    PROPHECY_BOAT_METRIC_STATE = STATE
    STATE["handle"] = unreal.register_slate_post_tick_callback(tick)
    print(json.dumps({"ok": True, "scheduled": True, "cases": CASES, "output": OUT_PATH}, indent=2))


start()
