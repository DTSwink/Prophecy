import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if not world:
    raise RuntimeError("PIE world is not running")
agents = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
if not agents:
    raise RuntimeError("No ProphecyAgent exists in PIE")
agent = agents[0]

agent.set_upper_nn_inputs(True, 0.25, -0.5)
if not agent.get_editor_property("bUpperNNHasSword"):
    raise RuntimeError("Upper sword input did not update")
if abs(agent.get_editor_property("UpperNNGazeYawNormalized") - 0.25) > 1.0e-6:
    raise RuntimeError("Upper gaze yaw input did not update")
if abs(agent.get_editor_property("UpperNNGazePitchNormalized") + 0.5) > 1.0e-6:
    raise RuntimeError("Upper gaze pitch input did not update")

if not agent.set_physical_feedback_tolerance("head", 1.25, 7.5):
    raise RuntimeError("FName upper-bone feedback setter rejected head")
settings = agent.get_physical_feedback_tolerance("head")
if abs(settings.linear_tolerance_cm - 1.25) > 1.0e-6:
    raise RuntimeError("Head linear feedback tolerance did not round-trip")
if abs(settings.angular_tolerance_degrees - 7.5) > 1.0e-6:
    raise RuntimeError("Head angular feedback tolerance did not round-trip")

affected = agent.set_physical_feedback_tolerance_below(
    "spine_03", True, 2.0, 9.0
)
if affected < 1:
    raise RuntimeError("FName hierarchy feedback setter found no upper bones")

agent.set_all_physical_feedback_tolerances(0.0, 0.0)
agent.set_upper_nn_inputs(False, 0.0, 0.0)
print("UPPER_BLUEPRINT_API_OK affected_bones=" + str(affected))
