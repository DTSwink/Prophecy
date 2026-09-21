import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserving active Play'
print('SUPPORT_SOURCE_ENABLED',unreal.SystemLibrary.get_console_variable_int_value('Prophecy.Tempering.SupportSource'))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.LowerTempering+Prophecy.NN.PelvisInertia.LegChain+Prophecy.NN.PolicyBlend.RegionalPose')
print('Requested focused support-source, tempering, and chain checks; no asset save/restart.')
