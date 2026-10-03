import unreal


def tick_info(obj, property_name):
    tick = obj.get_editor_property(property_name)
    result = {}
    for name in [
        "tick_group", "end_tick_group", "can_ever_tick", "start_with_tick_enabled",
        "tick_even_when_paused", "allow_tick_on_dedicated_server", "high_priority",
    ]:
        try:
            result[name] = str(tick.get_editor_property(name))
        except Exception:
            pass
    return result


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if not world:
    raise RuntimeError("PIE is not running")
for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
    if not any(token in actor.get_class().get_name() for token in [
        "BP_ProphecyManualPoseAgent", "SandboxCharacter_CMC"
    ]):
        continue
    print("ACTOR {} {}".format(actor.get_name(), tick_info(actor, "primary_actor_tick")))
    for component in actor.get_components_by_class(unreal.ActorComponent):
        if component.get_name() in ["Mesh", "CharacterMesh0", "PhysicalMesh", "CharMoveComp"]:
            print("  {} {} enabled={}".format(
                component.get_name(), tick_info(component, "primary_component_tick"),
                component.is_component_tick_enabled()))
