import traceback
import unreal


MAP_PATH = "/Game/Prophecy/MetaHumanPipeline/LVL_MetaHumanProductionReference"


def log(message):
    unreal.log(f"[ProphecyKellanInspect] {message}")


def object_path(value):
    if value is None:
        return "None"
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


def safe_get(obj, prop_name):
    try:
        return obj.get_editor_property(prop_name)
    except Exception as exc:
        return f"<{exc}>"


def describe_material_slots(component):
    try:
        count = component.get_num_materials()
    except Exception:
        return
    for index in range(count):
        mat = component.get_material(index)
        log(f"      mat[{index}]={object_path(mat)}")


def main():
    unreal.EditorLevelLibrary.load_level(MAP_PATH)
    actors = [
        actor
        for actor in unreal.EditorLevelLibrary.get_all_level_actors()
        if actor.get_actor_label() == "ProphecyProduction_MetaHuman_Kellan"
    ]
    if not actors:
        raise RuntimeError("Could not find ProphecyProduction_MetaHuman_Kellan")

    actor = actors[0]
    log(f"actor={actor.get_path_name()} class={actor.get_class().get_name()}")
    for component in actor.get_components_by_class(unreal.ActorComponent):
        class_name = component.get_class().get_name()
        name = component.get_name()
        log(f"component {name} class={class_name}")
        if "LODSync" in class_name:
            for prop_name in ("forced_lod", "min_lod", "num_lods", "components_to_sync"):
                log(f"    {prop_name}={safe_get(component, prop_name)}")
        if isinstance(component, unreal.SkinnedMeshComponent):
            mesh = safe_get(component, "skeletal_mesh_asset")
            log(f"    mesh={object_path(mesh)}")
            for prop_name in ("forced_lod_model", "min_lod_model", "predicted_lod_level"):
                log(f"    {prop_name}={safe_get(component, prop_name)}")
            describe_material_slots(component)
        elif isinstance(component, unreal.StaticMeshComponent):
            mesh = safe_get(component, "static_mesh")
            log(f"    mesh={object_path(mesh)}")
            describe_material_slots(component)


try:
    main()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
