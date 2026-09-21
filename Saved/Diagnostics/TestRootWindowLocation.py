import unreal,json,pathlib,time,traceback,math
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world()
lib=unreal.get_default_object(unreal.ProphecyRootPhysicsLibrary)
s={'start':time.monotonic(),'rows':[],'phase':'warm','frames':0}
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RootWindowLocationPIE.json'
def xyz(v):return [v.x,v.y,v.z]
def roots(a):return unreal.ProphecyRootPhysicsLibrary.get_continuous_locomotion_root_window(a)[-2:]
def dist(a,b):return (a-b).length()
def finish(result,error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 if ed.get_game_world():level.editor_request_end_play()
 out.write_text(json.dumps(dict(result=result,error=error,rows=s['rows']),indent=2))
 print('ROOT_WINDOW_LOCATION',result,error)
def tick(_):
 try:
  assert time.monotonic()-s['start']<60,'Timeout'
  w=ed.get_game_world()
  if not w:return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t<1:return
  if s['phase']=='warm':
   a=unreal.GameplayStatics.get_player_pawn(w,0)
   before,times=roots(a)
   if not before:return
   raw,rawtimes=a.get_locomotion_root_window()[-2:]
   others=[(o,o.get_root_low_point()) for o in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent) if o!=a]
   delta=unreal.Vector(100,20,5); target=before[0].translation+delta
   yaw=a.get_actor_rotation().yaw
   result=lib.call_method('SetLocomotionRootWindowLocation',args=(a,target))
   assert result,result
   after,newtimes=roots(a)
   newraw,newrawtimes=a.get_locomotion_root_window()[-2:]
   errors=[dist(b.translation+delta,c.translation) for b,c in zip(before,after)]
   rawerrors=[dist(b.translation+delta,c.translation) for b,c in zip(raw,newraw)]
   assert max(errors)<.01,errors
   assert max(rawerrors)<.01,rawerrors
   assert list(times)==list(newtimes) and list(rawtimes)==list(newrawtimes)
   assert a.get_actor_rotation().yaw==yaw
   assert all(dist(p,o.get_root_low_point())<.001 for o,p in others)
   assert all(abs(sum(getattr(b.rotation,k)*getattr(c.rotation,k) for k in ("x","y","z","w")))>.999999 for b,c in zip(before,after))
   assert lib.call_method('SetLocomotionRootWindowLocation',args=(a,target)), 'Idempotent placement failed'
   s['rows'].append(dict(stage='shift',target=xyz(target),current=xyz(after[0].translation),max_window_error=max(errors),max_raw_error=max(rawerrors)))
   s.update(phase='follow',actor=a,delta=delta,after=after,target=target,time=t)
  else:
   a=s['actor']; r,ts=roots(a)
   elapsed=t-s['time']
   # Current setup is steady running: use the pre-shift future window to verify
   # the first policy boundary keeps the requested translated trajectory.
   if elapsed<=s['after'].__len__()/30:
    sample=elapsed/ts[1];i=min(int(sample),7);alpha=sample-i
    p0=s['after'][i].translation;p1=s['after'][i+1].translation
    expected=p0+(p1-p0)*alpha
    error=dist(r[0].translation,expected)
    s['rows'].append(dict(stage='follow',elapsed=elapsed,current=xyz(r[0].translation),expected=xyz(expected),error=error))
    assert error<5,('Translated trajectory lost at policy boundary',error)
   s['frames']+=1
   if s['frames']>=5:finish('passed')
 except Exception:finish('failed',traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
