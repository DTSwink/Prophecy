import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('PIE_ACTIVE',bool(ed.get_game_world()))
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySlashReturnLibrary'))
assert unreal.find_object(None,'/Script/GameAnimationSample3.ProphecySlashReturnLibrary:SetAttackArmReturnRotationBlend')
assert lib.call_method('SetAttackArmReturnRotationBlend',(None,0.,1.)) is False
for key in ['Prophecy.SlashReturn.Audit','Prophecy.SlashReturn.BodyRoute','Prophecy.SlashReturn.Refined','Prophecy.SlashReturn.UnarmedShortestRotation']:
 print(key,unreal.SystemLibrary.get_console_variable_int_value(key))
print('ROTATION_BLEND_NODE_REFLECTED_AND_CALLABLE')
