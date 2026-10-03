import unreal

world = unreal.EditorLevelLibrary.get_game_world()
unreal.SystemLibrary.execute_console_command(world, "prophecy.Physical.LogTrackingError 1")
unreal.SystemLibrary.execute_console_command(world, "prophecy.Physical.LogPelvisError 1")
print("TRACKING_LOG=1 PELVIS_LOG=1")
