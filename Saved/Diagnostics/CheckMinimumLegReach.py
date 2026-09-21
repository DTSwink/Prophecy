import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('PLAY_ACTIVE',bool(ed.get_game_world()))
fn=unreal.find_object(None,'/Script/GameAnimationSample3.ProphecyLegChainDebugLibrary:SetLocomotionMinimumLegReach')
assert fn,'Missing reflected minimum reach node'
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyLegChainDebugLibrary'))
assert lib.call_method('SetLocomotionMinimumLegReach',args=(None,1.2)) is False
print('MINIMUM_REACH_NODE',fn.get_path_name(),'callable, rejects null agent')
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
print('BLUEPRINT',bp.get_path_name())
if not ed.get_game_world():
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    print('BLUEPRINT_COMPILE_REQUESTED')
else:
    print('PRESERVING_USER_PLAY_NO_AUTOMATION')
