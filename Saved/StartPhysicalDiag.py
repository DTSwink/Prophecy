import unreal
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world,'prophecy.Physical.LogPelvisError 1')
unreal.SystemLibrary.execute_console_command(world,'prophecy.Physical.LogTrackingError 1')
unreal.SystemLibrary.execute_console_command(world,'t.MaxFPS 60')
sub=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
sub.editor_request_begin_play()
print('STARTED_DIAG')
