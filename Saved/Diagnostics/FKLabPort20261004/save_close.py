import unreal,pathlib,shutil
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);assert ed.get_game_world() is None
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
r=(p/'LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig');assert 'status=3' in r,r
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
shutil.copy2(pathlib.Path(unreal.Paths.project_content_dir())/'_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset',p/'FKLabPort20261004/before/BP-live-before.uasset')
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
print('User Blueprint saved and backed up; normal rebuild required before reopen.')
unreal.SystemLibrary.quit_editor()
