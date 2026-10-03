import unreal
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
unreal.SystemLibrary.execute_console_command(world,'prophecy.Physical.LogPelvisError 1')
unreal.SystemLibrary.execute_console_command(world,'prophecy.Physical.LogTrackingError 1')
print('DIAG_ON')
