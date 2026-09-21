import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve current Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.LowerTempering.RootLocalPinAndChain+Prophecy.NN.PelvisInertia.LegChain')
print('Requested the two focused leg reconstruction tests.')
