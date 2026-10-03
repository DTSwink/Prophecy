import unreal
unreal.load_module('GameAnimationSample3')
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyAttackFootLocomotionLibrary'))
assert api.call_method('GetAttackFootLocomotion',(None,))==(False,False)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.AttackEntry.FootLocomotion+Prophecy.NN.AttackEntry.FootInertia+Prophecy.NN.AttackEntry.PelvisRegression')
print('FOOT_AUTHORING_NODES_REFLECTED')
