import unreal

world = unreal.EditorLevelLibrary.get_game_world()
agents = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
if len(agents) != 1:
    raise RuntimeError("Expected one agent, found {}".format(len(agents)))
root = agents[0].get_root_low_point()
print("AGENT_ROOT {:.6f} {:.6f} {:.6f}".format(root.x, root.y, root.z))
