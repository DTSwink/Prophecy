import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SwordHead20261006';p.mkdir(exist_ok=True)
w=ed.get_game_world()
out={'play':w is not None,'agents':[]}
if w:
 out['paused']=unreal.GameplayStatics.is_game_paused(w)
 for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
  d={'actor':a.get_name(),'attack':str(a.get_nn_attack_state())}
  for prop in ['absolute tick debug','tick debug','bool debug 1','SwordHandSocket']:
   try:d[prop]=str(a.get_editor_property(prop))
   except Exception:pass
  sw=a.get_held_sword()
  if sw:
   c=sw.get_component_by_class(unreal.StaticMeshComponent)
   d['sword']={'name':sw.get_name(),'collision':str(c.get_collision_enabled()),'object':str(c.get_collision_object_type()),'responses':{str(ch):str(c.get_collision_response_to_channel(ch)) for ch in [unreal.CollisionChannel.ECC_PAWN,unreal.CollisionChannel.ECC_PHYSICS_BODY,unreal.CollisionChannel.ECC_WORLD_DYNAMIC]},'transform':str(c.get_world_transform())}
  out['agents'].append(d)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
(p/'graph.txt').write_bytes((p.parent/'SwordThigh/BlueprintGraph.txt').read_bytes())
(p/'inspect.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
