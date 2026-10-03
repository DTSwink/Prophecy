import unreal

world = unreal.EditorLevelLibrary.get_game_world()
agents = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
for agent in agents:
    mesh = agent.get_agent_mesh()
    mesh.set_all_motors_angular_position_drive(False, False, False)
    mesh.set_all_motors_angular_velocity_drive(False, False, False)
print(f"RUNTIME_JOINT_MOTORS_DISABLED agents={len(agents)}")
