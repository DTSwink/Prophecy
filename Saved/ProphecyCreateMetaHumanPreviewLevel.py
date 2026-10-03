import traceback
import unreal


MAP_PATH = "/Game/Prophecy/MetaHumanPipeline/LVL_MetaHumanPlaceholderPreview"
BLUEPRINT_CLASS_PATH = "/Game/Prophecy/MetaHumans/ProphecyPlaceholder/BP_ProphecyPlaceholder.BP_ProphecyPlaceholder_C"


def log(message):
    unreal.log(f"[ProphecyMetaHumanPreview] {message}")


def main():
    unreal.EditorLevelLibrary.new_level(MAP_PATH)

    placeholder_class = unreal.load_object(None, BLUEPRINT_CLASS_PATH)
    if placeholder_class is None:
        raise RuntimeError(f"Could not load placeholder class: {BLUEPRINT_CLASS_PATH}")

    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        placeholder_class,
        unreal.Vector(0.0, 0.0, 0.0),
        unreal.Rotator(0.0, 0.0, 0.0),
    )
    if actor is None:
        raise RuntimeError("Could not spawn placeholder actor")

    actor.set_actor_label("ProphecyPlaceholder_MetaHuman")

    # Keep map content minimal. The benchmark preview run adds camera, floor, and light.
    unreal.EditorLevelLibrary.save_current_level()
    log(f"Saved preview level: {MAP_PATH}")


try:
    main()
except Exception:
    unreal.log_error(traceback.format_exc())
    raise
