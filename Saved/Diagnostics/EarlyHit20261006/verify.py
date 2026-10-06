import unreal,pathlib,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/EarlyHit20261006'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
d={'playing':bool(ed.get_game_world()),'graph_unchanged':(p/'baseline-graph.txt').read_bytes()==(p.parent/'SwordThigh/BlueprintGraph.txt').read_bytes()}
(p/'verify.json').write_text(json.dumps(d));print(json.dumps(d))
