import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
w=ed.get_editor_world()
cls=unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyAttackStartInertiaLibrary')
assert cls
lib=unreal.get_default_object(cls)
a=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)[0]
print('ATTACK_START_NODE_DISABLE_CALL',lib.call_method('SetAttackStartPelvisInertia',args=(a,False,5,1.0,5,1.0)))
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RepairLibraryDefaults')
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
print('ATTACK_START_BP_COMPILE_REQUESTED')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.SystemLibrary.execute_console_command(w,'Automation RunTests Prophecy.NN.PhysicalTargets.RecoveryCalfLength+Prophecy.NN.PelvisInertia+Prophecy.NN.Presentation')
print('ATTACK_START_TESTS_QUEUED')
