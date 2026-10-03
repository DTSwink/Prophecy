import unreal


ASSET_DIR = "/Game/_mygame/locomotion"
ASSET_NAME = "BP_ProphecyManualPoseAgent"
ASSET_PATH = ASSET_DIR + "/" + ASSET_NAME

if unreal.EditorAssetLibrary.does_asset_exist(ASSET_PATH):
    blueprint = unreal.EditorAssetLibrary.load_asset(ASSET_PATH)
    if not blueprint:
        # An interrupted editor reload can leave an asset-registry entry without
        # a loadable package. This removes only this test Blueprint entry.
        unreal.EditorAssetLibrary.delete_asset(ASSET_PATH)
        blueprint = None
else:
    blueprint = None

if not blueprint:
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.ProphecyAgent)
    blueprint = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        ASSET_NAME, ASSET_DIR, unreal.Blueprint, factory)

if not blueprint:
    raise RuntimeError("Could not create " + ASSET_PATH)

agent_class = unreal.EditorAssetLibrary.load_blueprint_class(ASSET_PATH)
if not agent_class:
    raise RuntimeError("Could not load generated class for " + ASSET_PATH)

defaults = unreal.get_default_object(agent_class)
defaults.modify()
defaults.set_editor_property("manual_nn_pose_application", True)
blueprint.modify()
unreal.EditorAssetLibrary.save_loaded_asset(blueprint, only_if_is_dirty=False)

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
managers = unreal.GameplayStatics.get_all_actors_of_class(
    world, unreal.ProphecyNNLocomotionManager)
if len(managers) != 1:
    raise RuntimeError("Expected exactly one locomotion manager, found {}".format(len(managers)))

manager = managers[0]
manager.set_editor_property("agent_class", agent_class)
manager.set_editor_property("crowd_size", 1)
manager.set_editor_property("initial_physical_agent_count", 0)
unreal.EditorLevelLibrary.save_current_level()
print("MANUAL_POSE_AGENT_READY asset={} manager={}".format(
    ASSET_PATH, manager.get_name()))
