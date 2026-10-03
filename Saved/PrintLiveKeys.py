import unreal

world = unreal.EditorLevelLibrary.get_game_world()
controller = unreal.GameplayStatics.get_player_controller(world, 0)
def key(name):
    value = unreal.Key()
    value.set_editor_property("key_name", name)
    return value

print("LIVE_KEYS Z={} S={} Q={} D={}".format(
    controller.is_input_key_down(key("Z")),
    controller.is_input_key_down(key("S")),
    controller.is_input_key_down(key("Q")),
    controller.is_input_key_down(key("D"))))
