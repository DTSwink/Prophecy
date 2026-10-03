import unreal

subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if subsystem.is_in_play_in_editor():
    subsystem.editor_request_end_play()
print("PIE_STOP_REQUESTED")
