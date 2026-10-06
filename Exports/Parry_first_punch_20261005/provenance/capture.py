import unreal,json,pathlib,time,traceback,shutil
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert ed.get_game_world() is None
p=pathlib.Path(unreal.Paths.project_dir())/'Exports/Parry_first_punch_20261005'
assert not p.exists(),'Do not overwrite an existing export'
p.mkdir(parents=True);raw=p/'reference_unreal';raw.mkdir()
trace=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/ParryExport/NativeTrace'
slash=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SlashContacts/live_steps.jsonl'
cv=['Prophecy.Debug.ParryTrace','Prophecy.SlashTraceAgent','Prophecy.SlashTraceFrames']
s={'world':None,'last':None,'start':time.monotonic(),'rows':[],'old':{c:unreal.SystemLibrary.get_console_variable_int_value(c) for c in cv},'seen':{f.name:f.stat().st_mtime_ns for f in trace.glob('*.json')},'slash_offset':slash.stat().st_size if slash.exists() else 0}
def vec(v):return [v.x,v.y,v.z]
def tr(t):return {'p_cm':vec(t.translation),'q_xyzw':[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w]}
def pose(a):
 result=a.read_nn_future_world_pose();assert result
 names,future,visible,alpha=result
 return {'names':[str(n) for n in names],'future':[tr(t) for t in future],'visible':[tr(t) for t in visible],'alpha':alpha,'previous':[tr(a.get_authored_body_world_target(n)[0]) for n in names]}
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 for c,v in s['old'].items():unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),c+' '+str(v))
 (raw/'capture.json').write_text(json.dumps({'reason':reason,'rows':s['rows'],'original_cvars':s['old'],'first_punch_start':s.get('punch_start'),'first_punch_family':s.get('punch_family')},indent=2))
 if slash.exists():
  with slash.open('rb') as f:f.seek(s['slash_offset']);(raw/'attack_nn_diagnostic.jsonl').write_bytes(f.read())
 if s['world'] and ed.get_game_world()==s['world']:level.editor_request_end_play()
 print('EXPORT_CAPTURE_DONE',reason,len(s['rows']),str(p))
def tick(_):
 try:
  if time.monotonic()-s['start']>150:finish('timeout');return
  w=ed.get_game_world()
  if not w:return
  a=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(a,unreal.ProphecyAgent):return
  n=int(a.get_editor_property('tick debug'))
  if n==s['last']:return
  s['last']=n
  victim=next((x for x in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent) if x.get_actor_label()=='BP_ProphecyManualPoseAgent4'),None)
  if victim is None:return
  if s['world'] is None:s['world']=w
  if not s.get('tracing'):
   unreal.SystemLibrary.execute_console_command(w,cv[0]+' 1');unreal.SystemLibrary.execute_console_command(w,cv[1]+' -2');unreal.SystemLibrary.execute_console_command(w,cv[2]+' 100');s['tracing']=True
  if n>=0:
   attack=a.get_nn_attack_state();d=unreal.ProphecyNNDefenseLibrary.get_nn_defense_status(victim)
   target=a.get_nn_attack_target()
   r={'tick':n,'world_time':unreal.GameplayStatics.get_time_seconds(w),'attack':{'family':str(attack[0]),'half':attack[1],'armed':attack[2],'hit':attack[3],'frame':attack[4]} if attack else None,'target':{'requested_cm':vec(target[0]),'effective_cm':vec(target[1]),'ghost_cm':vec(target[2])} if target else None,'attacker':pose(a),'defender':pose(victim),'defense':{'active':d.active,'steps':d.completed_steps,'attacker_frame':d.attacker_frame} if d else None,'defender_mode':str(unreal.ProphecyNNDefenseLibrary.get_agent_state(victim)),'defense_delay':list(unreal.ProphecyNNDefenseLibrary.get_defense_frames_after_hit(victim)),'attacker_name':a.get_name(),'defender_name':victim.get_name()}
   s['rows'].append(r)
   for f in trace.glob('*.json'):
    stamp=f.stat().st_mtime_ns
    if s['seen'].get(f.name)!=stamp:
     s['seen'][f.name]=stamp;shutil.copy2(f,raw/(str(n).zfill(4)+'_'+f.name))
  if attack and str(attack[0]).lower().startswith(('hook','jab','over','upper')) and not s.get('punch_start'):
   s['punch_start']=n;s['punch_family']=str(attack[0]);s['punch_frame']=attack[4]
  if s.get('punch_start') and (not attack or str(attack[0])!=s['punch_family'] or attack[4]<s['punch_frame']):finish('complete')
  elif n>=1800:finish('no completed first punch within 1800 ticks')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play();print('EXPORT_CAPTURE_STARTED',str(p))
