import unreal,pathlib,json,time,traceback,math
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/GetUpFloorRemoval20261010'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'User Play is active'
assert not hasattr(unreal.ProphecyGetUpLibrary,'set_get_up_floor_correction')
s={'world':None,'started':time.monotonic(),'last':None,'status':[]}
def finish(reason):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 (out/'smoke.json').write_text(json.dumps({'reason':reason,'status':s['status']},indent=2),encoding='utf-8')
 if s['world'] is not None and ed.get_game_world()==s['world']:level.editor_request_end_play()
 print('FLOOR_REMOVAL_SMOKE_FINISHED',reason)
def tick(_):
 try:
  if time.monotonic()-s['started']>90:finish('timeout');return
  w=ed.get_game_world()
  if not w:
   if s['world'] is not None:finish('world ended')
   return
  s['world']=w;a=unreal.GameplayStatics.get_player_pawn(w,0)
  if not isinstance(a,unreal.ProphecyAgent):return
  n=int(a.get_editor_property('absolute tick debug'))
  if s['last']==n:return
  s['last']=n
  assert a.get_simulation_mode()==unreal.ProphecyAgentSimulationMode.PHYSICAL
  if n in [29,30,52,65]:
   names,future,presented,alpha=a.read_nn_future_world_pose()
   assert all(math.isfinite(x) for v in presented for x in [v.translation.x,v.translation.y,v.translation.z,v.rotation.x,v.rotation.y,v.rotation.z,v.rotation.w])
   unreal.SystemLibrary.execute_console_command(w,'Prophecy.GetUp.Inspect')
   data=(out.parent/'GetUp-Inspect.txt').read_bytes();text=data.decode('utf-16' if data.startswith(b'\xff\xfe') else 'utf-8-sig')
   row=next(x for x in text.splitlines() if x.startswith(a.get_name()+' '))
   assert ('active=0' if n==29 else 'active=1') in row,row
   assert 'floor_correction' not in row and 'floor_supports' not in row
   s['status'].append({'tick':n,'value':row})
  if n>=65:finish('passed')
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('FLOOR_REMOVAL_SMOKE_STARTED')
