import traceback
import unreal


MAP_PATH = "/Game/Prophecy/MetaHumanPipeline/LVL_MetaHumanPlaceholderPreview"
FACE_MESH_PATH = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/SKM_MHC_ProphecyPlaceholder_FaceMesh"
HEAD_SKIN_PATH = "/Game/Prophecy/MetaHumanPipeline/M_ProphecyPlaceholderHeadSkin"
FACE_SKIN_SLOT_INDICES = (7, 9, 10)


def log(message):
    unreal.log(f"[ProphecyMetaHumanHeadSkin] {message}")


def force_asset_face_slots():
    face_mesh = unreal.load_asset(FACE_MESH_PATH)
    head_skin = unreal.load_asset(HEAD_SKIN_PATH)
    if face_mesh is None:
        raise RuntimeError(f"Missing face mesh: {FACE_MESH_PATH}")
    if head_skin is None:
        raise RuntimeError(f"Missing head skin material: {HEAD_SKIN_PATH}")

    try:
        material_slots = face_mesh.get_editor_property("materials")
        for slot_index in FACE_SKIN_SLOT_INDICES:
            slot = material_slots[slot_index]
            slot.set_editor_property("material_interface", head_skin)
            log(f"Face mesh asset slot {slot_index} -> {head_skin.get_name()}")

        face_mesh.set_editor_property("materials", material_slots)
        unreal.EditorAssetLibrary.save_loaded_asset(face_mesh, only_if_is_dirty=False)
    except Exception as exc:
        log(f"Asset material slot override skipped: {exc}")


def force_preview_component_slots():
    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if level_subsystem is not None:
        level_subsystem.load_level(MAP_PATH)
    else:
        unreal.EditorLevelLibrary.load_level(MAP_PATH)

    head_skin = unreal.load_asset(HEAD_SKIN_PATH)
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
                for slot_index in FACE_SKIN_SLOT_INDICES:
                    component.set_material(slot_index, head_skin)
                    log(f"Preview component {component.get_name()} slot {slot_index} -> {head_skin.get_name()}")
        break
    else:
        raise RuntimeError("Could not find ProphecyPlaceholder_MetaHuman in preview level")

    unreal.EditorLevelLibrary.save_current_level()


def main():
    force_asset_face_slots()
    force_preview_component_slots()
    log("DONE")


try:
    main()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
