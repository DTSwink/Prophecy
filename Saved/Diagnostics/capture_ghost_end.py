import unreal, pathlib, json, time, traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user PIE'
folder=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/GhostEnd');folder.mkdir(exist_ok=True)
trace=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/SlashContacts/live_steps.jsonl')
offset=trace.stat().st_size if trace.exists() else 0
def cmd(s):unreal.SystemLibrary.execute_console_command(ed.get_game_world() or ed.get_editor_world(),s)
cmd('Prophecy.SlashTraceAgent -2');cmd('Prophecy.SlashTraceFrames 400')
s=dict(start=time.monotonic(),last=None,n=0,rows=[])
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 cmd('Prophecy.SlashTraceFrames 0');cmd('Prophecy.SlashTraceAgent -1')
 (folder/'capture.json').write_text(json.dumps(dict(error=error,rows=s['rows'])),encoding='utf-8')
 if trace.exists():
  with trace.open('rb') as f:f.seek(offset);(folder/'steps.jsonl').write_bytes(f.read())
 if ed.get_game_world():level.editor_request_end_play()
 print('GHOST_END_DONE',error or 'complete',s['n'])
def tick(_):
 try:
  if time.monotonic()-s['start']>90:finish('timeout');return
  w=ed.get_game_world()
  if not w:return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t;s['n']+=1
  for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
   if a.is_player_controlled():s['rows'].append(dict(tick=int(a.get_editor_property('tick debug')),time=t,actor=a.get_name(),attack=str(a.get_nn_attack_state())))
  if s['n']>=430:finish()
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('GHOST_END_STARTED')
