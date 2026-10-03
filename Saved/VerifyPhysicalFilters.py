import unreal

world = unreal.EditorLevelLibrary.get_game_world()
agent = [
    actor for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
    if actor.get_simulation_mode() == unreal.ProphecyAgentSimulationMode.PHYSICAL
][0]
mesh = agent.get_agent_mesh()
for channel in (
    unreal.CollisionChannel.ECC_WORLD_STATIC,
    unreal.CollisionChannel.ECC_WORLD_DYNAMIC,
    unreal.CollisionChannel.ECC_PAWN,
):
    print(str(channel) + "=" + str(mesh.get_collision_response_to_channel(channel)))
print("CONSTRAINTS=" + str(len(mesh.get_constraints(False))))
