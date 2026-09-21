import unreal,json,pathlib,time,traceback,math
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world()
api=unreal.ProphecyRootPhysicsLibrary;s={'start':time.monotonic(),'phase':'setup','rows':[]}
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RootFreeImpulseAfterFacingFix.json'
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 if ed.get_game_world():level.editor_request_end_play()
 out.write_text(json.dumps(dict(error=error,rows=s['rows']),indent=2))
 print('FREE_IMPULSE_FACING_FIX',error or 'passed')
def tick(_):
 try:
  assert time.monotonic()-s['start']<90,'Timeout'
  w=ed.get_game_world()
  if not w:return
  t=unreal.GameplayStatics.get_time_seconds(w);dt=unreal.GameplayStatics.get_world_delta_seconds(w)
  if t<.5:return
  if s['phase']=='setup':
   actors=[a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent) if a.has_valid_agent_handle()]
   for a in actors:
    a.set_editor_property('auto_publish_manual_follower_substep_targets',False);a.set_actor_tick_enabled(False)
    a.stop_nn_attack();a.stop_locomotion_input()
    api.set_root_magic_velocity(a,unreal.Vector(),False);api.set_root_magic_ang_velocity(a,unreal.Vector(),False)
    api.set_root_self_balancing(a,False)
    for c in a.get_components_by_class(unreal.StaticMeshComponent):
     c.set_collision_response_to_all_channels(unreal.CollisionResponseType.ECR_IGNORE)
   player=unreal.GameplayStatics.get_player_pawn(w,0)
   s.update(actors=actors,cases=[a for a in actors if a!=player],phase='settle',time=t)
  for a in s['actors']:a.publish_manual_follower_substep_targets(dt)
  if s['phase']=='settle' and t-s['time']>.3:
   tracking=[]
   for i,a in enumerate(s['cases']):
    if i:a.set_locomotion_input(unreal.Vector(),False,unreal.Vector(0,1,0),1.,1.)
    rate=a.get_root_velocity()[-1].z
    assert abs(rate)<1e-5,rate
    assert api.add_root_angular_impulse(a,unreal.Vector(0,0,22.406),True)
    step=math.radians(900)/30;steps=math.ceil(22.406/step)-1
    expected=math.degrees(steps*(22.406-.5*step*(steps+1))/30)
    tracking.append(dict(agent=a.get_name(),prior_facing=bool(i),last=a.get_actor_rotation().yaw,total=0.,reverse=0.,expected=expected,min_mover_rate=0.))
   s.update(tracking=tracking,phase='impulse',time=t)
  elif s['phase']=='impulse':
   for a,r in zip(s['cases'],s['tracking']):
    yaw=a.get_actor_rotation().yaw;delta=(yaw-r['last']+180)%360-180
    r['last']=yaw;r['total']+=delta;r['reverse']+=max(0.,-delta)
    r['min_mover_rate']=min(r['min_mover_rate'],a.get_root_velocity()[-1].z)
   if t-s['time']>4:
    s['rows']=s['tracking']
    for a,r in zip(s['cases'],s['tracking']):
     assert abs(r['total']-r['expected'])<.1,r
     # The untouched no-facing path is the control for this change. Both paths
     # must preserve the stopping heading and avoid any full-turn unwind.
     assert r['reverse']<10.,r
     assert abs(a.get_root_velocity()[-1].z)<1e-5
    control,held=s['tracking']
    assert abs(control['total']-held['total'])<.01
    assert abs(control['reverse']-held['reverse'])<.01
    assert abs(control['min_mover_rate']-held['min_mover_rate'])<.001
    finish()
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
