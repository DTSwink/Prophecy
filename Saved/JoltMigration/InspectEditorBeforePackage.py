"""Read-only editor state before requesting the final package build window."""
import json
from pathlib import Path
import unreal

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
report = {'world': world.get_path_name() if world else None,
          'pie': unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(),
          'dirty_maps': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
          'dirty_content': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]}
target = Path(unreal.Paths.project_saved_dir()).resolve()/'JoltMigration/EditorBeforeFinalPackage.json'
target.write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
