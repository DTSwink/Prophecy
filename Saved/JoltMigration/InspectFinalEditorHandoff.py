"""Read-only confirmation that the requested editor map is ready after package checks."""
import json
from pathlib import Path
import unreal

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
report = {
    "world": world.get_path_name() if world else None,
    "pie": unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(),
    "dirty_maps": [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
    "dirty_content": [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
    "jolt_blueprint_library_available": hasattr(unreal, "ProphecyJoltBlueprintLibrary"),
}
assert report["world"] == "/Game/testNN.testNN", report
assert report["pie"] is False, report
assert report["jolt_blueprint_library_available"], report
target = Path(unreal.Paths.project_saved_dir()).resolve() / "JoltMigration/FinalEditorHandoff-20260910.json"
assert not target.exists(), str(target)
target.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
