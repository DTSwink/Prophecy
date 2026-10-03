import json
from pathlib import Path
import unreal

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world(), 'Play is active; no graph changes made.'
unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'Prophecy.Editor.BuildSlashTrain')
unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'Prophecy.Sword.AuditCollisionGraph')
bp = unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
cdo = unreal.get_default_object(bp.generated_class())
names = [str(x) for x in cdo.get_editor_property('Codex Slash Train Attacks')]
targets = cdo.get_editor_property('Codex Slash Train Local Targets')
data = json.loads((Path(unreal.Paths.project_dir()) / 'Tools/NN/Fixtures/SlashTrain2026092223.json').read_text())
assert names == [x['attack'] for x in data['rows']], names
assert len(targets) == 30
maximum = 0.0
for actual, row in zip(targets, data['rows']):
    error = max(abs(a-b) for a,b in zip((actual.x,actual.y,actual.z), row['targetLocalCm']))
    maximum = max(maximum, error)
assert maximum < 1e-8, maximum
assert cdo.get_editor_property('Codex Slash Train Index') == 0
print('SLASH_TRAIN_DATA_VERIFIED', len(names), 'maximum target copy error cm', maximum)
print('Blueprint left unsaved. No Play session started.')
