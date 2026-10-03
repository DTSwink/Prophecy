import unreal

POSE_FIT_BODY = "/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody_PoseFitTest"
LABEL = "ProphecyPoseFitCompare"

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
existing = [a for a in actor_subsystem.get_all_level_actors() if a.get_actor_label() == LABEL]
if existing:
    actor = existing[0]
else:
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.SkeletalMeshActor, unreal.Vector(0.0, -300.0, 0.0), unreal.Rotator()
    )
    actor.set_actor_label(LABEL)
body = unreal.load_asset(POSE_FIT_BODY)
if not body:
    raise RuntimeError("Pose-fit body missing")
actor.skeletal_mesh_component.set_skeletal_mesh_asset(body)
print("COMPARE_ACTOR_READY|{}".format(actor.skeletal_mesh_component.get_skinned_asset().get_name()))
