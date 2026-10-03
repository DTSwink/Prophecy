import unreal


level_editor = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if level_editor.is_in_play_in_editor():
    raise RuntimeError("PIE is already running; refusing to replace the active session")

editor_world = unreal.get_editor_subsystem(
    unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(
    editor_world, "prophecy.Physical.AuditManualFollower 1")
level_editor.editor_request_begin_play()
print("MANUAL_FOLLOW_AUDIT_PIE_REQUESTED")
