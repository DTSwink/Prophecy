import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Recovery.UpperLengthBlend 1')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.PhysicalTargets.RecoveryUpperHandoff+Prophecy.NN.PhysicalTargets.RecoveryCalfLength+Prophecy.NN.Presentation.FrameCadence+Prophecy.NN.Presentation.SharedReadersAndLifecycle+Prophecy.Joints.CalfReturnLocomotionTarget+Prophecy.Joints.KickFootLeeway+Prophecy.Blends.SixtyTickClock')
print('KNEE202_REGRESSIONS_QUEUED')
