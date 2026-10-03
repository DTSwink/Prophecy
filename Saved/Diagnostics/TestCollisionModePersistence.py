import unreal,json,pathlib,time,traceback,itertools
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
s=dict(start=time.monotonic(),phase='setup',rows=[])
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CollisionModePersistence.json'
def ok(x):
 assert x is not None,x
def pairs(a):
 result={}
 for x,y in itertools.combinations(s['bones'],2):
  v=a.get_jolt_body_pair_self_collision_enabled(x,y)
  assert v is not None,(x,y)
  result[x+'|'+y]=bool(v[0])
 return result
def cycle(next_phase):
 assert s['a'].set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
 s.update(phase='kinematic',next=next_phase)
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 out.write_text(json.dumps(dict(result='failed' if error else 'passed',error=error,rows=s['rows']),indent=2))
 if ed.get_game_world():level.editor_request_end_play()
 print('COLLISION_MODE_PERSISTENCE',error or 'passed')
def tick(_):
 try:
  assert time.monotonic()-s['start']<100,'Timeout'
  w=ed.get_game_world()
  if not w:return
  if unreal.GameplayStatics.get_time_seconds(w)<.5:return
  if s['phase']=='setup':
   a=unreal.GameplayStatics.get_player_pawn(w,0);s['a']=a
   assert isinstance(a,unreal.ProphecyAgent)
   a.stop_nn_attack()
   assert a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.PHYSICAL)
   s['phase']='ready';return
  a=s['a']
  if s['phase']=='kinematic':
   assert a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.PHYSICAL)
   s['phase']='wait';return
  if not a.is_jolt_physical_animation_enabled():return
  if s['phase']=='wait':s['phase']=s['next']
  if s['phase']=='ready':
   mesh=a.get_pose_reference_mesh()
   s['bones']=[str(mesh.get_bone_name(i)) for i in range(mesh.get_num_bones()) if a.get_physical_body_state(mesh.get_bone_name(i)) is not None]
   assert len(s['bones'])==22,s['bones']
   ok(a.reset_jolt_self_collision());s['base']=pairs(a)
   ok(a.set_jolt_body_pair_self_collision_enabled('hand_l','foot_r',False))
   ok(a.set_jolt_bodies_self_collision_enabled(['hand_r'],False))
   ok(a.set_jolt_self_collision_below('calf_l',False,True))
   ok(unreal.ProphecyFootColliderLibrary.set_foot_collider_front_trim(a,4.))
   s['modified']=pairs(a)
   assert s['modified']!=s['base']
   assert a.set_jolt_body_pair_self_collision_enabled('no_such_bone','head',False) is None
   cycle('check_modified')
  elif s['phase']=='check_modified':
   assert pairs(a)==s['modified'],'Pair/body/subtree overrides lost'
   s['rows'].append(dict(stage='pair_body_subtree_recreated',pairs=len(s['modified']),passed=True))
   ok(a.set_jolt_self_collision_enabled(False));assert not any(pairs(a).values())
   cycle('check_global')
  elif s['phase']=='check_global':
   assert not any(pairs(a).values()),'Global disable lost'
   ok(a.set_jolt_self_collision_enabled(True));assert pairs(a)==s['modified'],'Underlying exclusions lost under global off'
   # Pair identities are unordered; undo only that pair and preserve other exclusions.
   ok(a.set_jolt_body_pair_self_collision_enabled('foot_r','hand_l',True))
   s['partial']=pairs(a);assert s['partial']!=s['modified']
   s['rows'].append(dict(stage='global_and_reverse_pair_enable',passed=True))
   cycle('check_partial')
  elif s['phase']=='check_partial':
   assert pairs(a)==s['partial'],'Pair re-enable was not retained'
   ok(a.reset_jolt_self_collision());assert pairs(a)==s['base']
   cycle('check_reset')
  elif s['phase']=='check_reset':
   assert pairs(a)==s['base'],'Reset resurrected exclusions'
   ok(unreal.ProphecyFootColliderLibrary.set_foot_collider_front_trim(a,0.))
   s['rows'].append(dict(stage='reset_preserves_authored_PHAT_across_recreation',passed=True))
   finish()
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
print('COLLISION_MODE_PERSISTENCE_STARTED')
