import unreal
e=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
unreal.SystemLibrary.execute_console_command(e.get_editor_world(),'Automation RunTests Prophecy.NN.PelvisInertia')
