import unreal, json, pathlib
sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = sub.get_game_world()
assert world, 'PIE must be running'
rows = []
for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent):
    mesh = actor.get_pose_reference_mesh()
    active = actor.is_jolt_physical_animation_enabled()
    row = {'actor': actor.get_name(), 'mesh': mesh.get_name(),
           'class': mesh.get_class().get_path_name(), 'jolt_active': active}
    assert isinstance(mesh, unreal.ProphecyPhysicsSkeletalMeshComponent), row
    if active:
        unreal.log('FORCE_SCENE_SMOKE_BEGIN ' + actor.get_name())
        mesh.add_force(unreal.Vector(10, 0, 0), 'foot_l', True)
        mesh.add_impulse(unreal.Vector(0.1, 0, 0), 'foot_r', True)
        row['standard_nodes_called'] = True
        assert actor.is_jolt_physical_animation_enabled()
        unreal.log('FORCE_SCENE_SMOKE_END ' + actor.get_name())
    rows.append(row)
props = []
for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
    if actor.get_class().get_name() == 'A_Sword_C':
        for mesh in actor.get_components_by_class(unreal.StaticMeshComponent):
            if mesh.get_name() == 'sword':
                assert isinstance(mesh, unreal.ProphecyPhysicsStaticMeshComponent)
                props.append({'actor': actor.get_name(), 'class': mesh.get_class().get_path_name()})
assert rows and any(r['jolt_active'] for r in rows), rows
result = {'characters': rows, 'swords': props}
path = pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/ForceNodes/SceneSmoke.json'
path.write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
