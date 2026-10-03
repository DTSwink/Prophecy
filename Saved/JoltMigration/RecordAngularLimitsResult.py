import json
import sys
from pathlib import Path
import unreal

folder = Path(unreal.Paths.project_saved_dir()).resolve() / 'JoltMigration/AngularLimits-20260910'
log_name = 'EditorFixtureReopened.log' if 'fixture' in sys.argv[1:] else 'EditorReopened.log'
log = (folder / log_name).read_text(encoding='utf-8', errors='replace')
names = ['Prophecy.Jolt.RigWorld.LiveAngularLimitsAtomic', 'Prophecy.Jolt.Character.AngularLimitControls']
history = [line for line in log.splitlines() if 'Test Completed.' in line and any('Path={' + name + '}' in line for name in names)]
start = log.rindex('Found 2 automation tests based on')
test_log = log[start:]
completed = [line for line in test_log.splitlines() if 'Test Completed.' in line and any('Path={' + name + '}' in line for name in names)]
assert len(completed) == 2 and all('Result={Success}' in line for line in completed), completed
assert 'LogAutomationController: Error:' not in test_log
(folder / 'Automation.log').write_text(test_log, encoding='utf-8')
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
result = {'tests': completed, 'run_history': history, 'source_log': log_name,
          'test_warnings': [line for line in test_log.splitlines() if 'LogAutomationController: Warning:' in line],
          'node_loaded': hasattr(unreal.ProphecyAgent, 'set_use_authored_angular_limits'),
          'map': world.get_path_name(),
          'pie': unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(),
          'dirty_maps': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
          'dirty_content': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]}
assert result['node_loaded'] and not result['pie']
(folder / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result))
