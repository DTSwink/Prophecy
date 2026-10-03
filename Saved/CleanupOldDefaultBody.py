import unreal

BODY = "/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody"

exists = unreal.EditorAssetLibrary.does_asset_exist(BODY)
print("BEFORE|asset_exists={}".format(exists))
if exists:
    data = unreal.EditorAssetLibrary.find_asset_data(BODY)
    print("ASSET_DATA|valid={}|class={}".format(
        data.is_valid(), data.asset_class_path.asset_name if data.is_valid() else "-"))
    deleted = unreal.EditorAssetLibrary.delete_asset(BODY)
    print("DELETE_RESULT|{}".format(deleted))
print("AFTER|asset_exists={}".format(unreal.EditorAssetLibrary.does_asset_exist(BODY)))
