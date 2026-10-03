import unreal
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world,'prophecy.Physical.LogPelvisError 0')
unreal.SystemLibrary.execute_console_command(world,'prophecy.Physical.LogTrackingError 0')
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
