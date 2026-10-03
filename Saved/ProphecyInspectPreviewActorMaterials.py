import traceback
import unreal


MAP_PATH = "/Game/Prophecy/MetaHumanPipeline/LVL_MetaHumanPlaceholderPreview"


def log(message):
    unreal.log(f"[ProphecyPreviewMaterials] {message}")


def object_path(value):
    return value.get_path_name() if value else "None"


def main():
    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if level_subsystem is not None:
        level_subsystem.load_level(MAP_PATH)
    else:
        unreal.EditorLevelLibrary.load_level(MAP_PATH)

    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        if actor.get_actor_label() != "ProphecyPlaceholder_MetaHuman":
            continue
        for component in actor.get_components_by_class(unreal.SkeletalMeshComponent):
            mesh = None
            for property_name in ("skeletal_mesh_asset", "skeletal_mesh"):
                try:
                    mesh = component.get_editor_property(property_name)
                    if mesh is not None:
                        break
                except Exception:
                    pass
            log(f"component={component.get_name()} mesh={mesh.get_name() if mesh else 'None'}")
            for slot_index in range(component.get_num_materials()):
                material = component.get_material(slot_index)
                log(f"  slot {slot_index}: {object_path(material)}")
        return

    raise RuntimeError("Could not find ProphecyPlaceholder_MetaHuman")


try:
    main()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
