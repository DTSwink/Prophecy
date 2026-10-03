import unreal,builtins,gc
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
s=getattr(builtins,'_attack_startup',None)
if s:s['actors']=None;s['rows']=[]
gc.collect()
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
assert bp,'Recovered Blueprint missing'
print('RECOVERED_BLUEPRINT',bp.get_path_name())
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.RepairLibraryDefaults')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.Editor.AttackCache.Fingerprint+Prophecy.NN.WalkPinning+Prophecy.NN.LowerTempering+Prophecy.NN.PelvisInertia+Prophecy.NN.PolicyBlend+Prophecy.NN.PhysicalTargets.RecoveryCalfLength+Prophecy.Joints.KickFootLeeway+Prophecy.NN.AgentReset.MotionAndWindow')
print('CACHE_TEST_QUEUED')
