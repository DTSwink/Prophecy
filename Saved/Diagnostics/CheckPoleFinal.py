import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('PIE',bool(ed.get_game_world()))
for n in ('Prophecy.Tempering.PoleSmoothing','Prophecy.Tempering.PoleTrace'):
 print(n,unreal.SystemLibrary.get_console_variable_int_value(n))
