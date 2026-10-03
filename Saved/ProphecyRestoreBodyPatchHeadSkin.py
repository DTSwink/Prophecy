import traceback
import unreal


BODY_MATERIAL = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/Materials/MI_Body_Skin"
FACE_MATERIALS = [
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD1",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD3",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD5to7",
]

PLACEHOLDER = "/Game/Prophecy/MetaHumans/Common/Lookdev_UHM/Common/Textures/Placeholders"
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

HEAD_SOURCE_TEXTURES = {
    "/Game/MetaHumans/Kellan/Face/Textures/T_HeadLOD1_BaseColor": {
        "dst": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_BaseColor",
        "srgb": True,
        "compression": unreal.TextureCompressionSettings.TC_DEFAULT,
        "lod": unreal.TextureGroup.TEXTUREGROUP_CHARACTER,
    },
    "/Game/MetaHumans/Kellan/Face/Textures/T_HeadLOD1_Normal": {
        "dst": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_Normal",
        "srgb": False,
        "compression": unreal.TextureCompressionSettings.TC_NORMALMAP,
        "lod": unreal.TextureGroup.TEXTUREGROUP_CHARACTER_NORMAL_MAP,
    },
    "/Game/MetaHumans/Kellan/Face/Textures/T_HeadLOD1_BaseColor_CM1": {
        "dst": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_BaseColor_CM1",
        "srgb": True,
        "compression": unreal.TextureCompressionSettings.TC_DEFAULT,
        "lod": unreal.TextureGroup.TEXTUREGROUP_CHARACTER,
    },
    "/Game/MetaHumans/Kellan/Face/Textures/T_HeadLOD1_BaseColor_CM2": {
        "dst": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_BaseColor_CM2",
        "srgb": True,
        "compression": unreal.TextureCompressionSettings.TC_DEFAULT,
        "lod": unreal.TextureGroup.TEXTUREGROUP_CHARACTER,
    },
    "/Game/MetaHumans/Kellan/Face/Textures/T_HeadLOD1_BaseColor_CM3": {
        "dst": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_BaseColor_CM3",
        "srgb": True,
        "compression": unreal.TextureCompressionSettings.TC_DEFAULT,
        "lod": unreal.TextureGroup.TEXTUREGROUP_CHARACTER,
    },
    "/Game/MetaHumans/Kellan/Face/Textures/T_HeadLOD1_Normal_WM1": {
        "dst": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_Normal_WM1",
        "srgb": False,
        "compression": unreal.TextureCompressionSettings.TC_NORMALMAP,
        "lod": unreal.TextureGroup.TEXTUREGROUP_CHARACTER_NORMAL_MAP,
    },
    "/Game/MetaHumans/Kellan/Face/Textures/T_HeadLOD1_Normal_WM2": {
        "dst": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_Normal_WM2",
        "srgb": False,
        "compression": unreal.TextureCompressionSettings.TC_NORMALMAP,
        "lod": unreal.TextureGroup.TEXTUREGROUP_CHARACTER_NORMAL_MAP,
    },
    "/Game/MetaHumans/Kellan/Face/Textures/T_HeadLOD1_Normal_WM3": {
        "dst": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_Normal_WM3",
        "srgb": False,
        "compression": unreal.TextureCompressionSettings.TC_NORMALMAP,
        "lod": unreal.TextureGroup.TEXTUREGROUP_CHARACTER_NORMAL_MAP,
    },
    "/Game/MetaHumans/Common/Face/Textures/Simplified/T_MH_BentNormal_Reduced_AO": {
        "dst": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHead_CavityAO",
        "srgb": False,
        "compression": unreal.TextureCompressionSettings.TC_MASKS,
        "lod": unreal.TextureGroup.TEXTUREGROUP_CHARACTER_SPECULAR,
    },
}

HEAD_TEXTURE_PARAMS = {
    "Basecolor": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_BaseColor",
    "Basecolor VT": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_BaseColor",
    "Basecolor Original": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_BaseColor",
    "Basecolor Original VT": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_BaseColor",
    "Basecolor Baked": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_BaseColor",
    "Basecolor Baked VT": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_BaseColor",
    "Basecolor Animated cm1": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_BaseColor_CM1",
    "Basecolor Animated cm1 VT": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_BaseColor_CM1",
    "Basecolor Animated cm2": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_BaseColor_CM2",
    "Basecolor Animated cm2 VT": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_BaseColor_CM2",
    "Basecolor Animated cm3": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_BaseColor_CM3",
    "Basecolor Animated cm3 VT": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_BaseColor_CM3",
    "Normal": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_Normal",
    "Normal VT": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_Normal",
    "Normal Original": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_Normal",
    "Normal Original VT": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_Normal",
    "Normal Baked": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_Normal",
    "Normal Baked VT": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_Normal",
    "Normal Animated wm1": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_Normal_WM1",
    "Normal Animated wm1 VT": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_Normal_WM1",
    "Normal Animated wm2": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_Normal_WM2",
    "Normal Animated wm2 VT": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_Normal_WM2",
    "Normal Animated wm3": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_Normal_WM3",
    "Normal Animated wm3 VT": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHeadLOD1_Normal_WM3",
    "Cavity": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHead_CavityAO",
    "Cavity VT": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_SourceHead_CavityAO",
}
HEAD_SWITCHES = {
    "Use Normal Map": True,
    "Use Cavity": True,
    "Use Roughness Map as Base": True,
    "Use Virtual Texture": True,
    "Use Baked Material": False,
    "IsBody": False,
}


def log(message):
    unreal.log(f"[ProphecyHeadSkinFix] {message}")


def load_asset(asset_path):
    asset = unreal.load_asset(asset_path)
    if asset is None:
        raise RuntimeError(f"Missing asset: {asset_path}")
    return asset


def path(value):
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


def set_texture_properties(texture, srgb, compression, lod):
    texture.modify()
    texture.set_editor_property("virtual_texture_streaming", True)
    texture.set_editor_property("srgb", srgb)
    texture.set_editor_property("compression_settings", compression)
    texture.set_editor_property("lod_group", lod)
    post_edit_change = getattr(texture, "post_edit_change", None)
    if post_edit_change is not None:
        post_edit_change()
    unreal.EditorAssetLibrary.save_loaded_asset(texture, only_if_is_dirty=False)


def ensure_texture_copy(source_path, copy_info):
    dst = copy_info["dst"]
    texture = unreal.load_asset(dst)
    if texture is None:
        if not unreal.EditorAssetLibrary.duplicate_asset(source_path, dst):
            raise RuntimeError(f"Could not duplicate {source_path} to {dst}")
        texture = load_asset(dst)
        log(f"duplicated {source_path} -> {dst}")
    set_texture_properties(texture, copy_info["srgb"], copy_info["compression"], copy_info["lod"])
    log(f"texture ready {path(texture)} vt={texture.get_editor_property('virtual_texture_streaming')}")
    return texture


def material_names(material):
    return {
        "texture": set(str(name) for name in unreal.MaterialEditingLibrary.get_texture_parameter_names(material)),
        "switch": set(str(name) for name in unreal.MaterialEditingLibrary.get_static_switch_parameter_names(material)),
        "scalar": set(str(name) for name in unreal.MaterialEditingLibrary.get_scalar_parameter_names(material)),
        "vector": set(str(name) for name in unreal.MaterialEditingLibrary.get_vector_parameter_names(material)),
    }


def set_texture_parameter(material, names, parameter_name, texture_path):
    if parameter_name not in names["texture"]:
        return False
    texture = load_asset(texture_path)
    unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(material, parameter_name, texture)
    log(f"{material.get_name()}.{parameter_name} -> {path(texture)}")
    return True


def set_switch_parameter(material, names, parameter_name, value):
    if parameter_name not in names["switch"]:
        return False
    unreal.MaterialEditingLibrary.set_material_instance_static_switch_parameter_value(material, parameter_name, value)
    log(f"{material.get_name()}.{parameter_name} -> {value}")
    return True


def set_scalar_parameter(material, names, parameter_name, value):
    if parameter_name not in names["scalar"]:
        return False
    unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(material, parameter_name, value)
    log(f"{material.get_name()}.{parameter_name} -> {value:.3f}")
    return True


def set_vector_parameter(material, names, parameter_name, value):
    if parameter_name not in names["vector"]:
        return False
    unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(material, parameter_name, value)
    log(f"{material.get_name()}.{parameter_name} -> ({value.r:.3f},{value.g:.3f},{value.b:.3f},{value.a:.3f})")
    return True


def restore_body_material():
    material = load_asset(BODY_MATERIAL)
    material.modify()
    names = material_names(material)

    for parameter_name, texture_path in BODY_RESTORE_TEXTURES.items():
        set_texture_parameter(material, names, parameter_name, texture_path)
    for parameter_name, value in BODY_RESTORE_SWITCHES.items():
        set_switch_parameter(material, names, parameter_name, value)
    for parameter_name in sorted(names["vector"]):
        if parameter_name.startswith("Basecolor Body"):
            set_vector_parameter(material, names, parameter_name, unreal.LinearColor(1.0, 1.0, 1.0, 1.0))

    unreal.MaterialEditingLibrary.update_material_instance(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)
    log(f"restored body material {path(material)}")


def patch_face_material(material_path):
    material = load_asset(material_path)
    material.modify()
    names = material_names(material)

    for parameter_name, texture_path in HEAD_TEXTURE_PARAMS.items():
        set_texture_parameter(material, names, parameter_name, texture_path)
    for parameter_name, value in HEAD_SWITCHES.items():
        set_switch_parameter(material, names, parameter_name, value)

    for parameter_name in sorted(names["scalar"]):
        if parameter_name.startswith("Specular Face"):
            set_scalar_parameter(material, names, parameter_name, 0.32)
        elif parameter_name.startswith("Roughness Face"):
            set_scalar_parameter(material, names, parameter_name, 0.78)

    set_scalar_parameter(material, names, "Fuzz Opacity", 0.25)
    set_scalar_parameter(material, names, "Fuzz Roughness Offset", 0.25)
    set_scalar_parameter(material, names, "Scatter Distance Base", 0.42)
    set_scalar_parameter(material, names, "CavityMapPower", 2.2)
    set_scalar_parameter(material, names, "FakeSpecAttenuation", 7.5)
    set_scalar_parameter(material, names, "MobileSpecStrength", 0.35)
    set_scalar_parameter(material, names, "FlattenNormal", 0.0)

    unreal.MaterialEditingLibrary.update_material_instance(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)
    log(f"patched face material {path(material)}")


def main():
    restore_body_material()
    for source_path, copy_info in HEAD_SOURCE_TEXTURES.items():
        ensure_texture_copy(source_path, copy_info)
    for material_path in FACE_MATERIALS:
        patch_face_material(material_path)
    log("DONE")


try:
    main()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
