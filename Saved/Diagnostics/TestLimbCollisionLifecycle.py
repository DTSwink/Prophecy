import unreal,json,pathlib,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world()
# Live Coding exposes the new class to Blueprint reflection before Python regenerates glue.
cdo=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyLimbCollisionLibrary'))
class ReflectedAPI:
 def __getattr__(self,name):
  fn=''.join(part.capitalize() for part in name.split('_'))
  return lambda *args:cdo.call_method(fn,args)
api=ReflectedAPI();defense=unreal.ProphecyNNDefenseLibrary
# Use an already wrapped channel for this generic filter test. The new Leg label was
# separately verified by ReloadChannels; this session's Python enum still predates it.
leg=unreal.CollisionChannel.ECC_VEHICLE
ignore=unreal.CollisionResponseType.ECR_IGNORE
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/LimbCollisionLifecycle.json'
s={'start':time.monotonic(),'phase':'setup','rows':[]}
def get(a,b='thigh_r'):return api.get_jolt_limb_collision_response(a,b,leg)
def mod(a):
 assert api.set_jolt_limb_collision_channel(a,'thigh_r',leg,True) is not None
 assert api.set_jolt_limb_collision_response(a,'thigh_r',leg,ignore,True) is not None
def check(a,active):
 for bone in s['bones']:
  x=get(a,bone);base=s['base'][a.get_name()][bone]
  assert x is not None,(bone,x)
  assert x[2] and x[3]==active,(bone,x,active)
  assert (x[0]==leg and x[1]==ignore) if active else x[:2]==base[:2],(bone,x,base,active)
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 if ed.get_game_world():level.editor_request_end_play()
 out.write_text(json.dumps(dict(result='failed' if error else 'passed',error=error,rows=s['rows']),indent=2))
 print('LIMB_COLLISION_LIFECYCLE',error or 'passed')
def tick(_):
 try:
  assert time.monotonic()-s['start']<150,'Timeout'
  w=ed.get_game_world()
  if not w:return
  t=unreal.GameplayStatics.get_time_seconds(w);dt=unreal.GameplayStatics.get_world_delta_seconds(w)
  if t<.5:return
  if s['phase']=='setup':
   actors=[a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent) if a.has_valid_agent_handle()]
   assert len(actors)==3
   for a in actors:
    a.set_editor_property('auto_publish_manual_follower_substep_targets',False);a.set_actor_tick_enabled(False)
    a.stop_nn_attack();defense.stop_nn_defense(a);a.stop_locomotion_input()
   a,d=actors[:2];other=actors[2]
   bones=['thigh_r','calf_r','foot_r']
   base={p.get_name():{b:get(p,b) for b in bones} for p in (a,d)}
   s.update(a=a,d=d,other=other,actors=actors,bones=bones,base=base)
   assert all(x is not None for row in base.values() for x in row.values()),base
   mod(a);mod(d)
   assert all(b in [str(x) for x in api.get_modified_limb_collision_bones(a)] for b in bones)
   assert not api.get_modified_limb_collision_bones(other)
   check(a,True);check(d,True)
   assert not get(a,'hand_r')[2]
   before=[str(x) for x in api.get_modified_limb_collision_bones(a)]
   assert api.set_jolt_limb_collision_channel(a,'no_such_bone',leg,False) is None
   assert before==[str(x) for x in api.get_modified_limb_collision_bones(a)]
   s['rows'].append(dict(stage='locomotion',bones=before,other_agent_unchanged=True,invalid_atomic=True))
   for p in (a,d):
    if not p.get_held_sword():assert p.equip_sword(False)
   s.update(phase='attack_start',time=t)
  for p in s.get('actors',[]):p.publish_manual_follower_substep_targets(dt)
  a,d=s['a'],s['d']
  if s['phase']=='attack_start' and t-s['time']>.2:
   assert a.trigger_nn_attack('slashRU',d.get_authored_body_world_target('spine_03')[1].translation,False)
   s.update(phase='attack',time=t)
  elif s['phase']=='attack' and t-s['time']>.08:
   assert a.get_nn_attack_state()[0];check(a,False);check(d,True)
   s['rows'].append(dict(stage='attack_restores_originals',passed=True))
   assert defense.start_nn_parry(d,a,unreal.ProphecyParryBlocker.BLADE,2.) is not None
   s.update(phase='parry',time=t)
  elif s['phase']=='parry' and t-s['time']>.05:
   assert defense.get_nn_defense_status(d).active;check(d,False)
   s['rows'].append(dict(stage='parry_restores_originals',passed=True))
   defense.stop_nn_defense(d);a.stop_nn_attack();s.update(phase='resume',time=t)
  elif s['phase']=='resume' and t-s['time']>.1:
   check(a,True);check(d,True)
   s['rows'].append(dict(stage='locomotion_reapplies_after_attack_parry',passed=True))
   assert a.trigger_nn_attack('slashRU',d.get_authored_body_world_target('spine_03')[1].translation,False)
   assert defense.start_nn_dodge(d,a,2.) is not None
   s.update(phase='dodge',time=t)
  elif s['phase']=='dodge' and t-s['time']>.06:
   assert defense.get_nn_defense_status(d).active;check(a,False);check(d,False)
   s['rows'].append(dict(stage='dodge_restores_originals',passed=True))
   defense.stop_nn_defense(d);a.stop_nn_attack();s.update(phase='finish',time=t)
  elif s['phase']=='finish' and t-s['time']>.1:
   check(a,True);check(d,True)
   for p in (a,d):
    assert api.reset_jolt_limb_collision(p,'thigh_r',True) is not None
    assert not api.get_modified_limb_collision_bones(p)
    for b in s['bones']:
     x=get(p,b);assert x[:2]==s['base'][p.get_name()][b][:2] and not x[2],(b,x)
   s['rows'].append(dict(stage='resume_and_reset_remove_tracking',passed=True))
   unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.MeshAudit')
   audit=json.loads((out.parent/'DefaultJoltMeshes/World.json').read_text(encoding='utf-8-sig'))
   assert not audit['shared_stopped'] and not audit['scene_error'],audit
   s['rows'].append(dict(stage='healthy_shared_world',steps=audit['completed_steps']))
   finish()
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
