import json
import pathlib
import unreal
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world()
cdo = unreal.get_default_object(unreal.ProphecyAgent)
result = dict(foot_node=hasattr(cdo, 'set_attack_foot_clamp'),
              calf_node=hasattr(cdo, 'set_attack_calf_clamp'),
              pin_default=cdo.get_editor_property('attack_foot_pinning_iterations'))
assert result['foot_node'] and result['calf_node'] and result['pin_default'] == 4
print(json.dumps(result))
(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SlashContacts/AttackLeewayControls.json').write_text(json.dumps(result))
unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'Automation RunTests Prophecy.NN.PhysicalTargets.AttackLegClamps')
