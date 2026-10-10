import unreal,pathlib,json,hashlib,shutil
root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/GetUpFloorRemoval20261010'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'User Play is active'
assert not hasattr(unreal.ProphecyGetUpLibrary,'set_get_up_floor_correction'),'Old native node remains'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.RemoveGetUpFloorCorrection')
report=(out/'migration.txt').read_bytes();report=report.decode('utf-16' if report.startswith(b'\xff\xfe') else 'utf-8-sig')
assert 'removed=1 status=3' in report,report
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
shutil.copy2(root/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt',out/'graph-after.txt')
before=(out/'graph-before.txt').read_text(encoding='utf-16')
after=(out/'graph-after.txt').read_text(encoding='utf-16')
blocks=before.split('\n\n');removed=[b for b in blocks if ' | K2Node_CallFunction_280 | Set Get Up Floor Correction' in b]
assert len(removed)==1,removed
expected='\n\n'.join(b for b in blocks if b not in removed)
expected=expected.replace('then= None -> K2Node_CallFunction_280.execute','then= None -> K2Node_CallFunction_281.execute')
expected=expected.replace('execute= None -> K2Node_CallFunction_280.then','execute= None -> K2Node_CallFunction_81.then')
assert expected==after,'Unexpected graph difference; refusing to save'
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
before_saved=json.loads((out/'saved-before.json').read_text())
map_path='Content\\testNN.umap'
assert hashlib.sha256((root/map_path).read_bytes()).hexdigest()==before_saved['assets'][map_path]
dirty=unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()+unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
assert not dirty,[p.get_path_name() for p in dirty]
result={'native_node_removed':True,'removed_graph_node':'K2Node_CallFunction_280','execution_reconnected':'K2Node_CallFunction_81.then -> K2Node_CallFunction_281.execute','all_other_nodes_pins_links_preserved':True,'saved':True,'blueprint_status':3,'map_unchanged':True,'dirty':[],
 'blueprint_sha256':hashlib.sha256((root/'Content/_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset').read_bytes()).hexdigest()}
(out/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
