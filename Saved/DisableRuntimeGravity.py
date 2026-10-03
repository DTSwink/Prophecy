import unreal

world = unreal.EditorLevelLibrary.get_game_world()
agents = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
for agent in agents:
    mesh = agent.get_agent_mesh()
    mesh.set_enable_gravity(False)
print(f"RUNTIME_GRAVITY_DISABLED agents={len(agents)}")
