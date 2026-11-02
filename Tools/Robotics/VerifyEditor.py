"""Read-only reflection/Blueprint check in the open editor; no Play or asset saves."""
from pathlib import Path
import json
import unreal

worlds = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if worlds.get_game_world():
    raise RuntimeError('Preserving active Play; editor verification needs stopped Play.')
bp = unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
if not bp or not bp.generated_class():
    raise RuntimeError('Manual-pose agent Blueprint did not load.')
library = unreal.ProphecyLocomotionTypeLibrary
functions = ('set_locomotion_type', 'get_locomotion_type',
             'set_locomotion_switch_upper_blend', 'set_locomotion_switch_lower_blend',
             'set_locomotion_switch_blend')
for name in functions:
    if not callable(getattr(library, name, None)):
        raise RuntimeError(f'Missing reflected node: {name}')
unreal.SystemLibrary.execute_console_command(worlds.get_editor_world(), 'Prophecy.Editor.LiveAgentTypes Inspect')
report = {'map': worlds.get_editor_world().get_path_name(), 'blueprint': bp.get_path_name(),
          'class': bp.generated_class().get_path_name(), 'functions': list(functions),
          'types': [str(unreal.ProphecyLocomotionType.NN), str(unreal.ProphecyLocomotionType.GET_UP),
                    str(unreal.ProphecyLocomotionType.CLANKER)], 'saved_assets': False, 'started_play': False}
folder = Path(unreal.Paths.project_saved_dir())/'Diagnostics/RobotLocomotion20261026'
folder.mkdir(parents=True, exist_ok=True)
(folder/'editor-reflection.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
