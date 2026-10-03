import unreal

body = unreal.load_asset("/Game/_mygame/MetaHumans/SKM_test_UEFN78_Body")
skel = unreal.load_asset("/Game/_mygame/SK_UEFN_Mannequin.SK_UEFN_Mannequin")
mann = unreal.load_asset("/Game/_mygame/SKM_UEFN_Mannequin")

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for label in ("RefPoseProbe",):
    for actor in subsystem.get_all_level_actors():
        if actor.get_actor_label().startswith(label):
            subsystem.destroy_actor(actor)

for name, mesh in (("Body78", body), ("Mann", mann)):
    actor = subsystem.spawn_actor_from_class(
        unreal.SkeletalMeshActor, unreal.Vector(0.0, 0.0, -5000.0), unreal.Rotator())
    actor.set_actor_label("RefPoseProbe_" + name)
    actor.skeletal_mesh_component.set_skeletal_mesh_asset(mesh)

actors = subsystem.get_all_level_actors()
body_actor = next(a for a in actors if a.get_actor_label() == "RefPoseProbe_Body78")
mann_actor = next(a for a in actors if a.get_actor_label() == "RefPoseProbe_Mann")

check = (
    "pelvis", "spine_03", "spine_05", "head", "clavicle_r",
    "upperarm_r", "lowerarm_r", "hand_r", "index_03_r",
)
for bone in check:
    bp = body_actor.skeletal_mesh_component.get_socket_location(bone)
    mp = mann_actor.skeletal_mesh_component.get_socket_location(bone)
    dist = ((bp.x - mp.x) ** 2 + (bp.y - mp.y) ** 2 + (bp.z - mp.z) ** 2) ** 0.5
    print("REF_DELTA|{}|dist_cm={:.3f}".format(bone, dist))

for actor in (body_actor, mann_actor):
    subsystem.destroy_actor(actor)
print("REF_POSE_CHECK_DONE")
