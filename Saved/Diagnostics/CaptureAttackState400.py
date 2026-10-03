import unreal,pathlib,json,time,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
s=dict(start=time.monotonic(),last=None,frame=0,rows=[])
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/AttackState400.json').write_text(json.dumps(dict(reason=reason,rows=s['rows']),separators=(',',':')))
 if ed.get_game_world():level.editor_request_end_play()
 print('ATTACK_STATE400_DONE',reason,len(s['rows']))
def tick(_):
 try:
  if time.monotonic()-s['start']>120:finish('Timeout');return
  w=ed.get_game_world()
  if not w:return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t;s['frame']+=1
  for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
   s['rows'].append(dict(tick=int(a.get_editor_property('tick debug')),actor=a.get_name(),player=a.is_player_controlled(),state=str(unreal.ProphecyNNDefenseLibrary.get_agent_state(a)),attack=str(a.get_nn_attack_state())))
  if s['frame']>=540:finish('Complete')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()

