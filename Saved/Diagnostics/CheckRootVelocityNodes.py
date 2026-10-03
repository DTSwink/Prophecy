import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
for name in ('SetRootVelocity','SetRootAngVelocity'):
    assert unreal.find_object(None,'/Script/GameAnimationSample3.ProphecyRootVelocityLibrary:'+name),name
print('Root velocity setters loaded. PIE:',bool(ed.get_game_world()))
if not ed.get_game_world():
    bp=unreal.load_object(None,'/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent')
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
    report=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
    assert 'status=3 ' in report,report
    print('Pose-agent Blueprint compile passed; no wiring changes or asset saves.')
