import unreal

world = unreal.EditorLevelLibrary.get_game_world()
controller = unreal.GameplayStatics.get_player_controller(world, 0)
print("PLAYER_INPUT_API {}".format([
    name for name in dir(controller)
    if "input" in name.lower() or "key" in name.lower()]))
