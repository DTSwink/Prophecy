import unreal
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world=editor.get_game_world() or editor.get_editor_world()
print('PIE',bool(editor.get_game_world()))
unreal.SystemLibrary.execute_console_command(world,'Trace.Status')
