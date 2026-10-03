import traceback
import unreal


MAP_PATH = "/Game/Prophecy/MetaHumanPipeline/LVL_MetaHumanPlaceholderPreview"
FACE_MATERIALS = [
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD1",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD3",
    "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD5to7",
]

TEXTURE_PARAMS = {
    "Basecolor": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Basecolor",
    "Normal": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Normal",
    "Cavity": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Cavity",
    "Basecolor Animated Delta cm1": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Basecolor_Animated_CM1",
    "Basecolor Animated Delta cm2": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Basecolor_Animated_CM2",
    "Basecolor Animated Delta cm3": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Basecolor_Animated_CM3",
    "Normal Animated Delta wm1": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Normal_Animated_WM1",
    "Normal Animated Delta wm2": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Normal_Animated_WM2",
    "Normal Animated Delta wm3": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Normal_Animated_WM3",
    "Color_CHEST": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/Textures/T_Basecolor",
    "Normal_CHEST": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/Textures/T_Normal",
    "Cavity_Chest": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/Textures/T_Cavity",
    "Underwear_Chest_BaseColor": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/Textures/T_Basecolor",
    "Underwear_Chest_Normal": "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/Textures/T_Normal",
}


def log(message):
    unreal.log(f"[ProphecyMetaHumanFix] {message}")


def set_texture_parameter(material, parameter_name, texture_path):
    texture = unreal.load_asset(texture_path)
    if texture is None:
        log(f"Missing texture for {parameter_name}: {texture_path}")
        return False
    unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(material, parameter_name, texture)
    log(f"{material.get_name()}.{parameter_name} -> {texture.get_name()}")
    return True


def patch_face_materials():
    for material_path in FACE_MATERIALS:
        material = unreal.load_asset(material_path)
        if material is None:
            raise RuntimeError(f"Missing material: {material_path}")

        for parameter_name, texture_path in TEXTURE_PARAMS.items():
            set_texture_parameter(material, parameter_name, texture_path)

        unreal.MaterialEditingLibrary.update_material_instance(material)
        unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)


def rotate_preview_actor():
    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if level_subsystem is not None:
        level_subsystem.load_level(MAP_PATH)
    else:
        unreal.EditorLevelLibrary.load_level(MAP_PATH)

    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        if actor.get_actor_label() == "ProphecyPlaceholder_MetaHuman":
            rotation = unreal.Rotator()
            rotation.pitch = 0.0
            rotation.yaw = 180.0
            rotation.roll = 0.0
            actor.set_actor_rotation(rotation, False)
            log(f"Rotated preview actor to face the close-preview camera: {actor.get_actor_rotation()}")
            break
    else:
        raise RuntimeError("Could not find ProphecyPlaceholder_MetaHuman in preview level")

    unreal.EditorLevelLibrary.save_current_level()


def main():
    patch_face_materials()
    rotate_preview_actor()
    log("DONE")


try:
    main()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
