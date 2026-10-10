import unreal,pathlib,json,hashlib,shutil
root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/SwordDraw20261010'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);assert not ed.get_game_world()
result={}
for name,path in [('agent','/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent'),('sword','/Game/_mygame/sword/A_Sword')]:
 asset=unreal.load_asset(path);assert unreal.EditorAssetLibrary.save_loaded_asset(asset,only_if_is_dirty=True)
 result[name]=hashlib.sha256((root/'Content'/path.removeprefix('/Game/') ).with_suffix('.uasset').read_bytes()).hexdigest()
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
shutil.copy2(out.parent/'SwordThigh/BlueprintGraph.txt',out/'graph-final.txt')
result['map_sha256']=hashlib.sha256((root/'Content/testNN.umap').read_bytes()).hexdigest()
result['dirty']=[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()+unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
result['play']=bool(ed.get_game_world())
(out/'saved.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
