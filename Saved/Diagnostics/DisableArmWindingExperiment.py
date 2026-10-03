import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.SlashReturn.ContinuousTwist 0')
print('WINDING_EXPERIMENT_DISABLED',unreal.SystemLibrary.get_console_variable_int_value('Prophecy.SlashReturn.ContinuousTwist'))
print('PIE_ACTIVE',bool(ed.get_game_world()))
