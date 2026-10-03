import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.LowerTempering.IndependentRecoveryClock+Prophecy.NN.LowerTempering.FootFramePoleSmoothing+Prophecy.NN.LowerTempering.CleanRecoverySource+Prophecy.NN.LowerTempering.HeightDirection+Prophecy.NN.LowerTempering.SupportSourceContracts+Prophecy.NN.PelvisInertia.LegChain+Prophecy.NN.PhysicalTargets.RecoveryCalfLength+Prophecy.Joints.CalfReturnLocomotionTarget+Prophecy.Joints.KickFootLeeway+Prophecy.Blends.SixtyTickClock')
