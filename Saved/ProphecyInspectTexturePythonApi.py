import traceback
import unreal


TEXTURE_PATH = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Basecolor"


def log(message):
    unreal.log(f"[ProphecyTextureApi] {message}")


def main():
    texture = unreal.load_asset(TEXTURE_PATH)
    if texture is None:
        raise RuntimeError(f"Missing texture: {TEXTURE_PATH}")

    names = [name for name in dir(texture) if "source" in name.lower() or "platform" in name.lower() or "mip" in name.lower() or "pixel" in name.lower() or "import" in name.lower()]
    for name in sorted(names):
        log(name)
    log(f"class attrs count={len(dir(texture))}")


try:
    main()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
