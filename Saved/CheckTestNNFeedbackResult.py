import unreal

for actor in unreal.ObjectIterator(unreal.Actor):
    world = actor.get_world()
    if not world or world.get_name() != "testNN" or "ProphecyManualPoseAgent" not in actor.get_class().get_name():
        continue
    physical = next((c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == "PhysicalMesh"), None)
    print("AGENT", actor.get_name(), "MODE", actor.get_simulation_mode())
    print("PHYSICAL_FOOT_R_COMPONENT", physical.get_socket_transform("foot_r", unreal.RelativeTransformSpace.RTS_COMPONENT))
    print("PHYSICAL_FOOT_R_WORLD", physical.get_socket_transform("foot_r", unreal.RelativeTransformSpace.RTS_WORLD))
    for component in unreal.ObjectIterator(unreal.PoseableMeshComponent):
        if component.get_world() == world and "KinematicDebugMesh" in component.get_name():
            print("KINEMATIC_FOOT_R_WORLD", component.get_socket_transform("foot_r", unreal.RelativeTransformSpace.RTS_WORLD))
    print("POSE_METHODS", [name for name in dir(actor) if "future" in name.lower() or "pose" in name.lower()])
    print("READ_DOC", actor.read_nn_future_world_pose.__doc__)
    try:
        result = actor.read_nn_future_world_pose()
        print("READ_RESULT", result)
        if result:
            names, future, interpolated, alpha = result
            index = list(names).index("foot_r")
            print("NN_FUTURE_FOOT_R_WORLD", future[index])
            print("NN_INTERPOLATED_FOOT_R_WORLD", interpolated[index])
    except Exception as exc:
        print("READ_ERROR", exc)
