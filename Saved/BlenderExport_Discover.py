import unreal

registry = unreal.AssetRegistryHelpers.get_asset_registry()

print("=== assets under /Game/MetaHumans/test_UEFNExactFull ===")
for data in registry.get_assets_by_path("/Game/MetaHumans/test_UEFNExactFull", recursive=True):
    cls = str(data.asset_class_path.asset_name)
    if cls in ("SkeletalMesh", "Skeleton", "Blueprint"):
        print("ASSET|{}|{}".format(cls, data.package_name))

print("=== key asset existence ===")
for path in (
    "/Game/MetaHumans/test_UEFNExactFull/Body/SKM_test_UEFNFit_BodyMesh",
    "/Game/_mygame/SKM_UEFN_Mannequin",
    "/Game/_mygame/SK_UEFN_Mannequin",
    "/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody",
    "/Game/_mygame/MetaHumans/BP_test_UEFNDirect",
    "/Game/Characters/UEFN_Mannequin/Animations/Traversal/Climb/M_Neutral_Traversal_Climb_Start_2_5_run_F_Lfoot",
    "/Game/Characters/UEFN_Mannequin/Animations/Traversal/Catch/Cliff/M_Neutral_Traversal_Catch_Cliff_high_stand",
    "/Game/Characters/UEFN_Mannequin/Animations/Sprint/M_Neutral_Sprint_Loop_F_L_20",
    "/Game/Characters/UEFN_Mannequin/Animations/Slide/M_Neutral_Slide_KneesOut_Loop",
    "/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Neutral_Stand_Idle_Loop",
):
    print("EXISTS|{}|{}".format(unreal.EditorAssetLibrary.does_asset_exist(path), path))
print("DISCOVERY_DONE")
