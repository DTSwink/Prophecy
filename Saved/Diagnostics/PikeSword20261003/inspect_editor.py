import unreal,json,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/PikeSword20261003';p.mkdir(exist_ok=True,parents=True)
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);w=ed.get_game_world()
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
(p/'current-graph.txt').write_bytes((p.parent/'SwordThigh/BlueprintGraph.txt').read_bytes())
out=dict(play=str(w),editor=str(ed.get_editor_world()),agents=[])
if w:
 for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
  if not a.is_player_controlled():continue
  sw=a.get_held_sword()
  out['agents'].append(dict(name=a.get_name(),tick=a.get_editor_property('tick debug'),attack=str(a.get_nn_attack_state()),mode=str(a.get_simulation_mode()),sword=str(sw),sword_class=str(sw.get_class()) if sw else None,components=[dict(name=c.get_name(),class_name=c.get_class().get_name()) for c in sw.get_components_by_class(unreal.SceneComponent)] if sw else []))
(p/'inspection.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
