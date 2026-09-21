import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world=ed.get_editor_world()
fn=unreal.find_object(None,'/Script/GameAnimationSample3.ProphecyRootPhysicsLibrary:SetKickSelfBalancingExceptionDurations')
assert fn
if not ed.get_game_world():
    assert float(unreal.EditorAssetLibrary.get_metadata_tag(fn,'CPP_Default_HoldDurationSeconds'))==0.
    assert float(unreal.EditorAssetLibrary.get_metadata_tag(fn,'CPP_Default_FadeDurationSeconds'))==1.
print('KICK_BALANCE_EXCEPTION_NODE_PRESENT')
unreal.SystemLibrary.execute_console_command(world,'Automation RunTests Prophecy.Root.KickSelfBalancingException+Prophecy.Blends.SixtyTickClock')
