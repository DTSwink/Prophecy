import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('FOREARM_PARENT_BUILD; user Play preserved:',bool(ed.get_game_world()))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'LiveCoding.Compile')
