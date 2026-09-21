import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve active Play session.'
paths=['/Script/GameAnimationSample3.ProphecyWalkPinningLibrary:SetWalkPinningLimit',
       '/Script/GameAnimationSample3.ProphecyPhysicalFootTargetLibrary:SetPhysicalFootTargetClampLeeway',
       '/Script/GameAnimationSample3.PhysicsHitVelocityLibrary:GetHitTrajectory']
for path in paths:
    assert unreal.find_object(None,path),path
    print('REOPEN_FUNCTION_OK',path)
trajectory=unreal.find_object(None,paths[-1])
assert unreal.EditorAssetLibrary.get_metadata_tag(trajectory,'DisplayName')=='Get Launch Trajectory'
bp=unreal.load_object(None,'/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent')
assert bp
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).open_editor_for_assets([bp])
print('REOPEN_BLUEPRINT_COMPILE_REQUESTED_NO_SAVE')
