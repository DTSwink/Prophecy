import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('PIE',bool(ed.get_game_world()))
c=unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyAttackWristLibrary')
api=unreal.get_default_object(c)
print('NODE',api.call_method('SetLeftHandConstraint',(None,False,unreal.ProphecyClampProfileMode.ALL,55.)))
