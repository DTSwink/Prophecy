import unreal


def get_template(path, component_name):
    blueprint = unreal.EditorAssetLibrary.load_asset(path)
    generated_class = blueprint.generated_class()
    default_object = unreal.get_default_object(generated_class)
    for component in default_object.get_components_by_class(unreal.PrimitiveComponent):
        if component.get_name() == component_name:
            return component
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    library = unreal.SubobjectDataBlueprintFunctionLibrary
    for handle in subsystem.k2_gather_subobject_data_for_blueprint(blueprint):
        data = subsystem.k2_find_subobject_data_from_handle(handle)
        component = library.get_object(data) or library.get_associated_object(data)
        if component and component.get_name().startswith(component_name):
            return component
    return None


channels = [
    unreal.CollisionChannel.ECC_WORLD_STATIC,
    unreal.CollisionChannel.ECC_WORLD_DYNAMIC,
    unreal.CollisionChannel.ECC_PAWN,
    unreal.CollisionChannel.ECC_PHYSICS_BODY,
    unreal.CollisionChannel.ECC_PROPHECY_AGENT_CAPSULE,
    unreal.CollisionChannel.ECC_PROPHECY_AGENT_LIMB,
]

for path in [
    "/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent",
    "/Game/_mygame/SandboxCharacter_CMC",
]:
    component = get_template(path, "PhysicalMesh")
    print("{} component={} profile={} enabled={} gravity={}".format(
        path,
        component,
        component.get_collision_profile_name(),
        component.get_collision_enabled(),
        component.get_editor_property("body_instance").enable_gravity,
    ))
    for channel in channels:
        print("  {}={}".format(channel, component.get_collision_response_to_channel(channel)))
