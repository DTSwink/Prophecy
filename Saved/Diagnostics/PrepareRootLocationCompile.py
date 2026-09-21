import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if ed.get_game_world():unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'t.MaxFPS 10')
