import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'LiveCoding.Compile')
print('Requested clamp profile Live Coding; preserving the current editor/Play session.')
