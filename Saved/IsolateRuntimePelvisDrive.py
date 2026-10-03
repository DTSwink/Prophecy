import unreal

world = unreal.EditorLevelLibrary.get_game_world()
managers = unreal.GameplayStatics.get_all_actors_of_class(
    world, unreal.ProphecyNNLocomotionManager)
agents = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
for manager in managers:
    manager.set_actor_tick_enabled(False)
for agent in agents:
    mesh = agent.get_agent_mesh()
    mesh.set_enable_gravity(False)
    mesh.set_all_motors_angular_position_drive(False, False, False)
    mesh.set_all_motors_angular_velocity_drive(False, False, False)
    mesh.set_all_physics_linear_velocity(unreal.Vector(), False)
    mesh.set_all_physics_angular_velocity_in_radians(unreal.Vector(), False)
print(f"RUNTIME_PELVIS_ISOLATED managers={len(managers)} agents={len(agents)}")
