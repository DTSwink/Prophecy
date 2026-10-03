import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.ClampEase.Transitions+Prophecy.Physics.FootTargetLeeway+Prophecy.NN.UpperBodyInertia')
print('WRIST230_FOCUSED_TESTS_REQUESTED')
