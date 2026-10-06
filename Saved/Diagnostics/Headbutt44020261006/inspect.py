import unreal,json,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/Headbutt44020261006'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world()
out={'playing':bool(w),'agents':[]}
if w:
 out['paused']=unreal.GameplayStatics.is_game_paused(w)
 for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
  r={'name':a.get_name(),'label':a.get_actor_label(),'attack':str(a.get_nn_attack_state()),'mode':str(a.get_simulation_mode())}
  for k in ['absolute tick debug','tick debug','bool debug 1','bool debug 2','bool debug 3']:
   try:r[k]=a.get_editor_property(k)
   except Exception as e:r[k]=str(e)
  out['agents'].append(r)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
graph=p.parent/'SwordThigh/BlueprintGraph.txt'
if graph.exists():(p/'current-graph.txt').write_bytes(graph.read_bytes())
(p/'inspect.json').write_text(json.dumps(out,indent=2),encoding='utf8')
print(json.dumps(out))
