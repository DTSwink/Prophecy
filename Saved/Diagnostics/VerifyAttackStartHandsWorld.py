import pathlib
import unreal

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
playing = bool(editor.get_game_world())
print('ENTRY_WORLD_PIE_ACTIVE', playing)
library = unreal.get_default_object(unreal.load_class(None, '/Script/GameAnimationSample3.ProphecyAttackStartInertiaLibrary'))
assert library.call_method('SetAttackStartHandInertia', (None, False, .1, .3, 0., .25, 1., 1., True, True)) is False
if not playing:
    unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'Prophecy.Editor.RepairLibraryDefaults')
    data = (pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics/LiveLibraryDefaults.txt').read_bytes()
    report = data.decode('utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
    print('ENTRY_WORLD_BLUEPRINT', report)
    assert 'status=3' in report or 'status=5' in report, report
    assert 'other_values_and_wiring_preserved=1' in report, report
    unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'Prophecy.Editor.LiveAgentTypes Inspect')
else:
    print('ENTRY_WORLD_BLUEPRINT_COMPILE_DEFERRED_PRESERVE_USER_PLAY')
unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'Automation RunTests Prophecy.NN.AttackEntry.Hand')
print('ENTRY_WORLD_FOCUSED_TESTS_REQUESTED')
