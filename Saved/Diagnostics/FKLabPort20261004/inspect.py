import unreal,pathlib,json
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/FKLabPort20261004'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('PLAY',ed.get_game_world() is not None)
print('DIRTY',str(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),str(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
(p/'before-graph.txt').write_bytes((p.parent/'SwordThigh/BlueprintGraph.txt').read_bytes())
print('WORLD',ed.get_editor_world().get_name())
