import unreal


game_world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem).get_game_world()
if game_world:
    unreal.SystemLibrary.execute_console_command(game_world, "Input.-Key Z")
    unreal.SystemLibrary.execute_console_command(game_world, "Input.-Key LeftShift")
level_editor = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if level_editor.is_in_play_in_editor():
    level_editor.editor_request_end_play()
editor_world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(
    editor_world, "prophecy.Physical.AuditManualFollower 0")
print("MANUAL_FOLLOW_AUDIT_PIE_STOP_REQUESTED")
