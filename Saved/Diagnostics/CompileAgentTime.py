import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('Agent time dilation: request Live Coding; preserve editor assets and current Play:',bool(ed.get_game_world()))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'LiveCoding.Compile')
