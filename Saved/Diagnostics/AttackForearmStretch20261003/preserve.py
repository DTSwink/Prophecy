import unreal,pathlib,shutil,json
p=pathlib.Path(unreal.Paths.project_dir()).resolve()
d=p/'Saved/Diagnostics/AttackForearmStretch20261003'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None,'User Play is active; preserve it.'
dirty=unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
maps=unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
asset='/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent'
assert not maps,'Dirty map must be preserved separately.'
assert all(x.get_path_name()==asset for x in dirty),str(dirty)
file=p/'Content/_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset'
shutil.copy2(file,d/'Before/BP-disk.uasset')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
shutil.copy2(p/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt',d/'Before/BlueprintGraph.txt')
bp=unreal.load_asset(asset)
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
shutil.copy2(file,d/'Before/BP-live.uasset')
(d/'preserved.json').write_text(json.dumps({'dirty_before':[x.get_path_name() for x in dirty],'map':ed.get_editor_world().get_path_name(),'saved_live':True}))
print('Live and disk Blueprint preserved; current live edits saved for normal-DLL rebuild.')
unreal.SystemLibrary.quit_editor()
