import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play session'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.SlashReturn+Prophecy.NN.HandRecovery+Prophecy.NN.CoreTempering')
print('JAB_PIKE_RETURN_TESTS_QUEUED')
