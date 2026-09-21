import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world=ed.get_editor_world()
fn=unreal.find_object(None,'/Script/GameAnimationSample3.ProphecyKickFootLeewayLibrary:SetKickFootJointLeeway')
bridge=unreal.find_object(None,'/Script/ProphecyJolt.ProphecyJoltFootJointLibrary:SetFootExtension')
assert fn and bridge
assert float(unreal.EditorAssetLibrary.get_metadata_tag(fn,'CPP_Default_LeewayCm'))==0.
assert float(unreal.EditorAssetLibrary.get_metadata_tag(fn,'CPP_Default_ReturnDurationSeconds'))==1.
print('KICK_FOOT_LEEWAY_NODE_AND_BRIDGE_PRESENT')
assert not ed.get_game_world(), 'Preserving user Play; run isolated checks after Play ends.'
unreal.SystemLibrary.execute_console_command(world,'Automation RunTests Prophecy.Jolt.Joints.FootExtension+Prophecy.Jolt.RigWorld.FootExtension+Prophecy.Joints.KickFootLeeway')
