import unreal


texture = unreal.EditorAssetLibrary.load_asset("/Game/Prophecy/Textures/T_ProphecyDirtMossClean")
if not texture:
    raise RuntimeError("Could not load /Game/Prophecy/Textures/T_ProphecyDirtMossClean")

texture.set_editor_property("address_x", unreal.TextureAddress.TA_WRAP)
texture.set_editor_property("address_y", unreal.TextureAddress.TA_WRAP)
texture.set_editor_property("srgb", True)
unreal.EditorAssetLibrary.save_loaded_asset(texture)
print("PROPHECY_DIRT_MOSS_TEXTURE_WRAP_SET")

