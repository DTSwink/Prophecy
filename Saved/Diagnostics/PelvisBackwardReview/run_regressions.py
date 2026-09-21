import unreal

editor = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if editor.is_in_play_in_editor():
    editor.editor_request_end_play()
print('Ending diagnostic PIE before isolated regression tests')
