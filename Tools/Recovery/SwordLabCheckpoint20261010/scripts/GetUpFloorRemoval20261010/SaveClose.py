import unreal,pathlib,json,shutil,hashlib
root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/GetUpFloorRemoval20261010'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'User Play is active'
dirty=unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()+unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert all(p.get_path_name()=='/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent' for p in dirty),'Unrelated dirty packages'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
graph=root/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt';shutil.copy2(graph,out/'graph-before.txt')
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
report=(root/'Saved/Diagnostics/LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
assert 'status=3' in report and 'native_properties=0 pin_types=0' in report,report
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
assert graph.read_bytes()==(out/'graph-before.txt').read_bytes(),'Compile changed graph'
if dirty:assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
asset=root/'Content/_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset';shutil.copy2(asset,out/'BP-user-edits-preserved.uasset')
result={'dirty_user_bp_saved':bool(dirty),'assets':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [asset,root/'Content/testNN.umap']}}
(out/'saved-before.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()+unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
print('Current Blueprint edits saved and backed up; closing for the required native layout rebuild.')
unreal.SystemLibrary.quit_editor()
