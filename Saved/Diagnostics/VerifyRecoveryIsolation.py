import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Recovery.PolePresentation 1')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.LowerTempering+Prophecy.NN.PhysicalTargets.RecoveryCalfLength+Prophecy.Joints.CalfReturnLocomotionTarget+Prophecy.Joints.KickFootLeeway+Prophecy.Blends.SixtyTickClock+Prophecy.NN.PhysicalFeedback.LowerTargetAlignment+Prophecy.NN.WalkPinning')
