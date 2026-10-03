import unreal

path = "/Game/_mygame/MetaHumans/SKM_ScaleTest_Body"
if unreal.EditorAssetLibrary.does_asset_exist(path):
    print("DELETED|{}|{}".format(path, unreal.EditorAssetLibrary.delete_asset(path)))
print("CLEANUP_DONE")
