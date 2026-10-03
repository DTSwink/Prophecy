import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if not world:
    raise RuntimeError("No PIE game world")
for agent in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent):
    print("AUDIT_AGENT", agent.get_name(), agent.get_class().get_name(), "tick", agent.is_actor_tick_enabled())
    for component in agent.get_components_by_class(unreal.SkeletalMeshComponent):
        print(
            "AUDIT_MESH",
            component.get_name(),
            "sim_root", component.is_simulating_physics(),
            "sim_any", component.is_any_simulating_physics(),
        )
unreal.SystemLibrary.execute_console_command(world, "prophecy.Physical.AuditManualFollower")
