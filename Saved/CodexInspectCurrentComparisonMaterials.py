import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
agent = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)[0]
manager = unreal.GameplayStatics.get_actor_of_class(world, unreal.ProphecyNNLocomotionManager)
components = list(agent.get_components_by_class(unreal.SkinnedMeshComponent))
components += list(manager.get_components_by_class(unreal.PoseableMeshComponent))
for component in components:
    materials = []
    for index in range(component.get_num_materials()):
        material = component.get_material(index)
        materials.append(material.get_path_name() if material else None)
    print("COMPARISON_MATERIAL", component.get_name(), materials)
