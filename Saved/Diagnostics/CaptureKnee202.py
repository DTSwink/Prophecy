import unreal,pathlib,json,time,traceback,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
tag=sys.argv[1] if len(sys.argv)>1 else 'baseline'
owned=not bool(ed.get_game_world());folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/Knee202';folder.mkdir(exist_ok=True)
paired=tag=='paired'
if paired:
 assert owned,'Do not alter user Play'
 unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Recovery.UpperLengthBlend 0')
trace=folder.parent/'SlashContacts/nn_inputs.jsonl';offset=trace.stat().st_size if trace.exists() else 0
s=dict(rows=[],last=None,wall=time.monotonic(),frame=0,tracing=False)
bones=('pelvis','thigh_l','calf_l','foot_l','ball_l','thigh_r','calf_r','foot_r','ball_r')
def tr(x):return dict(p=[x.translation.x,x.translation.y,x.translation.z],q=[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w],s=[x.scale3d.x,x.scale3d.y,x.scale3d.z])
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 if s['tracing']:unreal.SystemLibrary.execute_console_command(ed.get_game_world() or ed.get_editor_world(),'Prophecy.NNInputTraceFrames 0')
 if paired:unreal.SystemLibrary.execute_console_command(ed.get_game_world() or ed.get_editor_world(),'Prophecy.Recovery.UpperLengthBlend 1')
 if trace.exists():
  with trace.open('rb') as f:f.seek(offset);(folder/(tag+'_nn.jsonl')).write_bytes(f.read())
 (folder/(tag+'.json')).write_text(json.dumps(dict(reason=reason,owned=owned,rows=s['rows']),separators=(',',':')))
 if owned and ed.get_game_world():level.editor_request_end_play()
 print('KNEE202_DONE',reason,len(s['rows']));s['rows'].clear()
def tick(_):
 try:
  w=ed.get_game_world()
  if not w:
   if s['frame'] or time.monotonic()-s['wall']>60:finish('No world')
   return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:
   if time.monotonic()-s['wall']>120:finish('Paused timeout')
   return
  s['last']=t;s['frame']+=1
  for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
   if not a.is_player_controlled():continue
   clock=int(a.get_editor_property('tick debug'))
   if owned and clock>=175 and not s['tracing']:
    unreal.SystemLibrary.execute_console_command(w,'Prophecy.NNInputTraceFrames 200');s['tracing']=True
    a.set_foot_pinning_debug_enabled(True)
   r=dict(t=t,tick=clock,actor=a.get_name(),attack=str(a.get_nn_attack_state()),mode=str(a.get_simulation_mode()),pin=str(a.get_locomotion_foot_pinning()),weights=list(a.get_locomotion_checkpoint_weights()),meshes={},targets={},raw={})
   for m in a.get_components_by_class(unreal.SkeletalMeshComponent):
    r['meshes'][m.get_name()]={b:tr(m.get_socket_transform(b,unreal.RelativeTransformSpace.RTS_WORLD)) for b in bones if m.get_bone_index(b)>=0}
   for b in bones:
    target=a.get_authored_body_world_target(b)
    if target:r['targets'][b]=dict(previous=tr(target[0]),future=tr(target[1]),target=tr(target[2]),alpha=target[3])
   pose=a.read_nn_future_world_pose()
   if pose:
    names,future,presented,alpha=pose;r['alpha']=alpha
    r['raw']={str(b):dict(future=tr(future[i]),presented=tr(presented[i])) for i,b in enumerate(names) if str(b) in bones}
   if paired and 185<=clock<=215:
    unreal.SystemLibrary.execute_console_command(w,'Prophecy.Recovery.UpperLengthBlend 1')
    try:
     r['consistent_upper']={}
     for b in bones:
      target=a.get_authored_body_world_target(b)
      if target:r['consistent_upper'][b]=tr(target[2])
    finally:unreal.SystemLibrary.execute_console_command(w,'Prophecy.Recovery.UpperLengthBlend 0')
   s['rows'].append(r)
  if s['frame']>=280:finish('Complete')
  elif time.monotonic()-s['wall']>120:finish('Timeout')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
if owned:level.editor_request_begin_play()
print('KNEE202_STARTED',tag,'owned',owned)
