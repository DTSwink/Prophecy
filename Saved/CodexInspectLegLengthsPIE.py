import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
agents = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
if len(agents) != 1:
    raise RuntimeError("Expected one Prophecy agent")
agent = agents[0]
target = agent.get_agent_mesh()
physical = None
for component in agent.get_components_by_class(unreal.SkeletalMeshComponent):
    if component.get_name() == "PhysicalMesh":
        physical = component
if not physical:
    raise RuntimeError("PhysicalMesh missing")
for side in ("l", "r"):
    thigh = "thigh_" + side
    calf = "calf_" + side
    foot = "foot_" + side
    for parent, child in ((thigh, calf), (calf, foot)):
        target_length = (target.get_socket_location(child) - target.get_socket_location(parent)).length()
        physical_length = (physical.get_socket_location(child) - physical.get_socket_location(parent)).length()
        print("LEG_LENGTH side={} segment={}->{} target_cm={:.6f} physical_cm={:.6f} difference_cm={:.6f}".format(
            side, parent, child, target_length, physical_length, target_length - physical_length))
