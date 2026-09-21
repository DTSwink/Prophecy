import unreal,json,pathlib,time,traceback,sys
mode=sys.argv[1] if len(sys.argv)>1 else 'baseline'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world()
s={'rows':[],'agents':[],'start':time.monotonic(),'last':None}
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RootCubeRunaway'
def vec(v):return [v.x,v.y,v.z]
def api(name):return unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.'+name))
bounds=api('ProphecyRootPelvisBoundsLibrary');limits=api('ProphecyRootSpeedLimitsLibrary')
root=unreal.ProphecyRootPhysicsLibrary
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 (out/(mode+'.json')).write_text(json.dumps(dict(reason=reason,rows=s['rows']),separators=(',',':')))
 if ed.get_game_world():level.editor_request_end_play()
 print('ROOT_CUBE_CAPTURE',mode,reason,len(s['rows']))
def tick(_):
 try:
  if time.monotonic()-s['start']>75:return finish('wall timeout')
  w=ed.get_game_world()
  if not w:return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t
  if not s['agents']:
   s['agents']=list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent))
  for a in s['agents']:
   if not a.has_valid_agent_handle():continue
   comps=a.get_components_by_class(unreal.StaticMeshComponent)
   cube=next((c for c in comps if 'magic' in c.get_name().lower()),None)
   if not cube:continue
   cfg=bounds.call_method('GetRootPelvisBounds',(a,));cap=limits.call_method('GetRootVelocityLimits',(a,))
   if mode=='no_bounds':bounds.call_method('SetRootPelvisBounds',(a,False,50.0,None))
   if mode=='no_caps':limits.call_method('SetRootVelocityLimits',(a,1000000.0,1000000.0,False))
   if mode=='no_cube_shift' and cfg[0]:bounds.call_method('SetRootPelvisBounds',(a,True,cfg[1],None))
   if mode=='no_feedback':a.set_physical_feedback_tolerance_below('pelvis',True,1000000.0,1000000.0)
   window=root.get_continuous_locomotion_root_window(a)
   pelvis=a.get_physical_body_state('pelvis')
   velocity=a.get_root_velocity()
   r=dict(t=t,a=a.get_name(),root=vec(a.get_root_low_point()),cube=vec(cube.get_world_location()),
    cv=vec(cube.get_component_velocity()),magic=vec(root.get_root_magic_velocity(a)),magic2=vec(root.get_root_magic_velocity2(a)),
    bounds=list(cfg),caps=list(cap),rv=[vec(v) for v in velocity] if velocity else [])
   if window:r['window']=[vec(x.translation) for x in window[0]]
   if pelvis:r['pelvis']=vec(pelvis[0].translation);r['pv']=vec(pelvis[1])
   pose=a.read_nn_future_world_pose()
   if pose:
    names,future,current,alpha=pose
    pi=next((i for i,n in enumerate(names) if str(n)=='pelvis'),None)
    if pi is not None:r['target']=vec(current[pi].translation);r['future_target']=vec(future[pi].translation)
   try:r['tick']=a.get_editor_property('tick debug')
   except:pass
   s['rows'].append(r)
  if t>=10:finish('complete')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
