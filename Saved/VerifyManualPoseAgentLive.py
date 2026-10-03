import unreal

world = unreal.EditorLevelLibrary.get_game_world()
agents = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent)
managers = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyNNLocomotionManager)
if len(agents) != 1:
    raise RuntimeError("Expected one agent, found {}".format(len(agents)))

agent = agents[0]
mesh = agent.get_agent_mesh()
future_pose = agent.read_nn_future_world_pose()
manager = managers[0] if managers else None
spawn_class = manager.get_editor_property("agent_class") if manager else None
spawn_cdo = unreal.get_default_object(spawn_class) if spawn_class else None
print("MANUAL_POSE_LIVE class={} root={} mode={} manual={} mesh_tick={} pose_result_type={}".format(
    agent.get_class().get_name(),
    agent.get_root_low_point(),
    agent.get_simulation_mode(),
    agent.get_editor_property("manual_nn_pose_application"),
    mesh.is_component_tick_enabled(),
    type(future_pose).__name__))
print("MANUAL_POSE_CLASS agents={} manager_class={} cdo_manual={}".format(
    len(agents), spawn_class,
    spawn_cdo.get_editor_property("manual_nn_pose_application") if spawn_cdo else None))
pose_shape = []
for value in future_pose:
    try:
        pose_shape.append(len(value))
    except TypeError:
        pose_shape.append(value)
root = agent.get_root_low_point()
foot = mesh.get_socket_location("foot_l")
foot_component = mesh.get_socket_transform(
    "foot_l", unreal.RelativeTransformSpace.RTS_COMPONENT).translation
print("MANUAL_POSE_DATA shape={} foot_minus_root=({:.4f},{:.4f},{:.4f}) foot_component=({:.4f},{:.4f},{:.4f})".format(
    pose_shape, foot.x - root.x, foot.y - root.y, foot.z - root.z,
    foot_component.x, foot_component.y, foot_component.z))
