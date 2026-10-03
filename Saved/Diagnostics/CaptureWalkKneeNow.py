import unreal,builtins,pathlib,json,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
s=dict(rows=[],last=None,wall=time.monotonic(),frame=0,trace=False)
builtins._walk_knee_now=s
w0=ed.get_editor_world()
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
trace=folder/'SlashContacts/nn_inputs.jsonl'
offset=trace.stat().st_size if trace.exists() else 0
bones=('pelvis','thigh_l','calf_l','foot_l','ball_l','thigh_r','calf_r','foot_r','ball_r')
def tr(x):
 return dict(p=[x.translation.x,x.translation.y,x.translation.z],q=[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w],s=[x.scale3d.x,x.scale3d.y,x.scale3d.z])
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 unreal.SystemLibrary.execute_console_command(ed.get_game_world() or w0,'Prophecy.NNInputTraceFrames 0')
 if trace.exists():
  with trace.open('rb') as f:f.seek(offset);(folder/'WalkKneeNow-nn.jsonl').write_bytes(f.read())
 (folder/'WalkKneeNow-capture.json').write_text(json.dumps(dict(reason=reason,rows=s['rows']),separators=(',',':')))
 if ed.get_game_world():unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
 print('WALK_KNEE_NOW_DONE',reason,len(s['rows']))
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
  if clock>=99999 and not s['trace']:
   unreal.SystemLibrary.execute_console_command(w,'Prophecy.NNInputTraceFrames 480');s['trace']=True
  if clock>=20:
   for a in agents:
    if not a.is_player_controlled():continue
    a.set_foot_pinning_debug_enabled(True)
    r=dict(frame=s['frame'],tick=int(a.get_editor_property('tick debug')),clock=clock,t=t,actor=a.get_name(),possessed=a.is_player_controlled(),mode=str(a.get_simulation_mode()),attack=str(a.get_nn_attack_state()),pin=str(a.get_locomotion_foot_pinning()),weights=list(a.get_locomotion_checkpoint_weights()),meshes={},targets={},raw={})
    for m in a.get_components_by_class(unreal.SkeletalMeshComponent):
     r['meshes'][m.get_name()]={b:tr(m.get_socket_transform(b,unreal.RelativeTransformSpace.RTS_WORLD)) for b in bones if m.get_bone_index(b)>=0}
    for b in bones:
     target=a.get_authored_body_world_target(b)
     if target:r['targets'][b]=dict(previous=tr(target[0]),future=tr(target[1]),target=tr(target[2]),alpha=target[3])
    pose=a.read_nn_future_world_pose()
    if pose:
     names,future,presented,alpha=pose
     r['raw']={str(b):dict(future=tr(future[i]),presented=tr(presented[i])) for i,b in enumerate(names) if str(b) in bones}
     r['alpha']=alpha
    s['rows'].append(r)
  if clock>=360:finish('Complete')
  elif time.monotonic()-s['wall']>180:finish('Timeout')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('WALK_KNEE_NOW_STARTED')
