import builtins,json,pathlib,time,traceback,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
s=dict(owned=not bool(ed.get_game_world()),start=time.monotonic(),rows=[],last=-1)
builtins._walk_bound_capture=s
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyRootPhysicsLibrary'))
def xyz(v):return [v.x,v.y,v.z]
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/WalkBoundMismatch.json').write_text(json.dumps(dict(reason=reason,rows=s['rows'])))
 if s['owned'] and ed.get_game_world():unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
def tick(_):
 try:
  if time.monotonic()-s['start']>35:finish('timeout');return
  w=ed.get_game_world()
  if not w:return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t
  a=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(a,unreal.ProphecyAgent):return
  sample=a.get_locomotion_foot_pinning()
  roots=lib.call_method('GetContinuousLocomotionRootWindow',(a,))
  meshes=a.get_components_by_class(unreal.SkinnedMeshComponent)
  s['rows'].append(dict(t=t,pin=str(sample),roots=[dict(p=xyz(r.translation),yaw=r.rotation.rotator().yaw) for r in roots[0]] if roots else [],meshes=[dict(name=m.get_name(),feet=[xyz(m.get_socket_location(b)) for b in ['foot_l','foot_r']]) for m in meshes]))
  if len(s['rows'])>=240:finish('complete')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
if s['owned']:unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
