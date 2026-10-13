"""Temporary owned-PIE reach/grasp fixture. Never saves the map or Blueprint."""
import argparse, json, math, pathlib, time, traceback, unreal
p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--kind',choices=['reach','balls','head'],default='balls');p.add_argument('--kinematic',action='store_true');p.add_argument('--ticks',type=int,default=420);p.add_argument('--fps',type=float,default=60);p.add_argument('--leave',action='store_true');p.add_argument('--lifecycle',action='store_true');p.add_argument('--radius',type=float,default=6.);args=p.parse_args()
root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/ReachGrasp20261012';out.mkdir(parents=True,exist_ok=True)
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Existing Play left untouched'
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyReachLibrary'))
oldfps=unreal.SystemLibrary.get_console_variable_float_value('t.MaxFPS');unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),f't.MaxFPS {args.fps}')
s={'start':time.monotonic(),'last':-1,'rows':[],'world':None,'actors':[],'balls':[],'calls':[]}
def pose(t):
 v,q=t.translation,t.rotation;return [v.x,v.y,v.z,q.x,q.y,q.z,q.w]
def vec(v):return [v.x,v.y,v.z]
def call(name,*a):return api.call_method(name,args=a)
def spawn(w,cls,pos,rot=None):
 transform=unreal.Transform(location=pos,rotation=rot or unreal.Rotator())
 gs=unreal.get_default_object(unreal.GameplayStatics)
 actor=gs.call_method('BeginDeferredActorSpawnFromClass',args=(w,cls,transform,unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN,None,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
 return gs.call_method('FinishSpawningActor',args=(actor,transform,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['callback'])
 if not args.leave and s['world'] and ed.get_game_world()==s['world']:level.editor_request_end_play()
 unreal.SystemLibrary.execute_console_command(ed.get_game_world() or ed.get_editor_world(),f't.MaxFPS {oldfps}')
 native=out/(args.name+'-native');native.mkdir(exist_ok=True)
 for f in out.glob('native-*.csv'):
  if f.stem.split('-')[-1].isdigit():f.replace(native/f.name)
 if (out/'live-performance.csv').exists():(out/'live-performance.csv').replace(native/'performance.csv')
 (out/(args.name+'.json')).write_text(json.dumps({'reason':reason,'options':vars(args),'rows':s['rows'],'calls':s['calls']},separators=(',',':')),encoding='utf-8')
 print('REACH_GRASP_FINISHED',args.name,reason,len(s['rows']))
def tick(_):
 try:
  if time.monotonic()-s['start']>180:return finish('timeout')
  w=ed.get_game_world()
  if not w:
   if s['world']:finish('ended externally')
   return
  s['world']=w;a=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(a,unreal.ProphecyAgent):return
  n=int(a.get_editor_property('absolute tick debug'))
  if n==s['last']:return
  s['last']=n
  if not s['actors']:
   s['actors']=sorted(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent),key=lambda x:x.get_name())
  if n>=4 and not s.get('setup'):
   for actor in s['actors']:
    unreal.get_default_object(unreal.SystemLibrary).call_method('SetBoolPropertyByName',args=(actor,'bool debug 3',True))
    unreal.get_default_object(unreal.SystemLibrary).call_method('SetBoolPropertyByName',args=(actor,'is player debug',False))
    unreal.get_default_object(unreal.SystemLibrary).call_method('SetBoolPropertyByName',args=(actor,'disable auto locomotion debug',True))
    actor.hide_sword();actor.set_show_kinematic_debug_mesh(False)
    actor.get_agent_mesh().set_visibility(False,True);actor.get_pose_reference_mesh().set_forced_lod(1)
    if args.kinematic:assert actor.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
   s['setup']=n
   s['facing']={actor.get_name():actor.get_actor_forward_vector() for actor in s['actors']}
   if args.kind=='head':
    other=next(x for x in s['actors'] if x!=a);direction=other.get_root_low_point()-a.get_root_low_point();direction.z=0;direction=direction/direction.length()
    s['facing'][a.get_name()]=direction;s['facing'][other.get_name()]=direction*-1
  if s.get('setup'):
   for actor in s['actors']:actor.set_locomotion_input(unreal.Vector(),True,s['facing'][actor.get_name()],1.,1.)
  if args.kind=='head' and s.get('setup'):
   other=next(x for x in s['actors'] if x!=a);s['head_agent']=other
   delta=a.get_root_low_point()-other.get_root_low_point();delta.z=0
   other.set_locomotion_input(delta/delta.length()*.4 if delta.length()>65 else unreal.Vector(),True,s['facing'][other.get_name()],1.,1.)
  if n>=90 and not s.get('requested') and (args.kind!='head' or (a.get_root_low_point()-s['head_agent'].get_root_low_point()).length()<75):
   mesh=a.get_pose_reference_mesh();pel=mesh.get_socket_location('pelvis');forward=s['facing'][a.get_name()];right=unreal.Vector(-forward.y,forward.x,0)
   s['targets']=[]
   for side in range(2):
    if args.kind=='head' and side==0:continue
    center=pel+forward*40+right*(-22 if side==0 else 22)+unreal.Vector(0,0,28)
    hand=unreal.ProphecyReachHand.LEFT if side==0 else unreal.ProphecyReachHand.RIGHT
    wrist=mesh.get_socket_transform('hand_l' if side==0 else 'hand_r')
    if args.kind=='reach':
     target=unreal.Transform(location=center,rotation=wrist.rotation.rotator());result=call('ReachTarget',a,hand,target,120.,180.)
    elif args.kind=='balls':
     ball=spawn(w,unreal.StaticMeshActor,center)
     comp=ball.static_mesh_component;comp.set_mobility(unreal.ComponentMobility.MOVABLE);comp.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Sphere'));comp.set_world_scale3d(unreal.Vector(args.radius/50,args.radius/50,args.radius/50));comp.set_collision_profile_name('PhysicsActor');comp.set_enable_gravity(False)
     comp.set_simulate_physics(not args.kinematic)
     if not args.kinematic:
      result=unreal.ProphecyJoltStaticMeshLibrary.enable_jolt_static_mesh_physics(comp)
      s['calls'].append(['admit_ball',str(result)])
     direction=wrist.translation-center;direction=direction/direction.length();point=center+direction*args.radius
     result=call('GrabObject',a,hand,comp,120.,True,point,180.);s['balls'].append(ball)
    else:
     other=s['head_agent'];targetmesh=other.get_pose_reference_mesh();head=targetmesh.get_socket_location('head')
     direction=a.get_root_low_point()-other.get_root_low_point();direction.z=0;direction=direction/direction.length()
     closest=targetmesh.get_closest_point_on_collision(head+direction*30+unreal.Vector(0,0,10),bone_name='head')
     point=closest[1];s['calls'].append(['head_surface',str(closest),vec(point)])
     result=call('GrabBone',a,hand,targetmesh,unreal.Name('head'),point,120.,180.)
    s['calls'].append([n,side,bool(result)]);s['targets'].append(vec(center))
   call('SetReachVisualization',a,True);s['requested']=n
  if s.get('requested'):
   mesh=a.get_pose_reference_mesh();row={'tick':n,'hands':[],'root':pose(a.get_actor_transform()),'mesh':pose(a.get_agent_mesh().get_world_transform()),'pelvis':pose(mesh.get_socket_transform('pelvis')),'balls':[pose(b.static_mesh_component.get_world_transform()) if b else None for b in s['balls']]}
   if args.kind=='head':row['head_target']=pose(s['head_agent'].get_pose_reference_mesh().get_socket_transform('head'))
   names,future,command,alpha=a.read_nn_future_world_pose();cmd={str(k):t for k,t in zip(names,command)}
   for side in range(2):
    hand=unreal.ProphecyReachHand.LEFT if side==0 else unreal.ProphecyReachHand.RIGHT;bone='hand_l' if side==0 else 'hand_r'
    status=call('GetGrabStatus',a,hand)
    row['hands'].append({'active':status.active,'gripped':status.gripped,'physical_grip':status.physical_grip,'distance':status.distance_cm,'contacts':status.contact_fingers,'surface':vec(status.surface_point),'target':pose(cmd[bone]),'physical':pose(mesh.get_socket_transform(bone)),'fingers':{f:pose(mesh.get_socket_transform(f)) for f in [f'{x}_{j:02d}_{"l" if side==0 else "r"}' for x in ['thumb','index','middle','ring','pinky'] for j in range(1,4)]}})
   s['rows'].append(row)
   if n>=280 and not s.get('camera'):
    pos=mesh.get_socket_location('spine_05');forward=s['facing'][a.get_name()];right=unreal.Vector(-forward.y,forward.x,0);camloc=pos+forward*150+right*50+unreal.Vector(0,0,20)
    if args.kind=='head':pos=(pos+s['head_agent'].get_pose_reference_mesh().get_socket_location('head'))*.5;camloc=pos+forward*80+right*160+unreal.Vector(0,0,15)
    cam=spawn(w,unreal.CameraActor,camloc,unreal.MathLibrary.find_look_at_rotation(camloc,pos))
    unreal.GameplayStatics.get_player_controller(w,0).set_view_target_with_blend(cam,0)
    s['camera']=cam
   if n in (100,179,183,200,221,239,241,270,277,310,316,351,371,391,410):unreal.SystemLibrary.execute_console_command(w,f'Prophecy.Reach.Inspect {n}')
   if n==300:unreal.SystemLibrary.execute_console_command(w,'Prophecy.Reach.Benchmark');unreal.AutomationLibrary.take_high_res_screenshot(1280,900,str(out/(args.name+'.png')))
   if args.lifecycle and args.kind=='balls':
    if n in (180,181,182,240,276,277,278,370):
     for side,ball in enumerate(s['balls']):
      if not ball:continue
      hand=unreal.ProphecyReachHand.LEFT if side==0 else unreal.ProphecyReachHand.RIGHT
      result=call('GrabObject',a,hand,ball.static_mesh_component,120.,False,unreal.Vector(),180.)
      s['calls'].append([n,'repeat',side,bool(result)])
    if n==220:call('ReleaseGrab',a,unreal.ProphecyReachHand.LEFT,.25);s['calls'].append([n,'release_left'])
    if n==270:call('StopReaching',a,1.);s['calls'].append([n,'stop_long'])
    if n==315:s['balls'][0].destroy_actor();s['balls'][0]=None;s['calls'].append([n,'destroy_left_target'])
    if n==350:a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC);s['calls'].append([n,'switch_mode'])
    if n==390:unreal.ProphecyAgentResetLibrary.reset_initial_agents(w);s['calls'].append([n,'reset'])
   elif n==350:
    call('StopReaching',a,.25);s['calls'].append([n,'stop'])
  if n>=args.ticks:return finish('captured')
 except Exception:return finish(traceback.format_exc())
s['callback']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play();print('REACH_GRASP_STARTED',args.name)



