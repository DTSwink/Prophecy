import unreal
e=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
c=unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyHandInertiaLibrary')
assert c,'Hand inertia Blueprint library must be loaded'
print('Hand inertia library loaded:',c.get_path_name())
unreal.SystemLibrary.execute_console_command(e.get_editor_world(),'Automation RunTests Prophecy.NN.HandInertia.ControlsAndIK')
