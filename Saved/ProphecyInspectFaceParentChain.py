import traceback
import unreal


ASSET_PATH = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD1"


def path(value):
    if value is None:
        return "None"
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


def log(message):
    unreal.log(f"[ProphecyFaceParentChain] {message}")


def main():
    material = unreal.load_asset(ASSET_PATH)
    depth = 0
    while material is not None and depth < 10:
        log(f"{depth}: {path(material)} class={material.get_class().get_name()}")
        try:
            material = material.get_editor_property("parent")
        except Exception as exc:
            log(f"{depth}: no parent property: {exc}")
            break
        depth += 1


try:
    main()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
