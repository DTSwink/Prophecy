import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('PIE_ACTIVE',bool(ed.get_game_world()))
for name in ['Prophecy.SlashReturn.Audit','Prophecy.SlashReturn.Refined']:
 print(name,unreal.SystemLibrary.get_console_variable_int_value(name))
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySlashReturnLibrary'))
assert lib.call_method('SetAttackArmReturnPelvisLocal',(None,*([False]*16))) is False
print('REFERENCE_NODE_REFLECTED_INVALID_AGENT_SAFELY_REJECTED')
