import unreal,pathlib,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
out={'play':bool(ed.get_game_world()),'map':ed.get_editor_world().get_name()}
print(out)
pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/NNModifiers20261004/editor-before.json').write_text(json.dumps(out))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
src=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/SwordThigh/BlueprintGraph.txt')
if src.exists():pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/NNModifiers20261004/before-graph.txt').write_bytes(src.read_bytes())
