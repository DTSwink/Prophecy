import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve active Play'
assert unreal.EditorAssetLibrary.save_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent',only_if_is_dirty=True)
print('HISTORICAL_CHECKPOINT_COMPLETE',ed.get_editor_world().get_path_name(), 'PIE',bool(ed.get_game_world()))
