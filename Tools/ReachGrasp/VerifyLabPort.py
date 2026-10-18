"""Owned reach-port smoke: runtime-only actors/settings, no package saves."""
import argparse,csv,io,json,pathlib,time,traceback,unreal
p=argparse.ArgumentParser();p.add_argument('--kinematic',action='store_true');p.add_argument('--explicit',action='store_true');args=p.parse_args()
r=pathlib.Path(unreal.Paths.project_dir());o=r/'Saved/Diagnostics/ReachPort20261016'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Existing user Play preserved'
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyReachLibrary'))
name=('kin' if args.kinematic else 'sim')+('-explicit' if args.explicit else '-auto')
s=dict(world=None,start=time.monotonic(),last=-1,rows=[],events=[],balls=[],samples=[],max_violation=0.)
def call(n,*a):return api.call_method(n,args=a)
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 if s['world'] and ed.get_game_world()==s['world']:le.editor_request_end_play()
 data={k:v for k,v in s.items() if k not in ['cb','world','start','balls','facing','actor','original']}
 data['reason']=reason;(o/(name+'.json')).write_text(json.dumps(data,indent=2),encoding='utf-8');print('REACH_PORT_FINISHED',name,reason)
def tick(_):
 try:
  if time.monotonic()-s['start']>180:return finish('timeout')
  w=ed.get_game_world()
  if not w:
   if s['world']:return finish('ended externally')
   return
  s['world']=w;a=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(a,unreal.ProphecyAgent):return
  n=int(a.get_editor_property('absolute tick debug'))
  if n==s['last']:return
  s['last']=n
  if n>=4 and not s.get('setup'):
   for actor in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
    for prop,val in [('bool debug 3',True),('is player debug',False),('disable auto locomotion debug',True)]:unreal.get_default_object(unreal.SystemLibrary).call_method('SetBoolPropertyByName',args=(actor,prop,val))
    actor.hide_sword()
   if args.kinematic:assert a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
   s['facing']=a.get_actor_forward_vector();s['setup']=n
   defaults=call('GetReachMotionTuning',a);s['defaults']=list(defaults);assert tuple(defaults)==(0.,1.),defaults
   for sync,elbow in [(0.,0.),(1.,1.),(.82,.5)]:assert call('SetReachMotionTuning',a,sync,elbow)
   for sync,elbow in [(-.1,1.),(1.1,1.),(0.,-1.),(0.,2.)]:assert not call('SetReachMotionTuning',a,sync,elbow)
   assert abs(call('GetReachMotionTuning',a)[0]-.82)<1e-6 and call('GetReachMotionTuning',a)[1]==.5
   assert call('SetReachMotionTuning',a,.82,1.)
  if not s.get('setup'):return
  a.set_locomotion_input(unreal.Vector(),True,s['facing'],1.,1.)
  m=a.get_pose_reference_mesh()
  if n>=89 and not s['balls']:
   pel=m.get_socket_location('pelvis');forward=s['facing'];right=unreal.Vector(-forward.y,forward.x,0);gs=unreal.get_default_object(unreal.GameplayStatics)
   for side in range(2):
    center=pel+forward*40+right*(-22 if side==0 else 22)+unreal.Vector(0,0,28);t=unreal.Transform(location=center)
    b=gs.call_method('BeginDeferredActorSpawnFromClass',args=(w,unreal.StaticMeshActor,t,unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN,None,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT));b=gs.call_method('FinishSpawningActor',args=(b,t,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
    c=b.static_mesh_component;c.set_mobility(unreal.ComponentMobility.MOVABLE);c.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Sphere'));c.set_world_scale3d(unreal.Vector(.06,.06,.06));c.set_collision_profile_name('PhysicsActor');c.set_enable_gravity(False);c.set_simulate_physics(True)
    if not args.kinematic:
     result=unreal.ProphecyJoltStaticMeshLibrary.enable_jolt_static_mesh_physics(c);assert result is not None and not result,result
    s['balls'].append(b)
   s['ball_tick']=n
  if s['balls'] and n>s['ball_tick'] and not s.get('requested'):
   call('StopReaching',a,0.)
   s['expected_points']=[]
   for side,hand in enumerate([unreal.ProphecyReachHand.LEFT,unreal.ProphecyReachHand.RIGHT]):
    c=s['balls'][side].static_mesh_component;center=c.get_world_location();reference=m.get_socket_location(('hand_' if args.explicit else 'upperarm_')+('l' if side==0 else 'r'));d=reference-center;point=center+d/d.length()*3
    assert call('GrabObject',a,hand,c,120.,args.explicit,point,180.)
    status=call('GetGrabStatus',a,hand);actual=status.get_editor_property('surface_point');assert (actual-point).length()<.1,(actual,point)
    s['expected_points'].append([point.x,point.y,point.z])
   s['requested']=n
  if s.get('requested') and n>s['requested']:
   if n%10==0:
    unreal.SystemLibrary.execute_console_command(w,'Prophecy.Reach.Inspect Wrists')
    raw=(r/'Saved/Diagnostics/ReachWristPHAT20261015/wrists.csv').read_bytes();rows=list(csv.DictReader(io.StringIO(raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig'))))
    for row in rows:
     if row['agent']==a.get_name() and (int(row['active']) or int(row['returning'])):
      assert float(row['violation'])<1e-6 and float(row['correction_rad'])<1e-6,row
      s['max_violation']=max(s['max_violation'],float(row['violation']));s['rows'].append(row)
    grips=[]
    for hand in [unreal.ProphecyReachHand.LEFT,unreal.ProphecyReachHand.RIGHT]:
     status=call('GetGrabStatus',a,hand);grips.append({key:status.get_editor_property(key) for key in ['active','gripped','physical_grip','distance_cm','contact_fingers']})
    s['samples'].append({'tick':n,'hands':grips})
    if all(g['gripped'] for g in grips) and not s.get('acquired'):s['acquired']=n
   if n>=s['requested']+300 and not s.get('released'):
    s['final_grips']=[str(call('GetGrabStatus',a,h)) for h in [unreal.ProphecyReachHand.LEFT,unreal.ProphecyReachHand.RIGHT]]
    assert s.get('acquired'),'Neither/both grip acquisition not completed; inspect samples'
    call('StopReaching',a,.25);s['released']=n
   if s.get('released') and n>s['released']+20:
    assert all(not call('GetGrabStatus',a,h).get_editor_property('active') for h in [unreal.ProphecyReachHand.LEFT,unreal.ProphecyReachHand.RIGHT])
    assert abs(call('GetReachMotionTuning',a)[0]-.82)<1e-6
    return finish('passed')
 except Exception:return finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);le.editor_request_begin_play();print('REACH_PORT_STARTED',name)
