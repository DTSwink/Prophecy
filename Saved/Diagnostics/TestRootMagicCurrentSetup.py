import unreal,json,pathlib,time,traceback,math
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world()
s={'start':time.monotonic(),'rows':[]}
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RootMagicCurrentSetup.json'
def finish(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 if ed.get_game_world():level.editor_request_end_play()
 out.write_text(json.dumps(dict(result='failed' if error else 'passed',error=error,rows=s['rows']),indent=2))
 print('ROOT_MAGIC_CURRENT_SETUP',error or 'passed')
def tick(_):
 try:
  assert time.monotonic()-s['start']<60,'Timeout'
  w=ed.get_game_world()
  if not w:return
  t=unreal.GameplayStatics.get_time_seconds(w)
  if t<3:return
  api=unreal.ProphecyRootPhysicsLibrary
  for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
   if not a.has_valid_agent_handle():continue
   r,ts=api.get_continuous_locomotion_root_window(a)[-2:]
   assert len(r)==9
   assert all(math.isfinite(c) for c in (r[0].translation.x,r[0].translation.y,r[0].translation.z))
   s['rows'].append(dict(agent=a.get_name(),root=str(r[0].translation),magic=str(api.get_root_magic_velocity(a)),angular=str(api.get_root_magic_ang_velocity(a))))
  assert len(s['rows'])>=3
  unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.MeshAudit')
  audit=json.loads((out.parent/'DefaultJoltMeshes/World.json').read_text(encoding='utf-8-sig'))
  assert not audit['shared_stopped'] and not audit['scene_error'] and audit['completed_steps']>=100,audit
  s['rows'].append(dict(steps=audit['completed_steps'],shared_error=audit['shared_error']))
  finish()
 except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
