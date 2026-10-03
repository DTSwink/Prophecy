import unreal,pathlib,shutil
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
world=ed.get_editor_world()
saved=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics')
asset=pathlib.Path(unreal.Paths.project_content_dir(),'_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset')
shutil.copy2(asset,saved/'KickRoles-BeforeRefresh.uasset')
for command in ['Prophecy.Editor.RefreshKickRoles','Prophecy.Editor.RepairLibraryDefaults']:
    unreal.SystemLibrary.execute_console_command(world,command)
for name,expected in [('KickRecoveryRoles.txt','values_and_links_preserved=1'),('KickTemperingRoles.txt','values_and_links_preserved=1'),('LiveLibraryDefaults.txt','other_values_and_wiring_preserved=1')]:
    raw=(saved/name).read_bytes()
    report=raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig')
    print(name,report)
    assert expected in report and 'status=3 ' in report,report
bp=unreal.load_object(None,'/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent')
unreal.BlueprintEditorLibrary.refresh_open_editors_for_blueprint(bp)
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=True),'Could not save refreshed role nodes'
unreal.SystemLibrary.execute_console_command(world,'Prophecy.Sword.AuditCollisionGraph')
print('POSE_BP_SAVED after verified role refresh; unrelated assets untouched')
tests=['Prophecy.NN.PolicyBlend.AttackRecovery','Prophecy.NN.PolicyBlend.RegionalPose','Prophecy.NN.LowerTempering.FootRoles','Prophecy.NN.LowerTempering.TranslationAxes','Prophecy.NN.LowerTempering.KickProfiles','Prophecy.NN.LowerTempering.ReturnTimeline','Prophecy.NN.LowerTempering.SeparateReturns','Prophecy.NN.LowerTempering.SupportSourceContracts','Prophecy.NN.LowerTempering.CalfTwistContinuity','Prophecy.NN.AgentReset.PhysicalBaseline','Prophecy.Blends.SixtyTickClock']
unreal.SystemLibrary.execute_console_command(world,'Automation RunTests '+'+'.join(tests))
