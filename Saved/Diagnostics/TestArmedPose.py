import unreal,pathlib,json,time,traceback,math
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyArmedPoseLibrary'))
assert api
s=dict(start=time.monotonic(),last=None,n=0,rows=[],events=[])
folder=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/ArmedPose');folder.mkdir(exist_ok=True)
def distance(a,attack='slashR'):
 r=api.call_method('GetUpperBodyArmedPoseDistance',(a,attack))
 assert r is not None,('distance unavailable',attack)
 if isinstance(r,tuple):assert r[0];return float(r[1])
 return float(r)
def start(a,speed,attack='slashR'):
 r=api.call_method('SetUpperBodyArmedPose',(a,True,attack,speed))
 s['events'].append(dict(n=s['n'],action='start',speed=speed,result=str(r)))
 assert (r[0] if isinstance(r,tuple) else r) is not False,r
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 w=ed.get_game_world()
 if w:unreal.SystemLibrary.execute_console_command(w,'Prophecy.AttackPerf.Capture stop')
 (folder/'live.json').write_text(json.dumps(dict(error=error,events=s['events'],rows=s['rows']),indent=2))
 if w:level.editor_request_end_play()
 print('ARMED_POSE_LIVE_DONE',error or 'passed',s['n'])
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
    other.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC);other.set_actor_tick_enabled(False);other.stop_nn_attack()
    if other!=a:other.set_editor_property('bNNInferenceEnabled',False)
   a.set_locomotion_policy_blend_times(0.,0.)
   a.set_locomotion_input(unreal.Vector(0,1,0),True,unreal.Vector(0,1,0),.4,1.)
  if n==30:
   s['initial']=distance(a);start(a,180.)
   unreal.SystemLibrary.execute_console_command(w,'Prophecy.AttackPerf.Capture manual_armed_pose 245')
  if 30<=n<=270:
   d=distance(a);names,future,presented,alpha=a.read_nn_future_world_pose()
   s['rows'].append(dict(n=n,time=t,distance=d,attack=str(a.get_nn_attack_state()),alpha=alpha,
    future=[[str(b),[p.translation.x,p.translation.y,p.translation.z],[p.rotation.x,p.rotation.y,p.rotation.z,p.rotation.w]] for b,p in zip(names,future)]))
   assert math.isfinite(d)
   if 100<=n<=120:assert d<.05,('Did not reach GT pose',n,d)
  if n==60:a.set_locomotion_input(unreal.Vector(1,0,0),True,unreal.Vector(1,0,0),.4,1.)
  if n==125:
   assert api.call_method('StopUpperBodyArmedPose',(a,));assert api.call_method('StopUpperBodyArmedPose',(a,))
   s['events'].append(dict(n=n,action='stop_held'))
  if n==155:assert distance(a)>.1,'Normal checkpoint failed to resume'
  if n==160:start(a,30.,'hookL')
  if n==175:
   assert api.call_method('StopUpperBodyArmedPose',(a,))
   s['events'].append(dict(n=n,action='stop_mid_blend'))
  if n==200:start(a,600.)
  if n==223:assert distance(a)<.05
  if n==225:
   names,p,_,_=a.read_nn_future_world_pose();pelvis=p[[str(b) for b in names].index('pelvis')].translation
   assert a.trigger_nn_attack('slashR',pelvis+unreal.Vector(0,180,10),True,None)
   s['events'].append(dict(n=n,action='real_half_attack'))
  if n==255:a.stop_nn_attack()
  if n==276:finish()
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
print('ARMED_POSE_LIVE_STARTED')
