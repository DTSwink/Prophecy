import unreal

world = unreal.EditorLevelLibrary.get_game_world()
if world is None:
    raise RuntimeError("PIE is not running")
agents = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
if not agents:
    raise RuntimeError("No ProphecyAgent exists in PIE")
agent = agents[0]
ok = agent.set_simulation_mode(unreal.ProphecyAgentSimulationMode.PHYSICAL)
mesh = agent.get_agent_mesh()
mesh.set_collision_response_to_all_channels(unreal.CollisionResponseType.ECR_IGNORE)
mesh.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
print("PROMOTE=" + str(ok) + " AGENT=" + agent.get_name() + " COLLISION=" + str(mesh.get_collision_enabled()))
