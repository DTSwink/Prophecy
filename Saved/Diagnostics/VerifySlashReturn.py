import unreal,json
from pathlib import Path
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
cls=unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySlashReturnLibrary')
assert cls
lib=unreal.get_default_object(cls)
name='SetSlashRightArmReturnToNeutral'
assert unreal.find_object(None,'/Script/GameAnimationSample3.ProphecySlashReturnLibrary:'+name)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
a=actors.spawn_actor_from_class(unreal.ProphecyAgent,unreal.Vector(0,0,-10000),transient=True)
try:
    assert lib.call_method(name,args=(a,True,.3,.5,100.))
    assert not lib.call_method(name,args=(a,True,-1.,.5,100.))
    assert lib.call_method(name,args=(a,False,0.,0.,100.))
finally:actors.destroy_actor(a)
playing=bool(unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world())
if not playing:
    bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    unreal.SystemLibrary.execute_console_command(world,'Prophecy.Editor.RepairLibraryDefaults')
    unreal.SystemLibrary.execute_console_command(world,'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.SystemLibrary.execute_console_command(world,'Automation RunTests Prophecy.NN.SlashReturn+Prophecy.NN.HandRecovery+Prophecy.NN.CoreTempering')
(Path(unreal.Paths.project_dir())/'Saved/Diagnostics/SlashReturnValidation.json').write_text(json.dumps({'reflected_and_called':name,'play_active':playing},indent=2))
print('SLASH_RETURN_NODE_VERIFIED')
