import unreal,pathlib,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/AttackCounter20261006'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
d={'playing':bool(ed.get_game_world()),'graph_unchanged':(p/'before-graph.txt').read_bytes()==(p.parent/'SwordThigh/BlueprintGraph.txt').read_bytes(),'dirty_content':[x.get_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],'dirty_maps':[x.get_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
assert d['graph_unchanged']
(p/'verify.json').write_text(json.dumps(d,indent=2));print(json.dumps(d))
