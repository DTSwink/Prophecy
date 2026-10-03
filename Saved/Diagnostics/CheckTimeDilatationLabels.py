import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assets=unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
for verb in ('Set','Get'):
    fn=unreal.find_object(None,'/Script/GameAnimationSample3.ProphecyAgentTimeLibrary:'+verb+'AgentTimeDilation')
    assert fn
    label=assets.get_metadata_tag(fn,'DisplayName')
    print(verb,label)
    assert label==verb+' Agent Time Dilatation',label
assert not ed.get_game_world(),'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.RepairLibraryDefaults')
report=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/LiveLibraryDefaults.txt').read_text(encoding='utf-8-sig')
print(report)
assert 'status=3 ' in report and 'other_values_and_wiring_preserved=1' in report,report
bp=unreal.load_object(None,'/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent')
unreal.BlueprintEditorLibrary.refresh_open_editors_for_blueprint(bp)
