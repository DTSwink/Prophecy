import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
w=ed.get_editor_world()
for c in ('Prophecy.Tempering.KneePlane 3','Prophecy.Recovery.CleanSource 1','Prophecy.Recovery.KneeReference 0','Prophecy.Tempering.HistoricalAudit 0'):
 unreal.SystemLibrary.execute_console_command(w,c)
unreal.SystemLibrary.execute_console_command(w,'Automation RunTests Prophecy.NN.LowerTempering+Prophecy.NN.PelvisInertia+Prophecy.NN.PolicyBlend+Prophecy.NN.PhysicalTargets.RecoveryCalfLength+Prophecy.Joints.KickFootLeeway+Prophecy.NN.Presentation+Prophecy.NN.WalkPinning')
print('HISTORICAL_KNEE_FINAL_TESTS_QUEUED')
