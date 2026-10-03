import traceback
import unreal


MAP_PATH = "/Game/Prophecy/MetaHumanPipeline/LVL_MetaHumanPlaceholderPreview"
FACE_MESH_PATH = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/SKM_MHC_ProphecyPlaceholder_FaceMesh"

FACE_SKIN_SLOTS = {
    7: "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD1",
    9: "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD3",
    10: "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD5to7",
}

FACE_MATERIALS = list(FACE_SKIN_SLOTS.values())

FACE_BASE = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Basecolor"
FACE_NORMAL = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Normal"
FACE_CAVITY = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Cavity"
FACE_BASE_CM1 = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Basecolor_Animated_CM1"
FACE_BASE_CM2 = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Basecolor_Animated_CM2"
FACE_BASE_CM3 = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Basecolor_Animated_CM3"
FACE_NORMAL_WM1 = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Normal_Animated_WM1"
FACE_NORMAL_WM2 = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Normal_Animated_WM2"
FACE_NORMAL_WM3 = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Normal_Animated_WM3"
BODY_BASE = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/Textures/T_Basecolor"
BODY_NORMAL = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/Textures/T_Normal"
BODY_CAVITY = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/Textures/T_Cavity"

TEXTURE_PARAMS = {
    "Basecolor": FACE_BASE,
    "Basecolor VT": FACE_BASE,
    "Basecolor Original": FACE_BASE,
    "Basecolor Original VT": FACE_BASE,
    "Basecolor Baked": FACE_BASE,
    "Basecolor Baked VT": FACE_BASE,
    "Normal": FACE_NORMAL,
    "Normal VT": FACE_NORMAL,
    "Normal Original": FACE_NORMAL,
    "Normal Original VT": FACE_NORMAL,
    "Cavity": FACE_CAVITY,
    "Cavity VT": FACE_CAVITY,
    "Basecolor Animated cm1": FACE_BASE_CM1,
    "Basecolor Animated cm1 VT": FACE_BASE_CM1,
    "Basecolor Animated cm2": FACE_BASE_CM2,
    "Basecolor Animated cm2 VT": FACE_BASE_CM2,
    "Basecolor Animated cm3": FACE_BASE_CM3,
    "Basecolor Animated cm3 VT": FACE_BASE_CM3,
    "Basecolor Animated Delta cm1": FACE_BASE_CM1,
    "Basecolor Animated Delta cm2": FACE_BASE_CM2,
    "Basecolor Animated Delta cm3": FACE_BASE_CM3,
    "Normal Animated wm1": FACE_NORMAL_WM1,
    "Normal Animated wm1 VT": FACE_NORMAL_WM1,
    "Normal Animated wm2": FACE_NORMAL_WM2,
    "Normal Animated wm2 VT": FACE_NORMAL_WM2,
    "Normal Animated wm3": FACE_NORMAL_WM3,
    "Normal Animated wm3 VT": FACE_NORMAL_WM3,
    "Normal Animated Delta wm1": FACE_NORMAL_WM1,
    "Normal Animated Delta wm2": FACE_NORMAL_WM2,
    "Normal Animated Delta wm3": FACE_NORMAL_WM3,
    "Color_CHEST": BODY_BASE,
    "Normal_CHEST": BODY_NORMAL,
    "Cavity_Chest": BODY_CAVITY,
    "Underwear_Chest_BaseColor": BODY_BASE,
    "Underwear_Chest_Normal": BODY_NORMAL,
}

STATIC_SWITCH_PARAMS = {
    # The placeholder builder creates ordinary Texture2D assets, not the optional
    # MetaHuman baked VT payload. Keeping this branch enabled makes the head read
    # the common grey placeholder textures while the body reads the seeded assets.
    "Use Virtual Texture": False,
    "Use Baked Material": False,
    "Bake ON": False,
    "Use Pre-Baked Groom Texture Set": False,
    "Use Baked Grooms": False,
}


def log(message):
    unreal.log(f"[ProphecyFaceMaterialFix] {message}")


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


def set_texture_parameter(material, available_names, parameter_name, texture_path):
    if parameter_name not in available_names:
        return

    texture = load_asset(texture_path)
    try:
        unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
            material, parameter_name, texture
        )
        log(f"{material.get_name()}.{parameter_name} -> {texture.get_name()}")
    except Exception as exc:
        log(f"{material.get_name()}.{parameter_name} skipped: {exc}")


def set_static_switch(material, available_names, parameter_name, value):
    if parameter_name not in available_names:
        return

    try:
        unreal.MaterialEditingLibrary.set_material_instance_static_switch_parameter_value(
            material, parameter_name, value
        )
        log(f"{material.get_name()}.{parameter_name} -> {value}")
    except Exception as exc:
        log(f"{material.get_name()}.{parameter_name} skipped: {exc}")


def patch_face_materials():
    for material_path in FACE_MATERIALS:
        material = load_asset(material_path)
        texture_names = set(str(name) for name in unreal.MaterialEditingLibrary.get_texture_parameter_names(material))
        switch_names = set(str(name) for name in unreal.MaterialEditingLibrary.get_static_switch_parameter_names(material))

        for parameter_name, texture_path in TEXTURE_PARAMS.items():
            set_texture_parameter(material, texture_names, parameter_name, texture_path)

        for parameter_name, value in STATIC_SWITCH_PARAMS.items():
            set_static_switch(material, switch_names, parameter_name, value)

        unreal.MaterialEditingLibrary.update_material_instance(material)
        unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)
        log(f"Saved {path(material)}")


def restore_face_mesh_slots():
    face_mesh = load_asset(FACE_MESH_PATH)
    material_slots = face_mesh.get_editor_property("materials")

    for slot_index, material_path in FACE_SKIN_SLOTS.items():
        material = load_asset(material_path)
        slot = material_slots[slot_index]
        slot.set_editor_property("material_interface", material)
        log(f"Face mesh slot {slot_index} -> {path(material)}")

    face_mesh.set_editor_property("materials", material_slots)
    unreal.EditorAssetLibrary.save_loaded_asset(face_mesh, only_if_is_dirty=False)


def restore_preview_actor_slots():
    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if level_subsystem is not None:
        level_subsystem.load_level(MAP_PATH)
    else:
        unreal.EditorLevelLibrary.load_level(MAP_PATH)

    materials = {slot: load_asset(material_path) for slot, material_path in FACE_SKIN_SLOTS.items()}

    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        if actor.get_actor_label() != "ProphecyPlaceholder_MetaHuman":
            continue

        rotation = unreal.Rotator()
        rotation.pitch = 0.0
        rotation.yaw = 180.0
        rotation.roll = 0.0
        actor.set_actor_rotation(rotation, False)

        for component in actor.get_components_by_class(unreal.SkeletalMeshComponent):
            mesh = None
            for property_name in ("skeletal_mesh_asset", "skeletal_mesh"):
                try:
                    mesh = component.get_editor_property(property_name)
                    if mesh is not None:
                        break
                except Exception:
                    pass

            if mesh and "FaceMesh" in mesh.get_name():
                for slot_index, material in materials.items():
                    component.set_material(slot_index, material)
                    log(f"Preview {component.get_name()} slot {slot_index} -> {path(material)}")

        break
    else:
        raise RuntimeError("Could not find ProphecyPlaceholder_MetaHuman in preview level")

    unreal.EditorLevelLibrary.save_current_level()


def main():
    patch_face_materials()
    restore_face_mesh_slots()
    restore_preview_actor_slots()
    log("DONE")


try:
    main()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
