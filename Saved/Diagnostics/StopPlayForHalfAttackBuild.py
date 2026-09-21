import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if ed.get_game_world():
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('Requested user-authorized end of Play; editor and assets remain open.')
else:
    print('Play already stopped.')
