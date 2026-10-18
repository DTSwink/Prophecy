"""Owned PIE limit checks. A transient duplicate tests live PHAT edits.
No user assets are saved or edited. No force-delete/undo-buffer clearing.
"""
import argparse,csv,io,json,pathlib,time,traceback,unreal
p=argparse.ArgumentParser();p.add_argument('--kinematic',action='store_true');p.add_argument('--balls',action='store_true');args=p.parse_args()
r=pathlib.Path(unreal.Paths.project_dir());o=r/'Saved/Diagnostics/ReachWristPHAT20261015';o.mkdir(parents=True,exist_ok=True)
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Existing user Play preserved'
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyReachLibrary'))
lib=unreal.ConstraintInstanceBlueprintLibrary
name=('kin' if args.kinematic else 'sim')+('-balls' if args.balls else '-reach')
s=dict(world=None,start=time.monotonic(),last=-1,rows=[],events=[],clone=None,balls=[])
def call(n,*a):return api.call_method(n,args=a)
def read(p):
 b=p.read_bytes();return b.decode('utf-16' if b.startswith(b'\xff\xfe') else 'utf-8-sig')
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 if s['world'] and ed.get_game_world()==s['world']:le.editor_request_end_play()
 if s['clone']:
  assert s['clone'].get_path_name().startswith('/Engine/Transient.')
  s['clone_path']=s['clone'].get_path_name();s['clone']=None
 data={k:v for k,v in s.items() if k not in ['cb','world','start','clone','balls','facing','original']}
 data['reason']=reason;(o/(name+'.json')).write_text(json.dumps(data,indent=2),encoding='utf-8');print('WRIST_PHAT_FINISHED',name,reason)
def tick(_):
 try:
  if time.monotonic()-s['start']>120:return finish('timeout')
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
    for prop,val in [('bool debug 3',True),('is player debug',False),('disable auto locomotion debug',True)]:
     unreal.get_default_object(unreal.SystemLibrary).call_method('SetBoolPropertyByName',args=(actor,prop,val))
    actor.hide_sword()
   if args.kinematic:assert a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
   s['facing']=a.get_actor_forward_vector();s['setup']=n
  if not s.get('setup'):return
  a.set_locomotion_input(unreal.Vector(),True,s['facing'],1.,1.)
  m=a.get_pose_reference_mesh()
  if args.balls and n>=89 and not s['balls']:
   pel=m.get_socket_location('pelvis');forward=s['facing'];right=unreal.Vector(-forward.y,forward.x,0)
   gs=unreal.get_default_object(unreal.GameplayStatics)
   for side in range(2):
    center=pel+forward*40+right*(-22 if side==0 else 22)+unreal.Vector(0,0,28)
    t=unreal.Transform(location=center)
    b=gs.call_method('BeginDeferredActorSpawnFromClass',args=(w,unreal.StaticMeshActor,t,unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN,None,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
    b=gs.call_method('FinishSpawningActor',args=(b,t,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
    c=b.static_mesh_component;c.set_mobility(unreal.ComponentMobility.MOVABLE);c.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Sphere'));c.set_world_scale3d(unreal.Vector(.06,.06,.06));c.set_collision_profile_name('PhysicsActor');c.set_enable_gravity(False);c.set_simulate_physics(True)
    result=unreal.ProphecyJoltStaticMeshLibrary.enable_jolt_static_mesh_physics(c)
    assert result is not None and not result,result
    s['balls'].append(b)
  if n>=90 and not s.get('requested'):
   for side,hand in enumerate([unreal.ProphecyReachHand.LEFT,unreal.ProphecyReachHand.RIGHT]):
    wrist=m.get_socket_transform('hand_l' if side==0 else 'hand_r')
    if args.balls:
     c=s['balls'][side].static_mesh_component;center=c.get_world_location();d=wrist.translation-center;point=center+d/d.length()*3
     result=call('GrabObject',a,hand,c,120.,True,point,180.)
    else:
     t=unreal.Transform(location=wrist.translation+s['facing']*20,rotation=unreal.Rotator(160,50,150))
     result=call('ReachTarget',a,hand,t,120.,720.)
    assert result,'Reach/grab admission failed'
   s['requested']=n
  if s.get('requested') and n>s['requested']:
   unreal.SystemLibrary.execute_console_command(w,'Prophecy.Reach.Inspect Wrists')
   rows=list(csv.DictReader(io.StringIO(read(o/'wrists.csv'))))
   for row in rows:
    if row['agent']!=a.get_name():continue
    row['tick']=n
    if int(row['active']) or int(row['returning']):
     assert float(row['violation'])<1.e-6,row
     assert float(row['correction_rad'])<1.e-6,row
    if args.kinematic and 142<=n<160:assert [int(row[k]) for k in ['mode1','mode2','mode_twist']]==[2,2,2],row
    if args.kinematic and 162<=n<180:assert [float(row[k]) for k in ['swing1','swing2','twist']]==[7.,9.,11.],row
    s['rows'].append(row)
  if args.kinematic and n==140:
   s['original']=m.get_editor_property('physics_asset_override') or m.get_skinned_asset().get_editor_property('physics_asset')
   unreal.SystemLibrary.execute_console_command(w,'Prophecy.Reach.Inspect WristClone')
   s['clone']=m.get_editor_property('physics_asset_override')
   assert s['clone'] and s['clone'].get_path_name().startswith('/Engine/Transient.')
   for c in s['clone'].get_constraints(True):
    if any(b in str(lib.get_attached_body_names(c)) for b in ['hand_l','hand_r']):lib.set_angular_limits(c,unreal.AngularConstraintMotion.ACM_LOCKED,50.,unreal.AngularConstraintMotion.ACM_LOCKED,30.,unreal.AngularConstraintMotion.ACM_LOCKED,20.)
   m.set_physics_asset(s['clone'],False);s['events'].append([n,'Loaded diagnostic PHAT with locked wrists'])
  if args.kinematic and n==160:
   for c in s['clone'].get_constraints(True):
    if any(b in str(lib.get_attached_body_names(c)) for b in ['hand_l','hand_r']):lib.set_angular_limits(c,unreal.AngularConstraintMotion.ACM_LIMITED,7.,unreal.AngularConstraintMotion.ACM_LIMITED,9.,unreal.AngularConstraintMotion.ACM_LIMITED,11.)
   s['events'].append([n,'Edited same loaded PHAT to 7/9/11 without restarting reach'])
  if args.kinematic and n==180:m.set_physics_asset(s['original'],False);s['events'].append([n,'Restored original PHAT reference'])
  if n==210:
   s['grips']=[str(call('GetGrabStatus',a,h)) for h in [unreal.ProphecyReachHand.LEFT,unreal.ProphecyReachHand.RIGHT]]
   call('StopReaching',a,.25)
  if n>=230:
   assert len(s['rows'])>150,'Insufficient samples'
   return finish('passed')
 except Exception:return finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);le.editor_request_begin_play();print('WRIST_PHAT_STARTED',name)
