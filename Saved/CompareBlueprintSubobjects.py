import unreal


def safe(call, default="<unavailable>"):
    try:
        return call()
    except Exception as error:
        return "{} ({})".format(default, error)


subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
library = unreal.SubobjectDataBlueprintFunctionLibrary
for path in [
    "/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent",
    "/Game/_mygame/SandboxCharacter_CMC",
]:
    blueprint = unreal.EditorAssetLibrary.load_asset(path)
    print("\nBLUEPRINT {}".format(path))
    handles = subsystem.k2_gather_subobject_data_for_blueprint(blueprint)
    print("HANDLES {}".format(len(handles)))
    for handle in handles:
        data = subsystem.k2_find_subobject_data_from_handle(handle)
        obj = library.get_object(data)
        if not obj:
            obj = library.get_associated_object(data)
        if not obj:
            continue
        name = obj.get_name()
        if name not in [
            "PhysicalMesh", "Mesh", "CharacterMesh0", "Capsule", "CapsuleComponent",
            "CollisionCylinder", "CharMoveComp", "PhysicalAnimation",
        ] and not any(token in name.lower() for token in ["physical", "skeletalmesh"]):
            continue
        print("  {} class={} object={}".format(name, obj.get_class().get_name(), obj))
        if isinstance(obj, unreal.SceneComponent):
            print("    parent={} rel_location={} rel_rotation={} rel_scale={}".format(
                safe(lambda o=obj: o.get_attach_parent().get_name() if o.get_attach_parent() else None),
                safe(lambda o=obj: o.get_editor_property("relative_location")),
                safe(lambda o=obj: o.get_editor_property("relative_rotation")),
                safe(lambda o=obj: o.get_editor_property("relative_scale3d"))))
        if isinstance(obj, unreal.PrimitiveComponent):
            print("    collision_profile={} collision_enabled={} object_type={} gravity={} sim={}".format(
                safe(lambda o=obj: o.get_collision_profile_name()),
                safe(lambda o=obj: o.get_collision_enabled()),
                safe(lambda o=obj: o.get_collision_object_type()),
                safe(lambda o=obj: o.get_editor_property("enable_gravity")),
                safe(lambda o=obj: o.is_simulating_physics())))
        for property_name in [
            "primary_component_tick", "skeletal_mesh_asset", "physics_asset_override",
            "animation_mode", "anim_class", "enable_update_rate_optimizations",
            "visibility_based_anim_tick_option", "update_joints_from_animation",
            "blend_physics", "physics_transform_update_mode", "kinematic_bones_update_type",
            "defer_kinematic_bone_update", "component_use_fixed_skel_bounds",
            "disable_post_process_blueprint", "body_instance",
        ]:
            value = safe(lambda o=obj, p=property_name: o.get_editor_property(p))
            print("    {}={}".format(property_name, value))
