import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if not ed.get_game_world(): unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
