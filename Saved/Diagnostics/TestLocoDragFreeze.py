import unreal,pathlib,json,time,traceback,math
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
api=unreal.get_default_object(unreal.ProphecyAttackFootLocomotionLibrary)
inertia=unreal.get_default_object(unreal.ProphecyAttackStartInertiaLibrary)
block=unreal.get_default_object(unreal.ProphecyGhostAttackLibrary)
s=dict(start=time.monotonic(),last=None,n=0,rows=[])
def v(p):return [p.x,p.y,p.z]
def configure(a,alpha):
 assert api.call_method('SetAttackFootLocomotion',(a,True,unreal.ProphecyAttackFootLocomotionMode.CURRENT_BLEND,0.,0.,alpha))
def window(a):return unreal.ProphecyRootPhysicsLibrary.get_continuous_locomotion_root_window(a)
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/LocoDragFreeze.json').write_text(json.dumps(dict(error=error,rows=s['rows']),separators=(',',':')))
 if ed.get_game_world():level.editor_request_end_play()
 print('LOCO_DRAG_FREEZE',error or 'passed',len(s['rows']))
def tick(_):
 try:
  assert time.monotonic()-s['start']<80,'Timeout'
  w=ed.get_game_world()
  if not w:return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if s['last']==t:return
  s['last']=t;s['n']+=1;n=s['n']
  a=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(a,unreal.ProphecyAgent):return
  if n==20:
   for other in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
    other.set_actor_tick_enabled(False);other.stop_nn_attack()
   inertia.call_method('SetAttackStartPelvisInertia',(a,False,10,1.,10,1.))
   inertia.call_method('SetAttackStartFootInertia',(a,False,10,1.,10,1.))
   a.set_locomotion_input(unreal.Vector(0,1,0),True,unreal.Vector(0,1,0),1.,1.)
  if n==40:
   configure(a,0.)
   block.call_method('SetAttackArmedBlocked',(a,True))
   p=a.read_nn_future_world_pose()[1][0].translation
   assert a.trigger_nn_attack('hookL',p+unreal.Vector(0,200,0),False,None)
  if 44<=n<100:
   assert any(api.call_method('GetAttackFootLocomotion',(a,))),(n,'Drag ended early')
   samples=[]
   for alpha in (0.,.5,1.):
    configure(a,alpha);result=window(a);assert result is not None
    roots,times=result;assert len(roots)==len(times)==9
    samples.append(([v(r.translation) for r in roots],[r.rotation for r in roots],list(times)))
   base,half,full=samples
   midpoint=max(abs(half[0][i][j]-(base[0][i][j]+full[0][i][j])*.5) for i in range(9) for j in range(3))
   assert midpoint<1e-6,(n,'Double blend',midpoint)
   assert base[2]==half[2]==full[2]
   for i in range(9):
    assert base[1][i]==half[1][i]==full[1][i]
   pelvis=a.read_nn_future_world_pose()[2][0].translation
   floor=a.get_root_low_point().z;target=[pelvis.x,pelvis.y,floor]
   frozen=max(math.dist(p,target) for p in full[0]);assert frozen<.001,(n,frozen)
   assert math.dist(base[0][0],v(a.get_root_low_point()))<.001
   raw=a.get_locomotion_root_window()[0]
   spread=max(math.dist(v(r.translation),v(raw[2].translation)) for r in raw[2:])
   if n>=82:assert spread<.001,(n,'NN input window not collapsed',spread)
   active=0. if n<60 else .5 if n<80 else 1.
   configure(a,active)
   s['rows'].append(dict(tick=n,alpha=active,midpoint_error=midpoint,freeze_error=frozen,raw_spread=spread,root=v(a.get_root_low_point()),pelvis=v(pelvis)))
  if n==100:a.stop_nn_attack()
  if n==102:
   assert api.call_method('GetAttackFootLocomotion',(a,))==(False,False)
   roots,times=window(a)
   assert math.dist(v(roots[0].translation),v(a.get_root_low_point()))<.001
   finish()
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
