import unreal,time,pathlib,json,math,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
owned=not bool(ed.get_game_world())
s=dict(start=time.monotonic(),last=None,frames=0,samples=[],owned=owned)
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 out=dict(error=error,owned=owned,frames=s['frames'],samples=s['samples'])
 pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/RunCheckpoint20260930-135852/live.json').write_text(json.dumps(out,indent=2))
 if owned and ed.get_game_world():level.editor_request_end_play()
 print('RUN_REFRESH_LOADED',error or 'passed',len(s['samples']))
def tick(_):
 try:
  if time.monotonic()-s['start']>90:raise RuntimeError('Timeout waiting for live inference')
  w=ed.get_game_world()
  if not w:return
  now=unreal.GameplayStatics.get_time_seconds(w)
  if now==s['last']:return
  s['last']=now;s['frames']+=1;n=s['frames']
  a=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(a,unreal.ProphecyAgent):return
  if n==10 and owned:
   # Keep the publishing tick enabled for Jolt target ordering.
   a.stop_nn_attack()
   a.set_locomotion_policy_blend_times(0.,0.)
   a.set_locomotion_walk_checkpoint_speed_threshold(-1.)
   a.set_locomotion_input(unreal.Vector(0,1,0),True,unreal.Vector(0,1,0),1.,1.)
  if n>=25:
   managers=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyNNLocomotionManager)
   assert managers,'No locomotion manager'
   m=managers[0]
   assert m.get_editor_property('onnx_model_path')=='Content/locomotion/NN/prophecy_lower_body_run_b100.onnx'
   runtime=m.get_active_runtime_name()
   assert 'Run=NNERuntime' in runtime,runtime
   pose=a.read_nn_future_world_pose()
   assert pose and len(pose[1])>0,'No NN pose'
   assert all(math.isfinite(v) for p in pose[1] for v in (p.translation.x,p.translation.y,p.translation.z))
   weights=a.get_locomotion_checkpoint_weights()
   s['samples'].append(dict(frame=n,runtime=runtime,weights=weights,pelvis=[pose[1][0].translation.x,pose[1][0].translation.y,pose[1][0].translation.z]))
  if n>=65:
   if owned:assert any(row['weights'][1]>.999 for row in s['samples']),'Run endpoint not exercised'
   finish()
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
if owned:level.editor_request_begin_play()
print('RUN_REFRESH_VERIFICATION_STARTED',owned)



