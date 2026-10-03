import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
print('LengthInterpolation',unreal.SystemLibrary.get_console_variable_int_value('Prophecy.Recovery.LengthInterpolation'))
print('PoleTrace',unreal.SystemLibrary.get_console_variable_int_value('Prophecy.Tempering.PoleTrace'))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.Physics.FootTargetLeeway+Prophecy.NN.PhysicalTargets.RecoveryCalfLength+Prophecy.NN.Presentation')
