import unreal
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
path='/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent'
assert unreal.EditorAssetLibrary.save_asset(path,only_if_is_dirty=True)
print('Saved verified pose-agent Blueprint only.')
