import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
world=ed.get_editor_world()
saved=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics')
for command in ['Prophecy.Editor.RefreshRecoveryPinOrder','Prophecy.Editor.RepairLibraryDefaults']:
    unreal.SystemLibrary.execute_console_command(world,command)
for name,expected in [('RecoveryPinOrder.txt','values_and_links_preserved=1'),('LiveLibraryDefaults.txt','other_values_and_wiring_preserved=1')]:
    raw=(saved/name).read_bytes()
    report=raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig')
    print(name,report)
    assert expected in report and 'status=3 ' in report,report
for cls,fn in [('ProphecyAttackRecoveryLibrary','SetKickToLocomotionBlend'),('ProphecyLowerTemperingLibrary','SetKickLocomotionLowerBodyTempering')]:
    function=unreal.find_object(None,'/Script/GameAnimationSample3.'+cls+':'+fn)
    assert function,fn
    print('NODE',function.get_path_name())
bp=unreal.load_object(None,'/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent')
unreal.BlueprintEditorLibrary.refresh_open_editors_for_blueprint(bp)
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=True),'Could not save refreshed recovery nodes'
print('POSE_BP_SAVED after verified pin refresh; unrelated assets untouched')
unreal.SystemLibrary.execute_console_command(world,'Automation RunTests Prophecy.NN.PolicyBlend.AttackRecovery+Prophecy.NN.LowerTempering.KickProfiles+Prophecy.NN.LowerTempering.ReturnTimeline+Prophecy.NN.LowerTempering.SeparateReturns+Prophecy.Blends.SixtyTickClock+Prophecy.Jolt.Sword.AttackCollisionPhases')
