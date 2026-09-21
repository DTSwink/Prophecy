import unreal,pathlib,json,time,traceback,math
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world()
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CombatDemo'
s=dict(start=time.monotonic(),rows=[],launches=[],phase='dodge',last_frame=-1,last_attack_frame=-1)
def finish(result,error=''):
 unreal.unregister_slate_post_tick_callback(s['callback'])
 if ed.get_game_world():level.editor_request_end_play()
 (folder/'PIE.json').write_text(json.dumps(dict(result=result,error=error,rows=s['rows'],launches=s['launches']),indent=2))
 print('COMBAT_DEMO_TEST',result,error)
def tick(dt):
 try:
  assert time.monotonic()-s['start']<120,'Timeout'
  w=ed.get_game_world()
  if not w:return
  if 'a' not in s:
   actors=list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent))
   players=[a for a in actors if a.is_player_controlled()]
   if not players:return
   a=players[0];d=a.get_editor_property('CombatDemoOpponent')
   if not d or not a.get_editor_property('CombatDemoInitialized') or not d.get_editor_property('CombatDemoInitialized'):return
   s.update(a=a,d=d)
  a=s['a'];d=s['d'];f=a.get_editor_property('CombatDemoFrame')
  if f==s['last_frame']:return
  s['last_frame']=f
  if f<5:return # Let the existing queued Jolt-to-kinematic restoration finish.
  assert a.get_simulation_mode()==d.get_simulation_mode()==unreal.ProphecyAgentSimulationMode.KINEMATIC,(f,str(a.get_simulation_mode()),str(d.get_simulation_mode()))
  for actor in (a,d):
   cube=next(c for c in actor.get_components_by_class(unreal.StaticMeshComponent) if c.get_name()=='magic Cube')
   assert cube.get_collision_enabled()==unreal.CollisionEnabled.NO_COLLISION,(actor.get_name(),str(cube.get_collision_enabled()))
  state=a.get_nn_attack_state();defense=unreal.ProphecyNNDefenseLibrary.get_nn_defense_status(d)
  if f%60==0:
   error=a.get_editor_property('CombatDemoError');assert not error,error
   assert state and defense,(state,defense)
   s['launches'].append(dict(frame=f,attack=str(a.get_editor_property('CombatDemoLastAttack')),mode=s['phase'],attacker_frame=state[-1],defense_steps=defense.completed_steps))
  if f%4==0:
   points={}
   for label,actor in [('a',a),('d',d)]:
    for bone in ['head','hand_r','foot_l','pelvis']:
     target=actor.get_authored_body_world_target(bone);assert target
     p=target[1].translation;assert all(math.isfinite(x) for x in (p.x,p.y,p.z))
     points[label+'_'+bone]=[p.x,p.y,p.z]
   s['rows'].append(dict(frame=f,mode=s['phase'],attack_frame=state[-1] if state else -1,defense_steps=defense.completed_steps if defense else 0,defense_frame=defense.attacker_frame if defense else -1,defense_active=defense.active if defense else False,harmful=defense.harmful_contact if defense else False,blocked=defense.blocked if defense else False,points=points))
   if defense and defense.active and defense.completed_steps>0:assert defense.attacker_frame==state[-1]
  if f>=245 and s['phase']=='dodge':
   a.set_editor_property('CombatDemoUseDodge',False);s['phase']='parry'
  if f>=425:
   assert len(s['launches'])==7,s['launches']
   assert all(b['frame']-a['frame']==60 for a,b in zip(s['launches'],s['launches'][1:]))
   for mode in ['dodge','parry']:assert any(r['mode']==mode and r['defense_steps']>0 for r in s['rows']),mode
   finish('passed')
 except Exception:finish('failed',traceback.format_exc())
s['callback']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
