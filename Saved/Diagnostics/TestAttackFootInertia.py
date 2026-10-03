import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
api=unreal.get_default_object(unreal.ProphecyAttackStartInertiaLibrary)
assert api.call_method('SetAttackStartFootInertia',(None,False,5,1.,5,1.)) is False
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.AttackEntry.FootInertia+Prophecy.NN.AttackEntry.PelvisRegression')
print('FOOT_INERTIA_NODE_REFLECTED')
