import unreal
sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if not sub.get_game_world():
    print('STARTING_CURRENT_SCENE=' + sub.get_editor_world().get_path_name())
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
