import unreal,pathlib,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
m=actors.spawn_actor_from_class(unreal.ProphecyNNLocomotionManager,unreal.Vector(0,0,-10000),transient=True)
try:print('AUDIT_RESULT',m.call_method('AuditSlashReference',args=(str(pathlib.Path(unreal.Paths.project_saved_dir())/'SlashTrain2223'),)))
finally:actors.destroy_actor(m)
