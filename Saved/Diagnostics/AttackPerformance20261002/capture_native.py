import unreal,pathlib,time,json,traceback
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
initial=ed.get_game_world();owned=initial is None
assert owned,'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Attack.NativeGeometry 1')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.ClearAttackCache')
root=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/AttackPerformance20261002'
s=dict(world=initial,started=False,last=None,ticks=0,start=time.monotonic(),owned=owned)
tag='oct02_native_a';frames=800

def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 w=ed.get_game_world()
 if s['started'] and w==s['world']:unreal.SystemLibrary.execute_console_command(w,'Prophecy.AttackPerf.Capture stop')
 (root/(tag+'-receipt.json')).write_text(json.dumps(dict(reason=reason,owned=owned,ticks=s['ticks']),indent=2),encoding='utf8')
 if owned and w is not None and w==s['world']:level.editor_request_end_play()
 print('ATTACK_COST_CAPTURE_DONE',reason,s['ticks'])

def tick(_):
 try:
  if time.monotonic()-s['start']>120:finish('Watchdog');return
  w=ed.get_game_world()
  if not w:
   if s['started']:finish('World ended')
   return
  if s['world'] is None:s['world']=w
  elif w!=s['world']:finish('World replaced');return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t==s['last']:return
  s['last']=t;s['ticks']+=1
  if not s['started'] and (not owned or s['ticks']>=30):
   agents=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)
   managers=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyNNLocomotionManager)
   info=dict(owned=owned,agents=[dict(name=a.get_name(),mode=str(a.get_simulation_mode()),inference=a.get_editor_property('bNNInferenceEnabled'),player=a.is_player_controlled()) for a in agents],managers=[dict(name=m.get_name(),crowd=m.get_editor_property('CrowdSize'),runtime=m.get_editor_property('PreferredRuntime')) for m in managers])
   (root/(tag+'-settings.json')).write_text(json.dumps(info,indent=2),encoding='utf8')
   unreal.SystemLibrary.execute_console_command(w,'Prophecy.AttackPerf.Capture '+tag+' '+str(frames));s['started']=True;s['start_tick']=s['ticks']
  if s['started'] and s['ticks']>=s['start_tick']+frames+1:finish('Complete')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
if owned:level.editor_request_begin_play()
print('ATTACK_COST_CAPTURE_STARTED',owned)

