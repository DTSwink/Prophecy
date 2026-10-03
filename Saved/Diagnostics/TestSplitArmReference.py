import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),
 'Automation RunTests Prophecy.NN.SlashReturn.PelvisReference+Prophecy.NN.SlashReturn.BothArms+Prophecy.NN.SlashReturn.ReachableIdleAndPath+Prophecy.NN.SlashReturn.RouteAndLifecycle+Prophecy.NN.SlashReturn.UnarmedRotation+Prophecy.NN.HandRecovery+Prophecy.NN.CoreTempering')
print('SPLIT_REFERENCE_TESTS_QUEUED')
