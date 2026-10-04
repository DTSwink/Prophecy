import unreal,pathlib,shutil,json
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/FKPerAttackTiming20261004'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);assert ed.get_game_world() is None
f=pathlib.Path(unreal.Paths.project_content_dir())/'_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset'
shutil.copy2(f,p/'before/BP-disk.uasset')
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
shutil.copy2(f,p/'before/BP-live.uasset')
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
unreal.SystemLibrary.quit_editor()
