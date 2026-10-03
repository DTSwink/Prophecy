import json
import re
from pathlib import Path
import unreal

saved = Path(unreal.Paths.project_saved_dir()).resolve()
folder = saved / 'JoltMigration/RuntimeSelfCollision-20260910'
log = (folder / 'Editor.log').read_text(encoding='utf-8', errors='replace')
starts = list(re.finditer(r'Found (\d+) automation tests based on', log))
assert starts, 'Automation has not discovered tests yet'
start = starts[-1]
test_log = log[start.start():]
completed = re.findall(r'Test Completed\. Result=\{([^}]+)\} Name=\{[^}]+\} Path=\{([^}]+)\}', test_log)
assert len(completed) == int(start[1]), (len(completed), start[1])
required = {
    'Prophecy.Jolt.Collision.LiveSelfCollisionContacts',
    'Prophecy.Jolt.Collision.SelfCollisionLayersAtomic',
    'Prophecy.Jolt.Collision.SelfCollisionPreservesExternalContacts',
    'Prophecy.Jolt.Character.RuntimeSelfCollisionControls',
}
assert required.issubset({name for _, name in completed})
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
result = {
    'test_count': len(completed),
    'tests': [{'name': name, 'result': result} for result, name in completed],
    'warnings': [line for line in test_log.splitlines() if 'LogAutomationController: Warning:' in line],
    'errors': [line for line in test_log.splitlines() if 'LogAutomationController: Error:' in line],
    'map': world.get_path_name(),
    'pie': unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor(),
    'dirty_maps': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
    'dirty_content': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
}
assert not result['pie']
(folder / 'Automation.log').write_text(test_log, encoding='utf-8')
(folder / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps({key: value for key, value in result.items() if key != 'tests'}))
assert all(result == 'Success' for result, _ in completed), 'Some tests failed; see result.json'
