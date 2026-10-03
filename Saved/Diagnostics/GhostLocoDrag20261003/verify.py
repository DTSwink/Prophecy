"""Check cold-loaded reflection and compile the existing BP without saving assets."""
import json
from pathlib import Path
import unreal

root = Path(unreal.Paths.project_dir()).resolve()
directory = root / 'Saved/Diagnostics/GhostLocoDrag20261003'
checks = [
    ('ProphecyAttackFootLocomotionLibrary', 'set_ghost_loco_drag', []),
    ('ProphecyAttackFootLocomotionLibrary', 'draw_ghost_loco_drag', []),
    ('ProphecyAttackFootLocomotionLibrary', 'read_ghost_loco_drag', []),
    ('ProphecyFKReturnLibrary', 'set_attack_fk_return', ['alpha_hold']),
    ('ProphecyAttackEndExtensionLibrary', 'set_attack_end_extension', []),
    ('ProphecyUpperCheckpointLibrary', 'set_upper_checkpoint', []),
    ('ProphecyUpperBodyInertiaLibrary', 'set_attack_upper_body_inertia', ['arms_alpha']),
    ('ProphecySlashReturnLibrary', 'set_slash_right_arm_return_to_neutral',
     ['left_hold_duration_seconds', 'left_blend_to_nn_duration_seconds', 'left_alpha']),
]
signatures = {}
for class_name, method_name, parameters in checks:
    method = getattr(getattr(unreal, class_name), method_name)
    documentation = method.__doc__ or ''
    for parameter in parameters:
        assert parameter in documentation, (class_name, method_name, parameter)
    signatures[class_name + '.' + method_name] = documentation.splitlines()[0]

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert '/Game/testNN' in editor.get_editor_world().get_path_name()
assert editor.get_game_world() is None, 'Do not compile during user Play'
bp = unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
assert bp is not None
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'Prophecy.Editor.LiveAgentTypes Inspect')
inspection = (root / 'Saved/Diagnostics/LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
assert 'status=3' in inspection and 'native_properties=0 pin_types=0' in inspection, inspection
report = {'passed': True, 'world': editor.get_editor_world().get_path_name(),
          'signatures': signatures, 'blueprint_inspection': inspection, 'assets_saved': False}
(directory / 'editor-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('COLD_LAUNCH_VERIFIED ' + json.dumps(report))
