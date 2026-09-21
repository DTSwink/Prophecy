import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world() or ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.AuditCollisionGraph')
out={'pie':bool(ed.get_game_world()),'actors':[]}
for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
 r={'name':a.get_name(),'location':str(a.get_actor_location()),'mode':str(a.get_simulation_mode()),'feedback':{}}
 for b in ('pelvis','thigh_l','calf_l','foot_l','ball_l','thigh_r','foot_r','hand_r'):
  try:r['feedback'][b]=str(a.get_physical_feedback_tolerance(b))
  except Exception as e:r['feedback'][b]=str(e)
 out['actors'].append(r)
(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/LegFeedbackIsolation/current_collision_setup.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
