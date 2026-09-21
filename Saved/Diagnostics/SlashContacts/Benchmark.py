import unreal,json,pathlib
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not world.get_game_world()
actor=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(unreal.ProphecyNNLocomotionManager,unreal.Vector(0,0,-10000),transient=True)
out={}
try:
    for count in [1,4,100]:
        result=actor.call_method('BenchmarkSlashRuntime',args=(False,count))
        p=pathlib.Path(unreal.Paths.project_saved_dir())/'SlashParity'/('native_cpu_b%d.json'%count)
        out[str(count)]={'returned':result,'report':json.loads(p.read_text())}
finally:unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(actor)
(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SlashContacts/Benchmark.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
