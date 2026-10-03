import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Preserve active user Play'
w=ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Automation RunTests Prophecy.Joints.KickFootLeeway+Prophecy.NN.PhysicalTargets.RecoveryCalfLength+Prophecy.NN.PhysicalTargets.AttackLegClamps+Prophecy.NN.PolicyBlend.RecoveryFootRotation+Prophecy.Blends.SixtyTickClock')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.LiveAgentTypes Inspect')
print('KICK_LENGTH_RECOVERY_TESTS_QUEUED')
