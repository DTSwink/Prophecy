"""Capture the user's unmodified TestNN fixture through the on-demand inspector."""
import json,pathlib,time,traceback,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Existing user Play preserved'
assert ed.get_editor_world().get_path_name()=='/Game/testNN.testNN'
out=pathlib.Path(unreal.Paths.project_dir())/'Saved/Diagnostics/ReachScenario20261016'
out.mkdir(parents=True,exist_ok=True)
source=out.parent/'ReachElbowHitch20261016/checkpoint.json'
s={'world':None,'last':-1,'rows':[],'start':time.monotonic()}
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 if s['world'] and ed.get_game_world()==s['world']:le.editor_request_end_play()
 (out/'native.json').write_text(json.dumps({'reason':reason,'rows':s['rows']},separators=(',',':')),encoding='utf-8')
 print('REACH_SCENARIO',reason,len(s['rows']))
def tick(_):
 try:
  if time.monotonic()-s['start']>120:return finish('timeout')
  w=ed.get_game_world()
  if not w:
   if s['world']:return finish('ended externally')
   return
  s['world']=w;a=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(a,unreal.ProphecyAgent):return
  n=int(a.get_editor_property('absolute tick debug'))
  if n==s['last']:return
  s['last']=n
  if n>=31:
   unreal.SystemLibrary.execute_console_command(w,'Prophecy.Reach.Inspect Checkpoint')
   row=json.loads(source.read_text(encoding='utf-8'));row['tick']=n;s['rows'].append(row)
  if n>=360:return finish('captured')
 except Exception:return finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
le.editor_request_begin_play();print('REACH_SCENARIO_STARTED')
