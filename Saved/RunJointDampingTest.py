import unreal
e=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyJointDampingLibrary')
unreal.SystemLibrary.execute_console_command(e.get_editor_world(),'Automation RunTests Prophecy.Jolt.Joints.AngularDamping')
print('Joint damping Blueprint library loaded; requested one native test')
