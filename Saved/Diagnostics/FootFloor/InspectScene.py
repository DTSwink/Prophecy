import unreal, json, pathlib

def prop(obj, name):
    try: return str(obj.get_editor_property(name))
    except Exception as exc: return 'UNAVAILABLE:' + str(exc)

sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = sub.get_game_world() or sub.get_editor_world()
rows = []
for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
    if isinstance(actor, unreal.ProphecyAgent):
        mesh = actor.get_pose_reference_mesh()
        row = dict(actor=actor.get_path_name(), mode=str(actor.get_simulation_mode()),
                   jolt=actor.is_jolt_physical_animation_enabled(), root=str(actor.get_actor_location()),
                   mesh=str(mesh), magnetization=prop(actor, 'body_magnetization_settings'),
                   input=prop(actor, 'locomotion_input'), mesh_body=prop(mesh, 'body_instance'))
        asset = mesh.get_editor_property('physics_asset_override') or mesh.get_skeletal_mesh_asset().get_editor_property('physics_asset')
        row['phat'] = str(asset)
        row['phat_body_setups'] = prop(asset, 'skeletal_body_setups')
        rows.append(row)
    elif 'floor' in actor.get_actor_label().lower():
        for mesh in actor.get_components_by_class(unreal.PrimitiveComponent):
            row = dict(actor=actor.get_path_name(), component=mesh.get_path_name(),
                       body=prop(mesh,'body_instance'), material=str(mesh.get_material(0)),
                       object_type=str(mesh.get_collision_object_type()), transform=str(mesh.get_world_transform()))
            rows.append(row)
result = dict(world=world.get_path_name(), rows=rows,
              physics_settings=str(unreal.get_default_object(unreal.PhysicsSettings)))
out = pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics/FootFloor'
out.mkdir(parents=True, exist_ok=True)
(out / ('scene-live.json' if sub.get_game_world() else 'scene-editor.json')).write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
