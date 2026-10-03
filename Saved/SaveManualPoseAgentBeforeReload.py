import unreal

asset = unreal.EditorAssetLibrary.load_asset(
    "/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent")
if not asset:
    raise RuntimeError("Manual pose Blueprint was not created")
unreal.EditorAssetLibrary.save_loaded_asset(asset)
print("MANUAL_POSE_AGENT_SAVED_FOR_RELOAD")
