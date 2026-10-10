import unreal,pathlib,json,hashlib,shutil
root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/GetUpPhysics20261010'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
dirty=unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()+unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
shutil.copy2(root/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt',out/'graph-before.txt')
result={'play':bool(ed.get_game_world()),'dirty':[p.get_path_name() for p in dirty],
 'assets':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [root/'Content/_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset',root/'Content/testNN.umap']}}
(out/'before.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
