import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.SlashReturn.NNHinge 0')
print('PREVIOUS_ARM_GUIDANCE_RESTORED',unreal.SystemLibrary.get_console_variable_int_value('Prophecy.SlashReturn.NNHinge'))
print('PIE_ACTIVE',bool(ed.get_game_world()))
