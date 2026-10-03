import unreal

world = unreal.EditorLevelLibrary.get_game_world()
if world is None:
    raise RuntimeError("PIE is not running")
managers = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyNNLocomotionManager)
for manager in managers:
    manager.set_editor_property("clamp_foot", True)
    manager.set_editor_property("foot_clamp_length_multiplier", 1.0)
    manager.set_editor_property("clamp_calf", True)
    manager.set_editor_property("calf_clamp_length_multiplier", 1.0)
print("RUNTIME_LEG_CLAMPS foot=1.0 calf=1.0 managers=" + str(len(managers)))
