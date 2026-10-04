import unreal,time,json,traceback,math
from pathlib import Path
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
out=Path(unreal.Paths.project_saved_dir())/'Diagnostics/FKLabPort20261004/scene.json'
s={'start':time.monotonic(),'last':None,'ticks':0,'agents':0,'pose_samples':0,'settings':False,'rows':[]}
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['callback'])
 w=ed.get_game_world()
 if w:unreal.SystemLibrary.execute_console_command(w,'Prophecy.FKReturn.Audit 0')
 report={k:v for k,v in s.items() if k not in ('callback','start')};report['error']=error
 out.write_text(json.dumps(report,indent=2));print('FK_LAB_SCENE_DONE',error or 'complete')
 if w:level.editor_request_end_play()
def tick(_):
 try:
  if time.monotonic()-s['start']>240:finish('timeout');return
  w=ed.get_game_world()
  if not w:return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t;s['ticks']+=1
  agents=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
  if not agents:return
  if not s['settings']:
   unreal.SystemLibrary.execute_console_command(w,'Prophecy.FKReturn.Audit 1');s['agents']=len(agents);s['settings']=True
  if s['ticks']%4==0:
   for a in agents:
    try:names,future,presented,alpha=a.read_nn_future_world_pose()
    except Exception:continue
    if not names:continue
    assert len(names)==len(future)==len(presented)
    for tr in presented:
     assert all(math.isfinite(v) and abs(v)<1e8 for v in [tr.translation.x,tr.translation.y,tr.translation.z,tr.rotation.x,tr.rotation.y,tr.rotation.z,tr.rotation.w])
    s['pose_samples']+=1
    if s['ticks']%20==0:s['rows'].append({'tick':s['ticks'],'actor':a.get_name(),'state':str(a.get_nn_attack_state()),'bones':len(names),'alpha':alpha})
  if s['ticks']>=600:finish()
 except Exception:finish(traceback.format_exc())
s['callback']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
