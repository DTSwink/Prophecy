import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.WalkPinning+Prophecy.NN.Presentation+Prophecy.NN.PhysicalTargets.RecoveryCalfLength')
print('KNEE1089_TESTS_QUEUED')
