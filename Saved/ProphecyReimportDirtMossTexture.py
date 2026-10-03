import os

import unreal


SAVED_DIR = unreal.Paths.project_saved_dir()
TEXTURE_DIR = "/Game/Prophecy/Textures"
SOURCE_PATH = os.path.join(SAVED_DIR, "ProphecyDirtMossClean.png")
ASSET_NAME = "T_ProphecyDirtMossClean"


def set_if_present(obj, name, value):
    try:
        obj.set_editor_property(name, value)
    except Exception:
        pass


task = unreal.AssetImportTask()
task.set_editor_property("filename", SOURCE_PATH)
task.set_editor_property("destination_path", TEXTURE_DIR)
task.set_editor_property("destination_name", ASSET_NAME)
task.set_editor_property("automated", True)
task.set_editor_property("replace_existing", True)
task.set_editor_property("save", True)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

texture = unreal.EditorAssetLibrary.load_asset(f"{TEXTURE_DIR}/{ASSET_NAME}")
if texture:
    set_if_present(texture, "srgb", True)
    set_if_present(texture, "address_x", unreal.TextureAddress.TA_WRAP)
    set_if_present(texture, "address_y", unreal.TextureAddress.TA_WRAP)
    unreal.EditorAssetLibrary.save_loaded_asset(texture)

