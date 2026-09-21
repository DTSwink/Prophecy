import unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('PHAT_SWEEP_USER_PIE_PRESERVED', bool(ed.get_game_world()))
cls = unreal.load_class(None, '/Script/ProphecyJolt.ProphecyJoltPHATSweepLibrary')
assert cls
lib = unreal.get_default_object(cls)
print('PHAT_SWEEP_DEFAULTS', lib.call_method('GetJoltPHATSweeps', (None,)))
assert lib.call_method('SetJoltPHATSweeps', (None, True, 1.0, 64)) is False
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), 'Automation RunTests Prophecy.Jolt.ContactShapes.SelectiveSweeps')
