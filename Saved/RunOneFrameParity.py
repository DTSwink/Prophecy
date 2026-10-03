import unreal

world = unreal.EditorLevelLibrary.get_game_world()
if world is None:
    raise RuntimeError("PIE is not running")
unreal.SystemLibrary.execute_console_command(world, "prophecy.Physical.OneFrameParity")
print("ONE_FRAME_PARITY_REQUESTED")
