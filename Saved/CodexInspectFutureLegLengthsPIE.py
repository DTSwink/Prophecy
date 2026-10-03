import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
agents = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
if len(agents) != 1:
    raise RuntimeError("Expected one Prophecy agent")
agent = agents[0]
result = agent.read_nn_future_world_pose()
names, future, interpolated, alpha = result
index = {str(name): i for i, name in enumerate(names)}
print("FUTURE_POSE_ALPHA", alpha, "NAMES", [str(name) for name in names])
for side in ("l", "r"):
    thigh = "thigh_" + side
    calf = "calf_" + side
    foot = "foot_" + side
    for parent, child in ((thigh, calf), (calf, foot)):
        fp = future[index[parent]].translation
        fc = future[index[child]].translation
        ip = interpolated[index[parent]].translation
        ic = interpolated[index[child]].translation
        print("FUTURE_LEG_LENGTH side={} segment={}->{} future_cm={:.6f} interpolated_cm={:.6f}".format(
            side, parent, child, (fc - fp).length(), (ic - ip).length()))
