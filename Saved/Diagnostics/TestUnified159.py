import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
w=ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Tempering.KneePlane 3')
unreal.SystemLibrary.execute_console_command(w,'Automation RunTests Prophecy.NN.LowerTempering+Prophecy.NN.PelvisInertia+Prophecy.NN.PolicyBlend+Prophecy.NN.PhysicalTargets.RecoveryCalfLength+Prophecy.Joints.KickFootLeeway')
print('UNIFIED_LEG_TESTS_QUEUED')
