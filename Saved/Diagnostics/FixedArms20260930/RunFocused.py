import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), 'Automation RunTests Prophecy.NN.PhysicalTargets.FixedForearms+Prophecy.NN.PhysicalTargets.InterpolationAndRigidForearms+Prophecy.NN.UpperBodyInertia+Prophecy.NN.HandRecovery.ChainContinuity+Prophecy.NN.HandRecovery.BendBlend+Prophecy.NN.AttackEntry.HandLifecycle+Prophecy.PhysicalProfiles.ClampSnapshots')
print('FIXED_ARMS_FOCUSED_TESTS_REQUESTED')
