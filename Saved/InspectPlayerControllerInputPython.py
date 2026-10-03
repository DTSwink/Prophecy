import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if not world:
    raise RuntimeError("PIE is not running")
controller = unreal.GameplayStatics.get_player_controller(world, 0)
print([name for name in dir(controller) if "input" in name.lower() or "key" in name.lower()])
print("INPUT_KEY_PARAMS {}".format([
    name for name in dir(unreal.InputKeyParams)
    if not name.startswith("_")
]))

