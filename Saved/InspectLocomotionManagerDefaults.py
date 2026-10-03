import unreal

world = unreal.EditorLevelLibrary.get_editor_world()
managers = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyNNLocomotionManager)
for manager in managers:
    print(
        "LOCOMOTION_MANAGER_DEFAULTS name=" + manager.get_name()
        + " clamp_foot=" + str(manager.get_editor_property("clamp_foot"))
        + " foot_multiplier=" + str(manager.get_editor_property("foot_clamp_length_multiplier"))
        + " clamp_calf=" + str(manager.get_editor_property("clamp_calf"))
        + " calf_multiplier=" + str(manager.get_editor_property("calf_clamp_length_multiplier"))
    )
