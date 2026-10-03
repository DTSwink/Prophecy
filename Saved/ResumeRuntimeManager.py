import unreal

world = unreal.EditorLevelLibrary.get_game_world()
managers = unreal.GameplayStatics.get_all_actors_of_class(
    world, unreal.ProphecyNNLocomotionManager)
for manager in managers:
    manager.set_actor_tick_enabled(True)
print(f"RUNTIME_MANAGERS_RESUMED managers={len(managers)}")
