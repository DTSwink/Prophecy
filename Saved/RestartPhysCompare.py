import unreal
sub=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if sub.is_in_play_in_editor(): sub.editor_request_end_play()
