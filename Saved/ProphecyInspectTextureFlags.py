import traceback
import unreal


TEXTURES = [
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Basecolor",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/Textures/T_Basecolor",
    "/Game/Prophecy/MetaHumans/Common/Lookdev_UHM/Common/Textures/Placeholders/T_Flat_Grey_C_VT",
    "/Game/Prophecy/MetaHumans/Common/Lookdev_UHM/Common/Textures/Placeholders/T_Flat_White_C_VT",
    "/Game/Prophecy/MetaHumans/Common/Lookdev_UHM/Common/Textures/Placeholders/T_Flat_Grey_C",
    "/Game/MetaHumans/Kellan/Face/Textures/T_HeadLOD1_BaseColor",
    "/Game/MetaHumans/Kellan/Body/Textures/T_Body_BaseColor",
]


def log(message):
    unreal.log(f"[ProphecyTextureFlags] {message}")


def path(value):
    if value is None:
        return "None"
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


def main():
    for texture_path in TEXTURES:
        texture = unreal.load_asset(texture_path)
        log(f"TEXTURE {texture_path}: {path(texture)} class={texture.get_class().get_name() if texture else 'None'}")
        if texture is None:
            continue

        for prop in (
            "virtual_texture_streaming",
            "srgb",
            "compression_settings",
            "lod_group",
            "source_color_settings",
            "color_space",
        ):
            try:
                log(f"  {prop}={texture.get_editor_property(prop)}")
            except Exception as exc:
                log(f"  {prop}=<{exc}>")


try:
    main()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
