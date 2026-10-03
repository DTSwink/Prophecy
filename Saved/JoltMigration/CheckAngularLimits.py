import json
from pathlib import Path
import unreal

assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
assert hasattr(unreal.ProphecyAgent, 'set_use_authored_angular_limits'), 'New Blueprint node is not loaded'
report = Path(unreal.Paths.project_saved_dir()).resolve() / 'JoltMigration/AngularLimits-20260910'
report.mkdir(exist_ok=True)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
state = {'world': world.get_path_name(), 'pie': False, 'node_loaded': True,
         'dirty_maps': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
         'dirty_content': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]}
(report / 'editor-state.json').write_text(json.dumps(state, indent=2))
print(json.dumps(state))
unreal.SystemLibrary.execute_console_command(world, 'Automation RunTests Prophecy.Jolt.RigWorld.LiveAngularLimitsAtomic+Prophecy.Jolt.Character.AngularLimitControls')
