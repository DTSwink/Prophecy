import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
# User explicitly requested compilation during their current PIE. No reflected
# layout changes or retained snapshot resizing are part of this patch.
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'LiveCoding.Compile')
print('Requested sword-reset Live Coding; preserving the user Play session.')
