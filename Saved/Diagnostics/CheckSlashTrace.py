import unreal
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Prophecy.SlashReturn.Audit 1')
unreal.SystemLibrary.execute_console_command(w,'Automation RunTests Prophecy.NN.SlashReturn.RouteAndLifecycle')
print('TRACE_CHECK',unreal.SystemLibrary.get_console_variable_int_value('Prophecy.SlashReturn.Audit'))
