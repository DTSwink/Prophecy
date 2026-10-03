import unreal


TAG = "CodexMetaHumanFinalAudit"
actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())

for actor in actors:
    if "audit" not in actor.get_actor_label().lower() and not actor.get_components_by_class(unreal.SkeletalMeshComponent):
        continue
    print("ACTOR|{}|{}".format(actor.get_actor_label(), actor.get_class().get_name()))
    components = actor.get_components_by_class(unreal.SkeletalMeshComponent)
    for component in components:
        anim_instance = component.get_anim_instance()
        print(
            "COMP|{}|mode={}|mesh={}|anim={}|post={}".format(
                component.get_name(),
                component.animation_mode,
                component.skeletal_mesh.get_name() if component.skeletal_mesh else "None",
                anim_instance.get_class().get_name() if anim_instance else "None",
                component.get_post_process_instance().get_class().get_name()
                if component.get_post_process_instance()
                else "None",
            )
        )
        if anim_instance:
            relevant = [name for name in dir(anim_instance) if "animation" in name.lower() or "position" in name.lower()]
            print("METHODS|{}|{}".format(component.get_name(), ",".join(relevant)))
