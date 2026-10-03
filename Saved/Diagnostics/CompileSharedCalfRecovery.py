import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('USER_PIE_ACTIVE',bool(ed.get_game_world()))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'LiveCoding.Compile')
print('SHARED_CALF_RECOVERY_BUILD_REQUESTED')
