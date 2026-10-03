import unreal
import json
from pathlib import Path
root=Path(unreal.Paths.project_dir()).resolve()
stage=root/'Saved/Slash123793'
check=stage/'startup_check';check.mkdir(exist_ok=True)
frame=json.loads((stage/'native_geometry_reference.json').read_text())[0]
(check/'chain_audit.json').write_text(json.dumps(dict(inputs=[frame['state']],expected=[frame['output']],four_step_oracle=[frame['output']],segments=[])))
(check/'source_native_geometry.json').write_text((stage/'prophecy_slash_native.json').read_text())
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
manager=actors.spawn_actor_from_class(unreal.ProphecyNNLocomotionManager,unreal.Vector(0,0,-10000),transient=True)
try:
    result=manager.call_method('AuditSlashReference',args=(str(check),))
    print('INSTALLED_STARTUP',result)
    assert result,'Installed checkpoint failed startup validation'
finally:
    actors.destroy_actor(manager)
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world():
    bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    unreal.SystemLibrary.execute_console_command(world,'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.SystemLibrary.execute_console_command(world,'Automation RunTests Prophecy.NN.PhysicalTargets.AttackLegClamps')
