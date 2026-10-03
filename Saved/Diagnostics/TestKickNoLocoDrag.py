import unreal,time,pathlib,json,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
owned=not bool(ed.get_game_world())
s=dict(start=time.monotonic(),last=None,n=0,rows=[],events=[])
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/KickNoLocoDrag.json').write_text(json.dumps(dict(error=error,owned=owned,rows=s['rows'],events=s['events']),default=str))
 if owned and ed.get_game_world():level.editor_request_end_play()
 print('KICK_NO_LOCO_DRAG',error or 'passed',len(s['rows']),'owned',owned)
def tick(_):
 try:
  w=ed.get_game_world()
  if not w:
   if s['n']:finish('User ended Play')
   elif time.monotonic()-s['start']>30:finish('No Play')
   return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t;s['n']+=1;n=s['n']
  a=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(a,unreal.ProphecyAgent):return
  if owned:
   if n==20:
    a.set_actor_tick_enabled(False);a.stop_nn_attack()
    assert unreal.ProphecyAttackFootLocomotionLibrary.set_attack_foot_locomotion(a,True,unreal.ProphecyAttackFootLocomotionMode.CURRENT_BLEND,0.,0.)
    assert unreal.ProphecyAttackStartInertiaLibrary.set_attack_start_foot_inertia(a,True,10,1.,10,1.)
   if n in (30,60,90):
    a.stop_nn_attack()
    target=a.read_nn_future_world_pose()[1][0].translation+unreal.Vector(0,160,0)
    attack={30:'kickl',60:'kickr',90:'hookL'}[n]
    assert a.trigger_nn_attack(attack,target,False,None)
    owners=unreal.ProphecyAttackFootLocomotionLibrary.get_attack_foot_locomotion(a)
    assert owners==((True,True) if n==90 else (False,False)),(n,owners)
    s['events'].append((n,attack,owners))
   if n==96:
    target=a.read_nn_future_world_pose()[1][0].translation+unreal.Vector(0,160,0)
    assert a.trigger_nn_attack('kickl',target,False,None)
    assert unreal.ProphecyAttackFootLocomotionLibrary.get_attack_foot_locomotion(a)==(False,False)
    s['events'].append((n,'hookL->kickl'))
  attack=a.get_nn_attack_state();owners=unreal.ProphecyAttackFootLocomotionLibrary.get_attack_foot_locomotion(a)
  if attack and str(attack[0]).lower() in ('kickl','kickr'):
   assert owners==(False,False),(n,attack,owners)
   s['rows'].append(dict(tick=n,attack=str(attack[0]),owners=owners))
  if n>=120 if owned else time.monotonic()-s['start']>12:
   finish('' if s['rows'] else 'No kick observed; user Play left unchanged')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
if owned:level.editor_request_begin_play()
