import unreal,json,pathlib,time,traceback,sys
mode=sys.argv[1] if len(sys.argv)>1 else 'parry'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert ed.get_game_world() is None,'Do not interrupt user Play'
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SpecialSnapshot20261006'/('live_'+mode+'.json')
s={'world':None,'last':None,'start':time.monotonic(),'rows':[],'configured':False,'started':False}
def values(a):
 m=a.get_body_magnetization_settings('head');f=a.get_physical_feedback_tolerance('head')
 return {'mag':[m.linear_strength_scale,m.angular_strength_scale], 'feedback':[f.linear_tolerance_cm,f.angular_tolerance_degrees],'damping':unreal.ProphecyJointDampingLibrary.get_jolt_joint_angular_damping(a,'head')}
def setup(a):
 a.set_body_magnetization('head',True,.23,.43);a.set_physical_feedback_tolerance('head',8,23);a.set_locomotion_foot_clamp(True,3)
 damp=unreal.ProphecyJointDampingLibrary.set_jolt_joint_angular_damping(a,'head',6)
 assert unreal.ProphecyPhysicalProfileLibrary.save_physical_profile_snapshot(a,'1')
 saved=values(a)
 a.set_body_magnetization('head',True,.9,.9);a.set_physical_feedback_tolerance('head',80,90);a.set_locomotion_foot_clamp(True,83)
 if damp is not None:unreal.ProphecyJointDampingLibrary.set_jolt_joint_angular_damping(a,'head',96)
 unreal.ProphecyPhysicalProfileLibrary.blend_body_magnetization_to_snapshot(a,'head',10,'1')
 unreal.ProphecyPhysicalProfileLibrary.blend_physical_feedback_tolerance_to_snapshot(a,'head',10,'1')
 if damp is not None:unreal.ProphecyPhysicalProfileLibrary.blend_joint_angular_damping_to_snapshot(a,'head',10,'1')
 unreal.ProphecyClampProfileLibrary.blend_all_clamps_to_snapshot(a,10,'1')
 return {'saved':saved,'perturbed':values(a),'damping_set_result':damp}
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 out.write_text(json.dumps({'mode':mode,'reason':reason,'setup':s.get('setup'),'defense_request':s.get('defense_request'),'rows':s['rows']},indent=2))
 if s['world'] and ed.get_game_world()==s['world']:level.editor_request_end_play()
 print('SPECIAL_SNAPSHOT_LIVE_DONE',mode,reason)
def tick(_):
 try:
  if time.monotonic()-s['start']>100:finish('timeout');return
  w=ed.get_game_world()
  if not w:return
  a=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(a,unreal.ProphecyAgent):return
  n=int(a.get_editor_property('tick debug'))
  if n==s['last']:return
  s['last']=n;s['world']=w
  v=next((x for x in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent) if x.get_actor_label()=='BP_ProphecyManualPoseAgent4'),None)
  if v is None:return
  if not s.get('flags'):
   for key,val in [('bool debug 1',True),('bool debug 2',mode=='parry')]:unreal.get_default_object(unreal.SystemLibrary).call_method('SetBoolPropertyByName',(a,key,val))
   s['flags']=True
  attack=a.get_nn_attack_state()
  if n>=20 and not s['configured']:
   assert not attack,'Setup arrived after attack; no meaningful entry comparison'
   s['setup']={'attacker':setup(a),'defender':setup(v)};s['configured']=True
  if s['configured']:
   d=unreal.ProphecyNNDefenseLibrary.get_nn_defense_status(v)
   s['rows'].append({'tick':n,'attack_frame':attack[4] if attack else None,'attack':str(attack[0]) if attack else None,'mode':str(unreal.ProphecyNNDefenseLibrary.get_agent_state(v)),'defense':bool(d and d.active),'attacker':values(a),'defender':values(v)})
   if attack and not s['started']:
    s['defense_request']=(unreal.ProphecyNNDefenseLibrary.start_nn_parry(v,a) if mode=='parry' else unreal.ProphecyNNDefenseLibrary.start_nn_dodge(v,a))
   if attack:s['started']=True
   if s['started'] and not attack:finish('complete');return
  if n>=200:finish('no attack')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play();print('SPECIAL_SNAPSHOT_LIVE_STARTED',mode)
