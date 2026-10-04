import unreal,json,pathlib,shutil
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/FKPerAttackTiming20261004'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
r={'play':ed.get_game_world() is not None,'content':[x.get_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],'maps':[x.get_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
print(json.dumps(r));(p/'state-before.json').write_text(json.dumps(r))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
(p/'before-graph.txt').write_bytes((p.parent/'SwordThigh/BlueprintGraph.txt').read_bytes())
