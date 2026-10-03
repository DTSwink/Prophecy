import unreal,pathlib,json,time,math,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyAttackFootLocomotionLibrary'))
inertia=unreal.get_default_object(unreal.ProphecyAttackStartInertiaLibrary)
block=unreal.get_default_object(unreal.ProphecyGhostAttackLibrary)
s=dict(start=time.monotonic(),last=None,n=0,rows=[])
def config(a,distance):
 assert api.call_method('SetAttackFootLocomotion',(a,True,unreal.ProphecyAttackFootLocomotionMode.RUN,distance,10000.,0.,.3,.2,.5))
def pose(a):
 names,future,current,_=a.read_nn_future_world_pose();return {str(b):t for b,t in zip(names,current)}
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 w=ed.get_game_world()
 if w:unreal.SystemLibrary.execute_console_command(w,'Prophecy.AttackPerf.Capture stop')
 pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/LocoDragHandoff.json').write_text(json.dumps(dict(error=error,rows=s['rows']),indent=2))
 if w:level.editor_request_end_play()
 print('LOCO_DRAG_HANDOFF',error or 'passed',len(s['rows']))
def tick(_):
 try:
  assert time.monotonic()-s['start']<100,'Timeout'
  w=ed.get_game_world()
  if not w:return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t;s['n']+=1;n=s['n']
  a=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(a,unreal.ProphecyAgent):return
  if n==20:
   for other in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
    other.set_actor_tick_enabled(False);other.stop_nn_attack()
    if other!=a:other.set_editor_property('bNNInferenceEnabled',False)
   inertia.call_method('SetAttackStartPelvisInertia',(a,False,5,1.,5,1.))
   inertia.call_method('SetAttackStartFootInertia',(a,False,5,1.,5,1.))
   a.set_locomotion_policy_blend_times(0.,0.)
   a.set_locomotion_input(unreal.Vector(0,1,0),True,unreal.Vector(0,1,0),.4,1.)
  if n==30:
   config(a,10000.);block.call_method('SetAttackArmedBlocked',(a,True))
   assert a.trigger_nn_attack('hookL',pose(a)['pelvis'].translation+unreal.Vector(0,200,0),False,None)
   assert api.call_method('GetAttackFootLocomotion',(a,))==(False,False),'Direct attack foot blended'
  if n==34:a.stop_nn_attack()
  if n==40:
   config(a,0.);block.call_method('SetAttackArmedBlocked',(a,True))
   p=pose(a);pelvis=p['pelvis'].translation;delta=p['foot_l'].translation-pelvis;delta.z=0
   length=math.hypot(delta.x,delta.y);assert length>1
   assert a.trigger_nn_attack('hookL',pelvis-delta*(200/length),False,None)
   assert api.call_method('GetAttackFootLocomotion',(a,))[0],'Left must start loco'
   unreal.SystemLibrary.execute_console_command(w,'Prophecy.AttackPerf.Capture loco_drag_handoff 140')
  if 45<=n<=60 or 80<=n<=95:
   p=pose(a);pelvis=p['pelvis'].translation
   delta=p['foot_l' if n<=60 else 'foot_r'].translation-pelvis;delta.z=0
   length=math.hypot(delta.x,delta.y)
   if length>1:a.set_nn_attack_target(pelvis+delta*(200/length))
  if 40<=n<=140:
   p=pose(a);owners=api.call_method('GetAttackFootLocomotion',(a,));attack=a.get_nn_attack_state()
   assert attack and not attack[1],('Attack ended',n)
   assert all(math.isfinite(v) for bone in ('foot_l','foot_r','calf_l','calf_r') for v in (p[bone].translation.x,p[bone].translation.y,p[bone].translation.z))
   s['rows'].append(dict(frame=n,owners=list(owners),feet=[[p[b].translation.x,p[b].translation.y,p[b].translation.z] for b in ('foot_l','foot_r')]))
   if n>=135:assert owners==(False,False),('Blend failed to release',n,owners)
  if n==142:finish()
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
