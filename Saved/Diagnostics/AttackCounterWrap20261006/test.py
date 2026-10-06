import unreal,pathlib,time,json,traceback
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/AttackCounterWrap20261006'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
s={'world':None,'last':None,'frame':0,'start':time.monotonic(),'values':[]}
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 (p/'test.json').write_text(json.dumps(dict(reason=reason,values=s['values']),indent=2))
 if s['world'] is not None and ed.get_game_world()==s['world']:level.editor_request_end_play()
 print('WRAP_TEST_DONE',reason)
def tick(dt):
 try:
  if time.monotonic()-s['start']>60:finish('timeout');return
  w=ed.get_game_world()
  if w is None:return
  if s['world'] is None:s['world']=w
  if s['world']!=w:finish('world replaced');return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t;s['frame']+=1
  if s['frame']==5:
   for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):a.set_actor_tick_enabled(False)
  if s['frame']==20:
   a=unreal.GameplayStatics.get_player_pawn(w,0);a.stop_nn_attack()
   unreal.get_default_object(unreal.SystemLibrary).call_method('SetInt64PropertyByName',(a,'AttackCounter',9998))
   names,pose,_,_=a.read_nn_future_world_pose();target=pose[[str(n) for n in names].index('pelvis')].translation+unreal.Vector(-30,90,30)
   for expected in (9999,0,1):
    a.stop_nn_attack();assert a.trigger_nn_attack('jabL',target,True)
    actual=a.get_attack_counter();s['values'].append(actual);assert actual==expected,(actual,expected)
    assert a.trigger_nn_attack('jabL',target,True)
    assert a.get_attack_counter()==expected,'Retrigger changed number'
   finish('complete')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play();print('WRAP_TEST_STARTED')
