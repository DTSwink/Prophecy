import unreal

world = unreal.EditorLevelLibrary.get_game_world()
unreal.SystemLibrary.execute_console_command(world, "prophecy.Physical.LogTrackingError 0")
unreal.SystemLibrary.execute_console_command(world, "prophecy.Physical.LogPelvisError 0")
print("TRACKING_LOG=0 PELVIS_LOG=0")
