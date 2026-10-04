import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);w=ed.get_game_world();p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RightArmReturn20261004'
r=dict(play=w is not None,cvars={n:unreal.SystemLibrary.get_console_variable_int_value(n) for n in ('Prophecy.SlashTraceAgent','Prophecy.SlashTraceFrames','Prophecy.NNInputTraceFrames')})
if w is None:
 unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
 r['graph_unchanged']=(p/'baseline-graph.txt').read_bytes()==(p.parent/'SwordThigh/BlueprintGraph.txt').read_bytes()
(p/'final-status.json').write_text(json.dumps(r,indent=2));print(r)
