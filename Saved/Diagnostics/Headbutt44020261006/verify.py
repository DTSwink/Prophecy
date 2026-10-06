import unreal,json,pathlib,hashlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/Headbutt44020261006'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
graph=p.parent/'SwordThigh/BlueprintGraph.txt'
d={'playing':bool(ed.get_game_world()),'graph_unchanged':graph.read_bytes()==(p/'current-graph.txt').read_bytes(),'trace':{c:unreal.SystemLibrary.get_console_variable_int_value(c) for c in ['Prophecy.SlashTraceAgent','Prophecy.SlashTraceFrames']}}
(p/'verify.json').write_text(json.dumps(d,indent=2));print(json.dumps(d))
