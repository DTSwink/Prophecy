import unreal
path='/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent'
assert unreal.EditorAssetLibrary.save_asset(path,only_if_is_dirty=True), 'Pose Blueprint save failed'
dirty=list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
print('DIRTY_AFTER_SAVE',[p.get_name() for p in dirty])
assert not dirty,'Other unsaved packages; keeping editor open'
unreal.SystemLibrary.execute_console_command(None,'QUIT_EDITOR')
