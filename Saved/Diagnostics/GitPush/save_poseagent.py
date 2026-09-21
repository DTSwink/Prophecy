import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Cannot save this checkpoint while PIE is active'
asset=unreal.EditorAssetLibrary.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
assert asset
assert unreal.EditorAssetLibrary.save_loaded_asset(asset,only_if_is_dirty=True), 'Blueprint save failed'
print('SAVED_POSEAGENT',asset.get_path_name())
