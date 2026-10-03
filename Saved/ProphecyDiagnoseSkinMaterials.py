import traceback
import unreal


ASSETS = [
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD1",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD3",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD5to7",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/M_ProphecyGeneratedFaceSkin",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/Materials/MI_Body_Skin",
    "/Game/Prophecy/MetaHumans/Common/Materials/MI_Skin_Head_UI_LOD1_VT",
    "/Game/Prophecy/MetaHumans/Common/Materials/MI_Skin_Head_UI_LOD0_VT",
    "/Game/Prophecy/MetaHumans/Common/Materials/MI_Skin_Body_MHC_VT",
    "/Game/Prophecy/MetaHumans/Common/Lookdev_UHM/Skin/Materials/M_skin_unified_UI",
    "/Game/MetaHumans/Kellan/Face/Materials/MI_HeadSynthesized_Simplified_LOD1",
    "/Game/MetaHumans/Kellan/Body/Materials/MI_BodySynthesized_Simplified",
]

TEXTURES = [
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Basecolor",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Normal",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Cavity",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/Textures/T_Basecolor",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/Textures/T_Normal",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/Textures/T_Cavity",
]

KEYWORDS = (
    "base", "normal", "cavity", "rough", "spec", "opacity", "alpha", "mask",
    "hide", "visible", "texture", "virtual", "bake", "simple", "head", "body",
    "face", "neck", "chest", "torso", "cloth", "underwear", "region", "lod",
)


def log(message):
    unreal.log(f"[ProphecySkinDiag] {message}")


def path(value):
    if value is None:
        return "None"
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


def get_parent(asset):
    try:
        return asset.get_editor_property("parent")
    except Exception:
        return None


def short_value(value):
    if hasattr(value, "get_path_name"):
        return path(value)
    return str(value)


def wanted(name):
    lower = str(name).lower()
    return any(keyword in lower for keyword in KEYWORDS)


def log_parent_chain(asset):
    current = asset
    for depth in range(8):
        if current is None:
            break
        log(f"    parent_chain[{depth}] {path(current)} class={current.get_class().get_name()}")
        current = get_parent(current)


def inspect_material(asset_path):
    asset = unreal.load_asset(asset_path)
    log(f"ASSET {asset_path}: {path(asset)} class={asset.get_class().get_name() if asset else 'None'}")
    if asset is None:
        return
    log_parent_chain(asset)
    for prop in ("blend_mode", "shading_model", "two_sided", "used_with_skeletal_mesh"):
        try:
            log(f"    {prop}={asset.get_editor_property(prop)}")
        except Exception:
            pass

    groups = [
        ("texture", unreal.MaterialEditingLibrary.get_texture_parameter_names,
         unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value),
        ("scalar", unreal.MaterialEditingLibrary.get_scalar_parameter_names,
         unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value),
        ("switch", unreal.MaterialEditingLibrary.get_static_switch_parameter_names,
         unreal.MaterialEditingLibrary.get_material_instance_static_switch_parameter_value),
        ("vector", unreal.MaterialEditingLibrary.get_vector_parameter_names,
         unreal.MaterialEditingLibrary.get_material_instance_vector_parameter_value),
    ]
    for label, names_fn, value_fn in groups:
        try:
            names = list(names_fn(asset))
        except Exception as exc:
            log(f"    {label}_params failed: {exc}")
            continue
        shown = 0
        log(f"    {label}_params={len(names)}")
        for name in names:
            if not wanted(name):
                continue
            try:
                value = value_fn(asset, name)
            except Exception as exc:
                value = f"<{exc}>"
            log(f"      {label} {name} = {short_value(value)}")
            shown += 1
            if shown >= 80:
                log(f"      ...truncated {label}")
                break


def inspect_texture(texture_path):
    texture = unreal.load_asset(texture_path)
    log(f"TEXTURE {texture_path}: {path(texture)} class={texture.get_class().get_name() if texture else 'None'}")
    if texture is None:
        return
    for prop in (
        "virtual_texture_streaming", "compression_settings", "srgb",
        "lod_group", "address_x", "address_y", "never_stream",
    ):
        try:
            log(f"    {prop}={texture.get_editor_property(prop)}")
        except Exception as exc:
            log(f"    {prop}=<{exc}>")


def main():
    for texture_path in TEXTURES:
        inspect_texture(texture_path)
    for asset_path in ASSETS:
        inspect_material(asset_path)


try:
    main()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
