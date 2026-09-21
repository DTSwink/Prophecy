import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world=ed.get_editor_world()
fn=unreal.find_object(None,'/Script/GameAnimationSample3.ProphecyAttackControlLibrary:SetAttackCameraOffsetFadeDuration')
assert fn
if not ed.get_game_world():
    assert float(unreal.EditorAssetLibrary.get_metadata_tag(fn,'CPP_Default_DurationSeconds'))==1.0
print('ATTACK_CAMERA_FADE_NODE_PRESENT')
unreal.SystemLibrary.execute_console_command(world,'Automation RunTests Prophecy.Camera.AttackOffsetFade')
