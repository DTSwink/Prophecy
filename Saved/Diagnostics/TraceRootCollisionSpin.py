import unreal,json,pathlib,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem); level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world()
s={'start':time.monotonic(),'rows':[]}
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RootCollisionSpin.json'
def v(x):return [x.x,x.y,x.z]
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 if ed.get_game_world():level.editor_request_end_play()
 out.write_text(json.dumps(dict(error=error,rows=s['rows']),indent=1))
 print('SPIN_TRACE',error or 'done',len(s['rows']))
def tick(_):
 try:
  assert time.monotonic()-s['start']<100,'Timeout'
  w=ed.get_game_world()
  if not w:return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t<.2:return
  for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
   if not a.has_valid_agent_handle():continue
   i=a.get_locomotion_input(); rv=a.get_root_velocity(); tar=a.get_locomotion_target()
   s['rows'].append(dict(t=t,a=a.get_name(),yaw=a.get_actor_rotation().yaw,p=v(a.get_root_low_point()),rate=v(rv[-1]),move=v(i.world_move_input),face=v(i.facing_world_direction),target=v(tar[-2]),magic=v(unreal.ProphecyRootPhysicsLibrary.get_root_magic_ang_velocity(a))))
  if t>15:finish()
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
