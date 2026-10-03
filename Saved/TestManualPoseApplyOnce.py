import unreal

world = unreal.EditorLevelLibrary.get_game_world()
agents = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
if len(agents) != 1:
    raise RuntimeError("Expected one agent, found {}".format(len(agents)))

agent = agents[0]
mesh = agent.get_agent_mesh()
before = mesh.get_socket_transform(
    "foot_l", unreal.RelativeTransformSpace.RTS_COMPONENT).translation
applied = agent.apply_nn_pose_kinematically(1.0 / 60.0)
after = mesh.get_socket_transform(
    "foot_l", unreal.RelativeTransformSpace.RTS_COMPONENT).translation
print("MANUAL_APPLY applied={} before=({:.4f},{:.4f},{:.4f}) after=({:.4f},{:.4f},{:.4f}) delta_cm={:.4f}".format(
    applied,
    before.x, before.y, before.z,
    after.x, after.y, after.z,
    (after - before).length()))
