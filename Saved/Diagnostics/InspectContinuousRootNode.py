import unreal
print('CONTINUOUS_ROOT_NODE', unreal.ProphecyRootPhysicsLibrary.get_continuous_locomotion_root_window.__doc__)
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), 'Automation RunTests Prophecy.NN.RootWindow.Continuous')
