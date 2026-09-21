import unreal
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(w, 'Automation RunTests Prophecy.NN.Presentation')
print('Requested both Prophecy.NN.Presentation regression tests')
