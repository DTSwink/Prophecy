import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world=ed.get_editor_world()
assert unreal.find_object(None,'/Script/GameAnimationSample3.PhysicsHitVelocityLibrary:GetHitTrajectory')
lib=unreal.get_default_object(unreal.PhysicsHitVelocityLibrary)
result=lib.call_method('GetHitTrajectory',(world,unreal.Vector(0,0,0),unreal.Vector(1000,0,0),unreal.Vector(0,0,0),45.,10000.,10.,1.))
print('HIT_TRAJECTORY_REFLECTION_OK',result)
unreal.SystemLibrary.execute_console_command(world,'Automation RunTests Prophecy.Physics.HitTrajectory')
