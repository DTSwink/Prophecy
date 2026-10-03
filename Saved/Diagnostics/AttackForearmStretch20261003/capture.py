import unreal,pathlib,json,time,traceback,sys,math
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
d=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/AttackForearmStretch20261003'
assert ed.get_game_world() is None,'Preserve user Play'
condition=sys.argv[1] if len(sys.argv)>1 else 'physical'
s=dict(world=None,last=None,start=time.monotonic(),rows=[],frames=0,checks=[],own=False)
def pose(a):
 result=a.read_nn_future_world_pose()
 if not result:return None
 names,future,presented,alpha=result
 def tr(t):return [t.translation.x,t.translation.y,t.translation.z,t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w]
 bones={str(n):dict(nn=tr(t),body=tr(b[0]) if (b:=a.get_physical_body_state(str(n))) else None) for n,t in zip(names,presented) if str(n) in ('lowerarm_l','hand_l','lowerarm_r','hand_r','pelvis','head')}
 return bones
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 if condition=='audit':unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.ForearmStretch.Audit 0')
 (d/(condition+'.json')).write_text(json.dumps(dict(reason=reason,rows=s['rows'],checks=s['checks'])))
 if s['own'] and ed.get_game_world()==s['world']:level.editor_request_end_play()
 print('FOREARM_CAPTURE_DONE',condition,reason,len(s['rows']))
def tick(_):
 try:
  if time.monotonic()-s['start']>180:finish('Watchdog');return
  w=ed.get_game_world()
  if w is None:
   if s['own']:finish('Owned Play ended')
   return
  if not s['own']:s['world']=w;s['own']=True
  if w!=s['world']:finish('World replaced');return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t;s['frames']+=1
  a=unreal.GameplayStatics.get_player_pawn(w,0)
  if isinstance(a,unreal.ProphecyAgent):
   n=int(a.get_editor_property('tick debug'));attack=a.get_nn_attack_state();bones=pose(a)
   if bones:s['rows'].append(dict(tick=n,attack=[str(attack[0]),*attack[1:]] if attack else None,mode=str(a.get_simulation_mode()),bones=bones))
   if n>=(60 if condition=='kinematic' else 15) and not s.get('mode_set'):
    mode=unreal.ProphecyAgentSimulationMode.KINEMATIC if condition=='kinematic' else unreal.ProphecyAgentSimulationMode.PHYSICAL
    a.set_simulation_mode(mode);s['mode_set']=True
   if condition=='audit' and n==30:unreal.SystemLibrary.execute_console_command(w,'Prophecy.ForearmStretch.Audit 1')
   if condition=='half' and attack and not s.get('half_set'):
    s['checks'].append(dict(half_switch_tick=n,result=a.set_nn_half_attack_enabled(True)));s['half_set']=True
   if condition in ('long','zero') and n>=100 and attack and not s.get('stopped'):
    duration=.6 if condition=='long' else 0.
    unreal.ProphecyAttackWristLibrary.set_attack_forearm_stretch_return(a,True,duration)
    s['checks'].append(dict(stop_tick=n,duration=duration,result=a.stop_nn_attack()));s['stopped']=True
   if n>=(65 if condition=='kinematic' else 20) and not attack and not s.get('gt_checked'):
    before=pose(a)
    result=unreal.ProphecySlashTrainDebugLibrary.prepare_gt_attack_from_idle(a,'slashR')
    after=pose(a)
    s['checks'].append(dict(gt_target=str(result),unchanged=before==after,mode=str(a.get_simulation_mode())))
    s['gt_checked']=True
  if s['frames']>=380:finish('Complete')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play();print('FOREARM_CAPTURE_STARTED',condition)
