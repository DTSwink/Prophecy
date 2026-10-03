import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if ed.get_game_world():
 print('SHOW_FOOT_FIX_ALREADY_PLAYING')
else:
 unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
 print('SHOW_FOOT_FIX_PLAY_REQUESTED')
