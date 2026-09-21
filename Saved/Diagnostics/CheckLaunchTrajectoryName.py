import unreal
function=unreal.find_object(None,'/Script/GameAnimationSample3.PhysicsHitVelocityLibrary:GetHitTrajectory')
assert function
name=unreal.EditorAssetLibrary.get_metadata_tag(function,'DisplayName')
assert name=='Get Launch Trajectory',repr(name)
print('LAUNCH_TRAJECTORY_NAME_OK',name)
