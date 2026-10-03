import unreal,time,traceback,pathlib,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
s=dict(wall=time.monotonic(),stage=-1,events=[])
def done(error=''):
 unreal.unregister_slate_post_tick_callback(s['cb'])
 # End with the callback enabled to exercise automatic world cleanup.
 if ed.get_game_world():level.editor_request_end_play()
 pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/JoltCollisionView.json').write_text(json.dumps(dict(error=error,events=s['events'])))
 print('JOLT_COLLISION_VIEW_DONE',error or 'passed')
def tick(_):
 try:
  if time.monotonic()-s['wall']>40:done('timeout');return
  w=ed.get_game_world()
  if not w:return
  t=unreal.GameplayStatics.get_time_seconds(w);stage=int(t)
  if stage>=4:done();return
  if stage!=s['stage']:
   s['stage']=stage;mode=[1,2,0,1][stage]
   unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.ShowCollision '+str(mode))
   s['events'].append(dict(time=t,mode=mode))
 except Exception:done(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
