import sys
import unreal

if len(sys.argv) != 3:
    raise RuntimeError("Usage: SetPhysicalRootGains.py <orientation_strength> <angular_velocity_strength>")

world = unreal.EditorLevelLibrary.get_game_world()
if world is None:
    raise RuntimeError("PIE is not running")

orientation_strength = float(sys.argv[1])
angular_velocity_strength = float(sys.argv[2])
agents = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
physical_agents = [
    agent for agent in agents
    if agent.get_simulation_mode() == unreal.ProphecyAgentSimulationMode.PHYSICAL
]
if not physical_agents:
    raise RuntimeError("No Physical ProphecyAgent exists in PIE")

for agent in physical_agents:
    settings = agent.get_editor_property("physical_drive_settings")
    settings.set_editor_property("orientation_strength", orientation_strength)
    settings.set_editor_property("angular_velocity_strength", angular_velocity_strength)
    agent.set_editor_property("physical_drive_settings", settings)

print(
    "PHYSICAL_ROOT_GAINS orientation="
    + str(orientation_strength)
    + " angular_velocity="
    + str(angular_velocity_strength)
    + " agents="
    + str(len(physical_agents))
)
