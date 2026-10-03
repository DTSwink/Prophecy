import unreal

world = unreal.EditorLevelLibrary.get_game_world()
agents = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
for agent in agents:
    mesh = agent.get_agent_mesh()
    print(
        "PHYSICAL_AGENT_STATE name=" + agent.get_name()
        + " mode=" + str(agent.get_simulation_mode())
        + " drive=" + str(agent.get_editor_property("physical_drive_mode"))
        + " tick=" + str(agent.is_actor_tick_enabled())
        + " pelvis_sim=" + str(mesh.is_simulating_physics("pelvis"))
        + " bodies=" + str(len(mesh.get_constraints(False)))
    )
