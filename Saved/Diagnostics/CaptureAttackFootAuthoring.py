import unreal,pathlib,json,time,traceback
unreal.load_module('GameAnimationSample3')
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyAttackFootLocomotionLibrary'))
inertia=unreal.get_default_object(unreal.ProphecyAttackStartInertiaLibrary)
block=unreal.get_default_object(unreal.ProphecyGhostAttackLibrary)
modes=[0,1,2,0]
def configure(w,enabled,mode,distance,height):
 assert api.call_method('SetAttackFootLocomotion',(unreal.GameplayStatics.get_player_pawn(w,0),enabled,unreal.ProphecyAttackFootLocomotionMode.cast(mode),distance,height))
s=dict(wall=time.monotonic(),last=None,frame=0,rows=[],events=[])
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 w=ed.get_game_world()
 if w:unreal.SystemLibrary.execute_console_command(w,'Prophecy.AttackPerf.Capture stop')
 pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/FootAuthoringLive.json').write_text(json.dumps(dict(error=error,rows=s['rows'],events=s['events']),separators=(',',':')))
 if w:level.editor_request_end_play()
 print('FOOT_AUTHORING_LIVE_DONE',error or 'passed',len(s['rows']))
def tick(_):
 try:
  assert time.monotonic()-s['wall']<100,'Timeout'
  w=ed.get_game_world()
  if not w:return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t;s['frame']+=1;f=s['frame']
  a=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(a,unreal.ProphecyAgent):return
  if f==20:
   for other in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
    other.set_actor_tick_enabled(False);other.stop_nn_attack()
    if other!=a:other.set_editor_property('bNNInferenceEnabled',False)
   assert inertia.call_method('SetAttackStartPelvisInertia',(a,False,5,1.,5,1.))
   assert inertia.call_method('SetAttackStartFootInertia',(a,True,8,1.,8,1.))
   assert block.call_method('SetAttackArmedBlocked',(a,True))
   a.set_locomotion_policy_blend_times(2.,2.)
   unreal.SystemLibrary.execute_console_command(w,'Prophecy.AttackPerf.Capture foot_authoring_live 340')
  if f<40:return
  case=(f-40)//70;offset=(f-40)%70
  if case>=4:finish();return
  mode=modes[case]
  if offset==0:
   a.stop_nn_attack();a.set_locomotion_input(unreal.Vector(0,1,0),case==1,unreal.Vector(0,1,0),1.,1.)
   pelvis=a.read_nn_future_world_pose()[1][0].translation
   target=pelvis+unreal.Vector(0,200,0);dist=0.;height=0.
   if case==3:
    names,_,pose,_=a.read_nn_future_world_pose();idx={str(n):i for i,n in enumerate(names)}
    delta=pose[idx['foot_l']].translation-pelvis
    length=(delta.x*delta.x+delta.y*delta.y)**.5
    assert length>1
    dist=length*.5;height=10000.
    target=pelvis+unreal.Vector(-delta.x/length*200,-delta.y/length*200,0)
   configure(w,True,mode,dist,height)
   assert a.trigger_nn_attack('hookL',target,False,None)
   owners=api.call_method('GetAttackFootLocomotion',(a,))
   assert any(owners) if case==3 else owners==(True,True)
  if offset==25 and case<3:
   # Explicit disable releases both pending feet, and starts their delayed inertia.
   configure(w,False,mode,0.,0.)
  if offset==35 and case<3:
   # Configuration alone cannot reopen the completed attack's ownership.
   configure(w,True,mode,0.,0.)
  if offset==55:a.stop_nn_attack()
  owners=api.call_method('GetAttackFootLocomotion',(a,));attack=a.get_nn_attack_state()
  if 4<=offset<25 and case<3:
   assert attack and not attack[1],('Full attack required',f,attack)
   assert owners==(True,True),(f,owners)
   weights=a.get_locomotion_checkpoint_weights()
   if case<2:assert abs(weights[0]-(1 if case==0 else 0))<1.e-5,(case,weights)
   else:assert 0.<weights[0]<1.,('Expected continued fractional blend',offset,weights)
  if 35<=offset<55:assert owners==(False,False),(f,owners)
  api.call_method('DrawAttackFootLocomotion',(a,0.))
  names,_,pose,_=a.read_nn_future_world_pose();idx={str(n):i for i,n in enumerate(names)}
  if case==3 and 10<=offset<30 and any(owners):
   pelvis=pose[0].translation;foot=pose[idx['foot_l' if owners[0] else 'foot_r']].translation
   delta=foot-pelvis;length=max(1.,(delta.x*delta.x+delta.y*delta.y)**.5)
   a.set_nn_attack_target(pelvis+unreal.Vector(-delta.y/length*200,delta.x/length*200,0))
  feet=[[pose[idx[b]].translation.x,pose[idx[b]].translation.y,pose[idx[b]].translation.z] for b in ('foot_l','foot_r')]
  s['rows'].append(dict(frame=f,time=t,case=case,offset=offset,owners=owners,attack=str(attack),weights=list(a.get_locomotion_checkpoint_weights()),feet=feet))
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
