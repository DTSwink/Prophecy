import unreal

world = unreal.EditorLevelLibrary.get_game_world()
agents = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
if not agents:
    raise RuntimeError("No ProphecyAgent in PIE")

for agent in agents:
    mesh = agent.get_agent_mesh()
    pelvis_simulated = mesh.is_simulating_physics("pelvis")
    print("LIVE_PHYSICAL agent={} mode={} pelvis_simulating={} constraints={} collision={}".format(
        agent.get_name(), agent.get_simulation_mode(), pelvis_simulated,
        len(mesh.get_constraints(False)), mesh.get_collision_enabled()))
