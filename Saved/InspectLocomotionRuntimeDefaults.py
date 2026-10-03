import unreal

world = unreal.EditorLevelLibrary.get_game_world()
for manager in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyNNLocomotionManager):
    print("MANAGER {} clamp_foot={} foot_mul={} clamp_calf={} calf_mul={} steps={}".format(
        manager.get_name(),
        manager.get_editor_property("clamp_foot"),
        manager.get_editor_property("foot_clamp_length_multiplier"),
        manager.get_editor_property("clamp_calf"),
        manager.get_editor_property("calf_clamp_length_multiplier"),
        manager.get_editor_property("foot_roll_integration_steps")))
for agent in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent):
    settings = agent.get_editor_property("physical_drive_settings")
    print("AGENT {} mode={} root_gains={}/{}/{}/{}".format(
        agent.get_name(), agent.get_simulation_mode(), settings.position_strength,
        settings.velocity_strength, settings.orientation_strength,
        settings.angular_velocity_strength))
