import unreal


def safe(call, default="<unavailable>"):
    try:
        return call()
    except Exception as error:
        return "{} ({})".format(default, error)


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if not world:
    raise RuntimeError("PIE is not running")

channel_type = unreal.CollisionChannel
channel_names = [
    name for name in dir(channel_type)
    if name.isupper() and not name.startswith("_")
]
print("CHANNEL_NAMES {}".format(channel_names))

for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
    class_name = actor.get_class().get_name()
    if not any(token in class_name for token in [
        "BP_ProphecyManualPoseAgent", "SandboxCharacter_CMC"
    ]):
        continue
    print("ACTOR {} {} tick_enabled={}".format(
        actor.get_name(), class_name, safe(lambda: actor.is_actor_tick_enabled())))
    for component in actor.get_components_by_class(unreal.PrimitiveComponent):
        if component.get_name() not in ["CapsuleComponent", "Capsule", "PhysicalMesh", "Mesh", "CharacterMesh0"]:
            continue
        print("  COMPONENT {} class={} profile={} enabled={} object_type={} sim={} parent={}".format(
            component.get_name(), component.get_class().get_name(),
            safe(lambda c=component: c.get_collision_profile_name()),
            safe(lambda c=component: c.get_collision_enabled()),
            safe(lambda c=component: c.get_collision_object_type()),
            safe(lambda c=component: c.is_simulating_physics()),
            safe(lambda c=component: c.get_attach_parent().get_name() if c.get_attach_parent() else None)))
        for channel_name in channel_names:
            channel = getattr(channel_type, channel_name)
            response = safe(lambda c=component, ch=channel: c.get_collision_response_to_channel(ch))
            print("    {}={}".format(channel_name, response))

