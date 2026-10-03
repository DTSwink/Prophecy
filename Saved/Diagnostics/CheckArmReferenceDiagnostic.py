import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('LEGACY_SPINE_REFERENCE',unreal.SystemLibrary.get_console_variable_int_value('Prophecy.SlashReturn.LegacySpineReference'))
print('PIE_ACTIVE',bool(ed.get_game_world()))
