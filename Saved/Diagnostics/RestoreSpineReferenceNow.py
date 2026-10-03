import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.SlashReturn.LegacySpineReference 1')
print('ORIGINAL_SPINE_REFERENCE_ENABLED',unreal.SystemLibrary.get_console_variable_int_value('Prophecy.SlashReturn.LegacySpineReference'))
print('PIE_ACTIVE',bool(ed.get_game_world()))
