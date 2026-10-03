import traceback
import unreal


MATERIAL_PATH = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD1"
KEYWORDS = (
    "color",
    "colour",
    "base",
    "skin",
    "tint",
    "tone",
    "scatter",
    "override",
    "simple",
    "albedo",
    "diffuse",
)


def log(message):
    unreal.log(f"[ProphecyFaceVectors] {message}")


def main():
    material = unreal.load_asset(MATERIAL_PATH)
    if material is None:
        raise RuntimeError(f"Missing material: {MATERIAL_PATH}")

    names = unreal.MaterialEditingLibrary.get_vector_parameter_names(material)
    for name in names:
        name_string = str(name)
        if not any(keyword in name_string.lower() for keyword in KEYWORDS):
            continue
        try:
            value = unreal.MaterialEditingLibrary.get_material_instance_vector_parameter_value(material, name)
            log(f"{name_string}: r={value.r:.4f} g={value.g:.4f} b={value.b:.4f} a={value.a:.4f}")
        except Exception as exc:
            log(f"{name_string}: failed {exc}")


try:
    main()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
