import sys
import unreal

world = unreal.EditorLevelLibrary.get_game_world()
if world is None:
    raise RuntimeError("PIE is not running")
mode = int(sys.argv[1]) if len(sys.argv) > 1 else 1
unreal.SystemLibrary.execute_console_command(
    world, "prophecy.Physical.OneFrameAngularLimits " + str(mode))
unreal.SystemLibrary.execute_console_command(world, "prophecy.Physical.OneFrameParity")
print("ONE_FRAME_PARITY_REQUESTED mode=" + str(mode))
