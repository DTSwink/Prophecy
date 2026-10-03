import unreal

for path in (
    "/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody",
    "/Game/_mygame/MetaHumans/BP_test_UEFNDirect",
):
    exists = unreal.EditorAssetLibrary.does_asset_exist(path)
    package_exists = unreal.EditorAssetLibrary.does_directory_exist(path)
    found = unreal.load_object(None, path)
    print("STATE|{}|asset_exists={}|loaded={}".format(path, exists, bool(found)))
