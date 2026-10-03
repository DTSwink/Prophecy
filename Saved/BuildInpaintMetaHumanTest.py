import unreal


SOURCE_BODY = "/Game/MetaHumans/test_UEFNExactFull/Body/SKM_test_UEFNFit_BodyMesh"
UEFN_MESH = "/Game/_mygame/SKM_UEFN_Mannequin"
SOURCE_BLUEPRINT = "/Game/MetaHumans/test_UEFNExactFull/BP_test_UEFNExactFull"
FACE_ANIM = "/Game/MetaHumans/Common/Face/Face_AnimBP"
BODY_OUTPUT = "/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody_InpaintTest"
BLUEPRINT_OUTPUT = "/Game/_mygame/MetaHumans/BP_test_UEFNDirect_InpaintTest"

for path in (BLUEPRINT_OUTPUT, BODY_OUTPUT):
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        if not unreal.EditorAssetLibrary.delete_asset(path):
            raise RuntimeError("Could not delete existing test asset: " + path)

unreal.SystemLibrary.execute_console_command(
    None,
    "Prophecy.MetaHuman.BuildUEFNBody {} {} {}".format(
        SOURCE_BODY, UEFN_MESH, BODY_OUTPUT
    ),
)
body = unreal.load_asset(BODY_OUTPUT)
uefn = unreal.load_asset(UEFN_MESH)
if not isinstance(body, unreal.SkeletalMesh) or not isinstance(uefn, unreal.SkeletalMesh):
    raise RuntimeError("Could not build/load Inpaint test body")

source_dynamic = unreal.DynamicMesh()
target_dynamic = unreal.DynamicMesh()
asset_options = unreal.GeometryScriptCopyMeshFromAssetOptions()
read_lod = unreal.GeometryScriptMeshReadLOD(
    lod_type=unreal.GeometryScriptLODType.SOURCE_MODEL,
    lod_index=0,
)

_, source_outcome = unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(
    uefn, source_dynamic, asset_options, read_lod
)
_, target_outcome = unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(
    body, target_dynamic, asset_options, read_lod
)
if source_outcome != unreal.GeometryScriptOutcomePins.SUCCESS:
    raise RuntimeError("Could not extract UEFN source dynamic mesh")
if target_outcome != unreal.GeometryScriptOutcomePins.SUCCESS:
    raise RuntimeError("Could not extract MetaHuman target dynamic mesh")

transfer_options = unreal.GeometryScriptTransferBoneWeightsOptions(
    transfer_method=unreal.TransferBoneWeightsMethod.INPAINT_WEIGHTS,
    output_target_mesh_bones=unreal.OutputTargetMeshBones.TARGET_BONES,
    radius_percentage=0.025,
    normal_threshold=30.0,
    layered_mesh_support=False,
    num_smoothing_iterations=5,
    smoothing_strength=0.25,
)
unreal.GeometryScript_BoneWeights.transfer_bone_weights_from_mesh(
    source_dynamic,
    target_dynamic,
    transfer_options,
)

write_options = unreal.GeometryScriptCopySkinWeightProfileToAssetOptions(
    overwrite_existing_profile=True,
    emit_transaction=False,
    defer_mesh_post_edit_change=False,
)
write_lod = unreal.GeometryScriptMeshWriteLOD(lod_index=0)
_, write_outcome = unreal.GeometryScript_AssetUtils.copy_skin_weight_profile_to_skeletal_mesh(
    target_dynamic,
    body,
    unreal.Name(""),
    unreal.Name("Default"),
    write_options,
    write_lod,
)
if write_outcome != unreal.GeometryScriptOutcomePins.SUCCESS:
    raise RuntimeError("Could not write Inpaint skin weights to test body")

mesh_editor = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
if not mesh_editor.remove_lods(body, [1, 2]):
    raise RuntimeError("Could not remove lower test LODs")
if not mesh_editor.regenerate_lod(body, 3, True, False):
    raise RuntimeError("Could not regenerate test LODs")
unreal.EditorAssetLibrary.save_loaded_asset(body, only_if_is_dirty=False)

unreal.SystemLibrary.execute_console_command(
    None,
    "Prophecy.MetaHuman.BuildUEFNBlueprint {} {} {} {}".format(
        SOURCE_BLUEPRINT, BODY_OUTPUT, FACE_ANIM, BLUEPRINT_OUTPUT
    ),
)
blueprint = unreal.load_asset(BLUEPRINT_OUTPUT)
if not isinstance(blueprint, unreal.Blueprint):
    raise RuntimeError("Could not build Inpaint test Blueprint")
unreal.EditorAssetLibrary.save_loaded_asset(blueprint, only_if_is_dirty=False)

print(
    "INPAINT_TEST_BUILT|body={}|blueprint={}|radius_pct=0.025|normal_deg=30|smooth=5x0.25".format(
        body.get_path_name(), blueprint.get_path_name()
    )
)
