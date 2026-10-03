import unreal

asset = unreal.EditorAssetLibrary.load_asset(
    "/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent")
if not asset:
    raise RuntimeError("Manual pose agent Blueprint is missing")

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
managers = unreal.GameplayStatics.get_all_actors_of_class(
    world, unreal.ProphecyNNLocomotionManager)
if len(managers) != 1:
    raise RuntimeError("Expected one editor manager, found {}".format(len(managers)))

manager = managers[0]
print("MANUAL_EDITOR_STATE class={} crowd={} physical={}".format(
    manager.get_editor_property("agent_class"),
    manager.get_editor_property("crowd_size"),
    manager.get_editor_property("initial_physical_agent_count")))
unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).open_editor_for_assets([asset])
print("MANUAL_POSE_AGENT_OPEN")
