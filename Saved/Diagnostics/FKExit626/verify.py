import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('FK_EXIT_CHECKS_USER_PLAY_PRESERVED',bool(ed.get_game_world()))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.FKReturn+Prophecy.Blends.SixtyTickClock')
