import unreal
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
print('INTERPOLATION_ENUM', list(unreal.ProphecyNNInterpolationMode))
unreal.SystemLibrary.execute_console_command(world, 'Automation RunTests Prophecy.NN.Interpolation')
