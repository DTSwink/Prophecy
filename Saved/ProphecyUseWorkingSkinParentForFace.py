import traceback
import unreal


FACE_MATERIALS = [
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD1",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD3",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD5to7",
]

WORKING_SKIN_PARENT = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/Materials/MI_Body_Skin"

TEXTURE_PARAMS = {
    "Basecolor": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Basecolor",
    "Basecolor VT": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Basecolor",
    "Basecolor Original": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Basecolor",
    "Basecolor Original VT": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Basecolor",
    "Basecolor Baked": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Basecolor",
    "Basecolor Baked VT": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Basecolor",
    "Normal": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Normal",
    "Normal VT": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Normal",
    "Normal Original": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Normal",
    "Normal Original VT": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Normal",
    "Normal Baked": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Normal",
    "Normal Baked VT": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Normal",
    "Cavity": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Cavity",
    "Cavity VT": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Cavity",
}


def log(message):
    unreal.log(f"[ProphecyWorkingSkinParent] {message}")


def load_asset(asset_path):
    asset = unreal.load_asset(asset_path)
    if asset is None:
        raise RuntimeError(f"Missing asset: {asset_path}")
    return asset


def main():
    parent = load_asset(WORKING_SKIN_PARENT)
    for material_path in FACE_MATERIALS:
        material = load_asset(material_path)

        try:
            unreal.MaterialEditingLibrary.set_material_instance_parent(material, parent)
        except Exception:
            material.set_editor_property("parent", parent)
        log(f"{material.get_name()}.parent -> {parent.get_path_name()}")

        texture_names = set(str(name) for name in unreal.MaterialEditingLibrary.get_texture_parameter_names(material))
        for parameter_name, texture_path in TEXTURE_PARAMS.items():
            if parameter_name not in texture_names:
                continue
            texture = load_asset(texture_path)
            unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
                material, parameter_name, texture
            )
            log(f"{material.get_name()}.{parameter_name} -> {texture.get_name()}")

        unreal.MaterialEditingLibrary.update_material_instance(material)
        unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)

    log("DONE")


try:
    main()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
