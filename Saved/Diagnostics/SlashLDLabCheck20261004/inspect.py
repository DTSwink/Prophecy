import unreal,json,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SlashLDLabCheck20261004'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);w=ed.get_game_world()
r={'play':w is not None,'map':ed.get_editor_world().get_path_name(),'dirty':[x.get_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]}
if w:r['time']=unreal.GameplayStatics.get_time_seconds(w)
print(json.dumps(r));(p/'state.json').write_text(json.dumps(r))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
(p/'graph.txt').write_bytes((p.parent/'SwordThigh/BlueprintGraph.txt').read_bytes())
