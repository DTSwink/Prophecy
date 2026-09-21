import unreal, pathlib, shutil, datetime
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Stop Play first'
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), 'Preserve dirty maps'
path='/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent'
dirty=unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
assert all(p.get_path_name()==path for p in dirty), 'Preserve unrelated dirty assets'
if dirty:
    # Keep the old disk asset too. The pose-agent is the only changed task asset.
    source=pathlib.Path(unreal.Paths.project_content_dir())/'_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset'
    backup=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/FineGrainedBlends-SavedBeforeRestart.uasset'
    shutil.copy2(source,backup)
    assert unreal.EditorAssetLibrary.save_asset(path,only_if_is_dirty=True)
unreal.SystemLibrary.quit_editor()
