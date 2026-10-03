import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
assert bp
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
print('RECOVERED_POSE_BLUEPRINT_SAVED',bp.get_path_name())
