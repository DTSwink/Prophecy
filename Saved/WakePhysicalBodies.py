import unreal

world = unreal.EditorLevelLibrary.get_game_world()
agents = [
    actor for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
    if actor.get_simulation_mode() == unreal.ProphecyAgentSimulationMode.PHYSICAL
]
for agent in agents:
    agent.get_agent_mesh().wake_all_rigid_bodies()
print("WOKE=" + str(len(agents)))
