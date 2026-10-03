import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Do not run automation over active Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.LowerTempering.HeightDirection+Prophecy.NN.LowerTempering.SupportSourceContracts+Prophecy.NN.PelvisInertia.LegChain')
