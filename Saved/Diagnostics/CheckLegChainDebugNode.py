import unreal
node=unreal.find_object(None,'/Script/GameAnimationSample3.ProphecyLegChainDebugLibrary:SetLegChainReconstruction')
assert node,'Leg-chain debug node not loaded'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('Set Leg Chain Reconstruction is reflected and loaded.')
if not ed.get_game_world():
    bp=unreal.load_object(None,'/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent')
    assert bp
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
    print('Compiled existing pose-agent Blueprint without changing wiring or saving assets.')
else:
    print('Active user Play session preserved; Blueprint compilation deferred.')
