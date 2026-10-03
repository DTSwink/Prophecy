import unreal,json
from pathlib import Path
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None, 'User Play is active'
root=Path(unreal.Paths.project_dir()).resolve();stage=root/'Saved/Slash174664'
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
manager=actors.spawn_actor_from_class(unreal.ProphecyNNLocomotionManager,unreal.Vector(0,0,-10000),transient=True)
try:
 result=manager.call_method('AuditSlashReference',args=(str(stage),))
 print('CHECKPOINT174664_AUDIT',result)
 assert result, 'Native checkpoint chain audit failed'
finally: actors.destroy_actor(manager)
report=json.loads((stage/'unreal_chain_audit.json').read_text())
print(json.dumps({k:v for k,v in report.items() if k not in ('frames','outputs','teacher_outputs')}))
