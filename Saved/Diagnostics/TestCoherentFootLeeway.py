import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve active Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.Physics.FootTargetLeeway+Prophecy.Joints.KickFootLeeway+Prophecy.Joints.CalfReturnLocomotionTarget+Prophecy.Jolt.RigWorld.FootExtension')
