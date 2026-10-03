import json
from pathlib import Path
import unreal

assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
assert world.get_path_name() == '/Game/testNN.testNN'
path = Path(unreal.Paths.project_saved_dir()).resolve() / 'JoltMigration/PoseIntegrity-20260910/clean-before-build.json'
assert not path.exists()
path.write_text(json.dumps({'map': world.get_path_name(), 'pie': False, 'dirty_maps': [], 'dirty_content': [], 'reason':'Normal build to persist skeletal handoff fix'}, indent=2))
unreal.SystemLibrary.quit_editor()
