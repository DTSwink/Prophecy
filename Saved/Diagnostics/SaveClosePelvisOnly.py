import unreal,pathlib,shutil,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve active Play'
path='/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent'
dirty=unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()+unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert all(p.get_path_name()==path for p in dirty),'Unrelated unsaved assets: '+str([p.get_path_name() for p in dirty])
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
source=pathlib.Path(unreal.Paths.project_content_dir())/'_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset'
shutil.copy2(source,folder/'BP-BeforePelvisOnlyRollback.uasset')
assert unreal.EditorAssetLibrary.save_asset(path,only_if_is_dirty=True),'Pose Blueprint save failed'
assert not (unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()+unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
(folder/'PelvisOnly-Restart.json').write_text(json.dumps({'map':ed.get_editor_world().get_path_name(),'saved':True}))
print('PELVIS_ONLY_ROLLBACK_SAVED_RESTARTING')
unreal.SystemLibrary.quit_editor()
