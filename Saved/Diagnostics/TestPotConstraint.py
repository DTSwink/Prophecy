import unreal,time,json,pathlib,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
s=dict(start=time.monotonic(),world=None,rows=[])
out=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/PotConstraintPIE.json')
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 if ed.get_game_world() and ed.get_game_world()==s['world']:level.editor_request_end_play()
 out.write_text(json.dumps(dict(error=error,samples=s['rows']),indent=2))
def tick(_):
 try:
  w=ed.get_game_world()
  if not w:
   if time.monotonic()-s['start']>40:finish('No PIE')
   return
  if s['world'] is None:s['world']=w
  if w!=s['world']:finish('World replaced');return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t<.1:return
  if s['rows'] and t<s['rows'][-1]['time']+.25:return
  pots=[a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor) if a.get_class().get_name()=='A_Pot_C']
  for a in pots:
   c=a.get_component_by_class(unreal.PhysicsConstraintComponent)
   p=a.get_component_by_class(unreal.StaticMeshComponent)
   rope=a.get_component_by_class(unreal.SkeletalMeshComponent)
   unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.ConstraintAudit A_Pot')
   audit=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/StandardConstraints/World.json')
   lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyJoltStaticMeshLibrary'))
   s['rows'].append(dict(time=t,pot_jolt=lib.call_method('IsJoltStaticMeshPhysicsEnabled',(p,)),pot=str(p.get_world_location()),rope_end=str(rope.get_socket_location('joint27')),rope_sim=rope.is_simulating_physics('joint27'),audit=json.loads(audit.read_text(encoding='utf-8-sig')) if audit.exists() else None))
  if t>=3:finish()
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
