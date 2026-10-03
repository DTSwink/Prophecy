import unreal

skeleton = unreal.load_asset("/Game/_mygame/SK_UEFN_Mannequin.SK_UEFN_Mannequin")
mesh = unreal.load_asset("/Game/_mygame/SKM_UEFN_Mannequin")
body = unreal.load_asset("/Game/_mygame/MetaHumans/SKM_test_UEFN78_Body")
face = unreal.load_asset("/Game/_mygame/MetaHumans/SKM_test_UEFN78_Face")

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
probe = actor_subsystem.spawn_actor_from_class(
    unreal.SkeletalMeshActor, unreal.Vector(0.0, 0.0, -10000.0), unreal.Rotator())
component = probe.skeletal_mesh_component

for label, asset in (("mannequin", mesh), ("body78", body), ("face78", face)):
    component.set_skeletal_mesh_asset(asset)
    names = [str(n) for n in component.get_all_socket_names()]
    print("BONES|{}|{}".format(label, len(names)))

component.set_skeletal_mesh_asset(mesh)
names_mann = [str(n) for n in component.get_all_socket_names()]
component.set_skeletal_mesh_asset(body)
names_body = [str(n) for n in component.get_all_socket_names()]
extra = set(names_body) - set(names_mann)
print("BODY_EXTRA_BONES|{}".format(sorted(extra)))
actor_subsystem.destroy_actor(probe)
print("SKELETON_VERIFY_DONE")
