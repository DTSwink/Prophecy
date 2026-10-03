import unreal,json,hashlib
from pathlib import Path
root=Path(unreal.Paths.project_dir()).resolve();stage=root/'Saved/Slash174664';dest=root/'Content/locomotion/NN'
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
runtime=json.loads((dest/'prophecy_slash_runtime.json').read_text());native=json.loads((dest/'prophecy_slash_native.json').read_text())
assert runtime['checkpoint_step']==174664 and runtime['checkpoint_sha256']==native['checkpoint_sha256']
assert native['pin_full_strength_at']==.99
for n in native['networks'].values(): assert hashlib.sha256((dest/n['file']).read_bytes()).hexdigest()==n['sha256']
check=stage/'startup_check';check.mkdir(exist_ok=True)
frame=json.loads((stage/'native_geometry_reference.json').read_text())[0]
(check/'chain_audit.json').write_text(json.dumps(dict(inputs=[frame['state']],expected=[frame['output']],four_step_oracle=[frame['output']],segments=[])))
(check/'source_native_geometry.json').write_text((dest/'prophecy_slash_native.json').read_text())
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
manager=actors.spawn_actor_from_class(unreal.ProphecyNNLocomotionManager,unreal.Vector(0,0,-10000),transient=True)
try:
 result=manager.call_method('AuditSlashReference',args=(str(check),))
 assert result,'Installed checkpoint failed startup validation'
 print('INSTALLED_STEP174664_VERIFIED',runtime['checkpoint_sha256'])
finally: actors.destroy_actor(manager)
unreal.SystemLibrary.execute_console_command(unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world(),'Prophecy.Editor.ClearAttackCache')
