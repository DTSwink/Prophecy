import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
library=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyAttackWristLibrary'))
assert library.call_method('SetNNWristFreedom',(None,True,True))==False
assert not ed.get_game_world(), 'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.AttackWrist+Prophecy.NN.PhysicalTargets.FixedForearms')
print('NN_WRIST_FREEDOM_AVAILABLE_AND_TESTS_REQUESTED')
