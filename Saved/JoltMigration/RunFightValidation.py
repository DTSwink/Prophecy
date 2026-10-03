"""Run the same aggregate entry used by final packaged validation, in the live editor."""
import json
from datetime import datetime
from pathlib import Path
import unreal

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not levels.is_in_play_in_editor(), 'End PIE before the isolated validation'
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
target = Path.home()/'.codex/tmp/ProphecyJolt'/('FightValidation-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
assert not target.exists()
unreal.SystemLibrary.execute_console_command(world, 'Prophecy.Jolt.ValidateFight '+target.as_posix())
report_path = target/'validation.json'
assert report_path.exists(), 'Aggregate validation did not produce a report'
result = json.loads(report_path.read_text(encoding='utf-8-sig'))
print('FIGHT_VALIDATION_REPORT', str(report_path))
print(json.dumps(result, indent=2))
assert result.get('success'), result.get('error')
