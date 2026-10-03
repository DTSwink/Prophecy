import unreal

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
labels = {actor.get_actor_label(): actor for actor in actors}
for name in ("UEFN_Far_Audit", "MetaHuman_Far_Audit", "ProphecySourceHelperProbe"):
    print("ACTOR|{}|{}".format(name, "present" if name in labels else "MISSING"))

uefn_actor = labels.get("UEFN_Far_Audit")
if uefn_actor:
    comp = uefn_actor.skeletal_mesh_component
    print("UEFN_MESH|{}".format(comp.get_skinned_asset().get_path_name()))
    print("HAS_REFRESH|{}".format(hasattr(comp, "refresh_bone_transforms")))

body = unreal.load_asset("/Game/MetaHumans/test_UEFNExactFull/Body/SKM_test_UEFNFit_BodyMesh")
modifier = unreal.SkinWeightModifier()
modifier.set_skeletal_mesh(body)
max_influences = 0
for vertex_id in range(0, modifier.get_num_vertices(), 7):
    count = len([1 for v in modifier.get_vertex_weights(vertex_id).values() if float(v) > 0.0001])
    max_influences = max(max_influences, count)
print("SOURCE_MAX_INFLUENCES_SAMPLED|{}".format(max_influences))

anim = unreal.load_asset("/Game/Characters/UEFN_Mannequin/Animations/Traversal/Climb/M_Neutral_Traversal_Climb_Start_2_5_run_F_Lfoot")
print("ANIM_LEN|{}".format(unreal.AnimationLibrary.get_sequence_length(anim)))
