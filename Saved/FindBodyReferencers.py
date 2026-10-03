import unreal

BODY = "/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody"

refs = unreal.EditorAssetLibrary.find_package_referencers_for_asset(BODY, load_assets_to_confirm=False)
print("PACKAGE_REFERENCERS|{}".format(list(refs)))

asset = unreal.load_asset(BODY)
print("LOAD|{}".format(bool(asset)))
if asset:
    referencers = unreal.EditorAssetLibrary.find_package_referencers_for_asset(BODY, load_assets_to_confirm=True)
    print("CONFIRMED_REFERENCERS|{}".format(list(referencers)))
