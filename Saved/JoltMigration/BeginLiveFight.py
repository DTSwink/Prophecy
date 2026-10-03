"""Explicit temporary PIE setup for one named existing fighter; never saves assets."""
import json
import sys
from pathlib import Path
from datetime import datetime
import unreal

assert len(sys.argv) == 2, 'Pass the exact existing PIE actor name from InspectLiveFight.py'
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
assert world and unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
scratch = Path.home() / '.codex/tmp/ProphecyJolt' / ('VisualBegin-' + stamp + '.json')
target = Path(unreal.Paths.project_saved_dir()).resolve() / 'JoltMigration' / ('VisualBegin-' + stamp + '.json')
assert not scratch.exists() and not target.exists()
unreal.SystemLibrary.execute_console_command(world, 'Prophecy.Jolt.VisualBegin ' + scratch.as_posix() + ' ' + sys.argv[1])
assert scratch.exists(), 'Native visual startup produced no report'
target.write_text(scratch.read_text(encoding='utf-8-sig'), encoding='utf-8')
result = json.loads(target.read_text())
print('VISUAL_BEGIN_REPORT ' + str(target))
print(json.dumps(result, indent=2))
assert result.get('startup_success'), result.get('startup_error')
