import unreal,pathlib,json
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/Knees49920261003'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world()
r={'world':str(w)}
if w:
 a=unreal.GameplayStatics.get_player_pawn(w,0)
 r.update(pawn=str(a),tick=int(a.get_editor_property('tick debug')),attack=str(a.get_nn_attack_state()))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
(p/'current-graph.txt').write_bytes((p.parent/'SwordThigh/BlueprintGraph.txt').read_bytes())
(p/'status.json').write_text(json.dumps(r))
print(r)
