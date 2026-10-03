import json
import re
from pathlib import Path
import unreal

folder = Path(unreal.Paths.project_saved_dir()).resolve() / 'JoltMigration/HighGainCrash-20260910'
log = (folder / 'EditorSafety.log').read_text(encoding='utf-8', errors='replace')
starts = list(re.finditer(r'Found (\d+) automation tests based on', log))
assert starts, 'Automation has not discovered tests yet'
start = starts[-1]
test_log = log[start.start():]
completed = re.findall(r'Test Completed\. Result=\{([^}]+)\} Name=\{[^}]+\} Path=\{([^}]+)\}', test_log)
assert len(completed) == int(start[1]), (len(completed), start[1])
assert all(result == 'Success' for result, _ in completed), completed
required = {
    'Prophecy.Jolt.NumericalSafety.RotationCorrections',
    'Prophecy.Jolt.NumericalSafety.PositionCorrections',
    'Prophecy.Jolt.NumericalSafety.WorkerSolverContainment',
    'Prophecy.Jolt.Character.HighMagnetizationSafety',
}
assert required.issubset({name for _, name in completed})
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
result = {
    'test_count': len(completed),
    'tests': [{'name': name, 'result': result} for result, name in completed],
    'stress_results': [line for line in test_log.splitlines() if 'max_body_movement_cm=' in line or 'safely stopped after' in line],
    'warnings': [line for line in test_log.splitlines() if 'LogAutomationController: Warning:' in line],
    'map': world.get_path_name(),
    'pie': unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(),
    'dirty_maps': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
    'dirty_content': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
}
assert not result['pie']
(folder / 'Automation.log').write_text(test_log, encoding='utf-8')
(folder / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps({key: value for key, value in result.items() if key != 'tests'}))
