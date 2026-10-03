import unreal


ANIMATION_PATH = "/Game/Characters/UEFN_Mannequin/Animations/Traversal/Vault/M_Neutral_Traversal_Vault_1_0_run_F_Lfoot"
SAMPLE_TIME = 1.4

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
uefn_actor = next(actor for actor in actors if actor.get_actor_label() == "UEFN_Far_Audit")
meta_actor = next(actor for actor in actors if actor.get_actor_label() == "MetaHuman_Far_Audit")
uefn_component = uefn_actor.skeletal_mesh_component
body = next(component for component in meta_actor.get_components_by_class(unreal.SkeletalMeshComponent) if component.get_name() == "Body")
face = next(component for component in meta_actor.get_components_by_class(unreal.SkeletalMeshComponent) if component.get_name() == "Face")
animation = unreal.load_asset(ANIMATION_PATH)

for component in (uefn_component, body):
    instance = component.get_anim_instance()
    print("SET_SIGNATURE|{}|{}".format(component.get_name(), instance.set_animation_asset.__doc__))
    instance.set_animation_asset(animation, False, 0.0)
    instance.set_position(SAMPLE_TIME, False)
    component.set_update_animation_in_editor(True)
    if hasattr(component, "refresh_bone_transforms"):
        component.refresh_bone_transforms()

for component in (uefn_component, body, face):
    values = []
    for bone_name in ("pelvis", "hand_l", "hand_r", "head"):
        transform = component.get_socket_transform(bone_name, unreal.RelativeTransformSpace.RTS_COMPONENT)
        location = transform.translation
        values.append("{}=({:.3f},{:.3f},{:.3f})".format(bone_name, location.x, location.y, location.z))
    instance = component.get_anim_instance()
    print("POSE|{}|asset={}|{}".format(
        component.get_name(),
        instance.get_animation_asset().get_name() if instance and hasattr(instance, "get_animation_asset") and instance.get_animation_asset() else "None",
        "|".join(values),
    ))
