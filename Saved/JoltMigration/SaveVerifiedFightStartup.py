import hashlib
import json
from pathlib import Path
import unreal

root = Path(unreal.Paths.project_dir()).resolve()
output = root / "Saved/JoltMigration/FightStartup-20260910"
placement = json.loads((output / "placement.json").read_text(encoding="utf-8"))
reports = sorted(output.glob("startup-*.json"), key=lambda p: p.stat().st_mtime)
assert reports
startup = json.loads(reports[-1].read_text(encoding="utf-8"))
assert startup["success"] and not startup["visual_test"], startup
assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
assert world.get_path_name() == "/Game/testNN.testNN"
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
dirty_maps = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
assert dirty_maps in ([], ["/Game/testNN"])
source = Path(placement["source"])
disk_hash = hashlib.sha256(source.read_bytes()).hexdigest()
already_saved_after_recovery = not dirty_maps
if already_saved_after_recovery:
    recovered = json.loads((output / 'recovered-state.json').read_text())
    assert disk_hash == recovered['disk_sha256']
    assert not recovered['dirty_maps'] and not recovered['dirty_content']
    assert not recovered['added_other_actors'] and not recovered['removed_other_actors']
else:
    assert disk_hash == placement["before_sha256"]
cls = unreal.load_class(None, "/Script/GameAnimationSample3.ProphecyJoltFightSetup")
setups = unreal.GameplayStatics.get_all_actors_of_class(world, cls)
assert len(setups) == 1 and setups[0].get_path_name() == placement["startup_actor"]
assert setups[0].get_editor_property("bEnableJolt")
other_actors = sorted(a.get_path_name() for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor) if a != setups[0])
assert other_actors == placement["before_actors"]
assert not (output / "publication.json").exists()
if not already_saved_after_recovery:
    assert unreal.EditorLevelLibrary.save_current_level()
report = {"success": True, "map": "/Game/testNN", "startup_actor": placement["startup_actor"],
          "startup_report": str(reports[-1]), "before_sha256": placement["before_sha256"],
          "after_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
          "dirty_maps": [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
          "dirty_content": [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
          "already_saved_when_checked_after_recovery": already_saved_after_recovery,
          "map_saved_by_this_script": not already_saved_after_recovery,
          "other_actor_paths_unchanged": True,
          "visual_test": False, "verification": "Normal Development Editor build succeeded; automatic startup checked in the reopened editor. Visual review and new packaged verification deferred."}
(output / "publication.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
assert not report["dirty_maps"] and not report["dirty_content"], report
print(json.dumps(report, indent=2))
