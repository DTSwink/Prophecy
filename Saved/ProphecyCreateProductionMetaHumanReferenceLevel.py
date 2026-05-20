import traceback
import unreal


MAP_PATH = "/Game/Prophecy/MetaHumanPipeline/LVL_MetaHumanProductionReference"
BLUEPRINT_CLASS_PATH = "/Game/MetaHumans/Kellan/BP_Kellan.BP_Kellan_C"


def log(message):
    unreal.log(f"[ProphecyProductionMetaHumanReference] {message}")


def main():
    if unreal.EditorAssetLibrary.does_asset_exist(MAP_PATH):
        unreal.EditorLevelLibrary.load_level(MAP_PATH)
    else:
        unreal.EditorLevelLibrary.new_level(MAP_PATH)

    metahuman_class = unreal.load_object(None, BLUEPRINT_CLASS_PATH)
    if metahuman_class is None:
        raise RuntimeError(f"Could not load MetaHuman class: {BLUEPRINT_CLASS_PATH}")

    actor = None
    for level_actor in unreal.EditorLevelLibrary.get_all_level_actors():
        if level_actor.get_actor_label() == "ProphecyProduction_MetaHuman_Kellan":
            actor = level_actor
            break

    if actor is None:
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
            metahuman_class,
            unreal.Vector(0.0, 0.0, 0.0),
            unreal.Rotator(0.0, 0.0, 0.0),
        )
        if actor is None:
            raise RuntimeError("Could not spawn production MetaHuman actor")

    actor.set_actor_label("ProphecyProduction_MetaHuman_Kellan")
    actor.set_actor_location(unreal.Vector(0.0, 0.0, 0.0), False, False)
    actor.set_actor_rotation(unreal.Rotator(0.0, 0.0, 0.0), False)

    # Keep the level as a pure source-of-truth reference. Runtime capture adds
    # the controlled floor, light, and camera so every tier can be compared.
    unreal.EditorLevelLibrary.save_current_level()
    log(f"Saved production reference level: {MAP_PATH}")


try:
    main()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
