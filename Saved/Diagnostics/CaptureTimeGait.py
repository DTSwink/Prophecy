import unreal,json,pathlib,time,traceback,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem); level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
def lib(n): return unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.'+n))
clock=lib('ProphecyAgentTimeLibrary'); root=lib('ProphecyRootPhysicsLibrary')
tag=sys.argv[1] if len(sys.argv)>1 else 'Current'
out=pathlib.Path(unreal.Paths.project_saved_dir())/('Diagnostics/TimeGait'+tag+'.json')
trace=out.parent/'SlashContacts/nn_inputs.jsonl'
offset=trace.stat().st_size if trace.exists() else 0
s=dict(rows=[],last=-1.,start=time.monotonic())
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 if ed.get_game_world():level.editor_request_end_play()
 out.write_text(json.dumps(dict(error=error,rows=s['rows']),indent=2))
 if trace.exists():
  with trace.open('rb') as f:
   f.seek(offset);out.with_suffix('.jsonl').write_bytes(f.read())
 print('TIME_GAIT_CAPTURE',len(s['rows']),error)
def tick(dt):
 try:
  if time.monotonic()-s['start']>65:finish('Timeout');return
  w=ed.get_game_world()
  if not w:return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t
  if not s.get('tracing'):
   unreal.SystemLibrary.execute_console_command(w,'Prophecy.NNInputTraceFrames 900')
   s['tracing']=True
  if t>6:finish();return
  for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
   if not a.has_valid_agent_handle():continue
   if tag=='Normal':clock.call_method('SetAgentTimeDilation',(a,1.))
   v=a.get_root_velocity()[0]
   r=dict(time=t,name=a.get_name(),rate=clock.call_method('GetAgentTimeDilation',(a,)),auto_run=root.call_method('GetLocomotionAutoRunSpeedThreshold',(a,)),walk_threshold=a.get_locomotion_walk_checkpoint_speed_threshold(),speed=v.length(),state=str(a.get_locomotion_state()),attack=str(a.get_nn_attack_state()),mode=str(a.get_simulation_mode()))
   r['magic']=[str(root.call_method(n,(a,))) for n in ('GetRootMagicVelocity','GetRootMagicVelocity2')]
   cubes=[c for c in a.get_components_by_class(unreal.StaticMeshComponent) if 'magic' in c.get_name().lower()]
   if cubes:
    delta=cubes[0].get_world_location()-a.get_root_low_point()
    r['cube_delta']=[delta.x,delta.y,delta.z]
    r['cube_velocity']=str(cubes[0].get_physics_linear_velocity())
   s['rows'].append(r)
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
