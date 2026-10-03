import traceback
import unreal


FACE_MATERIALS = [
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD1",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD3",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD5to7",
]

STATIC_SWITCH_PARAMS = {
    "Use Virtual Texture": False,
    "Use Baked Material": False,
    "Bake ON": False,
    "UseSimpleShading": True,
    "Use Face Region Masks": False,
    "Use Region Adjustments": False,
    "Use Global Adjustments": False,
    "Use Global Adjustments Post-Bake": False,
    "Use Fuzz": False,
    "Use Makeup": False,
    "Use Wet": False,
    "Use Cavity": False,
    "Use Animated Maps": False,
    "Use Delta Maps": False,
    "Use Mipmap Mask": False,
    "Use Micro Skin Details": False,
    "Use Bent Normal": False,
    "Use Material AO": False,
    "Use Extra Shadowing": False,
    "Use Scatter Compensation": False,
    "Use Skin Accents": False,
    "Use Freckles": False,
    "Use Hair Mask": False,
    "Use Baked Grooms": False,
    "Use Pre-Baked Groom Texture Set": False,
}

SCALAR_PARAMS = {
    "Use Texture Override": 1.0,
}


def log(message):
    unreal.log(f"[ProphecyFaceSimpleBranch] {message}")


def main():
    for material_path in FACE_MATERIALS:
        material = unreal.load_asset(material_path)
        if material is None:
            raise RuntimeError(f"Missing material: {material_path}")

        switch_names = set(str(name) for name in unreal.MaterialEditingLibrary.get_static_switch_parameter_names(material))
        scalar_names = set(str(name) for name in unreal.MaterialEditingLibrary.get_scalar_parameter_names(material))

        for parameter_name, value in STATIC_SWITCH_PARAMS.items():
            if parameter_name not in switch_names:
                continue
            unreal.MaterialEditingLibrary.set_material_instance_static_switch_parameter_value(
                material, parameter_name, value
            )
            log(f"{material.get_name()}.{parameter_name} -> {value}")

        for parameter_name, value in SCALAR_PARAMS.items():
            if parameter_name not in scalar_names:
                continue
            unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
                material, parameter_name, value
            )
            log(f"{material.get_name()}.{parameter_name} -> {value}")

        unreal.MaterialEditingLibrary.update_material_instance(material)
        unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)

    log("DONE")


try:
    main()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
