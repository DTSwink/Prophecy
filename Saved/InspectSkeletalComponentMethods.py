import unreal


actor = next(
    actor
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    if actor.get_actor_label() == "MetaHuman_Far_Audit"
)
body = next(component for component in actor.get_components_by_class(unreal.SkeletalMeshComponent) if component.get_name() == "Body")
for token in ("dirty", "refresh", "bone", "tick", "pose", "animation", "position"):
    print("COMP_METHODS|{}|{}".format(token, ",".join(name for name in dir(body) if token in name.lower())))
