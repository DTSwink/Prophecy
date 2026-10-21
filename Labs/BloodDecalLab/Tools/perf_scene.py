"""CPU stress checks in the isolated lab; no user project or rendering."""
import json
import pathlib
import statistics
import unreal

assert pathlib.Path(unreal.Paths.get_project_file_path()).stem == "BloodDecalLab"
assert "-nullrhi" in unreal.SystemLibrary.get_command_line().lower()
world = unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
material = unreal.load_asset("/Game/Lab/M_Blood")
out = pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())) / "Results"
report = {"scope": "NullRHI native ProcessChanges timing; no GPU or render-thread cost"}

def measure(name, setup, update, trials=12):
    times = []
    counters = []
    updates = []
    totals = []
    allocation_max = 0
    for _ in range(trials):
        a = actors.spawn_actor_from_class(unreal.BloodMergeScene, unreal.Vector())
        a.set_editor_property("decal_material", material)
        setup(a)
        before_created = a.get_editor_property("created_components")
        update(a)
        trial_times = [a.get_editor_property("last_update_ms")]
        allocation_max = max(allocation_max, a.get_editor_property("created_components")-before_created)
        while a.has_pending_changes():
            before_created = a.get_editor_property("created_components")
            a.process_changes()
            trial_times.append(a.get_editor_property("last_update_ms"))
            allocation_max = max(allocation_max, a.get_editor_property("created_components")-before_created)
            assert len(trial_times)<2048
        times.extend(trial_times)
        updates.append(len(trial_times))
        totals.append(sum(trial_times))
        counters.append(a.get_editor_property("active_decals"))
        actors.destroy_actor(a)
    times.sort()
    report[name] = {"median_ms":statistics.median(times), "p95_ms":times[int(.95*(len(times)-1))],
                    "max_ms":max(times), "decals_min":min(counters), "decals_max":max(counters),
                    "trials":trials, "measured_updates":len(times), "updates_per_trial_max":max(updates),
                    "total_work_median_ms":statistics.median(totals), "new_components_per_update_max":allocation_max}

def checker(a):
    for y in range(32):
        for x in range(32):
            if (x+y)%2 == 0:
                a.add_cell(x,y)

def filled(a):
    for y in range(32):
        for x in range(32):
            a.add_cell(x,y)

def checker_to_filled(a):
    checker(a)
    while a.has_pending_changes():
        a.process_changes()
    filled(a)

measure("cold_checker_512_components", checker, lambda a:a.process_changes())
measure("cold_full_region_1_component", filled, lambda a:a.process_changes())
measure("collapse_512_components_to_1", checker_to_filled, lambda a:a.process_changes())
measure("idle_no_changes", lambda a:None, lambda a:a.process_changes())
out.mkdir(parents=True, exist_ok=True)
(out/"performance.json").write_text(json.dumps(report,indent=2))
print(json.dumps(report))
