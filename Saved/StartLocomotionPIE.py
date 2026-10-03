import unreal

subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not subsystem.is_in_play_in_editor():
    subsystem.editor_request_begin_play()
print("PIE_REQUESTED")
