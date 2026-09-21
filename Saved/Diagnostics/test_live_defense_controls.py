import unreal,pathlib,json,time,traceback,math
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world()
D=unreal.ProphecyNNDefenseLibrary;R=unreal.ProphecyRootPhysicsLibrary
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/LiveDefenseControls';folder.mkdir(parents=True,exist_ok=True)
s=dict(start=time.monotonic(),phase='setup',rows=[],cases=[])
def point(a):return a.get_authored_body_world_target('head')[1].translation
def finish(result,error=''):
 unreal.unregister_slate_post_tick_callback(s['callback'])
 if ed.get_game_world():level.editor_request_end_play()
 (folder/'PIE.json').write_text(json.dumps(dict(result=result,error=error,rows=s['rows'],cases=s['cases']),indent=2))
 print('LIVE_DEFENSE_CONTROLS',result,error)
def feet_midpoint(a):
 mesh=a.get_pose_reference_mesh()
 p=(mesh.get_socket_location('foot_l')+mesh.get_socket_location('foot_r'))*.5
 p.z=a.get_root_low_point().z
 return p

def check_handoff(a,stop):
 expected=feet_midpoint(a)
 mesh=a.get_pose_reference_mesh()
 before=[mesh.get_socket_location(n) for n in ['pelvis','head','hand_l','hand_r','foot_l','foot_r']]
 stop()
 err=(a.get_root_low_point()-expected).length()
 after=[mesh.get_socket_location(n) for n in ['pelvis','head','hand_l','hand_r','foot_l','foot_r']]
 pose_err=max((x-y).length() for x,y in zip(before,after))
 assert err<.01,('return root midpoint',err)
 assert pose_err<.02,('return moved world pose',pose_err)
 s['cases'].append(dict(handoff_root_error_cm=err,handoff_pose_error_cm=pose_err))

def launch(mode):
 a,d=s['a'],s['d'];D.stop_nn_defense(d);a.stop_nn_attack();d.stop_nn_attack();d.stop_locomotion_input()
 target=point(a)+a.get_actor_forward_vector()*90
 assert a.trigger_nn_attack('headbutt',target,False,d)
 assert a.get_nn_attack_victim()==d
 before=a.get_nn_attack_state();assert before and not before[2]
 target+=unreal.Vector(0,2,0)
 assert a.set_nn_attack_target(target)
 assert a.get_nn_attack_state()==before,'retarget reset attack state'
 assert (a.get_nn_attack_target()[0]-target).length()<.001
 result=D.start_nn_dodge(d,a,3.) if mode=='dodge' else D.start_nn_parry(d,a,unreal.ProphecyParryBlocker.RIGHT_ARM,3.)
 assert result is not None
 assert tuple(a.get_nn_attack_defense_state())==((False,True) if mode=='dodge' else (True,False)),a.get_nn_attack_defense_state()
 assert not D.get_nn_defense_status(d).active
 R.set_root_magic_velocity(d,unreal.Vector(100,0,0),False)
 R.set_root_magic_ang_velocity(d,unreal.Vector(0,0,20),False)
 s.update(phase=mode,last=-1,seen_armed=False,steps=0,target=target,flipped=False,launched=time.monotonic())
def tick(dt):
 try:
  assert time.monotonic()-s['start']<100,'Timeout'
  w=ed.get_game_world()
  if not w:return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if s['phase']=='setup':
   if t<.4:return
   actors=[a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent) if a.has_valid_agent_handle()]
   a=next(a for a in actors if a.is_player_controlled());d=a.get_editor_property('CombatDemoOpponent');assert d
   for p in actors:
    assert p.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
    p.set_actor_tick_enabled(False);p.stop_nn_attack();D.stop_nn_defense(p);p.stop_locomotion_input();p.stop_nn_animation_layer(0)
    for mesh in p.get_components_by_class(unreal.StaticMeshComponent):
     if mesh.get_name()=='magic Cube':
      unreal.ProphecyJoltStaticMeshLibrary.disable_jolt_static_mesh_physics(mesh)
      mesh.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION);mesh.set_simulate_physics(False)
    R.set_root_magic_velocity(p,unreal.Vector(),False);R.set_root_magic_ang_velocity(p,unreal.Vector(),False)
    R.set_root_magic_velocity2(p,unreal.Vector(),False);R.set_root_magic_ang_velocity2(p,unreal.Vector(),False)
    R.set_root_self_balancing(p,False)
    unreal.ProphecyNNRootWindowLibrary.set_locomotion_root_window_smoothing(p,1.,1.,1.)
    p.hide_sword()
   for mode in ['parry','dodge']:
    for limb in ['foot','calf','hand','forearm']:
     node=getattr(D,'set_'+mode+'_'+limb+'_clamp')
     assert node(d,True,2.) and node(d,False,0.)
     assert not node(d,True,-1.)
   assert R.set_locomotion_root_window_location(d,d.get_root_low_point()+unreal.Vector(600,0,0))
   s.update(a=a,d=d,actors=actors,phase='settle',time=t)
  for p in s.get('actors',[]):p.apply_nn_pose_kinematically(dt)
  if s['phase']=='settle':
   if t-s['time']<.15:return
   a,d=s['a'],s['d']
   assert a.trigger_nn_attack('headbutt',point(a)+a.get_actor_forward_vector()*90,False)
   assert a.get_nn_attack_victim() is None
   check_handoff(a,a.stop_nn_attack);assert tuple(a.get_nn_attack_defense_state())==(False,False)
   s['cases'].append('air attack has no victim; eight independent clamp setters accept valid/reject negative leeway')
   launch('dodge');return
  a,d=s['a'],s['d'];attack=a.get_nn_attack_state();status=D.get_nn_defense_status(d)
  assert attack and status,(s['phase'],attack,status)
  if attack[4]==s['last']:return
  s['last']=attack[4]
  before=attack;s['target']+=unreal.Vector(0,.5,0)
  assert a.set_nn_attack_target(s['target']) and a.get_nn_attack_state()==before
  assert a.get_nn_attack_victim()==d
  window=R.get_continuous_locomotion_root_window(d)
  assert window and len(window[0])==9,'continuous window unavailable in defense'
  roots,times=window
  assert all(math.isfinite(v) for x in roots for v in (x.translation.x,x.translation.y,x.translation.z))
  velocity=d.get_root_velocity();assert velocity
  flags=tuple(a.get_nn_attack_defense_state())
  if not attack[2]:assert not status.active and status.completed_steps==0
  if status.active:
   assert attack[2],'defense before Armed'
   assert flags==((False,True) if s['phase']=='dodge' else (True,False))
   s['seen_armed']=True
  s['rows'].append(dict(mode=s['phase'],frame=attack[4],armed=attack[2],steps=status.completed_steps,active=status.active,flags=flags,
    root=[roots[0].translation.x,roots[0].translation.y,roots[0].translation.z],future=[roots[1].translation.x,roots[1].translation.y,roots[1].translation.z],
    velocity=[velocity[0].x,velocity[0].y,velocity[1].z],magic_sign=-1 if s['flipped'] else 1))
  if status.completed_steps>=1 and not s['flipped']:
   R.set_root_magic_velocity(d,unreal.Vector(-100,0,0),False)
   R.set_root_magic_ang_velocity(d,unreal.Vector(0,0,-20),False)
   d.set_locomotion_input(unreal.Vector(0,.2,0),False,unreal.Vector(),1.,1.)
   s['flipped']=True
  if status.completed_steps>=3 or (s['seen_armed'] and not status.active and status.completed_steps):
   assert status.completed_steps>=2,('too-short controlled episode',status.completed_steps)
   check_handoff(d,lambda:D.stop_nn_defense(d));assert tuple(a.get_nn_attack_defense_state())==(False,False)
   # Restart while already armed to check immediate status and independent mode selection.
   s['cases'].append(dict(mode=s['phase'],completed_steps=status.completed_steps,retarget_preserved_state=True,live_window=True))
   if s['phase']=='dodge':launch('parry')
   else:finish('passed')
  assert time.monotonic()-s['launched']<25,'Episode did not advance'
 except Exception:finish('failed',traceback.format_exc())
s['callback']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
