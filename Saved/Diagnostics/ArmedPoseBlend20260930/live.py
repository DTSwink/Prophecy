import unreal,pathlib,json,time,traceback,math
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyArmedPoseLibrary'))
cone=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyArmConeLibrary'))
folder=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/ArmedPoseBlend20260930');folder.mkdir(exist_ok=True)
gt=json.loads(pathlib.Path(unreal.Paths.project_content_dir(),'locomotion/NN/prophecy_slash_half_gt.json').read_text(encoding='utf-8'))
s=dict(start=time.monotonic(),last=None,n=0,rows=[],events=[])
def qmul(a,b):
 x,y,z,w=a;X,Y,Z,W=b
 return [w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z]
def local(q,p):return qmul([-p[0],-p[1],-p[2],p[3]],q)
def angle(q,p):return math.degrees(2*math.acos(min(1,abs(sum(a*b for a,b in zip(q,p))))))
def quat(t):return [t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w]
def start(a,weights):
 r=api.call_method('SetUpperBodyArmedPose',(a,True,'jabL',720.,.5,*weights))
 s['events'].append(dict(n=s['n'],time=s['last'],action='set',weights=weights,result=str(r)))
 assert (r[0] if isinstance(r,tuple) else r) is not False,r
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 w=ed.get_game_world()
 if w:unreal.SystemLibrary.execute_console_command(w,'Prophecy.AttackPerf.Capture stop')
 (folder/'live.json').write_text(json.dumps(dict(error=error,events=s['events'],rows=s['rows']),indent=2),encoding='utf-8')
 if w:level.editor_request_end_play()
 print('ARMED_BLEND_LIVE_DONE',error or 'passed',s['n'])
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
   cone.call_method('SetArmRepellantCone',(a,False,45.,100.,20.,.3,.5,False,90.,100.,20.))
   a.set_locomotion_input(unreal.Vector(0,1,0),True,unreal.Vector(0,1,0),.4,1.)
  if n==25:unreal.SystemLibrary.execute_console_command(w,'Prophecy.AttackPerf.Capture armed_pose_blend20260930 160')
  if n==30:start(a,[.5]*5+[1.]*3+[1.]*4+[0.]*4)
  if 30<=n<=150:
   names,future,presented,alpha=a.read_nn_future_world_pose();pose={str(b):p for b,p in zip(names,future)}
   gt_pose=dict(zip(gt['bone_names'],gt['families']['jabl']['pose_current']))
   d=angle(local(quat(pose['hand_l']),quat(pose['lowerarm_l'])),local(gt_pose['hand_l'][3:7],gt_pose['lowerarm_l'][3:7]))
   average=api.call_method('GetUpperBodyArmedPoseDistance',(a,'jabL'))
   average=float(average[-1] if isinstance(average,tuple) else average)
   assert math.isfinite(d) and math.isfinite(average)
   s['rows'].append(dict(n=n,time=t,left_hand_error=d,average=average))
   if 90<=n<=99:assert d<.05,('Hitting hand did not reach its full-weight goal',n,d)
   if 120<=n<=129:assert average<.05,('Full influence did not reach GT pose',n,average)
  if n==100:start(a,[1.]*16)
  if n==130:
   assert api.call_method('StopUpperBodyArmedPose',(a,))
   s['events'].append(dict(n=n,time=t,action='stop'))
  if n==150:assert average>.1,'Upper locomotion did not resume'
  if n==155:finish()
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('ARMED_BLEND_LIVE_STARTED')
