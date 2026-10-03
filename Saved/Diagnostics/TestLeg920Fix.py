import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.KneeSmoothing.SpecialOrder 1')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.PhysicalTargets.KneePopSmoothing+Prophecy.NN.PhysicalTargets.RecoveryCalfLength+Prophecy.NN.Presentation+Prophecy.NN.WalkPinning')
print('LEG920_TESTS_QUEUED')
