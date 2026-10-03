import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('FINAL_USER_WORLD',bool(ed.get_game_world()))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.WalkPinning.PreserveHinge')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.NNInputTraceFrames')
