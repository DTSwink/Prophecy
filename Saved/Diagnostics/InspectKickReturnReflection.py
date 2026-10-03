import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('PLAY',bool(ed.get_game_world()))
print('KICK_METHOD',hasattr(unreal.ProphecyLowerTemperingLibrary,'blend_kick_locomotion_lower_body_tempering_to_normal'))
print('LIBRARY',unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyLowerTemperingLibrary'))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'DumpConsoleCommands Prophecy.SeparateKickTemperingReturns')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.SeparateKickTemperingReturns')
