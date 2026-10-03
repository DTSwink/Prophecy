import unreal

for actor in unreal.ObjectIterator(unreal.Actor):
    world = actor.get_world()
    if not world:
        continue
    if "ProphecyManualPoseAgent" not in actor.get_class().get_name():
        continue
    print("AGENT", actor.get_name(), actor.get_world().get_name())
    try:
        print("MODE", actor.get_simulation_mode())
    except Exception as exc:
        print("MODE_ERROR", exc)
    print("MANUAL", actor.get_editor_property("manual_nn_pose_application"))
    for component in actor.get_components_by_class(unreal.SkeletalMeshComponent):
        print(
            "MESH", component.get_name(),
            "SIM", component.is_simulating_physics("pelvis"),
            "FOOT_R_WORLD", component.get_socket_transform("foot_r", unreal.RelativeTransformSpace.RTS_WORLD).translation,
            "FOOT_R_COMPONENT", component.get_socket_transform("foot_r", unreal.RelativeTransformSpace.RTS_COMPONENT).translation,
        )
