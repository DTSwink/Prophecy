import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user Play'
bp=unreal.EditorAssetLibrary.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
print('LEFT_HAND_ANGLE_BLUEPRINT_SAVED')
