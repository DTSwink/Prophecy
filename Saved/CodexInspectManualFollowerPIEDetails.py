import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if not world:
    raise RuntimeError("No PIE game world")
for agent in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent):
    try:
        print("MANUAL_FOLLOW_PHYSICAL_BONES", agent.get_editor_property("physical bones"))
    except Exception as error:
        print("MANUAL_FOLLOW_PHYSICAL_BONES_ERROR", error)
    for component in agent.get_components_by_class(unreal.SkeletalMeshComponent):
        if component.get_name() == "PhysicalMesh":
            asset = component.get_editor_property("physics_asset_override") or component.get_physics_asset()
            print("MANUAL_FOLLOW_PHYSICS_ASSET", asset)
