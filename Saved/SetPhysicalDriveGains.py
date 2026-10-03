import sys
import unreal

world = unreal.EditorLevelLibrary.get_game_world()
if world is None:
    raise RuntimeError("PIE is not running")
position = float(sys.argv[1]) if len(sys.argv) > 1 else 10000.0
velocity = float(sys.argv[2]) if len(sys.argv) > 2 else 200.0
orientation = float(sys.argv[3]) if len(sys.argv) > 3 else 15000.0
angular_velocity = float(sys.argv[4]) if len(sys.argv) > 4 else 500.0
count = 0
for agent in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent):
    settings = agent.get_editor_property("physical_drive_settings")
    settings.position_strength = position
    settings.velocity_strength = velocity
    settings.orientation_strength = orientation
    settings.angular_velocity_strength = angular_velocity
    agent.set_editor_property("physical_drive_settings", settings)
    count += 1
print("PHYSICAL_GAINS pos={} vel={} ori={} ang_vel={} agents={}".format(
    position, velocity, orientation, angular_velocity, count))
