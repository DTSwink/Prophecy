import unreal,json,pathlib,time,traceback,math
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world()
api=unreal.ProphecyRootPhysicsLibrary;zero=unreal.Vector()
s={'start':time.monotonic(),'phase':'setup','rows':[]}
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RootMagicFocused.json'
def xyz(v):return [v.x,v.y,v.z]
def near(a,b,tol=.01):assert (a-b).length()<tol,(a,b,(a-b).length())
def roots(a):return api.get_continuous_locomotion_root_window(a)[-2:]
def lin(a,v):assert api.set_root_magic_velocity(a,v,False)
def ang(a,v):assert api.set_root_magic_ang_velocity(a,unreal.Vector(0,0,v),False)
def balance(a,enabled,lt=10000.,at=10000.):
 assert api.set_root_self_balancing(a,enabled,1e6,1.,2.,1.,0.,1000.,lt,at)
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 if ed.get_game_world():level.editor_request_end_play()
 out.write_text(json.dumps(dict(result='failed' if error else 'passed',error=error,rows=s['rows']),indent=2))
 print('ROOT_MAGIC_FOCUSED',error or 'passed')
def tick(_):
 try:
  assert time.monotonic()-s['start']<120,'Timeout'
  w=ed.get_game_world()
  if not w:return
  t=unreal.GameplayStatics.get_time_seconds(w);dt=unreal.GameplayStatics.get_world_delta_seconds(w)
  if t<1:return
  if s['phase']=='setup':
   actors=[a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent) if a.has_valid_agent_handle()]
   assert len(actors)==3,len(actors)
   for a in actors:
    a.set_editor_property('auto_publish_manual_follower_substep_targets',False);a.set_actor_tick_enabled(False)
    a.stop_nn_attack();a.stop_locomotion_input();lin(a,zero);ang(a,0);balance(a,False)
    unreal.ProphecyNNRootWindowLibrary.set_locomotion_root_window_smoothing(a,1.,1.,1.)
   a=unreal.GameplayStatics.get_player_pawn(w,0)
   for _ in range(40):
    for p in actors:balance(p,True);balance(p,False)
   lin(a,unreal.Vector(1,2,3));ang(a,-30)
   assert api.set_root_magic_velocity(a,unreal.Vector(4,-2,1),True)
   assert api.set_root_magic_ang_velocity(a,unreal.Vector(0,0,10),True)
   near(api.get_root_magic_velocity(a),unreal.Vector(5,0,4));near(api.get_root_magic_ang_velocity(a),unreal.Vector(0,0,-20))
   lin(a,zero);near(api.get_root_magic_ang_velocity(a),unreal.Vector(0,0,-20));ang(a,0)
   for p in actors:near(api.get_root_magic_velocity(p),zero);near(api.get_root_magic_ang_velocity(p),zero)
   s['rows'].append(dict(stage='setters_getters_isolation_and_map_churn',balance_calls=240,passed=True))
   s.update(actors=actors,a=a,phase='settle',time=t)
  for p in s.get('actors',[]):p.publish_manual_follower_substep_targets(dt)
  a=s['a']
  if s['phase']=='settle' and t-s['time']>1:
   before,times=roots(a);raw,rt=a.get_locomotion_root_window()[-2:];d=unreal.Vector(30,20,3);target=before[0].translation+d
   assert api.set_locomotion_root_window_location(a,target)
   after,nt=roots(a);newraw,nrt=a.get_locomotion_root_window()[-2:]
   errors=[(b.translation+d-c.translation).length() for b,c in zip(before,after)]
   rawerrors=[(b.translation+d-c.translation).length() for b,c in zip(raw,newraw)]
   assert max(errors)<.01 and max(rawerrors)<.01,(errors,rawerrors)
   assert list(times)==list(nt) and list(rt)==list(nrt)
   assert all(abs(sum(getattr(b.rotation,k)*getattr(c.rotation,k) for k in ('x','y','z','w')))>.999999 for b,c in zip(before,after))
   assert api.set_locomotion_root_window_location(a,target)
   s['rows'].append(dict(stage='window_shift',max_error=max(errors),raw_error=max(rawerrors)))
   s.update(phase='shift_follow',time=t,target=target)
  elif s['phase']=='shift_follow' and t-s['time']>.15:
   near(a.get_root_low_point(),s['target'],.1)
   s['rows'].append(dict(stage='shift_survives_policy_boundary',error=(a.get_root_low_point()-s['target']).length()))
   lin(a,unreal.Vector(60,-20,6));ang(a,45);s.update(phase='motion_warm',time=t)
  elif s['phase']=='motion_warm' and t-s['time']>.15:
   s.update(phase='motion',time=t,origin=a.get_root_low_point(),yaw=a.get_actor_rotation().yaw)
  elif s['phase']=='motion' and t-s['time']>.5:
   elapsed=t-s['time'];delta=a.get_root_low_point()-s['origin'];expected=unreal.Vector(60,-20,6)*elapsed
   near(delta,expected,.1)
   dy=(a.get_actor_rotation().yaw-s['yaw']+180)%360-180
   assert abs(dy-45*elapsed)<.1,(dy,elapsed)
   r,ts=roots(a);future_error=max((v.translation-r[0].translation-unreal.Vector(60,-20,6)*tm).length() for v,tm in zip(r,ts))
   assert future_error<.1,future_error
   s['rows'].append(dict(stage='independent_world_motion',seconds=elapsed,delta=xyz(delta),expected=xyz(expected),yaw=dy,future_error=future_error))
   lin(a,zero);ang(a,0);s.update(phase='clear_warm',time=t)
  elif s['phase']=='clear_warm' and t-s['time']>.15:
   s.update(phase='clear',time=t,origin=a.get_root_low_point(),yaw=a.get_actor_rotation().yaw)
  elif s['phase']=='clear' and t-s['time']>.2:
   near(a.get_root_low_point(),s['origin'],.1);assert abs(a.get_actor_rotation().yaw-s['yaw'])<.1
   s['rows'].append(dict(stage='clear_has_no_residual_momentum',passed=True))
   s.update(phase='gates',case=0,time=t)
   s['cases']=[(49,0,50,20,True),(50,0,50,20,True),(51,0,50,20,False),(0,-21,50,20,False),(0,-20,50,20,True),(0,0,50,20,True),(100,100,10000,10000,True)]
   lv,av,lt,at,expected=s['cases'][0];lin(a,unreal.Vector(lv,0,0));ang(a,av);balance(a,True,lt,at)
  elif s['phase']=='gates' and t-s['time']>.12:
   lv,av,lt,at,expected=s['cases'][s['case']]
   state=api.get_root_self_balancing_state(a)
   assert state[0] and state[1]==expected,(s['case'],state,expected)
   s['rows'].append(dict(stage='gate',linear=lv,angular=av,linear_threshold=lt,angular_threshold=at,active=state[1]))
   s['case']+=1;s['time']=t
   if s['case']==len(s['cases']):
    for p in s['actors']:lin(p,zero);ang(p,0);balance(p,False)
    unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.MeshAudit')
    audit=json.loads((out.parent/'DefaultJoltMeshes/World.json').read_text(encoding='utf-8-sig'))
    assert not audit['shared_stopped'] and not audit['shared_error'],audit
    s['rows'].append(dict(stage='jolt_health',steps=audit['completed_steps']))
    finish()
   else:
    lv,av,lt,at,expected=s['cases'][s['case']];lin(a,unreal.Vector(lv,0,0));ang(a,av);balance(a,True,lt,at)
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
