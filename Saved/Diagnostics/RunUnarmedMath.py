import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('PRESERVING_USER_PLAY',bool(ed.get_game_world()))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.SlashReturn.UnarmedRotation')
