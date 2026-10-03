import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('PIE_ACTIVE',bool(ed.get_game_world()))
for name in ('Prophecy.Recovery.UpperLengthBlend','Prophecy.NNInputTraceFrames','Prophecy.SlashReturn.Audit'):
 print(name,unreal.SystemLibrary.get_console_variable_int_value(name))
