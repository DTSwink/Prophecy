import unreal

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
print("ACTOR_COUNT|{}".format(len(actors)))
for actor in actors:
    label = actor.get_actor_label()
    components = actor.get_components_by_class(unreal.SkeletalMeshComponent)
    if components or "Audit" in label or "Probe" in label:
        meshes = ",".join(
            (c.get_skinned_asset().get_name() if c.get_skinned_asset() else "None")
            for c in components
        )
        print("ACTOR|{}|{}|{}".format(label, actor.get_class().get_name(), meshes))
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
print("WORLD|{}".format(world.get_name()))
