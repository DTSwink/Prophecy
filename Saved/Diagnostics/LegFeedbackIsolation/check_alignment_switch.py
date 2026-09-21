import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('PIE',bool(ed.get_game_world()))
print('FEEDBACK_ALIGNMENT',unreal.SystemLibrary.get_console_variable_int_value('Prophecy.NNLowerFeedbackAlignment'))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.NNLowerFeedbackAlignment')
