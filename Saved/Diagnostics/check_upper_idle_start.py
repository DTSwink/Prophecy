import unreal,json,pathlib,time,traceback,math
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world()
s={'start':time.monotonic(),'first':{},'rows':[]}
def v(p):return [p.x,p.y,p.z]
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 (pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/UpperIdleStartup.json').write_text(json.dumps(dict(error=error,first=s['first'],rows=s['rows']),indent=2))
 if ed.get_game_world():level.editor_request_end_play()
 print('UPPER_IDLE_STARTUP',error or 'passed')
def tick(_):
 try:
  assert time.monotonic()-s['start']<40,'Timeout'
  w=ed.get_game_world()
  if not w:return
  t=unreal.GameplayStatics.get_time_seconds(w)
  for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
   if not a.has_valid_agent_handle():continue
   pose=a.read_nn_future_world_pose()
   if not pose:continue
   names,future,current,alpha=pose
   lookup={str(n):i for i,n in enumerate(names)}
   row={'agent':a.get_name(),'time':t,'bones':{n:v(current[lookup[n]].translation) for n in ('pelvis','head','upperarm_l','upperarm_r','hand_l','hand_r')}}
   assert all(math.isfinite(c) for xyz in row['bones'].values() for c in xyz)
   if a.get_name() not in s['first']:
    for side in ('l','r'):
     assert row['bones']['upperarm_'+side][2]-row['bones']['hand_'+side][2]>25, str(row)
    s['first'][a.get_name()]=row
   s['rows'].append(row)
  if t>=.15:
   assert len(s['first'])>=3,'Missing scene agents'
   assert max(r['time'] for r in s['first'].values())<.034,'Missed startup seed'
   finish()
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
