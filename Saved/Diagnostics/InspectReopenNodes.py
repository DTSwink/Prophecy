import unreal,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
paths=['/Script/GameAnimationSample3.ProphecyWalkPinningLibrary:SetWalkPinningLimit',
       '/Script/GameAnimationSample3.ProphecyPhysicalFootTargetLibrary:SetPhysicalFootTargetClampLeeway',
       '/Script/GameAnimationSample3.PhysicsHitVelocityLibrary:GetHitTrajectory']
print('REOPEN_NODES',json.dumps({p:bool(unreal.find_object(None,p)) for p in paths}))
print('PIE_ACTIVE',bool(ed.get_game_world()))
print('DIRTY_CONTENT',[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()])
print('DIRTY_MAPS',[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])
