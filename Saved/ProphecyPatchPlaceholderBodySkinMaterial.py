import traceback
import unreal


BODY_MATERIAL = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/Materials/MI_Body_Skin"
BODY_BASE = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/Textures/T_Basecolor"
BODY_NORMAL = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/Textures/T_Normal"
BODY_CAVITY = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/Textures/T_Cavity"

BODY_TEXTURES = {
    BODY_BASE: {
        "virtual_texture_streaming": True,
        "srgb": True,
        "compression_settings": unreal.TextureCompressionSettings.TC_DEFAULT,
        "lod_group": unreal.TextureGroup.TEXTUREGROUP_CHARACTER,
    },
    BODY_NORMAL: {
        "virtual_texture_streaming": True,
        "srgb": False,
        "compression_settings": unreal.TextureCompressionSettings.TC_NORMALMAP,
        "lod_group": unreal.TextureGroup.TEXTUREGROUP_CHARACTER_NORMAL_MAP,
    },
    BODY_CAVITY: {
        "virtual_texture_streaming": True,
        "srgb": False,
        "compression_settings": unreal.TextureCompressionSettings.TC_MASKS,
        "lod_group": unreal.TextureGroup.TEXTUREGROUP_CHARACTER_SPECULAR,
    },
}

TEXTURE_PARAMS = {
    "Basecolor": BODY_BASE,
    "Basecolor VT": BODY_BASE,
    "Basecolor Original": BODY_BASE,
    "Basecolor Original VT": BODY_BASE,
    "Basecolor Baked": BODY_BASE,
    "Basecolor Baked VT": BODY_BASE,
    "Color_CHEST": BODY_BASE,

    "Normal": BODY_NORMAL,
    "Normal VT": BODY_NORMAL,
    "Normal Original": BODY_NORMAL,
    "Normal Original VT": BODY_NORMAL,
    "Normal Baked": BODY_NORMAL,
    "Normal Baked VT": BODY_NORMAL,
    "Normal_CHEST": BODY_NORMAL,

    "Cavity": BODY_CAVITY,
    "Cavity VT": BODY_CAVITY,
    "Cavity_Chest": BODY_CAVITY,
}

SWITCH_PARAMS = {
    "Basecolor Region Adjustments": True,
    "IsBody": True,
    "Use Virtual Texture": True,
    "Use Baked Material": False,
    "Bake ON": False,
    "Use Body Hider": True,
}

REGION_VECTOR_DEFAULT = unreal.LinearColor(1.0, 1.20, 1.35, 1.0)
REGION_VECTOR_CHEST = unreal.LinearColor(1.05, 1.16, 1.24, 1.0)
REGION_VECTOR_LIMB = unreal.LinearColor(1.00, 1.38, 1.78, 1.0)
REGION_VECTOR_EXTREMITY = unreal.LinearColor(0.98, 1.32, 1.62, 1.0)


def log(message):
    unreal.log(f"[ProphecyPatchBodySkin] {message}")


def load_asset(asset_path):
    asset = unreal.load_asset(asset_path)
    if asset is None:
        raise RuntimeError(f"Missing asset: {asset_path}")
    return asset


def path(value):
    if value is None:
        return "None"
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


def patch_texture(texture_path, properties):
    texture = load_asset(texture_path)
    texture.modify()
    for property_name, value in properties.items():
        texture.set_editor_property(property_name, value)
    post_edit_change = getattr(texture, "post_edit_change", None)
    if post_edit_change is not None:
        post_edit_change()
    unreal.EditorAssetLibrary.save_loaded_asset(texture, only_if_is_dirty=False)
    log(
        f"texture {texture.get_name()} vt={texture.get_editor_property('virtual_texture_streaming')} "
        f"srgb={texture.get_editor_property('srgb')} "
        f"compression={texture.get_editor_property('compression_settings')} "
        f"lod={texture.get_editor_property('lod_group')}"
    )
    return texture


def set_texture_parameter(material, available_names, parameter_name, texture_path):
    if parameter_name not in available_names:
        return
    texture = load_asset(texture_path)
    unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
        material, parameter_name, texture
    )
    log(f"{material.get_name()}.{parameter_name} -> {path(texture)}")


def set_static_switch(material, available_names, parameter_name, value):
    if parameter_name not in available_names:
        return
    unreal.MaterialEditingLibrary.set_material_instance_static_switch_parameter_value(
        material, parameter_name, value
    )
    log(f"{material.get_name()}.{parameter_name} -> {value}")


def set_vector_parameter(material, available_names, parameter_name, value):
    if parameter_name not in available_names:
        return
    unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(
        material, parameter_name, value
    )
    log(
        f"{material.get_name()}.{parameter_name} -> "
        f"({value.r:.3f},{value.g:.3f},{value.b:.3f},{value.a:.3f})"
    )


def body_region_vector(parameter_name):
    lower = parameter_name.lower()
    if "chest" in lower or "neck" in lower:
        return REGION_VECTOR_CHEST
    if "hand" in lower or "foot" in lower or "palm" in lower or "sole" in lower or "nail" in lower:
        return REGION_VECTOR_EXTREMITY
    if "arm" in lower or "leg" in lower:
        return REGION_VECTOR_LIMB
    if lower == "basecolor body":
        return REGION_VECTOR_DEFAULT
    return None


def patch_body_material():
    for texture_path, properties in BODY_TEXTURES.items():
        patch_texture(texture_path, properties)

    material = load_asset(BODY_MATERIAL)
    material.modify()
    texture_names = set(str(name) for name in unreal.MaterialEditingLibrary.get_texture_parameter_names(material))
    switch_names = set(str(name) for name in unreal.MaterialEditingLibrary.get_static_switch_parameter_names(material))
    vector_names = set(str(name) for name in unreal.MaterialEditingLibrary.get_vector_parameter_names(material))

    for parameter_name, texture_path in TEXTURE_PARAMS.items():
        set_texture_parameter(material, texture_names, parameter_name, texture_path)

    for parameter_name, value in SWITCH_PARAMS.items():
        set_static_switch(material, switch_names, parameter_name, value)

    for parameter_name in sorted(vector_names):
        if not parameter_name.startswith("Basecolor Body"):
            continue
        value = body_region_vector(parameter_name)
        if value is not None:
            set_vector_parameter(material, vector_names, parameter_name, value)

    unreal.MaterialEditingLibrary.update_material_instance(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)
    log(f"saved {path(material)}")


def main():
    patch_body_material()
    log("DONE")


try:
    main()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
