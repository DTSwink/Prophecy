import unreal


actor = next(
    actor
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    if actor.get_actor_label() == "MetaHuman_Far_Audit"
)
body = next(component for component in actor.get_components_by_class(unreal.SkeletalMeshComponent) if component.get_name() == "Body")
for name in ("override_animation_data", "set_animation", "play_animation", "set_position", "set_update_animation_in_editor", "set_animation_mode"):
    method = getattr(body, name)
    print("DOC|{}|{}".format(name, method.__doc__))
print("ANIMATION_DATA|{}".format(body.animation_data))
print("ANIMATION_DATA_DIR|{}".format(",".join(name for name in dir(body.animation_data) if not name.startswith("_"))))
