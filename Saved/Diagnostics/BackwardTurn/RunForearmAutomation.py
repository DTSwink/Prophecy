import unreal
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
assert hasattr(unreal.ProphecyAgent,'set_locomotion_forearm_clamp')
unreal.SystemLibrary.execute_console_command(w,'Automation RunTests Prophecy.NN.PhysicalTargets.LocomotionForearmClamp')
