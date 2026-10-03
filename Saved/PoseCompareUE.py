"""Compare reduced body vs mannequin bone poses at climb time 2.0s."""

import unreal

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for actor in subsystem.get_all_level_actors():
    label = actor.get_actor_label()
    if label.startswith("PoseProbe"):
        subsystem.destroy_actor(actor)

body_mesh = unreal.load_asset("/Game/_mygame/MetaHumans/SKM_test_UEFN78_Body")
mann_mesh = unreal.load_asset("/Game/_mygame/SKM_UEFN_Mannequin")
anim = unreal.load_asset(
    "/Game/Characters/UEFN_Mannequin/Animations/Traversal/Climb/"
    "M_Neutral_Traversal_Climb_Start_2_5_run_F_Lfoot"
)

for name, mesh, offset in (("Body", body_mesh, 0.0), ("Mann", mann_mesh, 200.0)):
    actor = subsystem.spawn_actor_from_class(
        unreal.SkeletalMeshActor,
        unreal.Vector(offset, 0.0, 0.0),
        unreal.Rotator(),
    )
    actor.set_actor_label("PoseProbe_" + name)
    comp = actor.skeletal_mesh_component
    comp.set_skeletal_mesh_asset(mesh)
    comp.set_update_animation_in_editor(True)
    comp.set_editor_property(
        "visibility_based_anim_tick_option",
        unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES,
    )
    comp.override_animation_data(anim, False, False, 2.0, 0.0)
    comp.set_position(2.0, False)

actors = subsystem.get_all_level_actors()
body = next(a for a in actors if a.get_actor_label() == "PoseProbe_Body")
mann = next(a for a in actors if a.get_actor_label() == "PoseProbe_Mann")

check = (
    "hand_r", "hand_l", "lowerarm_r", "lowerarm_l",
    "upperarm_r", "wrist", "head", "pelvis",
)
for bone in check:
    if bone not in [str(n) for n in body.skeletal_mesh_component.get_all_socket_names()]:
        continue
    bp = body.skeletal_mesh_component.get_socket_location(bone)
    mp = mann.skeletal_mesh_component.get_socket_location(bone)
    dist = ((bp.x - mp.x) ** 2 + (bp.y - mp.y) ** 2 + (bp.z - mp.z) ** 2) ** 0.5
    print("POSE_DELTA|{}|dist_cm={:.3f}".format(bone, dist))

for actor in (body, mann):
    subsystem.destroy_actor(actor)
print("POSE_COMPARE_DONE")
