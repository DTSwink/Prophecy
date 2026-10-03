import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.Physics.FootTargetLeeway+Prophecy.PhysicalProfiles.ClampSnapshots+Prophecy.NN.PhysicalTargets.RecoveryCalfLength+Prophecy.Joints.KickFootLeeway+Prophecy.Jolt.Joints.FootExtension+Prophecy.Jolt.RigWorld.FootExtension')
print('SHARED_LOCOMOTION_FOOT_TESTS_QUEUED')
