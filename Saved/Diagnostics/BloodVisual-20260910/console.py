import unreal,sys
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() or unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
for command in sys.argv[1:]:
 unreal.SystemLibrary.execute_console_command(w,command)
 print('EXECUTED',command)
