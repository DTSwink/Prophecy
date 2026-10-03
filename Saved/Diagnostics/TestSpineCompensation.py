import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyGhostAttackLibrary'))
assert not lib.call_method('EnableSpine01CompensationHalfAttack',args=(None,False,False))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.HalfAttack.SpineCompensation+Prophecy.NN.HalfAttack.PelvisMount')
print('SPINE_NODE_REFLECTED_AND_CALLABLE')
