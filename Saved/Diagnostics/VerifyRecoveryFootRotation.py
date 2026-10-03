import unreal,json
from pathlib import Path
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world=ed.get_editor_world()
name='SetAttackRecoveryFootRotationFromWalk'
assert unreal.find_object(None,'/Script/GameAnimationSample3.ProphecyAttackRecoveryLibrary:'+name)
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyAttackRecoveryLibrary'))
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
a=actors.spawn_actor_from_class(unreal.ProphecyAgent,unreal.Vector(0,0,-10000),transient=True)
try:
    assert lib.call_method(name,args=(a,True))
    assert lib.call_method(name,args=(a,False))
finally:actors.destroy_actor(a)
playing=bool(ed.get_game_world())
if not playing:
    bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    unreal.SystemLibrary.execute_console_command(world,'Prophecy.Editor.RepairLibraryDefaults')
    unreal.SystemLibrary.execute_console_command(world,'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.SystemLibrary.execute_console_command(world,'Automation RunTests Prophecy.NN.PolicyBlend.RecoveryFootRotation+Prophecy.NN.PolicyBlend.AttackRecovery+Prophecy.Blends.SixtyTickClock')
(Path(unreal.Paths.project_saved_dir())/'Diagnostics/RecoveryFootRotationValidation.json').write_text(json.dumps({'node':name,'called_enable_disable':True,'play_active':playing},indent=2))
print('RECOVERY_FOOT_ROTATION_NODE_VERIFIED',playing)
