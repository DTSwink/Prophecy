import unreal,pathlib,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None
root=pathlib.Path(unreal.Paths.project_dir()).resolve()
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
(root/'Saved/Diagnostics/GhostLocoDrag20261003/after-graph.txt').write_bytes((root/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt').read_bytes())
print(json.dumps({'content':[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],'maps':[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}))
