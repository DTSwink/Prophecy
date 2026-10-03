import unreal

POSE_FIT_BODY = "/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody_PoseFitTest"
UEFN_MESH = "/Game/_mygame/SKM_UEFN_Mannequin"
BASE = unreal.Vector(0.0, -2500.0, 0.0)

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = {a.get_actor_label(): a for a in actor_subsystem.get_all_level_actors()}

compare = actors.get("ProphecyPoseFitCompare")
if compare is None:
    compare = actor_subsystem.spawn_actor_from_class(unreal.SkeletalMeshActor, BASE, unreal.Rotator())
    compare.set_actor_label("ProphecyPoseFitCompare")
compare.set_actor_location(BASE, False, False)
compare.skeletal_mesh_component.set_skeletal_mesh_asset(unreal.load_asset(POSE_FIT_BODY))

reference = actors.get("ProphecyUEFNCompare")
if reference is None:
    reference = actor_subsystem.spawn_actor_from_class(
        unreal.SkeletalMeshActor, BASE + unreal.Vector(0.0, 150.0, 0.0), unreal.Rotator()
    )
    reference.set_actor_label("ProphecyUEFNCompare")
reference.set_actor_location(BASE + unreal.Vector(0.0, 150.0, 0.0), False, False)
reference.skeletal_mesh_component.set_skeletal_mesh_asset(unreal.load_asset(UEFN_MESH))

print("ISOLATED_READY|compare={}|reference={}".format(
    compare.get_actor_location(), reference.get_actor_location()))
