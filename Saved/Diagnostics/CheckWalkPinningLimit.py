import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
lib=unreal.get_default_object(unreal.ProphecyWalkPinningLibrary)
assert unreal.find_object(None,'/Script/GameAnimationSample3.ProphecyWalkPinningLibrary:SetWalkPinningLimit')
assert unreal.find_object(None,'/Script/GameAnimationSample3.ProphecyWalkPinningLibrary:GetWalkPinningLimit')
# Check the static reflected API on an editor agent; restore its prior override.
agents=unreal.GameplayStatics.get_all_actors_of_class(ed.get_editor_world(),unreal.ProphecyAgent)
assert agents
a=agents[0];old=lib.call_method('GetWalkPinningLimit',(a,))
try:
    assert lib.call_method('SetWalkPinningLimit',(a,.75))
    assert abs(lib.call_method('GetWalkPinningLimit',(a,))-.75)<1e-6
    assert not lib.call_method('SetWalkPinningLimit',(a,float('nan')))
    assert abs(lib.call_method('GetWalkPinningLimit',(a,))-.75)<1e-6
    assert lib.call_method('SetWalkPinningLimit',(a,2.))
    assert lib.call_method('GetWalkPinningLimit',(a,))==2.
finally:
    assert lib.call_method('SetWalkPinningLimit',(a,old))
print('WALK_PIN_LIMIT_REFLECTION_OK',old)
if not ed.get_game_world():
    bp=unreal.load_object(None,'/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent')
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
    print('Compiled existing Blueprint without rewiring or saving.')
else:print('User Play session preserved; no Blueprint compile.')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.WalkPinning')
