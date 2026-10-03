import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyWalkPinningLibrary'))
assert lib.call_method('SetWalkPinningReachGuard',args=(None,False,6)) is False
print('REACH_GUARD_REFLECTED',lib.get_path_name())
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.RepairLibraryDefaults')
print('POSE_BLUEPRINT_COMPILE_REQUESTED')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.WalkPinning+Prophecy.NN.LowerTempering+Prophecy.NN.PelvisInertia+Prophecy.NN.PolicyBlend+Prophecy.NN.PhysicalTargets.RecoveryCalfLength+Prophecy.Joints.KickFootLeeway+Prophecy.NN.AgentReset.MotionAndWindow')
print('WALK_PIN_REACH_TESTS_QUEUED')
