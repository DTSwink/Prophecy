import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user Play'
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyAttackWristLibrary'))
assert lib.call_method('SetLeftHandConstraintGlobalEnabled',(None,False))==False
assert lib.call_method('SetLeftHandConstraintAttacks',(None,*([True]*16)))==False
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LeftHandAngle')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.AttackWrist')
print('LEFT_HAND_ANGLE_INSTALLED_FOCUSED_TESTS_REQUESTED')
