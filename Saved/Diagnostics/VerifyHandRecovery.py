import unreal,json
from pathlib import Path
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
cls=unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyHandRecoveryLibrary')
assert cls
lib=unreal.get_default_object(cls)
names=['SetLocomotionHandTempering','BlendLocomotionHandTemperingToNormal','SetAttackToLocomotionHandBlend']
for n in names:
    assert unreal.find_object(None,'/Script/GameAnimationSample3.ProphecyHandRecoveryLibrary:'+n),n
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
a=actors.spawn_actor_from_class(unreal.ProphecyAgent,unreal.Vector(0,0,-10000),transient=True)
try:
    assert lib.call_method(names[0],args=(a,True,0.,.2,.3,.4,.5,.6))
    assert lib.call_method(names[1],args=(a,.5,1.,0.,.5))
    assert lib.call_method(names[2],args=(a,unreal.ProphecyRecoverySource.WALK,.5,1.,unreal.ProphecyRecoverySource.RUN,0.,.5))
    assert lib.call_method(names[0],args=(a,False,1.,1.,1.,1.,1.,1.))
    assert lib.call_method(names[2],args=(a,unreal.ProphecyRecoverySource.NORMAL,0.,0.,unreal.ProphecyRecoverySource.NORMAL,0.,0.))
finally:
    actors.destroy_actor(a)
playing=bool(unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world())
if not playing:
    bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    unreal.SystemLibrary.execute_console_command(world,'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.SystemLibrary.execute_console_command(world,'Automation RunTests Prophecy.NN.HandRecovery')
(Path(unreal.Paths.project_dir())/'Saved/Diagnostics/HandRecoveryValidation.json').write_text(json.dumps({'reflected_and_called':names,'play_active':playing},indent=2))
print('HAND_RECOVERY_NODES_VERIFIED',names)
