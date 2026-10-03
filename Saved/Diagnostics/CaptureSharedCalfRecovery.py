import unreal,builtins,pathlib,json,time,traceback,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
mode=sys.argv[1] if len(sys.argv)>1 else 'paired'
assert mode in ('baseline','paired','all')
s=dict(rows=[],last=None,wall=time.monotonic(),frame=0,enabled=mode=='all')
builtins._sharedcalfcapture=s
w0=ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w0,'Prophecy.Debug.SharedCalfRecovery '+str(int(s['enabled'])))
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
bones=('pelvis','thigh_l','calf_l','foot_l','ball_l','thigh_r','calf_r','foot_r','ball_r')
def tr(x):
 return dict(p=[x.translation.x,x.translation.y,x.translation.z],q=[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w],s=[x.scale3d.x,x.scale3d.y,x.scale3d.z])
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 unreal.SystemLibrary.execute_console_command(ed.get_game_world() or w0,'Prophecy.Debug.SharedCalfRecovery 1')
 (folder/('SharedCalf-'+mode+'.json')).write_text(json.dumps(dict(reason=reason,rows=s['rows']),separators=(',',':')))
 if ed.get_game_world():unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
 print('SHARED_CALF_DONE',mode,reason,len(s['rows']))
 s['rows'].clear()
def tick(_):
 try:
  w=ed.get_game_world()
  if not w:
   if time.monotonic()-s['wall']>60:finish('No world')
   return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t;s['frame']+=1
  agents=list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent))
  ticks=[int(a.get_editor_property('tick debug')) for a in agents if a.is_player_controlled()]
  clock=ticks[0] if ticks else s['frame']
  if mode=='paired' and clock>=1493 and not s['enabled']:
   unreal.SystemLibrary.execute_console_command(w,'Prophecy.Debug.SharedCalfRecovery 1');s['enabled']=True
  if clock>=1380 or mode=='all':
   for a in agents:
    if not a.is_player_controlled():continue
    r=dict(frame=s['frame'],tick=int(a.get_editor_property('tick debug')),clock=clock,t=t,actor=a.get_name(),possessed=True,mode=str(a.get_simulation_mode()),attack=str(a.get_nn_attack_state()),meshes={},targets={})
    for m in a.get_components_by_class(unreal.SkeletalMeshComponent):
     r['meshes'][m.get_name()]={b:tr(m.get_socket_transform(b,unreal.RelativeTransformSpace.RTS_WORLD)) for b in bones if m.get_bone_index(b)>=0}
    for b in bones:
     target=a.get_authored_body_world_target(b)
     if target:r['targets'][b]=dict(previous=tr(target[0]),future=tr(target[1]),target=tr(target[2]),alpha=target[3])
    s['rows'].append(r)
  if clock>=1565:finish('Complete')
  elif time.monotonic()-s['wall']>180:finish('Timeout')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('SHARED_CALF_STARTED',mode)
