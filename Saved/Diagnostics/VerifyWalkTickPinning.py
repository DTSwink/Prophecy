import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve Play'
w=ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Automation RunTests Prophecy.NN.WalkPinning+Prophecy.NN.Presentation')
print('TICK_PINNING_TESTS_QUEUED')
