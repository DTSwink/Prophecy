import unreal


actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
uefn_actor = next(actor for actor in actors if actor.get_actor_label() == "UEFN_Far_Audit")
meta_actor = next(actor for actor in actors if actor.get_actor_label() == "MetaHuman_Far_Audit")
components = [uefn_actor.skeletal_mesh_component]
components.extend(meta_actor.get_components_by_class(unreal.SkeletalMeshComponent))

for component in components:
    values = []
    for bone_name in ("pelvis", "hand_l", "hand_r", "head"):
        transform = component.get_socket_transform(bone_name, unreal.RelativeTransformSpace.RTS_COMPONENT)
        location = transform.translation
        values.append("{}=({:.3f},{:.3f},{:.3f})".format(bone_name, location.x, location.y, location.z))
    instance = component.get_anim_instance()
    print("CURRENT|{}|asset={}|{}".format(
        component.get_name(),
        instance.get_animation_asset().get_name() if instance and hasattr(instance, "get_animation_asset") and instance.get_animation_asset() else "None",
        "|".join(values),
    ))
