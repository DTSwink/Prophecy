import traceback
import unreal


MAP_PATH = "/Game/Prophecy/MetaHumanPipeline/LVL_MetaHumanPlaceholderPreview"
FACE_MESH_PATH = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/SKM_MHC_ProphecyPlaceholder_FaceMesh"

FACE_LOD1 = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD1"
FACE_LOD3 = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD3"
FACE_LOD5 = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD5to7"
HEAD_LOD1_PARENT = "/Game/Prophecy/MetaHumans/Common/Materials/MI_Skin_Head_UI_LOD1_VT"

FACE_SKIN_SLOTS = {
    7: FACE_LOD1,
    9: FACE_LOD3,
    10: FACE_LOD5,
}

PARENTS = {
    FACE_LOD1: HEAD_LOD1_PARENT,
    FACE_LOD3: FACE_LOD1,
    FACE_LOD5: FACE_LOD3,
}

FACE_BASE = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Basecolor"
FACE_NORMAL = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Normal"
FACE_CAVITY = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Cavity"

LOD1_TEXTURE_PARAMS = {
    # These two placeholder face textures are real virtual textures, so keep the
    # MetaHuman material on its VT branch and feed the branch it actually uses.
    "Basecolor VT": FACE_BASE,
    "Normal VT": FACE_NORMAL,
    "Basecolor Original VT": FACE_BASE,
    "Normal Original VT": FACE_NORMAL,
    "Basecolor Baked VT": FACE_BASE,
    "Normal Baked VT": FACE_NORMAL,

    # Cavity is currently generated as a regular texture. Leave the VT cavity
    # slots inherited so the real shader never samples a non-VT texture as VT.
    "Cavity": FACE_CAVITY,
}

STATIC_SWITCH_PARAMS = {
    "Use Virtual Texture": True,
    "Use Baked Material": False,
    "Bake ON": False,
    "UseSimpleShading": False,
    "Use Face Region Masks": True,
    "Use Region Adjustments": True,
    "Use Global Adjustments": True,
    "Use Global Adjustments Post-Bake": True,
    "Use Body Hider": True,
    "Use Pre-Baked Groom Texture Set": False,
    "Use Baked Grooms": False,
}


def log(message):
    unreal.log(f"[ProphecyRestoreRealFaceSkin] {message}")


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


def clear_parameters(material):
    clear_fn = getattr(unreal.MaterialEditingLibrary, "clear_all_material_instance_parameters", None)
    if clear_fn is None:
        raise RuntimeError("MaterialEditingLibrary.clear_all_material_instance_parameters is unavailable")
    clear_fn(material)
    log(f"{material.get_name()} cleared old overrides")


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


def patch_material_instance(material_path, write_overrides):
    material = load_asset(material_path)
    parent = load_asset(PARENTS[material_path])
    material.set_editor_property("parent", parent)
    clear_parameters(material)

    texture_names = set(str(name) for name in unreal.MaterialEditingLibrary.get_texture_parameter_names(material))
    switch_names = set(str(name) for name in unreal.MaterialEditingLibrary.get_static_switch_parameter_names(material))

    if write_overrides:
        for parameter_name, texture_path in LOD1_TEXTURE_PARAMS.items():
            set_texture_parameter(material, texture_names, parameter_name, texture_path)

        for parameter_name, value in STATIC_SWITCH_PARAMS.items():
            set_static_switch(material, switch_names, parameter_name, value)
    else:
        log(f"{material.get_name()} will inherit texture and switch overrides")

    unreal.MaterialEditingLibrary.update_material_instance(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)
    log(f"{material.get_name()} parent -> {path(parent)}")
    return material


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

        log("Preview actor kept facing the camera")
        break
    else:
        raise RuntimeError("Could not find ProphecyPlaceholder_MetaHuman in preview level")

    unreal.EditorLevelLibrary.save_current_level()


def main():
    patch_material_instance(FACE_LOD1, write_overrides=True)
    patch_material_instance(FACE_LOD3, write_overrides=False)
    patch_material_instance(FACE_LOD5, write_overrides=False)
    restore_face_mesh_slots()
    restore_preview_actor_slots()
    log("DONE")


try:
    main()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
