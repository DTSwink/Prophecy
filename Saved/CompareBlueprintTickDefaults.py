import unreal


for path in [
    "/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent",
    "/Game/_mygame/SandboxCharacter_CMC",
]:
    blueprint = unreal.EditorAssetLibrary.load_asset(path)
    default_object = unreal.get_default_object(blueprint.generated_class())
    tick = default_object.get_editor_property("primary_actor_tick")
    print("{} actor tick={}".format(path, tick))
    for name in ["tick_interval", "tick_group", "end_tick_group", "start_with_tick_enabled", "high_priority"]:
        try:
            print("  {}={}".format(name, tick.get_editor_property(name)))
        except Exception as error:
            print("  {} unavailable={}".format(name, error))
    for component in default_object.get_components_by_class(unreal.ActorComponent):
        if component.get_name() not in ["Mesh", "CharacterMesh0", "PhysicalMesh"]:
            continue
        component_tick = component.get_editor_property("primary_component_tick")
        print("  component {} enabled={} tick={}".format(
            component.get_name(), component.is_component_tick_enabled(), component_tick))
        for name in ["tick_interval", "tick_group", "end_tick_group", "start_with_tick_enabled", "high_priority"]:
            try:
                print("    {}={}".format(name, component_tick.get_editor_property(name)))
            except Exception as error:
                print("    {} unavailable={}".format(name, error))
