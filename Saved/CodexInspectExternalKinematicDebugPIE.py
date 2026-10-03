import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
agents = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
if len(agents) != 1:
    raise RuntimeError(f"Expected one agent, got {len(agents)}")
agent = agents[0]
print("KINEMATIC_DEBUG_OPTION", agent.get_editor_property("show_kinematic_debug_mesh"))
manager = unreal.GameplayStatics.get_actor_of_class(world, unreal.ProphecyNNLocomotionManager)
components = list(agent.get_components_by_class(unreal.SkinnedMeshComponent))
components += list(manager.get_components_by_class(unreal.PoseableMeshComponent))
for component in components:
    print(
        "KINEMATIC_DEBUG_COMPONENT", component.get_name(),
        "asset=", component.get_skinned_asset(),
        "tick=", component.is_component_tick_enabled(),
        "visible=", component.is_visible(),
        "simulate=", component.is_simulating_physics(),
        "anim=", component.get_anim_instance()
        if isinstance(component, unreal.SkeletalMeshComponent) else None,
    )
