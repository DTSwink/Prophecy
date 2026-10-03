import traceback
import unreal


BODY_MATERIAL = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/Materials/MI_Body_Skin"
FACE_MATERIALS = [
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD1",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD3",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD5to7",
]

PLACEHOLDER = "/Game/Prophecy/MetaHumans/Common/Lookdev_UHM/Common/Textures/Placeholders"
SHARED_FACE_BASE = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Basecolor"
FACE_NORMAL = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Normal"
FACE_CAVITY = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Cavity"

BODY_RESTORE_TEXTURES = {
    "Basecolor": f"{PLACEHOLDER}/T_Flat_Grey_C",
    "Basecolor VT": f"{PLACEHOLDER}/T_Flat_Grey_C_VT",
    "Basecolor Original": f"{PLACEHOLDER}/T_Flat_White_C",
    "Basecolor Original VT": f"{PLACEHOLDER}/T_Flat_White_C_VT",
    "Basecolor Baked": f"{PLACEHOLDER}/T_Flat_Grey_C",
    "Basecolor Baked VT": f"{PLACEHOLDER}/T_Flat_Grey_C_VT",
    "Color_CHEST": f"{PLACEHOLDER}/T_Flat_Grey_C",
    "Normal": f"{PLACEHOLDER}/T_Flat_N",
    "Normal VT": f"{PLACEHOLDER}/T_Flat_N_VT",
    "Normal Original": f"{PLACEHOLDER}/T_Flat_N",
    "Normal Original VT": f"{PLACEHOLDER}/T_Flat_N_VT",
    "Normal Baked": f"{PLACEHOLDER}/T_Flat_N",
    "Normal Baked VT": f"{PLACEHOLDER}/T_Flat_N_VT",
    "Normal_CHEST": f"{PLACEHOLDER}/T_Flat_N",
    "Cavity": f"{PLACEHOLDER}/T_Flat_Black_M",
    "Cavity VT": f"{PLACEHOLDER}/T_Flat_Black_M_VT",
    "Cavity_Chest": f"{PLACEHOLDER}/T_Flat_Black_M",
}
BODY_RESTORE_SWITCHES = {
    "Basecolor Region Adjustments": False,
    "IsBody": True,
    "Use Virtual Texture": True,
    "Use Baked Material": False,
    "Bake ON": False,
    "Use Body Hider": True,
}

FACE_TEXTURES = {
    "Basecolor": SHARED_FACE_BASE,
    "Basecolor VT": SHARED_FACE_BASE,
    "Basecolor Original": SHARED_FACE_BASE,
    "Basecolor Original VT": SHARED_FACE_BASE,
    "Basecolor Baked": SHARED_FACE_BASE,
    "Basecolor Baked VT": SHARED_FACE_BASE,
    "Basecolor Animated cm1": f"{PLACEHOLDER}/T_Flat_White_C",
    "Basecolor Animated cm1 VT": f"{PLACEHOLDER}/T_Flat_White_C_VT",
    "Basecolor Animated cm2": f"{PLACEHOLDER}/T_Flat_White_C",
    "Basecolor Animated cm2 VT": f"{PLACEHOLDER}/T_Flat_White_C_VT",
    "Basecolor Animated cm3": f"{PLACEHOLDER}/T_Flat_White_C",
    "Basecolor Animated cm3 VT": f"{PLACEHOLDER}/T_Flat_White_C_VT",
    "Normal": FACE_NORMAL,
    "Normal VT": FACE_NORMAL,
    "Normal Original": FACE_NORMAL,
    "Normal Original VT": FACE_NORMAL,
    "Normal Baked": FACE_NORMAL,
    "Normal Baked VT": FACE_NORMAL,
    "Cavity": FACE_CAVITY,
    "Cavity VT": FACE_CAVITY,
}
FACE_SWITCHES = {
    "Basecolor Region Adjustments": False,
    "Use Normal Map": True,
    "Use Cavity": True,
    "Use Roughness Map as Base": False,
    "Use Virtual Texture": True,
    "Use Baked Material": False,
    "IsBody": False,
}


def log(message):
    unreal.log(f"[ProphecySharedHeadSkin] {message}")


def load_asset(asset_path):
    asset = unreal.load_asset(asset_path)
    if asset is None:
        raise RuntimeError(f"Missing asset: {asset_path}")
    return asset


def material_names(material):
    return {
        "texture": set(str(name) for name in unreal.MaterialEditingLibrary.get_texture_parameter_names(material)),
        "switch": set(str(name) for name in unreal.MaterialEditingLibrary.get_static_switch_parameter_names(material)),
        "scalar": set(str(name) for name in unreal.MaterialEditingLibrary.get_scalar_parameter_names(material)),
        "vector": set(str(name) for name in unreal.MaterialEditingLibrary.get_vector_parameter_names(material)),
    }


def set_texture(material, names, parameter_name, texture_path):
    if parameter_name not in names["texture"]:
        return
    texture = load_asset(texture_path)
    unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(material, parameter_name, texture)
    log(f"{material.get_name()}.{parameter_name} -> {texture.get_path_name()}")


def set_switch(material, names, parameter_name, value):
    if parameter_name not in names["switch"]:
        return
    unreal.MaterialEditingLibrary.set_material_instance_static_switch_parameter_value(material, parameter_name, value)
    log(f"{material.get_name()}.{parameter_name} -> {value}")


def set_scalar(material, names, parameter_name, value):
    if parameter_name not in names["scalar"]:
        return
    unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(material, parameter_name, value)
    log(f"{material.get_name()}.{parameter_name} -> {value:.3f}")


def set_vector(material, names, parameter_name, value):
    if parameter_name not in names["vector"]:
        return
    unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(material, parameter_name, value)
    log(f"{material.get_name()}.{parameter_name} -> ({value.r:.3f},{value.g:.3f},{value.b:.3f},{value.a:.3f})")


def restore_body_material():
    material = load_asset(BODY_MATERIAL)
    material.modify()
    names = material_names(material)
    for parameter_name, texture_path in BODY_RESTORE_TEXTURES.items():
        set_texture(material, names, parameter_name, texture_path)
    for parameter_name, value in BODY_RESTORE_SWITCHES.items():
        set_switch(material, names, parameter_name, value)
    for parameter_name in sorted(names["vector"]):
        if parameter_name.startswith("Basecolor Body"):
            set_vector(material, names, parameter_name, unreal.LinearColor(1.0, 1.0, 1.0, 1.0))
    unreal.MaterialEditingLibrary.update_material_instance(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)
    log(f"restored body material {material.get_path_name()}")


def patch_face_material(material_path):
    material = load_asset(material_path)
    material.modify()
    names = material_names(material)

    for parameter_name, texture_path in FACE_TEXTURES.items():
        set_texture(material, names, parameter_name, texture_path)
    for parameter_name, value in FACE_SWITCHES.items():
        set_switch(material, names, parameter_name, value)

    for parameter_name in sorted(names["scalar"]):
        if parameter_name.startswith("Specular Face"):
            set_scalar(material, names, parameter_name, 0.28)
        elif parameter_name.startswith("Roughness Face"):
            set_scalar(material, names, parameter_name, 0.82)

    set_scalar(material, names, "Fuzz Opacity", 0.16)
    set_scalar(material, names, "Fuzz Roughness Offset", 0.24)
    set_scalar(material, names, "Scatter Distance Base", 0.46)
    set_scalar(material, names, "CavityMapPower", 1.6)
    set_scalar(material, names, "FakeSpecAttenuation", 8.0)
    set_scalar(material, names, "MobileSpecStrength", 0.35)
    set_scalar(material, names, "FlattenNormal", 0.0)

    unreal.MaterialEditingLibrary.update_material_instance(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)
    log(f"patched face material {material.get_path_name()}")


def main():
    restore_body_material()
    for material_path in FACE_MATERIALS:
        patch_face_material(material_path)
    log("DONE")


try:
    main()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
