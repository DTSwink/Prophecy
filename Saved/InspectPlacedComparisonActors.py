import unreal


subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for actor in subsystem.get_all_level_actors():
    class_name = actor.get_class().get_name()
    if "SandboxCharacter_CMC" in class_name or "BP_ProphecyManualPoseAgent" in class_name or "ProphecyNNLocomotionManager" in class_name:
        print("{} class={} location={}".format(actor.get_name(), class_name, actor.get_actor_location()))
