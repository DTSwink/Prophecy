import json
import re
from pathlib import Path
import unreal

assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
saved = Path(unreal.Paths.project_saved_dir()).resolve()
folder = saved / 'JoltMigration/RuntimeSelfCollision-20260910'
log = (saved / 'JoltMigration/HighGainCrash-20260910/EditorSafety.log').read_text(encoding='utf-8', errors='replace')
begin = log.rfind('Found 8 automation tests based on')
assert begin >= 0
text = log[begin:]
results = re.findall(r'Test Completed\. Result=\{([^}]+)\} Name=\{[^}]+\} Path=\{([^}]+)\}', text)
assert len(results) == 8 and all(result == 'Success' for result, _ in results), results
(folder / 'NativeCollisionTests.log').write_text(text, encoding='utf-8')
live_start = log.rfind('Requested Live Coding compile')
(folder / 'LiveCoding.log').write_text(log[live_start:begin], encoding='utf-8')
print('All 8 native collision tests pass. No unsaved packages; closing for the authorized rebuild.')
unreal.SystemLibrary.quit_editor()
