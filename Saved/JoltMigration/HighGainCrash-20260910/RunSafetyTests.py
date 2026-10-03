import json
from pathlib import Path
import unreal

assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
folder = Path(unreal.Paths.project_saved_dir()).resolve() / 'JoltMigration/HighGainCrash-20260910'
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
state = {
    'map': world.get_path_name(),
    'pie': False,
    'dirty_maps': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
    'dirty_content': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
}
(folder / 'editor-state-before-tests.json').write_text(json.dumps(state, indent=2))
print(json.dumps(state))
unreal.SystemLibrary.execute_console_command(world, 'Automation RunTests Prophecy.Jolt')
