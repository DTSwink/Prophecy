import unreal,json,pathlib,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world()
s={'start':time.monotonic(),'rows':[],'seen':False};folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/DodgeMismatch';folder.mkdir(parents=True,exist_ok=True)
def v(x):return [x.x,x.y,x.z]
def tr(t):q=t.rotation;return dict(p=v(t.translation),q=[q.x,q.y,q.z,q.w])
def sample(a):
 pose=a.read_nn_future_world_pose();mesh=a.get_pose_reference_mesh()
 r=dict(name=a.get_name(),root=v(a.get_root_low_point()),rotation=str(a.get_actor_rotation()),mode=str(a.get_simulation_mode()),input=str(a.get_editor_property('LocomotionInput')))
 if pose:r.update(names=[str(n) for n in pose[0]],future=[tr(t) for t in pose[1]],visible=[tr(t) for t in pose[2]],alpha=pose[3])
 r['mesh']={b:tr(mesh.get_socket_transform(b,unreal.RelativeTransformSpace.RTS_WORLD)) for b in ['head','pelvis','hand_l','hand_r']}
 return r
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['handle']);level.editor_request_end_play()
 (folder/'corrected_ue.json').write_text(json.dumps(dict(error=error,rows=s['rows']),separators=(',',':')))
 print('DODGE_MISMATCH_CAPTURE',len(s['rows']),error)
def tick(dt):
 try:
  w=ed.get_game_world()
  if not w:return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if time.monotonic()-s['start']>90:raise RuntimeError('timeout')
  if 'a' not in s:
   actors=list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent))
   a=next((a for a in actors if a.is_player_controlled() and a.has_valid_agent_handle()),None)
   if not a:return
   d=a.get_editor_property('CombatDemoOpponent')
   if not d or not d.has_valid_agent_handle():return
   s.update(a=a,d=d)
  a,d=s['a'],s['d'];attack=a.get_nn_attack_state();status=unreal.ProphecyNNDefenseLibrary.get_nn_defense_status(d)
  if attack:s['seen']=True
  r=dict(time=t,frame=a.get_editor_property('CombatDemoFrame'),a=sample(a),d=sample(d),attack=[str(attack[0])]+list(attack[1:]) if attack else None,target=[v(p) for p in a.get_nn_attack_target()] if a.get_nn_attack_target() else None)
  if status:r['defense']=dict(active=status.active,steps=status.completed_steps,frame=status.attacker_frame,harmful=status.harmful_contact,blocked=status.blocked,contact=str(status.contact_collider),contact_time=status.contact_time_seconds)
  s['rows'].append(r)
  if (s['seen'] and (not attack or (len(s['rows'])>2 and attack[-1]<s.get('last',-1)))) or t>5.5:finish()
  elif attack:s['last']=attack[-1]
 except Exception:finish(traceback.format_exc())
s['handle']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
