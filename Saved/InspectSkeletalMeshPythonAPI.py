import unreal

world = unreal.EditorLevelLibrary.get_editor_world()
agents = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
if not agents:
    print("NO_EDITOR_AGENT")
else:
    mesh = agents[0].get_agent_mesh().get_skeletal_mesh_asset()
    names = [name for name in dir(mesh) if "bone" in name.lower() or "ref" in name.lower() or "skeleton" in name.lower()]
    print("SKELETAL_MESH_API=" + ",".join(names))
    skeleton = mesh.get_editor_property("skeleton")
    names = [name for name in dir(skeleton) if "bone" in name.lower() or "ref" in name.lower()]
    print("SKELETON_API=" + ",".join(names))
