import json
from pathlib import Path
from datetime import datetime
import unreal

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not levels.is_in_play_in_editor(), 'Run before the visual PIE session'
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
scratch = Path.home() / '.codex/tmp/ProphecyJolt' / ('SwordContact-' + stamp + '.json')
target = Path(unreal.Paths.project_saved_dir()).resolve() / 'JoltMigration' / ('SwordContact-' + stamp + '.json')
assert not scratch.exists() and not target.exists()
unreal.SystemLibrary.execute_console_command(world, 'Prophecy.Jolt.SwordContactFixture ' + scratch.as_posix())
assert scratch.exists(), 'Native contact fixture produced no report'
target.write_text(scratch.read_text(encoding='utf-8-sig'), encoding='utf-8')
result = json.loads(target.read_text())
print('SWORD_CONTACT_REPORT ' + str(target))
print(json.dumps({k:v for k,v in result.items() if k != 'samples'}, indent=2))
assert result.get('success'), result.get('error')
