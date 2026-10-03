import os

import unreal


PROJECT_SAVED_DIR = unreal.Paths.project_saved_dir()
TEXTURE_DIR = "/Game/Prophecy/Textures"
GROUND_TEXTURE_SOURCE = os.path.join(PROJECT_SAVED_DIR, "ProphecyGrassGroundNoise.png")
GENERATOR_SCRIPT = os.path.join(PROJECT_SAVED_DIR, "ProphecyCreateGrassMaterials.py")


def set_if_present(obj, name, value):
    try:
        obj.set_editor_property(name, value)
    except Exception:
        pass


def force_reimport_ground_texture():
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", GROUND_TEXTURE_SOURCE)
    task.set_editor_property("destination_path", TEXTURE_DIR)
    task.set_editor_property("destination_name", "T_ProphecyGrassGroundNoise")
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    texture = unreal.EditorAssetLibrary.load_asset(f"{TEXTURE_DIR}/T_ProphecyGrassGroundNoise")
    if texture:
        set_if_present(texture, "srgb", True)
        unreal.EditorAssetLibrary.save_loaded_asset(texture)
    return texture


force_reimport_ground_texture()

with open(GENERATOR_SCRIPT, "r", encoding="utf-8") as handle:
    code = compile(handle.read(), GENERATOR_SCRIPT, "exec")
exec(code, {"__name__": "__main__"})

