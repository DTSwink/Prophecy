import unreal,pathlib,json,hashlib
r=pathlib.Path(unreal.Paths.project_dir()).resolve();out=r/'Saved/Diagnostics/HolsterStrap20261013'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);assert not ed.get_game_world(),'Preserve user Play'
bp=unreal.load_asset('/Game/_mygame/assets/holster/Animated/BP_HolsterWithStrap')
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=True)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
graph=(r/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt').read_bytes()
before=(out/'graph-before.txt').read_bytes()
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
health=(r/'Saved/Diagnostics/LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
hashes=json.loads((out/'saved-before-build.json').read_text())['hashes']
changed=[f for f,h in hashes.items() if hashlib.sha256((r/f).read_bytes()).hexdigest()!=h]
dirty=[p.get_path_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]
result={'user_graph_exact':graph==before,'saved_user_packages_changed':changed,'health':health,'dirty_preserved':dirty}
(out/'finish.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
assert graph==before and not changed,'Unexpected user asset change; inspect before proceeding'
assert 'status=3' in health and 'native_properties=0 pin_types=0' in health
unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).open_editor_for_assets([bp])
