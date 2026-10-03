import unreal,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
w=ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Tempering.ConnectedSources '+(sys.argv[1] if len(sys.argv)>1 else '3'))
unreal.SystemLibrary.execute_console_command(w,'Automation RunTests Prophecy.NN.LowerTempering+Prophecy.NN.PelvisInertia+Prophecy.NN.PolicyBlend+Prophecy.NN.PhysicalTargets.RecoveryCalfLength+Prophecy.Joints.KickFootLeeway')
print('RECOVERY_KNEE_TESTS_QUEUED')
