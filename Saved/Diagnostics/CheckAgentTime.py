import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
for name in ('SetAgentTimeDilation','GetAgentTimeDilation'):
    assert unreal.find_object(None,'/Script/GameAnimationSample3.ProphecyAgentTimeLibrary:'+name),name
print('Agent time nodes loaded; current Play:',bool(ed.get_game_world()))
if not ed.get_game_world():
    bp=unreal.load_object(None,'/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent')
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
    report=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
    assert 'status=3 ' in report,report
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),
        'Automation RunTests Prophecy.Agent.TimeDilation+Prophecy.Blends.SixtyTickClock+Prophecy.NN.Presentation.FrameCadence')
    print('Blueprint compiled without save; requested focused time and existing blend/presentation tests.')
