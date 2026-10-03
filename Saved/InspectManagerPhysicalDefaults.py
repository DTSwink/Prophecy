import unreal


subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for actor in subsystem.get_all_level_actors():
    if "ProphecyNNLocomotionManager" not in actor.get_class().get_name():
        continue
    print("MANAGER {}".format(actor))
    for name in [
        "agent_class",
        "initial_physical_agent_count",
        "initial_physical_drive_mode",
        "initial_physical_count",
        "crowd_size",
    ]:
        try:
            print("  {}={}".format(name, actor.get_editor_property(name)))
        except Exception as error:
            print("  {} unavailable={}".format(name, error))
