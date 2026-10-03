import unreal,pathlib,json,time,traceback,builtins
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
trace=folder/'SlashContacts/nn_inputs.jsonl';offset=trace.stat().st_size if trace.exists() else 0
s=dict(rows=[],last=None,start=time.monotonic(),trace=False)
builtins._pin216=s
def tr(x):return dict(p=[x.translation.x,x.translation.y,x.translation.z],q=[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w])
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 w=ed.get_game_world()
 unreal.SystemLibrary.execute_console_command(w or ed.get_editor_world(),'Prophecy.NNInputTraceFrames 0')
 if trace.exists():
  with trace.open('rb') as f:f.seek(offset);(folder/'Pin216-nn.jsonl').write_bytes(f.read())
 (folder/'Pin216.json').write_text(json.dumps(dict(reason=reason,rows=s['rows']),separators=(',',':')))
 if w:unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
 print('PIN216_DONE',reason,len(s['rows']))
 s['rows'].clear()
def tick(dt):
 try:
  w=ed.get_game_world()
  if not w:
   if time.monotonic()-s['start']>30:finish('No world')
   return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if s['last']==t:return
  s['last']=t
  for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
   if not a.is_player_controlled():continue
   n=int(a.get_editor_property('tick debug'))
   if n>=150 and not s['trace']:
    a.set_foot_pinning_debug_enabled(True)
    unreal.SystemLibrary.execute_console_command(w,'Prophecy.NNInputTraceFrames 60');s['trace']=True
   if n>=180:
    sample=a.get_locomotion_foot_pinning()
    roots=unreal.ProphecyRootPhysicsLibrary.get_continuous_locomotion_root_window(a)
    r=dict(tick=n,time=t,actor=a.get_name(),attack=str(a.get_nn_attack_state()),pin=str(sample),weights=list(a.get_locomotion_checkpoint_weights()),roots=[tr(x) for x in roots[0]] if roots else [],targets={})
    for b in ('pelvis','thigh_l','calf_l','foot_l','thigh_r','calf_r','foot_r'):
     target=a.get_authored_body_world_target(b)
     if target:r['targets'][b]=[tr(x) for x in target[:3]]
    s['rows'].append(r)
   if n>=230:finish('Complete');return
  if time.monotonic()-s['start']>90:finish('Timeout')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
print('PIN216_STARTED')
