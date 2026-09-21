import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.NNLowerFeedbackAlignment 1')
v=unreal.SystemLibrary.get_console_variable_int_value('Prophecy.NNLowerFeedbackAlignment')
print('FEEDBACK_ALIGNMENT',v)
print('PIE_ACTIVE',bool(ed.get_game_world()))
assert v==1,'Corrected feedback was not restored'
