"""Run isolated BP_Boat sinking metrics in a disposable map.

This must be scheduled through the live editor bridge.  It changes the active
editor map only after proving the original map is clean, owns PIE through a
Slate post-tick state machine, reloads the original map in all exit paths, and
never saves the original map.  The caller removes the temporary .umap after
the original map is loaded again.
"""

import json
import gc
import os
import statistics
import time
import traceback

import unreal


ORIGINAL_MAP = "/Game/mybasic"
TEMP_MAP = "/Game/__CodexTemp/BoatBuoyancyMetricMap"
OUT_PATH = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "Profiling",
    "BoatBuoyancy",
    "latest_metrics.json",
)
CASES = ("empty", "cube_90kg", "character")
DURATION = 12.0
FINAL_WINDOW = 3.0
TIMEOUT = 90.0
BOAT_Z = -75.531329
CHAR_RELATIVE = unreal.Vector(-29.2983799, -12.6322797, 105.6019280)
CUBE_RELATIVE = unreal.Vector(-29.2983799, -12.6322797, 70.0)


STATE = {
    "handle": None,
    "step": "init",
    "case_index": 0,
    "phase_started": time.time(),
    "game_started": 0.0,
    "last_game_time": 0.0,
    "last_game_progress_real": time.time(),
    "samples": [],
    "results": [],
    "errors": [],
    "started": time.time(),
    "finished": False,
    "original_world_path": None,
    "switched_to_temp": False,
    "actors": {},
    "active": None,
    "cleanup_ready": False,
}


def log(message):
    unreal.log(f"[BoatTempMapMetrics] {message}")


def level_subsystem():
    return unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)


def editor_world():
    subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    return subsystem.get_editor_world() if subsystem else None


def pie_world():
    worlds = list(unreal.EditorLevelLibrary.get_pie_worlds(True))
    return worlds[0] if worlds else None


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


def configure_static_mesh_actor(actor, mesh, mobility, collision, scale, simulate=False):
    component = actor.static_mesh_component
    component.set_simulate_physics(False)
    component.set_mobility(mobility)
    component.set_static_mesh(mesh)
    actor.set_actor_scale3d(scale)
    component.set_collision_profile_name(unreal.Name(collision), True)
    component.set_simulate_physics(bool(simulate))
    return component


def preflight_original_map():
    current = editor_world()
    if not current or not current.get_path_name().startswith(ORIGINAL_MAP + "."):
        raise RuntimeError(f"Expected {ORIGINAL_MAP}, found {current}")
    dirty_maps = [package.get_path_name() for package in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    if dirty_maps:
        raise RuntimeError(f"Refusing to leave original map because dirty map packages exist: {dirty_maps}")
    return current.get_path_name()


def build_temp_map_after_old_world_release():
    # This function must not receive or acquire any wrapper from the old world
    # before NewBlankMap.  UE's Python wrappers participate in GC references;
    # retaining even the old Package wrapper makes EditorDestroyWorld fatal.
    world = unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    if not world:
        raise RuntimeError("new_blank_map returned no world")
    STATE["switched_to_temp"] = True

    if unreal.EditorAssetLibrary.does_asset_exist(TEMP_MAP):
        raise RuntimeError(f"Temporary map already exists and was not overwritten: {TEMP_MAP}")

    cube_mesh = unreal.load_asset("/Engine/BasicShapes/Cube")
    boat_class = unreal.load_class(None, "/Game/_mygame/assets/boat/StaticMeshes/BP_Boat.BP_Boat_C")
    character_class = unreal.load_class(None, "/Game/_mygame/SandboxCharacter_CMC.SandboxCharacter_CMC_C")
    if not cube_mesh or not boat_class or not character_class:
        raise RuntimeError("Could not load cube mesh, BP_Boat class, or character class")

    floor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.StaticMeshActor, unreal.Vector(0.0, 0.0, -1050.0), unreal.Rotator(), False
    )
    floor.set_actor_label("BoatMetric_Floor")
    configure_static_mesh_actor(
        floor,
        cube_mesh,
        unreal.ComponentMobility.STATIC,
        "BlockAll",
        unreal.Vector(50.0, 50.0, 1.0),
        False,
    )

    boat = unreal.EditorLevelLibrary.spawn_actor_from_class(
        boat_class, unreal.Vector(0.0, 0.0, BOAT_Z), unreal.Rotator(), False
    )
    boat.set_actor_label("BoatMetric_Boat")

    cube = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.StaticMeshActor, unreal.Vector(10000.0, 0.0, 500.0), unreal.Rotator(), False
    )
    cube.set_actor_label("BoatMetric_Cube")
    configure_static_mesh_actor(
        cube,
        cube_mesh,
        unreal.ComponentMobility.MOVABLE,
        "NoCollision",
        unreal.Vector(0.5, 0.5, 0.5),
        False,
    )

    character = unreal.EditorLevelLibrary.spawn_actor_from_class(
        character_class, unreal.Vector(10000.0, 0.0, 500.0), unreal.Rotator(), False
    )
    character.set_actor_label("BoatMetric_Character")
    character.set_actor_enable_collision(False)

    boat_mesh = find_component(boat, "SM_Boat")
    if not boat_mesh:
        raise RuntimeError("Spawned BP_Boat has no SM_Boat component")

    STATE["actors"] = {"floor": floor, "boat": boat, "cube": cube, "character": character}
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, TEMP_MAP):
        raise RuntimeError(f"Could not save temporary map {TEMP_MAP}")
    log(f"Created isolated map {TEMP_MAP} with floor Z=-1050")


def configure_editor_case(case_name):
    actors = STATE["actors"]
    boat = actors["boat"]
    cube = actors["cube"]
    character = actors["character"]
    boat.set_actor_location(unreal.Vector(0.0, 0.0, BOAT_Z), False, True)
    boat.set_actor_rotation(unreal.Rotator(), True)

    cube_component = cube.static_mesh_component
    cube_component.set_simulate_physics(False)
    cube.set_actor_location(unreal.Vector(10000.0, 0.0, 500.0), False, True)
    cube_component.set_collision_profile_name(unreal.Name("NoCollision"), True)

    character.set_actor_location(unreal.Vector(10000.0, 0.0, 500.0), False, True)
    character.set_actor_rotation(unreal.Rotator(), True)
    character.set_actor_enable_collision(False)

    if case_name == "cube_90kg":
        cube.set_actor_location(
            unreal.Vector(CUBE_RELATIVE.x, CUBE_RELATIVE.y, BOAT_Z + CUBE_RELATIVE.z),
            False,
            True,
        )
        cube_component.set_collision_profile_name(unreal.Name("PhysicsActor"), True)
        cube_component.set_simulate_physics(True)
        cube_component.set_mass_override_in_kg(unreal.Name("None"), 90.0, True)
    elif case_name == "character":
        character.set_actor_location(
            unreal.Vector(
                CHAR_RELATIVE.x,
                CHAR_RELATIVE.y,
                BOAT_Z + CHAR_RELATIVE.z,
            ),
            False,
            True,
        )
        character.set_actor_rotation(
            unreal.Rotator(yaw=4.2599558, pitch=0.0, roll=0.0), True
        )
        character.set_actor_enable_collision(True)

    level_subsystem().editor_request_begin_play()
    STATE["phase_started"] = time.time()
    STATE["step"] = "wait_pie"
    log(f"Requested isolated PIE case={case_name}")


def simulated_mass(actor):
    total = 0.0
    details = []
    for component in actor.get_components_by_class(unreal.PrimitiveComponent):
        try:
            if component.is_simulating_physics():
                mass = float(component.get_mass())
                total += mass
                details.append({"component": component.get_name(), "mass_kg": mass})
        except Exception:
            pass
    return total, details


def begin_collection(case_name, world):
    boat = find_actor(world, "BoatMetric_Boat")
    cube = find_actor(world, "BoatMetric_Cube")
    character = find_actor(world, "BoatMetric_Character")
    boat_mesh = find_component(boat, "SM_Boat")
    if not boat or not boat_mesh or not cube or not character:
        raise RuntimeError("PIE copy is missing one or more isolated test actors")
    unreal.GameplayStatics.set_game_paused(world, False)

    load_mass = 0.0
    movement_mass = 0.0
    load_details = []
    if case_name == "cube_90kg":
        component = cube.static_mesh_component
        component.set_mass_override_in_kg(unreal.Name("None"), 90.0, True)
        component.wake_all_rigid_bodies()
        load_mass = float(component.get_mass())
        load_details = [{"component": component.get_name(), "mass_kg": load_mass}]
    elif case_name == "character":
        load_mass, load_details = simulated_mass(character)
        movement = find_component(character, "CharMoveComp")
        if movement:
            try:
                movement_mass = float(movement.get_editor_property("mass"))
            except Exception:
                pass

    boat_mesh.wake_all_rigid_bodies()
    STATE["active"] = {
        "world": world,
        "boat_mesh": boat_mesh,
        "boat_mass": float(boat_mesh.get_mass()),
        "load_mass": load_mass,
        "movement_mass": movement_mass,
        "load_details": load_details,
    }
    STATE["samples"] = []
    now_game = float(unreal.GameplayStatics.get_time_seconds(world))
    STATE["game_started"] = now_game
    STATE["last_game_time"] = now_game
    STATE["last_game_progress_real"] = time.time()
    STATE["step"] = "collect"
    log(
        f"Collecting {case_name}: boat={STATE['active']['boat_mass']:.3f}kg "
        f"load={load_mass:.3f}kg movement={movement_mass:.3f}kg"
    )


def summarize(case_name):
    samples = STATE["samples"]
    active = STATE["active"]
    if not samples:
        raise RuntimeError(f"No samples for {case_name}")
    window_start = max(samples[-1]["t"] - FINAL_WINDOW, 0.0)
    window = [sample for sample in samples if sample["t"] >= window_start]
    mean_t = statistics.fmean(sample["t"] for sample in window)
    mean_z = statistics.fmean(sample["z"] for sample in window)
    denom = sum((sample["t"] - mean_t) ** 2 for sample in window)
    trend = (
        sum((sample["t"] - mean_t) * (sample["z"] - mean_z) for sample in window) / denom
        if denom > 1.0e-9 else 0.0
    )
    zs = [sample["z"] for sample in window]
    return {
        "case": case_name,
        "samples": len(samples),
        "duration_game_seconds": samples[-1]["t"],
        "boat_mass_kg": active["boat_mass"],
        "simulated_load_mass_kg": active["load_mass"],
        "movement_mass_kg": active["movement_mass"],
        "load_components": active["load_details"],
        "initial_z": samples[0]["z"],
        "minimum_z": min(sample["z"] for sample in samples),
        "final_z": samples[-1]["z"],
        "settled_mean_z": mean_z,
        "settled_stddev_z": statistics.pstdev(zs) if len(zs) > 1 else 0.0,
        "settled_trend_cm_s": trend,
        "settled_mean_abs_vz": statistics.fmean(abs(sample["vz"]) for sample in window),
        "maximum_tilt_deg": max(sample["tilt"] for sample in samples),
    }


def collect(case_name):
    active = STATE["active"]
    world = active["world"]
    mesh = active["boat_mesh"]
    game_time = float(unreal.GameplayStatics.get_time_seconds(world))
    elapsed = game_time - STATE["game_started"]
    location = mesh.get_world_location()
    rotation = mesh.get_world_rotation()
    velocity = mesh.get_physics_linear_velocity()
    STATE["samples"].append({
        "t": elapsed,
        "z": float(location.z),
        "vz": float(velocity.z),
        "tilt": max(abs(float(rotation.roll)), abs(float(rotation.pitch))),
    })

    if game_time > STATE["last_game_time"] + 0.01:
        STATE["last_game_time"] = game_time
        STATE["last_game_progress_real"] = time.time()
    elif time.time() - STATE["last_game_progress_real"] > 10.0:
        raise RuntimeError(f"Game time stopped during {case_name}")

    if elapsed >= DURATION:
        result = summarize(case_name)
        STATE["results"].append(result)
        # Release persistent wrappers to the PIE world before asking Unreal to
        # destroy it.  Locals disappear when this Slate callback returns.
        STATE["active"] = None
        STATE["samples"] = []
        level_subsystem().editor_request_end_play()
        STATE["phase_started"] = time.time()
        STATE["step"] = "wait_pie_end"
        log(
            f"Completed {case_name}: mean_z={result['settled_mean_z']:.3f} "
            f"trend={result['settled_trend_cm_s']:.3f} std={result['settled_stddev_z']:.3f}"
        )


def add_verdicts():
    if len(STATE["results"]) != len(CASES):
        return
    empty = next(result for result in STATE["results"] if result["case"] == "empty")
    baseline = empty["settled_mean_z"]
    threshold = baseline - max(75.0, 4.0 * empty["settled_stddev_z"])
    for result in STATE["results"]:
        continued = result["settled_trend_cm_s"] < -10.0 and result["final_z"] < baseline - 50.0
        sinking = (
            result["settled_mean_z"] < threshold
            or result["minimum_z"] < baseline - 250.0
            or continued
        )
        settled = (
            abs(result["settled_trend_cm_s"]) < 5.0
            and result["settled_stddev_z"] < 25.0
            and result["settled_mean_abs_vz"] < 25.0
        )
        result.update({
            "empty_baseline_z": baseline,
            "sink_threshold_z": threshold,
            "depth_below_empty_mean_cm": baseline - result["settled_mean_z"],
            "verdict": "SINKING" if sinking else "FLOATING",
            "settled": bool(settled),
        })


def write_report():
    add_verdicts()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    current = editor_world()
    report = {
        "ok": len(STATE["errors"]) == 0 and len(STATE["results"]) == len(CASES),
        "pipeline": "live bridge -> disposable saved map -> asynchronous PIE -> original map reload",
        "original_map": ORIGINAL_MAP,
        "temporary_map": TEMP_MAP,
        "current_world_after_cleanup": current.get_path_name() if current else None,
        "temporary_map_file_cleanup_ready": bool(STATE["cleanup_ready"]),
        "level_saved": ORIGINAL_MAP not in [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
        "duration_per_case_seconds": DURATION,
        "final_window_seconds": FINAL_WINDOW,
        "criteria": {
            "sinking": "mean >75 cm below empty (or 4x empty std), 250 cm deep excursion, or >10 cm/s continued descent while >50 cm low",
            "settled": "abs trend <5 cm/s, std <25 cm, mean abs Vz <25 cm/s",
        },
        "results": STATE["results"],
        "errors": STATE["errors"],
        "wall_seconds": time.time() - STATE["started"],
    }
    with open(OUT_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    log(f"Wrote {OUT_PATH}")


def finalize_report_and_callback():
    write_report()
    if STATE["handle"] is not None:
        unreal.unregister_slate_post_tick_callback(STATE["handle"])
        STATE["handle"] = None
    STATE["finished"] = True
    STATE["step"] = "done"
    log(f"DONE results={len(STATE['results'])} errors={len(STATE['errors'])}")


def release_temp_wrappers_for_next_tick():
    # Map unload must happen on a later Slate tick, after this frame and all
    # Python locals that referenced temp actors/worlds are gone.
    STATE["active"] = None
    STATE["actors"] = {}
    STATE["samples"] = []
    gc.collect()
    STATE["step"] = "load_original"


def load_original_and_finish():
    try:
        world = unreal.EditorLoadingAndSavingUtils.load_map(ORIGINAL_MAP)
        if not world or not world.get_path_name().startswith(ORIGINAL_MAP + "."):
            raise RuntimeError(f"Failed to reload {ORIGINAL_MAP}: {world}")
        STATE["cleanup_ready"] = True
    except Exception:
        STATE["errors"].append("Original map reload failed:\n" + traceback.format_exc())
    finalize_report_and_callback()


def fail(message):
    STATE["errors"].append(message)
    unreal.log_error("[BoatTempMapMetrics] " + message)
    try:
        if level_subsystem().is_in_play_in_editor():
            STATE["active"] = None
            STATE["samples"] = []
            level_subsystem().editor_request_end_play()
            STATE["step"] = "cleanup_wait"
            STATE["phase_started"] = time.time()
            return
    except Exception:
        STATE["errors"].append(traceback.format_exc())
    if STATE["switched_to_temp"]:
        STATE["step"] = "release_temp_refs"
    else:
        STATE["cleanup_ready"] = True
        finalize_report_and_callback()


def tick(_delta_seconds):
    try:
        if STATE["step"] == "init":
            if level_subsystem().is_in_play_in_editor():
                raise RuntimeError("PIE was already active")
            # Preflight and map destruction are deliberately separate ticks so
            # no old-world Python wrapper survives into NewBlankMap.
            STATE["original_world_path"] = preflight_original_map()
            STATE["step"] = "switch_map"
            return

        if STATE["step"] == "switch_map":
            build_temp_map_after_old_world_release()
            configure_editor_case(CASES[0])
            return

        case_name = CASES[STATE["case_index"]] if STATE["case_index"] < len(CASES) else None
        if STATE["step"] == "wait_pie":
            world = pie_world()
            if world:
                begin_collection(case_name, world)
            elif time.time() - STATE["phase_started"] > TIMEOUT:
                raise RuntimeError(f"Timed out creating PIE for {case_name}")
            return

        if STATE["step"] == "collect":
            if not pie_world():
                raise RuntimeError(f"PIE ended unexpectedly during {case_name}")
            collect(case_name)
            return

        if STATE["step"] == "wait_pie_end":
            if pie_world() or level_subsystem().is_in_play_in_editor():
                if time.time() - STATE["phase_started"] > TIMEOUT:
                    raise RuntimeError(f"Timed out ending PIE for {case_name}")
                return
            STATE["case_index"] += 1
            if STATE["case_index"] >= len(CASES):
                STATE["step"] = "release_temp_refs"
                return
            STATE["phase_started"] = time.time()
            STATE["step"] = "between_cases"
            return

        if STATE["step"] == "between_cases":
            if time.time() - STATE["phase_started"] < 0.75:
                return
            configure_editor_case(CASES[STATE["case_index"]])
            return

        if STATE["step"] == "cleanup_wait":
            if not pie_world() and not level_subsystem().is_in_play_in_editor():
                STATE["step"] = "release_temp_refs"
            elif time.time() - STATE["phase_started"] > TIMEOUT:
                STATE["errors"].append("Timed out waiting for PIE cleanup")
                STATE["step"] = "release_temp_refs"
            return

        if STATE["step"] == "release_temp_refs":
            release_temp_wrappers_for_next_tick()
            return

        if STATE["step"] == "load_original":
            load_original_and_finish()
            return

    except Exception:
        fail(traceback.format_exc())


def start():
    global PROPHECY_BOAT_TEMP_MAP_STATE
    existing = globals().get("PROPHECY_BOAT_TEMP_MAP_STATE")
    if existing and not existing.get("finished", False):
        raise RuntimeError("Temporary-map boat metric run is already active")
    PROPHECY_BOAT_TEMP_MAP_STATE = STATE
    STATE["handle"] = unreal.register_slate_post_tick_callback(tick)
    print(json.dumps({
        "ok": True,
        "scheduled": True,
        "original_map": ORIGINAL_MAP,
        "temporary_map": TEMP_MAP,
        "output": OUT_PATH,
    }, indent=2))


start()
