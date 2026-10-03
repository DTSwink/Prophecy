import unreal


actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
for label in ("UEFN_Far_Audit", "MetaHuman_Far_Audit"):
    actor = next(actor for actor in actors if actor.get_actor_label() == label)
    location = actor.get_actor_location()
    rotation = actor.get_actor_rotation()
    print("ACTOR_SETUP|{}|class={}|loc=({:.3f},{:.3f},{:.3f})|rot=({:.3f},{:.3f},{:.3f})|tags={}".format(
        label, actor.get_class().get_name(), location.x, location.y, location.z,
        rotation.pitch, rotation.yaw, rotation.roll, list(actor.tags)))
    for component in actor.get_components_by_class(unreal.ActorComponent):
        if isinstance(component, unreal.SkeletalMeshComponent):
            parent = component.get_attach_parent()
            try:
                predicted = component.get_editor_property("predicted_lod_level")
            except Exception:
                predicted = "unavailable"
            print("SKELETAL_SETUP|{}|parent={}|anim_class={}|forced={}|predicted={}".format(
                component.get_name(), parent.get_name() if parent else "None",
                component.anim_class.get_name() if component.anim_class else "None",
                component.forced_lod_model, predicted))
        elif "LODSync" in component.get_name() or component.get_class().get_name() == "LODSyncComponent":
            values = []
            for prop in ("forced_lod", "num_lods", "min_lod"):
                try:
                    values.append("{}={}".format(prop, component.get_editor_property(prop)))
                except Exception:
                    pass
            print("LOD_SETUP|{}|{}".format(component.get_name(), "|".join(values)))
