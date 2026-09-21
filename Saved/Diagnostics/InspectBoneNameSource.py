import unreal

subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = subsystem.get_game_world() or subsystem.get_editor_world()
print('WORLD=' + world.get_path_name())
for agent in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent):
    print('AGENT=' + agent.get_path_name())
    for mesh in agent.get_components_by_class(unreal.SkeletalMeshComponent):
        asset = mesh.get_skeletal_mesh_asset()
        names = mesh.get_all_socket_names()
        print('COMPONENT={} ASSET={} SOCKET_AND_BONE_NAMES={} FIRST={}'.format(
            mesh.get_name(), asset.get_path_name() if asset else 'NONE', len(names),
            ','.join(str(name) for name in names[:5])))
