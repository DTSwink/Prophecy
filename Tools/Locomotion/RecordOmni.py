"""Capture stock omni-seeded NN continuation in owned PIE, without asset writes.
Full authored layer seeds both recurrent frames; remove it, settle120ticks,
then record180tick intervals (181 endpoints). Run via RunUnrealRemote.py.
"""
import unreal,json,pathlib,time,traceback,math,argparse
p=argparse.ArgumentParser();p.add_argument('--filter',default='');p.add_argument('--skip-existing',action='store_true');args=p.parse_args()
root=pathlib.Path(unreal.Paths.project_dir());out=root/'Saved/Diagnostics/OmniRecord20261015';out.mkdir(parents=True,exist_ok=True)
clips=json.loads((out/'clips.json').read_text());clips=[c for c in clips if args.filter in c['asset']]
if args.skip_existing:clips=[c for c in clips if not (out/(c['asset'].split('/')[-1]+'.json')).exists()]
assert clips
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'User Play left untouched'
old_fps=unreal.SystemLibrary.get_console_variable_float_value('t.MaxFPS')
names=json.loads((root/'Labs/SwordHolsterLab/data/motions.json').read_text())['names']
s={'world':None,'cb':None,'case':-1,'last_time':None,'tick':0,'stage':'begin','start':time.monotonic(),'cases':[]}
def tr(t):
 v,q=t.translation,t.rotation;return [v.x,v.y,v.z,q.x,q.y,q.z,q.w]
def vec(v):return [v.x,v.y,v.z]
def status(reason='running'):
 (out/'capture-status.json').write_text(json.dumps({'state':reason,'completed':s['cases'],'current':s.get('clip',{}).get('asset'),'stage':s['stage'],'tick':s['tick']},indent=2))
def finish(reason):
 if s['cb']:unreal.unregister_slate_post_tick_callback(s['cb']);s['cb']=None
 if s['world'] and ed.get_game_world()==s['world']:level.editor_request_end_play()
 unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),f't.MaxFPS {old_fps}')
 status(reason);print('OMNI_CAPTURE',reason)
def next_case():
 s['case']+=1
 if s['case']>=len(clips):finish('complete');return
 s.update(clip=clips[s['case']],world=None,actor=None,last_time=None,tick=0,stage='init',rows=[],seed=[],case_start=time.monotonic())
 status();level.editor_request_begin_play()
def tick(_):
 try:
  if time.monotonic()-s['start']>1500:return finish('total timeout')
  w=ed.get_game_world()
  if s['stage']=='begin':return next_case()
  if s['stage']=='ending':
   if not w:return next_case()
   return
  if time.monotonic()-s['case_start']>90:return finish('case timeout')
  if not w:
   if s['world']:return finish('Play ended externally')
   return
  s['world']=w
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last_time']:return
  s['last_time']=t;s['tick']+=1;n=s['tick']
  if n<6:return
  if s['actor'] is None:
   a=unreal.GameplayStatics.get_player_pawn(w,0)
   if not isinstance(a,unreal.ProphecyAgent):return
   s['actor']=a
   assert a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
   a.set_actor_tick_enabled(False);a.hide_sword();a.stop_nn_attack();a.set_nn_inference_enabled(True)
   for other in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
    if other!=a:
     other.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC);other.destroy_actor()
   a.get_component_by_class(unreal.CapsuleComponent).set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
   a.set_upper_nn_gaze(0.,0.);a.set_locomotion_walk_checkpoint_speed_threshold(-1.);a.set_locomotion_policy_blend_times(0.,0.)
   unreal.ProphecyRootPhysicsLibrary.set_locomotion_auto_run_speed_threshold(a,100000.)
   s['run']='/Run/' in s['clip']['asset'];s['carrier']=a.mesh.get_world_transform();s['facing']=unreal.MathLibrary.quat_rotate_vector(s['carrier'].rotation,unreal.Vector(0,1,0))
   v=unreal.Vector(*s['clip']['velocity_mesh_cm_s']);v=unreal.MathLibrary.quat_rotate_vector(s['carrier'].rotation,v);v.z=0
   s['requested_speed']=v.length();s['direction']=v/s['requested_speed'];s['amplitude']=1.
   a.set_locomotion_input(s['direction'],s['run'],s['facing'],1.,1.)
   assert a.play_nn_animation_layer(unreal.load_asset(s['clip']['asset']),'None',0.,0.,1.,True)
   s['stage']='seed';s['seed_start']=n
   managers=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyNNLocomotionManager)
   s['contracts']={k:str(managers[0].get_editor_property(k)) for k in ['onnx_model_path','runtime_contract_path','walk_onnx_model_path','walk_runtime_contract_path','upper_onnx_model_path','upper_runtime_contract_path']}
   return
  a=s['actor']
  if s['stage']=='seed':
   play,weight=a.get_nn_animation_layer_state()
   if play>=.2:
    target=a.get_locomotion_target();speed=target[1]
    assert speed>0,'No moving target'
    ratio=s['requested_speed']/speed
    s['unscaled_target_speed']=speed
    # Native directional caps are retained. Never silently boost beyond them.
    assert ratio<1.015,f"Clip speed {s['requested_speed']} exceeds native directional cap {speed}"
    s['amplitude']=min(1.,ratio)
    a.set_locomotion_input(s['direction']*s['amplitude'],s['run'],s['facing'],1.,1.)
    s['seed_end_seconds']=play
    s['seed']=[tr(x) for x in a.read_nn_future_world_pose()[1]]
    assert a.stop_nn_animation_layer(0.)
    s['stage']='release'
   return
  if s['stage']=='release':
   if not a.is_nn_animation_layer_active():s['release_tick']=n;s['stage']='settle'
   return
  elapsed=n-s['release_tick']
  if elapsed<120:return
  assert not a.is_nn_animation_layer_active(),'Reference layer remained active'
  weights=a.get_locomotion_checkpoint_weights();assert abs(weights[1]-(1 if s['run'] else 0))<1e-5,('Wrong checkpoint',weights)
  bn,future,presented,alpha=a.read_nn_future_world_pose();lookup={str(k):v for k,v in zip(bn,presented)}
  frame=a.mesh.get_world_transform()
  assert all(k in lookup for k in names if k!='root')
  poses=[tr(unreal.MathLibrary.make_relative_transform(lookup[k] if k!='root' else frame,s['carrier'])) for k in names]
  assert all(math.isfinite(v) for b in poses for v in b)
  velocity,facing,running=a.get_locomotion_state();target=a.get_locomotion_target()
  expected_speed=min(s['requested_speed'],s['unscaled_target_speed'])
  assert abs(velocity.length()-expected_speed)<1.5,('Incorrect sustained speed',velocity.length(),expected_speed)
  assert (facing-s['facing']).length()<.001,('Incorrect heading',vec(facing))
  s['rows'].append({'tick':n,'engine_frame':unreal.SystemLibrary.get_frame_count(),'world_time':t,'elapsed':elapsed,'pose':poses,'alpha':alpha,'velocity_cm_s':vec(velocity),'target_cm_s':vec(target[0]),'weights':list(weights)})
  if elapsed==120:s['stage']='record';status()
  if elapsed>=300:
   assert all(b['engine_frame']==a['engine_frame']+1 for a,b in zip(s['rows'],s['rows'][1:])), 'Skipped engine frame'
   assert len(s['rows'])==181
   data={**s['clip'],'names':names,'fps':60,'settle_ticks':120,'record_ticks':180,'mode':'kinematic','run':s['run'],'seed_end_seconds':s['seed_end_seconds'],'seed_future':s['seed'],'contracts':s['contracts'],'requested_speed':s['requested_speed'],'unscaled_target_speed':s['unscaled_target_speed'],'amplitude':s['amplitude'],'direction_world':vec(s['direction']),'facing_world':vec(s['facing']),'carrier':tr(s['carrier']),'rows':s['rows']}
   name=s['clip']['asset'].split('/')[-1];(out/(name+'.json')).write_text(json.dumps(data,separators=(',',':')))
   s['cases'].append(name);s['stage']='ending';status();level.editor_request_end_play()
 except Exception:finish(traceback.format_exc())
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'t.MaxFPS 60')
s['cb']=unreal.register_slate_post_tick_callback(tick)
print('OMNI_CAPTURE_STARTED',len(clips))
