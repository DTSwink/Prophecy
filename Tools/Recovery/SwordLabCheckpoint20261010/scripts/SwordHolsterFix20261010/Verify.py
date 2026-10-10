import unreal,pathlib,json,hashlib,shutil
root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/SwordHolsterFix20261010'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Play active; verification deferred'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
shutil.copy2(root/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt',out/'graph-after.txt')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
before=json.loads((out/'hashes-before.json').read_text(encoding='utf-8'))
after={p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() for p in before}
result={'graph_identical':(out/'graph-before.txt').read_bytes()==(out/'graph-after.txt').read_bytes(),'hashes_identical':after==before,'hashes':after,'dirty':[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()+unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
(out/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('SWORD_FIX_VERIFY',json.dumps(result))
