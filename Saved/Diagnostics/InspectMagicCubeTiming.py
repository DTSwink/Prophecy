import unreal,json,pathlib,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
s={'owned':not bool(ed.get_game_world()),'rows':[],'start':time.monotonic(),'frames':0}
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/MagicCubeTiming.json'
def xyz(v):return [v.x,v.y,v.z]
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 if s['owned'] and ed.get_game_world():level.editor_request_end_play()
 out.write_text(json.dumps({'error':error,'rows':s['rows']},indent=2))
 print('MAGIC_CUBE_CAPTURE',len(s['rows']),error)
def tick(_):
 try:
  w=ed.get_game_world()
  if not w:
   if time.monotonic()-s['start']>30:finish('No PIE world')
   return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t<.5:return
  actors=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
  for a in actors:
   meshes=[m for m in a.get_components_by_class(unreal.StaticMeshComponent) if 'magic' in m.get_name().lower()]
   if not meshes:continue
   result=unreal.ProphecyRootPhysicsLibrary.get_continuous_locomotion_root_window(a)
   if result is None:continue
   roots,times=result[-2:]
   m=meshes[0]
   s['rows'].append(dict(t=t,dt=unreal.GameplayStatics.get_world_delta_seconds(w),actor=a.get_name(),cube=xyz(m.get_world_location()),velocity=xyz(m.get_physics_linear_velocity()),root0=xyz(roots[0].translation),root1=xyz(roots[1].translation),offsets=list(times)))
  s['frames']+=1
  if s['frames']>=180:finish()
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
if s['owned']:level.editor_request_begin_play()
