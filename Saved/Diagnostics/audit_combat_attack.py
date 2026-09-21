import unreal,pathlib,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CombatDemo/AttackReference'
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
m=actors.spawn_actor_from_class(unreal.ProphecyNNLocomotionManager,unreal.Vector(),transient=True)
try:assert m.call_method('AuditSlashReference',(str(folder.resolve()),))
finally:actors.destroy_actor(m)
r=json.loads((folder/'unreal_chain_audit.json').read_text())
print({k:v for k,v in r.items() if k not in ['outputs','teacher_outputs','frames']})
